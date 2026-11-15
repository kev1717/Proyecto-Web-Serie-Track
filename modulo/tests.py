"""Pruebas de SerieTrack.  Ejecutar con:  py manage.py test modulo"""
import shutil
import tempfile
from io import BytesIO, StringIO

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Comentario, Genero, Seguimiento, Titulo
from .portadas import COLORES_PORTADA, generar_portada

CLAVE = 'clave-de-prueba-123'


class DatosBase(TestCase):
    """Crea un género, dos títulos y dos usuarios para todas las pruebas."""

    @classmethod
    def setUpTestData(cls):
        cls.genero = Genero.objects.create(nombre='Drama')
        cls.serie = Titulo.objects.create(
            nombre='Serie de prueba', tipo='serie', genero=cls.genero, total_episodios=3, anio=2020,
        )
        cls.anime = Titulo.objects.create(
            nombre='Anime de prueba', tipo='anime', genero=cls.genero, total_episodios=12, anio=2021,
        )
        cls.ana = User.objects.create_user('ana', password=CLAVE)
        cls.beto = User.objects.create_user('beto', password=CLAVE)

    def entrar(self, usuario):
        self.client.login(username=usuario.username, password=CLAVE)


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------

class SeguimientoModeloTests(DatosBase):
    def test_episodio_no_puede_superar_el_total(self):
        s = Seguimiento(usuario=self.ana, titulo=self.serie, episodio_actual=4)
        with self.assertRaises(ValidationError) as error:
            s.full_clean()
        self.assertIn('episodio_actual', error.exception.message_dict)

    def test_episodio_igual_al_total_es_valido(self):
        Seguimiento(usuario=self.ana, titulo=self.serie, episodio_actual=3).full_clean()

    def test_calificacion_fuera_de_rango(self):
        for valor in (0, 11):
            s = Seguimiento(usuario=self.ana, titulo=self.serie, calificacion=valor)
            with self.assertRaises(ValidationError):
                s.full_clean()

    def test_unico_por_usuario_y_titulo(self):
        Seguimiento.objects.create(usuario=self.ana, titulo=self.serie)
        with self.assertRaises(IntegrityError):
            Seguimiento.objects.create(usuario=self.ana, titulo=self.serie)

    def test_porcentaje_y_terminado(self):
        s = Seguimiento(usuario=self.ana, titulo=self.serie, episodio_actual=1)
        self.assertEqual(s.porcentaje, 33)
        self.assertFalse(s.terminado)
        s.episodio_actual = 3
        self.assertEqual(s.porcentaje, 100)
        self.assertTrue(s.terminado)


# ---------------------------------------------------------------------------
# Páginas públicas
# ---------------------------------------------------------------------------

class PaginasPublicasTests(DatosBase):
    def test_paginas_abiertas_a_visitantes(self):
        for url in ('inicio', 'catalogo', 'ranking', 'registro', 'login'):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(reverse(url)).status_code, 200)
        self.assertEqual(self.client.get(self.serie.get_absolute_url()).status_code, 200)

    def test_titulo_inexistente_da_404(self):
        self.assertEqual(self.client.get(reverse('titulo_detalle', args=[999])).status_code, 404)

    def test_filtros_del_catalogo(self):
        respuesta = self.client.get(reverse('catalogo'), {'tipo': 'anime'})
        self.assertContains(respuesta, 'Anime de prueba')
        self.assertNotContains(respuesta, 'Serie de prueba')

        respuesta = self.client.get(reverse('catalogo'), {'q': 'serie'})
        self.assertContains(respuesta, 'Serie de prueba')
        self.assertNotContains(respuesta, 'Anime de prueba')

    def test_registro_inicia_sesion(self):
        respuesta = self.client.post(reverse('registro'), {
            'username': 'nuevo',
            'email': 'nuevo@ejemplo.com',
            'password1': 'Una-clave-segura-99',
            'password2': 'Una-clave-segura-99',
        })
        self.assertRedirects(respuesta, reverse('inicio'))
        self.assertEqual(int(self.client.session['_auth_user_id']), User.objects.get(username='nuevo').pk)


