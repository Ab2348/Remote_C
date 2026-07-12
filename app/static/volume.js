(() => {
  const panel = document.querySelector(".volume-panel");
  const slider = document.querySelector("#volume-slider");
  const stateOutput = document.querySelector("#volume-value");
  const displayOutput = document.querySelector("#volume-display");
  const muteButton = document.querySelector("#mute-button");
  const volumeButtons = [
    ...document.querySelectorAll('button[data-endpoint="volume"]'),
  ];

  if (!panel || !slider || !stateOutput || !displayOutput || !muteButton) {
    return;
  }

  let volumeInteracting = false;
  let requestInFlight = false;
  let activeRequestedVolume = null;
  let queuedVolume = null;
  let commitTimer = null;
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
    const match = stateOutput.textContent.match(/-?\d+(?:\.\d+)?/);

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
    displayOutput.value = `${percentage}%`;
    displayOutput.textContent = `${percentage}%`;
  }

  function renderLocalVolume(value) {
    renderSlider(value);
    renderReadout(value);
  }

  function applyMuteState(muted) {
    const label = muted ? "Activar sonido" : "Silenciar";
    muteButton.setAttribute("aria-pressed", String(muted));
    muteButton.setAttribute("aria-label", label);
    muteButton.title = label;
    panel.classList.toggle("is-muted", muted);
  }

  function applyConfirmedState(state, { forceRender = false } = {}) {
    const percentage = normalizePercentage(state.volume);
    lastConfirmedVolume = percentage;
    pendingRenderedVolume = null;
    applyMuteState(Boolean(state.muted));

    if (
      forceRender
      || (!volumeInteracting && queuedVolume === null)
    ) {
      renderLocalVolume(percentage);
    }
  }

  function syncVolumeFromRenderedState() {
    const renderedVolume = parseRenderedVolume();

    if (renderedVolume === null) {
      return;
    }

    if (volumeInteracting || requestInFlight) {
      pendingRenderedVolume = renderedVolume;
      return;
    }

    lastConfirmedVolume = renderedVolume;
    renderLocalVolume(renderedVolume);
  }

  function syncMuteFromRenderedState() {
    const label = muteButton.textContent.trim().toLocaleLowerCase("es");
    applyMuteState(label.startsWith("activar"));
  }

  function setBusy(busy) {
    panel.classList.toggle("is-busy", busy);
    volumeButtons.forEach((button) => {
      button.disabled = busy;
    });
  }

  async function postVolume(path, body) {
    const response = await fetch(`/api/volume/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return response.json();
  }

  function restoreLatestVolume() {
    const value = pendingRenderedVolume ?? lastConfirmedVolume;
    pendingRenderedVolume = null;

    if (value !== null) {
      renderLocalVolume(value);
    }
  }

  async function sendControl(action) {
    if (requestInFlight) {
      return;
    }

    requestInFlight = true;
    setBusy(true);

    try {
      const state = await postVolume("control", { action });
      applyConfirmedState(state, { forceRender: true });
      navigator.vibrate?.(20);
    } catch (error) {
      console.error("No se pudo cambiar el volumen", error);
      restoreLatestVolume();
    } finally {
      requestInFlight = false;
      setBusy(false);
    }
  }

  async function sendSetVolume(value) {
    const requestedVolume = normalizePercentage(value);

    if (requestInFlight) {
      if (requestedVolume !== activeRequestedVolume) {
        queuedVolume = requestedVolume;
      }
      return;
    }

    if (
      requestedVolume === lastConfirmedVolume
      && pendingRenderedVolume === null
    ) {
      if (!volumeInteracting) {
        renderLocalVolume(requestedVolume);
      }
      return;
    }

    requestInFlight = true;
    activeRequestedVolume = requestedVolume;
    queuedVolume = null;
    panel.classList.add("is-busy");

    try {
      const state = await postVolume("set", { volume: requestedVolume });
      applyConfirmedState(state);
      navigator.vibrate?.(20);
    } catch (error) {
      console.error("No se pudo establecer el volumen", error);
      restoreLatestVolume();
    } finally {
      requestInFlight = false;
      activeRequestedVolume = null;
      panel.classList.remove("is-busy");

      if (queuedVolume !== null) {
        const nextVolume = queuedVolume;
        queuedVolume = null;
        sendSetVolume(nextVolume);
      } else if (!volumeInteracting && pendingRenderedVolume !== null) {
        const pendingVolume = pendingRenderedVolume;
        pendingRenderedVolume = null;
        lastConfirmedVolume = pendingVolume;
        renderLocalVolume(pendingVolume);
      }
    }
  }

  function scheduleSliderCommit() {
    window.clearTimeout(commitTimer);
    commitTimer = window.setTimeout(() => {
      sendSetVolume(slider.value);
    }, 180);
  }

  function finishSliderInteraction() {
    if (!volumeInteracting) {
      return;
    }

    volumeInteracting = false;
    window.clearTimeout(commitTimer);
    sendSetVolume(slider.value);
  }

  volumeButtons.forEach((button) => {
    button.addEventListener(
      "click",
      (event) => {
        event.preventDefault();
        event.stopImmediatePropagation();
        sendControl(button.dataset.action);
      },
      { capture: true },
    );
  });

  const volumeObserver = new MutationObserver(syncVolumeFromRenderedState);
  volumeObserver.observe(stateOutput, {
    childList: true,
    characterData: true,
    subtree: true,
  });

  const muteObserver = new MutationObserver(syncMuteFromRenderedState);
  muteObserver.observe(muteButton, {
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
    scheduleSliderCommit();
  });

  slider.addEventListener("change", finishSliderInteraction);
  slider.addEventListener("pointerup", finishSliderInteraction);
  slider.addEventListener("touchend", finishSliderInteraction, { passive: true });

  slider.addEventListener("blur", () => {
    if (volumeInteracting) {
      finishSliderInteraction();
    }
  });

  slider.addEventListener("pointercancel", () => {
    volumeInteracting = false;
    window.clearTimeout(commitTimer);
    restoreLatestVolume();
  });

  syncVolumeFromRenderedState();
  syncMuteFromRenderedState();
})();
