(() => {
  const SURFACE_SELECTOR = ".header, .panel";
  const MAX_SAMPLE_SIZE = 240;
  const SAMPLE_GRID_SIZE = 6;
  const MIN_TEXT_CONTRAST = 4.5;
  const SCROLL_SETTLE_DELAY = 140;
  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d", { willReadFrequently: true });
  let wallpaperSample = null;
  let scrollTimer = 0;

  function toLinear(value) {
    const channel = value / 255;
    return channel <= 0.04045
      ? channel / 12.92
      : ((channel + 0.055) / 1.055) ** 2.4;
  }

  function contrastRatio(foregroundLuminance, backgroundLuminance) {
    const lighter = Math.max(foregroundLuminance, backgroundLuminance);
    const darker = Math.min(foregroundLuminance, backgroundLuminance);
    return (lighter + 0.05) / (darker + 0.05);
  }

  function buildWallpaperSample(image) {
    wallpaperSample = null;
    if (!context || !image?.naturalWidth || !image?.naturalHeight) return;

    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const sampleScale = Math.min(
      1,
      MAX_SAMPLE_SIZE / Math.max(viewportWidth, viewportHeight),
    );
    const width = Math.max(1, Math.round(viewportWidth * sampleScale));
    const height = Math.max(1, Math.round(viewportHeight * sampleScale));
    canvas.width = width;
    canvas.height = height;
    context.clearRect(0, 0, width, height);

    const coverScale = Math.max(
      viewportWidth / image.naturalWidth,
      viewportHeight / image.naturalHeight,
    ) * 1.025;
    const renderedWidth = image.naturalWidth * coverScale;
    const renderedHeight = image.naturalHeight * coverScale;
    context.drawImage(
      image,
      ((viewportWidth - renderedWidth) / 2) * sampleScale,
      ((viewportHeight - renderedHeight) / 2) * sampleScale,
      renderedWidth * sampleScale,
      renderedHeight * sampleScale,
    );

    const pixels = context.getImageData(0, 0, width, height).data;
    wallpaperSample = { pixels, width, height, viewportWidth, viewportHeight };
  }

  function luminanceAt(viewportX, viewportY) {
    if (!wallpaperSample) return 0;

    const x = Math.max(0, Math.min(
      wallpaperSample.width - 1,
      Math.floor((viewportX / wallpaperSample.viewportWidth) * wallpaperSample.width),
    ));
    const y = Math.max(0, Math.min(
      wallpaperSample.height - 1,
      Math.floor((viewportY / wallpaperSample.viewportHeight) * wallpaperSample.height),
    ));
    const index = (y * wallpaperSample.width + x) * 4;
    return (
      0.2126 * toLinear(wallpaperSample.pixels[index])
      + 0.7152 * toLinear(wallpaperSample.pixels[index + 1])
      + 0.0722 * toLinear(wallpaperSample.pixels[index + 2])
    );
  }

  function visibleSurfaceLuminances(surface) {
    const rect = surface.getBoundingClientRect();
    const left = Math.max(0, rect.left);
    const right = Math.min(wallpaperSample?.viewportWidth || 0, rect.right);
    const top = Math.max(0, rect.top);
    const bottom = Math.min(wallpaperSample?.viewportHeight || 0, rect.bottom);
    if (right <= left || bottom <= top) return [];

    const luminances = [];
    for (let row = 0; row < SAMPLE_GRID_SIZE; row += 1) {
      for (let column = 0; column < SAMPLE_GRID_SIZE; column += 1) {
        luminances.push(luminanceAt(
          left + ((column + 0.5) / SAMPLE_GRID_SIZE) * (right - left),
          top + ((row + 0.5) / SAMPLE_GRID_SIZE) * (bottom - top),
        ));
      }
    }
    return luminances;
  }

  function prefersDarkForeground(luminances, surface) {
    let blackPasses = 0;
    let whitePasses = 0;
    let blackScore = 0;
    let whiteScore = 0;

    luminances.forEach((luminance) => {
      const blackContrast = contrastRatio(0, luminance);
      const whiteContrast = contrastRatio(1, luminance);
      if (blackContrast >= MIN_TEXT_CONTRAST) blackPasses += 1;
      if (whiteContrast >= MIN_TEXT_CONTRAST) whitePasses += 1;
      blackScore += Math.min(blackContrast, 7);
      whiteScore += Math.min(whiteContrast, 7);
    });

    if (blackPasses !== whitePasses) return blackPasses > whitePasses;
    if (blackScore !== whiteScore) return blackScore > whiteScore;
    return surface.classList.contains("has-dark-foreground");
  }

  function updateVisibleSurfaceContrast() {
    if (!wallpaperSample) return;

    document.querySelectorAll(SURFACE_SELECTOR).forEach((surface) => {
      const luminances = visibleSurfaceLuminances(surface);
      if (luminances.length === 0) return;

      const darkForeground = prefersDarkForeground(luminances, surface);
      surface.classList.toggle("has-dark-foreground", darkForeground);
      surface.classList.toggle("has-light-foreground", !darkForeground);
    });
  }

  function clearSurfaceContrast() {
    document.querySelectorAll(SURFACE_SELECTOR).forEach((surface) => {
      surface.classList.remove("has-dark-foreground", "has-light-foreground");
    });
  }

  function updateAfterScrollSettles() {
    window.clearTimeout(scrollTimer);
    scrollTimer = window.setTimeout(updateVisibleSurfaceContrast, SCROLL_SETTLE_DELAY);
  }

  document.addEventListener("remote-c:wallpaper-loaded", (event) => {
    try {
      buildWallpaperSample(event.detail?.image);
      updateVisibleSurfaceContrast();
    } catch (error) {
      wallpaperSample = null;
      clearSurfaceContrast();
      console.warn("No se pudo analizar el contraste del wallpaper", error);
    }
  });

  document.addEventListener("remote-c:wallpaper-unavailable", () => {
    wallpaperSample = null;
    clearSurfaceContrast();
  });

  window.addEventListener("scroll", updateAfterScrollSettles, { passive: true });
})();
