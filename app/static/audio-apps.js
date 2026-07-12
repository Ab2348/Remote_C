(() => {
  const status = document.querySelector("#audio-routing-status");
  const container = document.querySelector("#audio-streams");

  if (!status || !container) return;

  let state = { outputs: [], applications: [] };
  let busy = false;
  let interacting = false;
  let pendingState = null;
  const selectedOutputs = new Map();

  function plural(count, singular, pluralLabel) {
    return `${count} ${count === 1 ? singular : pluralLabel}`;
  }

  function appInitial(application) {
    return (application.trim().charAt(0) || "A").toLocaleUpperCase("es");
  }

  function mediaDescription(application) {
    const parts = [];
    const media = Array.isArray(application.media) ? application.media : [];

    if (media.length > 0) {
      parts.push(media.slice(0, 2).join(" · "));
    }

    parts.push(application.output_label || "Salida desconocida");
    return parts.join(" — ");
  }

  function setBusy(value) {
    busy = value;
    container.classList.toggle("is-busy", value);
    container.querySelectorAll("button, select, input").forEach((control) => {
      control.disabled = value;
    });

    if (!value) {
      container.querySelectorAll(".audio-application-routing").forEach((routing) => {
        const select = routing.querySelector("select");
        const button = routing.querySelector("button");
        if (select && button) button.disabled = !select.value;
      });
    }

    if (!value) applyPendingState();
  }

  function applyPendingState() {
    if (busy || interacting || pendingState === null) return;

    const nextState = pendingState;
    pendingState = null;
    render(nextState);
  }

  function outputSelect(application) {
    const select = document.createElement("select");
    select.setAttribute("aria-label", `Salida de ${application.application}`);

    if (!application.output_name) {
      const mixed = document.createElement("option");
      mixed.value = "";
      mixed.textContent = application.output_label || "Varias salidas";
      mixed.disabled = true;
      select.append(mixed);
    }

    state.outputs.forEach((output) => {
      const option = document.createElement("option");
      option.value = output.name;
      option.textContent = output.label;
      select.append(option);
    });

    const availableNames = state.outputs.map((output) => output.name);
    const remembered = selectedOutputs.get(application.id);
    const selected = availableNames.includes(remembered)
      ? remembered
      : application.output_name;

    if (selected && availableNames.includes(selected)) {
      select.value = selected;
    } else if (!application.output_name) {
      select.value = "";
    }

    select.addEventListener("change", () => {
      selectedOutputs.set(application.id, select.value);
    });

    return select;
  }

  async function requestAction(path, body) {
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
      status.textContent = "No se pudo aplicar el cambio · actualizando";

      try {
        const response = await fetch("/api/audio-routing", { cache: "no-store" });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        document.dispatchEvent(new CustomEvent("remote-c:audio-routing-update", {
          detail: await response.json(),
        }));
      } catch (refreshError) {
        console.error("No se pudo actualizar el ruteo de audio", refreshError);
        status.textContent = "Control de aplicaciones no disponible";
      }
    } finally {
      setBusy(false);
    }
  }

  function applicationCard(application) {
    const item = document.createElement("article");
    item.className = "audio-application";

    const heading = document.createElement("div");
    heading.className = "audio-application-heading";

    const icon = document.createElement("span");
    icon.className = "audio-application-icon";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = appInitial(application.application);

    const copy = document.createElement("div");
    copy.className = "audio-application-copy";

    const title = document.createElement("h3");
    title.textContent = application.application;

    const description = document.createElement("p");
    description.textContent = mediaDescription(application);
    copy.append(title, description);
    heading.append(icon, copy);

    if (application.stream_count > 1) {
      const count = document.createElement("span");
      count.className = "audio-application-count";
      count.textContent = plural(application.stream_count, "flujo", "flujos");
      heading.append(count);
    }

    const volumeRow = document.createElement("div");
    volumeRow.className = "audio-application-volume";

    const volumeLabel = document.createElement("label");
    volumeLabel.className = "audio-application-volume-label";

    const labelText = document.createElement("span");
    labelText.textContent = application.mixed_volume ? "Volumen medio" : "Volumen";

    const volumeOutput = document.createElement("output");
    volumeOutput.textContent = `${application.mixed_volume ? "≈" : ""}${application.volume}%`;

    const slider = document.createElement("input");
    slider.type = "range";
    slider.min = "0";
    slider.max = "100";
    slider.step = "1";
    slider.value = String(application.volume);
    slider.setAttribute("aria-label", `Volumen de ${application.application}`);

    const beginInteraction = () => { interacting = true; };
    const endInteraction = () => {
      interacting = false;
      applyPendingState();
    };

    slider.addEventListener("pointerdown", beginInteraction);
    slider.addEventListener("input", () => {
      volumeOutput.textContent = `${slider.value}%`;
    });
    slider.addEventListener("change", () => {
      endInteraction();
      requestAction("volume", {
        stream_indexes: application.stream_indexes,
        volume: Number(slider.value),
      });
    });
    slider.addEventListener("pointercancel", endInteraction);

    volumeLabel.append(labelText, volumeOutput);
    volumeRow.append(volumeLabel, slider);

    const controls = document.createElement("div");
    controls.className = "audio-application-controls";

    const mute = document.createElement("button");
    mute.type = "button";
    mute.className = "audio-application-mute";
    mute.setAttribute("aria-pressed", String(application.muted));
    mute.textContent = application.muted
      ? "Activar sonido"
      : application.partially_muted
        ? "Silenciar todo"
        : "Silenciar";
    mute.addEventListener("click", () => {
      requestAction("mute", {
        stream_indexes: application.stream_indexes,
        muted: !application.muted,
      });
    });

    const routing = document.createElement("div");
    routing.className = "audio-application-routing";
    const select = outputSelect(application);

    const move = document.createElement("button");
    move.type = "button";
    move.textContent = "Mover";
    move.disabled = state.outputs.length === 0 || !select.value;
    select.addEventListener("change", () => {
      move.disabled = busy || !select.value;
    });
    move.addEventListener("click", () => {
      if (!select.value) return;
      requestAction("output", {
        stream_indexes: application.stream_indexes,
        name: select.value,
      });
    });

    routing.append(select, move);
    controls.append(mute, routing);
    item.append(heading, volumeRow, controls);
    return item;
  }

  function render(nextState) {
    state = {
      outputs: Array.isArray(nextState?.outputs) ? nextState.outputs : [],
      applications: Array.isArray(nextState?.applications)
        ? nextState.applications
        : [],
    };
    container.replaceChildren();

    if (state.applications.length === 0) {
      status.textContent = state.outputs.length === 0
        ? "Sin salidas de audio disponibles"
        : "Sin aplicaciones activas";
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "Las aplicaciones aparecerán cuando reproduzcan audio.";
      container.append(empty);
      return;
    }

    const streamCount = state.applications.reduce(
      (total, application) => total + application.stream_count,
      0,
    );
    status.textContent = `${plural(state.applications.length, "aplicación", "aplicaciones")} · ${plural(streamCount, "flujo", "flujos")}`;

    state.applications.forEach((application) => {
      container.append(applicationCard(application));
    });
  }

  document.addEventListener("remote-c:audio-routing", (event) => {
    if (busy || interacting) {
      pendingState = event.detail;
      return;
    }

    render(event.detail);
  });

  document.addEventListener("remote-c:audio-routing-error", () => {
    if (!busy) render({ outputs: [], applications: [] });
  });
})();
