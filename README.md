# Remote C

Control remoto local para Arch Linux, accesible desde la red privada de Tailscale.

## Funciones

- Volumen general, silencio y reproducción multimedia.
- Control independiente de sesiones y aplicaciones con audio.
- Volumen, silencio y salida por aplicación.
- Brillo conjunto o independiente para los dos monitores DDC/CI.
- Selección de salida predeterminada y movimiento de todos los flujos activos.
- Interfaz PWA móvil con estado actualizado mediante eventos.

## Estado en tiempo real

La interfaz mantiene una sola conexión SSE con `GET /api/events`. El servidor publica cambios detectados por `pactl subscribe` y `playerctl --follow`; los endpoints de control también publican su resultado inmediatamente.

DDC/CI no ofrece una fuente de eventos. Mientras haya al menos un cliente conectado, el servidor comprueba el brillo cada 30 segundos y solo publica si cambió. Los cambios realizados mediante `POST /api/brightness` se publican de inmediato.

## Interfaz

El frontend usa JavaScript y CSS nativos. Cada control principal vive en un componente independiente dentro de `app/static/`: `volume`, `now-playing`, `audio-apps`, `brightness` y `output-routing`. `app.js` conserva la conexión SSE, distribuye estados y coordina únicamente las acciones generales.

Los componentes no realizan sondeo mientras `EventSource` está disponible. Si el navegador no soporta SSE, `app.js` activa la actualización periódica de respaldo.

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
