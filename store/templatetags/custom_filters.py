from django import template

register = template.Library()

@register.filter(name='multiply_by_100')
def multiply_by_100(value):
    return value * 100