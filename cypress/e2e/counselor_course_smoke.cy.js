/**
 * Counselor course E2E (password login via cy.counselorLoginPassword):
 * - After login: open course learning → Resume (or Start Learning) to load the next lesson
 * - Then loop through course steps (chapters/parts: video → quiz per template flow)
 * - Until header shows "Completed"
 * - Open course results + certificate view
 *
 * Env (cypress.config.js or cypress/cypress.counselor.config.js):
 * - counselorEmail, counselorPassword — same pattern as student_psychometric_class10.cy.js (studentClass10Email + studentDefaultPassword).
 * Override: CYPRESS_counselorEmail=... CYPRESS_counselorPassword=...
 * - counselorCourseFast — true: shorter fixed waits + lower command timeouts (local/CI when stable).
 * - counselorCourseMaxSteps — override max loop steps (default 100; e.g. 30 for a shorter run).
 *
 * Demo counselors can seek video. Loop stops as soon as the header shows Completed (no fixed 100 iterations).
 *
 * Timing: refreshTimingFromEnv() reads counselorCourseFast; if something flakes, set counselorCourseFast=false
 * or raise values in TIMING_STABLE below.
 */

const TIMING_STABLE = {
  PAGE_SETTLE_MS: 400,
  QUIZ_AFTER_ANSWER_MS: 500,
  QUIZ_AFTER_MANUAL_NEXT_MS: 300,
  VIDEO_SEEK_BEFORE_END_SEC: 2,
  VIDEO_WAIT_AFTER_PROGRESS_RESTORE_MS: 2500,
  VIDEO_WAIT_AFTER_ENDED_MS: 5500,
  TIMEOUT_LEARNING_CHROME_MS: 15000,
  TIMEOUT_VIDEO_METADATA_MS: 60000,
  TIMEOUT_VIDEO_AFTER_RELOAD_MS: 90000,
  TIMEOUT_QUIZ_FORM_MS: 12000,
  TIMEOUT_QUIZ_ANSWER_MS: 12000,
  TIMEOUT_QUIZ_NEXT_MS: 10000,
  TIMEOUT_QUIZ_SUBMIT_PANEL_MS: 20000,
  TIMEOUT_QUIZ_SUBMIT_BTN_MS: 12000,
  TIMEOUT_QUIZ_LOCATION_MS: 60000,
  TIMEOUT_QUIZ_POST_SUBMIT_MS: 60000,
  TIMEOUT_BODY_MS: 12000,
  TIMEOUT_ASSERT_COMPLETE_MS: 12000,
  TIMEOUT_RESULTS_CERT_MS: 15000,
  /** Extra settle after progress-restore wait before seek (video). */
  VIDEO_POST_RESTORE_EXTRA_MS: 400,
};

/** Shorter waits; use when app + network are fast. Revert to stable if you see video/quiz flakes. */
const TIMING_FAST = {
  PAGE_SETTLE_MS: 150,
  QUIZ_AFTER_ANSWER_MS: 350,
  QUIZ_AFTER_MANUAL_NEXT_MS: 150,
  VIDEO_SEEK_BEFORE_END_SEC: 1.5,
  VIDEO_WAIT_AFTER_PROGRESS_RESTORE_MS: 1200,
  VIDEO_WAIT_AFTER_ENDED_MS: 3500,
  TIMEOUT_LEARNING_CHROME_MS: 12000,
  TIMEOUT_VIDEO_METADATA_MS: 45000,
  TIMEOUT_VIDEO_AFTER_RELOAD_MS: 60000,
  TIMEOUT_QUIZ_FORM_MS: 8000,
  TIMEOUT_QUIZ_ANSWER_MS: 8000,
  TIMEOUT_QUIZ_NEXT_MS: 8000,
  TIMEOUT_QUIZ_SUBMIT_PANEL_MS: 12000,
  TIMEOUT_QUIZ_SUBMIT_BTN_MS: 8000,
  TIMEOUT_QUIZ_LOCATION_MS: 45000,
  TIMEOUT_QUIZ_POST_SUBMIT_MS: 45000,
  TIMEOUT_BODY_MS: 8000,
  TIMEOUT_ASSERT_COMPLETE_MS: 10000,
  TIMEOUT_RESULTS_CERT_MS: 12000,
  VIDEO_POST_RESTORE_EXTRA_MS: 220,
};

