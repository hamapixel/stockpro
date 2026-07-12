from django import forms

from .models import Client


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            "full_name",
            "phone",
            "address",
            "email",
        ]

        widgets = {
            "full_name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ex: Boubacar Traoré",
            }),
            "phone": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ex: 76 00 00 00",
            }),
            "address": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ex: Bamako, Mali",
            }),
            "email": forms.EmailInput(attrs={
                "class": "form-control",
                "placeholder": "Ex: client@email.com",
            }),
        }