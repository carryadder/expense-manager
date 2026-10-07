from django import template
from django.utils.safestring import mark_safe

from expenses.icons import ICONS

register = template.Library()


@register.simple_tag
def icon(name, size=24, cls=''):
    """Render an inline SVG icon by name. Colour follows CSS `currentColor`."""
    inner = ICONS.get(name) or ICONS['wallet']
    classes = ('icon ' + cls).strip()
    return mark_safe(
        f'<svg class="{classes}" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true">{inner}</svg>'
    )


@register.filter
def money(amount, app_settings=None):
    """Format a Decimal/number with the user's currency symbol and 2 decimals."""
    symbol = getattr(app_settings, 'currency_symbol', '$')
    try:
        value = float(amount)
    except (TypeError, ValueError):
        value = 0.0
    return mark_safe(f'{symbol}{value:,.2f}')


@register.filter
def userdate(dt, app_settings=None):
    """Format a datetime per the user's chosen date format."""
    if not dt:
        return ''
    fmt = getattr(app_settings, 'date_format', 'relative')
    if fmt == 'dmy':
        return dt.strftime('%d/%m/%Y')
    if fmt == 'mdy':
        return dt.strftime('%m/%d/%Y')
    if fmt == 'iso':
        return dt.strftime('%Y-%m-%d')
    # relative
    from django.utils import timezone
    now = timezone.now()
    delta = now - dt
    secs = delta.total_seconds()
    if secs < 60:
        return 'just now'
    if secs < 3600:
        m = int(secs // 60)
        return f'{m} min{"s" if m != 1 else ""} ago'
    if secs < 86400:
        h = int(secs // 3600)
        return f'{h} hour{"s" if h != 1 else ""} ago'
    d = int(secs // 86400)
    if d == 1:
        return 'yesterday'
    if d < 30:
        return f'{d} days ago'
    return dt.strftime('%d %b %Y')


@register.filter
def get_item(mapping, key):
    """Look up a value in a dict by key, tolerating str/int key mismatch.
    Returns '' when absent so it's safe to use as an input value."""
    if not mapping:
        return ''
    return mapping.get(str(key)) or mapping.get(key) or ''