/** Current timing profile — updated in beforeEach via refreshTimingFromEnv(). */
let T = { ...TIMING_STABLE };

function refreshTimingFromEnv() {
  const fast =
    Cypress.env("counselorCourseFast") === true ||
    Cypress.env("counselorCourseFast") === "true";
  T = fast ? { ...TIMING_FAST } : { ...TIMING_STABLE };
}

function maxChapterQuizStepsFromEnv() {
  const raw = Cypress.env("counselorCourseMaxSteps");
  const n = Number(raw);
  if (Number.isFinite(n) && n > 0) return Math.floor(n);
  return 100;
}

function isCourseCompleteInHeader($body) {
  const el = $body.find(".learning-top-actions .btn-resume-course").first();
  return el.length && /Completed/i.test(el.text());
}

/** Quiz id from `#quizForm`: `data-quiz-id` if present, else parsed from `action` (`.../submit_full_quiz/<counselor>/<quiz>/`). */
function quizIdFromQuizForm($form) {
  const raw = String($form.attr("data-quiz-id") || "").trim();
  if (raw) return raw;
  const action = String($form.attr("action") || "");
  const m = action.match(/submit_full_quiz\/\d+\/(\d+)/);
  return m ? m[1] : "";
}

/**
 * After login + first visit to course_learning: enter the course so the loop can complete lessons.
 *
 * - Header "Resume" goes to the next incomplete lesson (same URL; server picks progress).
 * - Welcome "Start Learning" jumps to chapter 1 — when both Resume and Start exist, click Resume first
 *   so saved progress is not reset.
 * - If there is already an active lesson (video / quiz / quiz-done), do not click Resume (avoid reload).
 * - If only "Resume" is available and no lesson is shown yet (e.g. empty welcome), click Resume once.
 *
 * Call only once after the first cy.visit(course_learning), not inside each loop step.
 */
function clickResumeOrStartCourseEntry() {
  cy.get("body", { timeout: T.TIMEOUT_BODY_MS }).then(($b) => {
    const $resume = $b.find("a.btn-resume-course").filter((_, el) => /Resume/i.test(Cypress.$(el).text().trim()));
    const $start = $b.find("button").filter((_, el) => /Start Learning/i.test(Cypress.$(el).text()));
    const hasActiveLesson =
      $b.find("#lesson-video-pane video").length > 0 ||
      $b.find("#quizForm").length > 0 ||
      $b.find(".quiz-completed-view").length > 0;

    if ($start.length && $resume.length) {
      cy.wrap($resume.first()).click({ force: true });
      cy.wait(T.PAGE_SETTLE_MS);
      cy.log("Course entry: Resume (prefer over Start Learning).");
      return;
    }
    if ($start.length) {
      cy.wrap($start.first()).click();
      cy.wait(T.PAGE_SETTLE_MS);
      cy.log("Course entry: Start Learning (no Resume link).");
      return;
    }
    if ($resume.length && !hasActiveLesson) {
      cy.wrap($resume.first()).click({ force: true });
      cy.wait(T.PAGE_SETTLE_MS);
      cy.log("Course entry: Resume (no active lesson on screen yet).");
    }
  });
}

/**
 * Based on counselor_course_smoke.cy-org.js: seek near end + play + wait for `ended`.
 * Adds: pause + wait so get_progress_and_duration fetch does not overwrite currentTime;
 * _noteSeekGuard matches course_learning.html seekLessonVideoToSeconds when restrictVideoSeek.
 */
