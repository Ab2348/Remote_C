const connection = document.querySelector("#connection");
const volumeValue = document.querySelector("#volume-value");
const muteButton = document.querySelector("#mute-button");
const track = document.querySelector("#track");
const playbackState = document.querySelector("#playback-state");
const playButton = document.querySelector("#play-button");
const brightnessValues = document.querySelector("#brightness-values");
const actionButtons = [...document.querySelectorAll("button[data-endpoint]")];

const playbackLabels = {
  playing: "Reproduciendo",
  paused: "Pausado",
  stopped: "Detenido",
};

function setConnection(online) {
  connection.textContent = online ? "Conectado" : "Sin conexión";
  connection.classList.toggle("online", online);
}

function render(state) {
  volumeValue.textContent = `${state.volume}%`;
  muteButton.textContent = state.muted ? "Activar sonido" : "Silenciar";
  track.textContent = state.current_track;
  playbackState.textContent =
    playbackLabels[state.playback_status] ?? "Detenido";
  playButton.textContent = state.playing ? "Pausar" : "Reproducir";

  const display1 = state.brightness.display_1;
  const display2 = state.brightness.display_2;
  brightnessValues.textContent = `Monitor 1: ${display1}% · Monitor 2: ${display2}%`;
}

async function requestState() {
  try {
    const response = await fetch("/api/state", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    render(await response.json());
    setConnection(true);
  } catch (error) {
    console.error("No se pudo obtener el estado", error);
    setConnection(false);
  }
}

async function sendAction(button) {
  const { endpoint, action } = button.dataset;
  actionButtons.forEach((item) => { item.disabled = true; });

  try {
    const response = await fetch(`/api/${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    render(await response.json());
    setConnection(true);
    navigator.vibrate?.(20);
  } catch (error) {
    console.error("No se pudo ejecutar la acción", error);
    setConnection(false);
  } finally {
    actionButtons.forEach((item) => { item.disabled = false; });
  }
}

actionButtons.forEach((button) => {
  button.addEventListener("click", () => sendAction(button));
});

requestState();
window.setInterval(requestState, 3000);

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((error) => {
      console.error("No se pudo registrar la PWA", error);
    });
  });
}
