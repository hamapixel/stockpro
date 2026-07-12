from decimal import Decimal

from django import forms

from .models import Payment


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = [
            "amount",
            "payment_method",
            "notes",
        ]

        widgets = {
            "amount": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "0.01",
                "step": "0.01",
                "placeholder": "Montant payé",
            }),
            "payment_method": forms.Select(attrs={
                "class": "form-select",
            }),
            "notes": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Note facultative",
            }),
        }

    def __init__(self, *args, **kwargs):
        self.sale = kwargs.pop("sale", None)
        super().__init__(*args, **kwargs)

        self.fields["amount"].label = "Montant payé"
        self.fields["payment_method"].label = "Mode de paiement"
        self.fields["notes"].label = "Notes"

    def clean_amount(self):
        amount = self.cleaned_data.get("amount") or Decimal("0.00")

        if amount <= Decimal("0.00"):
            raise forms.ValidationError("Le montant doit être supérieur à 0.")

        if self.sale and amount > self.sale.remaining_amount:
            raise forms.ValidationError(
                f"Le montant ne peut pas dépasser le reste à payer : {self.sale.remaining_amount} F CFA."
            )

        return amount