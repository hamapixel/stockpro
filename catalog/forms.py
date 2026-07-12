from django import forms

from .models import Category, Product, Unit


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = [
            "name",
            "description",
            "is_active",
        ]

        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ex: Électricité",
            }),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Petite description de la catégorie",
            }),
            "is_active": forms.CheckboxInput(attrs={
                "class": "form-check-input",
            }),
        }


class UnitForm(forms.ModelForm):
    class Meta:
        model = Unit
        fields = [
            "name",
            "short_name",
        ]

        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ex: Pièce",
            }),
            "short_name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ex: pcs",
            }),
        }


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "category",
            "unit",
            "name",
            "reference",
            "barcode",
            "purchase_price",
            "sale_price",
            "stock_quantity",
            "alert_quantity",
            "description",
            "image",
            "is_active",
        ]

        widgets = {
            "category": forms.Select(attrs={
                "class": "form-select",
            }),
            "unit": forms.Select(attrs={
                "class": "form-select",
            }),
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ex: Ampoule rechargeable 20W",
            }),
            "reference": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ex: AMP-20W-001",
            }),
            "barcode": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Code-barres si disponible",
            }),
            "purchase_price": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "0",
                "step": "0.01",
                "placeholder": "Prix d'achat",
            }),
            "sale_price": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "0",
                "step": "0.01",
                "placeholder": "Prix de vente",
            }),
            "stock_quantity": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "0",
                "step": "0.01",
                "placeholder": "Quantité en stock",
            }),
            "alert_quantity": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "0",
                "step": "0.01",
                "placeholder": "Stock minimum",
            }),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Description du produit",
            }),
            "image": forms.ClearableFileInput(attrs={
                "class": "form-control",
            }),
            "is_active": forms.CheckboxInput(attrs={
                "class": "form-check-input",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["category"].queryset = Category.objects.filter(is_active=True).order_by("name")
        self.fields["unit"].queryset = Unit.objects.all().order_by("name")

        self.fields["category"].empty_label = "Choisir une catégorie"
        self.fields["unit"].empty_label = "Choisir une unité"