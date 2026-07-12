from decimal import Decimal, InvalidOperation

from django import template


register = template.Library()


@register.filter
def fcfa(value):
    try:
        amount = Decimal(value or 0)
    except (InvalidOperation, TypeError, ValueError):
        amount = Decimal("0")

    amount = int(amount)
    formatted = f"{amount:,}".replace(",", " ")
    return f"{formatted} F CFA"