/**
 * Class 12 — Career Direction follow-on: post-matric hub `/api/web/tests/` and linear `take_test` pages.
 * Loaded from student_psychometric.js (see cypress/support/e2e.js).
 */

function registerClass12DismissPostMatricPopups() {
  Cypress.Commands.add("class12DismissPostMatricPopups", () => {
    const maxMs = 25000;
    const started = Date.now();
    let stableNoPopup = 0;

    const loop = () => {
      const elapsed = Date.now() - started;
      if (elapsed > maxMs) return;

      cy.get("body").then(($b) => {
        const $m = $b.find(".personality-questionnaire-modal.show");
        if (!$m.length) {
          stableNoPopup += 1;
          if (stableNoPopup >= 3) return;
          cy.wait(400);
          cy.then(loop);
          return;
        }

        stableNoPopup = 0;

        cy.wrap($m.first()).within(() => {
          // Pick option 1 and continue (some modals enable Continue only after click)
          cy.get("input[type=radio]").first().click({ force: true });
          cy.get("button.btn-continue", { timeout: 15000 })
            .should("be.visible")
            .should("not.be.disabled")
            .click({ force: true });
        });

        cy.wait(700);
        cy.then(loop);
      });
    };

    loop();
  });
}

function registerClass12PostMatricLinearTestBeginSmoke() {
  Cypress.Commands.add(
    "class12PostMatricLinearTestBeginSmoke",
    (options = {}) => {
      const onlyFirstTest =
        options.onlyFirstTest === true || options.onlyFirstTest === "true";
      const answerFirstQuestion =
        options.answerFirstQuestion === true ||
        options.answerFirstQuestion === "true";

      cy.class12DismissPostMatricPopups();

      cy.get("#tests-container", { timeout: 120000 }).should("exist");
      cy.get("#tests-container .take-test-btn", { timeout: 120000 }).should(
        "exist"
      );

      cy.get("#tests-container a.take-test-btn").then(($els) => {
        const els = ($els && typeof $els.toArray === "function")
          ? $els.toArray()
          : Array.from($els || []);

        // Prefer explicitly the first card: "Personality Assessment" (test 1 in the hub UI).
        const personalityCardBtn = els.find((el) => {
          if (
            el.offsetParent === null ||
            el.classList.contains("d-none") ||
            !/Start Test/i.test(el.textContent || "")
          ) {
            return false;
          }
          const card = el.closest(".pt-y-box");
          const title = card ? (card.querySelector(".test-title")?.textContent || "") : "";
          return /Personality Assessment/i.test(title) && (el.getAttribute("href") || "").includes("/take_test/");
        });

        if (personalityCardBtn) {
          cy.wrap(personalityCardBtn).click({ force: true });
          return;
        }

        const linear = els.filter(
          (el) =>
            el.offsetParent !== null &&
            !el.classList.contains("d-none") &&
            /Start Test/i.test(el.textContent || "") &&
            (el.getAttribute("href") || "").includes("/take_test/")
        );

        if (linear[0]) {
          cy.wrap(linear[0]).click({ force: true });
          return;
        }

        if (onlyFirstTest) {
          cy.then(() => {
            throw new Error(
              "class12PostMatricLinearTestBeginSmoke: onlyFirstTest enabled but no /take_test/ Start Test link was found."
            );
          });
          return;
        }

        // Fallback: Aptitude (Test 4) uses sections/subtests UI: /api/web/test/4/sections/
        const sections = els.filter(
          (el) =>
            el.offsetParent !== null &&
            !el.classList.contains("d-none") &&
            /Start Test/i.test(el.textContent || "") &&
            (el.getAttribute("href") || "").includes("/sections/")
        );

        expect(
          sections[0],
          "a visible Start Test link for /api/web/test/<id>/sections/ (Aptitude subtests)"
        ).to.exist;
        cy.wrap(sections[0]).click({ force: true });
      });

      cy.url({ timeout: 45000 }).then((href) => {
        if (href.includes("/take_test/")) {
          cy.get("#startTestBtn", { timeout: 45000 })
            .should("be.visible")
            .click();
          cy.get("#testContent", { timeout: 120000 }).should("be.visible");

          if (answerFirstQuestion) {
            cy.wait(500);
            cy.get("#questionsContainer .question.active label.custom-radio", {
              timeout: 120000,
            })
              .first()
              .click({ force: true });
            cy.wait(800);
            cy.get("#testContent .question-number", { timeout: 60000 }).should(
              "be.visible"
            );
          }
          return;
        }

        if (href.includes("/sections/")) {
          cy.get("#startBtn", { timeout: 45000 })
            .should("be.visible")
            .click({ force: true });
          cy.get("#sections-container", { timeout: 45000 }).should("exist");
          cy.get("#sections-container button.start-section-btn", {
            timeout: 45000,
          })
            .first()
            .should("be.visible")
            .click({ force: true });
          cy.url({ timeout: 45000 }).should("include", "/starttest/");
          return;
        }

        cy.then(() => {
          throw new Error(
            `class12PostMatricLinearTestBeginSmoke: unexpected URL after Start Test click: ${href}`
          );
        });
      });
    }
  );
}

