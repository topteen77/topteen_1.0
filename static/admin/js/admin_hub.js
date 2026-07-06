(function () {
  "use strict";

  function initHubSearch() {
    var input = document.getElementById("tt-admin-hub-search");
    var sectionsRoot = document.getElementById("tt-admin-hub-sections");
    var noResults = document.getElementById("tt-admin-hub-no-results");
    if (!input || !sectionsRoot) {
      return;
    }

    function filterItems() {
      var query = (input.value || "").trim().toLowerCase();
      var visibleItems = 0;
      var sections = sectionsRoot.querySelectorAll("[data-hub-section]");

      sections.forEach(function (section) {
        var sectionVisible = 0;
        section.querySelectorAll("[data-hub-item]").forEach(function (item) {
          var haystack = item.getAttribute("data-search") || item.textContent.toLowerCase();
          var show = !query || haystack.indexOf(query) !== -1;
          item.hidden = !show;
          if (show) {
            sectionVisible += 1;
            visibleItems += 1;
          }
        });
        section.hidden = sectionVisible === 0;
      });

      if (noResults) {
        noResults.hidden = visibleItems > 0 || !query;
      }
    }

    input.addEventListener("input", filterItems);
    input.addEventListener("search", filterItems);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initHubSearch);
  } else {
    initHubSearch();
  }
})();
