from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, redirect_to_login
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ComentarioForm, FiltroCatalogoForm, FiltroMiListaForm, LoginForm, RegistroForm, SeguimientoForm
from .models import Seguimiento, Titulo

TITULOS_POR_PAGINA = 12

# Ranking: cuántas calificaciones necesita un título para aparecer y cuántos se muestran.
# Con pocos usuarios (proyecto local) basta 1; en un sitio real convendría subirlo
# para que un único 10 no ponga a un título en el primer puesto.
VOTOS_MINIMOS_RANKING = 1
TAMANO_RANKING = 50


def inicio(request):
    recientes = Titulo.objects.select_related('genero').order_by('-id')[:4]
    return render(request, 'modulo/inicio.html', {'recientes': recientes})


def catalogo(request):
    titulos = Titulo.objects.select_related('genero')
    form = FiltroCatalogoForm(request.GET or None)

    if form.is_valid():
        q = form.cleaned_data['q'].strip()
        tipo = form.cleaned_data['tipo']
        genero = form.cleaned_data['genero']
        if q:
            titulos = titulos.filter(nombre__icontains=q)
        if tipo:
            titulos = titulos.filter(tipo=tipo)
        if genero:
            titulos = titulos.filter(genero=genero)

    paginador = Paginator(titulos, TITULOS_POR_PAGINA)
    pagina = paginador.get_page(request.GET.get('page'))

    return render(request, 'modulo/catalogo.html', {
        'form': form,
        'pagina': pagina,
        'total': paginador.count,
    })


def titulo_detalle(request, pk):
    titulo = get_object_or_404(Titulo.objects.select_related('genero'), pk=pk)

    # Publicar un comentario (el formulario está en esta misma página)
    form_comentario = None
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        form_comentario = ComentarioForm(request.POST)
        if form_comentario.is_valid():
            comentario = form_comentario.save(commit=False)
            comentario.usuario = request.user
            comentario.titulo = titulo
            comentario.save()
            messages.success(request, 'Tu comentario se publicó.')
            # Redirigir tras el POST evita que al recargar se publique dos veces
            return redirect(titulo.get_absolute_url() + '#comentarios')

    seguimiento = None
    if request.user.is_authenticated:
        seguimiento = Seguimiento.objects.filter(usuario=request.user, titulo=titulo).first()
        if form_comentario is None:
            form_comentario = ComentarioForm()

    # Solo se muestran los comentarios que el admin no ha ocultado
    comentarios = titulo.comentarios.filter(visible=True).select_related('usuario')

    # Estadísticas de la comunidad: promedio de calificaciones y número de seguidores
    estadisticas = titulo.seguimientos.aggregate(
        promedio=Avg('calificacion'),
        votos=Count('calificacion'),  # Count ignora los NULL (sin calificar)
        seguidores=Count('id'),
    )

    return render(request, 'modulo/titulo_detalle.html', {
        'titulo': titulo,
        'seguimiento': seguimiento,
        'comentarios': comentarios,
        'form_comentario': form_comentario,
        'estadisticas': estadisticas,
    })


def ranking(request):
    titulos = (
        Titulo.objects
        .select_related('genero')
        .annotate(
            promedio=Avg('seguimientos__calificacion'),
            votos=Count('seguimientos__calificacion'),
        )
        .filter(votos__gte=VOTOS_MINIMOS_RANKING)
        # En caso de empate, gana el que tiene más votos
        .order_by('-promedio', '-votos', 'nombre')
    )

    tipo = request.GET.get('tipo', '')
    if tipo in Titulo.Tipo.values:
        titulos = titulos.filter(tipo=tipo)
    else:
        tipo = ''

    return render(request, 'modulo/ranking.html', {
        'titulos': titulos[:TAMANO_RANKING],
        'tipo_actual': tipo,
        'tipos': Titulo.Tipo.choices,
        'votos_minimos': VOTOS_MINIMOS_RANKING,
    })


def registro(request):
    if request.user.is_authenticated:
        return redirect('inicio')

    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            login(request, usuario)
            messages.success(request, f'¡Bienvenido a SerieTrack, {usuario.username}!')
            return redirect('inicio')
    else:
        form = RegistroForm()

    return render(request, 'modulo/registro.html', {'form': form})


class IniciarSesionView(LoginView):
    template_name = 'modulo/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True


