(() => {
  const status = document.querySelector("#audio-routing-status");
  const container = document.querySelector("#audio-streams");

  if (!status || !container) return;

  let routingState = { outputs: [], applications: [] };
  let mediaSessions = [];
  let busy = false;
  let interacting = false;
  let renderPending = false;
  let initialExpansionApplied = false;
  const expandedApplications = new Map();
  const openOutputMenus = new Set();

  function normalizeIdentity(value) {
    return String(value || "")
      .split(".instance", 1)[0]
      .toLocaleLowerCase("es")
      .replace(/[^a-z0-9]+/g, "");
  }

  function uniqueIdentities(values) {
    return [...new Set(values.map(normalizeIdentity).filter(Boolean))];
  }

  function sessionIdentities(session) {
    return uniqueIdentities([session.name, session.label]);
  }

  function applicationIdentities(application) {
    return uniqueIdentities([
      application.id,
      application.binary,
      application.application,
    ]);
  }

  function sessionMatchesApplication(session, application) {
    const sessionIds = sessionIdentities(session);
    const applicationIds = applicationIdentities(application);
    return sessionIds.some((identity) => applicationIds.includes(identity));
  }

  function preferredSession(sessions) {
    return [...sessions].sort((left, right) => {
      const priority = { playing: 0, paused: 1, stopped: 2 };
      return (priority[left.status] ?? 3) - (priority[right.status] ?? 3);
    })[0] || null;
  }

  function mergeApplications() {
    const applications = routingState.applications.map((application) => ({
      ...application,
      sessions: [],
      has_audio_streams: application.stream_indexes.length > 0,
    }));

    mediaSessions.forEach((session) => {
      let application = applications.find((candidate) => (
        sessionMatchesApplication(session, candidate)
      ));

      if (!application) {
        const identity = sessionIdentities(session)[0] || `session-${applications.length}`;
        application = applications.find((candidate) => candidate.id === identity);

        if (!application) {
          application = {
            id: identity,
            application: session.label || "Reproductor multimedia",
            binary: "",
            media: [],
            stream_indexes: [],
            stream_count: 0,
            volume: 0,
            mixed_volume: false,
            muted: false,
            partially_muted: false,
            output_name: null,
            output_label: "Sin flujo de audio activo",
            playing: false,
            playback_status: "paused",
            sessions: [],
            has_audio_streams: false,
          };
          applications.push(application);
        }
      }

      application.sessions.push(session);
    });

    const merged = applications.map((application) => {
      const session = preferredSession(application.sessions);
      const playbackStatus = session?.status || application.playback_status || "paused";

      return {
        ...application,
        session,
        playback_status: playbackStatus,
        playing: playbackStatus === "playing",
      };
    });

    merged.sort((left, right) => (
      Number(right.playing) - Number(left.playing)
      || left.application.localeCompare(right.application, "es")
    ));

    if (!initialExpansionApplied && merged.length > 0) {
      const initiallyExpanded = merged.find((application) => application.playing);
      if (initiallyExpanded) expandedApplications.set(initiallyExpanded.id, true);
      initialExpansionApplied = true;
    }

    return merged;
  }

  function playbackLabel(application) {
    const labels = {
      playing: "Reproduciendo",
      paused: "En pausa",
      stopped: "Detenido",
    };
    return labels[application.playback_status] || "En pausa";
  }

  function appInitial(application) {
    return (application.trim().charAt(0) || "A").toLocaleUpperCase("es");
  }

  function setBusy(value) {
    busy = value;
    container.classList.toggle("is-busy", value);
    container.setAttribute("aria-busy", String(value));
    container.querySelectorAll("button, input, select").forEach((control) => {
      control.disabled = value;
    });

    if (!value) {
      renderPending = false;
      render();
    }
  }

  function requestRender() {
    if (busy || interacting) {
      renderPending = true;
      return;
    }

    render();
  }

  async function refreshRouting() {
    const response = await fetch("/api/audio-routing", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    document.dispatchEvent(new CustomEvent("remote-c:audio-routing-update", {
      detail: await response.json(),
    }));
  }

  async function refreshMediaSessions() {
    const response = await fetch("/api/media/sessions", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const state = await response.json();
    mediaSessions = Array.isArray(state.players) ? state.players : [];
    requestRender();
  }

  async function sendRoutingAction(path, body) {
    setBusy(true);

    try {
      const response = await fetch(`/api/audio-routing/application/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      document.dispatchEvent(new CustomEvent("remote-c:audio-routing-update", {
        detail: await response.json(),
      }));
      navigator.vibrate?.(20);
    } catch (error) {
      console.error("No se pudo actualizar la aplicación de audio", error);
      window.remoteCNotify?.("No se pudo aplicar el cambio de audio.", "error");

      try {
        await refreshRouting();
      } catch (refreshError) {
        console.error("No se pudo actualizar el ruteo de audio", refreshError);
        window.remoteCNotify?.("No se pudo actualizar el control de aplicaciones.", "error");
      }
    } finally {
      setBusy(false);
    }
  }

  async function sendMediaAction(application, action) {
    if (!application.session) return;
    setBusy(true);

    try {
      const response = await fetch("/api/media/sessions/control", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          player: application.session.name,
          action,
        }),
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const state = await response.json();
      mediaSessions = Array.isArray(state.players) ? state.players : [];
      renderPending = true;
      navigator.vibrate?.(20);
    } catch (error) {
      console.warn("La sesión multimedia cambió; actualizando", error);

      try {
        await refreshMediaSessions();
      } catch (refreshError) {
        console.error("No se pudieron actualizar las sesiones", refreshError);
        window.remoteCNotify?.("No se pudo actualizar el reproductor.", "error");
      }
    } finally {
      setBusy(false);
    }
  }

  function mediaControls(application) {
    const session = application.session;
    if (!session) return null;

    const actions = [];
    if (session.can_seek) actions.push(["seek_backward", "−10 s"]);
    if (session.can_play_pause) {
      actions.push(["play_pause", session.playing ? "Pausar" : "Reproducir"]);
    }
    if (session.can_seek) actions.push(["seek_forward", "+10 s"]);
    if (actions.length === 0) return null;

    const controls = document.createElement("div");
    controls.className = "audio-application-media-controls";

    actions.forEach(([action, label]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = label;
      button.addEventListener("click", () => sendMediaAction(application, action));
      controls.append(button);
    });

    return controls;
  }

  function volumeControl(application) {
    const row = document.createElement("div");
    row.className = "audio-application-volume";

    const mute = document.createElement("button");
    mute.type = "button";
    mute.className = "audio-application-mute";
    mute.textContent = application.muted ? "🔇" : "🔊";
    mute.setAttribute("aria-pressed", String(application.muted));
    mute.setAttribute(
      "aria-label",
      application.muted
        ? `Activar sonido de ${application.application}`
        : `Silenciar ${application.application}`,
    );
    mute.addEventListener("click", () => {
      sendRoutingAction("mute", {
        stream_indexes: application.stream_indexes,
        muted: !application.muted,
      });
    });

    const slider = document.createElement("input");
    slider.type = "range";
    slider.min = "0";
    slider.max = "100";
    slider.step = "1";
    slider.value = String(application.volume);
    slider.setAttribute("aria-label", `Volumen de ${application.application}`);

    const output = document.createElement("output");
    output.textContent = `${application.mixed_volume ? "≈" : ""}${application.volume}%`;

    const beginInteraction = () => { interacting = true; };
    const finishInteraction = () => {
      if (!interacting) return;
      interacting = false;
      sendRoutingAction("volume", {
        stream_indexes: application.stream_indexes,
        volume: Number(slider.value),
      });
    };

    slider.addEventListener("pointerdown", beginInteraction);
    slider.addEventListener("input", () => {
      interacting = true;
      output.textContent = `${slider.value}%`;
    });
    slider.addEventListener("change", finishInteraction);
    slider.addEventListener("pointerup", finishInteraction);
    slider.addEventListener("touchend", finishInteraction, { passive: true });
    slider.addEventListener("blur", finishInteraction);
    slider.addEventListener("pointercancel", () => {
      interacting = false;
      requestRender();
    });

    row.append(mute, slider, output);
    return row;
  }

  function outputDisclosure(application) {
    if (routingState.outputs.length === 0) return null;

    const disclosure = document.createElement("details");
    disclosure.className = "audio-application-output";
    disclosure.open = openOutputMenus.has(application.id);

    const summary = document.createElement("summary");
    const summaryCopy = document.createElement("span");
    const label = document.createElement("span");
    label.textContent = "Mover salida a";
    const current = document.createElement("strong");
    current.textContent = application.output_label;
    summaryCopy.append(label, current);
    summary.append(summaryCopy);

    const menu = document.createElement("div");
    menu.className = "audio-application-output-menu";

    routingState.outputs.forEach((output) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = output.label;
      button.classList.toggle("is-current", output.name === application.output_name);
      button.disabled = output.name === application.output_name;
      button.addEventListener("click", () => {
        openOutputMenus.delete(application.id);
        sendRoutingAction("output", {
          stream_indexes: application.stream_indexes,
          name: output.name,
        });
      });
      menu.append(button);
    });

    disclosure.addEventListener("toggle", () => {
      if (disclosure.open) {
        openOutputMenus.add(application.id);
      } else {
        openOutputMenus.delete(application.id);
      }
    });
    disclosure.append(summary, menu);
    return disclosure;
  }

  function applicationCard(application, index) {
    const expanded = expandedApplications.get(application.id) === true;
    const detailsId = `audio-application-details-${index}`;
    const card = document.createElement("article");
    card.className = "audio-application";
    card.classList.toggle("is-expanded", expanded);

    const heading = document.createElement("div");
    heading.className = "audio-application-heading";

    const icon = document.createElement("span");
    icon.className = "audio-application-icon";
    icon.dataset.app = normalizeIdentity(application.application);
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = appInitial(application.application);

    const copy = document.createElement("div");
    copy.className = "audio-application-copy";
    const title = document.createElement("h3");
    title.textContent = application.application;
    const playback = document.createElement("p");
    playback.textContent = playbackLabel(application);
    playback.dataset.state = application.playback_status;
    copy.append(title, playback);

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "audio-application-toggle";
    toggle.textContent = expanded ? "⌃" : "⌄";
    toggle.setAttribute("aria-expanded", String(expanded));
    toggle.setAttribute("aria-controls", detailsId);
    toggle.setAttribute(
      "aria-label",
      `${expanded ? "Contraer" : "Expandir"} ${application.application}`,
    );
    toggle.addEventListener("click", () => {
      expandedApplications.set(application.id, !expanded);
      render();
    });
    heading.append(icon, copy, toggle);

    const controls = mediaControls(application);
    const details = document.createElement("div");
    details.id = detailsId;
    details.className = "audio-application-details";
    details.hidden = !expanded;

    if (application.has_audio_streams) {
      details.append(volumeControl(application));
      const output = outputDisclosure(application);
      if (output) details.append(output);
    } else {
      const empty = document.createElement("p");
      empty.className = "audio-application-no-stream";
      empty.textContent = "Sin flujo de audio activo.";
      details.append(empty);
    }

    card.append(heading);
    if (controls) card.append(controls);
    card.append(details);
    return card;
  }

  function render() {
    const applications = mergeApplications();
    container.replaceChildren();

    if (applications.length === 0) {
      status.textContent = routingState.outputs.length === 0
        ? "Sin salidas de audio disponibles"
        : "Sin aplicaciones activas";
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "Las aplicaciones aparecerán al reproducir contenido.";
      container.append(empty);
      return;
    }

    const activeCount = applications.filter((application) => application.playing).length;
    status.textContent = activeCount > 0
      ? `${activeCount} ${activeCount === 1 ? "activa" : "activas"}`
      : `${applications.length} ${applications.length === 1 ? "aplicación" : "aplicaciones"} · ninguna activa`;

    applications.forEach((application, index) => {
      container.append(applicationCard(application, index));
    });
  }

  document.addEventListener("remote-c:state", (event) => {
    mediaSessions = Array.isArray(event.detail.media_sessions)
      ? event.detail.media_sessions
      : [];
    requestRender();
  });

  document.addEventListener("remote-c:audio-routing", (event) => {
    routingState = {
      outputs: Array.isArray(event.detail?.outputs) ? event.detail.outputs : [],
      applications: Array.isArray(event.detail?.applications)
        ? event.detail.applications
        : [],
    };
    requestRender();
  });

  document.addEventListener("remote-c:audio-routing-error", () => {
    routingState = { outputs: [], applications: [] };
    requestRender();
  });
})();
