from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from catalog.models import Product


class StockMovement(models.Model):
    class MovementType(models.TextChoices):
        IN = "in", "Entrée"
        OUT = "out", "Sortie"
        SALE = "sale", "Vente"
        CORRECTION = "correction", "Correction"

    product = models.ForeignKey(
        Product,
        verbose_name="Produit",
        on_delete=models.CASCADE,
        related_name="stock_movements",
    )

    movement_type = models.CharField(
        "Type de mouvement",
        max_length=20,
        choices=MovementType.choices,
    )

    batch_reference = models.CharField(
        "Référence du bon",
        max_length=80,
        blank=True,
        db_index=True,
        help_text=(
            "Référence commune aux produits enregistrés "
            "dans la même entrée ou la même sortie."
        ),
    )

    quantity = models.DecimalField(
        "Quantité",
        max_digits=18,
        decimal_places=2,
        validators=[
            MinValueValidator(
                Decimal("0.01")
            )
        ],
    )

    old_quantity = models.DecimalField(
        "Ancienne quantité",
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    new_quantity = models.DecimalField(
        "Nouvelle quantité",
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    reason = models.CharField(
        "Motif",
        max_length=255,
        blank=True,
    )

    created_at = models.DateTimeField(
        "Créé le",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "Mouvement de stock"
        verbose_name_plural = "Mouvements de stock"
        ordering = [
            "-created_at",
            "-pk",
        ]
        indexes = [
            models.Index(
                fields=["movement_type"],
            ),
            models.Index(
                fields=["created_at"],
            ),
            models.Index(
                fields=[
                    "batch_reference",
                    "movement_type",
                ],
            ),
        ]

    def __str__(self):
        reference = (
            self.batch_reference
            or f"MVT-{self.pk}"
        )

        return (
            f"{reference} - "
            f"{self.get_movement_type_display()} - "
            f"{self.product.name} - "
            f"{self.quantity}"
        )