from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Expense(models.Model):
    class ExpenseCategory(models.TextChoices):
        RENT = "rent", "Loyer"
        TRANSPORT = "transport", "Transport"
        SALARY = "salary", "Salaire"
        FOOD = "food", "Nourriture"
        ELECTRICITY = "electricity", "Électricité"
        INTERNET = "internet", "Internet"
        MAINTENANCE = "maintenance", "Maintenance"
        OTHER = "other", "Autre"

    title = models.CharField("Titre", max_length=180)

    category = models.CharField(
        "Catégorie",
        max_length=30,
        choices=ExpenseCategory.choices,
        default=ExpenseCategory.OTHER,
    )

    amount = models.DecimalField(
        "Montant",
        max_digits=18,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    expense_date = models.DateTimeField("Date dépense", default=timezone.now)

    description = models.TextField("Description", blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Créé par",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_expenses",
    )

    created_at = models.DateTimeField("Créé le", auto_now_add=True)
    updated_at = models.DateTimeField("Modifié le", auto_now=True)

    class Meta:
        verbose_name = "Dépense"
        verbose_name_plural = "Dépenses"
        ordering = ["-expense_date"]
        indexes = [
            models.Index(fields=["expense_date"]),
            models.Index(fields=["category"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.amount}"