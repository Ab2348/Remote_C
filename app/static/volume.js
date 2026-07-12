(() => {
  const panel = document.querySelector(".volume-panel");
  const slider = document.querySelector("#volume-slider");
  const valueOutput = document.querySelector("#volume-value");
  const muteButton = document.querySelector("#mute-button");

  if (!panel || !slider || !valueOutput || !muteButton) {
    return;
  }

  let volumeInteracting = false;
  let requestInFlight = false;
  let ignoreNextReadoutMutation = false;
  let lastConfirmedVolume = null;
  let pendingRenderedVolume = null;

  function normalizePercentage(value) {
    const percentage = Number(value);

    if (!Number.isFinite(percentage)) {
      return 0;
    }

    return Math.min(100, Math.max(0, Math.round(percentage)));
  }

  function parseRenderedVolume() {
    const match = valueOutput.textContent.match(/-?\d+(?:\.\d+)?/);

    if (match === null) {
      return null;
    }

    return normalizePercentage(match[0]);
  }

  function renderSlider(value) {
    const percentage = normalizePercentage(value);
    slider.value = String(percentage);
    slider.style.setProperty("--range-progress", `${percentage}%`);
    slider.setAttribute("aria-valuetext", `${percentage}%`);
  }

  function renderReadout(value) {
    const percentage = normalizePercentage(value);
    ignoreNextReadoutMutation = true;
    valueOutput.value = `${percentage}%`;
    valueOutput.textContent = `${percentage}%`;
  }

  function renderLocalVolume(value) {
    renderSlider(value);
    renderReadout(value);
  }

  function applyConfirmedVolume(value) {
    const percentage = normalizePercentage(value);
    lastConfirmedVolume = percentage;
    pendingRenderedVolume = null;
    renderLocalVolume(percentage);
  }

  function syncVolumeFromRenderedState() {
    if (ignoreNextReadoutMutation) {
      ignoreNextReadoutMutation = false;
      return;
    }

    const renderedVolume = parseRenderedVolume();

    if (renderedVolume === null) {
      return;
    }

    if (volumeInteracting || requestInFlight) {
      pendingRenderedVolume = renderedVolume;
      return;
    }

    lastConfirmedVolume = renderedVolume;
    renderSlider(renderedVolume);
  }

  function applyMuteState(muted) {
    const label = muted ? "Activar sonido" : "Silenciar";
    muteButton.setAttribute("aria-pressed", String(muted));
    muteButton.setAttribute("aria-label", label);
    muteButton.title = label;
    panel.classList.toggle("is-muted", muted);
  }

  function syncMuteFromRenderedState() {
    const label = muteButton.textContent.trim().toLocaleLowerCase("es");
    applyMuteState(label.startsWith("activar"));
  }

  function restoreLatestVolume() {
    const value = pendingRenderedVolume ?? lastConfirmedVolume;
    pendingRenderedVolume = null;

    if (value !== null) {
      applyConfirmedVolume(value);
    }
  }

  async function setVolume(value) {
    if (requestInFlight) {
      return;
    }

    const requestedVolume = normalizePercentage(value);
    requestInFlight = true;
    pendingRenderedVolume = null;
    slider.disabled = true;
    panel.classList.add("is-busy");

    try {
      const response = await fetch("/api/volume/set", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ volume: requestedVolume }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const state = await response.json();
      applyConfirmedVolume(state.volume);
      applyMuteState(Boolean(state.muted));
      navigator.vibrate?.(20);
    } catch (error) {
      console.error("No se pudo establecer el volumen", error);
      restoreLatestVolume();
    } finally {
      requestInFlight = false;
      slider.disabled = false;
      panel.classList.remove("is-busy");
    }
  }

  function commitSliderValue() {
    if (!volumeInteracting || requestInFlight) {
      return;
    }

    volumeInteracting = false;
    setVolume(slider.value);
  }

  const stateObserver = new MutationObserver(() => {
    syncVolumeFromRenderedState();
    syncMuteFromRenderedState();
  });

  stateObserver.observe(valueOutput, {
    childList: true,
    characterData: true,
    subtree: true,
  });
  stateObserver.observe(muteButton, {
    childList: true,
    characterData: true,
    subtree: true,
  });

  slider.addEventListener("pointerdown", () => {
    volumeInteracting = true;
    pendingRenderedVolume = null;
  });

  slider.addEventListener("input", () => {
    volumeInteracting = true;
    renderLocalVolume(slider.value);
  });

  slider.addEventListener("change", commitSliderValue);

  slider.addEventListener("blur", () => {
    if (volumeInteracting) {
      commitSliderValue();
    }
  });

  slider.addEventListener("pointercancel", () => {
    volumeInteracting = false;
    restoreLatestVolume();
  });

  syncVolumeFromRenderedState();
  syncMuteFromRenderedState();
})();
