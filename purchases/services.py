from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from catalog.models import Product
from inventory.models import StockMovement

from .models import (
    Purchase,
    PurchaseItem,
    PurchasePayment,
)


ZERO = Decimal("0.00")


class PurchaseOperationError(
    ValidationError
):
    """
    Erreur fonctionnelle provoquant l'annulation
    complète de l'approvisionnement.
    """


def format_fcfa(value):
    value = value or ZERO

    return (
        f"{value:,.0f}"
        .replace(",", " ")
        + " F CFA"
    )


def get_active_purchase_lines(
    item_formset,
):
    """
    Extrait uniquement les lignes valides
    et non supprimées du formulaire.
    """
    active_lines = []

    for form in item_formset.forms:
        cleaned_data = getattr(
            form,
            "cleaned_data",
            None,
        )

        if not cleaned_data:
            continue

        if cleaned_data.get(
            "DELETE",
            False,
        ):
            continue

        product = cleaned_data.get(
            "product"
        )

        quantity = cleaned_data.get(
            "quantity"
        )

        unit_cost = cleaned_data.get(
            "unit_cost"
        )

        discount = (
            cleaned_data.get(
                "discount"
            )
            or ZERO
        )

        if (
            product is None
            and quantity is None
            and unit_cost is None
        ):
            continue

        if product is None:
            raise PurchaseOperationError(
                "Une ligne ne comporte aucun produit."
            )

        if (
            quantity is None
            or quantity <= ZERO
        ):
            raise PurchaseOperationError(
                (
                    "La quantité du produit "
                    f"« {product.name} » "
                    "doit être supérieure à zéro."
                )
            )

        if (
            unit_cost is None
            or unit_cost < ZERO
        ):
            raise PurchaseOperationError(
                (
                    "Le prix d'achat du produit "
                    f"« {product.name} » "
                    "n'est pas valide."
                )
            )

        gross_total = (
            quantity * unit_cost
        )

        if discount > gross_total:
            raise PurchaseOperationError(
                (
                    "La remise du produit "
                    f"« {product.name} » "
                    "dépasse le montant de la ligne."
                )
            )

        active_lines.append(
            {
                "product_id": product.pk,
                "product_name": product.name,
                "quantity": quantity,
                "unit_cost": unit_cost,
                "discount": discount,
                "total_line": (
                    gross_total - discount
                ),
            }
        )

    if not active_lines:
        raise PurchaseOperationError(
            "Ajoutez au moins un produit "
            "à l'approvisionnement."
        )

    product_ids = [
        line["product_id"]
        for line in active_lines
    ]

    if (
        len(product_ids)
        != len(set(product_ids))
    ):
        raise PurchaseOperationError(
            "Un produit apparaît plusieurs fois. "
            "Regroupez sa quantité sur une seule ligne."
        )

    return active_lines


