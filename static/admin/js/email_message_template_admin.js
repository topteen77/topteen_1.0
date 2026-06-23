(function () {
  'use strict';

  var previewDebounceTimer = null;
  var PREVIEW_DEBOUNCE_MS = 200;
  var previewRequestId = 0;
  var previewInitialized = false;
  var BODY_FIELD_ID = 'id_body_html_template';

  function styleEmailTemplateEditor(editor) {
    if (!editor || !editor.element || editor.element.getId() !== BODY_FIELD_ID) {
      return;
    }

    function applySourceStyles() {
      var doc = editor.document;
      if (doc && doc.getBody && doc.getBody()) {
        var body = doc.getBody().$;
        body.style.background = '#ffffff';
        body.style.color = '#111111';
        body.style.webkitTextFillColor = '#111111';
      }

      var textarea = editor.container && editor.container.findOne('textarea.cke_source');
      if (textarea && textarea.$) {
        textarea.$.style.background = '#ffffff';
        textarea.$.style.color = '#111111';
        textarea.$.style.webkitTextFillColor = '#111111';
        textarea.$.style.caretColor = '#111111';
      }
    }

    applySourceStyles();
    editor.on('mode', applySourceStyles);
    editor.on('contentDom', applySourceStyles);
  }

  function getCsrfToken() {
    var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : '';
  }

  function getBodyHtmlEditor() {
    if (!window.CKEDITOR || !CKEDITOR.instances) {
      return null;
    }

    if (CKEDITOR.instances[BODY_FIELD_ID]) {
      return CKEDITOR.instances[BODY_FIELD_ID];
    }

    var instanceNames = Object.keys(CKEDITOR.instances);
    for (var i = 0; i < instanceNames.length; i++) {
      var editor = CKEDITOR.instances[instanceNames[i]];
      try {
        if (editor.element && editor.element.getId() === BODY_FIELD_ID) {
          return editor;
        }
      } catch (err) {
        continue;
      }
    }
    return null;
  }

  function getBodyHtmlValue() {
    var editor = getBodyHtmlEditor();
    if (editor) {
      return editor.getData();
    }

    var textarea = document.getElementById(BODY_FIELD_ID);
    return textarea ? textarea.value : '';
  }

  function getPreviewUrl() {
    var wrap = document.querySelector('.email-template-live-preview-wrap');
    if (wrap && wrap.getAttribute('data-preview-url')) {
      return wrap.getAttribute('data-preview-url');
    }

    var objectIdMatch = window.location.pathname.match(/emailmessagetemplate\/(\d+)\/change\/?/);
    if (!objectIdMatch) {
      return null;
    }
    return '/admin/communication/emailmessagetemplate/' + objectIdMatch[1] + '/preview/';
  }

  function scheduleEmailPreviewRefresh() {
    clearTimeout(previewDebounceTimer);
    previewDebounceTimer = setTimeout(function () {
      refreshEmailPreview({ silent: true });
    }, PREVIEW_DEBOUNCE_MS);
  }

  function refreshEmailPreview(options) {
    options = options || {};
    var silent = !!options.silent;

    var wrap = document.querySelector('.email-template-live-preview-wrap');
    if (!wrap) {
      return;
    }

    var previewUrl = getPreviewUrl();
    if (!previewUrl) {
      return;
    }

    var subjectInput = document.getElementById('id_subject_template');
    var button = wrap.querySelector('.email-template-preview-refresh');
    var requestId = ++previewRequestId;
    var bodyHtml = getBodyHtmlValue();

    if (!silent && button) {
      button.disabled = true;
      button.textContent = 'Refreshing...';
    }

    var formData = new FormData();
    formData.append('subject_template', subjectInput ? subjectInput.value : '');
    formData.append('body_html_template', bodyHtml);
    formData.append('csrfmiddlewaretoken', getCsrfToken());

    fetch(previewUrl, {
      method: 'POST',
      body: formData,
      credentials: 'same-origin',
      headers: {
        'X-CSRFToken': getCsrfToken(),
      },
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error('HTTP ' + response.status);
        }
        return response.json();
      })
      .then(function (data) {
        if (requestId !== previewRequestId) {
          return;
        }
        if (!data || !data.html) {
          throw new Error('Preview unavailable');
        }

        var subjectLine = wrap.querySelector('p strong');
        if (subjectLine && subjectLine.parentNode && data.subject) {
          subjectLine.parentNode.innerHTML = '<strong>Subject:</strong> ' + data.subject;
        }

        var iframe = wrap.querySelector('.email-template-live-preview-frame');
        if (iframe) {
          iframe.srcdoc = data.html;
        }
      })
      .catch(function () {
        if (!silent) {
          window.alert('Could not refresh email preview. Save the template and try again.');
        }
      })
      .finally(function () {
        if (!silent && button) {
          button.disabled = false;
          button.textContent = 'Refresh preview from fields above';
        }
      });
  }

  function bindSourceModePreview(editor) {
    if (!editor || editor.element.getId() !== BODY_FIELD_ID) {
      return;
    }
    if (editor.mode === 'source') {
      var textarea = editor.container.findOne('textarea.cke_source');
      if (textarea && textarea.$ && !textarea.$.dataset.previewBound) {
        textarea.$.dataset.previewBound = '1';
        textarea.$.addEventListener('input', scheduleEmailPreviewRefresh);
      }
    }
  }

  function bindCkEditorPreview(editor) {
    if (!editor || !editor.element || editor.element.getId() !== BODY_FIELD_ID) {
      return;
    }
    if (editor._emailPreviewBound) {
      return;
    }
    editor._emailPreviewBound = true;

    editor.on('change', scheduleEmailPreviewRefresh);
    editor.on('keyup', scheduleEmailPreviewRefresh);
    editor.on('key', scheduleEmailPreviewRefresh);
    editor.on('afterPaste', scheduleEmailPreviewRefresh);
    editor.on('mode', function () {
      bindSourceModePreview(editor);
      scheduleEmailPreviewRefresh();
    });
    bindSourceModePreview(editor);
  }

  function bindExistingEditors() {
    if (!window.CKEDITOR || !CKEDITOR.instances) {
      return;
    }
    Object.keys(CKEDITOR.instances).forEach(function (name) {
      var editor = CKEDITOR.instances[name];
      styleEmailTemplateEditor(editor);
      bindCkEditorPreview(editor);
    });
  }

  function waitForCkEditor(callback) {
    var attempts = 0;
    function tick() {
      attempts += 1;
      if (window.CKEDITOR) {
        callback();
        return;
      }
      if (attempts < 200) {
        setTimeout(tick, 50);
      }
    }
    tick();
  }

  function bindPreviewRefresh() {
    document.querySelectorAll('.email-template-preview-refresh').forEach(function (button) {
      if (button.dataset.previewBound) {
        return;
      }
      button.dataset.previewBound = '1';
      button.addEventListener('click', function () {
        refreshEmailPreview({ silent: false });
      });
    });

    var subjectInput = document.getElementById('id_subject_template');
    if (subjectInput && !subjectInput.dataset.previewBound) {
      subjectInput.dataset.previewBound = '1';
      subjectInput.addEventListener('input', scheduleEmailPreviewRefresh);
      subjectInput.addEventListener('change', scheduleEmailPreviewRefresh);
    }

    var bodyTextarea = document.getElementById(BODY_FIELD_ID);
    if (bodyTextarea && !getBodyHtmlEditor() && !bodyTextarea.dataset.previewBound) {
      bodyTextarea.dataset.previewBound = '1';
      bodyTextarea.addEventListener('input', scheduleEmailPreviewRefresh);
    }
  }

  function initEmailTemplatePreviewAdmin() {
    if (previewInitialized) {
      return;
    }
    previewInitialized = true;

    bindPreviewRefresh();

    waitForCkEditor(function () {
      CKEDITOR.on('instanceReady', function (evt) {
        styleEmailTemplateEditor(evt.editor);
        bindCkEditorPreview(evt.editor);
      });
      bindExistingEditors();
    });
  }

  window.initEmailTemplatePreviewAdmin = initEmailTemplatePreviewAdmin;
})();
