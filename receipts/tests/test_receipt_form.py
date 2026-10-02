from datetime import date, datetime, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from receipts.models import DUPLICATE_MESSAGE, Receipt

URL = "/receipts/new/"


@override_settings(
    PROMO_START_DATE=date(2026, 1, 1),
    PROMO_END_DATE=date(2026, 3, 31),
)
class ReceiptRegistrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user("buyer")
        cls.other = User.objects.create_user("other")

    def setUp(self):
        self.client.force_login(self.user)
        # «Сейчас» фиксируем после конца периода, чтобы тесты не зависели от даты запуска.
        now = patch(
            "django.utils.timezone.now",
            return_value=datetime(2026, 4, 15, 12, 0, tzinfo=dt_timezone.utc),
        )
        now.start()
        self.addCleanup(now.stop)

    def post(self, **overrides):
        data = {
            "fn": "1234567890123456",
            "fd": "10",
            "fp": "20",
            "purchased_at": "2026-02-10T12:00",
            "amount": "1500",
        }
        data.update(overrides)
        return self.client.post(URL, data)

    def assertRejected(self, response, field):
        self.assertEqual(response.status_code, 400)
        self.assertIn(field, response.json()["errors"])

    def test_valid_receipt_is_created_pending_for_current_user(self):
        response = self.post()
        self.assertEqual(response.status_code, 201)
        receipt = Receipt.objects.get()
        self.assertEqual(receipt.status, Receipt.Status.PENDING)
        self.assertEqual(receipt.user, self.user)

    def test_status_and_user_from_request_are_ignored(self):
        response = self.post(status="accepted", user=self.other.pk)
        self.assertEqual(response.status_code, 201)
        receipt = Receipt.objects.get()
        self.assertEqual(receipt.status, Receipt.Status.PENDING)
        self.assertEqual(receipt.user, self.user)

    def test_anonymous_cannot_create(self):
        self.client.logout()
        response = self.post()
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Receipt.objects.exists())

    def test_amount_boundary(self):
        self.assertRejected(self.post(fd="1", amount="999.99"), "amount")
        self.assertEqual(self.post(fd="2", amount="1000").status_code, 201)

    def test_amount_accepts_comma_and_spaces(self):
        self.assertEqual(self.post(amount="1 500,50").status_code, 201)
        self.assertEqual(str(Receipt.objects.get().amount), "1500.50")

    def test_amount_rejects_garbage(self):
        for index, value in enumerate(["abc", "-5", "1e5", "Infinity", "1000.555", ""]):
            with self.subTest(value=value):
                self.assertRejected(self.post(fd=str(index + 1), amount=value), "amount")

    def test_period_boundaries(self):
        cases = {
            "2025-12-31T23:59": 400,
            "2026-01-01T00:00": 201,
            "2026-02-10T12:00": 201,
            "2026-03-31T23:59": 201,
            "2026-04-01T00:00": 400,
        }
        for index, (value, expected) in enumerate(cases.items()):
            with self.subTest(purchased_at=value):
                response = self.post(fd=str(index + 1), purchased_at=value)
                self.assertEqual(response.status_code, expected)

    def test_purchase_time_is_read_in_promo_timezone(self):
        self.post(purchased_at="2026-01-01T00:00")
        # PROMO_TIMEZONE=Europe/Moscow (UTC+3)
        self.assertEqual(
            Receipt.objects.get().purchased_at,
            datetime(2025, 12, 31, 21, 0, tzinfo=dt_timezone.utc),
        )

    def test_purchase_in_future_is_rejected(self):
        # «Сейчас» — 20 февраля, 15:00 по Москве.
        moment = datetime(2026, 2, 20, 12, 0, tzinfo=dt_timezone.utc)
        with patch("django.utils.timezone.now", return_value=moment):
            self.assertEqual(self.post(fd="1", purchased_at="2026-02-20T14:59").status_code, 201)
            self.assertRejected(self.post(fd="2", purchased_at="2026-02-20T15:01"), "purchased_at")

    def test_garbage_date_is_rejected(self):
        self.assertRejected(self.post(purchased_at="мусор"), "purchased_at")

    def test_requisites_format(self):
        self.assertRejected(self.post(fn="123"), "fn")
        self.assertRejected(self.post(fn="12345678901234ab"), "fn")
        self.assertRejected(self.post(fd="12345678901"), "fd")
        self.assertRejected(self.post(fp="x1"), "fp")
        self.assertFalse(Receipt.objects.exists())

    def test_required_fields(self):
        response = self.client.post(URL, {})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            set(response.json()["errors"]),
            {"fn", "fd", "fp", "purchased_at", "amount"},
        )

    def test_duplicate_is_rejected_with_message(self):
        self.post()
        response = self.post()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["errors"]["__all__"], [DUPLICATE_MESSAGE])
        self.assertEqual(Receipt.objects.count(), 1)

    def test_duplicate_from_another_user_is_rejected(self):
        self.post()
        self.client.force_login(self.other)
        response = self.post()
        self.assertEqual(response.json()["errors"]["__all__"], [DUPLICATE_MESSAGE])

    def test_leading_zeros_do_not_make_a_new_receipt(self):
        self.post(fd="10", fp="20")
        response = self.post(fd="0010", fp="020")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Receipt.objects.count(), 1)

    def test_rejected_receipt_can_be_registered_again(self):
        self.post()
        Receipt.objects.update(status=Receipt.Status.REJECTED, reject_reason="Нечитаемый чек")
        self.assertEqual(self.post().status_code, 201)
        self.assertEqual(Receipt.objects.count(), 2)

    def test_accepted_receipt_cannot_be_registered_again(self):
        self.post()
        Receipt.objects.update(status=Receipt.Status.ACCEPTED)
        self.assertEqual(self.post().status_code, 400)

    def test_race_on_duplicate_gives_message_not_500(self):
        self.post()
        # Форма «не заметила» дубль, как при двух одновременных запросах:
        # срабатывает уникальный индекс в базе.
        with patch.object(Receipt, "clean", lambda self: None):
            response = self.post()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["errors"]["__all__"], [DUPLICATE_MESSAGE])
        self.assertEqual(Receipt.objects.count(), 1)
