from datetime import datetime, timedelta, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from receipts.models import Receipt

BASE_TIME = datetime(2026, 2, 1, 9, 0, tzinfo=dt_timezone.utc)


def make_receipt(user, number, **overrides):
    fields = {
        "fn": "1234567890123456",
        "fd": str(number),
        "fp": "20",
        "purchased_at": BASE_TIME + timedelta(hours=number),
        "amount": "1500",
        "user": user,
    }
    fields.update(overrides)
    return Receipt.objects.create(**fields)


class CabinetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user("buyer")
        cls.other = User.objects.create_user("other")
        cls.url = reverse("cabinet")

    def setUp(self):
        self.client.force_login(self.user)

    def numbers(self, response):
        return [receipt.fd for receipt in response.context["page"]]

    def test_anonymous_is_redirected_to_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('login')}?next={self.url}")

    def test_empty_cabinet(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Вы не добавили еще ни одного чека")
        self.assertContains(response, reverse("receipt_create"))

    def test_shows_only_own_receipts(self):
        make_receipt(self.user, 1)
        make_receipt(self.other, 2)
        response = self.client.get(self.url)
        self.assertEqual(self.numbers(response), ["1"])
        self.assertEqual(response.context["total"], 1)

    def test_ordered_by_purchase_date_newest_first(self):
        make_receipt(self.user, 2)
        make_receipt(self.user, 3)
        make_receipt(self.user, 1)
        self.assertEqual(self.numbers(self.client.get(self.url)), ["3", "2", "1"])

    def test_same_purchase_date_keeps_stable_order(self):
        for number in (1, 2, 3):
            make_receipt(self.user, number, purchased_at=BASE_TIME)
        self.assertEqual(self.numbers(self.client.get(self.url)), ["3", "2", "1"])

    def test_pagination_by_ten(self):
        for number in range(1, 26):
            make_receipt(self.user, number)
        first = self.client.get(self.url)
        self.assertEqual(len(self.numbers(first)), 10)
        self.assertEqual(first.context["total"], 25)
        self.assertEqual(first.context["page"].paginator.num_pages, 3)
        last = self.client.get(self.url, {"page": 3})
        self.assertEqual(self.numbers(last), ["5", "4", "3", "2", "1"])

    def test_wrong_page_number_does_not_fail(self):
        make_receipt(self.user, 1)
        for value in ("abc", "0", "99", "-1"):
            with self.subTest(page=value):
                self.assertEqual(self.client.get(self.url, {"page": value}).status_code, 200)

    def test_status_and_reject_reason_are_shown(self):
        make_receipt(
            self.user,
            1,
            status=Receipt.Status.REJECTED,
            reject_reason="Магазин не участвует в акции",
        )
        make_receipt(self.user, 2)
        response = self.client.get(self.url)
        self.assertContains(response, "Отклонён")
        self.assertContains(response, "Магазин не участвует в акции")
        self.assertContains(response, "Чек в обработке")

    def test_dates_are_shown_in_promo_timezone(self):
        make_receipt(self.user, 1, purchased_at=datetime(2026, 2, 1, 21, 30, tzinfo=dt_timezone.utc))
        # 21:30 UTC — это 00:30 следующего дня по Москве.
        self.assertContains(self.client.get(self.url), "00:30 02.02.2026")
