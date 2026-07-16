from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import (
    MinValueValidator,
)
from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone

from catalog.models import Product
from inventory.models import StockMovement


ZERO = Decimal("0.00")


def generate_purchase_number():
    """
    Génère un numéro d'achat unique.
    Exemple : ACH-20260715-A12B34CD
    """
    today = timezone.localdate()

    return (
        f"ACH-{today:%Y%m%d}-"
        f"{uuid4().hex[:8].upper()}"
    )


class Supplier(models.Model):
    name = models.CharField(
        "Nom du fournisseur",
        max_length=150,
    )

    phone = models.CharField(
        "Téléphone",
        max_length=30,
        blank=True,
    )

    email = models.EmailField(
        "Adresse e-mail",
        blank=True,
    )

    address = models.TextField(
        "Adresse",
        blank=True,
    )

    balance = models.DecimalField(
        "Dette fournisseur",
        max_digits=18,
        decimal_places=2,
        default=ZERO,
        validators=[
            MinValueValidator(ZERO),
        ],
    )

    is_active = models.BooleanField(
        "Fournisseur actif",
        default=True,
    )

    created_at = models.DateTimeField(
        "Créé le",
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        "Modifié le",
        auto_now=True,
    )

    class Meta:
        verbose_name = "Fournisseur"
        verbose_name_plural = "Fournisseurs"
        ordering = ["name"]

        indexes = [
            models.Index(
                fields=["name"],
            ),
            models.Index(
                fields=["phone"],
            ),
        ]

    def __str__(self):
        return self.name


