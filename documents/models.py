from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone

from catalog.models import Product
from customers.models import Client


ZERO = Decimal("0.00")


def generate_proforma_number():
    """
    Exemple : PRO-20260717-A1B2C3D4
    """
    today = timezone.localdate()

    return (
        f"PRO-{today:%Y%m%d}-"
        f"{uuid4().hex[:8].upper()}"
    )


def default_valid_until():
    return timezone.localdate() + timedelta(
        days=15
    )


def get_proforma_local_date(value):
    """
    Retourne la date locale d'une valeur datetime,
    qu'elle soit avec ou sans fuseau horaire.
    """
    if value is None:
        return None

    if timezone.is_aware(value):
        return timezone.localtime(
            value
        ).date()

    return value.date()


class Proforma(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        SENT = "sent", "Envoyée"
        ACCEPTED = "accepted", "Acceptée"
        REJECTED = "rejected", "Refusée"
        CONVERTED = (
            "converted",
            "Convertie en vente",
        )
        CANCELLED = "cancelled", "Annulée"

    proforma_number = models.CharField(
        "Numéro de proforma",
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
        related_name="proformas",
    )

    proforma_date = models.DateTimeField(
        "Date de la proforma",
        default=timezone.now,
    )

    valid_until = models.DateField(
        "Valable jusqu’au",
        default=default_valid_until,
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

    status = models.CharField(
        "Statut",
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    notes = models.TextField(
        "Notes",
        blank=True,
    )

    terms = models.TextField(
        "Conditions commerciales",
        blank=True,
        default=(
            "Cette proforma est valable jusqu’à la "
            "date indiquée. Les prix et les "
            "disponibilités peuvent évoluer après "
            "expiration."
        ),
    )

    converted_sale = models.OneToOneField(
        "sales.Sale",
        verbose_name="Vente créée",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_proforma",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Créé par",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_proformas",
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
        verbose_name = "Proforma"
        verbose_name_plural = "Proformas"
        ordering = [
            "-proforma_date",
            "-created_at",
        ]
        indexes = [
            models.Index(
                fields=["proforma_number"],
            ),
            models.Index(
                fields=["proforma_date"],
            ),
            models.Index(
                fields=["valid_until"],
            ),
            models.Index(
                fields=["status"],
            ),
        ]

    def __str__(self):
        return (
            self.proforma_number
            or "Proforma non enregistrée"
        )

    @property
    def is_expired(self):
        return (
            self.valid_until
            < timezone.localdate()
            and self.status
            not in {
                self.Status.CONVERTED,
                self.Status.CANCELLED,
            }
        )

    @property
    def can_be_modified(self):
        return self.status not in {
            self.Status.CONVERTED,
            self.Status.CANCELLED,
        }

    @property
    def can_be_converted(self):
        return (
            self.client_id is not None
            and not self.is_expired
            and self.status
            not in {
                self.Status.CONVERTED,
                self.Status.CANCELLED,
                self.Status.REJECTED,
            }
            and self.items.exists()
        )

    def clean(self):
        errors = {}

        proforma_day = None

        if self.proforma_date:
            try:
                proforma_day = (
                    get_proforma_local_date(
                        self.proforma_date
                    )
                )
            except (
                AttributeError,
                TypeError,
                ValueError,
            ):
                errors["proforma_date"] = (
                    "La date de la proforma "
                    "n'est pas valide."
                )

        if (
            proforma_day
            and self.valid_until
            and self.valid_until
            < proforma_day
        ):
            errors["valid_until"] = (
                "La date de validité ne peut pas "
                "être antérieure à la date de la "
                "proforma."
            )

        if (
            self.converted_sale_id
            and self.status
            != self.Status.CONVERTED
        ):
            errors["status"] = (
                "Une proforma liée à une vente "
                "doit avoir le statut « Convertie "
                "en vente »."
            )

        if (
            self.status
            == self.Status.CONVERTED
            and not self.converted_sale_id
        ):
            errors["converted_sale"] = (
                "Une proforma convertie doit être "
                "liée à la vente créée."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.proforma_number:
            self.proforma_number = (
                generate_proforma_number()
            )

        if self.converted_sale_id:
            self.status = self.Status.CONVERTED

        self.full_clean()

        update_fields = kwargs.get(
            "update_fields"
        )

        if update_fields is not None:
            update_fields = set(update_fields)
            update_fields.add(
                "proforma_number"
            )

            if self.converted_sale_id:
                update_fields.add("status")

            kwargs["update_fields"] = list(
                update_fields
            )

        super().save(*args, **kwargs)

    def calculate_totals(self, save=True):
        if not self.pk:
            return ZERO

        subtotal = (
            self.items.aggregate(
                total=Sum("total_line")
            )["total"]
            or ZERO
        )

        discount = self.discount or ZERO

        if discount > subtotal:
            discount = subtotal

        total = subtotal - discount

        if total < ZERO:
            total = ZERO

        self.subtotal = subtotal
        self.discount = discount
        self.total = total

        if save:
            self.save(
                update_fields=[
                    "subtotal",
                    "discount",
                    "total",
                    "updated_at",
                ]
            )

        return self.total

    def cancel(self):
        if (
            self.status
            == self.Status.CONVERTED
        ):
            raise ValidationError(
                "Une proforma déjà convertie "
                "ne peut pas être annulée."
            )

        if (
            self.status
            == self.Status.CANCELLED
        ):
            return False

        self.status = self.Status.CANCELLED

        self.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        return True


class ProformaItem(models.Model):
    proforma = models.ForeignKey(
        Proforma,
        verbose_name="Proforma",
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        Product,
        verbose_name="Produit",
        on_delete=models.PROTECT,
        related_name="proforma_items",
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
        "Prix unitaire proposé",
        max_digits=18,
        decimal_places=2,
        validators=[
            MinValueValidator(ZERO),
        ],
    )

    discount = models.DecimalField(
        "Remise de la ligne",
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

    updated_at = models.DateTimeField(
        "Modifié le",
        auto_now=True,
    )

    class Meta:
        verbose_name = "Ligne de proforma"
        verbose_name_plural = (
            "Lignes de proforma"
        )
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "proforma",
                    "product",
                ],
                name=(
                    "unique_product_per_"
                    "proforma"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    quantity__gt=ZERO
                ),
                name=(
                    "proforma_item_"
                    "quantity_gt_zero"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    unit_price__gte=ZERO
                ),
                name=(
                    "proforma_item_"
                    "unit_price_gte_zero"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    discount__gte=ZERO
                ),
                name=(
                    "proforma_item_"
                    "discount_gte_zero"
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

        quantity = self.quantity or ZERO
        unit_price = self.unit_price or ZERO
        discount = self.discount or ZERO

        if (
            self.proforma_id
            and not self.proforma.can_be_modified
        ):
            errors["proforma"] = (
                "Impossible de modifier une "
                "proforma convertie ou annulée."
            )

        if quantity <= ZERO:
            errors["quantity"] = (
                "La quantité doit être "
                "supérieure à zéro."
            )

        if unit_price < ZERO:
            errors["unit_price"] = (
                "Le prix unitaire ne peut pas "
                "être négatif."
            )

        if discount < ZERO:
            errors["discount"] = (
                "La remise ne peut pas être "
                "négative."
            )

        gross_total = quantity * unit_price

        if discount > gross_total:
            errors["discount"] = (
                "La remise ne peut pas dépasser "
                "le montant brut de la ligne."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()

        total_line = (
            self.quantity
            * self.unit_price
        ) - self.discount

        if total_line < ZERO:
            total_line = ZERO

        self.total_line = total_line

        super().save(*args, **kwargs)