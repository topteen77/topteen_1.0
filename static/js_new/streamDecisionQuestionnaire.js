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

  const questionKeys = [
    "preferred_stream",
    "confidence_level",
    "biggest_concern",
    "discussed_with_adult",
    "decision_readiness",
  ];

  const otherPanel = document.getElementById("streamDecisionOtherPanel");
  const otherTrigger = document.getElementById("preferredStreamOtherTrigger");

  const toggleOtherPanel = function () {
    if (!otherPanel || !otherTrigger) {
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

    if (choice.value === "not_sure") {
      return {
        stream: "Not sure yet",
        source: "not_sure",
        matchScore: "0",
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
      window.localStorage.setItem(storageKey, "1");
    } catch (err) {
      /* ignore storage errors */
    }
  };

  const clearMinimizedState = function () {
    try {
      window.localStorage.removeItem(storageKey);
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

  const collectAnswers = function () {
    const preferred = resolvePreferredStream();
    const answers = {
      preferred_stream: preferred.stream,
      preferred_stream_source: preferred.source,
      preferred_stream_match_score: preferred.matchScore,
    };
    questionKeys.slice(1).forEach(function (key) {
      const selected = form.querySelector('input[name="' + key + '"]:checked');
      answers[key] = selected ? selected.value : "";
    });
    return answers;
  };

  const validateAnswers = function (answers) {
    if (!String(answers.preferred_stream || "").trim()) {
      return false;
    }
    return questionKeys.slice(1).every(function (key) {
      return String(answers[key] || "").trim().length > 0;
    });
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

  form.querySelectorAll('input[name="preferred_stream_choice"]').forEach(function (input) {
    input.addEventListener("change", toggleOtherPanel);
  });

  popup.addEventListener("click", function (event) {
    if (event.target === popup) {
      minimizePopup();
    }
  });

  if (form) {
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      hideError();

      const answers = collectAnswers();
      if (!validateAnswers(answers)) {
        if (answers.preferred_stream_source === "other" && !answers.preferred_stream) {
          showError("Please choose one stream from the other combinations list.");
        } else {
          showError("Please answer all questions before submitting.");
        }
        return;
      }

      if (!submitUrl) {
        showError("Unable to submit responses right now. Please refresh and try again.");
        return;
      }

      submitBtn.disabled = true;
      submitBtn.textContent = "Submitting...";

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
          hidePopup();
          popup.remove();
          if (pendingWrap) {
            pendingWrap.remove();
          }
        })
        .catch(function (error) {
          showError(error.message || "Unable to save your responses.");
          submitBtn.disabled = false;
          submitBtn.textContent = "Submit responses";
        });
    });
  }

  let wasMinimized = false;
  try {
    wasMinimized = window.localStorage.getItem(storageKey) === "1";
  } catch (err) {
    wasMinimized = false;
  }

  if (wasMinimized) {
    hidePopup();
    showPendingButton();
  } else {
    showPopup();
  }
})();
