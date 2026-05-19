/* ─── Config Page ─────────────────────────────────────────────────────────── */

async function loadConfigs() {
    const res = await fetch('/api/configs');
    const configs = await res.json();
    const grid = document.getElementById('config-list');
    if (!grid) return;

    grid.innerHTML = configs.map(c => `
        <div class="card">
            <h3>${c.salon.name}</h3>
            <div class="card-meta">
                📅 ${c.salon.dates}<br>
                📍 ${c.salon.location}
            </div>
            <div style="font-size:.85rem;">
                <strong>${c.signal_types_count}</strong> types de signaux
            </div>
            <div class="card-actions">
                <button class="btn btn-small" onclick="editConfig('${c.name}')">Modifier</button>
                <a href="/signals?config=${c.name}" class="btn btn-small btn-primary">Voir signaux</a>
            </div>
        </div>
    `).join('');
}

function showCreateForm() {
    document.getElementById('modal-title').textContent = 'Nouveau salon';
    document.getElementById('config-form').reset();
    document.getElementById('cfg-name').disabled = false;
    document.getElementById('signal-types-container').innerHTML = '';
    addSignalType();
    document.getElementById('config-modal').classList.remove('hidden');
}

async function editConfig(name) {
    const res = await fetch(`/api/config/${name}`);
    const config = await res.json();

    document.getElementById('modal-title').textContent = `Modifier : ${config.salon.name}`;
    document.getElementById('cfg-name').value = name;
    document.getElementById('cfg-name').disabled = true;
    document.getElementById('cfg-salon-name').value = config.salon.name;
    document.getElementById('cfg-short-code').value = config.salon.short_code;
    document.getElementById('cfg-dates').value = config.salon.dates;
    document.getElementById('cfg-location').value = config.salon.location;
    document.getElementById('cfg-themes').value = (config.salon.themes || []).join('\n');

    // Signal types
    const sc = document.getElementById('signal-types-container');
    sc.innerHTML = '';
    (config.signal_types || []).forEach(s => addSignalType(s));
    if (!config.signal_types?.length) addSignalType();

    // Scoring
    const w = config.scoring?.weights || {};
    document.getElementById('cfg-w-fit').value = (w.account_fit || 0.35) * 100;
    document.getElementById('cfg-w-strength').value = (w.signal_strength || 0.40) * 100;
    document.getElementById('cfg-w-timing').value = (w.timing || 0.25) * 100;
    const t = config.scoring?.thresholds || {};
    document.getElementById('cfg-t-hot').value = t.hot ?? 7.5;
    document.getElementById('cfg-t-warm').value = t.warm ?? 5.0;

    document.getElementById('config-modal').classList.remove('hidden');
}

function closeModal() {
    document.getElementById('config-modal').classList.add('hidden');
}

function addSignalType(data) {
    const c = document.getElementById('signal-types-container');
    const row = document.createElement('div');
    row.className = 'dynamic-row';
    row.innerHTML = `
        <input type="text" placeholder="ID (ex: funding)" class="st-id" value="${data?.id || ''}">
        <input type="text" placeholder="Label" class="st-label" value="${data?.label || ''}">
        <input type="number" placeholder="Poids" class="st-weight" step="0.5" min="0.5" max="5" value="${data?.weight || 1.5}">
        <button type="button" class="btn-remove" onclick="this.parentElement.remove()">&times;</button>
    `;
    c.appendChild(row);
}

