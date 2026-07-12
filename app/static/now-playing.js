(() => {
  const panel = document.querySelector(".now-playing-panel");
  const trackTitle = document.querySelector("#track-title");
  const trackArtist = document.querySelector("#track-artist");
  const trackSource = document.querySelector("#track-source");
  const playbackState = document.querySelector("#playback-state");
  const playButton = document.querySelector("#play-button");
  const mediaButtons = [
    ...document.querySelectorAll('button[data-endpoint="media"]'),
  ];

  if (
    !panel
    || !trackTitle
    || !trackArtist
    || !trackSource
    || !playbackState
    || !playButton
  ) {
    return;
  }

  const playbackLabels = {
    playing: "Reproduciendo",
    paused: "Pausado",
    stopped: "Detenido",
  };

  function splitTrack(value) {
    const normalized = value.trim();
    const separator = normalized.lastIndexOf(" — ");

    if (separator === -1) {
      return { title: normalized, artist: "" };
    }

    return {
      title: normalized.slice(0, separator).trim(),
      artist: normalized.slice(separator + 3).trim(),
    };
  }

  function activeSession(state) {
    const sessions = Array.isArray(state.media_sessions)
      ? state.media_sessions
      : [];

    return sessions.find((session) => session.playing) ?? sessions[0] ?? null;
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

  function renderNowPlaying(state) {
    const rawTrack = String(state.current_track ?? "Sin reproducción").trim();
    const normalizedTrack = rawTrack.toLocaleLowerCase("es");
    const empty = normalizedTrack === "" || normalizedTrack === "sin reproducción";
    const rawStatus = String(state.playback_status ?? "stopped").toLowerCase();
    const status = rawStatus === "playing" || rawStatus === "paused"
      ? rawStatus
      : "stopped";
    const session = activeSession(state);
    const parsed = splitTrack(rawTrack);

    panel.classList.toggle("is-empty", empty);
    playbackState.dataset.state = status;
    playbackState.textContent = playbackLabels[status] ?? "Detenido";

    if (empty) {
      trackTitle.textContent = "Sin reproducción";
      trackArtist.textContent = "Inicia contenido multimedia en el equipo";
      trackSource.textContent = "Sin reproductor activo";
    } else {
      trackTitle.textContent = parsed.title || rawTrack;
      trackArtist.textContent = parsed.artist || session?.artist || "Artista desconocido";
      trackSource.textContent = session?.label || "Reproductor multimedia";
    }

    trackTitle.title = trackTitle.textContent;
    trackArtist.title = trackArtist.textContent;
    trackSource.title = trackSource.textContent;

    const playing = status === "playing";
    const playLabel = playing ? "Pausar" : "Reproducir";
    playButton.textContent = playLabel;
    playButton.classList.toggle("is-playing", playing);
    playButton.setAttribute("aria-label", playLabel);
    playButton.title = playLabel;

    setButtonAvailability(!empty);
  }

  document.addEventListener("remote-c:state", (event) => {
    renderNowPlaying(event.detail);
  });

})();
