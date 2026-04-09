const { defineConfig } = require("cypress");

/**
 * Student psychometric smoke tests (Class 10 Stream Sorter + Class 12 Career Direction).
 *
 * Run: npx cypress run --config-file cypress/cypress.student.psychometric.config.js
 * Open: npx cypress open --config-file cypress/cypress.student.psychometric.config.js
 *
 * Override credentials (CLI): CYPRESS_studentClass12Email=... CYPRESS_studentDefaultPassword=...
 * Or set env in this file / cypress.env.json (not committed).
 *
 * Class 12: Career Direction uses ADVANCED payment; paid users hitting career-direction are
 * redirected to /api/web/tests/ (post_matric Tests). Class 12 spec reads studentClass12Email +
 * studentDefaultPassword only from env below (no hardcoded fallbacks in the spec).
 */
module.exports = defineConfig({
  e2e: {
    // Loads login helpers + Class 12 post-matric hub command (see cypress/support/e2e.js).
    supportFile: "cypress/support/e2e.js",
    specPattern: "cypress/e2e/student_psychometric_class*.cy.js",
    baseUrl: "http://localhost:8002",
    redirectionLimit: 60,
    chromeWebSecurity: false,
    env: {
      /** Class 10 (Stream Sorter) demo student */
      studentClass10Email: "demo_student_1@topteen.demo",
      /** Class 12 (Career Direction) — must be class 12 + ADVANCED access as your Django DB expects */
      studentClass12Email: "test12@yopmail.com",
      /** Must match Django password for these users */
      studentDefaultPassword: "12345",
      /** Class 12: run post-matric take_test smoke (hub → Start Test → Begin). Set false for faster runs. */
      class12DeepTakeTest: true,
      /** Class 10 only: if true, stop after /psychometric/home (skip answering Test 1; saves many minutes). */
      psychometricSkipTest1Full: false,
      /** Class 10 only: if true, after Test 1 dashboard skip Career Interest + Aptitude automation. */
      psychometricSkipTest2And3: false,
    },
  },
});
