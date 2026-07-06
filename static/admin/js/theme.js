'use strict';
{
    function setTheme(mode) {
        if (mode !== "light" && mode !== "dark" && mode !== "auto") {
            console.error(`Got invalid theme mode: ${mode}. Resetting to auto.`);
            mode = "auto";
        }
        document.documentElement.dataset.theme = mode;
        try {
            localStorage.setItem("theme", mode);
        } catch (e) {
            /* private browsing may block storage */
        }
        try {
            document.dispatchEvent(new CustomEvent("topteen-theme-change", { detail: { mode: mode } }));
        } catch (e) {
            /* older browsers */
        }
    }

    function cycleTheme() {
        const currentTheme = localStorage.getItem("theme") || "auto";
        const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;

        if (prefersDark) {
            if (currentTheme === "auto") {
                setTheme("light");
            } else if (currentTheme === "light") {
                setTheme("dark");
            } else {
                setTheme("auto");
            }
        } else {
            if (currentTheme === "auto") {
                setTheme("dark");
            } else if (currentTheme === "dark") {
                setTheme("light");
            } else {
                setTheme("auto");
            }
        }
    }

    function initTheme() {
        try {
            const currentTheme = localStorage.getItem("theme");
            currentTheme ? setTheme(currentTheme) : setTheme("auto");
        } catch (e) {
            setTheme("auto");
        }
    }

    function bindThemeToggles() {
        const buttons = document.getElementsByClassName("theme-toggle");
        Array.from(buttons).forEach(function (btn) {
            if (btn.dataset.topteenThemeBound === "1") {
                return;
            }
            btn.dataset.topteenThemeBound = "1";
            btn.setAttribute("type", "button");
            btn.addEventListener("click", function (event) {
                event.preventDefault();
                cycleTheme();
            });
        });
    }

    // Apply saved theme immediately (before paint when script is in <head>).
    initTheme();

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", bindThemeToggles);
    } else {
        bindThemeToggles();
    }

    window.addEventListener("load", bindThemeToggles);
}