async function saveConfig(e) {
    e.preventDefault();

    const signalTypes = [...document.querySelectorAll('#signal-types-container .dynamic-row')].map(row => ({
        id: row.querySelector('.st-id').value,
        label: row.querySelector('.st-label').value,
        description: '',
        weight: parseFloat(row.querySelector('.st-weight').value) || 1.5,
    })).filter(s => s.id);

    const body = {
        name: document.getElementById('cfg-name').value,
        salon: {
            name: document.getElementById('cfg-salon-name').value,
            short_code: document.getElementById('cfg-short-code').value,
            dates: document.getElementById('cfg-dates').value,
            location: document.getElementById('cfg-location').value,
            themes: document.getElementById('cfg-themes').value.split('\n').filter(t => t.trim()),
        },
        signal_types: signalTypes,
        scoring: {
            weights: {
                account_fit: parseInt(document.getElementById('cfg-w-fit').value) / 100,
                signal_strength: parseInt(document.getElementById('cfg-w-strength').value) / 100,
                timing: parseInt(document.getElementById('cfg-w-timing').value) / 100,
            },
            thresholds: {
                hot: parseFloat(document.getElementById('cfg-t-hot').value),
                warm: parseFloat(document.getElementById('cfg-t-warm').value),
                cold: 0.0,
            },
        },
    };

    const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });

    if (res.ok) {
        closeModal();
        loadConfigs();
    } else {
        const err = await res.json();
        alert(err.error || 'Erreur lors de la sauvegarde');
    }
}


/* ─── Signals Page ────────────────────────────────────────────────────────── */

let _allSignals = [];
let _activeFilters = { priority: new Set(), company: new Set() };
let _currentConfig = '';

async function initSignalsPage() {
    // Load config dropdown
    const res = await fetch('/api/configs');
    const configs = await res.json();
    const sel = document.getElementById('config-select');
    if (!sel) return;

    configs.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.name;
        opt.textContent = c.salon.name;
        sel.appendChild(opt);
    });

    // Check URL param
    const params = new URLSearchParams(window.location.search);
    if (params.get('config')) {
        sel.value = params.get('config');
        loadSignals();
    }
}

async function loadSignals() {
    const sel = document.getElementById('config-select');
    const configName = sel.value;
    if (!configName) return;
    _currentConfig = configName;

    document.getElementById('signal-list').innerHTML = '<div class="empty-state"><div class="spinner"></div> Chargement…</div>';
    document.getElementById('empty-state').classList.add('hidden');

    const res = await fetch(`/api/signals/${configName}`);
    _allSignals = await res.json();

    // Build filters
    const priorities = [...new Set(_allSignals.map(s => s.priority))];
    const companies = [...new Set(_allSignals.map(s => s.company))].sort();

    _activeFilters.priority = new Set(priorities);
    _activeFilters.company = new Set(companies);

    renderFilterChips('filter-priority', priorities, 'priority');
    renderCompanyDropdown(companies);

    document.getElementById('kpi-bar').classList.remove('hidden');
    document.getElementById('filters').classList.remove('hidden');

    renderSignals();
}

async function refreshSignals() {
    if (!_currentConfig) return;
    await fetch(`/api/refresh/${_currentConfig}`, { method: 'POST' });
    loadSignals();
}

function renderFilterChips(containerId, values, filterKey) {
    const c = document.getElementById(containerId);
    c.innerHTML = values.map(v => {
        const active = _activeFilters[filterKey].has(v);
        return `<span class="chip ${active ? 'active' : ''}" onclick="toggleFilter('${filterKey}', '${v.replace(/'/g, "\\'")}', this)">${v}</span>`;
    }).join('');
}

function toggleFilter(key, value, el) {
    if (_activeFilters[key].has(value)) {
        _activeFilters[key].delete(value);
        el.classList.remove('active');
    } else {
        _activeFilters[key].add(value);
        el.classList.add('active');
    }
    renderSignals();
}

function renderCompanyDropdown(companies) {
    const menu = document.getElementById('company-dropdown-menu');
    menu.innerHTML = `
        <label class="dropdown-item" style="font-weight:600;border-bottom:1px solid #eee;padding-bottom:6px;margin-bottom:4px;">
            <input type="checkbox" checked onchange="toggleAllCompanies(this.checked)"> Tout sélectionner
        </label>
    ` + companies.map(c => {
        const checked = _activeFilters.company.has(c) ? 'checked' : '';
        return `<label class="dropdown-item"><input type="checkbox" ${checked} value="${c}" onchange="toggleCompanyFilter('${c.replace(/'/g, "\\'")}', this.checked)"> ${c}</label>`;
    }).join('');
    updateCompanyBadge();
}

function toggleDropdown() {
    document.getElementById('company-dropdown-menu').classList.toggle('hidden');
}