function registerClass12CompleteFirstLinearTest() {
  Cypress.Commands.add("class12CompleteFirstLinearTest", () => {
    cy.class12PostMatricLinearTestBeginSmoke({
      onlyFirstTest: true,
      answerFirstQuestion: true,
    });
    cy.class12CompleteCurrentLinearTakeTest();
  });
}

function registerClass12CompleteCurrentLinearTakeTest() {
  Cypress.Commands.add("class12CompleteCurrentLinearTakeTest", () => {
    /**
     * take_test.html often has ENABLE_AUTO_FORWARD: selecting an answer advances after ~300ms.
     * If we also click "Next", we double-advance and skip questions → partial submit / test not completed.
     * Rule: after answering, wait; only click Next if the question number did NOT change.
     */
    const maxSteps = 600;
    const waitAfterAnswerMs = 1800;
    const waitBeforeSubmitMs = 2500;
    const optTimeout = 180000;
    const submitTimeout = 90000;
    const swalTimeout = 90000;

    const pickFirstOption = () => {
      cy.get("#questionsContainer .question.active", { timeout: optTimeout }).should(
        "exist"
      );
      cy.get("#questionsContainer .question.active", { timeout: optTimeout }).then(
        ($q) => {
          const $lab = $q.find("label.custom-radio");
          if ($lab.length) {
            cy.wrap($lab.first()).click({ force: true });
          } else {
            cy.wrap($q)
              .find('input[type="radio"], input[type="checkbox"]')
              .first()
              .click({ force: true });
          }
        }
      );
    };

    const step = (remaining) => {
      if (remaining <= 0) {
        cy.then(() => {
          throw new Error(
            "class12CompleteCurrentLinearTakeTest: exceeded maxSteps (test may have changed or got stuck)"
          );
        });
        return;
      }

      cy.get("#testContent", { timeout: optTimeout }).should("be.visible");

      // loadAnswers() is async — wait until options exist before answering (fixes stuck Q27 / Test 3).
      cy.get("#questionsContainer .question.active", { timeout: optTimeout }).should(
        "exist"
      );
      cy.get("#questionsContainer .question.active", { timeout: optTimeout }).should(
        ($el) => {
          const n =
            $el.find("label.custom-radio").length +
            $el.find('input[type="radio"],input[type="checkbox"]').length;
          expect(n, "question options rendered").to.be.greaterThan(0);
        }
      );

      cy.get("#currentQuestionNum", { timeout: optTimeout })
        .invoke("text")
        .then((curTxt) => {
          cy.get("#totalQuestions", { timeout: optTimeout })
            .invoke("text")
            .then((totTxt) => {
              const curBefore = parseInt(String(curTxt).trim(), 10);
              const tot = parseInt(String(totTxt).trim(), 10);
              expect(curBefore, "current question number").to.be.a("number").and
                .not.be.NaN;
              expect(tot, "total question count").to.be.a("number").and.not.be
                .NaN;

              pickFirstOption();
              cy.wait(waitAfterAnswerMs);

              cy.get("#currentQuestionNum", { timeout: optTimeout })
                .invoke("text")
                .then((afterTxt) => {
                  const curAfter = parseInt(String(afterTxt).trim(), 10);
                  expect(curAfter, "question # after answer").to.be.a("number").and
                    .not.be.NaN;

                  const isLastQuestion = curBefore === tot;

                  if (isLastQuestion) {
                    cy.wait(waitBeforeSubmitMs);
                    cy.get("#submitTestBtn", { timeout: submitTimeout })
                      .should("be.visible")
                      .should("not.be.disabled");
                    cy.get("#submitTestBtn").click({ force: true });
                    cy.get(".swal2-confirm", { timeout: swalTimeout })
                      .should("be.visible")
                      .click({ force: true });
                    return;
                  }

                  // Not last: only click Next if auto-forward did not advance
                  if (curAfter === curBefore) {
                    cy.get("#nextQuestionBtn", { timeout: submitTimeout })
                      .should("be.visible")
                      .click({ force: true });
                    cy.wait(500);
                  }

                  cy.then(() => step(remaining - 1));
                });
            });
        });
    };

    step(maxSteps);
  });
}

