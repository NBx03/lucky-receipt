import csv

from django.contrib import admin, messages
from django.http import HttpResponse
from django.utils import timezone

from .models import Receipt

CSV_HEADER = [
    "ID",
    "ФН",
    "ФД",
    "ФП",
    "Дата покупки",
    "Сумма",
    "Пользователь",
    "Email",
    "Дата регистрации",
]


def csv_safe(value):
    # Excel выполняет ячейки, начинающиеся с этих символов, как формулы.
    # Логин пользователя может начаться с «+», «-» или «@».
    return f"'{value}" if value[:1] in ("=", "+", "-", "@") else value


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "fn",
        "fd",
        "fp",
        "purchased_at",
        "amount",
        "status",
        "user",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("fn", "fd", "fp", "user__username", "user__email")
    list_select_related = ("user",)
    raw_id_fields = ("user",)
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
    actions = ["export_accepted_csv"]

    @admin.action(description="Выгрузить принятые чеки в CSV", permissions=["view"])
    def export_accepted_csv(self, request, queryset):
        receipts = (
            queryset.filter(status=Receipt.Status.ACCEPTED)
            .select_related("user")
            .order_by("purchased_at", "id")
        )
        if not receipts:
            self.message_user(
                request, "Среди выбранных нет принятых чеков.", messages.WARNING
            )
            return None

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        filename = f"accepted_receipts_{timezone.localdate():%Y%m%d}.csv"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        # BOM и «;» нужны, чтобы русский Excel открыл файл сразу и в нужной кодировке.
        response.write("﻿")
        writer = csv.writer(response, delimiter=";")
        writer.writerow(CSV_HEADER)
        for receipt in receipts:
            writer.writerow(
                [
                    receipt.id,
                    receipt.fn,
                    receipt.fd,
                    receipt.fp,
                    timezone.localtime(receipt.purchased_at).strftime("%d.%m.%Y %H:%M"),
                    receipt.amount,
                    csv_safe(receipt.user.get_username()),
                    csv_safe(receipt.user.email),
                    timezone.localtime(receipt.created_at).strftime("%d.%m.%Y %H:%M"),
                ]
            )
        return response
