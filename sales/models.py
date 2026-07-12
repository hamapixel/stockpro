from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from catalog.models import Product
from customers.models import Client
from inventory.models import StockMovement


def generate_sale_number():
    today = timezone.localdate()
    prefix = today.strftime("VTE-%Y%m%d")

    count = Sale.objects.filter(
        sale_date__date=today
    ).count() + 1

    return f"{prefix}-{count:04d}"


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

    sale_date = models.DateTimeField("Date de vente", default=timezone.now)

    subtotal = models.DecimalField(
        "Sous-total",
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    discount = models.DecimalField(
        "Remise globale",
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    total = models.DecimalField(
        "Total net",
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    amount_paid = models.DecimalField(
        "Montant payé",
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    remaining_amount = models.DecimalField(
        "Reste à payer",
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
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

    notes = models.TextField("Notes", blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Créé par",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_sales",
    )

    is_cancelled = models.BooleanField("Vente annulée", default=False)

    created_at = models.DateTimeField("Créé le", auto_now_add=True)
    updated_at = models.DateTimeField("Modifié le", auto_now=True)

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
        return self.sale_number

    def save(self, *args, **kwargs):
        if not self.sale_number:
            self.sale_number = generate_sale_number()

        if self.is_cancelled:
            self.payment_status = self.PaymentStatus.CANCELLED

        super().save(*args, **kwargs)

    def calculate_totals(self, save=True):
        subtotal = Decimal("0.00")

        for item in self.items.all():
            subtotal += item.total_line

        total = subtotal - self.discount

        if total < Decimal("0.00"):
            total = Decimal("0.00")

        remaining = total - self.amount_paid

        if remaining < Decimal("0.00"):
            remaining = Decimal("0.00")

        self.subtotal = subtotal
        self.total = total
        self.remaining_amount = remaining

        if self.is_cancelled:
            self.payment_status = self.PaymentStatus.CANCELLED
        elif self.amount_paid >= self.total and self.total > Decimal("0.00"):
            self.payment_status = self.PaymentStatus.PAID
            self.remaining_amount = Decimal("0.00")
        elif self.amount_paid > Decimal("0.00"):
            self.payment_status = self.PaymentStatus.PARTIAL
        else:
            self.payment_status = self.PaymentStatus.CREDIT

        if save:
            self.save(
                update_fields=[
                    "subtotal",
                    "total",
                    "remaining_amount",
                    "payment_status",
                    "updated_at",
                ]
            )

        return self.total

    def cancel_sale(self):
        if self.is_cancelled:
            return

        for item in self.items.select_related("product"):
            product = item.product
            old_quantity = product.stock_quantity
            new_quantity = old_quantity + item.quantity

            product.stock_quantity = new_quantity
            product.save(update_fields=["stock_quantity", "updated_at"])

            StockMovement.objects.create(
                product=product,
                movement_type=StockMovement.MovementType.IN,
                quantity=item.quantity,
                old_quantity=old_quantity,
                new_quantity=new_quantity,
                reason=f"Annulation de la vente {self.sale_number}",
            )

        self.is_cancelled = True
        self.payment_status = self.PaymentStatus.CANCELLED
        self.save(update_fields=["is_cancelled", "payment_status", "updated_at"])


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
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    unit_price = models.DecimalField(
        "Prix unitaire",
        max_digits=18,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    discount = models.DecimalField(
        "Remise ligne",
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    total_line = models.DecimalField(
        "Montant ligne",
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    created_at = models.DateTimeField("Créé le", auto_now_add=True)

    class Meta:
        verbose_name = "Ligne de vente"
        verbose_name_plural = "Lignes de vente"

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

    def save(self, *args, **kwargs):
        total = (self.quantity * self.unit_price) - self.discount

        if total < Decimal("0.00"):
            total = Decimal("0.00")

        self.total_line = total

        super().save(*args, **kwargs)