function registerClass12CompleteCurrentSectionDetails() {
  /**
   * One aptitude *section* (`section_details.html`): same pattern as `take_test` — auto-advance
   * can move to the next question; do not also click Next (skips questions → incomplete section).
   * Progress is `#questionProgress` / `#questionProgressMobile` text like "3 / 12".
   *
   * Instruction step: `#introduction-section` + `#startBtn` "Begin" (scoped — Test 4 hub also uses `#startBtn` "Get Sections").
   */
  Cypress.Commands.add("class12CompleteCurrentSectionDetails", () => {
    const optTimeout = 180000;
    const settleMs = 2200;
    const waitBeforeSubmitMs = 2200;
    const modalTimeout = 90000;
    const navTimeout = 120000;

    /**
     * Instruction step → test UI: click **Begin** (`#introduction-section #startBtn`).
     * Cypress synthetic `.click()` can fail to run the delegated jQuery handler reliably here; use a
     * native `HTMLElement.click()` and retry once if the intro is still visible.
     * Skip only when MCQ radios already exist (resume / already past intro).
     */
    cy.document({ timeout: 60000 }).its("readyState").should("eq", "complete");
    cy.get("body", { timeout: 90000 }).then(($b) => {
      const hasMcq =
        $b.find("#questions-container .answers-container label.custom-radio").length > 0;
      if (hasMcq) {
        cy.log("Section details: MCQ already in DOM — skipping Begin.");
        return;
      }
      cy.get("#introduction-section", { timeout: 90000 }).should("exist");
      cy.get("#introduction-section button#startBtn", { timeout: 90000 })
        .should("exist")
        .should("not.be.disabled")
        .then(($btn) => {
          $btn[0].click();
        });
    });
    cy.wait(600);
    cy.get("body").then(($b) => {
      const hasMcq =
        $b.find("#questions-container .answers-container label.custom-radio").length > 0;
      const testUiOpen = $b.find(".question-container").is(":visible");
      if (hasMcq || testUiOpen) return;
      cy.get("#introduction-section button#startBtn", { timeout: 15000 })
        .should("exist")
        .then(($btn) => {
          $btn[0].click();
        });
    });
    cy.wait(400);
    cy.get(".question-container", { timeout: optTimeout }).should("be.visible");
    /**
     * `section_details.html` initially puts a `.loading` block with "Loading questions..." inside
     * `#questions-container`. That string must never be used for negative assertions (flakes).
     * Real questions render `.question-box` > `.answers-container` > `label.custom-radio` only
     * after `loadQuestions()` + `renderCurrentQuestion()` — wait for that positive signal.
     */
    cy.get("#questions-container .answers-container", { timeout: optTimeout }).should(
      "be.visible"
    );
    cy.get("#questions-container .answers-container label.custom-radio", {
      timeout: optTimeout,
    })
      .should("have.length.at.least", 1)
      .first()
      .should("be.visible");

    const readProgressText = () => {
      return cy.get("body", { timeout: optTimeout }).then(($b) => {
        let txt = ($b.find("#questionProgress").text() || "").trim();
        if (!/\d+\s*\/\s*\d+/.test(txt)) {
          txt = ($b.find("#questionProgressMobile").text() || "").trim();
        }
        expect(txt, "section progress (e.g. 3 / 12)").to.match(/\d+\s*\/\s*\d+/);
        return txt;
      });
    };

    const parsePair = (text) => {
      const m = String(text).match(/(\d+)\s*\/\s*(\d+)/);
      expect(m, `section progress "${text}"`).to.exist;
      return { cur: parseInt(m[1], 10), tot: parseInt(m[2], 10) };
    };

    const pickFirstOption = () => {
      cy.get("#questions-container .answers-container", { timeout: optTimeout }).then(
        ($ac) => {
          const $lab = $ac.find("label.custom-radio");
          if ($lab.length) {
            cy.wrap($lab.first()).click({ force: true });
          } else {
            cy.wrap($ac).find('input[type="radio"]').first().click({ force: true });
          }
        }
      );
    };

    const maxSteps = 400;
    const step = (remaining) => {
      if (remaining <= 0) {
        cy.then(() => {
          throw new Error(
            "class12CompleteCurrentSectionDetails: exceeded maxSteps (section may have changed or got stuck)"
          );
        });
        return;
      }

      cy.get(".question-container", { timeout: optTimeout }).should("be.visible");
      cy.get("#questions-container .answers-container", { timeout: optTimeout }).should(
        "be.visible"
      );
      cy.get("#questions-container .answers-container label.custom-radio", {
        timeout: optTimeout,
      })
        .should("have.length.at.least", 1)
        .first()
        .should("be.visible");

      readProgressText().then((txt) => {
        const { cur: curBefore, tot } = parsePair(txt);

        const isLast = curBefore === tot;
        pickFirstOption();
        cy.wait(settleMs);

        readProgressText().then((txtAfter) => {
          const { cur: curAfter } = parsePair(txtAfter);

          if (isLast) {
            cy.wait(waitBeforeSubmitMs);
            cy.get("#submit-section", { timeout: modalTimeout })
              .should("be.visible")
              .click({ force: true });
            cy.get("#submitConfirmationModal", { timeout: modalTimeout }).should(
              "have.class",
              "show"
            );
            cy.get("#submitConfirmBtn", { timeout: modalTimeout })
              .should("be.visible")
              .then(($btn) => {
                $btn[0].click();
              });
            // Async submit + redirect to aptitude section list (or full tests hub)
            cy.url({ timeout: navTimeout }).should("satisfy", (u) =>
              /\/api\/web\/test\/\d+\/sections/i.test(u) ||
                /\/api\/web\/tests/i.test(u)
            );
            return;
          }

          if (curAfter === curBefore) {
            cy.get("#next-question", { timeout: modalTimeout })
              .should("exist")
              .then(($el) => {
                if ($el.is(":visible")) {
                  cy.wrap($el).click({ force: true });
                } else {
                  cy.get(".navigation-buttons", { timeout: modalTimeout })
                    .contains("button", /^(Next|Continue)$/i)
                    .click({ force: true });
                }
              });
            cy.wait(400);
          }

          cy.then(() => step(remaining - 1));
        });
      });
    };

    step(maxSteps);
  });
}

