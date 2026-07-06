'use strict';
(function () {
    function getNavSidebar() {
        return document.getElementById('nav-sidebar');
    }

    function getMain() {
        return document.getElementById('main');
    }

    function keepSidebarOpen() {
        const main = getMain();
        const navSidebar = getNavSidebar();
        if (!main || !navSidebar) {
            return;
        }
        try {
            localStorage.setItem('django.admin.navSidebarIsOpen', 'true');
        } catch (e) {
            /* ignore */
        }
        main.classList.add('shifted');
        navSidebar.setAttribute('aria-expanded', 'true');
    }

    function highlightSidebarNav() {
        const path = window.location.pathname.replace(/\/$/, '') || '/';
        const hash = window.location.hash.replace('#', '');

        document.querySelectorAll('[data-sidebar-nav]').forEach(function (link) {
            const key = link.getAttribute('data-sidebar-nav');
            let active = false;
            if (key === 'home' && (path === '/admin' || path === '')) {
                active = true;
            } else if (key === 'configuration' && path.indexOf('/admin/hub/configuration') === 0) {
                active = true;
            } else if (key === 'operations' && path.indexOf('/admin/hub/operations') === 0) {
                active = true;
            }
            link.closest('.tt-sidebar-nav__item, .tt-sidebar-nav__group')
                ?.classList.toggle('is-active', active);
            link.closest('.tt-sidebar-nav__group')
                ?.classList.toggle('is-open', active);
        });

        document.querySelectorAll('[data-sidebar-section]').forEach(function (link) {
            const sectionId = link.getAttribute('data-sidebar-section');
            const onHub = path.indexOf('/admin/hub/') === 0;
            const active = (onHub && hash && hash === sectionId)
                || (!hash && link.classList.contains('is-active'));
            link.classList.toggle('is-active', active);
        });

        if (hash) {
            const sectionLink = document.querySelector('[data-sidebar-section="' + hash + '"]');
            if (sectionLink) {
                sectionLink.classList.add('is-active');
                sectionLink.closest('.tt-sidebar-nav__group')?.classList.add('is-open', 'is-active');
            }
        }
    }

    function scrollHubSectionIntoView() {
        const hash = window.location.hash.replace('#', '');
        if (!hash) {
            return;
        }
        const target = document.getElementById(hash);
        if (target) {
            target.scrollIntoView({ block: 'start', behavior: 'instant' });
        }
    }

    function scrollAdvancedModelIntoView() {
        const navSidebar = getNavSidebar();
        if (!navSidebar) {
            return;
        }
        const active = navSidebar.querySelector('.tt-sidebar-advanced .current-model')
            || navSidebar.querySelector('.tt-sidebar-advanced .current-app');
        if (!active) {
            return;
        }

        const advanced = document.getElementById('tt-sidebar-advanced');
        if (advanced && !advanced.open) {
            advanced.open = true;
        }

        const hiddenRow = active.tagName === 'TR' ? active : active.closest('tr');
        if (hiddenRow && hiddenRow.style.display === 'none') {
            const navFilter = document.getElementById('nav-filter');
            if (navFilter) {
                navFilter.value = '';
                try {
                    sessionStorage.removeItem('django.admin.navSidebarFilterValue');
                } catch (e) {
                    /* ignore */
                }
                navSidebar.querySelectorAll('.tt-sidebar-advanced tbody tr').forEach(function (row) {
                    row.style.display = '';
                });
            }
        }

        const scrollTarget = active.tagName === 'TR' ? active : (active.closest('tr') || active);
        if (scrollTarget && typeof scrollTarget.scrollIntoView === 'function') {
            scrollTarget.scrollIntoView({ block: 'center', behavior: 'instant' });
        }
    }

    function initTopteenNavSidebar() {
        keepSidebarOpen();
        highlightSidebarNav();
        scrollHubSectionIntoView();
        scrollAdvancedModelIntoView();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTopteenNavSidebar);
    } else {
        initTopteenNavSidebar();
    }

    window.addEventListener('load', initTopteenNavSidebar);
    window.addEventListener('hashchange', function () {
        highlightSidebarNav();
        scrollHubSectionIntoView();
    });
})();
