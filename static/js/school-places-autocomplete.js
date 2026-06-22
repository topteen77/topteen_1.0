/**
 * Google Places Autocomplete for school name fields.
 * Requires Maps JavaScript API with Places library enabled on the API key.
 */
(function (global) {
  'use strict';

  if (!document.getElementById('school-places-autocomplete-css')) {
    var style = document.createElement('style');
    style.id = 'school-places-autocomplete-css';
    style.textContent = [
      '.pac-container {',
      '  z-index: 20000 !important;',
      '  border-radius: 10px;',
      '  border: 1px solid #e5e7eb;',
      '  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);',
      '  font-family: inherit;',
      '  margin-top: 6px;',
      '  overflow: hidden;',
      '}',
      '.pac-item {',
      '  padding: 10px 14px;',
      '  cursor: pointer;',
      '  font-size: 14px;',
      '  line-height: 1.4;',
      '}',
      '.pac-item:hover, .pac-item-selected {',
      '  background: #f3f0ff;',
      '}',
      '.pac-icon {',
      '  margin-top: 4px;',
      '}',
      '.pac-logo:after {',
      '  padding: 6px 10px;',
      '}',
    ].join('\n');
    document.head.appendChild(style);
  }

  function initSchoolPlacesAutocomplete(inputId, options) {
    options = options || {};
    var input = document.getElementById(inputId);
    if (!input || input.dataset.placesBound === '1') {
      return;
    }
    if (!global.google || !global.google.maps || !global.google.maps.places) {
      return;
    }

    var autocomplete = new global.google.maps.places.Autocomplete(input, {
      types: ['school'],
      componentRestrictions: { country: options.country || 'in' },
      fields: ['name', 'formatted_address'],
    });

    autocomplete.addListener('place_changed', function () {
      var place = autocomplete.getPlace();
      if (place && place.name) {
        input.value = place.name;
      } else if (place && place.formatted_address) {
        input.value = place.formatted_address.split(',')[0].trim();
      }
    });

    input.dataset.placesBound = '1';
  }

  global.initSchoolPlacesAutocomplete = initSchoolPlacesAutocomplete;

  global.initGoogleSchoolPlaces = function () {
    initSchoolPlacesAutocomplete('userschool', { country: 'in' });
    initSchoolPlacesAutocomplete('piSchool', { country: 'in' });
  };
})(window);
