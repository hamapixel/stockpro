from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone

from catalog.models import Product
from customers.models import Client
from inventory.models import StockMovement


ZERO = Decimal("0.00")


def generate_sale_number():
    """
    Génère un numéro de vente unique.

    L'utilisation d'un identifiant aléatoire évite les collisions
    lorsque deux ventes sont enregistrées presque simultanément.
    """
    today = timezone.localdate()

    return (
        f"VTE-{today:%Y%m%d}-"
        f"{uuid4().hex[:8].upper()}"
    )


class Sale(models.Model):
    class PaymentStatus(models.TextChoices):
        PAID = "paid", "Payé"
        PARTIAL = "partial", "Partiel"
        CREDIT = "credit", "Crédit"
        CANCELLED = "cancelled", "Annulé"

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Espèce"
        ORANGE_MONEY = "orange_money", "Orange Money"
        WAVE = "wave", "Wave"
        BANK_TRANSFER = "bank_transfer", "Virement"
        CREDIT = "credit", "Crédit"
        OTHER = "other", "Autre"

    sale_number = models.CharField(
        "Numéro de vente",
        max_length=40,
        unique=True,
        blank=True,
    )

    client = models.ForeignKey(
        Client,
        verbose_name="Client",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales",
    )

    sale_date = models.DateTimeField(
        "Date de vente",
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
        "Statut paiement",
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
        related_name="created_sales",
    )

    is_cancelled = models.BooleanField(
        "Vente annulée",
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
        verbose_name = "Vente"
        verbose_name_plural = "Ventes"
        ordering = ["-sale_date"]
        indexes = [
            models.Index(fields=["sale_number"]),
            models.Index(fields=["sale_date"]),
            models.Index(fields=["payment_status"]),
            models.Index(fields=["payment_method"]),
        ]

    def __str__(self):
        return self.sale_number or "Vente non enregistrée"

    def save(self, *args, **kwargs):
        if not self.sale_number:
            self.sale_number = generate_sale_number()

        if self.is_cancelled:
            self.payment_status = (
                self.PaymentStatus.CANCELLED
            )

            self.remaining_amount = ZERO

            update_fields = kwargs.get("update_fields")

            if update_fields is not None:
                update_fields = set(update_fields)
                update_fields.add("payment_status")
                update_fields.add("remaining_amount")
                update_fields.add("sale_number")

                kwargs["update_fields"] = list(
                    update_fields
                )

        super().save(*args, **kwargs)

    def calculate_totals(self, save=True):
        """
        Recalcule les montants de la vente à partir des lignes
        et des paiements réellement enregistrés.
        """
        if not self.pk:
            return ZERO

        subtotal = (
            self.items.aggregate(
                total=Sum("total_line")
            )["total"]
            or ZERO
        )

        total = subtotal - (self.discount or ZERO)

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

            if total > ZERO and total_paid >= total:
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
            self.save(
                update_fields=[
                    "subtotal",
                    "total",
                    "amount_paid",
                    "remaining_amount",
                    "payment_status",
                    "updated_at",
                ]
            )

        return self.total

    @classmethod
    def update_client_balance(cls, client):
        """
        Recalcule la dette globale d'un client.

        Les ventes annulées sont toujours exclues.
        """
        if client is None:
            return

        balance = (
            cls.objects.filter(
                client=client,
                is_cancelled=False,
            ).aggregate(
                total=Sum("remaining_amount")
            )["total"]
            or ZERO
        )

        client.balance = balance

        client.save(
            update_fields=[
                "balance",
                "updated_at",
            ]
        )

    def cancel_sale(
        self,
        cancelled_by=None,
        reason="",
    ):
        """
        Annule complètement une vente.

        Toutes les quantités sont restaurées dans une seule
        transaction. Si une erreur apparaît, rien n'est modifié.
        """
        if not self.pk:
            raise ValidationError(
                "Cette vente n'est pas enregistrée."
            )

        with transaction.atomic():
            # Le client est nullable : on verrouille
            # uniquement la vente pour éviter l'erreur
            # PostgreSQL sur une jointure externe.
            locked_sale = (
                Sale.objects
                .select_for_update()
                .get(pk=self.pk)
            )

            if locked_sale.is_cancelled:
                return False

            items = list(
                locked_sale.items
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
                    .filter(pk__in=product_ids)
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
                        (
                            "Impossible de restaurer le "
                            f"produit {item.product_id}."
                        )
                    )

                old_quantity = (
                    product.stock_quantity
                    or ZERO
                )

                new_quantity = (
                    old_quantity + item.quantity
                )

                product.stock_quantity = new_quantity

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
                        "Annulation de la vente "
                        f"{locked_sale.sale_number}"
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
                        .IN
                    ),
                    quantity=item.quantity,
                    old_quantity=old_quantity,
                    new_quantity=new_quantity,
                    reason=movement_reason,
                )

            locked_sale.is_cancelled = True

            locked_sale.payment_status = (
                Sale.PaymentStatus.CANCELLED
            )

            locked_sale.remaining_amount = ZERO

            locked_sale.save(
                update_fields=[
                    "is_cancelled",
                    "payment_status",
                    "remaining_amount",
                    "updated_at",
                ]
            )

            Sale.update_client_balance(
                locked_sale.client
            )

            self.is_cancelled = True

            self.payment_status = (
                Sale.PaymentStatus.CANCELLED
            )

            self.remaining_amount = ZERO

        return True


class SaleItem(models.Model):
    sale = models.ForeignKey(
        Sale,
        verbose_name="Vente",
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        Product,
        verbose_name="Produit",
        on_delete=models.PROTECT,
        related_name="sale_items",
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

    unit_price = models.DecimalField(
        "Prix unitaire",
        max_digits=18,
        decimal_places=2,
        validators=[
            MinValueValidator(ZERO),
        ],
    )

    discount = models.DecimalField(
        "Remise ligne",
        max_digits=18,
        decimal_places=2,
        default=ZERO,
        validators=[
            MinValueValidator(ZERO),
        ],
    )

    total_line = models.DecimalField(
        "Montant ligne",
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
        verbose_name = "Ligne de vente"
        verbose_name_plural = "Lignes de vente"

    def __str__(self):
        return (
            f"{self.product.name} "
            f"x {self.quantity}"
        )

    def clean(self):
        errors = {}

        if (
            self.sale_id
            and self.sale.is_cancelled
        ):
            errors["sale"] = (
                "Impossible de modifier une vente annulée."
            )

        quantity = self.quantity or ZERO
        unit_price = self.unit_price or ZERO
        discount = self.discount or ZERO

        gross_total = quantity * unit_price

        if discount > gross_total:
            errors["discount"] = (
                "La remise ne peut pas dépasser "
                "le montant de la ligne."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()

        total = (
            self.quantity * self.unit_price
        ) - self.discount

        if total < ZERO:
            total = ZERO

        self.total_line = total

        super().save(*args, **kwargs)