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
  const errorEl = document.getElementById("streamDecisionFormError");
  const submitUrl = popup.dataset.submitUrl || "";
  const userId = popup.dataset.userId || "guest";
  const storageKey = "streamDecisionQuestionnaireMinimized:" + userId;
  const legacyStorageKey = storageKey;

  const questionKeys = [
    "preferred_stream",
    "confidence_level",
    "biggest_concern",
    "discussed_with_adult",
    "decision_readiness",
  ];

  const otherPanel = document.getElementById("streamDecisionOtherPanel");
  const otherTrigger = document.getElementById("preferredStreamOtherTrigger");

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

  const toggleOtherPanel = function () {
    if (!otherPanel || !otherTrigger || !form) {
      return;
    }
    const showOther = otherTrigger.checked;
    otherPanel.classList.toggle("d-none", !showOther);
    otherPanel.setAttribute("aria-hidden", showOther ? "false" : "true");
    if (!showOther) {
      form.querySelectorAll('input[name="preferred_stream_other"]').forEach(function (input) {
        input.checked = false;
      });
    }
  };

  const resolvePreferredStream = function () {
    if (!form) {
      return { stream: "", source: "", matchScore: "" };
    }
    const choice = form.querySelector('input[name="preferred_stream_choice"]:checked');
    if (!choice) {
      return { stream: "", source: "", matchScore: "" };
    }

    if (choice.value === "__OTHER__") {
      const otherChoice = form.querySelector('input[name="preferred_stream_other"]:checked');
      if (!otherChoice) {
        return { stream: "", source: "other", matchScore: "" };
      }
      return {
        stream: otherChoice.value,
        source: "other",
        matchScore: otherChoice.dataset.matchScore || "",
      };
    }

    const streamValue = choice.dataset.stream || choice.value.replace(/^suggested:/, "");
    return {
      stream: streamValue,
      source: "suggested",
      matchScore: choice.dataset.matchScore || "",
    };
  };

  const showPopup = function () {
    popup.classList.remove("d-none");
    popup.setAttribute("aria-hidden", "false");
    if (pendingWrap) {
      pendingWrap.classList.add("d-none");
    }
  };

  const hidePopup = function () {
    popup.classList.add("d-none");
    popup.setAttribute("aria-hidden", "true");
  };

  const showPendingButton = function () {
    if (pendingWrap) {
      pendingWrap.classList.remove("d-none");
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
    const preferred = resolvePreferredStream();
    const answers = {
      preferred_stream: preferred.stream,
      preferred_stream_source: preferred.source,
      preferred_stream_match_score: preferred.matchScore,
    };
    if (!form) {
      return answers;
    }
    questionKeys.slice(1).forEach(function (key) {
      const selected = form.querySelector('input[name="' + key + '"]:checked');
      answers[key] = selected ? selected.value : "";
    });
    return answers;
  };

  const validateAnswers = function (answers) {
    clearQuestionErrors();

    if (!String(answers.preferred_stream || "").trim()) {
      markQuestionInvalid("preferred_stream");
      if (answers.preferred_stream_source === "other") {
        return {
          valid: false,
          message: "Please choose one stream from the other combinations list.",
        };
      }
      return {
        valid: false,
        message: "Please select a suggested stream before submitting.",
      };
    }

    for (let i = 1; i < questionKeys.length; i += 1) {
      const key = questionKeys[i];
      if (!String(answers[key] || "").trim()) {
        markQuestionInvalid(key);
        if (key === "confidence_level") {
          return {
            valid: false,
            message: "Please answer question 2: How confident are you that these suggestions fit your career goals?",
          };
        }
        return {
          valid: false,
          message: "Please answer all questions before submitting.",
        };
      }
    }

    return { valid: true, message: "" };
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

  if (form) {
    form.querySelectorAll('input[name="preferred_stream_choice"]').forEach(function (input) {
      input.addEventListener("change", function () {
        hideError();
        clearQuestionErrors();
        toggleOtherPanel();
      });
    });

    form.querySelectorAll('input[type="radio"]').forEach(function (input) {
      input.addEventListener("change", function () {
        hideError();
        const question = input.closest(".stream-decision-question");
        if (question) {
          question.classList.remove("stream-decision-question-invalid");
        }
      });
    });

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      hideError();

      const answers = collectAnswers();
      const validation = validateAnswers(answers);
      if (!validation.valid) {
        showError(validation.message);
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

  if (readMinimizedState()) {
    hidePopup();
    showPendingButton();
  } else {
    showPopup();
  }
})();
