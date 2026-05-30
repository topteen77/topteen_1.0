(function () {
  const AUTO_SHOW_DELAY_MS = 3000;

  const popup = document.getElementById("careerBattleExitPopup");
  if (!popup) {
    return;
  }

  const closeBtn = document.getElementById("careerBattlePopupClose");
  const laterBtn = document.getElementById("careerBattlePopupLater");
  let hasOpened = false;

  const openPopup = function () {
    if (hasOpened) {
      return;
    }

    hasOpened = true;
    popup.classList.remove("d-none");
    popup.setAttribute("aria-hidden", "false");
  };

  const closePopup = function () {
    popup.classList.add("d-none");
    popup.setAttribute("aria-hidden", "true");
  };

  if (closeBtn) {
    closeBtn.addEventListener("click", closePopup);
  }

  if (laterBtn) {
    laterBtn.addEventListener("click", closePopup);
  }

  popup.addEventListener("click", function (event) {
    if (event.target === popup) {
      closePopup();
    }
  });

  window.setTimeout(function () {
    openPopup();
  }, AUTO_SHOW_DELAY_MS);
})();
