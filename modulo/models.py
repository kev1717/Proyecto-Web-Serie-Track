from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Genero(models.Model):
    nombre = models.CharField('nombre', max_length=50, unique=True)

    class Meta:
        verbose_name = 'género'
        verbose_name_plural = 'géneros'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Titulo(models.Model):
    class Tipo(models.TextChoices):
        SERIE = 'serie', 'Serie'
        ANIME = 'anime', 'Anime'

    class ColorPortada(models.TextChoices):
        # El valor vacío usa el color del género (comportamiento original)
        GENERO = '', 'Según el género'
        ROJO = 'rojo', 'Rojo'
        NARANJA = 'naranja', 'Naranja'
        AMARILLO = 'amarillo', 'Amarillo'
        VERDE = 'verde', 'Verde'
        TURQUESA = 'turquesa', 'Turquesa'
        AZUL = 'azul', 'Azul'
        MORADO = 'morado', 'Morado'
        GRIS = 'gris', 'Gris'

    nombre = models.CharField('nombre', max_length=150)
    tipo = models.CharField('tipo', max_length=10, choices=Tipo.choices)
    genero = models.ForeignKey(
        Genero,
        on_delete=models.PROTECT,
        related_name='titulos',
        verbose_name='género',
    )
    sinopsis = models.TextField('sinopsis', blank=True)
    total_episodios = models.PositiveIntegerField(
        'total de episodios',
        validators=[MinValueValidator(1)],
    )
    anio = models.PositiveSmallIntegerField(
        'año',
        validators=[MinValueValidator(1900), MaxValueValidator(2100)],
    )
    portada = models.ImageField('portada', upload_to='portadas/', blank=True)
    color_portada = models.CharField(
        'color de la portada',
        max_length=10,
        choices=ColorPortada.choices,
        blank=True,
        default=ColorPortada.GENERO,
        help_text='Color con el que se genera la portada. No se aplica si subes una imagen.',
    )
    # True si la portada actual la generó el sitio (se puede regenerar); False si la subió
    # el admin (nunca se reemplaza). No se muestra en formularios.
    portada_generada = models.BooleanField(default=False, editable=False)

    class Meta:
        verbose_name = 'título'
        verbose_name_plural = 'títulos'
        ordering = ['nombre']

    def __str__(self):
        return f'{self.nombre} ({self.anio})'

    def get_absolute_url(self):
        return reverse('titulo_detalle', args=[self.pk])


class Seguimiento(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        VIENDO = 'viendo', 'Viendo'
        PAUSADA = 'pausada', 'En pausa'
        COMPLETADA = 'completada', 'Completada'
        ABANDONADA = 'abandonada', 'Abandonada'

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='seguimientos',
        verbose_name='usuario',
    )
    titulo = models.ForeignKey(
        Titulo,
        on_delete=models.CASCADE,
        related_name='seguimientos',
        verbose_name='título',
    )
    episodio_actual = models.PositiveIntegerField('episodio actual', default=0)
    estado = models.CharField(
        'estado',
        max_length=12,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
    )
    calificacion = models.PositiveSmallIntegerField(
        'calificación',
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    plataforma = models.CharField('plataforma', max_length=50, blank=True)
    favorita = models.BooleanField('favorita', default=False)
    fecha_inicio = models.DateField('fecha de inicio', default=timezone.localdate)

    class Meta:
        verbose_name = 'seguimiento'
        verbose_name_plural = 'seguimientos'
        constraints = [
            models.UniqueConstraint(
                fields=['usuario', 'titulo'],
                name='seguimiento_unico_por_usuario_titulo',
                violation_error_message='Este título ya está en la lista del usuario.',
            ),
        ]

    def __str__(self):
        return f'{self.usuario} - {self.titulo.nombre}'

    @property
    def porcentaje(self):
        """Porcentaje de episodios vistos, para la barra de progreso."""
        return round(self.episodio_actual * 100 / self.titulo.total_episodios)

    @property
    def terminado(self):
        return self.episodio_actual >= self.titulo.total_episodios

    def clean(self):
        super().clean()
        if self.titulo_id and self.episodio_actual > self.titulo.total_episodios:
            raise ValidationError({
                'episodio_actual': (
                    f'No puede superar el total de episodios '
                    f'({self.titulo.total_episodios}).'
                ),
            })


class Comentario(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='comentarios',
        verbose_name='usuario',
    )
    titulo = models.ForeignKey(
        Titulo,
        on_delete=models.CASCADE,
        related_name='comentarios',
        verbose_name='título',
    )
    texto = models.TextField('texto', max_length=1000)
    fecha = models.DateTimeField('fecha', auto_now_add=True)
    visible = models.BooleanField('visible', default=True)

    class Meta:
        verbose_name = 'comentario'
        verbose_name_plural = 'comentarios'
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.usuario} en {self.titulo.nombre}'
