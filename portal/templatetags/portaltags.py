from django import template

register = template.Library()

@register.simple_tag
def url_case_id(value, id):
    return int(value.split("/")[2])