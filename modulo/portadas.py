"""Genera portadas originales (sin derechos de autor de terceros) para los títulos.

Cada portada es una imagen de 400x600 px (proporción de póster 2:3) con un
degradado del color elegido por el admin (o del género, si no eligió), el nombre
del título, el tipo y el año.
"""
import colorsys
import zlib
from io import BytesIO

from django.core.files.base import ContentFile
from django.utils.text import slugify
from PIL import Image, ImageDraw, ImageFont

ANCHO, ALTO = 400, 600
MARGEN = 32

# Color principal de cada género; los que no estén aquí usan COLOR_POR_DEFECTO
COLORES_GENERO = {
    'Acción': (200, 55, 45),
    'Comedia': (230, 150, 20),
    'Drama': (60, 70, 140),
    'Ciencia ficción': (20, 130, 150),
    'Suspenso': (90, 40, 110),
    'Deportes': (40, 140, 70),
    'Fantasía': (170, 60, 140),
}
COLOR_POR_DEFECTO = (80, 90, 100)

# Colores que el admin puede elegir (claves = valores de Titulo.ColorPortada).
# A diferencia del color del género, estos se usan tal cual, sin variar el tono.
COLORES_PORTADA = {
    'rojo': (200, 55, 45),
    'naranja': (225, 110, 25),
    'amarillo': (215, 165, 20),
    'verde': (40, 140, 70),
    'turquesa': (20, 130, 150),
    'azul': (40, 90, 180),
    'morado': (110, 50, 150),
    'gris': (80, 90, 100),
}

# Fuentes en orden de preferencia (Windows, Linux); si ninguna existe se usa la de Pillow
FUENTES_NEGRITA = ['arialbd.ttf', 'DejaVuSans-Bold.ttf']
FUENTES_NORMAL = ['arial.ttf', 'DejaVuSans.ttf']


def _fuente(candidatas, tamano):
    for nombre in candidatas:
        try:
            return ImageFont.truetype(nombre, tamano)
        except OSError:
            continue
    return ImageFont.load_default(size=tamano)


