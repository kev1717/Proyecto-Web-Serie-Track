"""Cifras para el resumen de la portada del panel de administración."""
from django import template
from django.contrib.auth.models import User

from modulo.models import Comentario, Seguimiento, Titulo

register = template.Library()


@register.simple_tag
def resumen_serietrack():
    return {
        'series': Titulo.objects.filter(tipo=Titulo.Tipo.SERIE).count(),
        'animes': Titulo.objects.filter(tipo=Titulo.Tipo.ANIME).count(),
        'usuarios': User.objects.filter(is_staff=False).count(),
        'seguimientos': Seguimiento.objects.count(),
        'comentarios': Comentario.objects.count(),
        'ocultos': Comentario.objects.filter(visible=False).count(),
        'sin_portada': Titulo.objects.filter(portada='').count(),
    }
