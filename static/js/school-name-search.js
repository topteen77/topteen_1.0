/**
 * Searchable school name field: type to filter suggestions, click to select,
 * or enter a custom school name.
 */
(function (global) {
  'use strict';

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function initSchoolNameSearch(inputId, suggestions) {
    var input = document.getElementById(inputId);
    if (!input || input.dataset.schoolSearchBound === '1') {
      return;
    }

    var wrap = input.closest('.school-search-wrap');
    if (!wrap) {
      return;
    }

    var list = Array.isArray(suggestions) ? suggestions.filter(Boolean) : [];
    var dropdown = document.createElement('div');
    dropdown.className = 'school-search-dropdown';
    dropdown.setAttribute('role', 'listbox');
    dropdown.hidden = true;
    wrap.appendChild(dropdown);

    var activeIndex = -1;

    function hideDropdown() {
      dropdown.hidden = true;
      activeIndex = -1;
    }

    function renderList(query) {
      var q = (query || '').trim().toLowerCase();
      var matches = q
        ? list.filter(function (name) {
            return name.toLowerCase().indexOf(q) !== -1;
          })
        : list.slice();
      matches = matches.slice(0, 12);

      if (!matches.length) {
        hideDropdown();
        return;
      }

      dropdown.innerHTML = matches.map(function (name, index) {
        return (
          '<button type="button" class="school-search-option" role="option" ' +
          'data-index="' + index + '" data-value="' + escapeHtml(name) + '">' +
          escapeHtml(name) +
          '</button>'
        );
      }).join('');
      dropdown.hidden = false;
      activeIndex = -1;
    }

    function selectValue(value) {
      input.value = value;
      hideDropdown();
      input.dispatchEvent(new Event('change', { bubbles: true }));
    }

    input.addEventListener('focus', function () {
      renderList(input.value);
    });

    input.addEventListener('input', function () {
      renderList(input.value);
    });

    input.addEventListener('keydown', function (event) {
      if (dropdown.hidden) {
        return;
      }
      var options = dropdown.querySelectorAll('.school-search-option');
      if (!options.length) {
        return;
      }

      if (event.key === 'ArrowDown') {
        event.preventDefault();
        activeIndex = Math.min(activeIndex + 1, options.length - 1);
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        activeIndex = Math.max(activeIndex - 1, 0);
      } else if (event.key === 'Enter' && activeIndex >= 0) {
        event.preventDefault();
        selectValue(options[activeIndex].getAttribute('data-value') || '');
        return;
      } else if (event.key === 'Escape') {
        hideDropdown();
        return;
      } else {
        return;
      }

      options.forEach(function (option, index) {
        option.classList.toggle('is-active', index === activeIndex);
      });
      if (activeIndex >= 0 && options[activeIndex]) {
        options[activeIndex].scrollIntoView({ block: 'nearest' });
      }
    });

    dropdown.addEventListener('mousedown', function (event) {
      var option = event.target.closest('.school-search-option');
      if (!option) {
        return;
      }
      event.preventDefault();
      selectValue(option.getAttribute('data-value') || '');
    });

    document.addEventListener('click', function (event) {
      if (!wrap.contains(event.target)) {
        hideDropdown();
      }
    });

    input.dataset.schoolSearchBound = '1';
  }

  global.initSchoolNameSearch = initSchoolNameSearch;
})(window);
