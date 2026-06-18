(function () {
  function initLevelBandMinPointSliders() {
    var milestonesEl = document.getElementById('level-band-milestones');
    if (!milestonesEl) return;

    var milestones = JSON.parse(milestonesEl.textContent);
    if (!milestones.length) return;

    var minPts = milestones[0];
    var maxPts = milestones[milestones.length - 1];

    function nearestIndex(value) {
      var parsed = parseInt(value, 10);
      if (isNaN(parsed)) return 0;
      parsed = Math.max(minPts, Math.min(maxPts, parsed));
      var bestIdx = 0;
      var bestDiff = Math.abs(milestones[0] - parsed);
      for (var i = 1; i < milestones.length; i++) {
        var diff = Math.abs(milestones[i] - parsed);
        if (diff < bestDiff) {
          bestDiff = diff;
          bestIdx = i;
        }
      }
      return bestIdx;
    }

    function enhanceMinPointsInput(input) {
      if (input.dataset.sliderReady === '1') return;
      input.dataset.sliderReady = '1';

      input.min = String(minPts);
      input.max = String(maxPts);

      var wrap = document.createElement('div');
      wrap.className = 'level-band-min-points-wrap';
      input.parentNode.insertBefore(wrap, input);
      wrap.appendChild(input);

      var slider = document.createElement('input');
      slider.type = 'range';
      slider.min = '0';
      slider.max = String(milestones.length - 1);
      slider.step = '1';
      slider.value = String(nearestIndex(input.value));
      slider.title = 'Min ' + minPts + ' — Max ' + maxPts;
      wrap.insertBefore(slider, input);

      var td = input.closest('td');
      if (td) td.classList.add('level-band-min-points-cell');

      function syncFromSlider() {
        var idx = parseInt(slider.value, 10);
        input.value = milestones[idx];
      }

      function syncFromInput() {
        var idx = nearestIndex(input.value);
        slider.value = String(idx);
        input.value = milestones[idx];
      }

      slider.addEventListener('input', syncFromSlider);
      slider.addEventListener('change', syncFromSlider);
      input.addEventListener('change', syncFromInput);
      input.addEventListener('blur', syncFromInput);

      syncFromInput();
    }

    document
      .querySelectorAll('input.dashboard-level-band-min-points-input, input[name$="-min_points"], input#id_min_points')
      .forEach(enhanceMinPointsInput);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initLevelBandMinPointSliders);
  } else {
    initLevelBandMinPointSliders();
  }
})();
