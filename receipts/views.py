from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import ReceiptForm
from .models import DUPLICATE_MESSAGE

RECEIPTS_PER_PAGE = 10


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
    # Второй ключ сортировки делает порядок стабильным, когда даты покупки совпадают.
    receipts = request.user.receipts.order_by("-purchased_at", "-id")
    paginator = Paginator(receipts, RECEIPTS_PER_PAGE)
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
