from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q

DUPLICATE_MESSAGE = "Этот чек уже зарегистрирован."


class Receipt(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "На проверке"
        ACCEPTED = "accepted", "Принят"
        REJECTED = "rejected", "Отклонён"

    # Реквизиты хранятся строками: у ФН 16 цифр, число потеряло бы ведущие нули.
    fn = models.CharField(
        "ФН",
        max_length=16,
        validators=[RegexValidator(r"^\d{16}$", "ФН состоит из 16 цифр.")],
    )
    fd = models.CharField(
        "ФД",
        max_length=10,
        validators=[RegexValidator(r"^\d{1,10}$", "ФД состоит из 1–10 цифр.")],
    )
    fp = models.CharField(
        "ФП",
        max_length=10,
        validators=[RegexValidator(r"^\d{1,10}$", "ФП состоит из 1–10 цифр.")],
    )
    purchased_at = models.DateTimeField("Дата и время покупки")
    amount = models.DecimalField("Сумма", max_digits=10, decimal_places=2)
    status = models.CharField(
        "Статус", max_length=10, choices=Status.choices, default=Status.PENDING
    )
    reject_reason = models.TextField("Причина отказа", blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="receipts",
        verbose_name="Пользователь",
    )
    created_at = models.DateTimeField("Дата регистрации", auto_now_add=True)

    class Meta:
        verbose_name = "чек"
        verbose_name_plural = "чеки"
        constraints = [
            # Отклонённый чек можно подать заново, поэтому он из уникальности исключён.
            models.UniqueConstraint(
                fields=["fn", "fd", "fp"],
                condition=~Q(status="rejected"),
                name="unique_active_receipt",
            ),
        ]

    def __str__(self):
        return f"{self.fn}/{self.fd}/{self.fp}"

    def clean(self):
        # Ведущие нули не должны давать «другой» чек: 0042 и 42 — один документ.
        self.fd = self.fd.lstrip("0") or "0"
        self.fp = self.fp.lstrip("0") or "0"
        # Условный UniqueConstraint Django сам не проверяет, если status нет в форме,
        # поэтому дубль ловим здесь. База остаётся последней защитой от гонки.
        if self.status != self.Status.REJECTED:
            duplicates = (
                Receipt.objects.filter(fn=self.fn, fd=self.fd, fp=self.fp)
                .exclude(status=self.Status.REJECTED)
                .exclude(pk=self.pk)
            )
            if duplicates.exists():
                raise ValidationError(DUPLICATE_MESSAGE)

    def validate_constraints(self, exclude=None):
        # Уникальность уже проверена в clean() с понятным сообщением;
        # стандартная проверка выдала бы второе, техническое сообщение.
        pass