function toggleCompanyFilter(company, checked) {
    if (checked) {
        _activeFilters.company.add(company);
    } else {
        _activeFilters.company.delete(company);
    }
    updateCompanyBadge();
    renderSignals();
}

function toggleAllCompanies(checked) {
    const menu = document.getElementById('company-dropdown-menu');
    const checkboxes = menu.querySelectorAll('input[type=checkbox][value]');
    const allCompanies = [...checkboxes].map(cb => cb.value);
    if (checked) {
        allCompanies.forEach(c => _activeFilters.company.add(c));
    } else {
        _activeFilters.company.clear();
    }
    checkboxes.forEach(cb => cb.checked = checked);
    updateCompanyBadge();
    renderSignals();
}

function updateCompanyBadge() {
    const total = [...new Set(_allSignals.map(s => s.company))].length;
    const selected = _activeFilters.company.size;
    const badge = document.getElementById('company-count-badge');
    const btn = document.querySelector('.dropdown-toggle');
    if (selected === total) {
        badge.textContent = '';
        btn.firstChild.textContent = 'Toutes les entreprises ';
    } else {
        badge.textContent = `(${selected}/${total})`;
        btn.firstChild.textContent = `${selected} entreprise${selected > 1 ? 's' : ''} `;
    }
}

// Close dropdown when clicking outside
document.addEventListener('click', (e) => {
    const dd = document.getElementById('company-dropdown');
    if (dd && !dd.contains(e.target)) {
        document.getElementById('company-dropdown-menu')?.classList.add('hidden');
    }
});

