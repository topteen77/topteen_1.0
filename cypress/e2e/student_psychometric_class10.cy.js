/**
 * Class 10 — Stream Sorter psychometric E2E: Book Now → Test 1 (Personality) → Test 2 (Career Interest)
 * → Test 3 hub + all 7 aptitude subtests (after each prior section shows "View report", or if already completed).
 *
 * Env:
 * - `psychometricSkipTest1Full` — stop after `/psychometric/home` (no Test 1–3 automation).
 * - `psychometricSkipTest2And3` — after Test 1, do not run Tests 2–3.
 */

describe("Student psychometric — Class 10 (Stream Sorter → Tests 1–3)", () => {
  const timeoutPage = 25000;
  const base = () => String(Cypress.config("baseUrl") || "").replace(/\/$/, "");

  const cardHasViewReport = ($card) =>
    $card.find("a.btn.blue-button").filter((_, el) => /View report/i.test(el.textContent))
      .length > 0;

  beforeEach(() => {
    cy.clearCookies();
    cy.clearLocalStorage();
  });

  it("login → Book Now → dashboard → Test 1 → Test 2 → Test 3 (when applicable)", () => {
    const email =
      Cypress.env("studentClass10Email") || "demo_student_1@topteen.demo";
    const password = Cypress.env("studentDefaultPassword");
    const skipFull =
      Cypress.env("psychometricSkipTest1Full") === true ||
      Cypress.env("psychometricSkipTest1Full") === "true";
    const skipTest2And3 =
      Cypress.env("psychometricSkipTest2And3") === true ||
      Cypress.env("psychometricSkipTest2And3") === "true";

    cy.studentLoginPassword(email, password);

    cy.visit(`${base()}/psychometrictest/stream-sorter/`, {
      timeout: timeoutPage,
    });

    cy.location("pathname", { timeout: timeoutPage }).then((pathname) => {
      if (!pathname.includes("/psychometrictest/")) {
        cy.log(
          "Already redirected off Stream Sorter landing (e.g. paid) — smoke session only."
        );
        cy.visit(`${base()}/user/dashboard/`, {
          timeout: timeoutPage,
          failOnStatusCode: false,
        });
        cy.get("body", { timeout: timeoutPage }).should("exist");
        return;
      }

      cy.contains(/Stream Sorter/i, { timeout: timeoutPage }).should("be.visible");

      cy.get("#payment-section form#paymentForm button.cta-button", {
        timeout: timeoutPage,
      })
        .should("be.visible")
        .should("contain.text", "Book Now")
        .scrollIntoView()
        .click({ force: true });

      cy.url({ timeout: 30000 }).should("include", "/psychometric/home");

      cy.contains("h2.title-test-info", "Psychometric Assessment", {
        timeout: timeoutPage,
      }).should("be.visible");

      if (skipFull) {
        cy.log("psychometricSkipTest1Full — skipping Test 1–3.");
        return;
      }

      cy.get("body").then(($body) => {
        const $card = $body
          .find(".psychometric-card")
          .filter((_, el) =>
            Cypress.$(el).text().includes("Personality assessment")
          );
        const $start = $card
          .find('button[type="submit"]')
          .filter((_, el) =>
            /Start Test|Resume Test/i.test(Cypress.$(el).text())
          );

        if ($start.length) {
          cy.wrap($start.first()).click({ force: true });
          cy.url({ timeout: timeoutPage }).should(
            "include",
            "/psychometric/t1_intro"
          );
          cy.contains("button", /Start Test/i, { timeout: timeoutPage })
            .should("be.visible")
            .click();
          cy.url({ timeout: timeoutPage }).should(
            "include",
            "/psychometric/test1"
          );
          cy.psychometricAnswerTest1AllQuestions(200);
          cy.url({ timeout: 120000 }).should(
            "include",
            "/psychometric/submit"
          );
          cy.get("body.test-submit-page", { timeout: timeoutPage }).should(
            "exist"
          );
        } else {
          cy.log(
            "Personality test already completed — assert View report link."
          );
          cy.wrap($card)
            .find("a.btn.blue-button")
            .should("be.visible")
            .and("contain.text", "View report");
        }
      });

      cy.then(() => {
        if (skipTest2And3) {
          cy.log("psychometricSkipTest2And3 — stopping after Test 1 flow.");
          return;
        }

        cy.visit(`${base()}/psychometric/submit`, { timeout: timeoutPage });

        cy.get("h2.title-test-info", { timeout: timeoutPage }).should(
          "contain.text",
          "Psychometric Assessment"
        );

        cy.contains("h3", "Personality assessment")
          .closest(".psychometric-card")
          .then(($card) => {
            expect(
              cardHasViewReport($card),
              "Personality assessment should show View report before Test 2"
            ).to.eq(true);
          });

        cy.contains("h3", "Career Interest assessment")
          .closest(".psychometric-card")
          .then(($card) => {
            if (cardHasViewReport($card)) {
              cy.log("Career Interest already complete — skipping Test 2.");
              return;
            }
            cy.wrap($card)
              .find("form")
              .first()
              .within(() => {
                cy.get('button[type="submit"]')
                  .contains(/Start Test|Resume Test/i)
                  .click({ force: true });
              });
            cy.url({ timeout: timeoutPage }).should(
              "include",
              "/psychometric/t2_intro"
            );
            cy.contains("form button", /Start/i, { timeout: timeoutPage })
              .should("be.visible")
              .click();
            cy.url({ timeout: timeoutPage }).should(
              "include",
              "/psychometric/test2"
            );
            cy.psychometricAnswerTest2AllQuestions(40);
            cy.visit(`${base()}/psychometric/submit`, { timeout: timeoutPage });
          });

        cy.contains("h3", "Career Interest assessment")
          .closest(".psychometric-card")
          .then(($card) => {
            expect(
              cardHasViewReport($card),
              "Career Interest should show View report before Test 3"
            ).to.eq(true);
          });

        cy.contains("h3", "Comprehensive Aptitude assessment")
          .closest(".psychometric-card")
          .then(($card) => {
            if (cardHasViewReport($card)) {
              cy.log(
                "Comprehensive Aptitude already complete — skipping Test 3."
              );
              return;
            }
            cy.wrap($card)
              .find("form")
              .first()
              .within(() => {
                cy.get('button[type="submit"]')
                  .contains(/Start Test|Resume Test/i)
                  .click({ force: true });
              });
            cy.url({ timeout: timeoutPage }).should(
              "include",
              "/psychometric/t3_intro"
            );
            cy.contains("form button", /Start/i, { timeout: timeoutPage })
              .should("be.visible")
              .click();
            cy.url({ timeout: timeoutPage }).should(
              "include",
              "/psychometric/test3"
            );

            const subtests = [
              "Numerical",
              "Verbal",
              "Logical",
              "Critical",
              "Mechanical",
              "Language",
              "Spatial",
            ];

            const runSubtest = (index) => {
              if (index >= subtests.length) {
                cy.visit(`${base()}/psychometric/submit`, {
                  timeout: timeoutPage,
                });
                cy.contains("h3", "Comprehensive Aptitude assessment")
                  .closest(".psychometric-card")
                  .then(($apt) => {
                    if (cardHasViewReport($apt)) {
                      cy.log("Comprehensive Aptitude shows View report.");
                    }
                  });
                return;
              }

              const label = subtests[index];
              cy.get(".subtest-grid", { timeout: timeoutPage }).should(
                "be.visible"
              );
              cy.contains("button.subtest-button", label, {
                timeout: timeoutPage,
              })
                .should("be.visible")
                .then(($btn) => {
                  if ($btn.hasClass("completed")) {
                    cy.log(
                      `${label} subtest already marked completed — skipping.`
                    );
                    cy.then(() => runSubtest(index + 1));
                    return;
                  }
                  cy.wrap($btn).click();
                  cy.url({ timeout: timeoutPage }).should(
                    "include",
                    "/psychometric/test3_"
                  );
                  cy.psychometricAnswerTest1AllQuestions(200);
                  // Some subtests leave the browser on the same URL after POST; always load the hub explicitly.
                  cy.location("pathname", { timeout: 120000 }).then((pathname) => {
                    const n = pathname.replace(/\/$/, "") || pathname;
                    if (n !== "/psychometric/test3") {
                      cy.visit(`${base()}/psychometric/test3/`, {
                        timeout: timeoutPage,
                      });
                    }
                  });
                  cy.location("pathname", { timeout: timeoutPage }).should(
                    (pathname) => {
                      const n = pathname.replace(/\/$/, "") || pathname;
                      expect(n, "aptitude hub").to.eq("/psychometric/test3");
                    }
                  );
                  cy.then(() => runSubtest(index + 1));
                });
            };

            runSubtest(0);
          });
      });
    });
  });
});
