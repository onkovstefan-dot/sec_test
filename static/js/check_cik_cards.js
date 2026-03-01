// filepath: static/js/check_cik_cards.js

(function () {
    function qs(sel) { return document.querySelector(sel); }

    const btn = qs('#load-more');
    const grid = qs('#cik-grid');

    if (!btn || !grid) return;

    function renderCard(c) {
        const details = document.createElement('details');
        details.className = 'cik-card';
        details.setAttribute('data-cik-card', '1');
        details.setAttribute('data-entity-id', String(c.entity_id));
        details.setAttribute('data-cik', String(c.cik));

        const summary = document.createElement('summary');
        summary.className = 'cik-card__summary';

        const header = document.createElement('div');
        header.className = 'cik-card__header';
        header.style.marginBottom = '0';

        const title = document.createElement('div');
        title.className = 'cik-card__title';
        title.textContent = c.company_name || 'Company';

        const eid = document.createElement('div');
        eid.className = 'cik-card__cik';
        eid.textContent = `ID ${c.entity_id}`;

        header.appendChild(title);
        header.appendChild(eid);
        summary.appendChild(header);

        const expanded = document.createElement('div');
        expanded.className = 'cik-card__expanded';

        const topMeta = document.createElement('div');
        topMeta.className = 'meta';
        topMeta.style.margin = '.5rem 0 .75rem 0';
        topMeta.innerHTML = `<strong>Company:</strong> ${c.cik}`;

        const dl = document.createElement('dl');
        dl.className = 'cik-card__dl';

        const md = c.metadata || {};
        const entries = Object.entries(md);
        for (const [k, v] of entries) {
            const dt = document.createElement('dt');
            dt.textContent = k;
            const dd = document.createElement('dd');
            const val = (v === null || v === undefined || v === '') ? '—' : String(v);
            dd.textContent = val;
            dl.appendChild(dt);
            dl.appendChild(dd);
        }

        const footer = document.createElement('div');
        footer.className = 'cik-card__footer';

        const a = document.createElement('a');
        a.className = 'button';
        a.href = `/daily-values?entity_id=${encodeURIComponent(c.entity_id)}`;
        a.textContent = 'Open daily values';

        footer.appendChild(a);

        expanded.appendChild(topMeta);
        expanded.appendChild(dl);
        expanded.appendChild(footer);

        details.appendChild(summary);
        details.appendChild(expanded);
        return details;
    }

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
                grid.appendChild(renderCard(c));
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
            alert('Failed to load more companies.');
        }
    });
})();
