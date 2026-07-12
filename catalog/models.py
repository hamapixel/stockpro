from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class Category(models.Model):
    name = models.CharField("Nom", max_length=120, unique=True)
    description = models.TextField("Description", blank=True)
    is_active = models.BooleanField("Actif", default=True)
    created_at = models.DateTimeField("Créé le", auto_now_add=True)
    updated_at = models.DateTimeField("Modifié le", auto_now=True)

    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Unit(models.Model):
    name = models.CharField("Nom", max_length=80, unique=True)
    short_name = models.CharField("Abréviation", max_length=20, unique=True)
    created_at = models.DateTimeField("Créé le", auto_now_add=True)

    class Meta:
        verbose_name = "Unité"
        verbose_name_plural = "Unités"
        ordering = ["name"]

    def __str__(self):
        return self.short_name


class Product(models.Model):
    category = models.ForeignKey(
        Category,
        verbose_name="Catégorie",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    unit = models.ForeignKey(
        Unit,
        verbose_name="Unité",
        on_delete=models.PROTECT,
        related_name="products",
    )

    name = models.CharField("Désignation", max_length=180)
    reference = models.CharField(
        "Référence",
        max_length=80,
        unique=True,
        null=True,
        blank=True,
    )
    barcode = models.CharField(
        "Code-barres",
        max_length=100,
        unique=True,
        null=True,
        blank=True,
    )

    purchase_price = models.DecimalField(
        "Prix d'achat",
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    sale_price = models.DecimalField(
        "Prix de vente",
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    stock_quantity = models.DecimalField(
        "Quantité en stock",
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    alert_quantity = models.DecimalField(
        "Stock minimum",
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    description = models.TextField("Description", blank=True)
    image = models.ImageField(
        "Image",
        upload_to="products/",
        null=True,
        blank=True,
    )

    is_active = models.BooleanField("Actif", default=True)
    created_at = models.DateTimeField("Créé le", auto_now_add=True)
    updated_at = models.DateTimeField("Modifié le", auto_now=True)

    class Meta:
        verbose_name = "Produit"
        verbose_name_plural = "Produits"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["reference"]),
            models.Index(fields=["barcode"]),
        ]

    def __str__(self):
        return self.name

    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.alert_quantity

    @property
    def margin(self):
        return self.sale_price - self.purchase_price