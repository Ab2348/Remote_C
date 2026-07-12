(() => {
  const panel = document.querySelector(".brightness-panel");
  const status = document.querySelector("#brightness-status");
  const container = document.querySelector("#brightness-displays");

  if (!panel || !status || !container) return;

  let displays = [];
  let pendingState = null;
  const busyDisplays = new Set();
  const interactingDisplays = new Set();

  function fallbackDisplays(state) {
    return Object.entries(state.brightness || {}).map(([key, brightness], index) => ({
      key,
      label: `Monitor ${index + 1}`,
      brightness,
    }));
  }

  function stateDisplays(state) {
    return Array.isArray(state.brightness_displays)
      ? state.brightness_displays
      : fallbackDisplays(state);
  }

  function normalizeBrightness(value) {
    const brightness = Number(value);
    if (!Number.isFinite(brightness)) return 0;
    return Math.min(100, Math.max(0, Math.round(brightness)));
  }

  function isLocked() {
    return busyDisplays.size > 0 || interactingDisplays.size > 0;
  }

  function setDisplayBusy(key, busy) {
    if (busy) {
      busyDisplays.add(key);
    } else {
      busyDisplays.delete(key);
    }

    const card = container.querySelector(`[data-display-key="${CSS.escape(key)}"]`);
    card?.classList.toggle("is-busy", busy);
    card?.setAttribute("aria-busy", String(busy));
    card?.querySelectorAll("button, input").forEach((control) => {
      control.disabled = busy;
    });

    if (!busy) applyPendingState();
  }

  function applyPendingState() {
    if (isLocked() || pendingState === null) return;

    const nextState = pendingState;
    pendingState = null;
    render(nextState);
  }

  async function refreshState() {
    const response = await fetch("/api/state", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    document.dispatchEvent(new CustomEvent("remote-c:brightness-update", {
      detail: await response.json(),
    }));
  }

  async function sendDisplayAction(key, path, body) {
    if (busyDisplays.has(key)) return;
    setDisplayBusy(key, true);

    try {
      const response = await fetch(`/api/brightness/display/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display: key, ...body }),
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      document.dispatchEvent(new CustomEvent("remote-c:brightness-update", {
        detail: await response.json(),
      }));
      navigator.vibrate?.(20);
    } catch (error) {
      console.error("No se pudo cambiar el brillo del monitor", error);
      status.textContent = "No se pudo aplicar el cambio · actualizando";
      window.remoteCNotify?.("No se pudo cambiar el brillo del monitor.", "error");

      try {
        await refreshState();
      } catch (refreshError) {
        console.error("No se pudo actualizar el brillo", refreshError);
        status.textContent = "Control de brillo no disponible";
        window.remoteCNotify?.("No se pudo actualizar el control de brillo.", "error");
      }
    } finally {
      setDisplayBusy(key, false);
    }
  }

  function displayCard(display, index) {
    const brightness = normalizeBrightness(display.brightness);
    const card = document.createElement("article");
    card.className = "brightness-display";
    card.dataset.displayKey = display.key;

    const heading = document.createElement("div");
    heading.className = "brightness-display-heading";

    const copy = document.createElement("div");
    const title = document.createElement("h3");
    title.textContent = display.label || `Monitor ${index + 1}`;
    const subtitle = document.createElement("p");
    subtitle.textContent = `Monitor ${index + 1}`;
    copy.append(title, subtitle);

    const output = document.createElement("output");
    output.className = "brightness-display-value";
    output.textContent = `${brightness}%`;
    heading.append(copy, output);

    const slider = document.createElement("input");
    slider.className = "brightness-display-slider";
    slider.type = "range";
    slider.min = "0";
    slider.max = "100";
    slider.step = "1";
    slider.value = String(brightness);
    slider.setAttribute("aria-label", `Brillo de ${display.label}`);

    const beginInteraction = () => {
      interactingDisplays.add(display.key);
    };
    const finishInteraction = () => {
      if (!interactingDisplays.has(display.key)) return;
      interactingDisplays.delete(display.key);
      sendDisplayAction(display.key, "set", {
        brightness: Number(slider.value),
      });
    };

    slider.addEventListener("pointerdown", beginInteraction);
    slider.addEventListener("input", () => {
      beginInteraction();
      output.textContent = `${slider.value}%`;
    });
    slider.addEventListener("change", finishInteraction);
    slider.addEventListener("pointerup", finishInteraction);
    slider.addEventListener("touchend", finishInteraction, { passive: true });
    slider.addEventListener("blur", finishInteraction);
    slider.addEventListener("pointercancel", () => {
      interactingDisplays.delete(display.key);
      applyPendingState();
    });

    const controls = document.createElement("div");
    controls.className = "brightness-display-controls";

    [["down", "− 10%"], ["up", "+ 10%"]].forEach(([action, label]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = label;
      button.setAttribute(
        "aria-label",
        `${action === "up" ? "Subir" : "Bajar"} brillo de ${display.label} 10%`,
      );
      button.addEventListener("click", () => {
        sendDisplayAction(display.key, "control", { action });
      });
      controls.append(button);
    });

    card.append(heading, slider, controls);
    return card;
  }

  function render(state) {
    displays = stateDisplays(state);
    container.replaceChildren();

    if (displays.length === 0) {
      status.textContent = "Sin monitores disponibles";
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "No se pudo obtener el brillo de los monitores.";
      container.append(empty);
      return;
    }

    status.textContent = `${displays.length} ${displays.length === 1 ? "monitor" : "monitores"} · control independiente`;
    displays.forEach((display, index) => {
      container.append(displayCard(display, index));
    });
  }

  document.addEventListener("remote-c:state", (event) => {
    if (isLocked()) {
      pendingState = event.detail;
      return;
    }

    render(event.detail);
  });
})();
