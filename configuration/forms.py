from django import forms
from django.core.exceptions import ValidationError

from .models import CompanySettings


MAX_IMAGE_SIZE = 5 * 1024 * 1024


class CompanySettingsForm(forms.ModelForm):
    remove_logo = forms.BooleanField(
        label="Supprimer le logo actuel",
        required=False,
        widget=forms.CheckboxInput(
            attrs={
                "class": "form-check-input",
            }
        ),
    )

    remove_invoice_header = forms.BooleanField(
        label="Revenir à l’entête MSF par défaut",
        required=False,
        widget=forms.CheckboxInput(
            attrs={
                "class": "form-check-input",
            }
        ),
    )

    class Meta:
        model = CompanySettings
        fields = [
            "company_name",
            "legal_name",
            "activity",
            "slogan",
            "address",
            "phone",
            "phone_secondary",
            "email",
            "website",
            "rccm",
            "nif",
            "bank_details",
            "logo",
            "invoice_header_mode",
            "invoice_header",
            "invoice_header_height_mm",
            "show_logo_on_generated_header",
            "invoice_footer_text",
            "invoice_terms",
            "currency_label",
        ]
        widgets = {
            "company_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Nom commercial",
                }
            ),
            "legal_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Raison sociale complète",
                }
            ),
            "activity": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Activité principale",
                }
            ),
            "slogan": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Slogan facultatif",
                }
            ),
            "address": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Adresse complète",
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Téléphone principal",
                }
            ),
            "phone_secondary": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Téléphone secondaire",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "adresse@societe.com",
                }
            ),
            "website": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "www.societe.com",
                }
            ),
            "rccm": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Numéro RCCM",
                }
            ),
            "nif": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Numéro NIF",
                }
            ),
            "bank_details": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Banque ou autres informations",
                }
            ),
            "logo": forms.FileInput(
                attrs={
                    "class": "form-control",
                    "accept": "image/png,image/jpeg,image/webp",
                }
            ),
            "invoice_header_mode": forms.RadioSelect(),
            "invoice_header": forms.FileInput(
                attrs={
                    "class": "form-control",
                    "accept": "image/png,image/jpeg,image/webp",
                }
            ),
            "invoice_header_height_mm": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "20",
                    "max": "80",
                    "step": "1",
                }
            ),
            "show_logo_on_generated_header": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
            "invoice_footer_text": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                }
            ),
            "invoice_terms": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                }
            ),
            "currency_label": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "F CFA",
                }
            ),
        }

    def _validate_image(self, image, field_label):
        if image and image.size > MAX_IMAGE_SIZE:
            raise ValidationError(
                f"{field_label} ne doit pas dépasser 5 Mo."
            )
        return image

    def clean_logo(self):
        return self._validate_image(
            self.cleaned_data.get("logo"),
            "Le logo",
        )

    def clean_invoice_header(self):
        return self._validate_image(
            self.cleaned_data.get("invoice_header"),
            "L’image d’entête",
        )