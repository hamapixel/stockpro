from django import template

from accounts.decorators import is_admin_user, is_seller_user

register = template.Library()


@register.filter
def is_admin_role(user):
    return is_admin_user(user)


@register.filter
def is_seller_role(user):
    return is_seller_user(user)