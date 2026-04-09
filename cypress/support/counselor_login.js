/**
 * Counselor E2E: password login via /user/loginsingup/ + /user/loginpwd/ (same HTTP flow as students).
 * Does not require show_password from loginsingup so accounts with default password still authenticate.
 */

function csrfFromHtml(html) {
  const v = Cypress.$(html).find('input[name="csrfmiddlewaretoken"]').first().val();
  if (v) return String(v);
  const m = String(html).match(/name=["']csrfmiddlewaretoken["']\s+value=["']([^"']+)["']/i);
  return m ? m[1] : "";
}

function counselorIdFromRedirectUrl(url) {
  const s = String(url || "");
  const m = s.match(/counselor_dashboard\/(\d+)/);
  return m ? Number(m[1]) : null;
}

function registerCounselorLoginPassword() {
  Cypress.Commands.add("counselorLoginPassword", (email, password) => {
    const pwd =
      password !== undefined && password !== null && password !== ""
        ? String(password)
        : Cypress.env("counselorPassword") || "12345";
    const base = String(Cypress.config("baseUrl") || "").replace(/\/$/, "");
    expect(email, "counselor email").to.be.a("string").and.not.be.empty;

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
        const enc = r2.body.enc_user_name;
        expect(enc, "enc_user_name from loginsingup").to.be.a("string").and.not.be.empty;

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
          const redir = r3.body.redirect_url || "";
          const id = counselorIdFromRedirectUrl(redir);
          expect(id, `expected counselor dashboard in redirect_url: ${redir}`).to.be.a("number");
          cy.wrap(id).as("counselorId");
          cy.visit(`${base}/`, { failOnStatusCode: false, log: false });
        });
      });
    });
  });
}

try {
  registerCounselorLoginPassword();
} catch (e) {
  if (!/already been added|duplicate command|already exists/i.test(String(e && e.message))) {
    throw e;
  }
}
