from django import template

register = template.Library()

@register.filter
def get_key(dictionary, key):
    return dictionary.get(key, None)

@register.filter(name='split')
def split(value, delimiter):
    """Split a string by the given delimiter."""
    return value.split(delimiter)