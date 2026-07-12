from datetime import datetime
from decimal import Decimal

from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone

from accounts.decorators import admin_required
from expenses.models import Expense
from payments.models import Payment


def decimal_sum(queryset, field_name):
    result = queryset.aggregate(
        total=Sum(field_name)
    )["total"]

    return result or Decimal("0.00")


def get_valid_date(date_value):
    if not date_value:
        return timezone.localdate()

    try:
        return datetime.strptime(
            date_value,
            "%Y-%m-%d",
        ).date()
    except ValueError:
        return timezone.localdate()


@admin_required
def cashbox_today(request):
    selected_date = request.GET.get(
        "date",
        "",
    ).strip()

    target_date = get_valid_date(selected_date)

    payments = Payment.objects.select_related(
        "sale",
        "client",
        "created_by",
    ).filter(
        payment_date__date=target_date,
    ).order_by("-payment_date")

    expenses = Expense.objects.select_related(
        "created_by",
    ).filter(
        expense_date__date=target_date,
    ).order_by("-expense_date")

    total_income = decimal_sum(
        payments,
        "amount",
    )

    total_expenses = decimal_sum(
        expenses,
        "amount",
    )

    balance = total_income - total_expenses

    cash_income = decimal_sum(
        payments.filter(
            payment_method=Payment.PaymentMethod.CASH,
        ),
        "amount",
    )

    orange_income = decimal_sum(
        payments.filter(
            payment_method=Payment.PaymentMethod.ORANGE_MONEY,
        ),
        "amount",
    )

    wave_income = decimal_sum(
        payments.filter(
            payment_method=Payment.PaymentMethod.WAVE,
        ),
        "amount",
    )

    bank_income = decimal_sum(
        payments.filter(
            payment_method=Payment.PaymentMethod.BANK_TRANSFER,
        ),
        "amount",
    )

    other_income = decimal_sum(
        payments.filter(
            payment_method=Payment.PaymentMethod.OTHER,
        ),
        "amount",
    )

    payment_count = payments.count()
    expense_count = expenses.count()
    operation_count = payment_count + expense_count

    context = {
        "target_date": target_date.isoformat(),

        "payments": payments,
        "expenses": expenses,

        "total_income": total_income,
        "total_expenses": total_expenses,
        "balance": balance,

        "payment_count": payment_count,
        "expense_count": expense_count,
        "operation_count": operation_count,

        "cash_income": cash_income,
        "orange_income": orange_income,
        "wave_income": wave_income,
        "bank_income": bank_income,
        "other_income": other_income,
    }

    return render(
        request,
        "cashbox/cashbox_today.html",
        context,
    )