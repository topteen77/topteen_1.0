'use strict';
(function () {
    function isHubOrHomePage() {
        return document.body.classList.contains('tt-admin-home-page')
            || document.body.classList.contains('tt-admin-hub-page')
            || document.body.classList.contains('login');
    }

    function shouldAddPageStrip() {
        if (isHubOrHomePage() || document.querySelector('.tt-admin-page-strip')) {
            return false;
        }
        var h1 = document.querySelector('#content > h1');
        return h1 && h1.textContent.trim();
    }

    function getPageTitle() {
        var h1 = document.querySelector('#content > h1');
        return h1 ? h1.textContent.trim() : '';
    }

    function getYouAreHere() {
        var el = document.getElementById('tt-admin-you-are-here');
        if (!el) {
            return null;
        }
        try {
            return JSON.parse(el.textContent);
        } catch (e) {
            return null;
        }
    }

    function getPageHint(here) {
        if (document.body.classList.contains('change-list')) {
            return 'Add, edit, or filter records below. Use the sidebar to return to your hub section.';
        }
        if (document.body.classList.contains('change-form')) {
            return 'Save changes when done. Use history or the sidebar to navigate back.';
        }
        if (document.body.classList.contains('delete-confirmation')) {
            return 'Confirm your action below.';
        }
        if (document.body.classList.contains('history')) {
            return 'Review past changes for this record.';
        }
        if (here && here.zone_label) {
            return 'Use the sidebar to return to ' + here.zone_label + ' when done.';
        }
        return 'Use the sidebar to return to Configuration, Operations, or Education Loan when done.';
    }

    function escapeHtml(text) {
        return String(text || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function crumbLink(href, text) {
        return '<a href="' + escapeHtml(href) + '">' + escapeHtml(text) + '</a>';
    }

    function crumbText(text) {
        return escapeHtml(text);
    }

    function extractTrailingCrumb(breadcrumbsEl) {
        if (!breadcrumbsEl) {
            return '';
        }
        var clone = breadcrumbsEl.cloneNode(true);
        var links = clone.querySelectorAll('a');
        for (var i = 0; i < links.length; i++) {
            links[i].remove();
        }
        var raw = (clone.textContent || '').replace(/\u203a/g, '›').split('›');
        var parts = [];
        for (var j = 0; j < raw.length; j++) {
            var p = raw[j].replace(/\s+/g, ' ').trim();
            if (p) {
                parts.push(p);
            }
        }
        if (!parts.length) {
            return '';
        }
        // On change forms / history / delete, last segment is the object action label.
        if (
            document.body.classList.contains('change-form')
            || document.body.classList.contains('delete-confirmation')
            || document.body.classList.contains('history')
            || /\/\d+(\/|$)/.test(window.location.pathname)
            || /\/add\/?$/.test(window.location.pathname)
        ) {
            return parts[parts.length - 1];
        }
        return '';
    }

    function rewriteHubBreadcrumbs() {
        var here = getYouAreHere();
        if (!here || !here.hub_url || !here.zone_label) {
            return;
        }
        var breadcrumbs = document.querySelector('.breadcrumbs');
        if (!breadcrumbs || breadcrumbs.classList.contains('tt-hub-breadcrumbs')) {
            return;
        }

        var trailing = extractTrailingCrumb(breadcrumbs);
        var html = [
            crumbLink('/admin/', 'Home'),
            crumbLink(here.hub_url, here.zone_label),
        ];

        if (here.section_title && here.section_url) {
            html.push(crumbLink(here.section_url, here.section_title));
        }

        if (here.page_label) {
            if (trailing && here.page_url) {
                html.push(crumbLink(here.page_url, here.page_label));
                html.push(crumbText(trailing));
            } else {
                html.push(crumbText(here.page_label));
            }
        } else if (trailing) {
            html.push(crumbText(trailing));
        }

        breadcrumbs.className = 'breadcrumbs tt-hub-breadcrumbs';
        breadcrumbs.innerHTML = html.join(' &rsaquo; ');
    }

    function buildPageStrip() {
        if (!shouldAddPageStrip()) {
            return;
        }
        var title = getPageTitle();
        if (!title) {
            return;
        }

        var here = getYouAreHere();
        var strip = document.createElement('div');
        strip.className = 'tt-admin-page-strip';
        strip.setAttribute('role', 'region');
        strip.setAttribute('aria-label', 'Page context');

        var titleEl = document.createElement('h1');
        titleEl.className = 'tt-admin-page-strip__title';
        titleEl.textContent = title;

        var hint = document.createElement('p');
        hint.className = 'tt-admin-page-strip__hint';
        hint.textContent = getPageHint(here);

        var left = document.createElement('div');
        left.appendChild(titleEl);
        left.appendChild(hint);

        var actions = document.createElement('div');
        actions.className = 'tt-admin-page-strip__actions';

        function addNavAction(selector, fallbackLabel) {
            var link = document.querySelector(selector);
            if (!link) {
                return;
            }
            var a = document.createElement('a');
            a.href = link.getAttribute('href');
            a.textContent = fallbackLabel;
            actions.appendChild(a);
        }

        addNavAction('[data-sidebar-nav="configuration"]', 'Configuration');
        addNavAction('[data-sidebar-nav="operations"]', 'Operations');
        addNavAction('[data-sidebar-nav="education_loan"]', 'Education Loan');

        if (here && here.hub_url && here.zone === 'education_loan') {
            // Prefer hub back-link first for loan pages.
            var existing = actions.querySelectorAll('a');
            var loanFirst = null;
            for (var i = 0; i < existing.length; i++) {
                if ((existing[i].textContent || '').indexOf('Education Loan') !== -1) {
                    loanFirst = existing[i];
                    break;
                }
            }
            if (loanFirst && actions.firstChild !== loanFirst) {
                actions.insertBefore(loanFirst, actions.firstChild);
            }
        }

        strip.appendChild(left);
        if (actions.childElementCount) {
            strip.appendChild(actions);
        }

        var content = document.getElementById('content');
        var h1 = content && content.querySelector(':scope > h1');
        if (content && h1) {
            h1.insertAdjacentElement('afterend', strip);
        }
    }

    function syncThemeClass() {
        document.body.classList.add('tt-admin-themed');
    }

    function init() {
        syncThemeClass();
        rewriteHubBreadcrumbs();
        buildPageStrip();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
