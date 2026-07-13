from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.utils import timezone

from .models import Payment


ZERO = Decimal("0.00")


class PaymentForm(forms.ModelForm):
    payment_date = forms.DateTimeField(
        label="Date du paiement",
        input_formats=[
            "%Y-%m-%dT%H:%M",
        ],
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M",
            attrs={
                "type": "datetime-local",
                "class": "form-control",
            },
        ),
    )

    class Meta:
        model = Payment

        fields = [
            "amount",
            "payment_method",
            "payment_date",
            "notes",
        ]

        widgets = {
            "amount": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0.01",
                    "step": "0.01",
                    "placeholder": "Montant payé",
                }
            ),
            "payment_method": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Note facultative...",
                }
            ),
        }

    def __init__(
        self,
        *args,
        sale=None,
        **kwargs,
    ):
        self.sale = sale

        super().__init__(
            *args,
            **kwargs,
        )

        # Le champ sale n'est pas affiché dans le formulaire,
        # mais Django valide l'instance Payment complète.
        # Il faut donc affecter la vente avant form.is_valid().
        if self.sale is not None:
            self.instance.sale = self.sale
            self.instance.client = self.sale.client

        if not self.instance.pk:
            self.fields["payment_date"].initial = (
                timezone.localtime()
                .strftime("%Y-%m-%dT%H:%M")
            )

        if self.sale is not None:
            remaining = (
                self.sale.remaining_amount
                or ZERO
            )

            self.fields["amount"].widget.attrs[
                "max"
            ] = str(remaining)

            self.fields["amount"].help_text = (
                f"Reste actuel : {remaining:,.0f} F CFA"
                .replace(",", " ")
            )

            if (
                not self.is_bound
                and not self.instance.pk
            ):
                self.fields["amount"].initial = (
                    remaining
                )

    def clean_amount(self):
        amount = self.cleaned_data.get(
            "amount"
        )

        if amount is None:
            raise ValidationError(
                "Saisissez le montant du paiement."
            )

        if amount <= ZERO:
            raise ValidationError(
                "Le montant doit être supérieur à zéro."
            )

        if self.sale is None:
            raise ValidationError(
                "La vente liée au paiement est introuvable."
            )

        if self.sale.is_cancelled:
            raise ValidationError(
                "Cette vente est annulée. "
                "Aucun paiement n'est autorisé."
            )

        other_payments = (
            Payment.objects
            .filter(sale_id=self.sale.pk)
            .exclude(pk=self.instance.pk)
            .aggregate(total=Sum("amount"))["total"]
            or ZERO
        )

        maximum_allowed = (
            self.sale.total
            - other_payments
        )

        if maximum_allowed < ZERO:
            maximum_allowed = ZERO

        if amount > maximum_allowed:
            formatted_amount = (
                f"{maximum_allowed:,.0f}"
                .replace(",", " ")
            )

            raise ValidationError(
                "Le paiement dépasse le reste à payer. "
                f"Maximum autorisé : "
                f"{formatted_amount} F CFA."
            )

        return amount

    def clean(self):
        cleaned_data = super().clean()

        if (
            self.sale is not None
            and self.sale.is_cancelled
        ):
            raise ValidationError(
                "Impossible d'enregistrer un paiement "
                "sur une vente annulée."
            )

        return cleaned_data