# ---------------------------------------------------------------------------
# Mi lista (seguimientos del usuario)
# ---------------------------------------------------------------------------

def _seguimiento_del_usuario(request, pk):
    """Devuelve el seguimiento solo si pertenece al usuario; si no, 404."""
    return get_object_or_404(
        Seguimiento.objects.select_related('titulo'),
        pk=pk,
        usuario=request.user,
    )


@login_required
def mi_lista(request):
    seguimientos = (
        Seguimiento.objects
        .filter(usuario=request.user)
        .select_related('titulo', 'titulo__genero')
        .order_by('-favorita', 'titulo__nombre')
    )

    # Cantidad por estado para las pestañas (se calcula antes de filtrar)
    conteos = seguimientos.aggregate(
        todos=Count('id'),
        favoritas=Count('id', filter=Q(favorita=True)),
        **{e.value: Count('id', filter=Q(estado=e.value)) for e in Seguimiento.Estado},
    )
    pestanas = [('', 'Todos', conteos['todos'])] + [
        (e.value, e.label, conteos[e.value]) for e in Seguimiento.Estado
    ]

    filtro = FiltroMiListaForm(request.GET)
    estado = favoritas = None
    if filtro.is_valid():
        estado = filtro.cleaned_data['estado']
        favoritas = filtro.cleaned_data['favoritas']
        if estado:
            seguimientos = seguimientos.filter(estado=estado)
        if favoritas:
            seguimientos = seguimientos.filter(favorita=True)

    return render(request, 'modulo/mi_lista.html', {
        'seguimientos': seguimientos,
        'pestanas': pestanas,
        'estado_actual': estado or '',
        'solo_favoritas': favoritas,
        'total_favoritas': conteos['favoritas'],
    })


@login_required
@require_POST
def agregar_seguimiento(request, pk):
    titulo = get_object_or_404(Titulo, pk=pk)
    _, creado = Seguimiento.objects.get_or_create(usuario=request.user, titulo=titulo)
    if creado:
        messages.success(request, f'"{titulo.nombre}" se agregó a tu lista.')
    else:
        messages.info(request, f'"{titulo.nombre}" ya estaba en tu lista.')
    return redirect(titulo)


@login_required
def editar_seguimiento(request, pk):
    seguimiento = _seguimiento_del_usuario(request, pk)

    if request.method == 'POST':
        form = SeguimientoForm(request.POST, instance=seguimiento)
        if form.is_valid():
            form.save()
            messages.success(request, f'Se actualizó tu progreso en "{seguimiento.titulo.nombre}".')
            return redirect('mi_lista')
    else:
        form = SeguimientoForm(instance=seguimiento)

    return render(request, 'modulo/seguimiento_form.html', {
        'form': form,
        'seguimiento': seguimiento,
    })


@login_required
@require_POST
def sumar_episodio(request, pk):
    """Botón rápido "+1": avanza un episodio y marca el título como completado al llegar al final."""
    seguimiento = _seguimiento_del_usuario(request, pk)
    titulo = seguimiento.titulo

    if seguimiento.terminado:
        messages.info(request, f'Ya viste todos los episodios de "{titulo.nombre}".')
    else:
        seguimiento.episodio_actual += 1
        if seguimiento.terminado:
            seguimiento.estado = Seguimiento.Estado.COMPLETADA
            messages.success(request, f'¡Terminaste "{titulo.nombre}"! Se marcó como completada.')
        else:
            if seguimiento.estado == Seguimiento.Estado.PENDIENTE:
                seguimiento.estado = Seguimiento.Estado.VIENDO
            messages.success(request, f'"{titulo.nombre}": vas en el episodio {seguimiento.episodio_actual}.')
        seguimiento.save()

    # Vuelve a la página desde donde se pulsó el botón
    if request.POST.get('volver') == 'titulo':
        return redirect(titulo)
    return redirect('mi_lista')


@login_required
def eliminar_seguimiento(request, pk):
    seguimiento = _seguimiento_del_usuario(request, pk)

    if request.method == 'POST':
        nombre = seguimiento.titulo.nombre
        seguimiento.delete()
        messages.success(request, f'"{nombre}" se quitó de tu lista.')
        return redirect('mi_lista')

    return render(request, 'modulo/seguimiento_eliminar.html', {'seguimiento': seguimiento})
