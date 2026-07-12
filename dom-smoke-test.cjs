const fs = require("node:fs");
const { JSDOM } = require("jsdom");

const html = fs.readFileSync("app/static/index.html", "utf8");
const dom = new JSDOM(html, {
  url: "http://127.0.0.1:8765/",
  runScripts: "outside-only",
});
const { window } = dom;

class EventSourceStub {
  constructor() {
    this.listeners = new Map();
    EventSourceStub.instance = this;
  }

  addEventListener(type, callback) {
    this.listeners.set(type, callback);
  }

  close() {}

  emit(type, payload) {
    this.listeners.get(type)?.({ data: JSON.stringify(payload) });
  }
}

window.EventSource = EventSourceStub;
window.fetch = async () => { throw new Error("fetch inesperado"); };
window.navigator.vibrate = () => true;
window.CSS = { escape: (value) => value };

for (const script of [
  "feedback.js",
  "volume.js",
  "now-playing.js",
  "audio-apps.js",
  "brightness.js",
  "output-routing.js",
  "app.js",
]) {
  window.eval(fs.readFileSync(`app/static/${script}`, "utf8"));
}

EventSourceStub.instance.emit("snapshot", {
  state: {
    volume: 37,
    muted: false,
    playing: true,
    playback_status: "playing",
    current_track: "Canción — Artista",
    media_sessions: [
      {
        name: "brave.instance7003",
        label: "Brave",
        playing: true,
        artist: "Artista",
        status: "playing",
        current_track: "Canción — Artista",
        artwork_id: "cover123",
        can_play_pause: true,
        can_previous: true,
        can_next: true,
        can_seek: true,
      },
      {
        name: "spotify",
        label: "Spotify",
        playing: false,
        artist: "",
        status: "paused",
        current_track: "Otra canción",
        artwork_id: null,
        can_play_pause: true,
        can_previous: true,
        can_next: true,
        can_seek: true,
      },
    ],
    brightness: { display_1: 70, display_2: 60 },
    brightness_displays: [
      { key: "display_1", label: "LG UltraGear", brightness: 70 },
      { key: "display_2", label: "GA271", brightness: 60 },
    ],
  },
  audio_routing: {
    outputs: [
      {
        name: "razer",
        label: "Razer Barracuda X",
        state: "running",
        active: true,
      },
      {
        name: "huawei",
        label: "HUAWEI Sound Joy",
        state: "suspended",
        active: false,
      },
    ],
    applications: [{
      id: "brave",
      application: "Brave",
      binary: "brave",
      icon_name: "brave-browser",
      pids: ["7003"],
      media: ["YouTube", "Spotify web"],
      stream_indexes: [94, 294],
      stream_count: 2,
      volume: 50,
      mixed_volume: true,
      muted: false,
      partially_muted: true,
      playing: true,
      playback_status: "playing",
      output_name: "razer",
      output_label: "Razer Barracuda X",
    }],
  },
});

