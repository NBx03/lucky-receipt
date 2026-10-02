import csv
import io
from datetime import datetime, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from receipts.admin import csv_safe
from receipts.models import Receipt

from .test_cabinet import make_receipt

URL = reverse("admin:receipts_receipt_changelist")


def parse(response):
    text = response.content.decode("utf-8")
    return text, list(csv.reader(io.StringIO(text.lstrip("﻿")), delimiter=";"))


class ExportAcceptedCsvTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_superuser("moderator", "mod@example.com", "x")
        cls.user = User.objects.create_user("buyer", email="buyer@example.com")

    def setUp(self):
        self.client.force_login(self.admin)

    def export(self, receipts):
        return self.client.post(
            URL,
            {
                "action": "export_accepted_csv",
                "_selected_action": [receipt.pk for receipt in receipts],
            },
        )

    def test_exports_only_accepted_among_selected(self):
        accepted = make_receipt(
            self.user,
            1,
            status=Receipt.Status.ACCEPTED,
            amount="1500.50",
            purchased_at=datetime(2026, 2, 1, 21, 30, tzinfo=dt_timezone.utc),
        )
        pending = make_receipt(self.user, 2)
        rejected = make_receipt(
            self.user, 3, status=Receipt.Status.REJECTED, reject_reason="Нечитаемый чек"
        )
        make_receipt(self.user, 4, status=Receipt.Status.ACCEPTED)  # не выбран

        response = self.export([accepted, pending, rejected])

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/csv"))
        self.assertIn("attachment", response["Content-Disposition"])
        text, rows = parse(response)
        self.assertTrue(text.startswith("﻿"))
        self.assertEqual(len(rows), 2)
        header, row = rows
        self.assertEqual(header[:3], ["ID", "ФН", "ФД"])
        self.assertEqual(row[:4], [str(accepted.pk), "1234567890123456", "1", "20"])
        # 21:30 UTC — это 00:30 следующего дня по Москве.
        self.assertEqual(row[4], "02.02.2026 00:30")
        self.assertEqual(row[5], "1500.50")
        self.assertEqual(row[6:8], ["buyer", "buyer@example.com"])

    def test_no_accepted_among_selected_gives_message_not_file(self):
        pending = make_receipt(self.user, 1)
        response = self.export([pending])
        self.assertEqual(response.status_code, 302)
        follow = self.client.get(URL)
        self.assertContains(follow, "Среди выбранных нет принятых чеков.")

    def test_csv_safe_escapes_formula_prefixes(self):
        for value in ("=1+1", "+1", "-1", "@x"):
            self.assertEqual(csv_safe(value), f"'{value}")
        self.assertEqual(csv_safe("buyer"), "buyer")
        self.assertEqual(csv_safe(""), "")
