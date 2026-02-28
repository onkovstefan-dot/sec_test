// Admin page JS placeholder (Milestone 2)
// No behavior changes yet.

(function () {
    "use strict";

    const root = document.getElementById("admin-page");
    if (!root) return; // only run on admin page

    const apiUrl = root.getAttribute("data-api-jobs-url") || "/api/v1/admin/jobs";

    const POLL_INTERVAL_MS = 5000;

    /** @param {string} id */
    function byId(id) {
        return document.getElementById(id);
    }

    function setText(el, text) {
        if (!el) return;
        el.textContent = text == null || text === "" ? "-" : String(text);
    }

    function fmtTs(ts) {
        if (!ts) return "-";
        const d = new Date(ts * 1000);
        if (Number.isNaN(d.getTime())) return "-";
        // Keep formatting simple & stable (local time like server-side)
        const pad = (n) => String(n).padStart(2, "0");
        return (
            d.getFullYear() +
            "-" +
            pad(d.getMonth() + 1) +
            "-" +
            pad(d.getDate()) +
            " " +
            pad(d.getHours()) +
            ":" +
            pad(d.getMinutes()) +
            ":" +
            pad(d.getSeconds())
        );
    }

    const pollStatusEl = byId("admin-polling-status");

    function setPollStatus(text) {
        if (!pollStatusEl) return;
        pollStatusEl.textContent = text ? ` (${text})` : "";
    }

    function applyJobs(data) {
        const pop = data && data.populate_daily_values;
        const rec = data && data.recreate_sqlite_db;

        if (pop) {
            setText(byId("admin-populate-status"), pop.running ? "RUNNING" : "IDLE");
            setText(byId("admin-populate-started"), fmtTs(pop.started_at));
            setText(byId("admin-populate-ended"), fmtTs(pop.ended_at));
            setText(byId("admin-populate-stop"), pop.stop_requested ? "YES" : "NO");
            // Note: API doesn't include log tail; keep server-rendered log line.
        }

        if (rec) {
            setText(byId("admin-recreate-status"), rec.running ? "RUNNING" : "IDLE");
            setText(byId("admin-recreate-started"), fmtTs(rec.started_at));
            setText(byId("admin-recreate-ended"), fmtTs(rec.ended_at));
            // Note: API doesn't include log tail.
        }
    }

    async function fetchJobs() {
        const res = await fetch(apiUrl, {
            method: "GET",
            headers: { Accept: "application/json" },
            credentials: "same-origin",
            cache: "no-store",
        });

        if (!res.ok) {
            throw new Error(`HTTP ${res.status}`);
        }

        const body = await res.json();
        if (!body || body.ok !== true) {
            throw new Error("Bad envelope");
        }
        return body.data;
    }

    let inFlight = false;
    async function tick() {
        if (inFlight) return;
        inFlight = true;

        try {
            const data = await fetchJobs();
            applyJobs(data);
            setPollStatus("live");
        } catch (e) {
            // Fail soft: keep page usable even if API route is missing/disabled
            setPollStatus("offline");
        } finally {
            inFlight = false;
        }
    }

    // First update quickly, then poll.
    tick();
    window.setInterval(tick, POLL_INTERVAL_MS);
})();
