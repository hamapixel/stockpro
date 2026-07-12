from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from customers.models import Client
from sales.models import Sale


class Payment(models.Model):
    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Espèce"
        ORANGE_MONEY = "orange_money", "Orange Money"
        WAVE = "wave", "Wave"
        BANK_TRANSFER = "bank_transfer", "Virement"
        OTHER = "other", "Autre"

    sale = models.ForeignKey(
        Sale,
        verbose_name="Vente",
        on_delete=models.CASCADE,
        related_name="payments",
    )

    client = models.ForeignKey(
        Client,
        verbose_name="Client",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )

    amount = models.DecimalField(
        "Montant payé",
        max_digits=18,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    payment_method = models.CharField(
        "Mode de paiement",
        max_length=30,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
    )

    payment_date = models.DateTimeField("Date paiement", default=timezone.now)

    notes = models.TextField("Notes", blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Créé par",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_payments",
    )

    created_at = models.DateTimeField("Créé le", auto_now_add=True)

    class Meta:
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"
        ordering = ["-payment_date"]
        indexes = [
            models.Index(fields=["payment_date"]),
            models.Index(fields=["payment_method"]),
        ]

    def __str__(self):
        return f"Paiement {self.amount} - {self.sale.sale_number}"

    def save(self, *args, **kwargs):
        if self.sale and not self.client:
            self.client = self.sale.client

        super().save(*args, **kwargs)

        self.update_sale_payment()
        self.update_client_balance()

    def update_sale_payment(self):
        total_paid = Payment.objects.filter(
            sale=self.sale
        ).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")

        self.sale.amount_paid = total_paid

        remaining = self.sale.total - total_paid

        if remaining < Decimal("0.00"):
            remaining = Decimal("0.00")

        self.sale.remaining_amount = remaining

        if self.sale.is_cancelled:
            self.sale.payment_status = Sale.PaymentStatus.CANCELLED
        elif total_paid >= self.sale.total and self.sale.total > Decimal("0.00"):
            self.sale.payment_status = Sale.PaymentStatus.PAID
            self.sale.remaining_amount = Decimal("0.00")
        elif total_paid > Decimal("0.00"):
            self.sale.payment_status = Sale.PaymentStatus.PARTIAL
        else:
            self.sale.payment_status = Sale.PaymentStatus.CREDIT

        self.sale.save(
            update_fields=[
                "amount_paid",
                "remaining_amount",
                "payment_status",
                "updated_at",
            ]
        )

    def update_client_balance(self):
        if not self.client:
            return

        balance = Sale.objects.filter(
            client=self.client,
            is_cancelled=False,
        ).aggregate(
            total=Sum("remaining_amount")
        )["total"] or Decimal("0.00")

        self.client.balance = balance
        self.client.save(update_fields=["balance", "updated_at"])