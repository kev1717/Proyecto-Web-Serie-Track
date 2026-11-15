from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from .models import Comentario, Genero, Seguimiento, Titulo


class BootstrapMixin:
    """Agrega las clases de Bootstrap a los widgets del formulario."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if isinstance(campo.widget, forms.CheckboxInput):
                campo.widget.attrs.setdefault('class', 'form-check-input')
            elif isinstance(campo.widget, forms.Select):
                campo.widget.attrs.setdefault('class', 'form-select')
            else:
                campo.widget.attrs.setdefault('class', 'form-control')

    def full_clean(self):
        super().full_clean()
        # Marca en rojo los campos que tienen errores
        for nombre in self.errors:
            if nombre in self.fields:
                widget = self.fields[nombre].widget
                widget.attrs['class'] = widget.attrs.get('class', '') + ' is-invalid'


class RegistroForm(BootstrapMixin, UserCreationForm):
    email = forms.EmailField(label='Correo electrónico')

    class Meta:
        model = User
        fields = ['username', 'email']

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Ya existe una cuenta con este correo.')
        return email


class LoginForm(BootstrapMixin, AuthenticationForm):
    pass


class FiltroCatalogoForm(BootstrapMixin, forms.Form):
    q = forms.CharField(
        label='Buscar',
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Nombre del título'}),
    )
    tipo = forms.ChoiceField(
        label='Tipo',
        required=False,
        choices=[('', 'Todos los tipos')] + Titulo.Tipo.choices,
    )
    genero = forms.ModelChoiceField(
        label='Género',
        required=False,
        queryset=Genero.objects.all(),
        empty_label='Todos los géneros',
    )


class SeguimientoForm(BootstrapMixin, forms.ModelForm):
    """Formulario con el que el usuario actualiza su progreso en un título.

    La instancia debe traer ya el título asignado: así la validación del
    modelo (episodio_actual <= total_episodios) se ejecuta al llamar is_valid().
    """

    class Meta:
        model = Seguimiento
        fields = ['estado', 'episodio_actual', 'calificacion', 'plataforma', 'favorita', 'fecha_inicio']
        widgets = {
            'calificacion': forms.NumberInput(attrs={'min': 1, 'max': 10, 'placeholder': 'Sin calificar'}),
            'plataforma': forms.TextInput(attrs={'placeholder': 'Netflix, Crunchyroll...'}),
            'fecha_inicio': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }
        help_texts = {
            'calificacion': 'Del 1 al 10. Déjalo vacío si aún no quieres calificar.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        total = self.instance.titulo.total_episodios
        self.fields['episodio_actual'].widget.attrs.update({'min': 0, 'max': total})
        self.fields['episodio_actual'].help_text = f'Este título tiene {total} episodios.'


class FiltroMiListaForm(forms.Form):
    estado = forms.ChoiceField(required=False, choices=[('', 'Todos')] + Seguimiento.Estado.choices)
    favoritas = forms.BooleanField(required=False)


class ComentarioForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Comentario
        fields = ['texto']
        labels = {'texto': 'Tu comentario'}
        widgets = {
            'texto': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': '¿Qué te pareció? Evita contar spoilers.',
            }),
        }
