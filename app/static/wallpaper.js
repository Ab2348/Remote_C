(() => {
  const background = document.querySelector("#wallpaper-background");
  const layers = [...document.querySelectorAll(".wallpaper-layer")];

  if (!background || layers.length !== 2) return;

  let activeIndex = 0;
  let currentRevision = null;
  let requestToken = 0;

  function showFallback() {
    requestToken += 1;
    currentRevision = null;
    background.classList.remove("has-wallpaper");
    document.dispatchEvent(new CustomEvent("remote-c:wallpaper-unavailable"));
  }

  function renderWallpaper(state) {
    if (!state?.available || !state.url || !state.revision) {
      showFallback();
      return;
    }

    if (state.revision === currentRevision) return;

    const token = ++requestToken;
    const nextIndex = activeIndex === 0 ? 1 : 0;
    const nextLayer = layers[nextIndex];
    const previousLayer = layers[activeIndex];

    nextLayer.onload = () => {
      if (token !== requestToken) return;

      nextLayer.classList.add("is-active");
      previousLayer.classList.remove("is-active");
      background.classList.add("has-wallpaper");
      activeIndex = nextIndex;
      currentRevision = state.revision;
      nextLayer.onload = null;
      nextLayer.onerror = null;
      document.dispatchEvent(new CustomEvent("remote-c:wallpaper-loaded", {
        detail: { image: nextLayer },
      }));
    };

    nextLayer.onerror = () => {
      if (token !== requestToken) return;
      nextLayer.removeAttribute("src");
      nextLayer.onload = null;
      nextLayer.onerror = null;
      console.warn("No se pudo cargar el wallpaper actual");
    };

    nextLayer.src = state.url;
  }

  document.addEventListener("remote-c:wallpaper", (event) => {
    renderWallpaper(event.detail);
  });
})();
