// Vista previa en vivo de la portada en el formulario de títulos del admin.
// Al cambiar el nombre, tipo, género, año o color se pide al servidor la portada
// con esos datos (sin guardar nada). Si se elige un archivo, se muestra ese.
document.addEventListener('DOMContentLoaded', function () {
    const imagen = document.getElementById('st-vista-previa');
    if (!imagen) return;

    const aviso = document.getElementById('st-aviso-subida');
    const archivo = document.getElementById('id_portada');
    const quitar = document.getElementById('portada-clear_id');  // casilla "Limpiar" del admin
    const campos = ['nombre', 'tipo', 'genero', 'anio', 'color_portada']
        .map(function (nombre) { return document.getElementById('id_' + nombre); })
        .filter(Boolean);

    const original = imagen.src;
    const tieneSubida = imagen.dataset.subida === '1';
    let urlArchivo = null;
    let espera = null;

    function mostrar() {
        const quitaLaSubida = quitar && quitar.checked;
        const esImagenSubida = Boolean(urlArchivo) || (tieneSubida && !quitaLaSubida);
        aviso.hidden = !esImagenSubida;

        if (urlArchivo) {
            imagen.src = urlArchivo;
        } else if (esImagenSubida) {
            imagen.src = original;
        } else {
            const parametros = new URLSearchParams();
            campos.forEach(function (campo) { parametros.set(campo.name, campo.value); });
            imagen.src = imagen.dataset.url + '?' + parametros.toString();
        }
    }

    campos.forEach(function (campo) {
        campo.addEventListener('change', mostrar);
        if (campo.tagName === 'INPUT') {
            // Mientras se escribe, espera medio segundo para no pedir una imagen por letra
            campo.addEventListener('input', function () {
                clearTimeout(espera);
                espera = setTimeout(mostrar, 500);
            });
        }
    });

    if (archivo) {
        archivo.addEventListener('change', function () {
            if (urlArchivo) URL.revokeObjectURL(urlArchivo);
            urlArchivo = archivo.files[0] ? URL.createObjectURL(archivo.files[0]) : null;
            mostrar();
        });
    }
    if (quitar) quitar.addEventListener('change', mostrar);
});
