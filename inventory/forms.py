from decimal import Decimal

from django import forms

from catalog.models import Product


class StockInForm(forms.Form):
    product = forms.ModelChoiceField(
        label="Produit",
        queryset=Product.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    quantity = forms.DecimalField(
        label="Quantité à ajouter",
        min_value=Decimal("0.01"),
        max_digits=18,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "step": "0.01",
            "min": "0.01",
            "placeholder": "Ex: 10",
        }),
    )

    reason = forms.CharField(
        label="Note / motif",
        required=False,
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 3,
            "placeholder": "Ex: Nouvelle livraison fournisseur",
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["product"].queryset = Product.objects.filter(
            is_active=True
        ).order_by("name")

        self.fields["product"].empty_label = "Choisir un produit"


class StockOutForm(forms.Form):
    product = forms.ModelChoiceField(
        label="Produit",
        queryset=Product.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    quantity = forms.DecimalField(
        label="Quantité à sortir",
        min_value=Decimal("0.01"),
        max_digits=18,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "step": "0.01",
            "min": "0.01",
            "placeholder": "Ex: 5",
        }),
    )

    reason = forms.CharField(
        label="Motif de sortie",
        required=False,
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 3,
            "placeholder": "Ex: Produit cassé, correction stock, retrait manuel...",
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["product"].queryset = Product.objects.filter(
            is_active=True
        ).order_by("name")

        self.fields["product"].empty_label = "Choisir un produit"