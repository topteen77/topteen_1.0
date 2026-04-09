const { defineConfig } = require("cypress");

/**
 * Counselor course E2E (counselor_course_smoke.cy.js).
 *
 * Run: npx cypress run --config-file cypress/cypress.counselor.config.js
 * Open: npx cypress open --config-file cypress/cypress.counselor.config.js
 *
 * Credentials: counselorEmail + counselorPassword (same keys as root cypress.config.js env).
 * Override: CYPRESS_counselorEmail=... CYPRESS_counselorPassword=...
 * Optional: CYPRESS_counselorCourseFast=true  CYPRESS_counselorCourseMaxSteps=40
 * Login helper: cy.counselorLoginPassword in cypress/support/counselor_login.js
 */
module.exports = defineConfig({
  e2e: {
    supportFile: "cypress/support/e2e.js",
    specPattern: "cypress/e2e/counselor_course_smoke.cy.js",
    baseUrl: process.env.CYPRESS_BASE_URL || "http://localhost:8002",
    video: false,
    screenshotOnRunFailure: true,
    chromeWebSecurity: false,
    redirectionLimit: 100,
    env: {
      counselorEmail: "demo_counselor@topteen.demo",
      counselorPassword: "12345",
      counselorCourseFast: false,
    },
  },
});
