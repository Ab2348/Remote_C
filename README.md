# Remote C

Control remoto local para Arch Linux, accesible desde la red privada de Tailscale.

## Funciones

- Volumen general, silencio y reproducción multimedia.
- Aplicaciones con audio unificadas con sus sesiones multimedia.
- Reproducción, seek, volumen, silencio y salida por aplicación.
- Carátula de la pista activa mediante metadata MPRIS.
- Brillo conjunto o independiente para los dos monitores DDC/CI.
- Selección de salida predeterminada y movimiento de todos los flujos activos.
- Interfaz PWA móvil con estado actualizado mediante eventos.
- Wallpaper activo de HyDE sincronizado por eventos y superficies translúcidas.

## Estado en tiempo real

La interfaz mantiene una sola conexión SSE con `GET /api/events`. El servidor publica cambios detectados por `pactl subscribe` y `playerctl --follow`; los endpoints de control también publican su resultado inmediatamente.

DDC/CI no ofrece una fuente de eventos. Mientras haya al menos un cliente conectado, el servidor comprueba el brillo cada 30 segundos y solo publica si cambió. Los cambios realizados mediante `POST /api/brightness` se publican de inmediato.

## Interfaz

El frontend usa JavaScript y CSS nativos. El CSS compartido está dividido por responsabilidad en `theme`, `foundation`, `shell`, `controls` y `panels`; `theme.css` concentra la paleta y todos los parámetros ajustables del efecto glass. Cada control principal conserva su componente independiente: `volume`, `now-playing`, `audio-apps`, `brightness` y `output-routing`. `app.js` mantiene la conexión SSE, distribuye estados y coordina únicamente las acciones generales.

Los componentes no realizan sondeo mientras `EventSource` está disponible. Los cambios de wallpaper se detectan observando los enlaces `wall.set` y `wall.thmb` de la caché de HyDE; por SSE solo viaja la revisión y la miniatura se descarga desde un endpoint versionado. Si el navegador no soporta SSE, `app.js` activa la actualización periódica de respaldo.

## Desarrollo

```bash
uv sync
uv run uvicorn main:app --host 127.0.0.1 --port 8765 --reload
```

Abrir `http://127.0.0.1:8765` o la IP de Tailscale del equipo cuando Uvicorn escuche en esa interfaz.

Para inspeccionar el canal de eventos:

```bash
curl -N http://127.0.0.1:8765/api/events
```

Para ejecutar las pruebas de regresión:

```bash
uv run python -m unittest discover -s tests -v
```

## Cliente de escritorio para Arch Linux

El cliente de escritorio usa GTK 4 y WebKitGTK 6 para abrir la misma interfaz
servida por FastAPI en `http://127.0.0.1:8765/`. No inicia otro backend. La
aplicación usa el identificador `io.github.ab2348.RemoteC`, por lo que una
segunda ejecución activa la ventana existente.

Instalar las dependencias del sistema:

```bash
sudo pacman -S --needed gtk4 webkitgtk-6.0 python-gobject
```

Instalar el cliente, su entrada de aplicaciones y el módulo de Waybar sin
modificar todavía el layout activo:

```bash
./deploy/install-desktop-client.sh
```

Probarlo desde una terminal o desde el lanzador de aplicaciones:

```bash
remote-c-client
```

Cuando la ventana funcione correctamente, integrar el módulo en el layout
`carlos-clean`:

```bash
./deploy/install-desktop-client.sh --integrate-waybar
```

El instalador también crea
`~/.config/hypr/userprefs.d/remote-c-client-persistent-size.conf`. La regla
hace que Remote C se abra como ventana flotante y que Hyprland recuerde el
último tamaño utilizado. En la primera apertura se usa el tamaño inicial de
480×780 definido por el cliente; después puede redimensionarse normalmente.

El configurador respalda `config.jsonc`, `layouts/carlos-clean.jsonc` y
`user-style.css` antes de modificarlos. Para retirar también la integración de
Waybar:

```bash
./deploy/uninstall-desktop-client.sh --integrate-waybar
```

La URL puede sustituirse para una prueba mediante `REMOTE_C_URL`. Los extras de
desarrollo de WebKit se habilitan únicamente con `REMOTE_C_DEBUG=1`.