# ---------------------------------------------------------------------------
# Mi lista
# ---------------------------------------------------------------------------

class MiListaTests(DatosBase):
    def test_requiere_iniciar_sesion(self):
        respuesta = self.client.get(reverse('mi_lista'))
        self.assertRedirects(respuesta, f"{reverse('login')}?next={reverse('mi_lista')}")

    def test_agregar_titulo_sin_duplicar(self):
        self.entrar(self.ana)
        url = reverse('agregar_seguimiento', args=[self.serie.pk])
        self.assertEqual(self.client.get(url).status_code, 405)  # solo POST
        self.client.post(url)
        self.client.post(url)
        self.assertEqual(Seguimiento.objects.filter(usuario=self.ana).count(), 1)
        self.assertContains(self.client.get(reverse('mi_lista')), 'Serie de prueba')

    def test_filtro_por_estado(self):
        Seguimiento.objects.create(usuario=self.ana, titulo=self.serie, estado='viendo')
        Seguimiento.objects.create(usuario=self.ana, titulo=self.anime, estado='pendiente')
        self.entrar(self.ana)
        respuesta = self.client.get(reverse('mi_lista'), {'estado': 'viendo'})
        self.assertContains(respuesta, 'Serie de prueba')
        self.assertNotContains(respuesta, 'Anime de prueba')

    def test_editar_valida_episodios(self):
        s = Seguimiento.objects.create(usuario=self.ana, titulo=self.serie)
        self.entrar(self.ana)
        datos = {'estado': 'viendo', 'episodio_actual': 5, 'calificacion': 8,
                 'plataforma': 'Netflix', 'fecha_inicio': '2026-11-01'}
        respuesta = self.client.post(reverse('editar_seguimiento', args=[s.pk]), datos)
        self.assertContains(respuesta, 'No puede superar el total de episodios (3)')

        datos['episodio_actual'] = 2
        respuesta = self.client.post(reverse('editar_seguimiento', args=[s.pk]), datos)
        self.assertRedirects(respuesta, reverse('mi_lista'))
        s.refresh_from_db()
        self.assertEqual((s.episodio_actual, s.calificacion, s.plataforma), (2, 8, 'Netflix'))

    def test_sumar_episodio_completa_al_final(self):
        s = Seguimiento.objects.create(usuario=self.ana, titulo=self.serie, episodio_actual=1)
        self.entrar(self.ana)
        url = reverse('sumar_episodio', args=[s.pk])

        self.client.post(url)
        s.refresh_from_db()
        self.assertEqual((s.episodio_actual, s.estado), (2, 'viendo'))  # pendiente -> viendo

        self.client.post(url)
        self.client.post(url)  # ya en el último: no pasa del total
        s.refresh_from_db()
        self.assertEqual((s.episodio_actual, s.estado), (3, 'completada'))

    def test_sumar_episodio_vuelve_al_titulo(self):
        s = Seguimiento.objects.create(usuario=self.ana, titulo=self.serie)
        self.entrar(self.ana)
        respuesta = self.client.post(reverse('sumar_episodio', args=[s.pk]), {'volver': 'titulo'})
        self.assertRedirects(respuesta, self.serie.get_absolute_url())

    def test_quitar_de_la_lista(self):
        s = Seguimiento.objects.create(usuario=self.ana, titulo=self.serie)
        self.entrar(self.ana)
        url = reverse('eliminar_seguimiento', args=[s.pk])
        self.assertEqual(self.client.get(url).status_code, 200)  # confirmación
        self.assertTrue(Seguimiento.objects.exists())
        self.client.post(url)
        self.assertFalse(Seguimiento.objects.exists())

    def test_no_se_puede_tocar_la_lista_de_otro(self):
        s = Seguimiento.objects.create(usuario=self.ana, titulo=self.serie)
        self.entrar(self.beto)
        for nombre in ('editar_seguimiento', 'eliminar_seguimiento'):
            with self.subTest(vista=nombre):
                self.assertEqual(self.client.get(reverse(nombre, args=[s.pk])).status_code, 404)
                self.assertEqual(self.client.post(reverse(nombre, args=[s.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('sumar_episodio', args=[s.pk])).status_code, 404)
        self.assertTrue(Seguimiento.objects.filter(pk=s.pk, episodio_actual=0).exists())


# ---------------------------------------------------------------------------
# Comentarios
# ---------------------------------------------------------------------------

class ComentariosTests(DatosBase):
    def test_visitante_no_puede_comentar(self):
        respuesta = self.client.post(self.serie.get_absolute_url(), {'texto': 'Hola'})
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse('login'), respuesta.url)
        self.assertFalse(Comentario.objects.exists())

    def test_publicar_comentario(self):
        self.entrar(self.ana)
        respuesta = self.client.post(self.serie.get_absolute_url(), {'texto': 'Muy buena'})
        self.assertRedirects(respuesta, self.serie.get_absolute_url() + '#comentarios')
        comentario = Comentario.objects.get()
        self.assertEqual((comentario.usuario, comentario.titulo), (self.ana, self.serie))
        self.assertContains(self.client.get(self.serie.get_absolute_url()), 'Muy buena')

    def test_comentario_vacio_no_se_guarda(self):
        self.entrar(self.ana)
        respuesta = self.client.post(self.serie.get_absolute_url(), {'texto': '   '})
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Comentario.objects.exists())

    def test_html_se_escapa(self):
        Comentario.objects.create(usuario=self.ana, titulo=self.serie, texto='<b>hola</b>')
        respuesta = self.client.get(self.serie.get_absolute_url())
        self.assertContains(respuesta, '&lt;b&gt;hola&lt;/b&gt;')

    def test_comentario_oculto_no_se_muestra(self):
        Comentario.objects.create(usuario=self.ana, titulo=self.serie, texto='Visible')
        Comentario.objects.create(usuario=self.ana, titulo=self.serie, texto='Moderado', visible=False)
        respuesta = self.client.get(self.serie.get_absolute_url())
        self.assertContains(respuesta, 'Visible')
        self.assertNotContains(respuesta, 'Moderado')