function registerClass12CompleteAptitudeAllSections() {
  Cypress.Commands.add("class12CompleteAptitudeAllSections", () => {
    const base = String(Cypress.config("baseUrl") || "").replace(/\/$/, "");
    const sectionsUrl = `${base}/api/web/test/4/sections/`;
    const hubUrl = `${base}/api/web/tests/`;

    /** After each section, `submitSection()` redirects to `/api/web/test/4/sections/`. */
    const runNextSection = (remaining) => {
      if (remaining <= 0) {
        cy.then(() => {
          throw new Error(
            "class12CompleteAptitudeAllSections: exceeded max section attempts (still pending Start Section?)"
          );
        });
        return;
      }

      cy.visit(sectionsUrl, { timeout: 60000 });
      cy.location("pathname", { timeout: 60000 }).should("include", "/sections");

      /**
       * `test_sections.html`: `#sections-list` is hidden until "Get Sections" is clicked.
       * Relying on `#startBtn:visible` alone can skip the click; always reveal the list when needed.
       */
      cy.get("body", { timeout: 60000 }).then(($b) => {
        const listVisible = $b.find("#sections-list:visible").length > 0;
        if (!listVisible) {
          cy.contains("#introduction-test-4 button", /Get Sections/i, { timeout: 60000 })
            .scrollIntoView()
            .click({ force: true });
        }
      });
      cy.get("#sections-list", { timeout: 60000 }).should("be.visible");
      cy.get("#sections-container", { timeout: 120000 }).should("exist");
      cy.get("#sections-container button.start-section-btn", { timeout: 120000 }).should(
        "have.length.at.least",
        1
      );
      cy.wait(1500);

      cy.get("#sections-container").then(($c) => {
        const candidates = $c
          .find("button.start-section-btn")
          .toArray()
          .filter((el) => {
            const t = el.textContent || "";
            if (!/Start Section/i.test(t)) return false;
            if (el.disabled || el.classList.contains("disabled")) return false;
            return true;
          });

        if (candidates.length === 0) {
          return cy.wrap("done");
        }
        return cy
          .wrap(candidates[0])
          .scrollIntoView()
          .click({ force: true })
          .then(() => "continue");
      }).then((state) => {
        if (state === "done") {
          cy.log("Aptitude (Test 4): all section subtests completed.");
          return;
        }
        cy.url({ timeout: 60000 }).should("include", "/starttest/");
        cy.class12CompleteCurrentSectionDetails();
        cy.url({ timeout: 120000 }).should("satisfy", (u) =>
          /\/test\/4\/sections/.test(u)
        );
        cy.then(() => runNextSection(remaining - 1));
      });
    };

    runNextSection(16);

    cy.visit(hubUrl, { timeout: 60000 });
    cy.wait(2500);
    cy.reload();
    cy.get("#tests-container", { timeout: 120000 }).should("exist");
    cy.contains(".pt-y-box", /Aptitude Assessment/i, { timeout: 120000 })
      .should("be.visible")
      .within(() => {
        cy.get(".questions-count", { timeout: 180000 }).should(($el) => {
          const t = $el.text() || "";
          expect(t, "Aptitude section progress on hub").to.match(
            /(\d+)\s*\/\s*(\d+)\s*sections completed/i
          );
          const m = t.match(/(\d+)\s*\/\s*(\d+)/);
          expect(m[1], "completed sections").to.eq(m[2]);
        });
        cy.contains(".badge, span", /Completed/i, { timeout: 180000 }).should(
          "be.visible"
        );
      });
  });
}

