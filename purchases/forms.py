from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet
from django.utils import timezone

from catalog.models import Product

from .models import (
    Purchase,
    PurchaseItem,
    PurchasePayment,
    Supplier,
)


ZERO = Decimal("0.00")


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier

        fields = [
            "name",
            "phone",
            "email",
            "address",
            "is_active",
        ]

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": (
                        "Nom du fournisseur"
                    ),
                    "autocomplete": "off",
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": (
                        "Numéro de téléphone"
                    ),
                    "autocomplete": "off",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": (
                        "Adresse e-mail facultative"
                    ),
                    "autocomplete": "off",
                }
            ),
            "address": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": (
                        "Adresse du fournisseur"
                    ),
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": (
                        "form-check-input"
                    ),
                }
            ),
        }

    def clean_name(self):
        name = (
            self.cleaned_data
            .get("name", "")
            .strip()
        )

        if not name:
            raise ValidationError(
                "Saisissez le nom du fournisseur."
            )

        duplicate_supplier = (
            Supplier.objects
            .filter(name__iexact=name)
            .exclude(pk=self.instance.pk)
            .exists()
        )

        if duplicate_supplier:
            raise ValidationError(
                "Un fournisseur portant ce nom "
                "existe déjà."
            )

        return name

    def clean_phone(self):
        phone = (
            self.cleaned_data
            .get("phone", "")
            .strip()
        )

        if not phone:
            return ""

        duplicate_phone = (
            Supplier.objects
            .filter(phone=phone)
            .exclude(pk=self.instance.pk)
            .exists()
        )

        if duplicate_phone:
            raise ValidationError(
                "Ce numéro de téléphone est déjà "
                "utilisé par un fournisseur."
            )

        return phone


