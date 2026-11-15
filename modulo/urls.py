from django.contrib.auth.views import LogoutView
from django.urls import path
from . import views

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('catalogo/', views.catalogo, name='catalogo'),
    path('titulos/<int:pk>/', views.titulo_detalle, name='titulo_detalle'),
    path('ranking/', views.ranking, name='ranking'),
    path('titulos/<int:pk>/agregar/', views.agregar_seguimiento, name='agregar_seguimiento'),
    path('mi-lista/', views.mi_lista, name='mi_lista'),
    path('mi-lista/<int:pk>/editar/', views.editar_seguimiento, name='editar_seguimiento'),
    path('mi-lista/<int:pk>/sumar/', views.sumar_episodio, name='sumar_episodio'),
    path('mi-lista/<int:pk>/quitar/', views.eliminar_seguimiento, name='eliminar_seguimiento'),
    path('registro/', views.registro, name='registro'),
    path('login/', views.IniciarSesionView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
]
