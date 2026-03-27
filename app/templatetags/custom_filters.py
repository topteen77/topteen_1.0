from django import template

register = template.Library()

@register.filter
def get_key(dictionary, key):
    return dictionary.get(key, None)

@register.filter(name='split')
def split(value, delimiter):
    """Split a string by the given delimiter."""
    return value.split(delimiter)


@register.simple_tag
def get_domain_cleanup_choices():
    """(value, label) pairs for user_analytics domain-scoped delete dropdowns (admin)."""
    from user_analytics.domain_cleanup import DOMAIN_CLEANUP_CHOICES
    return DOMAIN_CLEANUP_CHOICES