function completeLessonVideoIfPresent() {
  cy.get("#lesson-video-pane video", { timeout: T.TIMEOUT_VIDEO_METADATA_MS }).should(($v) => {
    const el = $v[0];
    expect(el.duration, "video duration").to.be.greaterThan(0);
  });
  cy.get("#lesson-video-pane video").then(($v) => {
    const el = $v[0];
    if (el.getAttribute("data-is-completed") === "true") {
      cy.log("Video already marked completed.");
      return;
    }
    try {
      el.pause();
    } catch (e) {
      /* ignore */
    }
    // Async fetch in template may set currentTime after saved progress — wait before seek (cy-org had seek immediately).
    cy.wait(T.VIDEO_WAIT_AFTER_PROGRESS_RESTORE_MS);
    cy.wait(T.VIDEO_POST_RESTORE_EXTRA_MS);
    cy.then(() => {
      const d = el.duration;
      const seekTo =
        d > T.VIDEO_SEEK_BEFORE_END_SEC ? d - T.VIDEO_SEEK_BEFORE_END_SEC : Math.max(0, d - 0.1);
      const beforeSeek = el.currentTime;
      try {
        el._noteSeekGuard = true;
      } catch (e) {
        /* ignore */
      }
      el.muted = true;
      el.currentTime = seekTo;
      const afterSeek = el.currentTime;

      const durationSec = Number(d.toFixed(3));
      const seekTargetSec = Number(seekTo.toFixed(3));
      const beforeSec = Number(beforeSeek.toFixed(3));
      const afterSec = Number(afterSeek.toFixed(3));
      const seekApplied = Math.abs(afterSeek - seekTo) < 1;
      const movedForward = afterSeek > beforeSeek + 0.05;
      const forwardedOk = seekApplied || movedForward;

      cy.log(
        `[video] length=${durationSec}s seek→${seekTargetSec}s | before=${beforeSec}s after=${afterSec}s`
      );
      cy.window().then((win) => {
        win.console.log(
          "[E2E video] length_sec:",
          durationSec,
          "| seek_target_sec:",
          seekTargetSec,
          "| before_seek_sec:",
          beforeSec,
          "| after_seek_sec:",
          afterSec
        );
        if (forwardedOk) {
          win.console.log("[E2E video] SUCCESS: Video forwarded; seek applied as expected.");
        } else {
          win.console.warn(
            "[E2E video] WARNING: Playback time did not jump to seek target (possible clamp or overwrite)."
          );
        }
      });

      // Template: on `ended`, POST update_progress then location.reload() after ~1s.
      cy.wrap(
        new Cypress.Promise((resolve, reject) => {
          const onEnded = () => {
            el.removeEventListener("ended", onEnded);
            resolve();
          };
          el.addEventListener("ended", onEnded);
          el.addEventListener(
            "error",
            () => {
              el.removeEventListener("ended", onEnded);
              reject(new Error("video error"));
            },
            { once: true }
          );
          const p = el.play && el.play();
          if (p && typeof p.catch === "function") p.catch(() => {});
        })
      );
      cy.wait(T.VIDEO_WAIT_AFTER_ENDED_MS);
    });
  });
  // After reload: quiz, no video pane, or completed video (same as cy-org).
  cy.get("body", { timeout: T.TIMEOUT_VIDEO_AFTER_RELOAD_MS }).should(($b) => {
    if ($b.find("#quizForm").length) return;
    const $v = $b.find("#lesson-video-pane video");
    if (!$v.length) return;
    expect($v.attr("data-is-completed")).to.eq("true");
  });
}

/**
 * Answer every question (first option), then submit once.
 * maxQuestions = .question-container count; loop that many times, then popup / #submitBtn.
 */
