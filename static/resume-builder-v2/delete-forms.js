(function (global) {
  "use strict";

  var DEFAULT_OPTS = {
    title: "Delete this resume?",
    message: "All sections and content will be permanently removed. This cannot be undone.",
    confirmLabel: "Delete resume",
    cancelLabel: "Keep resume",
    variant: "danger",
  };

  function bindDeleteForm(form) {
    if (!form || form.dataset.rb2DeleteBound === "1") return;
    form.dataset.rb2DeleteBound = "1";
    form.addEventListener("submit", function (e) {
      if (form.dataset.rb2DeleteConfirmed === "1") {
        form.dataset.rb2DeleteConfirmed = "";
        return;
      }
      e.preventDefault();
      var msgs = global.RB2Messages;
      if (!msgs || typeof msgs.confirm !== "function") {
        form.dataset.rb2DeleteConfirmed = "1";
        form.submit();
        return;
      }
      msgs
        .confirm({
          title: form.dataset.deleteTitle || DEFAULT_OPTS.title,
          message: form.dataset.deleteMessage || DEFAULT_OPTS.message,
          confirmLabel: form.dataset.deleteConfirm || DEFAULT_OPTS.confirmLabel,
          cancelLabel: form.dataset.deleteCancel || DEFAULT_OPTS.cancelLabel,
          variant: DEFAULT_OPTS.variant,
        })
        .then(function (ok) {
          if (!ok) return;
          form.dataset.rb2DeleteConfirmed = "1";
          if (typeof form.requestSubmit === "function") {
            form.requestSubmit();
          } else {
            form.submit();
          }
        });
    });
  }

  function init() {
    document
      .querySelectorAll(".rb2-resume-delete-form, .my-resume-delete-form")
      .forEach(bindDeleteForm);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  global.RB2DeleteForms = { init: init, bind: bindDeleteForm };
})(typeof window !== "undefined" ? window : this);
