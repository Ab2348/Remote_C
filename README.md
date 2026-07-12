# Remote C

Control remoto local para Arch Linux, accesible desde la red privada de Tailscale.

## Estado en tiempo real

La interfaz mantiene una sola conexión SSE con `GET /api/events`. El servidor publica cambios detectados por `pactl subscribe` y `playerctl --follow`; los endpoints de control también publican su resultado inmediatamente.

DDC/CI no ofrece una fuente de eventos. Mientras haya al menos un cliente conectado, el servidor comprueba el brillo cada 30 segundos y solo publica si cambió. Los cambios realizados mediante `POST /api/brightness` se publican de inmediato.

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
