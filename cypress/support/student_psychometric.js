/**
 * Support for student psychometric E2E: password login via /user/loginsingup/ + /user/loginpwd/.
 *
 * Cypress open can re-evaluate this file when switching specs; duplicate Cypress.Commands.add throws
 * and blocks the next spec. Register each command only once.
 */

function csrfFromHtml(html) {
  const v = Cypress.$(html).find('input[name="csrfmiddlewaretoken"]').first().val();
  if (v) return String(v);
  const m = String(html).match(/name=["']csrfmiddlewaretoken["']\s+value=["']([^"']+)["']/i);
  return m ? m[1] : "";
}

/**
 * @param {string} email Student email (e.g. from Cypress.env)
 * @param {string} [password] Defaults to Cypress.env('studentDefaultPassword') or '12345'
 */
function registerStudentLoginPassword() {
  Cypress.Commands.add("studentLoginPassword", (email, password) => {
    const pwd =
      password !== undefined && password !== null && password !== ""
        ? String(password)
        : Cypress.env("studentDefaultPassword") || "12345";
    const base = String(Cypress.config("baseUrl") || "").replace(/\/$/, "");
    expect(email, "student email").to.be.a("string").and.not.be.empty;

    cy.request({ method: "GET", url: `${base}/user/login/` }).then((resp) => {
      const csrf = csrfFromHtml(resp.body);
      expect(csrf, "CSRF from /user/login/").to.not.be.empty;

      cy.request({
        method: "POST",
        url: `${base}/user/loginsingup/`,
        form: true,
        body: {
          csrfmiddlewaretoken: csrf,
          user_name: email,
        },
        headers: { Referer: `${base}/user/login/` },
      }).then((r2) => {
        expect(r2.status, "loginsingup status").to.eq(200);
        expect(r2.body.show_password, "expect password step for students").to.eq(
          true
        );
        const enc = r2.body.enc_user_name;
        expect(enc, "enc_user_name").to.be.a("string").and.not.be.empty;

        cy.request({
          method: "POST",
          url: `${base}/user/loginpwd/`,
          form: true,
          body: {
            csrfmiddlewaretoken: csrf,
            enc_user_name: enc,
            password: pwd,
          },
          headers: { Referer: `${base}/user/login/` },
        }).then((r3) => {
          expect(r3.status, "loginpwd status").to.eq(200);
          expect(
            r3.body.success,
            r3.body.errMsg || r3.body.message || JSON.stringify(r3.body)
          ).to.eq(true);
          // Apply session cookies to the browser so the next cy.visit() is logged in (fixes 2nd spec / stale session).
          cy.visit(`${base}/`, { failOnStatusCode: false, log: false });
        });
      });
    });
  });
}

/**
 * Multistep tests with `#multiStepForm` (Test 1, aptitude subtests).
 * The last question shows Submit while no option is selected yet; `validateForm()` requires every
 * question answered — so we must pick an option on `.question.active` before clicking Submit.
 *
 * @param {number} [maxSteps] safety cap (default 200; ~60 questions may need answer + Continue each)
 */
function registerPsychometricAnswerTest1AllQuestions() {
  Cypress.Commands.add("psychometricAnswerTest1AllQuestions", (maxSteps = 200) => {
    cy.get("#multiStepForm", { timeout: 120000 }).should("exist");

    /** ~300ms auto-forward in template; small buffer so Continue is visible when auto-forward is off */
    const afterRadioMs = 450;

    const loop = (remaining) => {
      if (remaining <= 0) {
        cy.then(() => {
          throw new Error(
            "psychometricAnswerTest1AllQuestions: exceeded max steps (test may have changed or stuck)"
          );
        });
        return;
      }

      cy.get(".question.active", { timeout: 60000 }).then(($active) => {
        const hasRadios = $active.find('input[type="radio"]').length > 0;
        const answered =
          hasRadios && $active.find('input[type="radio"]:checked').length > 0;
        const $submitInActive = $active.find(".submit-button:visible");
        const $nextInActive = $active.find(".next-button:visible");

        if (hasRadios && !answered) {
          cy.wrap($active).find("label.custom-radio").first().click({ force: true });
          cy.wait(afterRadioMs);
          cy.then(() => loop(remaining));
          return;
        }

        if ($submitInActive.length && answered) {
          cy.wrap($submitInActive.first()).scrollIntoView();
          cy.url().then((urlBefore) => {
            cy.wrap($submitInActive.first()).click({ force: true });
            cy.url({ timeout: 120000 }).should((u) => u !== urlBefore);
            cy.document().its("readyState").should("eq", "complete");
          });
          return;
        }

        if ($nextInActive.length) {
          cy.wrap($nextInActive.first()).click({ force: true });
          cy.wait(150);
          cy.then(() => loop(remaining - 1));
          return;
        }

        cy.wait(200);
        cy.then(() => loop(remaining - 1));
      });
    };

    loop(maxSteps);
  });
}

try {
  registerStudentLoginPassword();
} catch (e) {
  if (!/already been added|duplicate command|already exists/i.test(String(e && e.message))) {
    throw e;
  }
}
try {
  registerPsychometricAnswerTest1AllQuestions();
} catch (e) {
  if (!/already been added|duplicate command|already exists/i.test(String(e && e.message))) {
    throw e;
  }
}

/**
 * Class 10 — Career Interest (`/psychometric/test2/`): on each step, check the **first 5**
 * checkboxes in `.question.active`, then Continue (steps 1–5) or Submit (step 6).
 */
function registerPsychometricAnswerTest2AllQuestions() {
  Cypress.Commands.add("psychometricAnswerTest2AllQuestions", (maxSteps = 40) => {
    cy.get("#multiStepForm", { timeout: 120000 }).should("exist");

    const step = (remaining) => {
      if (remaining <= 0) {
        cy.then(() => {
          throw new Error(
            "psychometricAnswerTest2AllQuestions: exceeded max steps (test may have changed or stuck)"
          );
        });
        return;
      }
      cy.url().then((href) => {
        if (href.includes("/psychometric/submit")) {
          return;
        }
        cy.get(".question.active", { timeout: 60000 }).should("be.visible");
        cy.get(".question.active input[type='checkbox']").each(($el, idx) => {
          if (idx < 5) {
            cy.wrap($el).check({ force: true });
          }
        });
        cy.wait(200);
        cy.get("body").then(($b) => {
          const $sub = $b.find(".question.active .submit-button:visible");
          if ($sub.length) {
            cy.wrap($sub.first()).scrollIntoView();
            cy.url().then((urlBefore) => {
              cy.wrap($sub.first()).click({ force: true });
              cy.url({ timeout: 120000 }).should((u) => u !== urlBefore);
              cy.document().its("readyState").should("eq", "complete");
            });
          } else {
            cy.get(".question.active .next-button").click({ force: true });
            cy.wait(250);
            cy.then(() => step(remaining - 1));
          }
        });
      });
    };

    step(maxSteps);
  });
}

try {
  registerPsychometricAnswerTest2AllQuestions();
} catch (e) {
  if (!/already been added|duplicate command|already exists/i.test(String(e && e.message))) {
    throw e;
  }
}

// Class 12 post-matric hub command — loaded here so `supportFile: student_psychometric.js` still works.
require("./class12_career_direction");
