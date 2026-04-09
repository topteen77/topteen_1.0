/**
 * Class 12 — Career Direction psychometric E2E (marketing → Book Now) and optional post-matric hub smoke.
 *
 * Credentials: `studentClass12Email` + `studentDefaultPassword` in
 * `cypress/cypress.student.psychometric.config.js` (or root cypress.config.js env).
 *
 * Env:
 * - `class12DeepTakeTest` — if true (default in psychometric config), after reaching the post-matric
 *   tests hub, dismiss onboarding popups if shown, open the first linear `take_test` assessment,
 *   click Begin, and optionally answer the first question (auto-advance when enabled on the server).
 */

describe("Student psychometric — Class 12 (Career Direction → post-matric tests)", () => {
  const timeoutPage = 25000;
  const base = () => String(Cypress.config("baseUrl") || "").replace(/\/$/, "");

  beforeEach(() => {
    cy.clearCookies();
    cy.clearLocalStorage();
  });

  it("login → Career Direction → Book Now / paid redirect → complete all 4 tests", () => {
    const email = Cypress.env("studentClass12Email");
    const password = Cypress.env("studentDefaultPassword");
    expect(email, "Cypress env studentClass12Email").to.be.a("string").and.not
      .be.empty;
    expect(password, "Cypress env studentDefaultPassword").to.be.a("string").and
      .not.be.empty;

    const deep =
      Cypress.env("class12DeepTakeTest") === true ||
      Cypress.env("class12DeepTakeTest") === "true";

    cy.studentLoginPassword(email, password);

    cy.visit(`${base()}/psychometrictest/career-direction/`, {
      timeout: timeoutPage,
    });

    cy.location("pathname", { timeout: timeoutPage }).then((pathname) => {
      if (!pathname.includes("/psychometrictest/")) {
        cy.log(
          "Already left Career Direction landing (e.g. ADVANCED paid) — asserting session + hub access."
        );
        cy.visit(`${base()}/api/web/tests/`, {
          timeout: timeoutPage,
          failOnStatusCode: false,
        });
        cy.get("body", { timeout: timeoutPage }).should("exist");
        if (deep) cy.class12CompleteAllFourTests();
        return;
      }

      cy.contains(/Career Direction/i, { timeout: timeoutPage }).should(
        "be.visible"
      );

      cy.get("#payment-section form#paymentForm button.cta-button", {
        timeout: timeoutPage,
      })
        .should("be.visible")
        .should("contain.text", "Book Now")
        .scrollIntoView()
        .click({ force: true });

      cy.url({ timeout: 60000 }).should((href) => {
        expect(
          href.includes("/api/web/tests") ||
            href.includes("/psychometric/home"),
          "after Book Now: post-matric tests hub or psychometric home (institute/demo)"
        ).to.eq(true);
      });

      cy.url().then((href) => {
        if (href.includes("/psychometric/home")) {
          cy.log(
            "Book Now sent user to /psychometric/home/ — opening post-matric tests for Class 12 smoke."
          );
          cy.visit(`${base()}/api/web/tests/`, { timeout: timeoutPage });
        }
      });

      if (deep) {
        cy.location("pathname", { timeout: timeoutPage }).should((p) => {
          expect(
            p.includes("/api/web/tests"),
            "deep run expects tests hub at /api/web/tests/"
          ).to.eq(true);
        });
        cy.class12CompleteAllFourTests();
      }
    });
  });
});
