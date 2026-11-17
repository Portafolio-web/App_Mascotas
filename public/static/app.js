(function () {
  "use strict";

  var pad = function (n) {
    return String(n).padStart(2, "0");
  };

  var countdowns = document.querySelectorAll("[data-countdown]");
  var reloading = false;

  function tick() {
    var finished = false;
    countdowns.forEach(function (el) {
      var target = new Date(el.getAttribute("data-countdown")).getTime();
      if (isNaN(target)) return;
      var diff = target - Date.now();
      if (diff <= 0) {
        el.textContent = "00:00:00";
        if (!el.dataset.done) {
          el.dataset.done = "1";
          finished = true;
        }
        return;
      }
      var seconds = Math.floor(diff / 1000);
      var hours = Math.floor(seconds / 3600);
      var minutes = Math.floor((seconds % 3600) / 60);
      el.textContent = pad(hours) + ":" + pad(minutes) + ":" + pad(seconds % 60);
    });
    if (finished && !reloading) {
      reloading = true;
      setTimeout(function () {
        window.location.reload();
      }, 2000);
    }
  }

  if (countdowns.length) {
    tick();
    setInterval(tick, 1000);
  }

  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.confirm(form.getAttribute("data-confirm"))) {
        event.preventDefault();
      }
    });
  });

  document.querySelectorAll(".flash").forEach(function (flash) {
    setTimeout(function () {
      flash.style.transition = "opacity .4s ease";
      flash.style.opacity = "0";
      setTimeout(function () {
        flash.remove();
      }, 400);
    }, 4200);
  });

  function formatBytes(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return Math.round(bytes / 1024) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  document.querySelectorAll("input[type=file][name=pet_photo]").forEach(function (input) {
    var preview = document.getElementById(input.id + "_preview");
    var placeholder = document.getElementById(input.id + "_placeholder");
    var title = document.getElementById(input.id + "_label");
    var hint = document.getElementById(input.id + "_name");
    if (!preview) return;

    var defaultLabel = input.getAttribute("data-default-label") || "Elegir foto";
    var defaultHint = input.getAttribute("data-default-hint") || "";
    var currentPhoto = input.getAttribute("data-current-photo");

    if (currentPhoto) {
      preview.src = currentPhoto;
      preview.hidden = false;
      if (placeholder) placeholder.hidden = true;
      if (title) title.textContent = "Foto actual";
      if (hint) hint.textContent = "Toca para cambiar";
    }

    input.addEventListener("change", function () {
      var file = input.files && input.files[0];
      if (!file) {
        preview.hidden = true;
        if (placeholder) placeholder.hidden = false;
        if (title) title.textContent = currentPhoto ? "Foto actual" : defaultLabel;
        if (hint) hint.textContent = currentPhoto ? "Toca para cambiar" : defaultHint;
        return;
      }
      preview.src = URL.createObjectURL(file);
      preview.hidden = false;
      if (placeholder) placeholder.hidden = true;
      if (title) title.textContent = file.name;
      if (hint) hint.textContent = formatBytes(file.size) + " · Toca para cambiar";
    });
  });

  if ("serviceWorker" in navigator && location.protocol.indexOf("http") === 0) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/static/sw.js").catch(function () {});
    });
  }
})();
