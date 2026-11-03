from django import template

register = template.Library()

@register.filter
def star_range(rating):
    try:
        full = int(round(float(rating)))
    except (ValueError, TypeError):
        full = 0
    return range(full)

@register.filter
def empty_star_range(rating):
    try:
        full = int(round(float(rating)))
    except (ValueError, TypeError):
        full = 0
    return range(5 - full)