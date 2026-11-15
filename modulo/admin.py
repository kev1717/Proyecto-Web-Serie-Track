from django.contrib import admin, messages
from django.db.models import Avg, Count
from django.template.defaultfilters import truncatechars
from django.utils.html import format_html, format_html_join

from .models import Comentario, Genero, Seguimiento, Titulo
from .portadas import COLORES_PORTADA, guardar_portada_generada

# Textos del encabezado del panel
admin.site.site_header = 'SerieTrack'
admin.site.site_title = 'SerieTrack · Administración'
admin.site.index_title = 'Panel de administración'


def _miniatura(titulo, clase='st-miniatura'):
    if titulo.portada:
        return format_html('<img src="{}" class="{}" alt="">', titulo.portada.url, clase)
    return format_html('<span class="{} st-sin-portada">Sin portada</span>', clase)


@admin.register(Genero)
class GeneroAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'cantidad_titulos']
    search_fields = ['nombre']

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_cantidad=Count('titulos'))

    @admin.display(description='títulos', ordering='_cantidad')
    def cantidad_titulos(self, obj):
        return obj._cantidad


class ComentarioInline(admin.TabularInline):
    """Permite moderar los comentarios desde la ficha de cada título."""
    model = Comentario
    fields = ['usuario', 'texto', 'fecha', 'visible']
    readonly_fields = ['usuario', 'texto', 'fecha']
    extra = 0
    can_delete = True
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False  # los comentarios los escriben los usuarios desde el sitio


@admin.register(Titulo)
class TituloAdmin(admin.ModelAdmin):
    list_display = ['portada_lista', 'nombre', 'tipo_etiqueta', 'genero', 'anio',
                    'total_episodios', 'promedio', 'seguidores']
    list_display_links = ['portada_lista', 'nombre']
    list_filter = ['tipo', 'genero']
    search_fields = ['nombre']
    list_per_page = 20
    readonly_fields = ['portada_vista', 'paleta']
    actions = ['generar_portadas']
    inlines = [ComentarioInline]
    fieldsets = [
        (None, {'fields': ['nombre', 'tipo', 'genero', 'anio', 'total_episodios']}),
        ('Sinopsis', {'fields': ['sinopsis']}),
        ('Portada', {
            'fields': ['portada_vista', 'color_portada', 'paleta', 'portada'],
            'description': 'Elige un color y, al guardar, la portada se genera sola. Si cambias '
                           'el color, el nombre, el tipo, el género o el año, se vuelve a generar. '
                           'Si subes una imagen propia, se usa esa y nunca se reemplaza.',
        }),
    ]

    # Datos que aparecen dibujados en la portada: si cambian, la portada generada se rehace
    CAMPOS_DE_LA_PORTADA = {'nombre', 'tipo', 'genero', 'anio', 'color_portada'}

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('genero').annotate(
            _promedio=Avg('seguimientos__calificacion'),
            _seguidores=Count('seguimientos', distinct=True),
        )

    @admin.display(description='portada')
    def portada_lista(self, obj):
        return _miniatura(obj)

    @admin.display(description='vista previa')
    def portada_vista(self, obj):
        return _miniatura(obj, 'st-portada-grande')

    @admin.display(description='colores disponibles')
    def paleta(self, obj):
        """Muestra de cada color de la lista, con el elegido resaltado."""
        actual = obj.color_portada if obj else ''
        muestras = format_html_join(
            '', '<span class="st-color{}" title="{}"><span style="background: rgb{}"></span>{}</span>',
            (
                (' st-color-actual' if valor == actual else '', etiqueta, COLORES_PORTADA[valor], etiqueta)
                for valor, etiqueta in Titulo.ColorPortada.choices if valor
            ),
        )
        return format_html('<div class="st-paleta">{}</div>', muestras)

    def save_model(self, request, obj, form, change):
        if 'portada' in form.changed_data:
            # El admin subió (o quitó) una imagen: deja de ser una portada generada
            obj.portada_generada = False
        super().save_model(request, obj, form, change)

        cambio_la_portada = self.CAMPOS_DE_LA_PORTADA & set(form.changed_data)
        if not obj.portada or (obj.portada_generada and cambio_la_portada):
            guardar_portada_generada(obj)

    @admin.display(description='tipo', ordering='tipo')
    def tipo_etiqueta(self, obj):
        return format_html('<span class="st-badge st-{}">{}</span>', obj.tipo, obj.get_tipo_display())

    @admin.display(description='calificación', ordering='_promedio')
    def promedio(self, obj):
        if obj._promedio is None:
            return '—'
        return format_html('★ {}', f'{obj._promedio:.1f}'.replace('.', ','))

    @admin.display(description='seguidores', ordering='_seguidores')
    def seguidores(self, obj):
        return obj._seguidores

    @admin.action(description='Generar portada (solo a los que no tienen)')
    def generar_portadas(self, request, queryset):
        generadas = 0
        for titulo in queryset.select_related('genero'):
            if not titulo.portada:
                guardar_portada_generada(titulo)
                generadas += 1
        omitidas = queryset.count() - generadas
        mensaje = f'Se generaron {generadas} portada(s).'
        if omitidas:
            mensaje += f' Se omitieron {omitidas} porque ya tenían una.'
        self.message_user(request, mensaje, messages.SUCCESS if generadas else messages.WARNING)