# ---------------------------------------------------------------------------
# Ranking y estadísticas
# ---------------------------------------------------------------------------

class RankingTests(DatosBase):
    def setUp(self):
        Seguimiento.objects.create(usuario=self.ana, titulo=self.serie, calificacion=8)
        Seguimiento.objects.create(usuario=self.beto, titulo=self.serie, calificacion=9)
        Seguimiento.objects.create(usuario=self.ana, titulo=self.anime, calificacion=10)

    def test_orden_por_promedio(self):
        titulos = list(self.client.get(reverse('ranking')).context['titulos'])
        self.assertEqual(titulos, [self.anime, self.serie])
        self.assertEqual(titulos[1].promedio, 8.5)
        self.assertEqual(titulos[1].votos, 2)

    def test_sin_calificar_no_aparece(self):
        sin_votos = Titulo.objects.create(
            nombre='Sin votos', tipo='serie', genero=self.genero, total_episodios=5, anio=2022,
        )
        Seguimiento.objects.create(usuario=self.beto, titulo=sin_votos)
        self.assertNotIn(sin_votos, self.client.get(reverse('ranking')).context['titulos'])

    def test_filtro_por_tipo(self):
        titulos = list(self.client.get(reverse('ranking'), {'tipo': 'serie'}).context['titulos'])
        self.assertEqual(titulos, [self.serie])
        titulos = list(self.client.get(reverse('ranking'), {'tipo': 'inventado'}).context['titulos'])
        self.assertEqual(len(titulos), 2)

    def test_estadisticas_en_detalle(self):
        estadisticas = self.client.get(self.serie.get_absolute_url()).context['estadisticas']
        self.assertEqual(estadisticas, {'promedio': 8.5, 'votos': 2, 'seguidores': 2})


