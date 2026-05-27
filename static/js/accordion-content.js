/**
 * Centralized accordion: parse HTML description into sections (one panel per <h2>).
 * Matches core.accordion_utils.sections_from_html (document-order h2, nested-safe body).
 */
(function (global) {
    'use strict';

    function isH2Element(node) {
        return node && node.nodeType === 1 && node.tagName && node.tagName.toUpperCase() === 'H2';
    }

    function collectContentBeforeH2(container, stopH2, parts) {
        var child = container.firstChild;
        while (child) {
            if (child === stopH2) return;
            if (child.nodeType === 1) {
                if (isH2Element(child)) return;
                if (stopH2 && child.contains && child.contains(stopH2)) {
                    collectContentBeforeH2(child, stopH2, parts);
                    return;
                }
                parts.push(child.outerHTML);
            } else if (child.nodeType === 3) {
                var text = child.textContent;
                if (text && text.trim()) parts.push(text);
            }
            child = child.nextSibling;
        }
    }

    function collectSectionContent(h2, nextH2) {
        var parts = [];
        var node = h2.nextSibling;
        while (node) {
            if (isH2Element(node)) break;
            if (nextH2 && node.nodeType === 1 && node.contains && node.contains(nextH2)) {
                collectContentBeforeH2(node, nextH2, parts);
                break;
            }
            if (node.nodeType === 1) {
                parts.push(node.outerHTML);
            } else if (node.nodeType === 3) {
                var t = node.textContent;
                if (t && t.trim()) parts.push(t);
            }
            node = node.nextSibling;
        }
        return parts.join('');
    }

    function sectionHtmlIsBlank(html) {
        if (!html || !String(html).trim()) return true;
        var temp = document.createElement('div');
        temp.innerHTML = String(html);
        temp.querySelectorAll('script,style,noscript').forEach(function (el) { el.remove(); });
        var text = (temp.textContent || '').replace(/\u00A0/g, ' ').trim();
        return !text;
    }

    function normalizeHeadingText(text) {
        return (text || '').replace(/\u00A0/g, ' ').replace(/\s+/g, ' ').trim();
    }

    function isIntroHeading(title) {
        var t = normalizeHeadingText(title).toLowerCase();
        return t === 'overview' || t === 'about' || t === 'introduction' || t === 'intro';
    }

    function collectPreambleHtml(root, firstH2) {
        var parts = [];
        var node = root.firstChild;
        while (node) {
            if (node === firstH2) break;
            if (node.nodeType === 1) {
                parts.push(node.outerHTML);
            } else if (node.nodeType === 3) {
                var t = node.textContent;
                if (t && t.trim()) parts.push(t);
            }
            node = node.nextSibling;
        }
        return parts.join('');
    }

    /**
     * @param {string} html
     * @returns {Array<{title: string, content: string, section_id?: string, h2_index?: number|null}>}
     */
    function parseDescriptionToAccordion(html) {
        if (!html || typeof html !== 'string') return [];
        var root = document.createElement('div');
        root.innerHTML = html;
        var h2Elements = root.querySelectorAll('h2');

        if (h2Elements.length === 0) {
            if (!sectionHtmlIsBlank(html)) {
                return [{
                    title: 'Overview',
                    content: html,
                    section_id: 'overview',
                    h2_index: null,
                    section_type: 'preamble'
                }];
            }
            return [];
        }

        var items = [];
        var firstH2 = h2Elements[0];
        var preamble = collectPreambleHtml(root, firstH2);
        var firstTitle = normalizeHeadingText(firstH2.textContent);

        if (preamble.trim() && !sectionHtmlIsBlank(preamble) && !isIntroHeading(firstTitle)) {
            items.push({
                title: 'Overview',
                content: preamble.trim(),
                section_id: 'overview',
                h2_index: null,
                section_type: 'preamble'
            });
        }

        for (var i = 0; i < h2Elements.length; i++) {
            var heading = h2Elements[i];
            var nextH2 = h2Elements[i + 1] || null;
            var title = normalizeHeadingText(heading.textContent);
            var content = collectSectionContent(heading, nextH2).trim();

            if (i === 0 && preamble.trim() && !sectionHtmlIsBlank(preamble) && isIntroHeading(firstTitle)) {
                content = (preamble + content).trim();
            }

            if (!title) title = 'Untitled Section';
            if (sectionHtmlIsBlank(content)) {
                content = '<p class="accordion-preview-empty" style="color:#888;font-style:italic;margin:0;">No content under this heading.</p>';
            }

            var sectionId = heading.id || ('section-' + (i + 1));
            items.push({
                title: title,
                content: content,
                section_id: sectionId,
                h2_index: i,
                section_type: 'h2'
            });
        }
        return items;
    }

    var CONCLUSION_WRAPPER_CLASS = 'career-description-conclusion';
    var MIN_CONCLUSION_PARAGRAPH_CHARS = 40;

    /**
     * Split trailing conclusion (matches careers.career_description_html.split_trailing_conclusion_from_description).
     * @returns {{ bodyHtml: string, conclusionHtml: string }}
     */
    function splitTrailingConclusionFromHtml(html) {
        if (!html || !String(html).trim()) {
            return { bodyHtml: '', conclusionHtml: '' };
        }
        var root = document.createElement('div');
        root.innerHTML = html;

        var wrapper = root.querySelector('div.' + CONCLUSION_WRAPPER_CLASS);
        if (wrapper) {
            var wrapped = wrapper.innerHTML.trim();
            wrapper.remove();
            return { bodyHtml: root.innerHTML.trim(), conclusionHtml: wrapped };
        }

        var paragraphs = [];
        root.querySelectorAll('p').forEach(function (p) {
            if (p.closest('div.' + CONCLUSION_WRAPPER_CLASS)) return;
            var text = normalizeHeadingText(p.textContent);
            if (text.length >= MIN_CONCLUSION_PARAGRAPH_CHARS) paragraphs.push(p);
        });

        if (paragraphs.length < 2) {
            return { bodyHtml: html, conclusionHtml: '' };
        }

        var lastP = paragraphs[paragraphs.length - 1];
        var firstP = paragraphs[0];
        if (lastP === firstP) {
            return { bodyHtml: html, conclusionHtml: '' };
        }

        var conclusionHtml = lastP.outerHTML;
        lastP.remove();
        return { bodyHtml: root.innerHTML.trim(), conclusionHtml: conclusionHtml };
    }

    function stripConclusionTextFromHtml(html, conclusionHtml) {
        if (!html || !conclusionHtml) return html;
        var temp = document.createElement('div');
        temp.innerHTML = conclusionHtml;
        var conclNorm = normalizeHeadingText(temp.textContent);
        if (!conclNorm) return html;

        var body = document.createElement('div');
        body.innerHTML = html;
        body.querySelectorAll('p').forEach(function (p) {
            if (normalizeHeadingText(p.textContent) === conclNorm) {
                p.remove();
            }
        });
        return body.innerHTML.trim();
    }

    /**
     * Admin preview: accordion panels from body without conclusion; conclusion rendered separately.
     */
    function parseDescriptionForAdminPreview(html) {
        var split = splitTrailingConclusionFromHtml(html);
        var items = parseDescriptionToAccordion(split.bodyHtml);

        if (split.conclusionHtml && !sectionHtmlIsBlank(split.conclusionHtml)) {
            items = items.map(function (item) {
                var content = stripConclusionTextFromHtml(
                    item.content || item.content_html || '',
                    split.conclusionHtml
                );
                return Object.assign({}, item, { content: content });
            });
        }

        return {
            bodyHtml: split.bodyHtml,
            conclusionHtml: split.conclusionHtml,
            items: items
        };
    }

    function renderAdminConclusionPreview(container, conclusionHtml) {
        if (!container) return;
        if (!conclusionHtml || sectionHtmlIsBlank(conclusionHtml)) {
            container.hidden = true;
            container.innerHTML = '';
            return;
        }
        container.hidden = false;
        container.innerHTML =
            '<h4 class="career-conclusion-preview-title">Conclusion</h4>' +
            '<div class="career-conclusion-preview-body blogDetail careerDetail">' +
            conclusionHtml +
            '</div>';
    }

    /** Count &lt;h2&gt; tags in raw HTML (same notion as the editor toolbar). */
    function countH2InHtml(html) {
        if (!html || !String(html).trim()) return 0;
        return (String(html).match(/<h2\b/gi) || []).length;
    }

    /**
     * Summary line for admin preview: H2 count vs accordion panel count.
     */
    function buildPreviewCountSummary(html, items, options) {
        options = options || {};
        var h2Count = countH2InHtml(html);
        var panelCount = items ? items.length : 0;
        var h2Panels = 0;
        var hasIntro = false;
        if (items) {
            items.forEach(function (it) {
                if (it.section_type === 'h2') h2Panels += 1;
                if (it.section_type === 'preamble') hasIntro = true;
            });
        }
        var expectedPanels = h2Count + (hasIntro ? 1 : 0);
        var countsAlign = panelCount === expectedPanels && h2Panels === h2Count;

        var statusClass = countsAlign ? 'accordion-preview-summary--ok' : 'accordion-preview-summary--warn';
        var statusText = countsAlign
            ? 'Counts match — each H2 maps to a preview section.'
            : 'Counts differ — check empty H2 headings or text before the first H2.';

        var detailParts = [];
        if (h2Count) detailParts.push(h2Count + ' H2 section' + (h2Count === 1 ? '' : 's'));
        if (hasIntro) detailParts.push('1 intro block before first H2');
        if (options && options.hasSeparateConclusion) {
            detailParts.push('conclusion shown below accordion');
        }
        var detail = detailParts.length ? ' (' + detailParts.join(' + ') + ')' : '';

        return {
            h2Count: h2Count,
            panelCount: panelCount,
            countsAlign: countsAlign,
            html: '<div class="accordion-preview-summary ' + statusClass + '" role="status">' +
                '<div class="accordion-preview-summary__counts">' +
                '<span><strong>' + h2Count + '</strong> H2 in description</span>' +
                '<span class="accordion-preview-summary__sep">→</span>' +
                '<span><strong>' + panelCount + '</strong> accordion panel' + (panelCount === 1 ? '' : 's') + '</span>' +
                '</div>' +
                '<div class="accordion-preview-summary__hint">' + escapeHtml(statusText) + escapeHtml(detail) + '</div>' +
                '</div>'
        };
    }

    function bindPreviewToggleClicks(container) {
        if (!container) return;
        container.querySelectorAll('.accordion-preview-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var tid = btn.getAttribute('data-accordion-target');
                var body = document.getElementById(tid);
                if (!body) return;
                var item = btn.closest('.accordion-preview-item');
                var sign = btn.querySelector('.accordion-preview-sign');
                var open = body.style.display === 'none';
                body.style.display = open ? 'block' : 'none';
                btn.style.background = open ? '#f4f3ff' : '#fff';
                if (sign) sign.textContent = open ? '−' : '+';
                if (item) item.classList.toggle('accordion-preview-item-active', open);
            });
        });
    }

    function escapeHtml(text) {
        var d = document.createElement('div');
        d.textContent = text;
        return d.innerHTML;
    }

    var CAREER_ICON_MAP = {
        'Overview': 'bx-id-card',
        'Roles and Responsibilities': 'bx-task',
        'Study Route & Eligibility Criteria': 'bx-book-reader',
        'Significant Observations': 'bx-bulb',
        'Internships & Practical Exposure': 'bx-briefcase-alt-2',
        'Courses & Specializations to Enter the Field': 'bx-book-content',
        'Top Institutes for Automobile Design Education in India': 'bx-building-house',
        'Top International Institutes': 'bx-globe',
        'Entrance Tests Required': 'bx-edit-alt',
        'Ideal Progressing Career Path': 'bx-trending-up',
        'Major Areas of Employment': 'bx-map-alt',
        'Prominent Employers': 'bx-building',
        'Pros and Cons of the Profession': 'bx-traffic-cone',
        'Industry Trends and Future Outlook': 'bx-line-chart',
        'Advice for Aspiring Automobile Designers': 'bx-message-dots',
        'Conclusion': 'bx-check-shield',
        'Related Courses': 'bx-book-open',
        'Career Resources': 'bx-folder-open',
        'Frequently Asked Questions': 'bx-help-circle'
    };

    function iconForTitle(title) {
        if (!title) return 'bx-layer';
        if (CAREER_ICON_MAP[title]) return CAREER_ICON_MAP[title];
        var lower = title.toLowerCase();
        var keys = Object.keys(CAREER_ICON_MAP);
        for (var k = 0; k < keys.length; k++) {
            if (lower.indexOf(keys[k].toLowerCase().substring(0, 12)) !== -1) {
                return CAREER_ICON_MAP[keys[k]];
            }
        }
        if (/\boverview\b/.test(lower)) return 'bx-id-card';
        if (/\broles?\b/.test(lower)) return 'bx-task';
        if (/\beligibility\b|\bstudy route\b/.test(lower)) return 'bx-book-reader';
        if (/\binternships?\b/.test(lower)) return 'bx-briefcase-alt-2';
        if (/\bcourses?\b/.test(lower)) return 'bx-book-content';
        if (/\binstitutes?\b/.test(lower)) return 'bx-building-house';
        if (/\bemployers?\b/.test(lower)) return 'bx-building';
        if (/\bconclusion\b/.test(lower)) return 'bx-check-shield';
        if (/\bfaq\b/.test(lower)) return 'bx-help-circle';
        return 'bx-layer';
    }

    /**
     * Render accordion items into a container.
     * @param {HTMLElement} container
     * @param {Array} items - from parseDescriptionToAccordion or server JSON
     * @param {object} options - { mode: 'bootstrap'|'preview', accordionId, expandAll, emptyMessage }
     */
    function renderAccordion(container, items, options) {
        options = options || {};
        var mode = options.mode || 'bootstrap';
        var accordionId = options.accordionId || 'contentAccordion';
        var expandAll = options.expandAll === true;

        if (!container) return;
        if (!items || !items.length) {
            container.innerHTML = '<p class="accordion-empty-msg" style="color:#666;font-style:italic;">' +
                (options.emptyMessage || 'No accordion structure found. Add H2 headings to create sections.') +
                '</p>';
            return;
        }

        if (mode === 'preview') {
            var sourceHtml = options.sourceHtml || '';
            var summary = buildPreviewCountSummary(sourceHtml, items, options);
            var out = '<div class="accordion-preview-inner">';
            if (options.showCount !== false) {
                out += summary.html;
            }
            items.forEach(function (item, index) {
                var itemId = accordionId + '-preview-' + index;
                var display = expandAll ? 'block' : 'none';
                var sign = expandAll ? '−' : '+';
                var bg = expandAll ? '#f4f3ff' : '#fff';
                var h2Attr = item.h2_index === null || item.h2_index === undefined ? '' : String(item.h2_index);
                var label = item.section_type === 'preamble'
                    ? 'Intro'
                    : ('H2 #' + (parseInt(h2Attr, 10) + 1));
                var previewKey = item.section_type === 'preamble' ? 'preamble' : ('h2-' + h2Attr);
                out += '<div class="career-accordion-item accordion-preview-item" data-section-index="' + index + '" data-h2-index="' + h2Attr + '" data-preview-key="' + previewKey + '" data-section-title="' + escapeHtml(item.title) + '">' +
                    '<button class="career-accordion-button accordion-preview-btn" type="button" data-accordion-target="' + itemId + '" style="background:' + bg + '">' +
                    '<span><span class="accordion-preview-badge">' + escapeHtml(label) + '</span>' +
                    escapeHtml(item.title) + '</span><span class="accordion-preview-sign">' + sign + '</span></button>' +
                    '<div id="' + itemId + '" class="career-accordion-body accordion-preview-body" style="display:' + display + ';">' +
                    (item.content || item.content_html || '') + '</div></div>';
            });
            out += '</div>';
            container.innerHTML = out;
            bindPreviewToggleClicks(container);
            return;
        }

        var accordion = document.createElement('div');
        accordion.className = 'accordion cat-accordion custom-faq';
        accordion.id = accordionId;

        var sectionIndex = 0;
        items.forEach(function (item) {
            if (sectionHtmlIsBlank(item.content || item.content_html)) return;
            sectionIndex += 1;
            var sectionId = item.section_id || (accordionId + 'Item' + sectionIndex);
            var title = item.title || 'Section';
            var iconClass = item.icon || iconForTitle(title);
            if (iconClass.indexOf('bx ') !== 0 && iconClass.indexOf('bx-') === 0) {
                iconClass = 'bx ' + iconClass;
            }

            var accordionItem = document.createElement('div');
            accordionItem.className = 'accordion-item';
            accordionItem.id = sectionId;

            var header = document.createElement('h2');
            header.className = 'accordion-header';
            header.id = 'heading-' + sectionId;

            var button = document.createElement('button');
            button.type = 'button';
            button.className = sectionIndex === 1 ? 'accordion-button' : 'accordion-button collapsed';
            button.setAttribute('data-bs-toggle', 'collapse');
            button.setAttribute('data-bs-target', '#collapse-' + sectionId);
            button.setAttribute('aria-expanded', sectionIndex === 1 ? 'true' : 'false');
            button.setAttribute('aria-controls', 'collapse-' + sectionId);
            button.innerHTML = '<i class="' + iconClass + '"></i><span>' + escapeHtml(title) + '</span>';

            header.appendChild(button);

            var collapse = document.createElement('div');
            collapse.id = 'collapse-' + sectionId;
            collapse.className = sectionIndex === 1 ? 'accordion-collapse collapse show' : 'accordion-collapse collapse';
            collapse.setAttribute('aria-labelledby', header.id);
            collapse.setAttribute('data-bs-parent', '#' + accordionId);

            var body = document.createElement('div');
            body.className = 'accordion-body';
            var inner = item.content || item.content_html || '';
            body.innerHTML = '<div class="blogDetail careerDetail">' + inner + '</div>';

            collapse.appendChild(body);
            accordionItem.appendChild(header);
            accordionItem.appendChild(collapse);
            accordion.appendChild(accordionItem);
        });

        container.innerHTML = '';
        container.appendChild(accordion);
        container.dataset.accordionReady = 'true';
    }

    function isUntitledSectionTitle(title) {
        var t = String(title || '').trim().toLowerCase();
        if (!t) return true;
        if (t === 'section' || t === 'untitled' || t === 'untitled section') return true;
        return t.indexOf('untitled') === 0;
    }

    /**
     * Career detail frontend: last untitled H2 body → footer paragraph (not accordion).
     */
    function splitTrailingUntitledForFrontend(items) {
        if (!items || !items.length) {
            return { accordionItems: [], footerHtml: '' };
        }
        var last = items[items.length - 1];
        if (!isUntitledSectionTitle(last.title)) {
            return { accordionItems: items, footerHtml: '' };
        }
        var content = last.content || last.content_html || '';
        if (sectionHtmlIsBlank(content)) {
            return { accordionItems: items, footerHtml: '' };
        }
        return { accordionItems: items.slice(0, -1), footerHtml: content };
    }

    function appendCareerFooterParagraph(container, footerHtml) {
        if (!container || !footerHtml || !String(footerHtml).trim()) return;
        var el = container.querySelector('.career-detail-closing-paragraph');
        if (!el) {
            el = document.createElement('div');
            el.className = 'career-detail-closing-paragraph blogDetail careerDetail';
            container.appendChild(el);
        }
        el.innerHTML = footerHtml;
    }

    global.TopTeenAccordion = {
        parseDescriptionToAccordion: parseDescriptionToAccordion,
        parseDescriptionForAdminPreview: parseDescriptionForAdminPreview,
        splitTrailingConclusionFromHtml: splitTrailingConclusionFromHtml,
        stripConclusionTextFromHtml: stripConclusionTextFromHtml,
        renderAdminConclusionPreview: renderAdminConclusionPreview,
        countH2InHtml: countH2InHtml,
        buildPreviewCountSummary: buildPreviewCountSummary,
        sectionHtmlIsBlank: sectionHtmlIsBlank,
        isUntitledSectionTitle: isUntitledSectionTitle,
        splitTrailingUntitledForFrontend: splitTrailingUntitledForFrontend,
        appendCareerFooterParagraph: appendCareerFooterParagraph,
        renderAccordion: renderAccordion,
        escapeHtml: escapeHtml,
        iconForTitle: iconForTitle
    };

    global.parseDescriptionToAccordion = parseDescriptionToAccordion;
    global.renderTopTeenAccordion = renderAccordion;
})(typeof window !== 'undefined' ? window : this);
