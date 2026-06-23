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

  if (window.CKEDITOR) {
    CKEDITOR.on('instanceReady', function (evt) {
      styleEmailTemplateEditor(evt.editor);
    });
  }
})();
