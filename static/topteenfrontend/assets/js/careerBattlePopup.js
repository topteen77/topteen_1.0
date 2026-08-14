(function () {
  const POPUP_STORAGE_KEY = "careerBattleExitPopupSeen";
  const POPUP_COOLDOWN_MS = 12 * 60 * 60 * 1000;
  const AUTO_SHOW_DELAY_MS = 10000;
  const RETRY_MS = 4000;

  const popup = document.getElementById("careerBattleExitPopup");
  if (!popup) {
    return;
  }

  const closeBtn = document.getElementById("careerBattlePopupClose");
  const laterBtn = document.getElementById("careerBattlePopupLater");
  let hasOpened = false;
  let pendingTimer = null;

  const canShowPopup = function () {
    const stored = localStorage.getItem(POPUP_STORAGE_KEY);
    if (!stored) {
      return true;
    }

    const shownAt = Number(stored);
    if (Number.isNaN(shownAt)) {
      return true;
    }

    return Date.now() - shownAt > POPUP_COOLDOWN_MS;
  };

  const isLoginInProgress = function () {
    if (window.__ttStudentLoginActive) {
      return true;
    }
    const login = document.getElementById("loginRequiredPopup");
    return !!(login && login.classList.contains("show"));
  };

  const closePopup = function () {
    popup.classList.add("hidden");
    popup.setAttribute("aria-hidden", "true");
  };

  const openPopup = function () {
    if (hasOpened || !canShowPopup()) {
      return;
    }
    if (isLoginInProgress()) {
      if (pendingTimer) {
        window.clearTimeout(pendingTimer);
      }
      pendingTimer = window.setTimeout(openPopup, RETRY_MS);
      return;
    }

    hasOpened = true;
    if (pendingTimer) {
      window.clearTimeout(pendingTimer);
      pendingTimer = null;
    }
    popup.classList.remove("hidden");
    popup.setAttribute("aria-hidden", "false");
    localStorage.setItem(POPUP_STORAGE_KEY, String(Date.now()));
  };

  window.__ttHideCareerBattlePopup = closePopup;

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
