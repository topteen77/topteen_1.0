(function () {
  "use strict";

  var DEBOUNCE_MS = 250;

  function initSkilllabCourseFinder() {
    var wrap = document.getElementById("sl-finder-search-wrap");
    if (!wrap) return;

    var form = document.getElementById("sl-finder-form");
    var input = document.getElementById("sl-finder-search");
    var suggest = document.getElementById("sl-finder-suggest");
    var hiddenQ = document.getElementById("sl-finder-q-value");
    var chipWrap = document.getElementById("sl-finder-chip-wrap");
    var chipText = document.getElementById("sl-finder-chip-text");
    var chipClose = document.getElementById("sl-finder-chip-close");
    var inputWrap = document.getElementById("sl-finder-input-wrap");
    var autocompleteUrl = wrap.getAttribute("data-autocomplete-url") || "";

    var suggestTimer = null;
    var blurTimer = null;
    var selectedIndex = -1;
    var currentResults = [];

    function escapeHtml(text) {
      return String(text || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/"/g, "&quot;");
    }

    function hasChip() {
      return chipWrap && chipWrap.classList.contains("is-visible");
    }

    function showChip(value) {
      var text = (value || "").trim();
      if (!text || !chipWrap || !chipText || !hiddenQ || !inputWrap) return;
      chipText.textContent = text;
      hiddenQ.value = text;
      chipWrap.classList.add("is-visible");
      inputWrap.classList.add("is-hidden");
      if (input) {
        input.value = "";
        input.setAttribute("aria-expanded", "false");
      }
      hideSuggest();
    }

    function clearChip() {
      if (!chipWrap || !chipText || !hiddenQ || !inputWrap) return;
      chipText.textContent = "";
      hiddenQ.value = "";
      chipWrap.classList.remove("is-visible");
      inputWrap.classList.remove("is-hidden");
      if (input) {
        input.value = "";
        input.focus();
      }
    }

    function hideSuggest() {
      if (!suggest) return;
      suggest.hidden = true;
      suggest.innerHTML = "";
      currentResults = [];
      selectedIndex = -1;
      if (input) input.setAttribute("aria-expanded", "false");
    }

    function renderSuggest(results) {
      if (!suggest) return;
      currentResults = results || [];
      selectedIndex = currentResults.length > 0 ? 0 : -1;

      if (!currentResults.length) {
        suggest.innerHTML =
          '<li class="sl-finder-search__suggest-empty" role="presentation">No courses found</li>';
        suggest.hidden = false;
        if (input) input.setAttribute("aria-expanded", "true");
        return;
      }

      suggest.innerHTML = currentResults
        .map(function (item, index) {
          var text = item.text || item.value || "";
          var active = index === selectedIndex ? " is-active" : "";
          return (
            '<li class="sl-finder-search__suggest-item' +
            active +
            '" role="option" data-value="' +
            escapeHtml(text) +
            '" aria-selected="' +
            (index === selectedIndex ? "true" : "false") +
            '">' +
            escapeHtml(text) +
            "</li>"
          );
        })
        .join("");
      suggest.hidden = false;
      if (input) input.setAttribute("aria-expanded", "true");
    }

    function fetchSuggestions(query, callback) {
      if (!autocompleteUrl || !query) {
        callback([]);
        return;
      }
      fetch(
        autocompleteUrl + "?q=" + encodeURIComponent(query) + "&limit=10",
        { headers: { Accept: "application/json" } }
      )
        .then(function (res) {
          return res.ok ? res.json() : { results: [] };
        })
        .then(function (data) {
          callback((data && data.results) || []);
        })
        .catch(function () {
          callback([]);
        });
    }

    function selectCourse(value) {
      showChip(value);
    }

    function syncHiddenOnSubmit() {
      if (!hiddenQ || !input) return;
      if (!hasChip()) {
        hiddenQ.value = (input.value || "").trim();
      }
    }

    if (chipClose) {
      chipClose.addEventListener("click", function (e) {
        e.preventDefault();
        clearChip();
      });
    }

    if (form) {
      form.addEventListener("submit", syncHiddenOnSubmit);
    }

    if (!input || !suggest) return;

    input.addEventListener("input", function () {
      if (suggestTimer) clearTimeout(suggestTimer);
      var query = (input.value || "").trim();
      if (!query) {
        hideSuggest();
        return;
      }
      suggestTimer = setTimeout(function () {
        suggestTimer = null;
        fetchSuggestions(query, renderSuggest);
      }, DEBOUNCE_MS);
    });

    input.addEventListener("focus", function () {
      if (blurTimer) clearTimeout(blurTimer);
      blurTimer = null;
      var query = (input.value || "").trim();
      if (query && currentResults.length) {
        suggest.hidden = false;
        input.setAttribute("aria-expanded", "true");
      }
    });

    input.addEventListener("blur", function () {
      blurTimer = setTimeout(function () {
        blurTimer = null;
        hideSuggest();
      }, 180);
    });

    suggest.addEventListener("mousedown", function (e) {
      var item = e.target.closest(".sl-finder-search__suggest-item");
      if (!item) return;
      e.preventDefault();
      selectCourse(item.getAttribute("data-value") || "");
    });

    input.addEventListener("keydown", function (e) {
      var items = suggest.querySelectorAll(".sl-finder-search__suggest-item");
      if (e.key === "Escape") {
        hideSuggest();
        return;
      }
      if (e.key === "ArrowDown" && items.length) {
        e.preventDefault();
        selectedIndex = (selectedIndex + 1) % items.length;
        renderSuggest(currentResults);
        items = suggest.querySelectorAll(".sl-finder-search__suggest-item");
        if (items[selectedIndex]) items[selectedIndex].scrollIntoView({ block: "nearest" });
        return;
      }
      if (e.key === "ArrowUp" && items.length) {
        e.preventDefault();
        selectedIndex = selectedIndex <= 0 ? items.length - 1 : selectedIndex - 1;
        renderSuggest(currentResults);
        items = suggest.querySelectorAll(".sl-finder-search__suggest-item");
        if (items[selectedIndex]) items[selectedIndex].scrollIntoView({ block: "nearest" });
        return;
      }
      if (e.key === "Enter" && !suggest.hidden && items.length && selectedIndex >= 0) {
        e.preventDefault();
        selectCourse(items[selectedIndex].getAttribute("data-value") || "");
      }
    });

    var initialQ = (wrap.getAttribute("data-initial-q") || hiddenQ.value || "").trim();
    if (initialQ) {
      showChip(initialQ);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSkilllabCourseFinder);
  } else {
    initSkilllabCourseFinder();
  }
})();
