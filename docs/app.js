/* PII Detection Benchmark — Chart.js Visualizations */

const COLORS = {
    ambientmeta: { bg: 'rgba(42, 122, 226, 0.8)', border: '#2a7ae2' },
    presidio:    { bg: 'rgba(167, 139, 250, 0.8)', border: '#a78bfa' },
    spacy:       { bg: 'rgba(52, 211, 153, 0.8)',  border: '#34d399' },
    regex:       { bg: 'rgba(100, 116, 139, 0.8)', border: '#64748b' },
};

const SYSTEM_ORDER = ['ambientmeta', 'presidio', 'spacy', 'regex'];
const CATEGORIES = ['standard', 'ambiguous', 'contextual', 'adversarial'];

const CHART_DEFAULTS = {
    color: '#94a3b8',
    borderColor: '#334155',
    font: { family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif" },
};

Chart.defaults.color = CHART_DEFAULTS.color;
Chart.defaults.borderColor = CHART_DEFAULTS.borderColor;
Chart.defaults.font.family = CHART_DEFAULTS.font.family;

// Embedded results data
const LAT = {
    regex:       { p50_ms: 0.04, p95_ms: 0.1, p99_ms: 0.1, total_docs: 1113, total_seconds: 0.05, throughput_docs_per_sec: 22260 },
    spacy:       { p50_ms: 5.7, p95_ms: 13.0, p99_ms: 15.2, total_docs: 1113, total_seconds: 7.6, throughput_docs_per_sec: 147 },
    presidio:    { p50_ms: 9.5, p95_ms: 24.7, p99_ms: 31.1, total_docs: 1113, total_seconds: 13.7, throughput_docs_per_sec: 81 },
    ambientmeta: { p50_ms: 14.1, p95_ms: 27.5, p99_ms: 33.3, total_docs: 1113, total_seconds: 295.3, throughput_docs_per_sec: 3.8 },
};

const FALLBACK_DATA = {
    adapters: {
        regex:       { name: 'Regex Only',                aggregate: { f1: 0.302, per_type: {"PERSON":{"f1":0.0},"CREDIT_CARD":{"f1":0.8644},"LOCATION":{"f1":0.0},"EMAIL":{"f1":0.963},"SSN":{"f1":0.8099},"PHONE":{"f1":0.5561},"MRN":{"f1":0.0},"ORGANIZATION":{"f1":0.0},"NPI":{"f1":0.0}} }, categories: { standard: { metrics: { f1: 0.438 }, latency: LAT.regex }, ambiguous: { metrics: { f1: 0.075 }, latency: LAT.regex }, contextual: { metrics: { f1: 0.069 }, css: { css: 0.037 }, latency: LAT.regex }, adversarial: { metrics: { f1: 0.287 }, latency: LAT.regex } } },
        spacy:       { name: 'spaCy NER',                 aggregate: { f1: 0.344, per_type: {"PERSON":{"f1":0.6143},"CREDIT_CARD":{"f1":0.0},"LOCATION":{"f1":0.3337},"EMAIL":{"f1":0.0},"ORGANIZATION":{"f1":0.1862},"SSN":{"f1":0.0},"PHONE":{"f1":0.0},"MRN":{"f1":0.0},"NPI":{"f1":0.0}} }, categories: { standard: { metrics: { f1: 0.296 }, latency: LAT.spacy }, ambiguous: { metrics: { f1: 0.422 }, latency: LAT.spacy }, contextual: { metrics: { f1: 0.255 }, css: { css: 0.432 }, latency: LAT.spacy }, adversarial: { metrics: { f1: 0.370 }, latency: LAT.spacy } } },
        presidio:    { name: 'Microsoft Presidio',        aggregate: { f1: 0.508, per_type: {"PERSON":{"f1":0.6143},"CREDIT_CARD":{"f1":0.9197},"LOCATION":{"f1":0.3337},"EMAIL":{"f1":1.0},"SSN":{"f1":0.6952},"PHONE":{"f1":0.5513},"MRN":{"f1":0.0},"ORGANIZATION":{"f1":0.0},"NPI":{"f1":0.0}} }, categories: { standard: { metrics: { f1: 0.572 }, latency: LAT.presidio }, ambiguous: { metrics: { f1: 0.469 }, latency: LAT.presidio }, contextual: { metrics: { f1: 0.298 }, css: { css: 0.389 }, latency: LAT.presidio }, adversarial: { metrics: { f1: 0.525 }, latency: LAT.presidio } } },
        ambientmeta: { name: 'AmbientMeta Privacy Guard', aggregate: { f1: 0.8351, per_type: {"PERSON":{"f1":0.8639},"CREDIT_CARD":{"f1":0.9844},"LOCATION":{"f1":0.7756},"EMAIL":{"f1":0.9772},"ORGANIZATION":{"f1":0.7158},"SSN":{"f1":0.8873},"PHONE":{"f1":0.8106},"MRN":{"f1":0.8},"NPI":{"f1":0.9565}} }, categories: { standard: { metrics: { f1: 0.829 }, latency: LAT.ambientmeta }, ambiguous: { metrics: { f1: 0.804 }, latency: LAT.ambientmeta }, contextual: { metrics: { f1: 0.805 }, css: { css: 0.691 }, latency: LAT.ambientmeta }, adversarial: { metrics: { f1: 0.867 }, latency: LAT.ambientmeta } } },
    }
};

function loadResults() {
    // Data is embedded in FALLBACK_DATA above — always available, no fetch needed.
    // To use live results instead, serve results/latest.json alongside docs/.
    return FALLBACK_DATA;
}

function getAdapterColor(key) {
    return COLORS[key] || { bg: 'rgba(148, 163, 184, 0.8)', border: '#94a3b8' };
}

function pct(val) {
    return (val * 100).toFixed(1) + '%';
}

function getSystemName(data, key) {
    return data.adapters[key]?.name || key;
}

function getOrderedAdapters(data) {
    return SYSTEM_ORDER.filter(k => k in data.adapters);
}

// ─── Results Table ──────────────────────────────────────────────────

function renderResultsTable(data) {
    const tbody = document.getElementById('resultsBody');
    const adapters = getOrderedAdapters(data);

    // Find best values per column
    const cols = ['overall', 'standard', 'ambiguous', 'css', 'adversarial'];
    const best = {};
    for (const col of cols) {
        let maxVal = -1;
        for (const key of adapters) {
            const a = data.adapters[key];
            let val;
            if (col === 'overall') val = a.aggregate?.f1 || 0;
            else if (col === 'css') val = a.categories?.contextual?.css?.css || 0;
            else val = a.categories?.[col]?.metrics?.f1 || 0;
            if (val > maxVal) maxVal = val;
        }
        best[col] = maxVal;
    }

    for (const key of adapters) {
        const a = data.adapters[key];
        const overall = a.aggregate?.f1 || 0;
        const standard = a.categories?.standard?.metrics?.f1 || 0;
        const ambiguous = a.categories?.ambiguous?.metrics?.f1 || 0;
        const css = a.categories?.contextual?.css?.css || 0;
        const adversarial = a.categories?.adversarial?.metrics?.f1 || 0;

        const row = document.createElement('tr');
        row.innerHTML = `
            <td class="system-name">${a.name}</td>
            <td class="${overall >= best.overall ? 'best' : ''}">${pct(overall)}</td>
            <td class="${standard >= best.standard ? 'best' : ''}">${pct(standard)}</td>
            <td class="${ambiguous >= best.ambiguous ? 'best' : ''}">${pct(ambiguous)}</td>
            <td class="${css >= best.css ? 'best' : ''}">${pct(css)}</td>
            <td class="${adversarial >= best.adversarial ? 'best' : ''}">${pct(adversarial)}</td>
        `;
        tbody.appendChild(row);
    }
}

// ─── Overall F1 Bar Chart ───────────────────────────────────────────

function renderOverallChart(data) {
    const adapters = getOrderedAdapters(data);
    const ctx = document.getElementById('overallChart').getContext('2d');

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: CATEGORIES.map(c => c.charAt(0).toUpperCase() + c.slice(1)),
            datasets: adapters.map(key => ({
                label: getSystemName(data, key),
                data: CATEGORIES.map(cat =>
                    (data.adapters[key].categories?.[cat]?.metrics?.f1 || 0) * 100
                ),
                backgroundColor: getAdapterColor(key).bg,
                borderColor: getAdapterColor(key).border,
                borderWidth: 1,
                borderRadius: 3,
            })),
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { position: 'bottom', labels: { padding: 16, usePointStyle: true, pointStyle: 'rect' } },
                tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)}%` } },
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 90,
                    ticks: { callback: v => v + '%' },
                    grid: { color: 'rgba(51, 65, 85, 0.5)' },
                },
                x: { grid: { display: false } },
            },
        },
    });
}

// ─── CSS Bar Chart ──────────────────────────────────────────────────

function renderCSSChart(data) {
    const adapters = getOrderedAdapters(data);
    const ctx = document.getElementById('cssChart').getContext('2d');

    const cssValues = adapters.map(key =>
        (data.adapters[key].categories?.contextual?.css?.css || 0) * 100
    );
    const names = adapters.map(key => getSystemName(data, key));
    const colors = adapters.map(key => getAdapterColor(key).bg);
    const borders = adapters.map(key => getAdapterColor(key).border);

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: names,
            datasets: [{
                label: 'CSS',
                data: cssValues,
                backgroundColor: colors,
                borderColor: borders,
                borderWidth: 1,
                borderRadius: 4,
            }],
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: (ctx) => `CSS: ${ctx.parsed.x.toFixed(1)}%` } },
            },
            scales: {
                x: {
                    beginAtZero: true,
                    max: 65,
                    ticks: { callback: v => v + '%' },
                    grid: { color: 'rgba(51, 65, 85, 0.5)' },
                },
                y: { grid: { display: false } },
            },
        },
    });
}

// ─── Per-Entity Chart + Table ───────────────────────────────────────

function renderEntityChart(data) {
    const adapters = getOrderedAdapters(data);

    // Collect all entity types
    const allTypes = new Set();
    for (const key of adapters) {
        const perType = data.adapters[key].aggregate?.per_type || {};
        Object.keys(perType).forEach(t => allTypes.add(t));
    }
    const entityTypes = Array.from(allTypes).sort();

    // Chart
    const ctx = document.getElementById('entityChart').getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: entityTypes,
            datasets: adapters.map(key => ({
                label: getSystemName(data, key),
                data: entityTypes.map(t =>
                    (data.adapters[key].aggregate?.per_type?.[t]?.f1 || 0) * 100
                ),
                backgroundColor: getAdapterColor(key).bg,
                borderColor: getAdapterColor(key).border,
                borderWidth: 1,
                borderRadius: 2,
            })),
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'bottom', labels: { padding: 16, usePointStyle: true, pointStyle: 'rect' } },
                tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)}%` } },
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: { callback: v => v + '%' },
                    grid: { color: 'rgba(51, 65, 85, 0.5)' },
                },
                x: { grid: { display: false }, ticks: { font: { size: 11 } } },
            },
        },
    });

    // Table
    const thead = document.getElementById('entityTableHead');
    const tbody = document.getElementById('entityTableBody');

    thead.innerHTML = '<th>Entity Type</th>' + adapters.map(key =>
        `<th>${getSystemName(data, key)}</th>`
    ).join('');

    for (const etype of entityTypes) {
        const vals = adapters.map(key => data.adapters[key].aggregate?.per_type?.[etype]?.f1 || 0);
        const maxVal = Math.max(...vals);

        const row = document.createElement('tr');
        row.innerHTML = `<td class="system-name">${etype}</td>` + vals.map(v =>
            `<td class="${v > 0 && v >= maxVal ? 'best' : ''}">${v > 0 ? pct(v) : '—'}</td>`
        ).join('');
        tbody.appendChild(row);
    }
}

