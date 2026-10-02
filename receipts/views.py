from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from .forms import MIN_AMOUNT, ReceiptForm
from .models import DUPLICATE_MESSAGE

RECEIPTS_PER_PAGE = 10


def user_receipts(user):
    # Выборка строится от пользователя, поэтому чужих чеков в ней нет.
    # Второй ключ сортировки делает порядок стабильным, когда даты покупки совпадают.
    return user.receipts.order_by("-purchased_at", "-id")


def signup(request):
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)
    form = UserCreationForm(request.POST or None)
    if form.is_valid():
        login(request, form.save())
        return redirect(settings.LOGIN_REDIRECT_URL)
    return render(request, "registration/signup.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def receipt_create(request):
    if request.method == "GET":
        context = {
            "form": ReceiptForm(),
            "promo_start": settings.PROMO_START_DATE,
            "promo_end": settings.PROMO_END_DATE,
            "min_amount": MIN_AMOUNT,
            "now": timezone.localtime(),
        }
        return render(request, "receipts/form.html", context)

    form = ReceiptForm(request.POST)
    if form.is_valid():
        receipt = form.save(commit=False)
        receipt.user = request.user
        try:
            with transaction.atomic():
                receipt.save()
        except IntegrityError:
            # Два одновременных запроса с одним чеком прошли проверку в форме.
            form.add_error(None, DUPLICATE_MESSAGE)
        else:
            return JsonResponse({"ok": True}, status=201)
    errors = {field: list(messages) for field, messages in form.errors.items()}
    return JsonResponse({"errors": errors}, status=400)


@login_required
def cabinet(request):
    paginator = Paginator(user_receipts(request.user), RECEIPTS_PER_PAGE)
    page = paginator.get_page(request.GET.get("page"))
    context = {
        "page": page,
        "total": paginator.count,
        "pages": paginator.get_elided_page_range(
            page.number, on_each_side=1, on_ends=1
        ),
        "ellipsis": paginator.ELLIPSIS,
    }
    return render(request, "receipts/cabinet.html", context)


@require_GET
def api_receipts(request):
    # Не login_required: тот отдал бы редирект на HTML-страницу входа, а не JSON.
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Требуется вход."}, status=403)
    data = [
        {
            "id": receipt.id,
            "fn": receipt.fn,
            "fd": receipt.fd,
            "fp": receipt.fp,
            "purchased_at": timezone.localtime(receipt.purchased_at).isoformat(),
            # Строкой, чтобы сумма не превращалась в float.
            "amount": str(receipt.amount),
            "status": receipt.status,
            "reject_reason": receipt.reject_reason,
            "created_at": timezone.localtime(receipt.created_at).isoformat(),
        }
        for receipt in user_receipts(request.user)
    ]
    return JsonResponse(data, safe=False)
