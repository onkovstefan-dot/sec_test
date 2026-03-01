// filepath: static/js/force_reload.js

(function () {
    "use strict";

    function byId(id) {
        return document.getElementById(id);
    }

    const btn = byId("force-reload");
    if (!btn) return;

    btn.addEventListener("click", (e) => {
        e.preventDefault();
        try {
            if (window.AppLoading && typeof window.AppLoading.show === "function") {
                window.AppLoading.show();
            }
        } catch {
            // ignore
        }

        // Force a full reload, bypassing cache where possible.
        window.location.reload(true);
    });
})();
