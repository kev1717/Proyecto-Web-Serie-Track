"""Carga datos de ejemplo para probar SerieTrack: géneros, series y animes (con portadas
generadas), usuarios, seguimientos y comentarios.

Uso:  py manage.py cargar_ejemplos

Se puede ejecutar varias veces: lo que ya existe no se duplica ni se modifica.
No toca a los usuarios administradores.
"""
from datetime import date

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from modulo.models import Comentario, Genero, Seguimiento, Titulo
from modulo.portadas import guardar_portada_generada

CLAVE_DEMO = 'serietrack123'

# (nombre, tipo, género, episodios, año, sinopsis)
TITULOS = [
    # --- Series ---
    ('Breaking Bad', 'serie', 'Drama', 62, 2008,
     'Un profesor de química con un diagnóstico terminal se asocia con un exalumno '
     'para fabricar y vender metanfetamina.'),
    ('The Office', 'serie', 'Comedia', 201, 2005,
     'El día a día de los empleados de una oficina de papel, contado como un falso documental.'),
    ('Stranger Things', 'serie', 'Ciencia ficción', 42, 2016,
     'En un pueblo de los años 80, un grupo de amigos busca a un niño desaparecido '
     'y se topa con experimentos secretos.'),
    ('Dark', 'serie', 'Ciencia ficción', 26, 2017,
     'La desaparición de dos niños destapa los secretos de cuatro familias '
     'unidas por viajes en el tiempo.'),
    ('Narcos', 'serie', 'Drama', 30, 2015,
     'La historia de los carteles de la droga en Colombia y de los agentes que los persiguieron.'),
    ('Brooklyn Nine-Nine', 'serie', 'Comedia', 153, 2013,
     'Las aventuras de un brillante pero inmaduro detective y sus compañeros de comisaría.'),
    ('House', 'serie', 'Drama', 177, 2004,
     'El Dr. Gregory House, un médico brillante, sarcástico y adicto a los analgésicos, '
     'resuelve los casos que nadie más puede diagnosticar.'),
    ('Peaky Blinders', 'serie', 'Drama', 36, 2013,
     'En la Birmingham de la posguerra, Tommy Shelby y su familia de gánsteres '
     'buscan expandir su imperio criminal.'),
    ('Game of Thrones', 'serie', 'Fantasía', 73, 2011,
     'Varias casas nobles luchan por el Trono de Hierro mientras una antigua amenaza '
     'despierta más allá del Muro.'),
    ('Friends', 'serie', 'Comedia', 236, 1994,
     'Seis amigos comparten amores, trabajos y tazas de café en Nueva York.'),
    ('The Walking Dead', 'serie', 'Suspenso', 177, 2010,
     'Tras un apocalipsis zombi, un grupo de sobrevivientes busca un lugar seguro '
     'y descubre que los vivos pueden ser más peligrosos que los muertos.'),
    ('Chernobyl', 'serie', 'Drama', 5, 2019,
     'La explosión de la central nuclear de Chernóbil en 1986 y la lucha por contener '
     'el desastre y ocultar la verdad.'),

    # --- Animes ---
    ('Fullmetal Alchemist: Brotherhood', 'anime', 'Acción', 64, 2009,
     'Dos hermanos alquimistas buscan la piedra filosofal para recuperar sus cuerpos.'),
    ('Attack on Titan', 'anime', 'Acción', 89, 2013,
     'La humanidad vive encerrada tras enormes murallas para protegerse de los titanes.'),
    ('Death Note', 'anime', 'Suspenso', 37, 2006,
     'Un estudiante encuentra un cuaderno que mata a cualquiera cuyo nombre se escriba en él.'),
    ('Steins;Gate', 'anime', 'Ciencia ficción', 24, 2011,
     'Un científico autoproclamado descubre por accidente cómo enviar mensajes al pasado.'),
    ('Haikyuu!!', 'anime', 'Deportes', 85, 2014,
     'Un chico bajito con un salto increíble se une al equipo de voleibol de su colegio.'),
    ('Spy x Family', 'anime', 'Comedia', 37, 2022,
     'Un espía, una asesina y una niña telépata forman una familia falsa, '
     'cada uno sin conocer el secreto de los otros.'),
    ('The Seven Deadly Sins', 'anime', 'Fantasía', 96, 2014,
     'Una princesa busca a los Siete Pecados Capitales, un grupo de caballeros acusados '
     'de traición, para liberar su reino de los Caballeros Sagrados.'),
    ('Naruto', 'anime', 'Acción', 220, 2002,
     'Un joven ninja marginado por su aldea sueña con convertirse en Hokage, '
     'el líder más fuerte y respetado de todos.'),
    ('Dragon Ball', 'anime', 'Acción', 153, 1986,
     'Un niño con cola de mono y fuerza sobrehumana recorre el mundo en busca '
     'de las siete esferas del dragón, capaces de cumplir cualquier deseo.'),
    ('Jujutsu Kaisen', 'anime', 'Acción', 59, 2020,
     'Un estudiante se traga un dedo maldito para salvar a sus amigos y termina '
     'en una escuela de hechiceros que combaten maldiciones.'),
    ('The Eminence in Shadow', 'anime', 'Fantasía', 32, 2022,
     'Reencarnado en otro mundo, Cid finge ser un simple estudiante mientras dirige '
     'en secreto Shadow Garden, una organización que combate a un culto que él cree inventado.'),
]

