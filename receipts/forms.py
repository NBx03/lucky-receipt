import re
from datetime import datetime, time, timedelta
from decimal import Decimal

from django import forms
from django.conf import settings
from django.utils import timezone

from .models import Receipt

MIN_AMOUNT = Decimal("1000")


def promo_bounds():
    """Период акции как полуинтервал [начало, конец) в часовом поясе акции.

    Конец включительный по дате, поэтому верхняя граница — полночь следующего дня.
    """
    start = timezone.make_aware(datetime.combine(settings.PROMO_START_DATE, time.min))
    end = timezone.make_aware(
        datetime.combine(settings.PROMO_END_DATE + timedelta(days=1), time.min)
    )
    return start, end


class AmountField(forms.DecimalField):
    """Сумма с запятой или пробелами: «1 500,50» читается как 1500.50."""

    def to_python(self, value):
        if isinstance(value, str):
            value = re.sub(r"\s", "", value).replace(",", ".")
            # Decimal разбирает и «1e5», и «Infinity»: оставляем только обычную запись.
            if value and not re.fullmatch(r"\d+(\.\d+)?", value):
                raise forms.ValidationError(self.error_messages["invalid"], code="invalid")
        return super().to_python(value)


class ReceiptForm(forms.ModelForm):
    purchased_at = forms.DateTimeField(
        label="Дата покупки",
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
        ),
    )
    amount = AmountField(
        label="Сумма",
        max_digits=10,
        decimal_places=2,
        min_value=MIN_AMOUNT,
        # type=number не пропустит запятую, поэтому обычное текстовое поле.
        widget=forms.TextInput(
            attrs={"placeholder": "0.00 ₽", "inputmode": "decimal", "autocomplete": "off"}
        ),
        error_messages={
            "min_value": f"Сумма чека должна быть не меньше {MIN_AMOUNT:.0f} ₽.",
            "invalid": "Введите сумму числом, например 1500.50.",
        },
    )

    class Meta:
        model = Receipt
        fields = ["fn", "fd", "fp", "purchased_at", "amount"]
        labels = {"fn": "ФН", "fd": "Номер чека", "fp": "ФП"}
        widgets = {
            "fn": forms.TextInput(
                attrs={"placeholder": "Введите ФН", "inputmode": "numeric", "autocomplete": "off"}
            ),
            "fd": forms.TextInput(
                attrs={
                    "placeholder": "Введите номер чека (ФД)",
                    "inputmode": "numeric",
                    "autocomplete": "off",
                }
            ),
            "fp": forms.TextInput(
                attrs={"placeholder": "Введите ФП", "inputmode": "numeric", "autocomplete": "off"}
            ),
        }

    def clean_purchased_at(self):
        value = self.cleaned_data["purchased_at"]
        start, end = promo_bounds()
        if not start <= value < end:
            raise forms.ValidationError(
                "Дата покупки вне периода акции: с "
                f"{settings.PROMO_START_DATE:%d.%m.%Y} по {settings.PROMO_END_DATE:%d.%m.%Y}."
            )
        if value > timezone.now():
            raise forms.ValidationError("Дата покупки не может быть в будущем.")
        return value