class Purchase(models.Model):
    class PaymentStatus(models.TextChoices):
        PAID = "paid", "Payé"
        PARTIAL = "partial", "Partiel"
        CREDIT = "credit", "Crédit"
        CANCELLED = "cancelled", "Annulé"

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Espèce"

        ORANGE_MONEY = (
            "orange_money",
            "Orange Money",
        )

        WAVE = "wave", "Wave"

        BANK_TRANSFER = (
            "bank_transfer",
            "Virement bancaire",
        )

        CREDIT = "credit", "Crédit"
        OTHER = "other", "Autre"

    purchase_number = models.CharField(
        "Numéro d'achat",
        max_length=40,
        unique=True,
        blank=True,
    )

    supplier = models.ForeignKey(
        Supplier,
        verbose_name="Fournisseur",
        on_delete=models.PROTECT,
        related_name="purchases",
    )

    supplier_reference = models.CharField(
        "Référence fournisseur",
        max_length=100,
        blank=True,
    )

    purchase_date = models.DateTimeField(
        "Date de l'achat",
        default=timezone.now,
    )

    subtotal = models.DecimalField(
        "Sous-total",
        max_digits=18,
        decimal_places=2,
        default=ZERO,
        validators=[
            MinValueValidator(ZERO),
        ],
    )

    discount = models.DecimalField(
        "Remise globale",
        max_digits=18,
        decimal_places=2,
        default=ZERO,
        validators=[
            MinValueValidator(ZERO),
        ],
    )

    total = models.DecimalField(
        "Total net",
        max_digits=18,
        decimal_places=2,
        default=ZERO,
        validators=[
            MinValueValidator(ZERO),
        ],
    )

    amount_paid = models.DecimalField(
        "Montant payé",
        max_digits=18,
        decimal_places=2,
        default=ZERO,
        validators=[
            MinValueValidator(ZERO),
        ],
    )

    remaining_amount = models.DecimalField(
        "Reste à payer",
        max_digits=18,
        decimal_places=2,
        default=ZERO,
        validators=[
            MinValueValidator(ZERO),
        ],
    )

    payment_status = models.CharField(
        "Statut du paiement",
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.CREDIT,
    )

    payment_method = models.CharField(
        "Mode de paiement",
        max_length=30,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
    )

    notes = models.TextField(
        "Notes",
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Créé par",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_purchases",
    )

    is_cancelled = models.BooleanField(
        "Achat annulé",
        default=False,
    )

    created_at = models.DateTimeField(
        "Créé le",
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        "Modifié le",
        auto_now=True,
    )

    class Meta:
        verbose_name = "Achat"
        verbose_name_plural = "Achats"
        ordering = ["-purchase_date"]

        indexes = [
            models.Index(
                fields=["purchase_number"],
            ),
            models.Index(
                fields=["purchase_date"],
            ),
            models.Index(
                fields=["payment_status"],
            ),
            models.Index(
                fields=["is_cancelled"],
            ),
        ]

    def __str__(self):
        return (
            self.purchase_number
            or "Achat non enregistré"
        )

    def save(self, *args, **kwargs):
        if not self.purchase_number:
            self.purchase_number = (
                generate_purchase_number()
            )

        if self.is_cancelled:
            self.payment_status = (
                self.PaymentStatus.CANCELLED
            )

            self.remaining_amount = ZERO

            update_fields = kwargs.get(
                "update_fields"
            )

            if update_fields is not None:
                update_fields = set(
                    update_fields
                )

                update_fields.add(
                    "purchase_number"
                )

                update_fields.add(
                    "payment_status"
                )

                update_fields.add(
                    "remaining_amount"
                )

                kwargs["update_fields"] = list(
                    update_fields
                )

        super().save(*args, **kwargs)

    def calculate_totals(self, save=True):
        """
        Recalcule les montants de l'achat à partir
        des lignes et des paiements enregistrés.
        """
        if not self.pk:
            return ZERO

        subtotal = (
            self.items.aggregate(
                total=Sum("total_line")
            )["total"]
            or ZERO
        )

        discount = self.discount or ZERO

        total = subtotal - discount

        if total < ZERO:
            total = ZERO

        total_paid = (
            self.payments.aggregate(
                total=Sum("amount")
            )["total"]
            or ZERO
        )

        if self.is_cancelled:
            remaining = ZERO

            payment_status = (
                self.PaymentStatus.CANCELLED
            )

        else:
            remaining = total - total_paid

            if remaining < ZERO:
                remaining = ZERO

            if (
                total > ZERO
                and total_paid >= total
            ):
                payment_status = (
                    self.PaymentStatus.PAID
                )

                remaining = ZERO

            elif total_paid > ZERO:
                payment_status = (
                    self.PaymentStatus.PARTIAL
                )

            else:
                payment_status = (
                    self.PaymentStatus.CREDIT
                )

        self.subtotal = subtotal
        self.total = total
        self.amount_paid = total_paid
        self.remaining_amount = remaining
        self.payment_status = payment_status

        if save:
            Purchase.objects.filter(
                pk=self.pk
            ).update(
                subtotal=subtotal,
                total=total,
                amount_paid=total_paid,
                remaining_amount=remaining,
                payment_status=payment_status,
                updated_at=timezone.now(),
            )

        Purchase.update_supplier_balance(
            self.supplier
        )

        return total

    @classmethod
    def update_supplier_balance(
        cls,
        supplier,
    ):
        """
        Recalcule la dette totale envers
        un fournisseur.
        """
        if supplier is None:
            return

        balance = (
            cls.objects.filter(
                supplier=supplier,
                is_cancelled=False,
            ).aggregate(
                total=Sum("remaining_amount")
            )["total"]
            or ZERO
        )

        supplier.balance = balance

        supplier.save(
            update_fields=[
                "balance",
                "updated_at",
            ]
        )

    def cancel_purchase(
        self,
        cancelled_by=None,
        reason="",
    ):
        """
        Annule un achat et retire du stock les
        quantités ajoutées par cet achat.

        L'annulation est refusée si le stock actuel
        est insuffisant.
        """
        if not self.pk:
            raise ValidationError(
                "Cet achat n'est pas enregistré."
            )

        with transaction.atomic():
            locked_purchase = (
                Purchase.objects
                .select_for_update()
                .get(pk=self.pk)
            )

            if locked_purchase.is_cancelled:
                return False

            items = list(
                locked_purchase.items
                .select_related(
                    "product",
                    "product__unit",
                )
                .order_by(
                    "product_id",
                    "pk",
                )
            )

            product_ids = sorted(
                {
                    item.product_id
                    for item in items
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

            actor_name = ""

            if cancelled_by is not None:
                actor_name = (
                    cancelled_by
                    .get_full_name()
                    .strip()
                    or cancelled_by.username
                )

            for item in items:
                product = locked_products.get(
                    item.product_id
                )

                if product is None:
                    raise ValidationError(
                        "Un produit de l'achat "
                        "est introuvable."
                    )

                old_quantity = (
                    product.stock_quantity
                    or ZERO
                )

                if old_quantity < item.quantity:
                    raise ValidationError(
                        (
                            "Impossible d'annuler "
                            "l'achat. Le stock du produit "
                            f"« {product.name} » est "
                            "insuffisant."
                        )
                    )

                new_quantity = (
                    old_quantity
                    - item.quantity
                )

                product.stock_quantity = (
                    new_quantity
                )

                product.save(
                    update_fields=[
                        "stock_quantity",
                        "updated_at",
                    ]
                )

                movement_reason = (
                    reason.strip()
                    if reason.strip()
                    else (
                        "Annulation de l'achat "
                        f"{locked_purchase.purchase_number}"
                    )
                )

                if actor_name:
                    movement_reason += (
                        f" par {actor_name}"
                    )

                StockMovement.objects.create(
                    product=product,
                    movement_type=(
                        StockMovement
                        .MovementType
                        .OUT
                    ),
                    quantity=item.quantity,
                    old_quantity=old_quantity,
                    new_quantity=new_quantity,
                    reason=movement_reason,
                )

            locked_purchase.is_cancelled = True

            locked_purchase.payment_status = (
                Purchase
                .PaymentStatus
                .CANCELLED
            )

            locked_purchase.remaining_amount = ZERO

            locked_purchase.save(
                update_fields=[
                    "is_cancelled",
                    "payment_status",
                    "remaining_amount",
                    "updated_at",
                ]
            )

            Purchase.update_supplier_balance(
                locked_purchase.supplier
            )

            self.is_cancelled = True

            self.payment_status = (
                Purchase
                .PaymentStatus
                .CANCELLED
            )

            self.remaining_amount = ZERO

        return True


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(
        Purchase,
        verbose_name="Achat",
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        Product,
        verbose_name="Produit",
        on_delete=models.PROTECT,
        related_name="purchase_items",
    )

    quantity = models.DecimalField(
        "Quantité",
        max_digits=18,
        decimal_places=2,
        validators=[
            MinValueValidator(
                Decimal("0.01")
            ),
        ],
    )

    unit_cost = models.DecimalField(
        "Prix d'achat unitaire",
        max_digits=18,
        decimal_places=2,
        validators=[
            MinValueValidator(ZERO),
        ],
    )

    discount = models.DecimalField(
        "Remise sur la ligne",
        max_digits=18,
        decimal_places=2,
        default=ZERO,
        validators=[
            MinValueValidator(ZERO),
        ],
    )

    total_line = models.DecimalField(
        "Montant de la ligne",
        max_digits=18,
        decimal_places=2,
        default=ZERO,
        validators=[
            MinValueValidator(ZERO),
        ],
    )

    created_at = models.DateTimeField(
        "Créé le",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "Ligne d'achat"
        verbose_name_plural = (
            "Lignes d'achat"
        )

        ordering = ["pk"]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "purchase",
                    "product",
                ],
                name=(
                    "unique_product_per_purchase"
                ),
            ),
        ]

    def __str__(self):
        return (
            f"{self.product.name} "
            f"x {self.quantity}"
        )

    def clean(self):
        errors = {}

        if (
            self.purchase_id
            and self.purchase.is_cancelled
        ):
            errors["purchase"] = (
                "Impossible de modifier "
                "un achat annulé."
            )

        quantity = self.quantity or ZERO
        unit_cost = self.unit_cost or ZERO
        discount = self.discount or ZERO

        gross_total = (
            quantity * unit_cost
        )

        if discount > gross_total:
            errors["discount"] = (
                "La remise ne peut pas dépasser "
                "le montant de la ligne."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        quantity = self.quantity or ZERO
        unit_cost = self.unit_cost or ZERO
        discount = self.discount or ZERO

        total = (
            quantity * unit_cost
        ) - discount

        if total < ZERO:
            total = ZERO

        self.total_line = total

        self.full_clean()

        super().save(*args, **kwargs)


class PurchasePayment(models.Model):
    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Espèce"

        ORANGE_MONEY = (
            "orange_money",
            "Orange Money",
        )

        WAVE = "wave", "Wave"

        BANK_TRANSFER = (
            "bank_transfer",
            "Virement bancaire",
        )

        OTHER = "other", "Autre"

    purchase = models.ForeignKey(
        Purchase,
        verbose_name="Achat",
        on_delete=models.CASCADE,
        related_name="payments",
    )

    supplier = models.ForeignKey(
        Supplier,
        verbose_name="Fournisseur",
        on_delete=models.PROTECT,
        related_name="payments",
    )

    amount = models.DecimalField(
        "Montant payé",
        max_digits=18,
        decimal_places=2,
        validators=[
            MinValueValidator(
                Decimal("0.01")
            ),
        ],
    )

    payment_method = models.CharField(
        "Mode de paiement",
        max_length=30,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
    )

    payment_date = models.DateTimeField(
        "Date du paiement",
        default=timezone.now,
    )

    notes = models.TextField(
        "Notes",
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Créé par",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name=(
            "created_purchase_payments"
        ),
    )

    created_at = models.DateTimeField(
        "Créé le",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = (
            "Paiement fournisseur"
        )

        verbose_name_plural = (
            "Paiements fournisseurs"
        )

        ordering = ["-payment_date"]

        indexes = [
            models.Index(
                fields=["payment_date"],
            ),
            models.Index(
                fields=["payment_method"],
            ),
        ]

    def __str__(self):
        return (
            f"{self.amount} - "
            f"{self.purchase.purchase_number}"
        )

    def clean(self):
        errors = {}

        if not self.purchase_id:
            errors["purchase"] = (
                "Sélectionnez un achat."
            )

        if (
            self.amount is None
            or self.amount <= ZERO
        ):
            errors["amount"] = (
                "Le montant doit être "
                "supérieur à zéro."
            )

        if self.purchase_id:
            purchase = self.purchase

            if purchase.is_cancelled:
                errors["purchase"] = (
                    "Impossible d'ajouter un "
                    "paiement à un achat annulé."
                )

            other_payments_total = (
                PurchasePayment.objects
                .filter(
                    purchase_id=self.purchase_id
                )
                .exclude(pk=self.pk)
                .aggregate(
                    total=Sum("amount")
                )["total"]
                or ZERO
            )

            maximum_allowed = (
                purchase.total
                - other_payments_total
            )

            if maximum_allowed < ZERO:
                maximum_allowed = ZERO

            if (
                self.amount is not None
                and self.amount
                > maximum_allowed
            ):
                errors["amount"] = (
                    "Le paiement dépasse le "
                    "reste à payer. Maximum "
                    f"autorisé : "
                    f"{maximum_allowed} F CFA."
                )

        if errors:
            raise ValidationError(errors)

    @classmethod
    def synchronize_purchase(
        cls,
        purchase,
    ):
        total_paid = (
            cls.objects.filter(
                purchase_id=purchase.pk
            ).aggregate(
                total=Sum("amount")
            )["total"]
            or ZERO
        )

        if purchase.is_cancelled:
            remaining = ZERO

            payment_status = (
                Purchase
                .PaymentStatus
                .CANCELLED
            )

        else:
            remaining = (
                purchase.total
                - total_paid
            )

            if remaining < ZERO:
                remaining = ZERO

            if (
                purchase.total > ZERO
                and total_paid
                >= purchase.total
            ):
                payment_status = (
                    Purchase
                    .PaymentStatus
                    .PAID
                )

                remaining = ZERO

            elif total_paid > ZERO:
                payment_status = (
                    Purchase
                    .PaymentStatus
                    .PARTIAL
                )

            else:
                payment_status = (
                    Purchase
                    .PaymentStatus
                    .CREDIT
                )

        Purchase.objects.filter(
            pk=purchase.pk
        ).update(
            amount_paid=total_paid,
            remaining_amount=remaining,
            payment_status=payment_status,
            updated_at=timezone.now(),
        )

        purchase.amount_paid = total_paid
        purchase.remaining_amount = remaining
        purchase.payment_status = (
            payment_status
        )

        Purchase.update_supplier_balance(
            purchase.supplier
        )

    def save(self, *args, **kwargs):
        if not self.purchase_id:
            raise ValidationError(
                {
                    "purchase": (
                        "Sélectionnez un achat."
                    )
                }
            )

        with transaction.atomic():
            locked_purchase = (
                Purchase.objects
                .select_for_update()
                .get(pk=self.purchase_id)
            )

            self.purchase = locked_purchase

            self.supplier = (
                locked_purchase.supplier
            )

            update_fields = kwargs.get(
                "update_fields"
            )

            if update_fields is not None:
                update_fields = set(
                    update_fields
                )

                update_fields.add(
                    "purchase"
                )

                update_fields.add(
                    "supplier"
                )

                kwargs["update_fields"] = list(
                    update_fields
                )

            self.full_clean()

            super().save(*args, **kwargs)

            PurchasePayment.synchronize_purchase(
                locked_purchase
            )

    def delete(self, *args, **kwargs):
        purchase_id = self.purchase_id

        with transaction.atomic():
            locked_purchase = (
                Purchase.objects
                .select_for_update()
                .get(pk=purchase_id)
            )

            result = super().delete(
                *args,
                **kwargs,
            )

            PurchasePayment.synchronize_purchase(
                locked_purchase
            )

        return result