# usuario -> [(título, estado, episodio, calificación, plataforma, favorita)]
SEGUIMIENTOS = {
    'laura': [
        ('Breaking Bad', 'completada', 62, 10, 'Netflix', True),
        ('Dark', 'completada', 26, 9, 'Netflix', True),
        ('The Office', 'pausada', 57, 7, 'Prime Video', False),
        ('House', 'viendo', 95, 9, 'Prime Video', False),
        ('Game of Thrones', 'abandonada', 40, 6, 'Max', False),
        ('Attack on Titan', 'viendo', 40, 9, 'Crunchyroll', False),
        ('Spy x Family', 'pendiente', 0, None, '', False),
        ('Jujutsu Kaisen', 'viendo', 30, 9, 'Crunchyroll', True),
        ('The Seven Deadly Sins', 'completada', 96, 7, 'Netflix', False),
    ],
    'andres': [
        ('Breaking Bad', 'completada', 62, 9, 'Netflix', False),
        ('Narcos', 'abandonada', 6, 5, 'Netflix', False),
        ('Peaky Blinders', 'completada', 36, 10, 'Netflix', True),
        ('Chernobyl', 'completada', 5, 10, 'Max', False),
        ('The Walking Dead', 'pausada', 70, 7, 'Disney+', False),
        ('Fullmetal Alchemist: Brotherhood', 'completada', 64, 10, 'Crunchyroll', True),
        ('Death Note', 'completada', 37, 8, 'Netflix', False),
        ('Haikyuu!!', 'viendo', 30, 9, 'Crunchyroll', True),
        ('Naruto', 'completada', 220, 9, 'Crunchyroll', True),
        ('Dragon Ball', 'viendo', 80, 8, 'Crunchyroll', False),
        ('Jujutsu Kaisen', 'completada', 59, 10, 'Crunchyroll', False),
        ('The Eminence in Shadow', 'completada', 32, 9, 'Crunchyroll', True),
    ],
    'sofia': [
        ('Brooklyn Nine-Nine', 'completada', 153, 9, 'Netflix', True),
        ('Stranger Things', 'viendo', 25, 8, 'Netflix', False),
        ('Dark', 'viendo', 10, None, 'Netflix', False),
        ('Friends', 'completada', 236, 9, 'Max', True),
        ('House', 'completada', 177, 9, 'Prime Video', False),
        ('Peaky Blinders', 'viendo', 20, 9, 'Netflix', False),
        ('Steins;Gate', 'completada', 24, 10, 'Crunchyroll', True),
        ('Attack on Titan', 'completada', 89, 8, 'Crunchyroll', False),
        ('Naruto', 'pausada', 120, 8, 'Netflix', False),
        ('The Seven Deadly Sins', 'viendo', 40, 8, 'Netflix', True),
        ('The Eminence in Shadow', 'viendo', 14, 8, 'Crunchyroll', False),
    ],
}

