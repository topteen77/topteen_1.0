/**
 * v2 dashboard AJAX auth: never inject login page HTML into content hosts.
 * On session expiry, open the shared login popup and reload after success.
 */
(function (global) {
  'use strict';

  function isLoginPageHtml(html) {
    if (!html || typeof html !== 'string') return false;
    var s = html.toLowerCase();
    if (s.indexOf('enter your details') !== -1 && s.indexOf('usersloginsignup') !== -1) {
      return true;
    }
    if (s.indexOf('id="sign_in_form"') !== -1 || s.indexOf("id='sign_in_form'") !== -1) {
      return true;
    }
    if (s.indexOf('student-login-popup-global') !== -1 && s.indexOf('<!doctype html') !== -1) {
      return true;
    }
    return false;
  }

  function promptLogin() {
    if (global.__ttv2LoginPromptOpen) return true;
    global.__ttv2LoginPromptOpen = true;
    var nextUrl = global.location.href;
    if (typeof global.showLoginRequiredPopup === 'function') {
      global.showLoginRequiredPopup(nextUrl);
      return true;
    }
    global.location.href = '/user/login/?next=' + encodeURIComponent(nextUrl);
    return true;
  }

  function clearLoginPromptFlag() {
    global.__ttv2LoginPromptOpen = false;
  }

  /**
   * @returns {boolean} true when caller should abort (auth required)
   */
  function handleAuthResponse(response) {
    if (!response) return false;
    if (response.status === 401) {
      promptLogin();
      return true;
    }
    if (response.status >= 300 && response.status < 400) {
      var loc = (response.headers && response.headers.get
        ? response.headers.get('Location')
        : '') || '';
      var low = String(loc).toLowerCase();
      if (
        low.indexOf('/user/login') !== -1 ||
        low.indexOf('/student/login') !== -1 ||
        low.indexOf('/parents/login') !== -1 ||
        low.indexOf('/institute/auth/login') !== -1 ||
        low.indexOf('/counselor/auth/login') !== -1
      ) {
        promptLogin();
        return true;
      }
    }
    return false;
  }

  function ajaxFetchOptions(extra) {
    var opts = extra || {};
    opts.credentials = opts.credentials || 'same-origin';
    opts.redirect = opts.redirect || 'manual';
    opts.headers = opts.headers || {};
    if (!opts.headers['X-Requested-With']) {
      opts.headers['X-Requested-With'] = 'XMLHttpRequest';
    }
    return opts;
  }

  global.ttv2IsLoginPageHtml = isLoginPageHtml;
  global.ttv2PromptLogin = promptLogin;
  global.ttv2ClearLoginPromptFlag = clearLoginPromptFlag;
  global.ttv2HandleAuthResponse = handleAuthResponse;
  global.ttv2AjaxFetchOptions = ajaxFetchOptions;

  document.addEventListener('DOMContentLoaded', function () {
    var popup = document.getElementById('loginRequiredPopup');
    if (!popup) return;
    popup.addEventListener('transitionend', function () {
      if (!popup.classList.contains('show')) clearLoginPromptFlag();
    });
  });
})(typeof window !== 'undefined' ? window : this);
