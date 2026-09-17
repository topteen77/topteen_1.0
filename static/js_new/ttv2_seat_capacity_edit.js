(function () {
  "use strict";
  var STREAMS = ["pcm", "cbm", "comm", "hme", "hmb"];
  function csrfToken() {
    var el = document.querySelector("[name=csrfmiddlewaretoken]");
    if (el && el.value) return el.value;
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }
  function num(value) {
    var n = parseInt(value, 10);
    return isNaN(n) ? 100 : n;
  }
  function fillForm(btn) {
    var form = document.getElementById("ttv2SeatCapacityEditForm");
    if (!form || !btn) return;
    form.institute_id.value = btn.getAttribute("data-institute-id") || "";
    var nameEl = document.getElementById("ttv2SeatCapacityInstituteName");
    if (nameEl) nameEl.textContent = btn.getAttribute("data-institute-name") || "";
    STREAMS.forEach(function (stream) {
      ["11", "12"].forEach(function (cls) {
        var input = form.querySelector('[name="' + stream + "_" + cls + '"]');
        if (input) input.value = num(btn.getAttribute("data-" + stream + "-" + cls));
      });
    });
  }
  function updateVisibleCells(instituteId, data) {
    var bag11 = (data && data.class_11) || {};
    var bag12 = (data && data.class_12) || {};
    STREAMS.forEach(function (stream) {
      var v11 = bag11[stream] != null ? bag11[stream] : data[stream];
      var v12 = bag12[stream] != null ? bag12[stream] : data[stream + "_12"];
      document.querySelectorAll('[data-seat-capacity-value][data-class="11"][data-stream="' + stream + '"]').forEach(function (el) {
        el.textContent = v11;
      });
      document.querySelectorAll('[data-seat-capacity-value][data-class="12"][data-stream="' + stream + '"]').forEach(function (el) {
        el.textContent = v12;
      });
    });
    document.querySelectorAll('[data-seat-capacity-edit][data-institute-id="' + instituteId + '"]').forEach(function (btn) {
      STREAMS.forEach(function (stream) {
        btn.setAttribute("data-" + stream + "-11", bag11[stream] != null ? bag11[stream] : data[stream]);
        btn.setAttribute("data-" + stream + "-12", bag12[stream] != null ? bag12[stream] : data[stream + "_12"]);
      });
    });
  }
  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-seat-capacity-edit]");
    if (!btn) return;
    ev.preventDefault();
    fillForm(btn);
    var modalEl = document.getElementById("ttv2SeatCapacityEditModal");
    if (modalEl && window.bootstrap && bootstrap.Modal) {
      bootstrap.Modal.getOrCreateInstance(modalEl).show();
    }
  });
  document.addEventListener("submit", function (ev) {
    var form = ev.target;
    if (!form || form.id !== "ttv2SeatCapacityEditForm") return;
    ev.preventDefault();
    var instituteId = form.institute_id.value;
    var fd = new FormData(form);
    fd.append("csrfmiddlewaretoken", csrfToken());
    fetch("/institute/update_seat_capacity/", {
      method: "POST",
      body: fd,
      headers: { "X-Requested-With": "XMLHttpRequest" },
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data || !data.success) throw new Error((data && data.error) || "Save failed");
        updateVisibleCells(instituteId, data.data || {});
        var modalEl = document.getElementById("ttv2SeatCapacityEditModal");
        if (modalEl && window.bootstrap && bootstrap.Modal) {
          var inst = bootstrap.Modal.getInstance(modalEl);
          if (inst) inst.hide();
        }
      })
      .catch(function (err) {
        window.alert(err.message || "Could not save seat capacity.");
      });
  });
})();
