(() => {
  const feedback = document.querySelector("#global-feedback");
  if (!feedback) return;

  let timer = null;

  function hide() {
    feedback.classList.remove("is-visible");
    window.clearTimeout(timer);
    timer = null;
  }

  window.remoteCNotify = (message, kind = "info", timeout = 3200) => {
    const text = String(message || "").trim();
    if (!text) return;

    window.clearTimeout(timer);
    feedback.textContent = text;
    feedback.dataset.kind = kind;
    feedback.classList.add("is-visible");
    timer = window.setTimeout(hide, timeout);
  };

  feedback.addEventListener("click", hide);
})();
