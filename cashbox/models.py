from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class CashMovement(models.Model):
    class MovementType(models.TextChoices):
        SALE_IN = "sale_in", "Encaissement vente"
        PAYMENT_IN = "payment_in", "Paiement crédit"
        EXPENSE_OUT = "expense_out", "Dépense"
        ADJUSTMENT_IN = "adjustment_in", "Ajustement entrée"
        ADJUSTMENT_OUT = "adjustment_out", "Ajustement sortie"

    movement_type = models.CharField(
        "Type mouvement",
        max_length=30,
        choices=MovementType.choices,
    )

    amount = models.DecimalField(
        "Montant",
        max_digits=18,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    movement_date = models.DateTimeField("Date mouvement", default=timezone.now)

    sale = models.ForeignKey(
        "sales.Sale",
        verbose_name="Vente",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cash_movements",
    )

    payment = models.ForeignKey(
        "payments.Payment",
        verbose_name="Paiement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cash_movements",
    )

    expense = models.ForeignKey(
        "expenses.Expense",
        verbose_name="Dépense",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cash_movements",
    )

    notes = models.TextField("Notes", blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Créé par",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_cash_movements",
    )

    created_at = models.DateTimeField("Créé le", auto_now_add=True)

    class Meta:
        verbose_name = "Mouvement de caisse"
        verbose_name_plural = "Mouvements de caisse"
        ordering = ["-movement_date"]
        indexes = [
            models.Index(fields=["movement_type"]),
            models.Index(fields=["movement_date"]),
        ]

    def __str__(self):
        return f"{self.get_movement_type_display()} - {self.amount}"