# ---------------------------------------------------------------------------
# Portadas generadas y datos de ejemplo
# ---------------------------------------------------------------------------

class PortadaTests(DatosBase):
    def test_genera_png_con_proporcion_de_poster(self):
        archivo = generar_portada(self.serie)
        self.assertEqual(archivo.name, 'serie-de-prueba.png')
        imagen = Image.open(BytesIO(archivo.read()))
        self.assertEqual((imagen.format, imagen.size), ('PNG', (400, 600)))

    def test_nombre_muy_largo_no_falla(self):
        self.serie.nombre = 'Supercalifragilisticoespialidoso ' * 4
        Image.open(BytesIO(generar_portada(self.serie).read())).verify()

    def test_usa_el_color_elegido_por_el_admin(self):
        # La esquina superior izquierda es el inicio del degradado: el color elegido tal cual
        for valor, rgb in COLORES_PORTADA.items():
            with self.subTest(color=valor):
                self.serie.color_portada = valor
                imagen = Image.open(BytesIO(generar_portada(self.serie).read())).convert('RGB')
                self.assertEqual(imagen.getpixel((0, 0)), rgb)

    def test_todos_los_colores_de_la_lista_tienen_rgb(self):
        valores = {valor for valor in Titulo.ColorPortada.values if valor}
        self.assertEqual(valores, set(COLORES_PORTADA))


class CargarEjemplosTests(TestCase):
    """El comando guarda portadas: se usa una carpeta temporal para no ensuciar media/."""

    def setUp(self):
        carpeta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, carpeta, ignore_errors=True)
        ajuste = override_settings(MEDIA_ROOT=carpeta)
        ajuste.enable()
        self.addCleanup(ajuste.disable)

    def test_se_puede_ejecutar_dos_veces_sin_duplicar(self):
        call_command('cargar_ejemplos', stdout=StringIO())
        cantidades = [m.objects.count() for m in (Genero, Titulo, Seguimiento, Comentario, User)]
        self.assertTrue(all(cantidades))

        call_command('cargar_ejemplos', stdout=StringIO())
        self.assertEqual(cantidades, [m.objects.count() for m in (Genero, Titulo, Seguimiento, Comentario, User)])

    def test_los_datos_cumplen_las_validaciones(self):
        call_command('cargar_ejemplos', stdout=StringIO())
        for seguimiento in Seguimiento.objects.select_related('titulo'):
            seguimiento.full_clean()

    def test_todos_los_titulos_quedan_con_portada(self):
        call_command('cargar_ejemplos', stdout=StringIO())
        self.assertFalse(Titulo.objects.filter(portada='').exists())

    def test_no_reemplaza_una_portada_existente(self):
        call_command('cargar_ejemplos', stdout=StringIO())
        titulo = Titulo.objects.first()
        nombre = default_storage.save('portadas/subida-por-el-admin.jpg', ContentFile(b'imagen'))
        titulo.portada = nombre
        titulo.save()
        call_command('cargar_ejemplos', stdout=StringIO())
        titulo.refresh_from_db()
        self.assertEqual(titulo.portada.name, nombre)

    def test_regenera_la_portada_si_falta_el_archivo(self):
        # Simula clonar el repo: la base de datos tiene la ruta, pero media/ no existe
        call_command('cargar_ejemplos', stdout=StringIO())
        titulo = Titulo.objects.first()
        default_storage.delete(titulo.portada.name)
        call_command('cargar_ejemplos', stdout=StringIO())
        titulo.refresh_from_db()
        self.assertTrue(default_storage.exists(titulo.portada.name))


# ---------------------------------------------------------------------------
# Panel de administración
# ---------------------------------------------------------------------------

