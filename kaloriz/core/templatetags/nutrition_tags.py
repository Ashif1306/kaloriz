from decimal import Decimal, InvalidOperation

from django import template


register = template.Library()


@register.filter
def nutrition_percent(value, max_value=100):
    """Calculate a percentage for nutrition visualization.

    Returns an integer between 0 and 100 so it can be used as a CSS width value.
    """
    if value in (None, ""):
        return 0

    try:
        value_decimal = Decimal(value)
        max_decimal = Decimal(max_value)
    except (InvalidOperation, TypeError, ValueError):
        return 0

    if max_decimal <= 0:
        return 0

    try:
        percent = (value_decimal / max_decimal) * 100
    except (InvalidOperation, ZeroDivisionError):
        return 0

    if percent < 0:
        return 0
    if percent > 100:
        return 100

    return int(percent.quantize(Decimal("1")))
