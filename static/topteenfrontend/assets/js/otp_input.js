(function () {
  'use strict';

  function getOtpContainer(el) {
    if (!el) return null;
    return (
      el.closest('#studentLoginOtpInputs, #studentSignupOtpInputs, #loginOtpInputStep')
      || el.closest('.otp-inputs-container')
    );
  }

  function getOtpInputs(container) {
    if (!container) return [];
    return Array.from(container.querySelectorAll('input'));
  }

  function fillOtpDigitInputs(inputs, rawText) {
    var digits = String(rawText || '').replace(/\D/g, '');
    if (!digits || !inputs.length) return false;
    var slice = digits.slice(0, inputs.length);
    for (var i = 0; i < inputs.length; i++) {
      inputs[i].value = slice[i] || '';
    }
    var focusIdx = Math.min(slice.length, inputs.length) - 1;
    if (focusIdx >= 0) {
      inputs[focusIdx].focus();
    }
    return slice.length === inputs.length;
  }

  function triggerOtpAutoSubmit(container, form) {
    setTimeout(function () {
      if (form && form.id) {
        if (form.id === 'singupotp' && typeof handleOtpSubmit === 'function') {
          handleOtpSubmit();
          return;
        }
        if (form.id === 'forgototppwd' && typeof forgotpasswordotp === 'function') {
          forgotpasswordotp();
          return;
        }
      }
      if (container && container.id === 'loginOtpInputStep' && typeof verifyLoginOtp === 'function') {
        verifyLoginOtp();
        return;
      }
      if (container && container.id === 'studentLoginOtpInputs') {
        var loginBtn = document.getElementById('studentLoginVerifyOtp');
        if (loginBtn) loginBtn.click();
        return;
      }
      if (container && container.id === 'studentSignupOtpInputs') {
        var signupBtn = document.getElementById('studentSignupVerifyOtp');
        if (signupBtn) signupBtn.click();
      }
    }, 100);
  }

  function distributeOtpFromTarget(target, rawText) {
    var container = getOtpContainer(target);
    if (!container) return false;
    var inputs = getOtpInputs(container);
    var complete = fillOtpDigitInputs(inputs, rawText);
    if (complete) {
      triggerOtpAutoSubmit(container, target.closest('form'));
    }
    return complete;
  }

  function onOtpPaste(e) {
    var target = e.target;
    if (!target || target.tagName !== 'INPUT') return;
    var container = getOtpContainer(target);
    if (!container) return;

    var clipboard = e.clipboardData || window.clipboardData;
    var pasted = clipboard ? clipboard.getData('text') : '';
    var digits = String(pasted || '').replace(/\D/g, '');
    if (!digits) return;

    e.preventDefault();
    distributeOtpFromTarget(target, digits);
  }

  function onOtpInput(e) {
    var target = e.target;
    if (!target || target.tagName !== 'INPUT') return;
    var container = getOtpContainer(target);
    if (!container) return;

    var digits = String(target.value || '').replace(/\D/g, '');
    if (digits.length <= 1) return;

    target.value = '';
    distributeOtpFromTarget(target, digits);
  }

  document.addEventListener('paste', onOtpPaste, true);
  document.addEventListener('input', onOtpInput, true);
})();