@transaction.atomic
def create_purchase_with_stock(
    *,
    purchase_form,
    item_formset,
    user,
):
    """
    Crée un achat complet et augmente le stock.

    L'ensemble de l'opération est atomique :
    en cas d'erreur, aucun achat, paiement,
    produit ou mouvement de stock n'est conservé.
    """
    if not purchase_form.is_valid():
        raise PurchaseOperationError(
            "Les informations de l'achat "
            "ne sont pas valides."
        )

    if not item_formset.is_valid():
        raise PurchaseOperationError(
            "Les lignes de l'approvisionnement "
            "ne sont pas valides."
        )

    active_lines = (
        get_active_purchase_lines(
            item_formset
        )
    )

    product_ids = sorted(
        {
            line["product_id"]
            for line in active_lines
        }
    )

    locked_products = {
        product.pk: product
        for product in (
            Product.objects
            .select_for_update()
            .filter(
                pk__in=product_ids
            )
            .order_by("pk")
        )
    }

    if (
        len(locked_products)
        != len(product_ids)
    ):
        raise PurchaseOperationError(
            "Un ou plusieurs produits "
            "sont introuvables."
        )

    initial_payment = (
        purchase_form.cleaned_data.get(
            "initial_payment"
        )
        or ZERO
    )

    purchase = purchase_form.save(
        commit=False
    )

    purchase.created_by = user

    purchase.subtotal = ZERO
    purchase.total = ZERO
    purchase.amount_paid = ZERO
    purchase.remaining_amount = ZERO

    purchase.payment_status = (
        Purchase.PaymentStatus.CREDIT
    )

    if initial_payment <= ZERO:
        purchase.payment_method = (
            Purchase.PaymentMethod.CREDIT
        )

    purchase.save()

    subtotal = ZERO

    for line in active_lines:
        product = locked_products.get(
            line["product_id"]
        )

        if product is None:
            raise PurchaseOperationError(
                (
                    "Le produit "
                    f"« {line['product_name']} » "
                    "est introuvable."
                )
            )

        quantity = line["quantity"]
        unit_cost = line["unit_cost"]
        discount = line["discount"]
        total_line = line["total_line"]

        PurchaseItem.objects.create(
            purchase=purchase,
            product=product,
            quantity=quantity,
            unit_cost=unit_cost,
            discount=discount,
            total_line=total_line,
        )

        old_quantity = (
            product.stock_quantity
            or ZERO
        )

        new_quantity = (
            old_quantity + quantity
        )

        product.stock_quantity = (
            new_quantity
        )

        update_fields = [
            "stock_quantity",
            "updated_at",
        ]

        # Le rapport de bénéfices utilise le prix
        # d'achat actuel du produit.
        if unit_cost > ZERO:
            product.purchase_price = (
                unit_cost
            )

            update_fields.append(
                "purchase_price"
            )

        product.save(
            update_fields=update_fields
        )

        StockMovement.objects.create(
            product=product,
            movement_type=(
                StockMovement
                .MovementType
                .IN
            ),
            quantity=quantity,
            old_quantity=old_quantity,
            new_quantity=new_quantity,
            reason=(
                "Approvisionnement "
                f"{purchase.purchase_number}"
            ),
        )

        subtotal += total_line

    global_discount = (
        purchase.discount
        or ZERO
    )

    if global_discount > subtotal:
        raise PurchaseOperationError(
            {
                "discount": (
                    "La remise globale dépasse "
                    "le sous-total de l'achat."
                )
            }
        )

    total = (
        subtotal - global_discount
    )

    if total < ZERO:
        total = ZERO

    if initial_payment > total:
        raise PurchaseOperationError(
            {
                "initial_payment": (
                    "Le montant payé dépasse "
                    "le total de l'achat. "
                    "Maximum autorisé : "
                    f"{format_fcfa(total)}."
                )
            }
        )

    purchase.subtotal = subtotal
    purchase.total = total
    purchase.amount_paid = ZERO
    purchase.remaining_amount = total

    if total <= ZERO:
        purchase.payment_status = (
            Purchase.PaymentStatus.PAID
        )

        purchase.remaining_amount = ZERO

    else:
        purchase.payment_status = (
            Purchase.PaymentStatus.CREDIT
        )

    purchase.save(
        update_fields=[
            "subtotal",
            "total",
            "amount_paid",
            "remaining_amount",
            "payment_status",
            "payment_method",
            "updated_at",
        ]
    )

    if initial_payment > ZERO:
        PurchasePayment.objects.create(
            purchase=purchase,
            supplier=purchase.supplier,
            amount=initial_payment,
            payment_method=(
                purchase.payment_method
            ),
            payment_date=(
                purchase.purchase_date
            ),
            notes=(
                "Paiement initial de l'achat "
                f"{purchase.purchase_number}"
            ),
            created_by=user,
        )

    else:
        Purchase.update_supplier_balance(
            purchase.supplier
        )

    purchase.refresh_from_db()

    return purchase