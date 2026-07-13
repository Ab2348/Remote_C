(() => {
  const STORAGE_KEY = "remote-c:last-wallpaper";
  const background = document.querySelector("#wallpaper-background");
  const layers = [...document.querySelectorAll(".wallpaper-layer")];

  if (!background || layers.length !== 2) return;

  let activeIndex = 0;
  let currentRevision = null;
  let pendingRevision = null;
  let requestToken = 0;

  function stateFromRevision(revision) {
    if (typeof revision !== "string" || !/^[a-f0-9]{20}$/.test(revision)) {
      return null;
    }

    return {
      available: true,
      revision,
      url: `/api/wallpaper/current?v=${revision}`,
    };
  }

  function readCachedWallpaper() {
    try {
      const cached = JSON.parse(window.localStorage.getItem(STORAGE_KEY));
      return stateFromRevision(cached?.revision);
    } catch {
      return null;
    }
  }

  function rememberWallpaper(state) {
    try {
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ revision: state.revision }),
      );
    } catch {
      // La caché HTTP sigue funcionando aunque el almacenamiento esté bloqueado.
    }
  }

  function forgetWallpaper() {
    try {
      window.localStorage.removeItem(STORAGE_KEY);
    } catch {
      // No hay nada más que limpiar si el almacenamiento está bloqueado.
    }
  }

  function showFallback() {
    requestToken += 1;
    currentRevision = null;
    pendingRevision = null;
    background.classList.remove("is-initial-paint");
    background.classList.remove("has-wallpaper");
    forgetWallpaper();
    document.dispatchEvent(new CustomEvent("remote-c:wallpaper-unavailable"));
  }

  function renderWallpaper(state) {
    if (!state?.available || !state.url || !state.revision) {
      showFallback();
      return;
    }

    if (
      state.revision === currentRevision
      || state.revision === pendingRevision
    ) return;

    const token = ++requestToken;
    pendingRevision = state.revision;
    const nextIndex = activeIndex === 0 ? 1 : 0;
    const nextLayer = layers[nextIndex];
    const previousLayer = layers[activeIndex];
    const isInitialPaint = currentRevision === null
      && !background.classList.contains("has-wallpaper");

    if (isInitialPaint) {
      background.classList.add("is-initial-paint");
    }

    nextLayer.onload = () => {
      if (token !== requestToken) return;

      nextLayer.classList.add("is-active");
      previousLayer.classList.remove("is-active");
      background.classList.add("has-wallpaper");
      activeIndex = nextIndex;
      currentRevision = state.revision;
      pendingRevision = null;
      nextLayer.onload = null;
      nextLayer.onerror = null;
      rememberWallpaper(state);

      if (isInitialPaint) {
        window.requestAnimationFrame(() => {
          window.requestAnimationFrame(() => {
            background.classList.remove("is-initial-paint");
          });
        });
      }

      document.dispatchEvent(new CustomEvent("remote-c:wallpaper-loaded", {
        detail: { image: nextLayer },
      }));
    };

    nextLayer.onerror = () => {
      if (token !== requestToken) return;
      pendingRevision = null;
      background.classList.remove("is-initial-paint");
      nextLayer.removeAttribute("src");
      nextLayer.onload = null;
      nextLayer.onerror = null;
      forgetWallpaper();
      console.warn("No se pudo cargar el wallpaper actual");
    };

    nextLayer.src = state.url;
  }

  document.addEventListener("remote-c:wallpaper", (event) => {
    renderWallpaper(event.detail);
  });

  const cachedWallpaper = readCachedWallpaper();
  if (cachedWallpaper !== null) {
    renderWallpaper(cachedWallpaper);
  }
})();
