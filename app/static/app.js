const connection = document.querySelector("#connection");
const mediaSessionsStatus = document.querySelector("#media-sessions-status");
const mediaSessions = document.querySelector("#media-sessions");
const actionButtons = [...document.querySelectorAll("button[data-endpoint]")];

const playbackLabels = {
  playing: "Reproduciendo",
  paused: "Pausado",
  stopped: "Detenido",
};

let mediaSessionsBusy = false;
let stateRequestInFlight = false;
let systemState = null;
let eventSource = null;

function setConnection(online) {
  connection.textContent = online ? "Conectado" : "Sin conexión";
  connection.classList.toggle("online", online);
}

function render(state) {
  systemState = state;

  if (!mediaSessionsBusy) {
    renderMediaSessions(
      Array.isArray(state.media_sessions) ? state.media_sessions : [],
    );
  }

  document.dispatchEvent(new CustomEvent("remote-c:state", {
    detail: state,
  }));
}

function setMediaSessionsBusy(busy) {
  mediaSessionsBusy = busy;
  mediaSessions
    .querySelectorAll("button")
    .forEach((button) => { button.disabled = busy; });
}

function renderMediaSession(player) {
  const item = document.createElement("article");
  item.className = "media-session";

  const heading = document.createElement("div");
  heading.className = "media-session-heading";

  const content = document.createElement("div");
  const title = document.createElement("h3");
  title.textContent = player.label;

  const track = document.createElement("p");
  track.textContent = player.current_track || "Sin reproducción";
  content.append(title, track);

  const status = document.createElement("span");
  status.className = "media-session-status";
  status.textContent =
    playbackLabels[player.status] ?? "Detenido";

  heading.append(content, status);

  const controls = document.createElement("div");
  controls.className = "media-session-controls";

  const actions = [];

  if (player.can_previous) {
    actions.push(["previous", "Anterior"]);
  }

  if (player.can_seek) {
    actions.push(["seek_backward", "−10 s"]);
  }

  if (player.can_play_pause) {
    actions.push([
      "play_pause",
      player.playing ? "Pausar" : "Reproducir",
    ]);
  }

  if (player.can_seek) {
    actions.push(["seek_forward", "+10 s"]);
  }

  if (player.can_next) {
    actions.push(["next", "Siguiente"]);
  }

  actions.forEach(([action, label]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.addEventListener("click", () => {
      sendMediaSessionAction(player.name, action);
    });
    controls.append(button);
  });

  item.append(heading);

  if (actions.length > 0) {
    item.append(controls);
  }

  return item;
}

function renderMediaSessions(players) {
  mediaSessions.replaceChildren();

  if (players.length === 0) {
    mediaSessionsStatus.textContent = "Sin reproductores disponibles";
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "No hay sesiones multimedia activas.";
    mediaSessions.append(empty);
  } else {
    mediaSessionsStatus.textContent =
      `${players.length} ${players.length === 1 ? "sesión" : "sesiones"} activas`;

    players.forEach((player) => {
      mediaSessions.append(renderMediaSession(player));
    });
  }

  setMediaSessionsBusy(false);
}

function renderAudioRouting(state) {
  document.dispatchEvent(new CustomEvent("remote-c:audio-routing", {
    detail: state,
  }));
}

function applyStatePatch(patch) {
  if (systemState === null) {
    requestState();
    return;
  }

  render({ ...systemState, ...patch });
}

function parseEvent(event, label) {
  try {
    return JSON.parse(event.data);
  } catch (error) {
    console.error(`Evento inválido: ${label}`, error);
    return null;
  }
}

function connectEvents() {
  eventSource?.close();
  eventSource = new EventSource("/api/events");

  eventSource.addEventListener("snapshot", (event) => {
    const snapshot = parseEvent(event, "snapshot");
    if (snapshot === null) return;

    render(snapshot.state);

    renderAudioRouting(snapshot.audio_routing);

    setConnection(true);
  });

  ["volume", "media", "brightness"].forEach((eventType) => {
    eventSource.addEventListener(eventType, (event) => {
      const patch = parseEvent(event, eventType);
      if (patch !== null) {
        applyStatePatch(patch);
        setConnection(true);
      }
    });
  });

  eventSource.addEventListener("audio-routing", (event) => {
    const state = parseEvent(event, "audio-routing");
    if (state === null) return;

    renderAudioRouting(state);

    setConnection(true);
  });

  eventSource.addEventListener("server-error", (event) => {
    const error = parseEvent(event, "server-error");
    console.error("El servidor no pudo preparar el estado", error);
    setConnection(false);
  });

  eventSource.onopen = () => {
    setConnection(true);
  };

  eventSource.onerror = () => {
    setConnection(false);
  };
}

async function requestState() {
  if (stateRequestInFlight) {
    return;
  }

  stateRequestInFlight = true;

  try {
    const response = await fetch("/api/state", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    render(await response.json());
    setConnection(true);
  } catch (error) {
    console.error("No se pudo obtener el estado", error);
    setConnection(false);
  } finally {
    stateRequestInFlight = false;
  }
}

async function requestAudioRouting() {
  try {
    const response = await fetch("/api/audio-routing", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    renderAudioRouting(await response.json());
  } catch (error) {
    console.error("No se pudo obtener el ruteo de audio", error);
    document.dispatchEvent(new CustomEvent("remote-c:audio-routing-error"));
  }
}

async function sendMediaSessionAction(player, action) {
  setMediaSessionsBusy(true);

  try {
    const response = await fetch("/api/media/sessions/control", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ player, action }),
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const state = await response.json();
    mediaSessionsBusy = false;
    renderMediaSessions(
      Array.isArray(state.players) ? state.players : [],
    );
    navigator.vibrate?.(20);
  } catch (error) {
    console.warn(
      "La capacidad del reproductor cambió; actualizando estado",
      error,
    );
    mediaSessionsBusy = false;
    await requestState();
  } finally {
    setMediaSessionsBusy(false);
  }
}

async function sendAction(button) {
  const { endpoint, action } = button.dataset;
  const disabledStates = actionButtons.map((item) => item.disabled);
  actionButtons.forEach((item) => { item.disabled = true; });

  try {
    const response = await fetch(`/api/${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    applyStatePatch(await response.json());
    setConnection(true);
    navigator.vibrate?.(20);
  } catch (error) {
    console.error("No se pudo ejecutar la acción", error);
    setConnection(false);
  } finally {
    actionButtons.forEach((item, index) => {
      item.disabled = disabledStates[index];
    });
  }
}

actionButtons.forEach((button) => {
  button.addEventListener("click", () => sendAction(button));
});

document.addEventListener("remote-c:audio-routing-update", (event) => {
  renderAudioRouting(event.detail);
});

document.addEventListener("remote-c:brightness-update", (event) => {
  applyStatePatch(event.detail);
});

if ("EventSource" in window) {
  connectEvents();
} else {
  requestState();
  requestAudioRouting();
  window.setInterval(requestState, 10000);
  window.setInterval(requestAudioRouting, 10000);
}

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((error) => {
      console.error("No se pudo registrar la PWA", error);
    });
  });
}
