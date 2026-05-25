/**
 * Admin / TopTeen admin live accordion preview while editing CKEditor description fields.
 * Requires accordion-content.js (TopTeenAccordion).
 *
 * - Preview rebuilds when description changes (no editor scroll on preview click).
 * - Purple highlight on preview panel for H2 at current scroll position in editor.
 */
(function () {
    'use strict';

    var syncDebounceTimer = null;
    var highlightDebounceTimer = null;

    function getDescriptionTextarea(config) {
        config = config || {};
        if (config.textareaId) {
            var byId = document.getElementById(config.textareaId);
            if (byId) return byId;
        }
        return document.getElementById('editordescription') ||
            document.querySelector('#career-description-field-container textarea[name="description"]') ||
            document.querySelector('textarea[name="description"]');
    }

    function getDescriptionHtml(config) {
        config = config || {};
        var ta = getDescriptionTextarea(config);
        if (ta && ta._ckeditorInstance && typeof ta._ckeditorInstance.getData === 'function') {
            try {
                return ta._ckeditorInstance.getData();
            } catch (e) { /* fall through */ }
        }
        var container = document.getElementById(config.editorContainerId || 'career-description-field-container');
        if (container) {
            var sourceTa = container.querySelector('.ck-source-editing-area textarea');
            if (sourceTa && sourceTa.offsetParent !== null) {
                return sourceTa.value || '';
            }
            var editable = container.querySelector('.ck-editor__editable[contenteditable="true"]');
            if (editable) return editable.innerHTML || '';
        }
        return ta ? (ta.value || '') : '';
    }

    function findScrollableParent(el) {
        var node = el;
        while (node && node !== document.body) {
            var style = window.getComputedStyle(node);
            if ((style.overflowY === 'auto' || style.overflowY === 'scroll') &&
                node.scrollHeight > node.clientHeight + 2) {
                return node;
            }
            node = node.parentElement;
        }
        return el;
    }

    function getEditorElements(config) {
        var container = document.getElementById(config.editorContainerId || 'career-description-field-container');
        if (!container) return null;
        var editable = container.querySelector('.ck-editor__editable[contenteditable="true"]');
        if (!editable) return null;
        var main = container.querySelector('.ck-editor__main');
        return {
            container: container,
            editable: editable,
            scrollRoot: findScrollableParent(main || editable)
        };
    }

    function getActiveScrollTarget(headings, scrollRoot) {
        if (!headings || !headings.length) {
            return { previewKey: 'preamble', h2Index: null };
        }
        var rootRect = scrollRoot.getBoundingClientRect();
        var zoneMid = rootRect.top + Math.min(140, scrollRoot.clientHeight * 0.3);
        if (headings[0].getBoundingClientRect().top > zoneMid) {
            return { previewKey: 'preamble', h2Index: null };
        }
        var activeIndex = 0;
        for (var i = 0; i < headings.length; i++) {
            if (headings[i].getBoundingClientRect().top <= zoneMid) activeIndex = i;
        }
        return { previewKey: 'h2-' + activeIndex, h2Index: activeIndex };
    }

    function findPreviewIndexForScroll(previewContainer, target) {
        var items = previewContainer.querySelectorAll('.accordion-preview-item');
        for (var i = 0; i < items.length; i++) {
            if (items[i].getAttribute('data-preview-key') === target.previewKey) return i;
        }
        if (target.h2Index !== null) {
            var best = -1;
            var bestH2 = -1;
            for (var j = 0; j < items.length; j++) {
                var attr = items[j].getAttribute('data-h2-index');
                if (attr === null || attr === '') continue;
                var n = parseInt(attr, 10);
                if (!isNaN(n) && n <= target.h2Index && n >= bestH2) {
                    bestH2 = n;
                    best = j;
                }
            }
            if (best >= 0) return best;
        }
        for (var k = 0; k < items.length; k++) {
            if (items[k].getAttribute('data-preview-key') === 'preamble') return k;
        }
        return 0;
    }

    function scrollPreviewPanelToItem(previewContainer, item) {
        if (!previewContainer || !item) return;
        var header = item.querySelector('.accordion-preview-btn') || item;
        var pad = 8;
        var cTop = previewContainer.getBoundingClientRect().top;
        var cBottom = previewContainer.getBoundingClientRect().bottom;
        var tTop = header.getBoundingClientRect().top;
        var tBottom = header.getBoundingClientRect().bottom;
        var next = previewContainer.scrollTop;
        if (tTop < cTop + pad) {
            next += tTop - cTop - pad;
        } else if (tBottom > cBottom - pad) {
            next += tBottom - cBottom + pad;
        } else {
            return;
        }
        previewContainer.scrollTop = Math.max(0, next);
    }

    function bindPreviewHighlightOnly(config) {
        config = config || {};
        var previewContainer = document.getElementById(config.previewContainerId || 'career-accordion-preview-container');
        if (!previewContainer) return;

        if (typeof previewContainer._previewHighlightCleanup === 'function') {
            previewContainer._previewHighlightCleanup();
        }

        var editor = getEditorElements(config);
        if (!editor) return;

        function updateHighlight() {
            var items = previewContainer.querySelectorAll('.accordion-preview-item');
            if (!items.length) return;
            var h2s = editor.editable.querySelectorAll('h2');
            var target = getActiveScrollTarget(h2s, editor.scrollRoot);
            var idx = findPreviewIndexForScroll(previewContainer, target);
            items.forEach(function (item, i) {
                var on = i === idx;
                item.classList.toggle('accordion-preview-item--current', on);
            });
            scrollPreviewPanelToItem(previewContainer, items[idx]);
        }

        function debouncedHighlight() {
            if (highlightDebounceTimer) clearTimeout(highlightDebounceTimer);
            highlightDebounceTimer = setTimeout(updateHighlight, 80);
        }

        var onScroll = debouncedHighlight;
        editor.scrollRoot.addEventListener('scroll', onScroll, { passive: true });
        editor.editable.addEventListener('scroll', onScroll, { passive: true });
        var editorCol = document.querySelector('.career-editor-col');
        if (editorCol) editorCol.addEventListener('scroll', onScroll, { passive: true });

        var ta = getDescriptionTextarea(config);
        if (ta && ta._ckeditorInstance && ta._ckeditorInstance.editing) {
            var viewDoc = ta._ckeditorInstance.editing.view.document;
            if (viewDoc) viewDoc.on('scroll', onScroll, { passive: true });
        }

        updateHighlight();

        previewContainer._previewHighlightCleanup = function () {
            editor.scrollRoot.removeEventListener('scroll', onScroll);
            editor.editable.removeEventListener('scroll', onScroll);
            if (editorCol) editorCol.removeEventListener('scroll', onScroll);
        };
        previewContainer._previewHighlightUpdate = updateHighlight;
    }

    function updateAccordionPreview(html, config) {
        config = config || {};
        var container = document.getElementById(config.previewContainerId || 'career-accordion-preview-container');
        if (!container || typeof TopTeenAccordion === 'undefined') return;
        var items = TopTeenAccordion.parseDescriptionToAccordion(html);
        TopTeenAccordion.renderAccordion(container, items, {
            mode: 'preview',
            accordionId: config.accordionId || 'admin-preview',
            expandAll: config.expandAll === true,
            showCount: true,
            sourceHtml: html,
            emptyMessage: config.emptyMessage
        });
        bindPreviewHighlightOnly(config);
    }

    function syncAll(config) {
        updateAccordionPreview(getDescriptionHtml(config), config);
    }

    function debouncedSyncAll(config) {
        if (syncDebounceTimer) clearTimeout(syncDebounceTimer);
        syncDebounceTimer = setTimeout(function () { syncAll(config); }, 100);
    }

    function bindSourceEditingInput(config) {
        var container = document.getElementById(config.editorContainerId || 'career-description-field-container');
        if (!container || container._accordionSourceInputBound) return;
        container.addEventListener('input', function (e) {
            if (e.target && e.target.closest && e.target.closest('.ck-source-editing-area')) {
                debouncedSyncAll(config);
            }
        });
        container._accordionSourceInputBound = true;
    }

    function attachEditorListeners(config) {
        var ta = getDescriptionTextarea(config);
        if (!ta || !ta._ckeditorInstance) return false;
        var editor = ta._ckeditorInstance;
        if (!ta._accordionPreviewBound) {
            ta._accordionPreviewBound = true;
            editor.model.document.on('change:data', function () {
                debouncedSyncAll(config);
            });
            if (editor.editing && editor.editing.view && editor.editing.view.document) {
                editor.editing.view.document.on('keyup', debouncedSyncAll.bind(null, config));
            }
            if (editor.plugins && editor.plugins.has('SourceEditing')) {
                try {
                    var sourceEditing = editor.plugins.get('SourceEditing');
                    if (typeof editor.listenTo === 'function') {
                        editor.listenTo(sourceEditing, 'change:isSourceEditingMode', function () {
                            debouncedSyncAll(config);
                        });
                    }
                } catch (e) { /* optional */ }
            }
            bindSourceEditingInput(config);
        }
        return true;
    }

    function initDescriptionEditor(config) {
        config = config || {};
        var ta = getDescriptionTextarea(config);
        if (!ta) return;

        if (ta._ckeditorInstance) {
            markDescriptionEditorReady(config);
            attachEditorListeners(config);
            syncAll(config);
            return;
        }

        if (typeof classieditor !== 'function') return;

        classieditor(ta.id).then(function () {
            markDescriptionEditorReady(config);
            attachEditorListeners(config);
            syncAll(config);
        });
    }

    function markDescriptionEditorReady(config) {
        config = config || {};
        var container = document.getElementById(config.editorContainerId || 'career-description-field-container');
        if (!container) return;
        var ta = getDescriptionTextarea(config);
        if (ta && ta._ckeditorInstance && container.querySelector('.ck-editor')) {
            container.classList.add('career-description-editor-box--ckeditor');
        }
    }

    function ensureDescriptionFieldInContainer(config) {
        config = config || {};
        var container = document.getElementById(config.editorContainerId || 'career-description-field-container');
        if (!container) return null;
        var ta = document.getElementById('editordescription') ||
            container.querySelector('textarea[name="description"]') ||
            document.querySelector('textarea[name="description"].ckeditor');
        if (ta && ta.parentElement !== container) {
            container.appendChild(ta);
        }
        markDescriptionEditorReady(config);
        return ta;
    }

    function initAccordionAdminPreview(userConfig) {
        var config = userConfig || {};
        config.previewContainerId = config.previewContainerId || 'career-accordion-preview-container';
        config.editorContainerId = config.editorContainerId || 'career-description-field-container';

        ensureDescriptionFieldInContainer(config);
        initDescriptionEditor(config);

        var pollCount = 0;
        var pollInterval = setInterval(function () {
            ensureDescriptionFieldInContainer(config);
            initDescriptionEditor(config);
            attachEditorListeners(config);
            syncAll(config);
            if (++pollCount >= 80) clearInterval(pollInterval);
        }, 250);

        document.addEventListener('topteen-ckeditor-ready', function () {
            initDescriptionEditor(config);
            attachEditorListeners(config);
            syncAll(config);
        });
    }

    window.ensureDescriptionFieldInContainer = ensureDescriptionFieldInContainer;
    window.initAccordionAdminPreview = initAccordionAdminPreview;
    window.initCareerDescriptionEditor = function () {
        initDescriptionEditor({});
    };
    window.initCareerAccordionPreview = function () {
        initAccordionAdminPreview({});
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            if (document.getElementById('career-accordion-preview-container')) {
                initAccordionAdminPreview({});
            }
        });
    } else if (document.getElementById('career-accordion-preview-container')) {
        initAccordionAdminPreview({});
    }
})();