// ─── Radar Chart ────────────────────────────────────────────────────

function renderRadarChart(data) {
    const adapters = getOrderedAdapters(data);
    const ctx = document.getElementById('radarChart').getContext('2d');

    const labels = ['Standard F1', 'Ambiguous F1', 'CSS', 'Adversarial F1', 'Overall F1'];

    new Chart(ctx, {
        type: 'radar',
        data: {
            labels,
            datasets: adapters.map(key => {
                const a = data.adapters[key];
                return {
                    label: a.name,
                    data: [
                        (a.categories?.standard?.metrics?.f1 || 0) * 100,
                        (a.categories?.ambiguous?.metrics?.f1 || 0) * 100,
                        (a.categories?.contextual?.css?.css || 0) * 100,
                        (a.categories?.adversarial?.metrics?.f1 || 0) * 100,
                        (a.aggregate?.f1 || 0) * 100,
                    ],
                    borderColor: getAdapterColor(key).border,
                    backgroundColor: getAdapterColor(key).bg.replace('0.8', '0.15'),
                    borderWidth: 2,
                    pointRadius: 4,
                    pointBackgroundColor: getAdapterColor(key).border,
                };
            }),
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'bottom', labels: { padding: 16, usePointStyle: true, pointStyle: 'circle' } },
                tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.r.toFixed(1)}%` } },
            },
            scales: {
                r: {
                    beginAtZero: true,
                    max: 90,
                    ticks: { callback: v => v + '%', backdropColor: 'transparent', font: { size: 10 } },
                    grid: { color: 'rgba(51, 65, 85, 0.5)' },
                    angleLines: { color: 'rgba(51, 65, 85, 0.5)' },
                    pointLabels: { font: { size: 12 } },
                },
            },
        },
    });
}

// ─── Latency Table ──────────────────────────────────────────────────

function renderLatencyTable(data) {
    const tbody = document.getElementById('latencyBody');
    const adapters = getOrderedAdapters(data);

    for (const key of adapters) {
        const a = data.adapters[key];
        let totalP50 = 0, totalP95 = 0, totalP99 = 0, totalDocs = 0, totalSecs = 0, count = 0;

        for (const cat of CATEGORIES) {
            const lat = a.categories?.[cat]?.latency;
            if (lat && lat.total_docs > 0) {
                totalP50 += lat.p50_ms || 0;
                totalP95 += lat.p95_ms || 0;
                totalP99 += lat.p99_ms || 0;
                totalDocs += lat.total_docs || 0;
                totalSecs += lat.total_seconds || 0;
                count++;
            }
        }

        const p50 = count > 0 ? (totalP50 / count).toFixed(1) : '—';
        const p95 = count > 0 ? (totalP95 / count).toFixed(1) : '—';
        const p99 = count > 0 ? (totalP99 / count).toFixed(1) : '—';
        const tps = totalSecs > 0 ? (totalDocs / totalSecs).toFixed(1) + ' docs/s' : '—';

        const row = document.createElement('tr');
        row.innerHTML = `
            <td class="system-name">${a.name}</td>
            <td>${p50} ms</td>
            <td>${p95} ms</td>
            <td>${p99} ms</td>
            <td>${tps}</td>
        `;
        tbody.appendChild(row);
    }
}

// ─── Init ───────────────────────────────────────────────────────────

function init() {
    const data = loadResults();

    const renders = [
        ['resultsTable', () => renderResultsTable(data)],
        ['overallChart', () => renderOverallChart(data)],
        ['cssChart', () => renderCSSChart(data)],
        ['entityChart', () => renderEntityChart(data)],
        ['radarChart', () => renderRadarChart(data)],
        ['latencyTable', () => renderLatencyTable(data)],
    ];
    for (const [name, fn] of renders) {
        try { fn(); } catch (e) { console.error(`Failed to render ${name}:`, e); }
    }

    // Update hero stats
    const adapters = getOrderedAdapters(data);
    document.getElementById('hero-systems').textContent = adapters.length;

    let bestCSS = 0;
    for (const key of adapters) {
        const css = data.adapters[key].categories?.contextual?.css?.css || 0;
        if (css > bestCSS) bestCSS = css;
    }
    document.getElementById('hero-css').textContent = pct(bestCSS);
}

init();