function submitQuizPickFirstOption() {
  cy.get("#quizForm", { timeout: T.TIMEOUT_QUIZ_FORM_MS }).should("exist");
  cy.get("#quizForm")
    .then(($f) => {
      const quizIdBefore = quizIdFromQuizForm($f);
      expect(quizIdBefore, "quiz id from #quizForm (data-quiz-id or action URL)").to.be.a("string").and.not.be.empty;
      cy.get(".question-container")
        .its("length")
        .then((maxQuestions) => {
          expect(maxQuestions, "quiz question count").to.be.greaterThan(0);
          cy.log(`Quiz ${quizIdBefore}: answering ${maxQuestions} question(s), then submit.`);

          cy.wrap(Array.from({ length: maxQuestions })).each((_, questionIndex) => {
            cy.get(".question-container.active").invoke("attr", "data-question-index").then((prevQ) => {
              cy.get(".question-container.active .answer-option", { timeout: T.TIMEOUT_QUIZ_ANSWER_MS })
                .first()
                .click({ force: true });
              cy.wait(T.QUIZ_AFTER_ANSWER_MS);
              cy.get(".question-container.active").invoke("attr", "data-question-index").then((qAfter) => {
                const same = String(qAfter) === String(prevQ);
                if (same && questionIndex < maxQuestions - 1) {
                  cy.get("#nextBtn", { timeout: T.TIMEOUT_QUIZ_NEXT_MS }).click({ force: true });
                  cy.wait(T.QUIZ_AFTER_MANUAL_NEXT_MS);
                }
              });
            });
          });
        });

      cy.get("body", { timeout: T.TIMEOUT_QUIZ_SUBMIT_PANEL_MS }).then(($b) => {
        if ($b.find(".submit-quiz-popup-overlay").length) {
          cy.contains(".submit-quiz-popup-overlay button", "Submit Quiz").should("be.visible").click({ force: true });
        } else {
          cy.get("#submitBtn", { timeout: T.TIMEOUT_QUIZ_SUBMIT_BTN_MS }).should("be.visible").click({ force: true });
        }
      });

      cy.location("pathname", { timeout: T.TIMEOUT_QUIZ_LOCATION_MS }).should("include", "/counselor/course_learning/");
      cy.get("body", { timeout: T.TIMEOUT_QUIZ_POST_SUBMIT_MS }).should(($b) => {
        const $f = $b.find("#quizForm");
        if (!$f.length) return;
        expect(quizIdFromQuizForm($f), "after submit, expect next content or another quiz").not.to.eq(quizIdBefore);
      });
    });
}

/** One step: video, quiz, resume, or continue — drives chapter/part progression. Resume/Start is handled once on first visit. */
function courseLearningStep() {
  cy.get("body", { timeout: T.TIMEOUT_BODY_MS }).then(($b) => {
    if (isCourseCompleteInHeader($b)) {
      cy.log("Course complete (header).");
      return;
    }

    const $vid = $b.find("#lesson-video-pane video");
    const vid = $vid[0];
    const vidIncomplete =
      vid &&
      vid.getAttribute("data-is-completed") !== "true" &&
      $b.find(".lesson-video-completion-status").length === 0;

    if (vid && vidIncomplete) {
      cy.wrap(null).then(() => completeLessonVideoIfPresent());
      cy.wait(T.PAGE_SETTLE_MS);
      cy.get("body").then(($inner) => {
        if (
          $inner.find("a.btn-resume-course").length &&
          /Resume/i.test($inner.find("a.btn-resume-course").first().text())
        ) {
          cy.get("a.btn-resume-course").contains(/Resume/i).click({ force: true });
        }
      });
      cy.wait(T.PAGE_SETTLE_MS);
      return;
    }

    if ($b.find("#quizForm").length) {
      cy.wrap(null).then(() => submitQuizPickFirstOption());
      cy.wait(T.PAGE_SETTLE_MS);
      cy.get("body").then(($q) => {
        if ($q.find('button:contains("Continue to Next Part")').length) {
          cy.contains("button", "Continue to Next Part").click({ force: true });
        } else if (
          $q.find("a.btn-resume-course").length &&
          /Resume/i.test($q.find("a.btn-resume-course").first().text())
        ) {
          cy.get("a.btn-resume-course").contains(/Resume/i).click({ force: true });
        }
      });
      cy.wait(T.PAGE_SETTLE_MS);
      return;
    }

    if ($b.find(".quiz-completed-view").length && $b.find('button:contains("Continue to Next Part")').length) {
      cy.contains("button", "Continue to Next Part").click({ force: true });
      cy.wait(T.PAGE_SETTLE_MS);
      return;
    }

    if ($b.find("a.btn-resume-course").length && /Resume/i.test($b.find("a.btn-resume-course").first().text())) {
      cy.get("a.btn-resume-course").contains(/Resume/i).click({ force: true });
      cy.wait(T.PAGE_SETTLE_MS);
    }
  });
}

