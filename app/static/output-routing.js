(() => {
  const panel = document.querySelector(".output-panel");
  const status = document.querySelector("#output-routing-status");
  const container = document.querySelector("#audio-outputs");
  const setDefaultButton = document.querySelector("#set-default-output");
  const forceButton = document.querySelector("#force-output");
  const hint = document.querySelector("#output-routing-hint");

  if (
    !panel
    || !status
    || !container
    || !setDefaultButton
    || !forceButton
    || !hint
  ) return;

  let state = { outputs: [], applications: [] };
  let selectedName = null;
  let selectionDirty = false;
  let busy = false;
  let pendingState = null;

  function outputStateLabel(output) {
    const labels = {
      running: "En uso",
      idle: "Disponible",
      suspended: "En espera",
    };
    return labels[output.state] || "Disponible";
  }

  function activeOutput() {
    return state.outputs.find((output) => output.active) || null;
  }

  function selectedOutput() {
    return state.outputs.find((output) => output.name === selectedName) || null;
  }

  function setBusy(value) {
    busy = value;
    panel.classList.toggle("is-busy", value);
    panel.setAttribute("aria-busy", String(value));
    container.querySelectorAll("button").forEach((button) => {
      button.disabled = value;
    });
    updateActions();

    if (!value) applyPendingState();
  }

  function applyPendingState() {
    if (busy || pendingState === null) return;

    const nextState = pendingState;
    pendingState = null;
    render(nextState);
  }

  function updateActions() {
    const selected = selectedOutput();
    const active = activeOutput();
    const unavailable = busy || selected === null;

    setDefaultButton.disabled = unavailable || selected?.name === active?.name;
    forceButton.disabled = unavailable;

    if (selected === null) {
      hint.textContent = "Selecciona una salida para continuar.";
    } else if (selected.name === active?.name) {
      hint.textContent = "Ya es la predeterminada. “Mover todo” también trae los flujos que permanezcan en otra salida.";
    } else {
      hint.textContent = "“Usar como predeterminada” afecta audio nuevo; “Mover todo” también cambia los flujos actuales.";
    }
  }

  function selectOutput(name) {
    if (busy || name === selectedName) return;

    selectedName = name;
    selectionDirty = true;
    render(state);
  }

  function outputCard(output) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "output-device";
    card.dataset.outputName = output.name;
    card.setAttribute("role", "radio");
    card.setAttribute("aria-checked", String(output.name === selectedName));
    card.tabIndex = output.name === selectedName ? 0 : -1;
    card.classList.toggle("is-selected", output.name === selectedName);
    card.classList.toggle("is-active", output.active);

    const icon = document.createElement("span");
    icon.className = "output-device-icon";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = output.label.trim().charAt(0).toLocaleUpperCase("es") || "A";

    const copy = document.createElement("span");
    copy.className = "output-device-copy";

    const label = document.createElement("strong");
    label.textContent = output.label;

    const deviceState = document.createElement("span");
    deviceState.textContent = outputStateLabel(output);
    copy.append(label, deviceState);

    const marker = document.createElement("span");
    marker.className = "output-device-marker";
    marker.textContent = output.active
      ? "Predeterminada"
      : output.name === selectedName
        ? "Seleccionada"
        : "Seleccionar";

    card.append(icon, copy, marker);
    card.addEventListener("click", () => selectOutput(output.name));
    return card;
  }

  async function refreshRouting() {
    const response = await fetch("/api/audio-routing", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    document.dispatchEvent(new CustomEvent("remote-c:audio-routing-update", {
      detail: await response.json(),
    }));
  }

  async function sendAction(path) {
    const selected = selectedOutput();
    if (busy || selected === null) return;

    setBusy(true);

    try {
      const response = await fetch(`/api/audio-routing/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: selected.name }),
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      selectionDirty = false;
      document.dispatchEvent(new CustomEvent("remote-c:audio-routing-update", {
        detail: await response.json(),
      }));
      window.remoteCNotify?.(
        path === "force"
          ? `Audio movido a ${selected.label}.`
          : `${selected.label} es ahora la salida predeterminada.`,
        "success",
      );
      navigator.vibrate?.(20);
    } catch (error) {
      console.error("No se pudo cambiar la salida de audio", error);
      status.textContent = "No se pudo aplicar el cambio · actualizando";
      window.remoteCNotify?.("No se pudo cambiar la salida de audio.", "error");

      try {
        await refreshRouting();
      } catch (refreshError) {
        console.error("No se pudo actualizar la salida de audio", refreshError);
        status.textContent = "Control de salidas no disponible";
        window.remoteCNotify?.("No se pudo actualizar el control de salidas.", "error");
      }
    } finally {
      setBusy(false);
    }
  }

  function render(nextState) {
    state = {
      outputs: Array.isArray(nextState?.outputs) ? nextState.outputs : [],
      applications: Array.isArray(nextState?.applications)
        ? nextState.applications
        : [],
    };

    const names = state.outputs.map((output) => output.name);
    const active = activeOutput();

    if (!names.includes(selectedName)) {
      selectedName = active?.name || names[0] || null;
      selectionDirty = false;
    } else if (!selectionDirty && active) {
      selectedName = active.name;
    }

    container.replaceChildren();

    if (state.outputs.length === 0) {
      status.textContent = "Sin salidas disponibles";
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "Conecta o activa un dispositivo de salida de audio.";
      container.append(empty);
      updateActions();
      return;
    }

    status.textContent = active
      ? `${state.outputs.length} ${state.outputs.length === 1 ? "salida" : "salidas"} · ${active.label}`
      : `${state.outputs.length} ${state.outputs.length === 1 ? "salida" : "salidas"}`;

    state.outputs.forEach((output) => {
      container.append(outputCard(output));
    });
    updateActions();
  }

  setDefaultButton.addEventListener("click", () => sendAction("default"));
  forceButton.addEventListener("click", () => sendAction("force"));

  container.addEventListener("keydown", (event) => {
    const keys = ["ArrowDown", "ArrowRight", "ArrowUp", "ArrowLeft", "Home", "End"];
    if (!keys.includes(event.key) || state.outputs.length === 0) return;

    event.preventDefault();
    const current = Math.max(
      0,
      state.outputs.findIndex((output) => output.name === selectedName),
    );
    let next = current;

    if (event.key === "Home") next = 0;
    if (event.key === "End") next = state.outputs.length - 1;
    if (event.key === "ArrowDown" || event.key === "ArrowRight") {
      next = (current + 1) % state.outputs.length;
    }
    if (event.key === "ArrowUp" || event.key === "ArrowLeft") {
      next = (current - 1 + state.outputs.length) % state.outputs.length;
    }

    selectOutput(state.outputs[next].name);
    container.querySelector(`[data-output-name="${CSS.escape(selectedName)}"]`)?.focus();
  });

  document.addEventListener("remote-c:audio-routing", (event) => {
    if (busy) {
      pendingState = event.detail;
      return;
    }

    render(event.detail);
  });

  document.addEventListener("remote-c:audio-routing-error", () => {
    if (!busy) render({ outputs: [], applications: [] });
  });
})();
