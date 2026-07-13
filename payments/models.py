from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone

from customers.models import Client
from sales.models import Sale


ZERO = Decimal("0.00")


class Payment(models.Model):
    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Espèce"
        ORANGE_MONEY = (
            "orange_money",
            "Orange Money",
        )
        WAVE = "wave", "Wave"
        BANK_TRANSFER = (
            "bank_transfer",
            "Virement",
        )
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
        "Date paiement",
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
        related_name="created_payments",
    )

    created_at = models.DateTimeField(
        "Créé le",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"
        ordering = ["-payment_date"]
        indexes = [
            models.Index(
                fields=["payment_date"]
            ),
            models.Index(
                fields=["payment_method"]
            ),
        ]

    def __str__(self):
        sale_number = (
            self.sale.sale_number
            if self.sale_id
            else "Vente inconnue"
        )

        return (
            f"Paiement {self.amount} - "
            f"{sale_number}"
        )

    def clean(self):
        errors = {}

        if not self.sale_id:
            errors["sale"] = (
                "Sélectionnez une vente."
            )

        if (
            self.amount is None
            or self.amount <= ZERO
        ):
            errors["amount"] = (
                "Le montant doit être supérieur à zéro."
            )

        if self.sale_id:
            sale = self.sale

            if sale.is_cancelled:
                errors["sale"] = (
                    "Impossible d'ajouter un paiement "
                    "à une vente annulée."
                )

            other_payments_total = (
                Payment.objects
                .filter(
                    sale_id=self.sale_id
                )
                .exclude(pk=self.pk)
                .aggregate(
                    total=Sum("amount")
                )["total"]
                or ZERO
            )

            maximum_allowed = (
                sale.total
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
                    "Le paiement dépasse le reste "
                    "à payer. Maximum autorisé : "
                    f"{maximum_allowed} F CFA."
                )

        if errors:
            raise ValidationError(errors)

    @classmethod
    def synchronize_sale(
        cls,
        sale,
    ):
        """
        Recalcule les montants de la vente après
        création, modification ou suppression
        d'un paiement.
        """
        total_paid = (
            cls.objects
            .filter(
                sale_id=sale.pk
            )
            .aggregate(
                total=Sum("amount")
            )["total"]
            or ZERO
        )

        if sale.is_cancelled:
            remaining = ZERO

            payment_status = (
                Sale.PaymentStatus.CANCELLED
            )

        else:
            remaining = (
                sale.total
                - total_paid
            )

            if remaining < ZERO:
                remaining = ZERO

            if (
                sale.total > ZERO
                and total_paid
                >= sale.total
            ):
                payment_status = (
                    Sale.PaymentStatus.PAID
                )

                remaining = ZERO

            elif total_paid > ZERO:
                payment_status = (
                    Sale.PaymentStatus.PARTIAL
                )

            else:
                payment_status = (
                    Sale.PaymentStatus.CREDIT
                )

        Sale.objects.filter(
            pk=sale.pk
        ).update(
            amount_paid=total_paid,
            remaining_amount=remaining,
            payment_status=payment_status,
            updated_at=timezone.now(),
        )

        sale.amount_paid = total_paid
        sale.remaining_amount = remaining
        sale.payment_status = payment_status

        Sale.update_client_balance(
            sale.client
        )

    def save(
        self,
        *args,
        **kwargs,
    ):
        if not self.sale_id:
            raise ValidationError(
                {
                    "sale": (
                        "Sélectionnez une vente."
                    )
                }
            )

        with transaction.atomic():
            # IMPORTANT :
            # Ne pas utiliser select_related("client")
            # avec select_for_update(), car le client
            # est nullable. PostgreSQL peut refuser de
            # verrouiller le côté nullable d'une jointure.
            locked_sale = (
                Sale.objects
                .select_for_update()
                .get(pk=self.sale_id)
            )

            self.sale = locked_sale
            self.client = (
                locked_sale.client
            )

            update_fields = kwargs.get(
                "update_fields"
            )

            if update_fields is not None:
                update_fields = set(
                    update_fields
                )

                update_fields.add("sale")
                update_fields.add("client")

                kwargs["update_fields"] = list(
                    update_fields
                )

            self.full_clean()

            super().save(
                *args,
                **kwargs,
            )

            Payment.synchronize_sale(
                locked_sale
            )

    def delete(
        self,
        *args,
        **kwargs,
    ):
        sale_id = self.sale_id

        if not sale_id:
            return super().delete(
                *args,
                **kwargs,
            )

        with transaction.atomic():
            # Même correction PostgreSQL ici :
            # verrouillage de la vente seulement.
            locked_sale = (
                Sale.objects
                .select_for_update()
                .get(pk=sale_id)
            )

            result = super().delete(
                *args,
                **kwargs,
            )

            Payment.synchronize_sale(
                locked_sale
            )

        return result