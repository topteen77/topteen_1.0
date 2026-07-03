(function () {
  function initInfoToggle() {
    document.querySelectorAll("#cmm-info-toggle").forEach(function (btn) {
      var panelId = btn.getAttribute("aria-controls");
      var panel = panelId ? document.getElementById(panelId) : btn.parentElement && btn.parentElement.querySelector(".cmm-help-panel");
      if (!panel) return;
      btn.addEventListener("click", function () {
        var open = panel.hasAttribute("hidden");
        if (open) {
          panel.removeAttribute("hidden");
          btn.setAttribute("aria-expanded", "true");
        } else {
          panel.setAttribute("hidden", "");
          btn.setAttribute("aria-expanded", "false");
        }
      });
    });
  }

  function initCourseTypeAjax() {
    var typeSelect = document.getElementById("id_course_type_key");
    var courseSelect = document.getElementById("id_course_id");
    if (!typeSelect || !courseSelect) return;

    typeSelect.addEventListener("change", function () {
      var key = typeSelect.value;
      courseSelect.innerHTML = "<option value=\"\">Loading…</option>";
      if (!key) {
        courseSelect.innerHTML = "<option value=\"\">— Select course type first —</option>";
        return;
      }
      var base = window.location.pathname.replace(/\/generate\/?$/, "");
      fetch(base + "/courses-by-type/?course_type_key=" + encodeURIComponent(key), {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      })
        .then(function (r) {
          return r.json();
        })
        .then(function (data) {
          var opts = "<option value=\"\">— Select —</option>";
          (data.courses || []).forEach(function (c) {
            opts += '<option value="' + c.id + '">' + escapeHtml(c.name) + "</option>";
          });
          courseSelect.innerHTML = opts;
        })
        .catch(function () {
          courseSelect.innerHTML = "<option value=\"\">— Error loading courses —</option>";
        });
    });
  }

  function escapeHtml(s) {
    var d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      initInfoToggle();
      initCourseTypeAjax();
    });
  } else {
    initInfoToggle();
    initCourseTypeAjax();
  }
})();
