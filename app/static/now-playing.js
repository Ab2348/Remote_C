(() => {
  const panel = document.querySelector(".now-playing-panel");
  const trackState = document.querySelector("#track");
  const trackTitle = document.querySelector("#track-title");
  const trackArtist = document.querySelector("#track-artist");
  const trackSource = document.querySelector("#track-source");
  const playbackState = document.querySelector("#playback-state");
  const playButton = document.querySelector("#play-button");
  const mediaSessions = document.querySelector("#media-sessions");
  const mediaButtons = [
    ...document.querySelectorAll('button[data-endpoint="media"]'),
  ];

  if (
    !panel
    || !trackState
    || !trackTitle
    || !trackArtist
    || !trackSource
    || !playbackState
    || !playButton
    || !mediaSessions
  ) {
    return;
  }

  let updateQueued = false;

  function splitTrack(value) {
    const normalized = value.trim();
    const separator = normalized.lastIndexOf(" — ");

    if (separator === -1) {
      return {
        title: normalized,
        artist: "",
      };
    }

    return {
      title: normalized.slice(0, separator).trim(),
      artist: normalized.slice(separator + 3).trim(),
    };
  }

  function activeSessionLabel() {
    const sessions = [...mediaSessions.querySelectorAll(".media-session")];

    if (sessions.length === 0) {
      return "";
    }

    const active = sessions.find((session) => {
      const status = session.querySelector(".media-session-status");
      return status?.textContent.trim().toLocaleLowerCase("es") === "reproduciendo";
    }) ?? sessions[0];

    return active.querySelector("h3")?.textContent.trim() ?? "";
  }

  function setButtonAvailability(available) {
    mediaButtons.forEach((button) => {
      if (!available) {
        if (!button.disabled) {
          button.disabled = true;
          button.dataset.nowPlayingDisabled = "true";
        }
        return;
      }

      if (button.dataset.nowPlayingDisabled === "true") {
        button.disabled = false;
        delete button.dataset.nowPlayingDisabled;
      }
    });
  }

  function renderNowPlaying() {
    updateQueued = false;

    const rawTrack = trackState.textContent.trim();
    const normalizedTrack = rawTrack.toLocaleLowerCase("es");
    const empty = normalizedTrack === "" || normalizedTrack === "sin reproducción";
    const statusLabel = playbackState.textContent.trim();
    const status = statusLabel.toLocaleLowerCase("es");
    const source = activeSessionLabel();
    const parsed = splitTrack(rawTrack);

    panel.classList.toggle("is-empty", empty);
    panel.classList.toggle("is-playing", status === "reproduciendo");
    panel.classList.toggle("is-paused", status === "pausado");

    playbackState.dataset.state = status === "reproduciendo"
      ? "playing"
      : status === "pausado"
        ? "paused"
        : "stopped";

    if (empty) {
      trackTitle.textContent = "Sin reproducción";
      trackArtist.textContent = "Inicia contenido multimedia en el equipo";
      trackSource.textContent = "Sin reproductor activo";
    } else {
      trackTitle.textContent = parsed.title || rawTrack;
      trackArtist.textContent = parsed.artist || source || "Artista desconocido";
      trackSource.textContent = source || "Reproductor multimedia";
    }

    trackTitle.title = trackTitle.textContent;
    trackArtist.title = trackArtist.textContent;
    trackSource.title = trackSource.textContent;

    const playing = status === "reproduciendo";
    const playLabel = playing ? "Pausar" : "Reproducir";
    playButton.classList.toggle("is-playing", playing);
    playButton.setAttribute("aria-label", playLabel);
    playButton.title = playLabel;

    setButtonAvailability(!empty);
  }

  function scheduleUpdate() {
    if (updateQueued) {
      return;
    }

    updateQueued = true;
    queueMicrotask(renderNowPlaying);
  }

  const stateObserver = new MutationObserver(scheduleUpdate);
  stateObserver.observe(trackState, {
    childList: true,
    characterData: true,
    subtree: true,
  });
  stateObserver.observe(playbackState, {
    childList: true,
    characterData: true,
    subtree: true,
  });
  stateObserver.observe(mediaSessions, {
    childList: true,
    subtree: true,
  });

  renderNowPlaying();
})();