class AdminTests(DatosBase):
    def setUp(self):
        carpeta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, carpeta, ignore_errors=True)
        ajuste = override_settings(MEDIA_ROOT=carpeta)
        ajuste.enable()
        self.addCleanup(ajuste.disable)

        self.admin = User.objects.create_superuser('jefe', password=CLAVE)
        self.entrar(self.admin)
        self.seguimiento = Seguimiento.objects.create(usuario=self.ana, titulo=self.serie, calificacion=7)
        self.comentario = Comentario.objects.create(usuario=self.ana, titulo=self.serie, texto='Hola', visible=False)

    def test_paginas_del_admin_cargan(self):
        urls = [
            reverse('admin:index'),
            reverse('admin:modulo_genero_changelist'),
            reverse('admin:modulo_titulo_changelist'),
            reverse('admin:modulo_titulo_change', args=[self.serie.pk]),
            reverse('admin:modulo_titulo_add'),
            reverse('admin:modulo_seguimiento_changelist'),
            reverse('admin:modulo_seguimiento_change', args=[self.seguimiento.pk]),
            reverse('admin:modulo_comentario_changelist'),
            reverse('admin:modulo_comentario_change', args=[self.comentario.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_resumen_en_la_portada(self):
        respuesta = self.client.get(reverse('admin:index'))
        self.assertContains(respuesta, 'st-resumen')
        self.assertContains(respuesta, '1 oculto')
        self.assertContains(respuesta, 'sin portada')

    def test_accion_generar_portada(self):
        respuesta = self.client.post(reverse('admin:modulo_titulo_changelist'), {
            'action': 'generar_portadas',
            '_selected_action': [self.serie.pk, self.anime.pk],
        }, follow=True)
        self.assertContains(respuesta, 'Se generaron 2 portada(s).')
        self.assertFalse(Titulo.objects.filter(portada='').exists())

    # --- Color de la portada elegido por el admin ---

    def _datos_formulario(self, titulo, **cambios):
        """Datos POST del formulario de título del admin (incluye el inline de comentarios vacío)."""
        datos = {
            'nombre': titulo.nombre, 'tipo': titulo.tipo, 'genero': titulo.genero_id,
            'anio': titulo.anio, 'total_episodios': titulo.total_episodios,
            'sinopsis': titulo.sinopsis, 'color_portada': titulo.color_portada,
            'comentarios-TOTAL_FORMS': 0, 'comentarios-INITIAL_FORMS': 0,
            'comentarios-MIN_NUM_FORMS': 0, 'comentarios-MAX_NUM_FORMS': 1000,
        }
        datos.update(cambios)
        return datos

    def _color_de_la_portada(self, titulo):
        with titulo.portada.open('rb') as archivo:
            return Image.open(archivo).convert('RGB').getpixel((0, 0))

    def test_al_crear_un_titulo_se_genera_la_portada_con_el_color_elegido(self):
        nuevo = Titulo(nombre='Serie nueva', tipo='serie', genero=self.genero,
                       anio=2024, total_episodios=8, color_portada='verde')
        respuesta = self.client.post(reverse('admin:modulo_titulo_add'), self._datos_formulario(nuevo))
        self.assertEqual(respuesta.status_code, 302)

        titulo = Titulo.objects.get(nombre='Serie nueva')
        self.assertTrue(titulo.portada_generada)
        self.assertEqual(self._color_de_la_portada(titulo), COLORES_PORTADA['verde'])

    def test_al_cambiar_el_color_se_regenera_y_se_borra_la_vieja(self):
        url = reverse('admin:modulo_titulo_change', args=[self.anime.pk])
        self.client.post(url, self._datos_formulario(self.anime, color_portada='rojo'))
        self.anime.refresh_from_db()
        vieja = self.anime.portada.name

        self.client.post(url, self._datos_formulario(self.anime, color_portada='azul'))
        self.anime.refresh_from_db()
        self.assertEqual(self._color_de_la_portada(self.anime), COLORES_PORTADA['azul'])
        if vieja != self.anime.portada.name:
            self.assertFalse(default_storage.exists(vieja))

    def test_si_no_cambia_nada_de_la_portada_no_se_regenera(self):
        url = reverse('admin:modulo_titulo_change', args=[self.anime.pk])
        self.client.post(url, self._datos_formulario(self.anime, color_portada='rojo'))
        self.anime.refresh_from_db()
        antes = self.anime.portada.name

        self.client.post(url, self._datos_formulario(self.anime, total_episodios=24))
        self.anime.refresh_from_db()
        self.assertEqual(self.anime.portada.name, antes)

    def test_una_portada_subida_nunca_se_reemplaza(self):
        subida = BytesIO()
        Image.new('RGB', (40, 60), (1, 2, 3)).save(subida, format='PNG')
        subida.name = 'mi-poster.png'
        subida.seek(0)
        url = reverse('admin:modulo_titulo_change', args=[self.anime.pk])
        respuesta = self.client.post(url, self._datos_formulario(self.anime, portada=subida))
        self.assertEqual(respuesta.status_code, 302)
        self.anime.refresh_from_db()
        self.assertFalse(self.anime.portada_generada)
        nombre = self.anime.portada.name

        self.client.post(url, self._datos_formulario(self.anime, color_portada='morado'))
        self.anime.refresh_from_db()
        self.assertEqual(self.anime.portada.name, nombre)
        self.assertEqual(self._color_de_la_portada(self.anime), (1, 2, 3))

    # --- Vista previa en vivo ---

    def test_vista_previa_devuelve_la_portada_sin_guardar_nada(self):
        cantidad = Titulo.objects.count()
        respuesta = self.client.get(reverse('admin:modulo_titulo_vista_previa'), {
            'nombre': 'Algo nuevo', 'tipo': 'anime', 'genero': self.genero.pk,
            'anio': 2025, 'color_portada': 'turquesa',
        })
        self.assertEqual(respuesta['Content-Type'], 'image/png')
        imagen = Image.open(BytesIO(respuesta.content)).convert('RGB')
        self.assertEqual(imagen.getpixel((0, 0)), COLORES_PORTADA['turquesa'])
        self.assertEqual(Titulo.objects.count(), cantidad)

    def test_vista_previa_tolera_datos_incompletos(self):
        # Mientras se llena el formulario puede haber campos vacíos o a medio escribir
        respuesta = self.client.get(reverse('admin:modulo_titulo_vista_previa'), {
            'nombre': '', 'tipo': 'x', 'genero': 'abc', 'anio': '20a', 'color_portada': 'fucsia',
        })
        self.assertEqual(respuesta.status_code, 200)
        Image.open(BytesIO(respuesta.content)).verify()

    def test_vista_previa_solo_para_el_admin(self):
        self.client.logout()
        self.entrar(self.ana)
        respuesta = self.client.get(reverse('admin:modulo_titulo_vista_previa'))
        self.assertNotEqual(respuesta.get('Content-Type'), 'image/png')
        self.assertEqual(respuesta.status_code, 302)  # al login del admin

    def test_formulario_incluye_la_vista_previa_en_vivo(self):
        for url in (reverse('admin:modulo_titulo_add'),
                    reverse('admin:modulo_titulo_change', args=[self.anime.pk])):
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertContains(respuesta, 'id="st-vista-previa"')
                self.assertContains(respuesta, 'modulo/js/vista_previa.js')

    def test_formulario_muestra_la_paleta(self):
        respuesta = self.client.get(reverse('admin:modulo_titulo_change', args=[self.anime.pk]))
        self.assertContains(respuesta, 'st-paleta')
        self.assertContains(respuesta, 'Según el género')

    def test_no_se_agregan_comentarios_desde_el_admin(self):
        self.assertEqual(self.client.get(reverse('admin:modulo_comentario_add')).status_code, 403)
