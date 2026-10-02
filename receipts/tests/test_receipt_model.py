from datetime import datetime, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from receipts.models import Receipt


class ReceiptModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user("buyer")

    def make(self, **overrides):
        fields = {
            "fn": "1234567890123456",
            "fd": "10",
            "fp": "20",
            "purchased_at": datetime(2026, 2, 10, 9, 0, tzinfo=dt_timezone.utc),
            "amount": "1500",
            "user": self.user,
        }
        fields.update(overrides)
        return Receipt(**fields)

    def test_rejection_requires_reason(self):
        receipt = self.make(status=Receipt.Status.REJECTED, reject_reason="  ")
        with self.assertRaises(ValidationError) as ctx:
            receipt.full_clean()
        self.assertIn("reject_reason", ctx.exception.message_dict)

    def test_reason_is_cleared_when_not_rejected(self):
        receipt = self.make(status=Receipt.Status.ACCEPTED, reject_reason="остаток")
        receipt.full_clean()
        self.assertEqual(receipt.reject_reason, "")

    def test_returning_rejected_receipt_to_pending_is_blocked_by_duplicate(self):
        old = self.make(status=Receipt.Status.REJECTED, reject_reason="Нечитаемый чек")
        old.save()
        self.make().save()
        old.status = Receipt.Status.PENDING
        with self.assertRaises(ValidationError):
            old.full_clean()