def _variar_tono(color, semilla):
    """Mueve un poco el tono del color para que dos títulos del mismo género no sean idénticos."""
    h, l, s = colorsys.rgb_to_hls(*(c / 255 for c in color))
    h = (h + ((semilla % 7) - 3) * 0.015) % 1
    l = min(max(l + ((semilla // 7 % 5) - 2) * 0.03, 0.15), 0.7)
    return tuple(round(c * 255) for c in colorsys.hls_to_rgb(h, l, s))


def _oscurecer(color, factor):
    return tuple(int(c * factor) for c in color)


def _partir_en_lineas(dibujo, texto, fuente, ancho_maximo):
    """Reparte las palabras en líneas que quepan en ancho_maximo."""
    lineas, actual = [], ''
    for palabra in texto.split():
        prueba = f'{actual} {palabra}'.strip()
        if dibujo.textlength(prueba, font=fuente) <= ancho_maximo:
            actual = prueba
        else:
            if actual:
                lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas


def _titulo_ajustado(dibujo, texto, ancho_maximo):
    """Busca el tamaño de letra más grande con el que el nombre quepa en máximo 4 líneas."""
    for tamano in range(48, 21, -2):
        fuente = _fuente(FUENTES_NEGRITA, tamano)
        lineas = _partir_en_lineas(dibujo, texto, fuente, ancho_maximo)
        cabe = all(dibujo.textlength(linea, font=fuente) <= ancho_maximo for linea in lineas)
        if cabe and len(lineas) <= 4:
            return fuente, lineas, tamano
    return fuente, lineas, tamano


def color_de_portada(titulo, semilla):
    """El color elegido por el admin o, si no eligió, el del género con el tono un poco variado."""
    if titulo.color_portada in COLORES_PORTADA:
        return COLORES_PORTADA[titulo.color_portada]
    return _variar_tono(COLORES_GENERO.get(titulo.genero.nombre, COLOR_POR_DEFECTO), semilla)


def guardar_portada_generada(titulo):
    """Genera la portada del título, la guarda y la marca como generada.

    Si el título ya tenía una portada generada, se borra el archivo viejo para no dejar
    imágenes sueltas en media/. Quien llama debe asegurarse de no usarla sobre una
    portada subida por el admin.
    """
    archivo = generar_portada(titulo)
    if titulo.portada and titulo.portada_generada:
        titulo.portada.delete(save=False)
    titulo.portada_generada = True
    titulo.portada.save(archivo.name, archivo)  # también guarda el título


def generar_portada(titulo):
    """Devuelve un ContentFile PNG listo para asignar a titulo.portada."""
    # Semilla fija a partir del nombre: el mismo título siempre da la misma portada
    semilla = zlib.crc32(titulo.nombre.encode('utf-8'))
    color = color_de_portada(titulo, semilla)
    arriba, abajo = color, _oscurecer(color, 0.35)

    imagen = Image.new('RGB', (ANCHO, ALTO))
    dibujo = ImageDraw.Draw(imagen)

    # Fondo: degradado vertical del color del género hacia uno más oscuro
    for y in range(ALTO):
        t = y / (ALTO - 1)
        fila = tuple(round(a + (b - a) * t) for a, b in zip(arriba, abajo))
        dibujo.line([(0, y), (ANCHO, y)], fill=fila)

    # Decoración: círculos semitransparentes cuya posición y tamaño dependen de la semilla
    capa = Image.new('RGBA', (ANCHO, ALTO), (0, 0, 0, 0))
    deco = ImageDraw.Draw(capa)
    r1 = 150 + semilla % 90
    x1, y1 = ANCHO - 40 - (semilla >> 4) % 120, 40 + (semilla >> 8) % 160
    deco.ellipse([x1 - r1, y1 - r1, x1 + r1, y1 + r1], fill=(255, 255, 255, 28))
    r2 = 110 + (semilla >> 12) % 80
    x2, y2 = 10 + (semilla >> 16) % 120, ALTO - 220 + (semilla >> 20) % 80
    deco.ellipse([x2 - r2, y2 - r2, x2 + r2, y2 + r2], fill=(255, 255, 255, 18))
    imagen = Image.alpha_composite(imagen.convert('RGBA'), capa).convert('RGB')
    dibujo = ImageDraw.Draw(imagen)

    # Etiqueta del tipo (SERIE / ANIME) arriba a la izquierda
    fuente_etiqueta = _fuente(FUENTES_NEGRITA, 18)
    etiqueta = titulo.get_tipo_display().upper()
    ancho_etiqueta = dibujo.textlength(etiqueta, font=fuente_etiqueta)
    dibujo.rounded_rectangle(
        [MARGEN, MARGEN, MARGEN + ancho_etiqueta + 24, MARGEN + 34],
        radius=17, fill=(255, 255, 255),
    )
    dibujo.text((MARGEN + 12, MARGEN + 17), etiqueta, font=fuente_etiqueta, fill=abajo, anchor='lm')

    # Nombre del título, abajo y alineado a la izquierda
    fuente_titulo, lineas, tamano = _titulo_ajustado(dibujo, titulo.nombre, ANCHO - 2 * MARGEN)
    alto_linea = int(tamano * 1.15)
    fuente_pie = _fuente(FUENTES_NORMAL, 20)
    y = ALTO - MARGEN - 40 - alto_linea * len(lineas)
    dibujo.line([(MARGEN, y - 18), (MARGEN + 60, y - 18)], fill=(255, 255, 255), width=4)
    for linea in lineas:
        dibujo.text((MARGEN, y), linea, font=fuente_titulo, fill=(255, 255, 255))
        y += alto_linea

    # Pie: año y género
    pie = f'{titulo.anio}  ·  {titulo.genero.nombre}'
    dibujo.text((MARGEN, ALTO - MARGEN), pie, font=fuente_pie, fill=(235, 235, 235), anchor='ls')

    salida = BytesIO()
    imagen.save(salida, format='PNG', optimize=True)
    return ContentFile(salida.getvalue(), name=f'{slugify(titulo.nombre) or "titulo"}.png')
