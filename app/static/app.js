const connection = document.querySelector("#connection");
const volumeValue = document.querySelector("#volume-value");
const muteButton = document.querySelector("#mute-button");
const track = document.querySelector("#track");
const playbackState = document.querySelector("#playback-state");
const playButton = document.querySelector("#play-button");
const brightnessValues = document.querySelector("#brightness-values");
const actionButtons = [...document.querySelectorAll("button[data-endpoint]")];
const audioRoutingStatus = document.querySelector("#audio-routing-status");
const audioOutput = document.querySelector("#audio-output");
const setDefaultOutputButton = document.querySelector("#set-default-output");
const forceOutputButton = document.querySelector("#force-output");
const audioStreams = document.querySelector("#audio-streams");
const audioRoutingButtons = [setDefaultOutputButton, forceOutputButton];

const playbackLabels = {
  playing: "Reproduciendo",
  paused: "Pausado",
  stopped: "Detenido",
};

let audioRoutingState = {
  outputs: [],
  streams: [],
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

function setAudioRoutingBusy(busy) {
  const disabled = busy || audioRoutingState.outputs.length === 0;

  audioOutput.disabled = disabled;
  audioRoutingButtons.forEach((button) => { button.disabled = disabled; });
  audioStreams
    .querySelectorAll("select, button, input")
    .forEach((control) => { control.disabled = disabled; });
}

function renderOutputOptions(selectedName) {
  audioOutput.replaceChildren();

  audioRoutingState.outputs.forEach((output) => {
    const option = document.createElement("option");
    option.value = output.name;
    option.textContent = output.active ? `${output.label} (activa)` : output.label;
    audioOutput.append(option);
  });

  const names = audioRoutingState.outputs.map((output) => output.name);
  const activeOutput = audioRoutingState.outputs.find((output) => output.active);

  if (selectedName && names.includes(selectedName)) {
    audioOutput.value = selectedName;
  } else if (activeOutput) {
    audioOutput.value = activeOutput.name;
  }
}

function renderStream(stream) {
  const item = document.createElement("article");
  item.className = "stream";

  const content = document.createElement("div");

  const title = document.createElement("h3");
  title.textContent = stream.application;

  const description = document.createElement("p");
  description.textContent = `${stream.media} · ${stream.output_label}`;

  content.append(title, description);

  const controls = document.createElement("div");
  controls.className = "stream-controls";

  const volumeControl = document.createElement("label");
  volumeControl.className = "stream-volume";

  const volumeHeading = document.createElement("span");
  volumeHeading.textContent = "Volumen";

  const volumeValue = document.createElement("output");
  volumeValue.value = `${stream.volume}%`;
  volumeValue.textContent = `${stream.volume}%`;

  const volumeLabel = document.createElement("span");
  volumeLabel.className = "stream-volume-label";
  volumeLabel.append(volumeHeading, volumeValue);

  const volume = document.createElement("input");
  volume.type = "range";
  volume.min = "0";
  volume.max = "100";
  volume.step = "1";
  volume.value = String(stream.volume);
  volume.setAttribute("aria-label", `Volumen de ${stream.application}`);
  volume.addEventListener("input", () => {
    volumeValue.value = `${volume.value}%`;
    volumeValue.textContent = `${volume.value}%`;
  });
  volume.addEventListener("change", () => {
    setStreamVolume(stream.index, Number(volume.value));
  });

  volumeControl.append(volumeLabel, volume);

  const muteButton = document.createElement("button");
  muteButton.type = "button";
  muteButton.className = "stream-mute";
  muteButton.textContent = stream.muted ? "Activar sonido" : "Silenciar";
  muteButton.setAttribute("aria-pressed", String(stream.muted));
  muteButton.addEventListener("click", () => {
    toggleStreamMute(stream.index);
  });

  const routingControls = document.createElement("div");
  routingControls.className = "stream-routing";

  const select = document.createElement("select");
  select.setAttribute("aria-label", `Salida para ${stream.application}`);

  audioRoutingState.outputs.forEach((output) => {
    const option = document.createElement("option");
    option.value = output.name;
    option.textContent = output.label;
    select.append(option);
  });

  if (stream.output_name) {
    select.value = stream.output_name;
  }

  const button = document.createElement("button");
  button.type = "button";
  button.textContent = "Mover";
  button.addEventListener("click", () => {
    moveStream(stream.index, select.value);
  });

  routingControls.append(select, button);
  controls.append(volumeControl, muteButton, routingControls);
  item.append(content, controls);

  return item;
}

function renderAudioRouting(state) {
  const selectedName = audioOutput.value;

  audioRoutingState = state;
  renderOutputOptions(selectedName);
  audioStreams.replaceChildren();

  if (state.outputs.length === 0) {
    audioRoutingStatus.textContent = "Sin salidas disponibles";
  } else if (state.streams.length === 0) {
    audioRoutingStatus.textContent = `${state.outputs.length} salidas · sin flujos activos`;
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "No hay aplicaciones reproduciendo audio.";
    audioStreams.append(empty);
  } else {
    audioRoutingStatus.textContent = `${state.outputs.length} salidas · ${state.streams.length} flujos activos`;
    state.streams.forEach((stream) => {
      audioStreams.append(renderStream(stream));
    });
  }

  setAudioRoutingBusy(false);
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

async function requestAudioRouting() {
  try {
    const response = await fetch("/api/audio-routing", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    renderAudioRouting(await response.json());
  } catch (error) {
    console.error("No se pudo obtener el ruteo de audio", error);
    audioRoutingStatus.textContent = "Audio no disponible";
    audioStreams.replaceChildren();
    audioRoutingState = { outputs: [], streams: [] };
    setAudioRoutingBusy(false);
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

async function sendAudioRoutingAction(path, body) {
  setAudioRoutingBusy(true);

  try {
    const response = await fetch(`/api/audio-routing/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    renderAudioRouting(await response.json());
    navigator.vibrate?.(20);
  } catch (error) {
    console.error("No se pudo cambiar el ruteo de audio", error);
    audioRoutingStatus.textContent = "No se pudo aplicar el cambio";
    await requestAudioRouting();
  } finally {
    setAudioRoutingBusy(false);
  }
}

function selectedAudioOutput() {
  return audioOutput.value;
}

function moveStream(streamIndex, outputName) {
  return sendAudioRoutingAction("stream", {
    stream_index: streamIndex,
    name: outputName,
  });
}

function setStreamVolume(streamIndex, volume) {
  return sendAudioRoutingAction("stream/volume", {
    stream_index: streamIndex,
    volume,
  });
}

function toggleStreamMute(streamIndex) {
  return sendAudioRoutingAction("stream/mute", {
    stream_index: streamIndex,
  });
}

actionButtons.forEach((button) => {
  button.addEventListener("click", () => sendAction(button));
});

setDefaultOutputButton.addEventListener("click", () => {
  sendAudioRoutingAction("default", { name: selectedAudioOutput() });
});

forceOutputButton.addEventListener("click", () => {
  sendAudioRoutingAction("force", { name: selectedAudioOutput() });
});

requestState();
requestAudioRouting();
window.setInterval(requestState, 3000);
window.setInterval(requestAudioRouting, 5000);

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((error) => {
      console.error("No se pudo registrar la PWA", error);
    });
  });
}
