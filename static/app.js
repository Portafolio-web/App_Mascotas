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

  if ("serviceWorker" in navigator && location.protocol.indexOf("http") === 0) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/static/sw.js").catch(function () {});
    });
  }
})();
