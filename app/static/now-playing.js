(() => {
  const panel = document.querySelector(".now-playing-panel");
  const trackTitle = document.querySelector("#track-title");
  const trackArtist = document.querySelector("#track-artist");
  const trackSource = document.querySelector("#track-source");
  const artwork = document.querySelector("#track-artwork");
  const coverPlaceholder = document.querySelector("#cover-placeholder");
  const indicator = document.querySelector("#now-playing-indicator");
  const playButton = document.querySelector("#play-button");
  const mediaButtons = [
    ...document.querySelectorAll('button[data-endpoint="media"]'),
  ];

  if (
    !panel
    || !trackTitle
    || !trackArtist
    || !trackSource
    || !artwork
    || !coverPlaceholder
    || !indicator
    || !playButton
  ) return;

  let currentArtworkKey = null;

  function splitTrack(value) {
    const normalized = value.trim();
    const separator = normalized.lastIndexOf(" — ");

    if (separator === -1) return { title: normalized, artist: "" };

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

  function clearArtwork() {
    currentArtworkKey = null;
    artwork.hidden = true;
    artwork.removeAttribute("src");
    coverPlaceholder.hidden = false;
  }

  function renderArtwork(session) {
    if (!session?.artwork_id) {
      clearArtwork();
      return;
    }

    const key = `${session.name}:${session.artwork_id}`;
    if (key === currentArtworkKey) return;

    currentArtworkKey = key;
    artwork.hidden = true;
    coverPlaceholder.hidden = false;
    artwork.onload = () => {
      if (currentArtworkKey !== key) return;
      artwork.hidden = false;
      coverPlaceholder.hidden = true;
    };
    artwork.onerror = () => {
      if (currentArtworkKey !== key) return;
      artwork.hidden = true;
      coverPlaceholder.hidden = false;
    };
    artwork.src = `/api/media/artwork?player=${encodeURIComponent(session.name)}&v=${session.artwork_id}`;
  }

  function renderNowPlaying(state) {
    const rawTrack = String(state.current_track ?? "Sin reproducción").trim();
    const normalizedTrack = rawTrack.toLocaleLowerCase("es");
    const empty = normalizedTrack === "" || normalizedTrack === "sin reproducción";
    const rawStatus = String(state.playback_status ?? "stopped").toLowerCase();
    const playbackStatus = ["playing", "paused"].includes(rawStatus)
      ? rawStatus
      : "stopped";
    const session = activeSession(state);
    const parsed = splitTrack(rawTrack);

    panel.classList.toggle("is-empty", empty);
    indicator.classList.toggle("is-playing", playbackStatus === "playing");
    indicator.classList.toggle("is-paused", playbackStatus === "paused");

    if (empty) {
      trackTitle.textContent = "Sin reproducción";
      trackArtist.textContent = "Inicia contenido multimedia en el equipo";
      trackSource.textContent = "Sin reproductor activo";
      clearArtwork();
    } else {
      trackTitle.textContent = parsed.title || rawTrack;
      trackArtist.textContent = parsed.artist || session?.artist || "Artista desconocido";
      trackSource.textContent = session?.label || "Reproductor multimedia";
      renderArtwork(session);
    }

    trackTitle.title = trackTitle.textContent;
    trackArtist.title = trackArtist.textContent;
    trackSource.title = trackSource.textContent;

    const playing = playbackStatus === "playing";
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
