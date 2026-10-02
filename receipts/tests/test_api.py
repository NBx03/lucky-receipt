from datetime import datetime, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from receipts.models import Receipt

from .test_cabinet import make_receipt


class ReceiptsApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user("buyer")
        cls.other = User.objects.create_user("other")
        cls.staff = User.objects.create_user("moderator", is_staff=True)
        cls.url = reverse("api_receipts")

    def test_url(self):
        self.assertEqual(self.url, "/api/receipts/")

    def test_anonymous_gets_json_error_not_redirect(self):
        make_receipt(self.user, 1)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertNotIn("fd", response.content.decode())

    def test_returns_only_own_receipts(self):
        make_receipt(self.user, 1)
        make_receipt(self.other, 2)
        self.client.force_login(self.user)
        data = self.client.get(self.url).json()
        self.assertEqual([item["fd"] for item in data], ["1"])

    def test_query_parameters_cannot_widen_the_selection(self):
        make_receipt(self.user, 1)
        make_receipt(self.other, 2)
        self.client.force_login(self.user)
        params = [
            {"user": self.other.pk},
            {"user_id": self.other.pk},
            {"username": "other"},
            {"user__username": "other"},
            {"all": "1"},
            {"id": make_receipt(self.other, 3).pk},
        ]
        for query in params:
            with self.subTest(query=query):
                data = self.client.get(self.url, query).json()
                self.assertEqual([item["fd"] for item in data], ["1"])

    def test_staff_sees_only_own_receipts(self):
        make_receipt(self.user, 1)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.url).json(), [])

    def test_ordered_by_purchase_date_newest_first(self):
        for number in (2, 3, 1):
            make_receipt(self.user, number)
        self.client.force_login(self.user)
        data = self.client.get(self.url).json()
        self.assertEqual([item["fd"] for item in data], ["3", "2", "1"])

    def test_item_format(self):
        make_receipt(
            self.user,
            1,
            amount="1500.5",
            purchased_at=datetime(2026, 2, 1, 21, 30, tzinfo=dt_timezone.utc),
            status=Receipt.Status.REJECTED,
            reject_reason="Магазин не участвует в акции",
        )
        self.client.force_login(self.user)
        (item,) = self.client.get(self.url).json()
        self.assertEqual(
            {key: item[key] for key in item if key not in ("id", "created_at")},
            {
                "fn": "1234567890123456",
                "fd": "1",
                "fp": "20",
                "purchased_at": "2026-02-02T00:30:00+03:00",
                "amount": "1500.50",
                "status": "rejected",
                "reject_reason": "Магазин не участвует в акции",
            },
        )
        self.assertIn("+03:00", item["created_at"])

    def test_only_get_is_allowed(self):
        self.client.force_login(self.user)
        for method in ("post", "put", "delete"):
            with self.subTest(method=method):
                self.assertEqual(getattr(self.client, method)(self.url).status_code, 405)