const text = (selector) => window.document.querySelector(selector).textContent;
if (text("#volume-display") !== "37%") throw new Error("volumen no renderizado");
if (text("#track-title") !== "Canción") throw new Error("título no renderizado");
if (text("#track-artist") !== "Artista") throw new Error("artista no renderizado");
if (text("#track-source") !== "Brave") throw new Error("fuente no renderizada");
if (!window.document.querySelector("#track-artwork").src.includes("player=brave.instance7003")) {
  throw new Error("miniatura multimedia no solicitada");
}
if (!window.document.querySelector("#now-playing-indicator").classList.contains("is-playing")) {
  throw new Error("indicador de reproducción no animado");
}
window.document.querySelector("#track-artwork").onerror();
if (window.document.querySelector("#cover-placeholder").hidden) {
  throw new Error("fallback de miniatura no restaurado");
}
if (window.document.querySelectorAll(".brightness-display").length !== 2) {
  throw new Error("monitores no renderizados");
}
if (text(".brightness-display-value") !== "70%") {
  throw new Error("brillo individual no renderizado");
}
if (window.document.querySelector("#media-sessions") !== null) {
  throw new Error("sección multimedia redundante todavía presente");
}
if (window.document.querySelectorAll(".audio-application").length !== 2) {
  throw new Error("aplicaciones y sesiones no unificadas");
}
if (text(".audio-application-copy h3") !== "Brave") {
  throw new Error("nombre de aplicación no renderizado");
}
if (window.document.querySelector(".audio-application-details").hidden) {
  throw new Error("aplicación activa no expandida");
}
if (text(".audio-application-volume output") !== "≈50%") {
  throw new Error("volumen mixto no renderizado");
}
if (!window.document.querySelector(".audio-application-mute svg")) {
  throw new Error("el silencio de aplicación no usa un icono SVG");
}
if (/[🔇🔊]/u.test(text(".audio-application-mute"))) {
  throw new Error("el control de silencio todavía usa emojis");
}
const braveIcon = window.document.querySelector(".audio-application-icon img");
if (!braveIcon?.src.endsWith("/api/audio-routing/application-icon/brave-browser")) {
  throw new Error("icono instalado de aplicación no solicitado");
}
if (text(".audio-application-icon-fallback") !== "B") {
  throw new Error("fallback de icono no disponible");
}
const spotifyCard = [...window.document.querySelectorAll(".audio-application")]
  .find((card) => card.querySelector("h3").textContent === "Spotify");
if (!spotifyCard?.querySelector(".audio-application-details").hidden) {
  throw new Error("sesión pausada no quedó contraída");
}
if (spotifyCard.querySelectorAll(".audio-application-media-controls button").length !== 3) {
  throw new Error("controles multimedia no disponibles al contraer");
}
if (!window.document.querySelector(".audio-application-output")) {
  throw new Error("selector colapsable de salida no renderizado");
}
window.document.querySelector(".audio-application-toggle").click();
EventSourceStub.instance.emit("media", {
  playing: true,
  playback_status: "playing",
  current_track: "Canción — Artista",
  media_sessions: [{
    name: "brave.instance7003",
    label: "Brave",
    playing: true,
    artist: "Artista",
    status: "playing",
    current_track: "Canción — Artista",
    artwork_id: "cover123",
    can_play_pause: true,
    can_previous: true,
    can_next: true,
    can_seek: true,
  }],
});
if (!window.document.querySelector(".audio-application-details").hidden) {
  throw new Error("estado contraído no persistió tras SSE");
}
EventSourceStub.instance.emit("media", {
  playing: false,
  playback_status: "paused",
  current_track: "Sin reproducción",
  media_sessions: [{
    name: "brave.instance7003",
    label: "Brave",
    playing: false,
    artist: "Artista",
    status: "paused",
    current_track: "Canción — Artista",
    artwork_id: "cover123",
    can_play_pause: true,
    can_previous: true,
    can_next: true,
    can_seek: true,
  }],
});
if (window.document.querySelector("#play-button").disabled) {
  throw new Error("reproducir ahora no permite reanudar la sesión pausada");
}
if (text("#track-title") !== "Canción") {
  throw new Error("reproduciendo ahora olvidó la sesión pausada");
}
if (window.document.querySelectorAll(".output-device").length !== 2) {
  throw new Error("salida predeterminada no renderizada");
}
if (text(".output-device-marker") !== "Predeterminada") {
  throw new Error("salida activa no identificada");
}
window.document.querySelector('[data-output-name="razer"]').dispatchEvent(
  new window.KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }),
);
if (window.document.querySelector('[data-output-name="huawei"]').getAttribute("aria-checked") !== "true") {
  throw new Error("navegación de salidas por teclado no funciona");
}
window.remoteCNotify("Listo", "success", 0);
if (!window.document.querySelector("#global-feedback").classList.contains("is-visible")) {
  throw new Error("feedback global no mostrado");
}

console.log("dom snapshot integration: ok");
