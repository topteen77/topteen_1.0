(function () {
      let currentIndex = 0;
      const answers = {}; // key: question index (0-based), value: 'A' | 'B' | 'C' | 'D'

      const progressLabel = document.getElementById("lpProgressLabel");
      const progressBar = document.getElementById("lpProgressBar");
      const questionContainer = document.getElementById("lpQuestionContainer");
      const questionNav = document.getElementById("lpQuestionNav");
      const prevBtn = document.getElementById("lpPrevBtn");
      const nextBtn = document.getElementById("lpNextBtn");
      const completeBadge = document.getElementById("lpCompleteBadge");
      const resultSummary = document.getElementById("lpResultSummary");
      const profileTab = document.getElementById("lp-profile-tab");
      const tabTooltip = document.getElementById("lpTabTooltip");
      const analyzeOverlay = document.getElementById("lpAnalyzeOverlay");
      const analyzeText = document.getElementById("lpAnalyzeText");
      const analyzeSubtext = document.getElementById("lpAnalyzeSubtext");
      const validationEl = document.getElementById("lpValidationMessage");
      let testCompleted = false;

      function showValidation(message) {
        if (!validationEl) return;
        validationEl.textContent = message;
        validationEl.removeAttribute("hidden");
        validationEl.classList.add("lp-validation-visible");
      }

      function clearValidation() {
        if (!validationEl) return;
        validationEl.textContent = "";
        validationEl.setAttribute("hidden", "");
        validationEl.classList.remove("lp-validation-visible");
      }

      function updateProgress() {
        const total = questions.length;
        const answeredCount = Object.keys(answers).length;
        const percent = Math.round((answeredCount / total) * 100);
        progressLabel.textContent = `Question ${currentIndex + 1} of ${total}`;
        progressBar.style.width = `${Math.max(percent, 5)}%`;
        progressBar.setAttribute("aria-valuenow", String(percent));

        if (answeredCount === total) {
          completeBadge.classList.add("lp-visible");
        } else {
          completeBadge.classList.remove("lp-visible");
        }
      }

      function renderQuestionNav() {
        questionNav.innerHTML = "";
        questions.forEach((_, idx) => {
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = "lp-question-nav-btn";
          btn.textContent = String(idx + 1);

          if (answers[idx] != null) {
            btn.classList.add("lp-answered");
          }
          if (idx === currentIndex) {
            btn.classList.add("lp-current");
          }

          btn.addEventListener("click", () => {
            currentIndex = idx;
            renderQuestion();
          });

          questionNav.appendChild(btn);
        });
      }

      function renderQuestion() {
        const q = questions[currentIndex];
        const selected = answers[currentIndex] || null;

        const wrapper = document.createElement("div");

        const titleEl = document.createElement("h2");
        titleEl.className = "lp-question-title";
        titleEl.textContent = q.title;
        wrapper.appendChild(titleEl);

        const textEl = document.createElement("p");
        textEl.className = "lp-question-text";
        textEl.textContent = q.text || "";
        wrapper.appendChild(textEl);

        const listEl = document.createElement("ul");
        listEl.className = "lp-options-list";

        ["A", "B", "C", "D"].forEach(function (letter) {
          const li = document.createElement("li");
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = "lp-option-btn";
          if (selected === letter) {
            btn.classList.add("lp-selected");
          }
          btn.dataset.option = letter;

          var badge = document.createElement("span");
          badge.className = "lp-option-letter";
          badge.textContent = letter;

          var textSpan = document.createElement("span");
          textSpan.className = "lp-option-text";
          textSpan.textContent = q.options[letter] || "";

          var checkIcon = document.createElement("span");
          checkIcon.className = "lp-option-check";
          checkIcon.innerHTML = "<i class='bx bx-check'></i>";

          btn.appendChild(badge);
          btn.appendChild(textSpan);
          btn.appendChild(checkIcon);

          btn.addEventListener("click", () => {
            answers[currentIndex] = letter;
            clearValidation();
            renderQuestion();
            renderQuestionNav();
            updateProgress();
          });

          li.appendChild(btn);
          listEl.appendChild(li);
        });

        wrapper.appendChild(listEl);
        questionContainer.innerHTML = "";
        questionContainer.appendChild(wrapper);

        prevBtn.disabled = currentIndex === 0;
        nextBtn.textContent = currentIndex === questions.length - 1 ? "Finish" : "Next";
      }

      function showTooltip() {
        if (!tabTooltip) return;
        tabTooltip.classList.add("lp-tooltip-visible");
        setTimeout(function () {
          tabTooltip.classList.remove("lp-tooltip-visible");
        }, 2200);
      }

      function enableProfileTab() {
        testCompleted = true;
        if (profileTab) {
          profileTab.classList.remove("lp-profile-tab-inactive");
          profileTab.setAttribute("data-bs-toggle", "pill");
        }
        var li = document.getElementById("lpProfileTabLi");
        if (li) li.classList.remove("lp-tab-locked");
      }

      function getCsrfToken() {
        var token = typeof window.lpCsrfToken !== "undefined" ? window.lpCsrfToken : null;
        if (!token && document.cookie) {
          var m = document.cookie.match(/\bcsrftoken=([^;]+)/);
          if (m) token = m[1];
        }
        return token || "";
      }

      function saveResultsToServer(counts, primary, profileName, profileSummary, onUnauthorized) {
        var url = typeof window.lpAssessmentSubmitUrl !== "undefined" ? window.lpAssessmentSubmitUrl : null;
        if (!url) return Promise.resolve();
        var answersForServer = {};
        Object.keys(answers).forEach(function (idx) {
          answersForServer[String(idx)] = answers[idx];
        });
        var body = JSON.stringify({
          answers: answersForServer,
          counts: counts,
          primary: primary,
          profile_name: profileName,
          profile_summary: profileSummary || ""
        });
        var headers = { "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest" };
        var csrf = getCsrfToken();
        if (csrf) headers["X-CSRFToken"] = csrf;
        return fetch(url, {
          method: "POST",
          headers: headers,
          body: body,
          credentials: "same-origin"
        }).then(function (res) {
          if (res.status === 401 && typeof onUnauthorized === "function") {
            onUnauthorized();
          }
          return res;
        });
      }

      function buildResults(skipOverlay) {
        const counts = { A: 0, B: 0, C: 0, D: 0 };
        Object.values(answers).forEach(function (letter) {
          if (counts[letter] != null) counts[letter]++;
        });

        let top = "A";
        ["B", "C", "D"].forEach(function (letter) {
          if (counts[letter] > counts[top]) {
            top = letter;
          }
        });

        const profile = profiles[top];
        if (!profile || !resultSummary) return;

        var profileName = profile.name || "";
        var profileSummary = profile.summary || "";
        if (!skipOverlay) {
          saveResultsToServer(counts, top, profileName, profileSummary, function () {
            var loginUrl = "/user/login/";
            var nextUrl = encodeURIComponent(window.location.href);
            window.location.href = (loginUrl.indexOf("?") >= 0 ? loginUrl + "&" : loginUrl + "?") + "next=" + nextUrl;
          });
        }

        if (profileTab && window.bootstrap && window.bootstrap.Tab) {
          var tab = new window.bootstrap.Tab(profileTab);
          tab.show();
        }

        function showResultUI() {
          if (analyzeOverlay) {
            analyzeOverlay.classList.remove("lp-analyze-visible");
          }
          resultSummary.innerHTML = "";
          var badge = document.createElement("div");
          badge.className = "lp-results-badge";
          badge.innerHTML = "<i class='bx bx-star'></i><span>Your primary learning style</span>";
          var typeEl = document.createElement("div");
          typeEl.className = "lp-results-type";
          typeEl.innerHTML = profile.name || "";
          var summaryEl = document.createElement("p");
          summaryEl.className = "lp-results-summary";
          summaryEl.innerHTML = profile.summary || "";
          var countsEl = document.createElement("p");
          countsEl.className = "lp-results-counts";
          countsEl.textContent =
            "Your answers: A = " + counts.A + ", B = " + counts.B + ", C = " + counts.C + ", D = " + counts.D + ". " +
            "Use these together with the detailed guide below to understand your full learning profile.";
          resultSummary.appendChild(badge);
          resultSummary.appendChild(typeEl);
          resultSummary.appendChild(summaryEl);
          resultSummary.appendChild(countsEl);
          enableProfileTab();
        }

        if (skipOverlay) {
          showResultUI();
        } else {
          if (analyzeOverlay) {
            analyzeOverlay.classList.add("lp-analyze-visible");
          }
          if (analyzeText) analyzeText.textContent = "AI analyzing your responses...";
          if (analyzeSubtext) analyzeSubtext.textContent = "Optimizing your result";
          setTimeout(function () {
            if (analyzeText) analyzeText.textContent = "Getting your result ready...";
            if (analyzeSubtext) analyzeSubtext.textContent = "Almost there";
          }, 1000);
          setTimeout(showResultUI, 2500);
        }
      }

      prevBtn.addEventListener("click", () => {
        if (currentIndex > 0) {
          currentIndex--;
          clearValidation();
          renderQuestion();
          renderQuestionNav();
          updateProgress();
        }
      });

      nextBtn.addEventListener("click", () => {
        const answeredCount = Object.keys(answers).length;
        const isLastQuestion = currentIndex === questions.length - 1;

        if (answers[currentIndex] == null) {
          showValidation("Please select an answer before continuing.");
          if (questionContainer && questionContainer.querySelector(".lp-options-list")) {
            questionContainer.querySelector(".lp-options-list").classList.add("lp-options-invalid");
          }
          return;
        }

        if (questionContainer && questionContainer.querySelector(".lp-options-list")) {
          questionContainer.querySelector(".lp-options-list").classList.remove("lp-options-invalid");
        }

        if (!isLastQuestion) {
          currentIndex++;
          clearValidation();
          renderQuestion();
          renderQuestionNav();
          updateProgress();
          return;
        }

        if (answeredCount === questions.length) {
          clearValidation();
          buildResults();
        } else {
          showValidation("Please answer all questions to see your results. Use the question navigator above to find any missing answers.");
          const firstUnanswered = questions.findIndex((_, idx) => answers[idx] == null);
          if (firstUnanswered >= 0) {
            currentIndex = firstUnanswered;
            renderQuestion();
            renderQuestionNav();
            updateProgress();
          }
        }
      });

      var profileTabLi = document.getElementById("lpProfileTabLi");
      if (profileTabLi) {
        profileTabLi.addEventListener("click", function (e) {
          if (!testCompleted) {
            e.preventDefault();
            e.stopPropagation();
            showTooltip();
            return false;
          }
        });
      }

      renderQuestionNav();
      renderQuestion();
      updateProgress();

      if (window.lpSavedResult && window.lpSavedResult.answers && Object.keys(window.lpSavedResult.answers).length > 0) {
        Object.keys(window.lpSavedResult.answers).forEach(function (k) {
          var idx = parseInt(k, 10);
          if (!isNaN(idx)) answers[idx] = window.lpSavedResult.answers[k];
        });
        renderQuestionNav();
        renderQuestion();
        updateProgress();
        buildResults(true);
      }

      /* When an accordion panel opens, scroll it into view and focus the open header */
      var guideAccordion = document.getElementById("lpGuideAccordion");
      if (guideAccordion) {
        guideAccordion.querySelectorAll(".accordion-collapse").forEach(function (collapseEl) {
          collapseEl.addEventListener("shown.bs.collapse", function () {
            var targetId = collapseEl.id;
            if (!targetId) return;
            var btn = guideAccordion.querySelector('[data-bs-target="#' + targetId + '"]');
            if (btn) {
              btn.scrollIntoView({ behavior: "smooth", block: "nearest" });
              btn.focus({ preventScroll: true });
            }
          });
        });
      }
    })();