/**
 * Outer loop: each step advances one “unit” (video, quiz, resume, continue).
 * Stops as soon as the header shows Completed — no wasted iterations after the course finishes.
 */
function runChapterAndQuizLoop(maxSteps) {
  cy.get("body", { timeout: T.TIMEOUT_BODY_MS }).then(($b) => {
    const chapterCount = $b.find(".chapter-list .chapter-item").length;
    cy.log(`Course sidebar: ${chapterCount} chapter block(s). Up to ${maxSteps} step(s); stops when Completed.`);
  });

  const runFrom = (stepIndex) => {
    if (stepIndex >= maxSteps) return;
    cy.get("body").then(($b) => {
      if (isCourseCompleteInHeader($b)) {
        cy.log(`Chapter/quiz loop: course complete after ${stepIndex} step(s).`);
        return;
      }
      cy.log(`Course step ${stepIndex + 1}/${maxSteps}`);
      courseLearningStep();
      cy.get("body").then(($b2) => {
        if (isCourseCompleteInHeader($b2)) {
          cy.log(`Chapter/quiz loop: course complete after ${stepIndex + 1} step(s).`);
          return;
        }
        cy.then(() => runFrom(stepIndex + 1));
      });
    });
  };

  cy.then(() => runFrom(0));
}

describe("Counselor course — resume/start through certificate (password login)", () => {
  beforeEach(() => {
    refreshTimingFromEnv();
    cy.clearCookies();
    cy.clearLocalStorage();
  });

  it("full course path", () => {
    const maxSteps = maxChapterQuizStepsFromEnv();
    const email =
      Cypress.env("counselorEmail") || "demo_counselor@topteen.demo";
    const password = Cypress.env("counselorPassword");
    cy.counselorLoginPassword(email, password);

    cy.get("@counselorId").then((counselorId) => {
      cy.visit(`/counselor/course_learning/${counselorId}/`);
    });

    cy.get(".learning-top-header", { timeout: T.TIMEOUT_LEARNING_CHROME_MS }).should("be.visible");
    cy.get(".course-sidebar", { timeout: T.TIMEOUT_LEARNING_CHROME_MS }).should("exist").scrollIntoView();

    // 1) After login: Resume (or Start Learning if no Resume) so the next incomplete lesson loads.
    cy.log("Step 1 — resume or start course entry");
    clickResumeOrStartCourseEntry();

    // 2) Drive videos/quizzes until the header shows Completed.
    cy.log("Step 2 — complete course (video / quiz loop)");
    runChapterAndQuizLoop(maxSteps);

    cy.get("@counselorId").then((counselorId) => {
      cy.visit(`/counselor/course_learning/${counselorId}/`);
      cy.get("body", { timeout: T.TIMEOUT_ASSERT_COMPLETE_MS }).should(($b) => {
        expect(
          isCourseCompleteInHeader($b),
          "After iterations, header should show Completed (requires full course data & passing quizzes)"
        ).to.be.true;
      });

      cy.visit(`/counselor/course_results/${counselorId}/`);
      cy.contains("Course Results", { timeout: T.TIMEOUT_RESULTS_CERT_MS }).should("be.visible");

      cy.get("body").then(($b) => {
        if ($b.find("a[href*='view_certificate']").length) {
          cy.contains("a", /View Certificate/i).first().click();
          cy.contains("Certificate of Completion", { timeout: T.TIMEOUT_RESULTS_CERT_MS }).should("be.visible");
        } else {
          cy.visit(`/counselor/view_certificate/${counselorId}/`);
          cy.contains(/Certificate of Completion|certificate/i, { timeout: T.TIMEOUT_RESULTS_CERT_MS }).should("exist");
        }
      });
    });
  });
});