@admin.register(Seguimiento)
class SeguimientoAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'titulo', 'estado_etiqueta', 'progreso', 'calificacion',
                    'favorita', 'plataforma']
    list_filter = ['estado', 'favorita', 'titulo__tipo']
    search_fields = ['usuario__username', 'titulo__nombre']
    autocomplete_fields = ['usuario', 'titulo']
    list_select_related = ['usuario', 'titulo']
    date_hierarchy = 'fecha_inicio'
    list_per_page = 25

    @admin.display(description='estado', ordering='estado')
    def estado_etiqueta(self, obj):
        return format_html('<span class="st-badge st-{}">{}</span>', obj.estado, obj.get_estado_display())

    @admin.display(description='progreso', ordering='episodio_actual')
    def progreso(self, obj):
        return format_html(
            '<div class="st-progreso" title="{}%"><div style="width: {}%"></div></div>'
            '<span class="st-progreso-texto">{} / {}</span>',
            obj.porcentaje, obj.porcentaje, obj.episodio_actual, obj.titulo.total_episodios,
        )


@admin.register(Comentario)
class ComentarioAdmin(admin.ModelAdmin):
    list_display = ['resumen', 'usuario', 'titulo', 'fecha', 'visible']
    list_display_links = ['resumen']
    list_filter = ['visible', 'titulo__tipo']
    list_editable = ['visible']
    list_select_related = ['usuario', 'titulo']
    search_fields = ['texto', 'usuario__username', 'titulo__nombre']
    date_hierarchy = 'fecha'
    readonly_fields = ['usuario', 'titulo', 'fecha']
    fields = ['usuario', 'titulo', 'fecha', 'texto', 'visible']
    actions = ['ocultar', 'mostrar']
    list_per_page = 25

    def has_add_permission(self, request):
        return False  # los comentarios se escriben desde el sitio, el admin solo modera

    @admin.display(description='comentario')
    def resumen(self, obj):
        return truncatechars(obj.texto, 70)

    @admin.action(description='Ocultar comentarios seleccionados')
    def ocultar(self, request, queryset):
        cantidad = queryset.update(visible=False)
        self.message_user(request, f'Se ocultaron {cantidad} comentario(s).', messages.SUCCESS)

    @admin.action(description='Mostrar comentarios seleccionados')
    def mostrar(self, request, queryset):
        cantidad = queryset.update(visible=True)
        self.message_user(request, f'Se mostraron {cantidad} comentario(s).', messages.SUCCESS)
