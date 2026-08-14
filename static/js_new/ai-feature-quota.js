/**
 * Shared student/parent AI feature quota helpers for widgets.
 * Expects window.AIFeatureQuotaConfig = { statusUrl, consumeUrl, shopUrl, csrfToken }.
 */
(function (global) {
  "use strict";

  var CFG = Object.assign(
    {
      statusUrl: "/ai-feature-quota/status/",
      consumeUrl: "/ai-feature-quota/consume/",
      shopUrl: "/ai-tokens/",
      csrfToken: "",
      message: "AI tokens need to recharge — Buy now.",
      ctaLabel: "Buy now",
    },
    global.AIFeatureQuotaConfig || {}
  );

  function csrf() {
    if (CFG.csrfToken) return CFG.csrfToken;
    var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function fetchStatus() {
    return fetch(CFG.statusUrl, {
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "X-Requested-With": "XMLHttpRequest",
      },
    }).then(function (r) {
      if (!r.ok) throw new Error("quota status failed");
      return r.json();
    });
  }

  function consume(feature) {
    return fetch(CFG.consumeUrl, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-CSRFToken": csrf(),
        "X-Requested-With": "XMLHttpRequest",
      },
      body: JSON.stringify({ feature: feature }),
    }).then(function (r) {
      return r.json().then(function (data) {
        return { ok: r.ok, status: r.status, data: data || {} };
      });
    });
  }

  function featureLocked(statusPayload, featureKey) {
    if (!statusPayload || !statusPayload.applies) return false;
    var f = (statusPayload.features || {})[featureKey] || {};
    return !!f.locked;
  }

  function mountInfo(container, opts) {
    opts = opts || {};
    if (!container) return null;
    var el = container.querySelector(".ai-quota-info");
    if (!el) {
      el = document.createElement("div");
      el.className = "ai-quota-info";
      el.innerHTML =
        '<a class="ai-quota-info__link" href="#">' +
        '<i class="bx bx-info-circle" aria-hidden="true"></i> ' +
        '<span class="ai-quota-info__text"></span></a>';
      container.appendChild(el);
    }
    var link = el.querySelector(".ai-quota-info__link");
    var text = el.querySelector(".ai-quota-info__text");
    var msg = opts.message || CFG.message;
    var shop = opts.shopUrl || CFG.shopUrl;
    if (text) text.textContent = msg;
    if (link) {
      link.href = shop;
      link.title = msg;
    }
    el.hidden = !opts.visible;
    return el;
  }

  global.AIFeatureQuota = {
    config: CFG,
    fetchStatus: fetchStatus,
    consume: consume,
    featureLocked: featureLocked,
    mountInfo: mountInfo,
    RECHARGE_MESSAGE: CFG.message,
    CTA_LABEL: CFG.ctaLabel,
  };
})(window);
