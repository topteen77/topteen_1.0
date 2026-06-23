(function () {
  'use strict';

  function styleEmailTemplateEditor(editor) {
    if (!editor || !editor.element || editor.element.getId() !== 'id_body_html_template') {
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

  function getBodyHtmlValue() {
    if (window.CKEDITOR && CKEDITOR.instances.id_body_html_template) {
      return CKEDITOR.instances.id_body_html_template.getData();
    }
    var textarea = document.getElementById('id_body_html_template');
    return textarea ? textarea.value : '';
  }

  function refreshEmailPreview() {
    var wrap = document.querySelector('.email-template-live-preview-wrap');
    if (!wrap) {
      return;
    }

    var slug = wrap.getAttribute('data-slug');
    var objectIdMatch = window.location.pathname.match(/emailmessagetemplate\/(\d+)\/change\//);
    if (!slug || !objectIdMatch) {
      return;
    }

    var subjectInput = document.getElementById('id_subject_template');
    var button = wrap.querySelector('.email-template-preview-refresh');
    if (button) {
      button.disabled = true;
      button.textContent = 'Refreshing...';
    }

    var formData = new FormData();
    formData.append('subject_template', subjectInput ? subjectInput.value : '');
    formData.append('body_html_template', getBodyHtmlValue());
    formData.append('csrfmiddlewaretoken', getCsrfToken());

    fetch('/admin/communication/emailmessagetemplate/' + objectIdMatch[1] + '/preview/', {
      method: 'POST',
      body: formData,
      credentials: 'same-origin',
      headers: {
        'X-CSRFToken': getCsrfToken(),
      },
    })
      .then(function (response) { return response.json(); })
      .then(function (data) {
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
        window.alert('Could not refresh email preview. Save the template and try again.');
      })
      .finally(function () {
        if (button) {
          button.disabled = false;
          button.textContent = 'Refresh preview from fields above';
        }
      });
  }

  function bindPreviewRefresh() {
    document.querySelectorAll('.email-template-preview-refresh').forEach(function (button) {
      button.addEventListener('click', refreshEmailPreview);
    });
  }

  if (window.CKEDITOR) {
    CKEDITOR.on('instanceReady', function (evt) {
      styleEmailTemplateEditor(evt.editor);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindPreviewRefresh);
  } else {
    bindPreviewRefresh();
  }
})();