class PurchaseForm(forms.ModelForm):
    initial_payment = forms.DecimalField(
        label="Montant payé maintenant",
        required=False,
        min_value=ZERO,
        decimal_places=2,
        max_digits=18,
        initial=ZERO,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "min": "0",
                "step": "0.01",
                "placeholder": (
                    "Montant payé maintenant"
                ),
            }
        ),
        help_text=(
            "Laissez zéro si l'achat est "
            "entièrement à crédit."
        ),
    )

    purchase_date = forms.DateTimeField(
        label="Date de l'achat",
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
        model = Purchase

        fields = [
            "supplier",
            "supplier_reference",
            "purchase_date",
            "payment_method",
            "discount",
            "notes",
        ]

        widgets = {
            "supplier": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "supplier_reference": (
                forms.TextInput(
                    attrs={
                        "class": "form-control",
                        "placeholder": (
                            "N° facture ou référence "
                            "du fournisseur"
                        ),
                    }
                )
            ),
            "payment_method": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "discount": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "step": "0.01",
                    "placeholder": (
                        "Remise globale"
                    ),
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": (
                        "Note facultative..."
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

        self.fields[
            "supplier"
        ].queryset = (
            Supplier.objects
            .filter(is_active=True)
            .order_by("name")
        )

        self.fields[
            "supplier"
        ].empty_label = (
            "Sélectionner un fournisseur"
        )

        if (
            self.instance.pk
            and self.instance.supplier_id
        ):
            self.fields[
                "supplier"
            ].queryset = (
                Supplier.objects
                .filter(
                    pk=self.instance.supplier_id
                )
                | Supplier.objects.filter(
                    is_active=True
                )
            )

        if not self.instance.pk:
            self.fields[
                "purchase_date"
            ].initial = (
                timezone.localtime()
                .strftime("%Y-%m-%dT%H:%M")
            )

            self.fields[
                "discount"
            ].initial = ZERO

    def clean_discount(self):
        discount = (
            self.cleaned_data
            .get("discount")
            or ZERO
        )

        if discount < ZERO:
            raise ValidationError(
                "La remise ne peut pas être "
                "négative."
            )

        return discount

    def clean_initial_payment(self):
        initial_payment = (
            self.cleaned_data
            .get("initial_payment")
            or ZERO
        )

        if initial_payment < ZERO:
            raise ValidationError(
                "Le montant payé ne peut pas "
                "être négatif."
            )

        return initial_payment

    def clean(self):
        cleaned_data = super().clean()

        payment_method = (
            cleaned_data.get(
                "payment_method"
            )
        )

        initial_payment = (
            cleaned_data.get(
                "initial_payment"
            )
            or ZERO
        )

        if (
            payment_method
            == Purchase.PaymentMethod.CREDIT
            and initial_payment > ZERO
        ):
            self.add_error(
                "payment_method",
                (
                    "Pour un paiement partiel, "
                    "sélectionnez le mode réellement "
                    "utilisé : espèce, Wave, "
                    "Orange Money ou virement."
                ),
            )

        return cleaned_data


class PurchaseItemForm(forms.ModelForm):
    class Meta:
        model = PurchaseItem

        fields = [
            "product",
            "quantity",
            "unit_cost",
            "discount",
        ]

        widgets = {
            "product": forms.Select(
                attrs={
                    "class": (
                        "form-select "
                        "purchase-product-select"
                    ),
                }
            ),
            "quantity": forms.NumberInput(
                attrs={
                    "class": (
                        "form-control "
                        "purchase-quantity"
                    ),
                    "min": "0.01",
                    "step": "0.01",
                    "placeholder": "Quantité",
                }
            ),
            "unit_cost": forms.NumberInput(
                attrs={
                    "class": (
                        "form-control "
                        "purchase-unit-cost"
                    ),
                    "min": "0",
                    "step": "0.01",
                    "placeholder": (
                        "Prix d'achat unitaire"
                    ),
                }
            ),
            "discount": forms.NumberInput(
                attrs={
                    "class": (
                        "form-control "
                        "purchase-line-discount"
                    ),
                    "min": "0",
                    "step": "0.01",
                    "placeholder": (
                        "Remise ligne"
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

        self.fields[
            "product"
        ].queryset = (
            Product.objects
            .filter(is_active=True)
            .select_related(
                "category",
                "unit",
            )
            .order_by("name")
        )

        self.fields[
            "product"
        ].empty_label = (
            "Sélectionner un produit"
        )

        if (
            self.instance.pk
            and self.instance.product_id
        ):
            self.fields[
                "product"
            ].queryset = (
                Product.objects
                .filter(
                    pk=self.instance.product_id
                )
                | Product.objects.filter(
                    is_active=True
                )
            )

        if not self.instance.pk:
            self.fields[
                "discount"
            ].initial = ZERO

    def clean_quantity(self):
        quantity = (
            self.cleaned_data
            .get("quantity")
        )

        if quantity is None:
            raise ValidationError(
                "Saisissez la quantité."
            )

        if quantity <= ZERO:
            raise ValidationError(
                "La quantité doit être "
                "supérieure à zéro."
            )

        return quantity

    def clean_unit_cost(self):
        unit_cost = (
            self.cleaned_data
            .get("unit_cost")
        )

        if unit_cost is None:
            raise ValidationError(
                "Saisissez le prix d'achat."
            )

        if unit_cost < ZERO:
            raise ValidationError(
                "Le prix d'achat ne peut pas "
                "être négatif."
            )

        return unit_cost

    def clean_discount(self):
        discount = (
            self.cleaned_data
            .get("discount")
            or ZERO
        )

        if discount < ZERO:
            raise ValidationError(
                "La remise ne peut pas être "
                "négative."
            )

        return discount

    def clean(self):
        cleaned_data = super().clean()

        quantity = (
            cleaned_data.get("quantity")
            or ZERO
        )

        unit_cost = (
            cleaned_data.get("unit_cost")
            or ZERO
        )

        discount = (
            cleaned_data.get("discount")
            or ZERO
        )

        gross_total = (
            quantity * unit_cost
        )

        if discount > gross_total:
            self.add_error(
                "discount",
                (
                    "La remise ne peut pas "
                    "dépasser le montant de "
                    "la ligne."
                ),
            )

        return cleaned_data


class BasePurchaseItemFormSet(
    BaseInlineFormSet
):
    def clean(self):
        super().clean()

        if any(self.errors):
            return

        active_lines = 0
        selected_products = set()

        for form in self.forms:
            cleaned_data = getattr(
                form,
                "cleaned_data",
                None,
            )

            if not cleaned_data:
                continue

            if cleaned_data.get(
                "DELETE",
                False,
            ):
                continue

            product = cleaned_data.get(
                "product"
            )

            quantity = cleaned_data.get(
                "quantity"
            )

            unit_cost = cleaned_data.get(
                "unit_cost"
            )

            if (
                product is None
                and quantity is None
                and unit_cost is None
            ):
                continue

            active_lines += 1

            if product is None:
                raise ValidationError(
                    "Chaque ligne doit avoir "
                    "un produit."
                )

            if product.pk in selected_products:
                raise ValidationError(
                    (
                        "Le produit "
                        f"« {product.name} » est "
                        "présent plusieurs fois. "
                        "Regroupez sa quantité dans "
                        "une seule ligne."
                    )
                )

            selected_products.add(
                product.pk
            )

        if active_lines == 0:
            raise ValidationError(
                "Ajoutez au moins un produit "
                "à l'approvisionnement."
            )


PurchaseItemFormSet = (
    forms.inlineformset_factory(
        Purchase,
        PurchaseItem,
        form=PurchaseItemForm,
        formset=BasePurchaseItemFormSet,
        extra=1,
        can_delete=True,
        min_num=1,
        validate_min=True,
    )
)


class PurchasePaymentForm(
    forms.ModelForm
):
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
        model = PurchasePayment

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
                    "placeholder": (
                        "Montant payé"
                    ),
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
                    "placeholder": (
                        "Note facultative..."
                    ),
                }
            ),
        }

    def __init__(
        self,
        *args,
        purchase=None,
        **kwargs,
    ):
        self.purchase = purchase

        super().__init__(
            *args,
            **kwargs,
        )

        if self.purchase is not None:
            self.instance.purchase = (
                self.purchase
            )

            self.instance.supplier = (
                self.purchase.supplier
            )

        if not self.instance.pk:
            self.fields[
                "payment_date"
            ].initial = (
                timezone.localtime()
                .strftime("%Y-%m-%dT%H:%M")
            )

        if self.purchase is not None:
            remaining = (
                self.purchase
                .remaining_amount
                or ZERO
            )

            self.fields[
                "amount"
            ].widget.attrs[
                "max"
            ] = str(remaining)

            formatted_remaining = (
                f"{remaining:,.0f}"
                .replace(",", " ")
            )

            self.fields[
                "amount"
            ].help_text = (
                "Reste actuel : "
                f"{formatted_remaining} F CFA"
            )

            if (
                not self.is_bound
                and not self.instance.pk
            ):
                self.fields[
                    "amount"
                ].initial = remaining

    def clean_amount(self):
        amount = (
            self.cleaned_data
            .get("amount")
        )

        if amount is None:
            raise ValidationError(
                "Saisissez le montant "
                "du paiement."
            )

        if amount <= ZERO:
            raise ValidationError(
                "Le montant doit être "
                "supérieur à zéro."
            )

        if self.purchase is None:
            raise ValidationError(
                "L'achat lié au paiement "
                "est introuvable."
            )

        if self.purchase.is_cancelled:
            raise ValidationError(
                "Cet achat est annulé. "
                "Aucun paiement n'est autorisé."
            )

        remaining = (
            self.purchase.remaining_amount
            or ZERO
        )

        if amount > remaining:
            formatted_remaining = (
                f"{remaining:,.0f}"
                .replace(",", " ")
            )

            raise ValidationError(
                "Le paiement dépasse le reste "
                "à payer. Maximum autorisé : "
                f"{formatted_remaining} F CFA."
            )

        return amount