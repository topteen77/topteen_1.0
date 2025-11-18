from django import template

register = template.Library()

@register.simple_tag
def my_url(value, field_name, urlencode=None):
    url = "?{}={}".format(field_name, value)
    if urlencode:
        querystring = urlencode.split('&')
        filtered_querystring = filter(lambda x: x.split('=')[0] != field_name, querystring)
        filtered_querystring = '&'.join(filtered_querystring)
        if filtered_querystring:
            url += "&{}".format(filtered_querystring)
    print("Generated URL:", url)
    return url