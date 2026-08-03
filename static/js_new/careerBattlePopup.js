(function () {
  const AUTO_SHOW_DELAY_MS = 20000;
  const RETRY_MS = 4000;

  const popup = document.getElementById("careerBattleExitPopup");
  if (!popup) {
    return;
  }

  const closeBtn = document.getElementById("careerBattlePopupClose");
  const laterBtn = document.getElementById("careerBattlePopupLater");
  let hasOpened = false;
  let pendingTimer = null;

  const isLoginInProgress = function () {
    if (window.__ttStudentLoginActive) {
      return true;
    }
    const login = document.getElementById("loginRequiredPopup");
    return !!(login && login.classList.contains("show"));
  };

  const closePopup = function () {
    popup.classList.add("d-none");
    popup.setAttribute("aria-hidden", "true");
  };

  const openPopup = function () {
    if (hasOpened) {
      return;
    }
    // Never interrupt / stack over Sign In / Create Account
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
    popup.classList.remove("d-none");
    popup.setAttribute("aria-hidden", "false");
  };

  // Allow login popup to dismiss Career Battle immediately
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
