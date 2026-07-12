from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class Client(models.Model):
    full_name = models.CharField("Nom complet", max_length=160)
    phone = models.CharField("Téléphone", max_length=40, blank=True)
    address = models.CharField("Adresse", max_length=255, blank=True)
    email = models.EmailField("Email", blank=True)

    balance = models.DecimalField(
        "Dette totale",
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    created_at = models.DateTimeField("Créé le", auto_now_add=True)
    updated_at = models.DateTimeField("Modifié le", auto_now=True)

    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        ordering = ["full_name"]
        indexes = [
            models.Index(fields=["full_name"]),
            models.Index(fields=["phone"]),
        ]

    def __str__(self):
        if self.phone:
            return f"{self.full_name} - {self.phone}"
        return self.full_name