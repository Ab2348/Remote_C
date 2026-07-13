(() => {
  const MAX_SAMPLE_SIZE = 160;
  const MIN_TEXT_CONTRAST = 4.5;
  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d", { willReadFrequently: true });

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

  function prefersDarkForeground(image) {
    if (!context || !image?.naturalWidth || !image?.naturalHeight) return false;

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
    let blackPasses = 0;
    let whitePasses = 0;
    let blackScore = 0;
    let whiteScore = 0;

    for (let index = 0; index < pixels.length; index += 4) {
      const luminance = (
        0.2126 * toLinear(pixels[index])
        + 0.7152 * toLinear(pixels[index + 1])
        + 0.0722 * toLinear(pixels[index + 2])
      );
      const blackContrast = contrastRatio(0, luminance);
      const whiteContrast = contrastRatio(1, luminance);
      if (blackContrast >= MIN_TEXT_CONTRAST) blackPasses += 1;
      if (whiteContrast >= MIN_TEXT_CONTRAST) whitePasses += 1;
      blackScore += Math.min(blackContrast, 7);
      whiteScore += Math.min(whiteContrast, 7);
    }

    if (blackPasses !== whitePasses) return blackPasses > whitePasses;
    return blackScore > whiteScore;
  }

  function applyWallpaperContrast(image) {
    try {
      const darkForeground = prefersDarkForeground(image);
      document.documentElement.classList.toggle("has-dark-foreground", darkForeground);
      document.documentElement.classList.toggle("has-light-foreground", !darkForeground);
    } catch (error) {
      document.documentElement.classList.remove("has-dark-foreground", "has-light-foreground");
      console.warn("No se pudo analizar el contraste del wallpaper", error);
    }
  }

  document.addEventListener("remote-c:wallpaper-loaded", (event) => {
    applyWallpaperContrast(event.detail?.image);
  });

  document.addEventListener("remote-c:wallpaper-unavailable", () => {
    document.documentElement.classList.remove("has-dark-foreground", "has-light-foreground");
  });
})();
