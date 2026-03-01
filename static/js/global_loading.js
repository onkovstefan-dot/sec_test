// filepath: static/js/global_loading.js

(function () {
    "use strict";

    const overlay = document.getElementById("global-loading");
    if (!overlay) return;

    let count = 0;
    let hideTimer = null;

    function _setDisabledState(on) {
        if (on) {
            document.body.classList.add("is-loading");
        } else {
            document.body.classList.remove("is-loading");
        }
    }

    function show() {
        count += 1;
        _setDisabledState(true);
        overlay.setAttribute("aria-hidden", "false");
        overlay.classList.add("is-visible");
    }

    function hide() {
        count = Math.max(0, count - 1);
        if (count !== 0) return;

        // avoid flicker for very fast interactions
        if (hideTimer) window.clearTimeout(hideTimer);
        hideTimer = window.setTimeout(() => {
            overlay.classList.remove("is-visible");
            overlay.setAttribute("aria-hidden", "true");
            _setDisabledState(false);
        }, 150);
    }

    // Expose a tiny API for pages that want to manually control it.
    window.AppLoading = { show, hide };

    // Show on full page navigations (link clicks) and form submits.
    document.addEventListener(
        "click",
        (e) => {
            const a = e.target && e.target.closest ? e.target.closest("a") : null;
            if (!a) return;

            // Ignore new-tab, downloads, hash-only, or explicit opt-out.
            if (a.target === "_blank") return;
            if (a.hasAttribute("download")) return;
            if (a.getAttribute("data-no-loading") === "1") return;

            const href = a.getAttribute("href") || "";
            if (!href || href.startsWith("#")) return;

            // Only same-origin navigations
            try {
                const url = new URL(href, window.location.href);
                if (url.origin !== window.location.origin) return;
            } catch {
                // if URL parsing fails, still attempt to show
            }

            show();
        },
        true
    );

    document.addEventListener(
        "submit",
        (e) => {
            const form = e.target;
            if (form && form.getAttribute && form.getAttribute("data-no-loading") === "1") {
                return;
            }
            show();
        },
        true
    );

    // Wrap fetch to show for async requests (e.g. load-more button, admin polling).
    if (window.fetch) {
        const origFetch = window.fetch.bind(window);
        window.fetch = function (...args) {
            const url = args && args[0];
            // Allow callers to opt-out by passing {headers: {'X-No-Loading':'1'}}
            const opts = args && args[1];
            const headers = (opts && opts.headers) || {};
            const noLoading =
                (headers && (headers["X-No-Loading"] || headers["x-no-loading"])) ||
                (opts && opts.noLoading === true);

            if (!noLoading) show();
            return origFetch(...args).finally(() => {
                if (!noLoading) hide();
            });
        };
    }

    // Always clear the overlay once the page finishes loading.
    window.addEventListener("pageshow", () => {
        count = 0;
        overlay.classList.remove("is-visible");
        overlay.setAttribute("aria-hidden", "true");
        _setDisabledState(false);
    });
})();
