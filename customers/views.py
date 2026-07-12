from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import (
    admin_required,
    seller_or_admin_required,
)
from payments.models import Payment
from sales.models import Sale

from .forms import ClientForm
from .models import Client


def decimal_sum(queryset, field_name):
    result = queryset.aggregate(
        total=Sum(field_name)
    )["total"]

    return result or Decimal("0.00")


def synchronize_client_balance(client):
    balance = Sale.objects.filter(
        client=client,
        is_cancelled=False,
    ).aggregate(
        total=Sum("remaining_amount")
    )["total"] or Decimal("0.00")

    if client.balance != balance:
        client.balance = balance
        client.save(
            update_fields=[
                "balance",
                "updated_at",
            ]
        )

    return balance


@seller_or_admin_required
def client_list(request):
    query = request.GET.get("q", "").strip()
    credit_filter = request.GET.get(
        "credit",
        "",
    ).strip()

    clients = Client.objects.all().order_by("full_name")

    if query:
        clients = clients.filter(
            Q(full_name__icontains=query)
            | Q(phone__icontains=query)
            | Q(address__icontains=query)
            | Q(email__icontains=query)
        )

    if credit_filter == "with_credit":
        clients = clients.filter(
            balance__gt=0,
        )

    elif credit_filter == "without_credit":
        clients = clients.filter(
            balance=0,
        )

    total_clients = Client.objects.count()

    credit_clients = Client.objects.filter(
        balance__gt=0,
    ).count()

    total_debt = Client.objects.aggregate(
        total=Sum("balance")
    )["total"] or Decimal("0.00")

    filtered_count = clients.count()

    paginator = Paginator(clients, 15)
    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "page_obj": page_obj,
        "query": query,
        "credit_filter": credit_filter,
        "total_clients": total_clients,
        "credit_clients": credit_clients,
        "total_debt": total_debt,
        "filtered_count": filtered_count,
    }

    return render(
        request,
        "customers/client_list.html",
        context,
    )


@seller_or_admin_required
def client_create(request):
    if request.method == "POST":
        form = ClientForm(request.POST)

        if form.is_valid():
            client = form.save()

            messages.success(
                request,
                f"Client « {client.full_name} » ajouté avec succès.",
            )

            return redirect(
                "client_detail",
                pk=client.pk,
            )
    else:
        form = ClientForm()

    context = {
        "form": form,
        "title": "Ajouter un client",
        "button_label": "Enregistrer",
    }

    return render(
        request,
        "customers/client_form.html",
        context,
    )


@seller_or_admin_required
def client_update(request, pk):
    client = get_object_or_404(
        Client,
        pk=pk,
    )

    if request.method == "POST":
        form = ClientForm(
            request.POST,
            instance=client,
        )

        if form.is_valid():
            updated_client = form.save()

            messages.success(
                request,
                "Client modifié avec succès.",
            )

            return redirect(
                "client_detail",
                pk=updated_client.pk,
            )
    else:
        form = ClientForm(instance=client)

    context = {
        "form": form,
        "client": client,
        "title": "Modifier le client",
        "button_label": "Modifier",
    }

    return render(
        request,
        "customers/client_form.html",
        context,
    )


@seller_or_admin_required
def client_detail(request, pk):
    client = get_object_or_404(
        Client,
        pk=pk,
    )

    sales = Sale.objects.filter(
        client=client,
        is_cancelled=False,
    ).select_related(
        "created_by",
    ).order_by("-sale_date")

    payments = Payment.objects.filter(
        client=client,
    ).select_related(
        "sale",
        "created_by",
    ).order_by("-payment_date")

    total_sales = decimal_sum(
        sales,
        "total",
    )

    total_paid = decimal_sum(
        sales,
        "amount_paid",
    )

    total_remaining = decimal_sum(
        sales,
        "remaining_amount",
    )

    sales_count = sales.count()
    payment_count = payments.count()

    synchronize_client_balance(client)

    recent_sales = sales[:10]
    recent_payments = payments[:10]

    context = {
        "client": client,
        "total_sales": total_sales,
        "total_paid": total_paid,
        "total_remaining": total_remaining,
        "sales_count": sales_count,
        "payment_count": payment_count,
        "recent_sales": recent_sales,
        "recent_payments": recent_payments,
    }

    return render(
        request,
        "customers/client_detail.html",
        context,
    )


@admin_required
def client_delete(request, pk):
    client = get_object_or_404(
        Client,
        pk=pk,
    )

    if request.method == "POST":
        client_name = client.full_name

        try:
            client.delete()

            messages.success(
                request,
                f"Client « {client_name} » supprimé avec succès.",
            )
        except ProtectedError:
            messages.error(
                request,
                "Ce client ne peut pas être supprimé, "
                "car il est lié à des opérations protégées.",
            )

        return redirect("client_list")

    context = {
        "client": client,
    }

    return render(
        request,
        "customers/client_confirm_delete.html",
        context,
    )