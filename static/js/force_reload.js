// filepath: static/js/force_reload.js

(function () {
    "use strict";

    function attach(el) {
        el.addEventListener("click", (e) => {
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
    }

    const els = document.querySelectorAll("[data-force-reload='1'], #force-reload");
    if (!els || els.length === 0) return;

    for (const el of els) attach(el);
})();
