from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from customers.models import Client

from .models import (
    Proforma,
    default_valid_until,
)


ZERO = Decimal("0.00")


class ProformaHeaderForm(forms.ModelForm):
    proforma_date = forms.DateTimeField(
        label="Date de la proforma",
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

    valid_until = forms.DateField(
        label="Valable jusqu’au",
        input_formats=[
            "%Y-%m-%d",
        ],
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={
                "type": "date",
                "class": "form-control",
            },
        ),
    )

    class Meta:
        model = Proforma

        fields = [
            "client",
            "proforma_date",
            "valid_until",
            "status",
            "discount",
            "notes",
            "terms",
        ]

        widgets = {
            "client": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "status": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "discount": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "step": "0.01",
                    "placeholder": "0",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": (
                        "Notes internes ou "
                        "précisions..."
                    ),
                }
            ),
            "terms": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": (
                        "Conditions commerciales..."
                    ),
                }
            ),
        }

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        self.fields["client"].queryset = (
            Client.objects.order_by(
                "full_name"
            )
        )

        self.fields["client"].required = True

        self.fields["client"].empty_label = (
            "Sélectionner un client"
        )

        allowed_statuses = {
            Proforma.Status.DRAFT,
            Proforma.Status.SENT,
            Proforma.Status.ACCEPTED,
            Proforma.Status.REJECTED,
        }

        self.fields["status"].choices = [
            choice
            for choice
            in Proforma.Status.choices
            if choice[0]
            in allowed_statuses
        ]

        if (
            not self.is_bound
            and not self.instance.pk
        ):
            self.initial[
                "proforma_date"
            ] = (
                timezone.localtime()
                .strftime("%Y-%m-%dT%H:%M")
            )

            self.initial[
                "valid_until"
            ] = default_valid_until()

            self.initial["discount"] = ZERO

    def clean_discount(self):
        discount = self.cleaned_data.get(
            "discount"
        )

        if discount is None:
            return ZERO

        if discount < ZERO:
            raise ValidationError(
                "La remise globale ne peut pas "
                "être négative."
            )

        return discount

    def clean(self):
        cleaned_data = super().clean()

        proforma_date = cleaned_data.get(
            "proforma_date"
        )

        valid_until = cleaned_data.get(
            "valid_until"
        )

        if (
            proforma_date
            and valid_until
            and valid_until
            < timezone.localdate(
                proforma_date
            )
        ):
            self.add_error(
                "valid_until",
                (
                    "La date de validité ne peut "
                    "pas être antérieure à la date "
                    "de la proforma."
                ),
            )

        return cleaned_data