function registerClass12CompleteAllFourTests() {
  Cypress.Commands.add("class12CompleteAllFourTests", () => {
    cy.class12DismissPostMatricPopups();
    cy.location("pathname", { timeout: 45000 }).should("include", "/api/web/tests");

    const completeLinearByTitle = (titleRegex) => {
      let status = "skip";
      cy.get("#tests-container", { timeout: 120000 }).should("exist");
      cy.get("#tests-container .pt-y-box", { timeout: 120000 }).then(($cards) => {
        const cards =
          $cards && typeof $cards.toArray === "function"
            ? $cards.toArray()
            : Array.from($cards || []);
        const cardEl = cards.find((c) => {
          const title = c.querySelector(".test-title")?.textContent || "";
          return titleRegex.test(title);
        });
        expect(cardEl, `test card matching ${titleRegex}`).to.exist;

        const $card = Cypress.$(cardEl);
        const viewVisible =
          $card.find("a.details-btn").not(".d-none").length > 0;
        if (viewVisible) {
          status = "skip";
          return;
        }

        const startEl = $card.find("a.take-test-btn").not(".d-none").get(0);
        expect(startEl, `Start Test button for ${titleRegex}`).to.exist;
        status = "started";
        cy.wrap(startEl).scrollIntoView().click({ force: true });
      });

      cy.then(() => {
        if (status === "skip") return;
          cy.location("pathname", { timeout: 45000 }).should(
            "include",
            "/take_test/"
          );
          cy.get("#startTestBtn", { timeout: 45000 })
            .should("be.visible")
            .click({ force: true });
          cy.get("#testContent", { timeout: 120000 }).should("be.visible");
          cy.class12CompleteCurrentLinearTakeTest();
          cy.visit(Cypress.config("baseUrl") + "/api/web/tests/", {
            timeout: 45000,
          });
          cy.class12DismissPostMatricPopups();
      });
    };

    // 1) Personality
    completeLinearByTitle(/Personality Assessment/i);
    // 2) Motivation
    completeLinearByTitle(/Motivation Assessment/i);
    // 3) Career Interest
    completeLinearByTitle(/Career Interest Inventory/i);

    // 4) Aptitude (sections)
    cy.visit(Cypress.config("baseUrl") + "/api/web/test/4/sections/", { timeout: 45000 });
    cy.class12CompleteAptitudeAllSections();
    cy.visit(Cypress.config("baseUrl") + "/api/web/tests/", { timeout: 45000 });
  });
}

try {
  registerClass12DismissPostMatricPopups();
} catch (e) {
  if (!/already been added|duplicate command|already exists/i.test(String(e && e.message))) {
    throw e;
  }
}
try {
  registerClass12PostMatricLinearTestBeginSmoke();
} catch (e) {
  if (!/already been added|duplicate command|already exists/i.test(String(e && e.message))) {
    throw e;
  }
}
try {
  registerClass12CompleteCurrentLinearTakeTest();
} catch (e) {
  if (!/already been added|duplicate command|already exists/i.test(String(e && e.message))) {
    throw e;
  }
}
try {
  registerClass12CompleteCurrentSectionDetails();
} catch (e) {
  if (!/already been added|duplicate command|already exists/i.test(String(e && e.message))) {
    throw e;
  }
}
try {
  registerClass12CompleteAptitudeAllSections();
} catch (e) {
  if (!/already been added|duplicate command|already exists/i.test(String(e && e.message))) {
    throw e;
  }
}
try {
  registerClass12CompleteFirstLinearTest();
} catch (e) {
  if (!/already been added|duplicate command|already exists/i.test(String(e && e.message))) {
    throw e;
  }
}
try {
  registerClass12CompleteAllFourTests();
} catch (e) {
  if (!/already been added|duplicate command|already exists/i.test(String(e && e.message))) {
    throw e;
  }
}
