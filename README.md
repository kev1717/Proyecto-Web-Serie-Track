# SerieTrack

Sitio web para llevar el seguimiento de las series y animes que ves: en qué episodio vas,
qué calificación les das y qué opina la comunidad.

Proyecto individual del curso **Programación en la Web** (UIS 2026-II), hecho en Django
con plantillas y Bootstrap 5. Funciona en local con SQLite.

## Funcionalidades

- **Visitante:** ve la página de inicio, el catálogo (con búsqueda y filtros por tipo y género),
  la página de cada título y el ranking. Puede registrarse e iniciar sesión.
- **Usuario:** agrega títulos a **Mi lista**, actualiza su progreso (incluido un botón rápido
  "+1 episodio"), cambia el estado, califica del 1 al 10, marca favoritas y comenta. Mi lista
  se puede filtrar por estado y por favoritas, y se muestra de a 12 títulos por página.
- **Administrador** (`/admin`): gestiona el catálogo, los géneros y los usuarios, y modera
  los comentarios (puede ocultarlos). Al añadir un título elige el color de la portada de
  una lista, con una vista previa que se actualiza mientras llena el formulario, y la
  portada se genera sola al guardar; también puede subir una imagen propia.

## Cómo ejecutarlo

Requiere Python 3.12 o superior. En Windows (PowerShell):

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
py manage.py runserver
```

Luego se abre http://127.0.0.1:8000/.

El repositorio ya incluye la base de datos (`db.sqlite3`) con títulos, usuarios,
seguimientos y comentarios de ejemplo, y las portadas en `media/portadas/`.

Si se empieza con una base de datos vacía, o falta alguna portada, se ejecuta:

```powershell
py manage.py migrate
py manage.py cargar_ejemplos
```

Ese comando crea los datos de ejemplo y genera las portadas que falten. Se puede
ejecutar varias veces sin duplicar nada ni reemplazar portadas existentes.

## Usuarios de ejemplo

| Usuario  | Contraseña      | Rol                                   |
|----------|-----------------|---------------------------------------|
| admin    | admin           | Administrador (entra a `/admin`)      |
| laura    | serietrack123   | Usuario                               |
| andres   | serietrack123   | Usuario                               |
| sofia    | serietrack123   | Usuario                               |

La cuenta `admin` viene en `db.sqlite3` (la del repositorio base del curso). Si se empieza
con una base de datos nueva, se crea otra con `py manage.py createsuperuser`.

## Pruebas

```powershell
py manage.py test modulo
```

## Estructura

Todo el código está en la app `modulo`:

- `models.py`: `Genero`, `Titulo`, `Seguimiento` y `Comentario`.
- `views.py`, `urls.py`, `forms.py`: las páginas del sitio.
- `admin.py` y `templates/admin/`: el panel de administración personalizado.
- `portadas.py`: genera portadas originales con Pillow (no se usan pósters con derechos de autor).
- `management/commands/cargar_ejemplos.py`: los datos de ejemplo.
- `tests.py`: las pruebas.
