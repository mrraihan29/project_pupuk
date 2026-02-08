from django import template
from decimal import Decimal

register = template.Library()


@register.filter
def rupiah(value):
    """
    Format angka ke format Rupiah tanpa desimal.
    Contoh: 55000000.00 → 55.000.000
    """
    if value is None:
        return '0'
    try:
        val = int(Decimal(str(value)).quantize(Decimal('1')))
    except Exception:
        return str(value)
    formatted = f'{val:,}'.replace(',', '.')
    return formatted
