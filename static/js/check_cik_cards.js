// filepath: static/js/check_cik_cards.js

(function () {
    function qs(sel) { return document.querySelector(sel); }

    const btn = qs('#load-more');
    const grid = qs('#cik-grid');

    if (!btn || !grid) return;

    btn.addEventListener('click', async function () {
        const curOffset = parseInt(btn.getAttribute('data-offset') || '0', 10);
        const limit = parseInt(btn.getAttribute('data-limit') || '20', 10);

        btn.disabled = true;
        btn.textContent = 'Loading…';

        try {
            const url = `/check-cik?format=json&offset=${encodeURIComponent(curOffset)}&limit=${encodeURIComponent(limit)}`;
            const res = await fetch(url, { headers: { 'Accept': 'application/json' } });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const payload = await res.json();

            const cards = payload.cards || [];
            for (const c of cards) {
                const a = document.createElement('a');
                a.className = 'cik-card';
                a.href = `/check-cik?cik=${encodeURIComponent(c.cik)}`;

                const header = document.createElement('div');
                header.className = 'cik-card__header';

                const title = document.createElement('div');
                title.className = 'cik-card__title';
                title.textContent = c.company_name || 'Company';

                const cik = document.createElement('div');
                cik.className = 'cik-card__cik';
                cik.textContent = `CIK ${c.cik}`;

                header.appendChild(title);
                header.appendChild(cik);

                const body = document.createElement('dl');
                body.className = 'cik-card__dl';

                const md = c.metadata || {};
                const entries = Object.entries(md);
                for (const [k, v] of entries) {
                    const dt = document.createElement('dt');
                    dt.textContent = k;
                    const dd = document.createElement('dd');
                    dd.textContent = String(v);
                    body.appendChild(dt);
                    body.appendChild(dd);
                }

                a.appendChild(header);
                a.appendChild(body);

                grid.appendChild(a);
            }

            const newOffset = payload.next_offset ?? (curOffset + cards.length);
            btn.setAttribute('data-offset', String(newOffset));

            if (!payload.has_more) {
                btn.remove();
            } else {
                btn.disabled = false;
                btn.textContent = 'Load more';
            }
        } catch (err) {
            console.error(err);
            btn.disabled = false;
            btn.textContent = 'Load more';
            alert('Failed to load more CIKs.');
        }
    });
})();