function renderSignals() {
    const filtered = _allSignals.filter(s =>
        _activeFilters.priority.has(s.priority) && _activeFilters.company.has(s.company)
    );

    // KPIs
    document.getElementById('kpi-total').textContent = filtered.length;
    document.getElementById('kpi-hot').textContent = filtered.filter(s => s.priority.includes('HOT')).length;
    document.getElementById('kpi-warm').textContent = filtered.filter(s => s.priority.includes('WARM')).length;
    document.getElementById('kpi-cold').textContent = filtered.filter(s => s.priority.includes('COLD')).length;

    const list = document.getElementById('signal-list');
    if (!filtered.length) {
        list.innerHTML = '<div class="empty-state">Aucun signal ne correspond aux filtres.</div>';
        return;
    }

    list.innerHTML = filtered.map(s => {
        const pClass = s.priority.includes('HOT') ? 'hot' : s.priority.includes('WARM') ? 'warm' : 'cold';
        const label = s.signal_meta?.label || s.signal_type;
        return `
        <div class="signal-card" id="card-${s.id}">
            <div class="signal-card-header" onclick="toggleCard('${s.id}')">
                <span class="priority-dot ${pClass}"></span>
                <div class="signal-card-title">
                    <strong>${s.company} — ${label}</strong>
                    <span>${s.title}</span>
                </div>
                <div class="signal-score">${s.scores.composite}/10</div>
            </div>
            <div class="signal-card-body">
                <p class="signal-summary">${s.summary}</p>
                <div class="score-grid">
                    <div class="score-item"><span class="score-val">${s.scores.account_fit}</span><span class="score-lbl">Fit compte</span></div>
                    <div class="score-item"><span class="score-val">${s.scores.signal_strength}</span><span class="score-lbl">Force signal</span></div>
                    <div class="score-item"><span class="score-val">${s.scores.timing}</span><span class="score-lbl">Timing</span></div>
                    <div class="score-item"><span class="score-val">${s.scores.composite}</span><span class="score-lbl">Composite</span></div>
                </div>
                <div class="signal-meta-row">
                    <span>Source: ${s.source}</span>
                    <span>Détecté: ${s.detected_at?.slice(0, 10)}</span>
                    <span>Priorité: ${s.priority}</span>
                    ${s.url ? `<a href="${s.url}" target="_blank" rel="noopener" class="article-link">Voir l'article &rarr;</a>` : ''}
                </div>
                <div class="activation-section" id="activation-${s.id}">
                    ${renderActivation(s)}
                </div>
            </div>
        </div>`;
    }).join('');
}

function toggleCard(id) {
    document.getElementById(`card-${id}`).classList.toggle('open');
}

function renderActivation(signal) {
    if (!signal.activation || !Object.keys(signal.activation).length) {
        return `
            <button class="btn btn-activate" onclick="activateSignal('${signal.id}', this)">
                🤖 Générer les activations
            </button>`;
    }

    if (signal.activation.error) {
        return `<p style="color:var(--hot)">${signal.activation.error}</p>`;
    }

    const act = signal.activation;
    return `
        <h4>🎯 Activations</h4>
        <div class="activation-tabs">
            <span class="activation-tab active" onclick="switchTab('${signal.id}', 'sales', this)">💼 Sales</span>
            <span class="activation-tab" onclick="switchTab('${signal.id}', 'direction', this)">🎯 Direction</span>
            <span class="activation-tab" onclick="switchTab('${signal.id}', 'marketing', this)">📢 Marketing</span>
        </div>
        <div id="tab-${signal.id}-sales" class="activation-panel active">
            ${renderSalesActivation(act.sales)}
        </div>
        <div id="tab-${signal.id}-direction" class="activation-panel">
            ${renderDirectionActivation(act.direction_salon)}
        </div>
        <div id="tab-${signal.id}-marketing" class="activation-panel">
            ${renderMarketingActivation(act.marketing)}
        </div>
    `;
}

function renderSalesActivation(s) {
    if (!s) return '<p>Pas de données</p>';
    return `
        <div class="activation-field"><label>Pourquoi</label><p>${s.pourquoi || ''}</p></div>
        <div class="activation-field"><label>Action</label><p>${s.action || ''}</p></div>
        <div class="activation-field"><label>Message LinkedIn</label><pre>${s.message_linkedin || ''}</pre></div>
        ${s.email_subject ? `<div class="activation-field"><label>Email — ${s.email_subject}</label><pre>${s.email_body || ''}</pre></div>` : ''}
        ${s.follow_up_sequence ? `<div class="activation-field"><label>Séquence de relance</label><p>${s.follow_up_sequence.join('<br>')}</p></div>` : ''}
    `;
}

function renderDirectionActivation(d) {
    if (!d) return '<p>Pas de données</p>';
    return `
        <div class="activation-field"><label>Pourquoi</label><p>${d.pourquoi || ''}</p></div>
        <div class="activation-field"><label>Action</label><p>${d.action || ''}</p></div>
        <div class="activation-field"><label>Insight</label><p>${d.insight_3_phrases || ''}</p></div>
        <div class="activation-field"><label>Angle de positionnement</label><p>${d.angle_positionnement || ''}</p></div>
    `;
}

function renderMarketingActivation(m) {
    if (!m) return '<p>Pas de données</p>';
    return `
        <div class="activation-field"><label>Pourquoi</label><p>${m.pourquoi || ''}</p></div>
        <div class="activation-field"><label>Action</label><p>${m.action || ''}</p></div>
        <div class="activation-field"><label>Draft post LinkedIn</label><pre>${m.post_linkedin_draft || ''}</pre></div>
        <div class="activation-field"><label>Idée contenu</label><p>${m.content_idea || ''}</p></div>
        <div class="activation-field"><label>Brief visuel</label><p>${m.visual_brief || ''}</p></div>
    `;
}

function switchTab(signalId, tab, el) {
    // Toggle tab buttons
    el.parentElement.querySelectorAll('.activation-tab').forEach(t => t.classList.remove('active'));
    el.classList.add('active');
    // Toggle panels
    const parent = el.closest('.activation-section');
    parent.querySelectorAll('.activation-panel').forEach(p => p.classList.remove('active'));
    document.getElementById(`tab-${signalId}-${tab}`).classList.add('active');
}

async function activateSignal(signalId, btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Génération…';

    const res = await fetch(`/api/activate/${signalId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config_name: _currentConfig }),
    });

    const activation = await res.json();

    // Update local data
    const signal = _allSignals.find(s => s.id === signalId);
    if (signal) {
        signal.activation = activation;
    }

    // Re-render just the activation section
    const section = document.getElementById(`activation-${signalId}`);
    section.innerHTML = renderActivation(signal || { id: signalId, activation });
}
