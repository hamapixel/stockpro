from django.contrib import messages
from django.shortcuts import redirect, render

from accounts.decorators import admin_required

from .forms import CompanySettingsForm
from .models import CompanySettings


@admin_required
def company_settings_update(request):
    settings_obj = CompanySettings.get_solo()

    if request.method == "POST":
        form = CompanySettingsForm(
            request.POST,
            request.FILES,
            instance=settings_obj,
        )

        if form.is_valid():
            settings_obj = form.save(commit=False)

            if form.cleaned_data.get("remove_logo"):
                if settings_obj.logo:
                    settings_obj.logo.delete(save=False)
                settings_obj.logo = None

            if form.cleaned_data.get("remove_invoice_header"):
                if settings_obj.invoice_header:
                    settings_obj.invoice_header.delete(save=False)
                settings_obj.invoice_header = None

            settings_obj.save()

            messages.success(
                request,
                "Les paramètres de la société ont été enregistrés.",
            )

            return redirect("company_settings")

        messages.error(
            request,
            "Corrigez les erreurs du formulaire.",
        )
    else:
        form = CompanySettingsForm(instance=settings_obj)

    return render(
        request,
        "configuration/company_settings_form.html",
        {
            "form": form,
            "company_settings": settings_obj,
        },
    )


@admin_required
def invoice_header_preview(request):
    settings_obj = CompanySettings.get_solo()

    return render(
        request,
        "configuration/invoice_header_preview.html",
        {
            "company_settings": settings_obj,
        },
    )