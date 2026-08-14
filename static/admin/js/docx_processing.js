/* Global DOCX → HTML import for Django admin (sidebar + page toolbars) */
(function () {
    'use strict';

    if (window.TopTeenDocxHtmlImport) {
        return;
    }

    var lastConvertedHtml = '';
    var lastFocusedFieldKey = '';

    function processDocxFile(input) {
        var file = input && input.files && input.files[0];
        if (!file) {
            return;
        }

        if (!file.name.toLowerCase().endsWith('.docx')) {
            alert('Please select a DOCX file.');
            input.value = '';
            return;
        }

        if (file.size > 10 * 1024 * 1024) {
            alert('File size must be under 10MB.');
            input.value = '';
            return;
        }

        showProcessingStatus();
        processDocxContent(file, input);
    }

    function statusRoot() {
        return document.getElementById('docx-sidebar-status') ||
            document.getElementById('docx-processing-status');
    }

    function showProcessingStatus() {
        var statusDiv = statusRoot();
        if (statusDiv) {
            statusDiv.style.display = 'block';
            updateProgress(0, 'Starting conversion...');
        }
    }

    function updateProgress(percent, message) {
        var root = statusRoot();
        if (!root) {
            return;
        }
        var progressBar = root.querySelector('#progress-bar, .progress-bar');
        var processingMessage = root.querySelector('#processing-message, .processing-message');

        if (progressBar) {
            progressBar.style.width = percent + '%';
        }
        if (processingMessage) {
            processingMessage.textContent = message;
            processingMessage.className = 'processing-message';
        }
    }

    function processDocxContent(file, input) {
        var formData = new FormData();
        formData.append('docx_file', file);

        var csrf = getCookie('csrftoken');
        if (csrf) {
            formData.append('csrfmiddlewaretoken', csrf);
        }

        updateProgress(15, 'Uploading (temporary, in memory)...');

        fetch('/careers/api/process-docx/', {
            method: 'POST',
            body: formData,
            credentials: 'same-origin',
            headers: csrf ? { 'X-CSRFToken': csrf } : {},
        })
            .then(function (response) {
                updateProgress(55, 'Converting Word → HTML...');
                return response.json().then(function (data) {
                    if (!response.ok) {
                        throw new Error((data && data.error) || ('HTTP ' + response.status));
                    }
                    return data;
                });
            })
            .then(function (data) {
                updateProgress(90, 'Preparing preview...');
                if (!data.success) {
                    throw new Error(data.error || 'Unknown error occurred');
                }

                lastConvertedHtml = data.html || data.description || '';
                updateProgress(100, 'Conversion complete');
                hideProcessingStatus();
                showHtmlPreviewModal(lastConvertedHtml);

                if (input) {
                    input.value = '';
                }
            })
            .catch(function (error) {
                console.error('DOCX conversion error:', error);
                updateProgress(0, 'Error converting file');
                showErrorMessage('Error converting DOCX: ' + error.message);
            });
    }

    function discoverHtmlFields() {
        var fields = [];
        var seen = {};

        function addField(key, label, textarea, editor) {
            if (!key || seen[key]) {
                return;
            }
            seen[key] = true;
            fields.push({
                key: key,
                label: label,
                textarea: textarea || null,
                editor: editor || null,
            });
        }

        if (typeof CKEDITOR !== 'undefined' && CKEDITOR.instances) {
            Object.keys(CKEDITOR.instances).forEach(function (name) {
                var editor = CKEDITOR.instances[name];
                var el = editor && editor.element && editor.element.$;
                var label = fieldLabelFor(el, name);
                addField('ck:' + name, label, el, editor);
            });
        }

        document.querySelectorAll(
            'textarea.django-ckeditor-widget, .django-ckeditor-widget textarea, ' +
            'textarea[name*="description"], textarea[name*="content"], ' +
            'textarea[name*="answer"], textarea[name*="html"], ' +
            'textarea[name*="body"], textarea[name*="message"]'
        ).forEach(function (ta) {
            var id = ta.id || ta.name;
            if (!id) {
                return;
            }
            addField('ta:' + id, fieldLabelFor(ta, id), ta, null);
        });

        return fields;
    }

    function fieldLabelFor(el, fallback) {
        if (!el) {
            return humanize(fallback);
        }
        var id = el.id;
        if (id) {
            var label = document.querySelector('label[for="' + id + '"]');
            if (label && label.textContent.trim()) {
                return label.textContent.trim().replace(/\*$/, '').trim();
            }
        }
        var row = el.closest('.form-row, .fieldBox, .form-group');
        if (row) {
            var rowLabel = row.querySelector('label');
            if (rowLabel && rowLabel.textContent.trim()) {
                return rowLabel.textContent.trim().replace(/\*$/, '').trim();
            }
        }
        return humanize(el.name || el.id || fallback);
    }

    function humanize(value) {
        return String(value || 'HTML field')
            .replace(/^id_/, '')
            .replace(/_/g, ' ')
            .replace(/\b\w/g, function (c) { return c.toUpperCase(); });
    }

    function ensureModal() {
        var existing = document.getElementById('docx-html-preview-modal');
        if (existing) {
            return existing;
        }

        var modal = document.createElement('div');
        modal.id = 'docx-html-preview-modal';
        modal.className = 'docx-html-modal';
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-modal', 'true');
        modal.setAttribute('aria-labelledby', 'docx-html-modal-title');
        modal.innerHTML =
            '<div class="docx-html-modal-backdrop" data-docx-close="1"></div>' +
            '<div class="docx-html-modal-dialog">' +
            '  <div class="docx-html-modal-header">' +
            '    <h2 id="docx-html-modal-title">Converted document (HTML)</h2>' +
            '    <button type="button" class="docx-html-modal-x" data-docx-close="1" aria-label="Close">&times;</button>' +
            '  </div>' +
            '  <div class="docx-html-modal-toolbar">' +
            '    <button type="button" class="button" id="docx-html-tab-preview">Preview</button>' +
            '    <button type="button" class="button" id="docx-html-tab-source">HTML source</button>' +
            '  </div>' +
            '  <div class="docx-html-modal-body">' +
            '    <div id="docx-html-preview-pane" class="docx-html-preview-pane"></div>' +
            '    <textarea id="docx-html-source-pane" class="docx-html-source-pane" readonly></textarea>' +
            '  </div>' +
            '  <div class="docx-html-target-row">' +
            '    <label for="docx-html-target-field">Target HTML field</label>' +
            '    <select id="docx-html-target-field"></select>' +
            '  </div>' +
            '  <div class="docx-html-modal-footer">' +
            '    <span id="docx-html-copy-status" class="docx-html-copy-status" aria-live="polite"></span>' +
            '    <button type="button" class="button" data-docx-close="1">Close</button>' +
            '    <button type="button" class="button" id="docx-html-copy-btn">Copy HTML</button>' +
            '    <button type="button" class="button default" id="docx-html-add-btn">Add to field</button>' +
            '  </div>' +
            '</div>';

        document.body.appendChild(modal);

        modal.addEventListener('click', function (e) {
            if (e.target && e.target.getAttribute('data-docx-close') === '1') {
                closeHtmlPreviewModal();
            }
        });

        document.getElementById('docx-html-copy-btn').addEventListener('click', copyConvertedHtml);
        document.getElementById('docx-html-add-btn').addEventListener('click', addConvertedHtmlToField);
        document.getElementById('docx-html-tab-preview').addEventListener('click', function () {
            setModalTab('preview');
        });
        document.getElementById('docx-html-tab-source').addEventListener('click', function () {
            setModalTab('source');
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && modal.classList.contains('is-open')) {
                closeHtmlPreviewModal();
            }
        });

        return modal;
    }

    function refreshTargetFieldOptions() {
        var select = document.getElementById('docx-html-target-field');
        if (!select) {
            return [];
        }

        var fields = discoverHtmlFields();
        select.innerHTML = '';

        if (!fields.length) {
            var opt = document.createElement('option');
            opt.value = '';
            opt.textContent = 'No HTML fields detected on this page';
            select.appendChild(opt);
            select.disabled = true;
            return fields;
        }

        select.disabled = false;
        fields.forEach(function (field) {
            var opt = document.createElement('option');
            opt.value = field.key;
            opt.textContent = field.label;
            select.appendChild(opt);
        });

        var preferred =
            lastFocusedFieldKey ||
            (document.getElementById('id_description') ? 'ck:id_description' : '') ||
            fields[0].key;

        var match = fields.some(function (f) { return f.key === preferred; });
        select.value = match ? preferred : fields[0].key;
        return fields;
    }

    function setModalTab(tab) {
        var preview = document.getElementById('docx-html-preview-pane');
        var source = document.getElementById('docx-html-source-pane');
        var btnPreview = document.getElementById('docx-html-tab-preview');
        var btnSource = document.getElementById('docx-html-tab-source');
        var isPreview = tab === 'preview';

        if (preview) {
            preview.style.display = isPreview ? 'block' : 'none';
        }
        if (source) {
            source.style.display = isPreview ? 'none' : 'block';
        }
        if (btnPreview) {
            btnPreview.classList.toggle('default', isPreview);
        }
        if (btnSource) {
            btnSource.classList.toggle('default', !isPreview);
        }
    }

    function showHtmlPreviewModal(html) {
        var modal = ensureModal();
        var preview = document.getElementById('docx-html-preview-pane');
        var source = document.getElementById('docx-html-source-pane');
        var status = document.getElementById('docx-html-copy-status');

        if (preview) {
            preview.innerHTML = html || '<p><em>No content</em></p>';
        }
        if (source) {
            source.value = html || '';
        }
        if (status) {
            status.textContent = '';
            status.className = 'docx-html-copy-status';
        }

        refreshTargetFieldOptions();
        setModalTab('preview');
        modal.classList.add('is-open');
        document.body.classList.add('docx-html-modal-open');
    }

    function closeHtmlPreviewModal() {
        var modal = document.getElementById('docx-html-preview-modal');
        if (modal) {
            modal.classList.remove('is-open');
        }
        document.body.classList.remove('docx-html-modal-open');
    }

    function getConvertedHtml() {
        var html = lastConvertedHtml;
        var source = document.getElementById('docx-html-source-pane');
        if (source && source.value) {
            html = source.value;
        }
        return html || '';
    }

    function copyConvertedHtml() {
        var html = getConvertedHtml();
        if (!html) {
            setCopyStatus('Nothing to copy', true);
            return;
        }

        function onSuccess() {
            setCopyStatus('HTML copied to clipboard', false);
        }

        function onFail() {
            var source = document.getElementById('docx-html-source-pane');
            if (source) {
                setModalTab('source');
                source.focus();
                source.select();
                try {
                    document.execCommand('copy');
                    onSuccess();
                    return;
                } catch (err) { /* ignore */ }
            }
            setCopyStatus('Copy failed — select HTML source and copy manually', true);
        }

        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(html).then(onSuccess).catch(onFail);
        } else {
            onFail();
        }
    }

    function findFieldByKey(key) {
        var fields = discoverHtmlFields();
        for (var i = 0; i < fields.length; i++) {
            if (fields[i].key === key) {
                return fields[i];
            }
        }
        return null;
    }

    function getFieldCurrentHtml(field) {
        if (field.editor && typeof field.editor.getData === 'function') {
            return field.editor.getData() || '';
        }
        if (field.textarea) {
            return field.textarea.value || '';
        }
        return '';
    }

    function setFieldHtml(field, html) {
        if (field.editor && typeof field.editor.setData === 'function') {
            field.editor.setData(html);
            try {
                field.editor.focus();
            } catch (e) { /* ignore */ }
        }
        if (field.textarea) {
            field.textarea.value = html;
            field.textarea.dispatchEvent(new Event('input', { bubbles: true }));
            field.textarea.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    function addConvertedHtmlToField() {
        var html = getConvertedHtml();
        if (!html) {
            setCopyStatus('Nothing to add', true);
            return;
        }

        var select = document.getElementById('docx-html-target-field');
        var key = select && select.value;
        var field = key ? findFieldByKey(key) : null;

        if (!field) {
            setCopyStatus('Select a target HTML field first', true);
            return;
        }

        var existing = getFieldCurrentHtml(field);
        var stripped = existing.replace(/<[^>]*>/g, '').replace(/&nbsp;/gi, ' ').trim();
        if (stripped) {
            if (!window.confirm('“' + field.label + '” already has content. Replace it with the converted HTML?')) {
                return;
            }
        }

        setFieldHtml(field, html);
        setCopyStatus('Added to “' + field.label + '”', false);
        setTimeout(closeHtmlPreviewModal, 600);
    }

    // Back-compat alias used by older career UI
    function addConvertedHtmlToDescription() {
        addConvertedHtmlToField();
    }

    function setCopyStatus(message, isError) {
        var status = document.getElementById('docx-html-copy-status');
        if (!status) {
            return;
        }
        status.textContent = message;
        status.className = 'docx-html-copy-status' + (isError ? ' is-error' : ' is-success');
    }

    function hideProcessingStatus() {
        var statusDiv = statusRoot();
        if (statusDiv) {
            statusDiv.style.display = 'none';
        }
    }

    function showErrorMessage(message) {
        var root = statusRoot();
        if (!root) {
            alert(message);
            return;
        }
        root.style.display = 'block';
        var processingMessage = root.querySelector('#processing-message, .processing-message');
        if (processingMessage) {
            processingMessage.textContent = message;
            processingMessage.className = 'processing-message error-message';
        }
    }

    function getCookie(name) {
        var cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === name + '=') {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    function hideOriginalDocxFieldset() {
        var input = document.getElementById('docx_file_input');
        if (!input) {
            return;
        }
        var row = input.closest('.form-row') || input.closest('.field-docx_file');
        if (row) {
            row.style.display = 'none';
        }
        var fieldset = input.closest('fieldset');
        if (fieldset) {
            var legend = fieldset.querySelector('h2, .fieldset-heading, legend');
            var title = (legend && legend.textContent) || '';
            if (title.indexOf('DOCX') !== -1 || title.indexOf('HTML Import') !== -1) {
                fieldset.style.display = 'none';
            }
        }
    }

    function trackFocusedFields() {
        document.addEventListener('focusin', function (e) {
            var t = e.target;
            if (!t) {
                return;
            }
            if (t.matches && t.matches('textarea, .cke_editable, iframe')) {
                var ta = t.tagName === 'TEXTAREA' ? t : null;
                if (!ta && t.classList && t.classList.contains('cke_editable')) {
                    // CKEditor iframe body — try active instance
                    if (typeof CKEDITOR !== 'undefined' && CKEDITOR.currentInstance) {
                        lastFocusedFieldKey = 'ck:' + CKEDITOR.currentInstance.name;
                        return;
                    }
                }
                if (ta) {
                    lastFocusedFieldKey = 'ta:' + (ta.id || ta.name);
                    if (typeof CKEDITOR !== 'undefined' && CKEDITOR.instances) {
                        var id = ta.id;
                        if (id && CKEDITOR.instances[id]) {
                            lastFocusedFieldKey = 'ck:' + id;
                        }
                    }
                }
            }
        }, true);
    }

    function wireSidebarImport() {
        var btn = document.getElementById('docx-sidebar-import-btn');
        var fileInput = document.getElementById('docx_sidebar_file_input');
        if (!btn || !fileInput || btn._docxWired) {
            return;
        }
        btn._docxWired = true;
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            fileInput.click();
        });
        fileInput.addEventListener('change', function () {
            processDocxFile(fileInput);
        });
    }

    function wireToolbarImport() {
        var toolbar = document.querySelector('.description-toolbar');
        var btn = document.getElementById('docx-html-import-btn');
        var fileInput = document.getElementById('docx_file_input_toolbar') ||
            document.getElementById('docx_file_input');

        if (toolbar && !btn) {
            btn = document.createElement('button');
            btn.type = 'button';
            btn.id = 'docx-html-import-btn';
            btn.className = 'button description-toolbar-btn';
            btn.title = 'Upload a Word file temporarily and convert to HTML';
            btn.textContent = 'Import HTML from Word';
            toolbar.appendChild(btn);
        }

        if (toolbar && !document.getElementById('docx_file_input_toolbar')) {
            fileInput = document.createElement('input');
            fileInput.type = 'file';
            fileInput.id = 'docx_file_input_toolbar';
            fileInput.accept = '.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document';
            fileInput.hidden = true;
            toolbar.appendChild(fileInput);
        } else {
            fileInput = document.getElementById('docx_file_input_toolbar') || fileInput;
        }

        if (btn && fileInput && !btn._docxWired) {
            btn._docxWired = true;
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                fileInput.click();
            });
            fileInput.addEventListener('change', function () {
                processDocxFile(fileInput);
            });
        }

        hideOriginalDocxFieldset();
    }

    function init() {
        ensureModal();
        trackFocusedFields();
        wireSidebarImport();
        wireToolbarImport();
        setTimeout(wireToolbarImport, 500);
        setTimeout(wireToolbarImport, 1500);
        setTimeout(wireSidebarImport, 300);
    }

    window.processDocxFile = processDocxFile;
    window.closeHtmlPreviewModal = closeHtmlPreviewModal;
    window.copyConvertedHtml = copyConvertedHtml;
    window.addConvertedHtmlToDescription = addConvertedHtmlToDescription;
    window.addConvertedHtmlToField = addConvertedHtmlToField;
    window.TopTeenDocxHtmlImport = {
        processDocxFile: processDocxFile,
        openPreview: showHtmlPreviewModal,
        discoverHtmlFields: discoverHtmlFields,
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
