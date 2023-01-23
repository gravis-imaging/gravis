from django import template

register = template.Library()

@register.simple_tag
def url_case_id(value):
    return int(value.split("/")[2])

@register.simple_tag
def case_info(cases, id):
    case = filter(lambda c: c.id == id, cases)
    return list(case)[0]