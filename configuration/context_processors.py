from django.db.utils import OperationalError, ProgrammingError

from .models import CompanySettings


def company_settings(request):
    try:
        settings_obj = CompanySettings.get_solo()
    except (OperationalError, ProgrammingError):
        settings_obj = None

    return {
        "company_settings": settings_obj,
    }