const connection = document.querySelector("#connection");
const actionButtons = [...document.querySelectorAll("button[data-endpoint]")];
let stateRequestInFlight = false;
let systemState = null;
let eventSource = null;

function setConnection(online) {
  connection.textContent = online ? "Conectado" : "Sin conexión";
  connection.classList.toggle("online", online);
}

function render(state) {
  systemState = state;

  document.dispatchEvent(new CustomEvent("remote-c:state", {
    detail: state,
  }));
}

function renderAudioRouting(state) {
  document.dispatchEvent(new CustomEvent("remote-c:audio-routing", {
    detail: state,
  }));
}

function renderWallpaper(state) {
  document.dispatchEvent(new CustomEvent("remote-c:wallpaper", {
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
    renderWallpaper(snapshot.wallpaper);

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

  eventSource.addEventListener("wallpaper", (event) => {
    const state = parseEvent(event, "wallpaper");
    if (state === null) return;

    renderWallpaper(state);
    setConnection(true);
  });

  eventSource.addEventListener("server-error", (event) => {
    const error = parseEvent(event, "server-error");
    console.error("El servidor no pudo preparar el estado", error);
    window.remoteCNotify?.("El servidor no pudo preparar el estado.", "error");
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
  let serverReached = false;

  try {
    const response = await fetch("/api/state", { cache: "no-store" });
    serverReached = true;
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    render(await response.json());
    setConnection(true);
  } catch (error) {
    console.error("No se pudo obtener el estado", error);
    if (!serverReached) setConnection(false);
    window.remoteCNotify?.(
      serverReached
        ? "Remote C respondió, pero no pudo preparar el estado."
        : "No se pudo conectar con Remote C.",
      "error",
    );
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
    window.remoteCNotify?.("No se pudo obtener el estado de audio.", "error");
  }
}

async function requestWallpaper() {
  try {
    const response = await fetch("/api/wallpaper", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    renderWallpaper(await response.json());
  } catch (error) {
    console.error("No se pudo obtener el wallpaper", error);
    renderWallpaper({ available: false, revision: null, url: null });
  }
}

async function sendAction(button) {
  const { endpoint, action } = button.dataset;
  const panel = button.closest(".panel");
  const disabledStates = actionButtons.map((item) => item.disabled);
  let serverReached = false;
  actionButtons.forEach((item) => { item.disabled = true; });
  panel?.setAttribute("aria-busy", "true");

  try {
    const response = await fetch(`/api/${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });
    serverReached = true;

    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    applyStatePatch(await response.json());
    setConnection(true);
    navigator.vibrate?.(20);
  } catch (error) {
    console.error("No se pudo ejecutar la acción", error);
    if (!serverReached) setConnection(false);
    window.remoteCNotify?.("No se pudo ejecutar la acción.", "error");
  } finally {
    panel?.setAttribute("aria-busy", "false");
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
  requestWallpaper();
  window.setInterval(requestState, 10000);
  window.setInterval(requestAudioRouting, 10000);
  window.setInterval(requestWallpaper, 10000);
}

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    const hadController = Boolean(navigator.serviceWorker.controller);
    let reloading = false;

    navigator.serviceWorker.addEventListener("controllerchange", () => {
      if (!hadController || reloading) return;
      reloading = true;
      window.location.reload();
    });

    navigator.serviceWorker.register("/sw.js")
      .then((registration) => registration.update())
      .catch((error) => {
        console.error("No se pudo registrar la PWA", error);
      });
  });
}