# (usuario, título, texto)
COMENTARIOS = [
    ('laura', 'Breaking Bad', 'El mejor final que he visto en una serie. Cada temporada es mejor que la anterior.'),
    ('andres', 'Breaking Bad', 'Arranca lento, pero cuando engancha no la puedes soltar.'),
    ('sofia', 'Dark', 'Recomiendo ir anotando los personajes y sus épocas, ¡es un rompecabezas!'),
    ('sofia', 'House', 'Todos los capítulos siguen la misma fórmula y aun así no me canso. "Todo el mundo miente."'),
    ('andres', 'Peaky Blinders', 'La música, la ambientación y Tommy Shelby. Por orden de los Peaky Blinders.'),
    ('andres', 'Chernobyl', 'Solo cinco episodios y te deja pensando durante días.'),
    ('laura', 'Game of Thrones', 'Las primeras temporadas son increíbles; la última me decepcionó.'),
    ('andres', 'Fullmetal Alchemist: Brotherhood', 'Una historia redonda de principio a fin. Imprescindible.'),
    ('sofia', 'Steins;Gate', 'Los primeros capítulos son raros, pero después de la mitad es una joya.'),
    ('laura', 'Attack on Titan', 'Los giros de la tercera temporada me dejaron sin palabras.'),
    ('andres', 'Naruto', 'Tiene mucho relleno, pero la historia de fondo vale cada episodio.'),
    ('sofia', 'The Seven Deadly Sins', 'La primera temporada es lo mejor; después la animación baja bastante.'),
    ('andres', 'The Eminence in Shadow', 'Cid y Shadow Garden son lo máximo: parodia y acción en partes iguales.'),
    ('laura', 'Jujutsu Kaisen', 'Las peleas de la segunda temporada son de otro nivel.'),
]


class Command(BaseCommand):
    help = 'Carga géneros, títulos, usuarios, seguimientos y comentarios de ejemplo.'

    @transaction.atomic
    def handle(self, *args, **options):
        creados = dict.fromkeys(['géneros', 'títulos', 'portadas', 'usuarios', 'seguimientos', 'comentarios'], 0)

        titulos = {}
        for nombre, tipo, genero, episodios, anio, sinopsis in TITULOS:
            genero_obj, nuevo = Genero.objects.get_or_create(nombre=genero)
            creados['géneros'] += nuevo
            titulos[nombre], nuevo = Titulo.objects.get_or_create(
                nombre=nombre,
                anio=anio,
                defaults={
                    'tipo': tipo,
                    'genero': genero_obj,
                    'total_episodios': episodios,
                    'sinopsis': sinopsis,
                },
            )
            creados['títulos'] += nuevo

            # Se genera portada si el título no tiene una o si el archivo no está en disco
            # (media/ no se sube a git, así que al clonar el repo las imágenes faltan).
            # Nunca pisa una portada que sí existe, como las subidas por el admin.
            portada_actual = titulos[nombre].portada
            if not portada_actual or not portada_actual.storage.exists(portada_actual.name):
                guardar_portada_generada(titulos[nombre])
                creados['portadas'] += 1

        usuarios = {}
        for username in SEGUIMIENTOS:
            usuario, nuevo = User.objects.get_or_create(
                username=username,
                defaults={'email': f'{username}@ejemplo.com'},
            )
            if nuevo:
                usuario.set_password(CLAVE_DEMO)
                usuario.save()
            usuarios[username] = usuario
            creados['usuarios'] += nuevo

        for username, lista in SEGUIMIENTOS.items():
            for titulo, estado, episodio, calificacion, plataforma, favorita in lista:
                _, nuevo = Seguimiento.objects.get_or_create(
                    usuario=usuarios[username],
                    titulo=titulos[titulo],
                    defaults={
                        'estado': estado,
                        'episodio_actual': episodio,
                        'calificacion': calificacion,
                        'plataforma': plataforma,
                        'favorita': favorita,
                        'fecha_inicio': date(2026, 8, 1),
                    },
                )
                creados['seguimientos'] += nuevo

        for username, titulo, texto in COMENTARIOS:
            _, nuevo = Comentario.objects.get_or_create(
                usuario=usuarios[username],
                titulo=titulos[titulo],
                texto=texto,
            )
            creados['comentarios'] += nuevo

        resumen = ', '.join(f'{cantidad} {nombre}' for nombre, cantidad in creados.items())
        self.stdout.write(self.style.SUCCESS(f'Datos de ejemplo cargados: {resumen}.'))
        if creados['usuarios']:
            self.stdout.write(
                f'Usuarios de prueba: {", ".join(SEGUIMIENTOS)} (contraseña: {CLAVE_DEMO})'
            )
