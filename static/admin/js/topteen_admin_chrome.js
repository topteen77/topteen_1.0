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

    function getPageHint() {
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
        return 'Use the sidebar to return to Configuration or Operations when done.';
    }

    function buildPageStrip() {
        if (!shouldAddPageStrip()) {
            return;
        }
        var title = getPageTitle();
        if (!title) {
            return;
        }

        var strip = document.createElement('div');
        strip.className = 'tt-admin-page-strip';
        strip.setAttribute('role', 'region');
        strip.setAttribute('aria-label', 'Page context');

        var titleEl = document.createElement('h1');
        titleEl.className = 'tt-admin-page-strip__title';
        titleEl.textContent = title;

        var hint = document.createElement('p');
        hint.className = 'tt-admin-page-strip__hint';
        hint.textContent = getPageHint();

        var left = document.createElement('div');
        left.appendChild(titleEl);
        left.appendChild(hint);

        var actions = document.createElement('div');
        actions.className = 'tt-admin-page-strip__actions';

        var configLink = document.querySelector('[data-sidebar-nav="configuration"]');
        var opsLink = document.querySelector('[data-sidebar-nav="operations"]');
        if (configLink) {
            var a1 = document.createElement('a');
            a1.href = configLink.getAttribute('href');
            a1.textContent = 'Configuration';
            actions.appendChild(a1);
        }
        if (opsLink) {
            var a2 = document.createElement('a');
            a2.href = opsLink.getAttribute('href');
            a2.textContent = 'Operations';
            actions.appendChild(a2);
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
        buildPageStrip();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
