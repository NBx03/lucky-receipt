from django.contrib import admin

from .models import Receipt


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
