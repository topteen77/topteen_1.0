(function () {
  const popup = document.getElementById("streamDecisionPopup");
  if (!popup) {
    return;
  }

  const mountToBody = function (node) {
    if (node && node.parentElement !== document.body) {
      document.body.appendChild(node);
    }
  };

  mountToBody(popup);

  const pendingWrap = document.getElementById("streamDecisionPendingWrap");
  const pendingBtn = document.getElementById("streamDecisionPendingBtn");
  if (pendingWrap) {
    mountToBody(pendingWrap);
  } else if (pendingBtn) {
    mountToBody(pendingBtn);
  }
  const minimizeBtn = document.getElementById("streamDecisionPopupMinimize");
  const laterBtn = document.getElementById("streamDecisionPopupLater");
  const form = document.getElementById("streamDecisionQuestionnaireForm");
  const submitBtn = document.getElementById("streamDecisionSubmitBtn");
  const nextBtn = document.getElementById("streamDecisionNextBtn");
  const backBtn = document.getElementById("streamDecisionBackBtn");
  const stepLabel = document.getElementById("streamDecisionStepLabel");
  const errorEl = document.getElementById("streamDecisionFormError");
  const step1Question = form ? form.querySelector('.stream-decision-question[data-step="1"]') : null;
  const step2Question = document.getElementById("streamDecisionStreamQuestion");
  const submitUrl = popup.dataset.submitUrl || "";
  const userId = popup.dataset.userId || "guest";
  const storageKey = "streamDecisionQuestionnaireMinimized:" + userId;
  const legacyStorageKey = storageKey;
  const shakeDelayMs = 20000;
  const prefersReducedMotion =
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let pendingShakeTimer = null;
  let currentStep = 1;

  const questionKeys = ["reports_reviewed", "preferred_stream"];
  const reportsReviewedNo = "No, not yet";

  const clearReportsReviewedSelection = function () {
    if (!form) {
      return;
    }
    form.querySelectorAll('input[name="reports_reviewed"]').forEach(function (input) {
      input.checked = false;
    });
  };

  const hasDeclinedReportReview = function () {
    const selected = form && form.querySelector('input[name="reports_reviewed"]:checked');
    return Boolean(selected && selected.value === reportsReviewedNo);
  };

  const minimizeBecauseReportsNotReviewed = function () {
    clearReportsReviewedSelection();
    minimizePopup();
  };

  const readMinimizedState = function () {
    try {
      if (window.sessionStorage.getItem(storageKey) === "1") {
        return true;
      }
      if (window.localStorage.getItem(legacyStorageKey) === "1") {
        window.localStorage.removeItem(legacyStorageKey);
      }
    } catch (err) {
      /* ignore storage errors */
    }
    return false;
  };

  const goToStep = function (step) {
    currentStep = step;

    if (step1Question) {
      const showStep1 = step === 1;
      step1Question.classList.toggle("d-none", !showStep1);
      step1Question.setAttribute("aria-hidden", showStep1 ? "false" : "true");
    }

    if (step2Question) {
      const showStep2 = step === 2;
      step2Question.classList.toggle("d-none", !showStep2);
      step2Question.setAttribute("aria-hidden", showStep2 ? "false" : "true");
    }

    if (nextBtn) {
      nextBtn.classList.toggle("d-none", step !== 1);
    }
    if (backBtn) {
      backBtn.classList.toggle("d-none", step !== 2);
    }
    if (submitBtn) {
      submitBtn.classList.toggle("d-none", step !== 2);
    }
    if (stepLabel) {
      stepLabel.textContent = "Step " + step + " of 2";
    }

    hideError();
    clearQuestionErrors();
  };

  const validateStep = function (step) {
    clearQuestionErrors();

    if (step === 1) {
      const selected = form && form.querySelector('input[name="reports_reviewed"]:checked');
      if (!selected) {
        markQuestionInvalid("reports_reviewed");
        return {
          valid: false,
          message: "Please answer question 1: Have you reviewed your reports thoroughly?",
        };
      }
      if (selected.value === reportsReviewedNo) {
        minimizeBecauseReportsNotReviewed();
        return { valid: false, message: "" };
      }
      return { valid: true, message: "" };
    }

    if (step === 2) {
      const selected = form && form.querySelector('input[name="preferred_stream"]:checked');
      if (!selected) {
        markQuestionInvalid("preferred_stream");
        return {
          valid: false,
          message: "Please select your most suitable stream before submitting.",
        };
      }
      return { valid: true, message: "" };
    }

    return { valid: true, message: "" };
  };

  const isPendingButtonVisible = function () {
    if (!pendingWrap) {
      return false;
    }
    if (pendingWrap.classList.contains("d-none")) {
      return false;
    }
    return window.getComputedStyle(pendingWrap).display !== "none";
  };

  const clearPendingShakeTimer = function () {
    if (pendingShakeTimer) {
      clearTimeout(pendingShakeTimer);
      pendingShakeTimer = null;
    }
  };

  const clearPendingShake = function () {
    clearPendingShakeTimer();
    if (pendingWrap) {
      pendingWrap.classList.remove("stream-decision-pending-shake");
    }
  };

  const isShakeAnimation = function (animationName) {
    return (
      animationName === "streamDecisionPendingBtnShake" ||
      (animationName && animationName.indexOf("streamDecisionPendingBtnShake") !== -1)
    );
  };

  const triggerPendingShake = function () {
    if (!pendingWrap || !pendingBtn || !isPendingButtonVisible() || prefersReducedMotion) {
      return;
    }
    let shakeFinished = false;
    const finishShake = function () {
      if (shakeFinished) {
        return;
      }
      shakeFinished = true;
      pendingWrap.classList.remove("stream-decision-pending-shake");
      if (pendingBtn) {
        pendingBtn.removeEventListener("animationend", onShakeEnd);
      }
    };

    const onShakeEnd = function (event) {
      if (event.target !== pendingBtn || !isShakeAnimation(event.animationName)) {
        return;
      }
      finishShake();
    };

    pendingWrap.classList.remove("stream-decision-pending-shake");
    void pendingBtn.offsetWidth;
    pendingWrap.classList.add("stream-decision-pending-shake");
    pendingBtn.addEventListener("animationend", onShakeEnd);
    setTimeout(finishShake, 900);
  };

  const schedulePendingShake = function () {
    clearPendingShakeTimer();
    if (!pendingWrap || prefersReducedMotion) {
      return;
    }
    pendingShakeTimer = setTimeout(function () {
      pendingShakeTimer = null;
      if (!isPendingButtonVisible()) {
        return;
      }
      triggerPendingShake();
      schedulePendingShake();
    }, shakeDelayMs);
  };

  const showPopup = function () {
    clearPendingShake();
    popup.classList.remove("d-none");
    popup.setAttribute("aria-hidden", "false");
    if (pendingWrap) {
      pendingWrap.classList.add("d-none");
    }
    goToStep(1);
  };

  const hidePopup = function () {
    popup.classList.add("d-none");
    popup.setAttribute("aria-hidden", "true");
  };

  const showPendingButton = function () {
    if (pendingWrap) {
      pendingWrap.classList.remove("d-none");
      schedulePendingShake();
    }
  };

  const minimizePopup = function () {
    hidePopup();
    showPendingButton();
    try {
      window.sessionStorage.setItem(storageKey, "1");
      window.localStorage.removeItem(legacyStorageKey);
    } catch (err) {
      /* ignore storage errors */
    }
  };

  const clearMinimizedState = function () {
    clearPendingShake();
    try {
      window.sessionStorage.removeItem(storageKey);
      window.localStorage.removeItem(legacyStorageKey);
    } catch (err) {
      /* ignore storage errors */
    }
    if (pendingWrap) {
      pendingWrap.classList.add("d-none");
    }
  };

  const showError = function (message) {
    if (!errorEl) {
      return;
    }
    errorEl.textContent = message;
    errorEl.classList.remove("d-none");
  };

  const hideError = function () {
    if (!errorEl) {
      return;
    }
    errorEl.textContent = "";
    errorEl.classList.add("d-none");
  };

  const clearQuestionErrors = function () {
    if (!form) {
      return;
    }
    form.querySelectorAll(".stream-decision-question").forEach(function (question) {
      question.classList.remove("stream-decision-question-invalid");
    });
  };

  const markQuestionInvalid = function (questionKey) {
    if (!form) {
      return;
    }
    const question = form.querySelector('.stream-decision-question[data-question="' + questionKey + '"]');
    if (question) {
      question.classList.add("stream-decision-question-invalid");
    }
  };

  const collectAnswers = function () {
    const answers = {};
    if (!form) {
      return answers;
    }
    questionKeys.forEach(function (key) {
      const selected = form.querySelector('input[name="' + key + '"]:checked');
      answers[key] = selected ? selected.value : "";
    });
    return answers;
  };

  const getCsrfToken = function () {
    const match = document.cookie.match(/(^| )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[2]) : "";
  };

  if (minimizeBtn) {
    minimizeBtn.addEventListener("click", minimizePopup);
  }

  if (laterBtn) {
    laterBtn.addEventListener("click", minimizePopup);
  }

  if (pendingBtn) {
    pendingBtn.addEventListener("click", showPopup);
  }

  if (nextBtn) {
    nextBtn.addEventListener("click", function () {
      const validation = validateStep(1);
      if (!validation.valid) {
        showError(validation.message);
        return;
      }
      goToStep(2);
    });
  }

  if (backBtn) {
    backBtn.addEventListener("click", function () {
      goToStep(1);
    });
  }

  if (form) {
    form.querySelectorAll('input[type="radio"]').forEach(function (input) {
      input.addEventListener("change", function () {
        hideError();
        const question = input.closest(".stream-decision-question");
        if (question) {
          question.classList.remove("stream-decision-question-invalid");
        }

        if (
          input.name === "reports_reviewed" &&
          input.value === reportsReviewedNo &&
          input.checked
        ) {
          minimizeBecauseReportsNotReviewed();
        }
      });
    });

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      hideError();

      if (currentStep === 1) {
        const stepOneValidation = validateStep(1);
        if (!stepOneValidation.valid) {
          showError(stepOneValidation.message);
          return;
        }
        goToStep(2);
        return;
      }

      const stepTwoValidation = validateStep(2);
      if (!stepTwoValidation.valid) {
        showError(stepTwoValidation.message);
        return;
      }

      const answers = collectAnswers();

      if (answers.reports_reviewed === reportsReviewedNo) {
        minimizeBecauseReportsNotReviewed();
        return;
      }

      if (!submitUrl) {
        showError("Unable to submit responses right now. Please refresh and try again.");
        return;
      }

      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = "Submitting...";
      }

      fetch(submitUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify({ answers: answers }),
      })
        .then(function (response) {
          return response.json().then(function (payload) {
            return { ok: response.ok, payload: payload };
          });
        })
        .then(function (result) {
          if (!result.ok) {
            throw new Error(
              (result.payload && result.payload.message) ||
                "Unable to save your responses."
            );
          }

          clearMinimizedState();
          window.location.reload();
        })
        .catch(function (error) {
          showError(error.message || "Unable to save your responses.");
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = "Submit responses";
          }
        });
    });
  }

  goToStep(1);

  if (readMinimizedState()) {
    hidePopup();
    showPendingButton();
  } else {
    showPopup();
  }
})();
