🎵 Flowy Ultra - Modern Music Player
Flowy Ultra es un reproductor de música de escritorio desarrollado en Python que permite buscar, reproducir y descargar audio directamente desde fuentes en línea. Combina una interfaz moderna y oscura con una gestión de cola inteligente y notificaciones nativas del sistema.

🚀 Características principales
Buscador Integrado: Encuentra cualquier canción o artista en tiempo real sin salir de la aplicación.

Gestión de Cola (Queue): Sistema dinámico para añadir canciones a una lista de espera con reproducción automática del siguiente tema.

Sistema de Favoritos: Base de datos local integrada (SQLite) para guardar tus pistas preferidas de forma permanente.

Descargas en MP3: Motor de descarga integrado que convierte el contenido a formato MP3 de alta calidad (192kbps).

Control de Audio Avanzado: * Barra de volumen con iconos dinámicos y porcentaje visual.

Slider de progreso con capacidad de "seek" (adelantar/atrasar).

Visualización de portadas (thumbnails) en tiempo real.

Notificaciones de Escritorio: Avisos nativos de Windows/OS que muestran el título de la canción al iniciar la reproducción.

🛠️ Tecnologías utilizadas
Lenguaje: Python 3.x

Interfaz Gráfica: CustomTkinter (UI moderna y adaptativa).

Motor de Audio: python-vlc (requiere VLC Media Player instalado).

Extracción de Media: yt_dlp para el manejo de streams y metadatos.

Base de Datos: SQLite3 para la persistencia de favoritos.

Notificaciones: plyer.

Procesamiento de Imágenes: Pillow (PIL) y Requests.

📦 Instalación
Clona el repositorio:
```python
Bash
git clone https://github.com/tu-usuario/flowy-ultra.git
cd flowy-ultra
```
Instala las dependencias:
```python
Bash
pip install customtkinter python-vlc yt-dlp pillow requests plyer
```
Requisito del Sistema:
Es necesario tener instalado VLC Media Player (64 bits preferiblemente) en tu sistema, ya que el motor de audio utiliza sus librerías dinámicas.

Ejecuta la aplicación:
```python
Bash
python flowy_app.py
```


📄 Licencia
Este proyecto está bajo la licencia MIT. Siéntete libre de usarlo y mejorarlo.
