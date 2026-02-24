/* ============================
   Verichains LeadHunter — App Logic
   Vanilla JS — API calls, rendering, interactions
   ============================ */

const API = '';
const STAGES = ['Discovered', 'Researching', 'Outreach', 'Proposal', 'Won', 'Lost'];

// ============================
//  Tab Navigation
// ============================
function switchTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.getElementById('tab-' + tabId).classList.add('active');
    document.querySelector(`.nav-item[data-tab="${tabId}"]`).classList.add('active');

    // Load data for each tab
    if (tabId === 'dashboard') loadDashboard();
    if (tabId === 'pipeline') loadPipeline();
    if (tabId === 'watchlist') loadWatchlist();
    if (tabId === 'incidents') loadIncidents();
    if (tabId === 'scans') loadScanLogs();
}

// ============================
//  API Helpers
// ============================
async function api(path, options = {}) {
    try {
        const resp = await fetch(API + path, {
            headers: { 'Content-Type': 'application/json' },
            ...options,
            body: options.body ? JSON.stringify(options.body) : undefined,
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: 'Request failed' }));
            throw new Error(err.detail || 'Request failed');
        }
        return await resp.json();
    } catch (e) {
        console.error('API Error:', e);
        throw e;
    }
}

// ============================
//  Toast Notifications
// ============================
function toast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const icons = { success: '✅', error: '❌', info: 'ℹ️' };
    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.innerHTML = `<span>${icons[type] || ''}</span> ${message}`;
    container.appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300); }, 4000);
}

// ============================
//  Badge Helpers
// ============================
function priorityBadge(priority) {
    const cls = { HOT: 'hot', WARM: 'warm', MONITOR: 'monitor', LOW: 'low' };
    const icons = { HOT: '🔴', WARM: '🟡', MONITOR: '🟢', LOW: '⚪' };
    return `<span class="badge badge-${cls[priority] || 'low'}">${icons[priority] || ''} ${priority}</span>`;
}

function scoreBadge(score) {
    return `<span class="badge badge-score">${score}/100</span>`;
}

function categoryBadge(cat) {
    return `<span class="badge badge-category">${cat}</span>`;
}

function scoredByBadge(scoredBy) {
    if (!scoredBy) return '';
    const isAI = scoredBy.startsWith('ai:');
    const label = isAI ? `🤖 ${scoredBy.replace('ai:', 'AI:').replace('gemini', 'Gemini').replace('anthropic', 'Claude').replace('openai', 'GPT').replace('antigravity', 'Antigravity')}` : '📐 Heuristic';
    const bg = isAI ? 'rgba(139, 92, 246, 0.15)' : 'rgba(107, 114, 128, 0.15)';
    const color = isAI ? '#a78bfa' : '#9ca3af';
    const border = isAI ? 'rgba(139, 92, 246, 0.3)' : 'rgba(107, 114, 128, 0.3)';
    return `<span style="display:inline-flex;align-items:center;gap:3px;padding:2px 8px;border-radius:6px;font-size:11px;font-weight:500;background:${bg};color:${color};border:1px solid ${border};">${label}</span>`;
}

function leadGroupBadge(group) {
    if (!group) return '';
    const config = {
        A: { label: 'A · Net-New', icon: '🆕', bg: 'rgba(59, 130, 246, 0.15)', color: '#60a5fa', border: 'rgba(59, 130, 246, 0.3)' },
        B: { label: 'B · Upgrade', icon: '⬆️', bg: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24', border: 'rgba(245, 158, 11, 0.3)' },
        C: { label: 'C · Incident', icon: '🚨', bg: 'rgba(239, 68, 68, 0.15)', color: '#f87171', border: 'rgba(239, 68, 68, 0.3)' },
        D: { label: 'D · Compliance', icon: '📋', bg: 'rgba(34, 197, 94, 0.15)', color: '#4ade80', border: 'rgba(34, 197, 94, 0.3)' },
    };
    const c = config[group] || config.A;
    return `<span style="display:inline-flex;align-items:center;gap:3px;padding:2px 8px;border-radius:6px;font-size:11px;font-weight:600;background:${c.bg};color:${c.color};border:1px solid ${c.border};">${c.icon} ${c.label}</span>`;
}

function projectLinksCompact(lead) {
    const links = [];
    if (lead.defillama_url) links.push(`<a href="${lead.defillama_url}" target="_blank" title="DeFiLlama" onclick="event.stopPropagation()" style="color:#60a5fa;text-decoration:none;font-size:13px;">📊</a>`);
    if (lead.website_url) links.push(`<a href="${lead.website_url}" target="_blank" title="Website" onclick="event.stopPropagation()" style="color:#60a5fa;text-decoration:none;font-size:13px;">🌐</a>`);
    if (lead.twitter_url) links.push(`<a href="${lead.twitter_url}" target="_blank" title="X / Twitter" onclick="event.stopPropagation()" style="color:#60a5fa;text-decoration:none;font-size:13px;">𝕏</a>`);
    if (lead.github_url) links.push(`<a href="${lead.github_url}" target="_blank" title="GitHub" onclick="event.stopPropagation()" style="color:#60a5fa;text-decoration:none;font-size:13px;">💻</a>`);
    if (links.length === 0) return '';
    return `<span style="display:inline-flex;gap:5px;align-items:center;margin-left:4px;">${links.join('')}</span>`;
}

function listedAtBadge(listedAt) {
    if (!listedAt) return '';
    return `<span style="display:inline-flex;align-items:center;gap:3px;padding:2px 8px;border-radius:6px;font-size:10px;font-weight:500;background:rgba(107,114,128,0.12);color:#9ca3af;border:1px solid rgba(107,114,128,0.2);">📅 ${listedAt}</span>`;
}

// ============================
//  Dashboard
// ============================
async function loadDashboard() {
    try {
        const stats = await api('/api/stats');
        document.getElementById('stat-hot').textContent = stats.hot || 0;
        document.getElementById('stat-warm').textContent = stats.warm || 0;
        document.getElementById('stat-monitor').textContent = stats.monitor || 0;
        document.getElementById('stat-total').textContent = stats.total_leads || 0;
        document.getElementById('stat-watchlist').textContent = stats.watchlist_count || 0;
        document.getElementById('stat-incidents').textContent = stats.incidents_count || 0;

        // Hot leads list
        const leads = await api('/api/leads?priority=HOT');
        const hotList = document.getElementById('hot-leads-list');
        if (leads.length === 0) {
            hotList.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🔍</div>No HOT leads yet. Run a scan!</div>';
        } else {
            hotList.innerHTML = leads.slice(0, 5).map(l => `
                <div class="lead-mini" onclick="showLeadDetail(${l.id})">
                    <span class="lead-mini-name">${esc(l.name)}</span>
                    ${categoryBadge(l.category)}
                    <span class="lead-mini-score" style="color: var(--hot)">${l.score}</span>
                </div>
            `).join('');
        }

        // Category chart
        const chartEl = document.getElementById('category-chart');
        const cats = stats.categories || {};
        const maxCat = Math.max(...Object.values(cats), 1);
        if (Object.keys(cats).length === 0) {
            chartEl.innerHTML = '<div class="empty-state">No data yet</div>';
        } else {
            chartEl.innerHTML = Object.entries(cats).sort((a, b) => b[1] - a[1]).map(([cat, count]) => `
                <div class="chart-bar-row">
                    <span class="chart-bar-label">${esc(cat)}</span>
                    <div class="chart-bar-track">
                        <div class="chart-bar-fill" style="width: ${(count / maxCat * 100)}%">${count}</div>
                    </div>
                </div>
            `).join('');
        }

        // Recent scans
        await renderRecentScans('recent-scans', 5);
    } catch (e) {
        toast('Failed to load dashboard: ' + e.message, 'error');
    }
}

// ============================
//  Pipeline (Kanban)
// ============================
let allLeads = [];

async function loadPipeline() {
    try {
        allLeads = await api('/api/leads');
        renderPipeline(allLeads);
    } catch (e) {
        toast('Failed to load pipeline: ' + e.message, 'error');
    }
}

function filterPipeline() {
    const search = document.getElementById('pipeline-search').value.toLowerCase();
    const priority = document.getElementById('pipeline-filter-priority').value;
    const category = document.getElementById('pipeline-filter-category').value;

    let filtered = allLeads;
    if (search) filtered = filtered.filter(l => l.name.toLowerCase().includes(search) || (l.summary || '').toLowerCase().includes(search));
    if (priority) filtered = filtered.filter(l => l.priority === priority);
    if (category) filtered = filtered.filter(l => l.category === category);

    renderPipeline(filtered);
}

function renderPipeline(leads) {
    STAGES.forEach(stage => {
        const col = document.getElementById('col-' + stage);
        const stageLeads = leads.filter(l => l.stage === stage);
        document.getElementById('count-' + stage).textContent = stageLeads.length;

        if (stageLeads.length === 0) {
            col.innerHTML = '<div class="empty-state" style="padding: 20px;">No leads</div>';
        } else {
            col.innerHTML = stageLeads.map(l => renderLeadCard(l)).join('');
        }
    });
}

function renderLeadCard(lead) {
    const stageOptions = STAGES.filter(s => s !== lead.stage)
        .map(s => `<button class="btn btn-ghost" onclick="moveLeadStage(${lead.id}, '${s}')">${s}</button>`)
        .join('');

    return `
        <div class="lead-card" onclick="showLeadDetail(${lead.id})">
            <div class="lead-card-name" style="display:flex;align-items:center;gap:6px;">
                ${esc(lead.name)} ${projectLinksCompact(lead)}
            </div>
            <div class="lead-card-meta">
                ${leadGroupBadge(lead.lead_group)}
                ${priorityBadge(lead.priority)}
                ${scoreBadge(lead.score)}
                ${categoryBadge(lead.category)}
                ${listedAtBadge(lead.listed_at)}
                ${scoredByBadge(lead.scored_by)}
            </div>
            <div class="lead-card-summary">${esc(lead.summary || '')}</div>
            <div class="lead-card-actions" onclick="event.stopPropagation()">
                ${stageOptions}
            </div>
        </div>
    `;
}

async function moveLeadStage(id, newStage) {
    try {
        await api(`/api/leads/${id}`, { method: 'PATCH', body: { stage: newStage } });
        toast(`Moved to ${newStage}`, 'success');
        loadPipeline();
    } catch (e) {
        toast('Move failed: ' + e.message, 'error');
    }
}

// ============================
//  Lead Detail Modal
// ============================
function showLeadDetail(id) {
    const lead = allLeads.find(l => l.id === id);
    if (!lead) return;

    // Parse score_breakdown JSON
    let breakdown = {};
    try {
        breakdown = typeof lead.score_breakdown === 'string'
            ? JSON.parse(lead.score_breakdown || '{}')
            : (lead.score_breakdown || {});
    } catch (e) { breakdown = {}; }

    // Build breakdown HTML
    let breakdownHtml = '';
    const keys = Object.keys(breakdown);
    if (keys.length > 0) {
        const rows = keys.map(key => {
            const b = breakdown[key];
            const pts = b.points || 0;
            const max = b.max || 1;
            const pct = Math.round((pts / max) * 100);
            const barColor = pct >= 70 ? 'var(--green)' : pct >= 40 ? 'var(--amber)' : pts === 0 ? 'var(--text-muted, #444)' : 'var(--red)';
            return `
                <div style="display: grid; grid-template-columns: 140px 55px 1fr; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px solid var(--border-subtle);">
                    <span style="font-size: 12px; font-weight: 500; color: var(--text-secondary);">${esc(key)}</span>
                    <span style="font-size: 12px; font-weight: 600; text-align: right; color: ${barColor};">${pts}/${max}</span>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <div style="flex: 1; height: 6px; background: var(--bg-tertiary, #1a1a2e); border-radius: 3px; overflow: hidden;">
                            <div style="width: ${pct}%; height: 100%; background: ${barColor}; border-radius: 3px; transition: width 0.3s;"></div>
                        </div>
                    </div>
                </div>
                <div style="grid-column: 1 / -1; font-size: 11px; color: var(--text-muted, #666); padding: 0 0 4px 0; margin-top: -4px;">${esc(b.reason || '')}</div>
            `;
        }).join('');

        const totalPts = keys.reduce((s, k) => s + (breakdown[k].points || 0), 0);
        const totalMax = keys.reduce((s, k) => s + (breakdown[k].max || 0), 0);

        breakdownHtml = `
            <div class="form-group" style="margin-top: 8px;">
                <label style="display: flex; justify-content: space-between; align-items: center;">
                    <span>📊 Score Breakdown</span>
                    <span style="font-size: 13px; font-weight: 600; color: var(--purple);">${totalPts} / ${totalMax}</span>
                </label>
                <div style="background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 10px 14px; margin-top: 4px;">
                    ${rows}
                </div>
            </div>
        `;
    }

    document.getElementById('modal-title').textContent = lead.name;
    document.getElementById('modal-body').innerHTML = `
        <div style="display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; align-items: center;">
            ${leadGroupBadge(lead.lead_group)}
            ${priorityBadge(lead.priority)} ${scoreBadge(lead.score)} ${categoryBadge(lead.category)}
            <span class="badge badge-source">${esc(lead.source)}</span>
            ${scoredByBadge(lead.scored_by)}
            ${listedAtBadge(lead.listed_at)}
        </div>

        ${(lead.defillama_url || lead.website_url || lead.twitter_url || lead.github_url) ? `
        <div style="display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; font-size: 13px;">
            ${lead.defillama_url ? `<a href="${lead.defillama_url}" target="_blank" style="color:#60a5fa;text-decoration:none;">📊 DeFiLlama</a>` : ''}
            ${lead.website_url ? `<a href="${lead.website_url}" target="_blank" style="color:#60a5fa;text-decoration:none;">🌐 Website</a>` : ''}
            ${lead.twitter_url ? `<a href="${lead.twitter_url}" target="_blank" style="color:#60a5fa;text-decoration:none;">𝕏 Twitter</a>` : ''}
            ${lead.github_url ? `<a href="${lead.github_url}" target="_blank" style="color:#60a5fa;text-decoration:none;">💻 GitHub</a>` : ''}
        </div>
        ` : ''}

        <div class="form-group">
            <label>AI Summary</label>
            <div style="font-size: 13px; color: var(--text-secondary); line-height: 1.6;">${esc(lead.summary || 'No summary')}</div>
        </div>

        ${breakdownHtml}

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
            <div class="form-group">
                <label>Funding</label>
                <div style="font-size: 13px;">${esc(lead.funding || 'N/A')}</div>
            </div>
            <div class="form-group">
                <label>Tech</label>
                <div style="font-size: 13px;">${esc(lead.tech || 'N/A')}</div>
            </div>
            <div class="form-group">
                <label>Audit Status</label>
                <div style="font-size: 13px;">${esc(lead.audit_status || 'Unknown')}</div>
            </div>
            <div class="form-group">
                <label>Services to Pitch</label>
                <div style="font-size: 13px;">${esc(lead.pitch_services || 'N/A')}</div>
            </div>
        </div>

        <div class="form-group">
            <label>Signals</label>
            <div style="font-size: 13px; color: var(--text-secondary);">${esc(lead.trigger_info || 'None')}</div>
        </div>

        <div class="form-group">
            <label>Stage</label>
            <select id="detail-stage" onchange="updateLeadField(${lead.id}, 'stage', this.value)" style="width: 100%; padding: 9px 12px; background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); color: var(--text-primary); font-size: 13px;">
                ${STAGES.map(s => `<option value="${s}" ${s === lead.stage ? 'selected' : ''}>${s}</option>`).join('')}
            </select>
        </div>

        <div class="form-group">
            <label>Contact Notes</label>
            <textarea id="detail-notes" rows="3" placeholder="Add contact info, LinkedIn, X handle..."
                style="width: 100%; padding: 9px 12px; background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); color: var(--text-primary); font-size: 13px; resize: vertical;"
            >${esc(lead.contact_notes || '')}</textarea>
        </div>

        <div class="form-actions">
            <button class="btn btn-danger btn-sm" onclick="deleteLead(${lead.id})">Delete</button>
            <button class="btn" style="background:rgba(245,158,11,0.15);color:#fbbf24;border:1px solid rgba(245,158,11,0.3);font-size:12px;" onclick="addLeadToWatchlist(${lead.id})">👁️ Monitor for Upgrades</button>
            <button class="btn btn-secondary" onclick="closeModal()">Close</button>
            <button class="btn btn-primary" onclick="saveLeadNotes(${lead.id})">Save Notes</button>
        </div>
    `;
    openModal();
}

async function saveLeadNotes(id) {
    const notes = document.getElementById('detail-notes').value;
    try {
        await api(`/api/leads/${id}`, { method: 'PATCH', body: { contact_notes: notes } });
        toast('Notes saved', 'success');
    } catch (e) {
        toast('Save failed: ' + e.message, 'error');
    }
}

async function updateLeadField(id, field, value) {
    try {
        await api(`/api/leads/${id}`, { method: 'PATCH', body: { [field]: value } });
        toast(`Updated ${field}`, 'success');
        loadPipeline();
    } catch (e) {
        toast('Update failed: ' + e.message, 'error');
    }
}

async function deleteLead(id) {
    if (!confirm('Delete this lead?')) return;
    try {
        await api(`/api/leads/${id}`, { method: 'DELETE' });
        toast('Lead deleted', 'success');
        closeModal();
        loadPipeline();
        loadDashboard();
    } catch (e) {
        toast('Delete failed: ' + e.message, 'error');
    }
}

async function addLeadToWatchlist(leadId) {
    const lead = allLeads.find(l => l.id === leadId);
    if (!lead) return;

    const project = {
        name: lead.name,
        github_repo: lead.github_url || '',
        x_account: lead.twitter_url || '',
        category: lead.category || 'DeFi',
        last_audit_date: '',
        auditor: (lead.audit_status || '').includes('✅') ? lead.audit_status.substring(0, 60) : '',
        client_type: 'Mid-cap',
        notes: `From pipeline (score: ${lead.score}, group: ${lead.lead_group || 'A'}). ${lead.audit_status || ''}`,
    };

    try {
        await api('/api/watchlist', { method: 'POST', body: project });
        toast(`${lead.name} added to Watchlist for monitoring!`, 'success');
    } catch (e) {
        if (e.message.includes('409') || e.message.includes('already')) {
            toast(`${lead.name} already in watchlist`, 'info');
        } else {
            toast('Failed: ' + e.message, 'error');
        }
    }
}

// ============================
//  Watchlist
// ============================
async function loadWatchlist() {
    try {
        const items = await api('/api/watchlist');
        const tbody = document.getElementById('watchlist-body');
        if (items.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="empty-state"><div class="empty-state-icon">👁️</div>No projects yet. Click "Add Project" to start.</td></tr>';
            return;
        }
        tbody.innerHTML = items.map(item => {
            let proxyCount = 0;
            try {
                const pc = typeof item.proxy_contracts === 'string' ? JSON.parse(item.proxy_contracts || '{}') : (item.proxy_contracts || {});
                proxyCount = Object.values(pc).reduce((sum, addrs) => sum + (Array.isArray(addrs) ? addrs.length : 0), 0);
            } catch (e) { }
            return `
            <tr>
                <td><strong>${esc(item.name)}</strong></td>
                <td>${categoryBadge(item.category || 'Other')}</td>
                <td>${item.github_repo ? `<a href="${esc(item.github_repo)}" target="_blank">📂 Repo</a>` : '—'}</td>
                <td>${item.snapshot_space ? esc(item.snapshot_space) : '—'}</td>
                <td><span class="badge badge-source">${esc(item.client_type || '—')}</span></td>
                <td>${proxyCount > 0 ? `<button class="btn btn-ghost btn-sm" onclick="showProxyContracts(${item.id})" style="color:#818cf8;">🔗 ${proxyCount}</button>` : `<button class="btn btn-ghost btn-sm" onclick="showProxyContracts(${item.id})" style="color:var(--text-tertiary);">+ Add</button>`}</td>
                <td>
                    <button class="btn btn-ghost btn-sm" onclick="deleteWatchlistItem(${item.id})">🗑️</button>
                </td>
            </tr>
        `}).join('');
    } catch (e) {
        toast('Failed to load watchlist: ' + e.message, 'error');
    }
}

function showAddWatchlistModal() {
    document.getElementById('modal-title').textContent = 'Add Project to Watchlist';
    document.getElementById('modal-body').innerHTML = `
        <div class="form-group">
            <label>Project Name *</label>
            <input type="text" id="wl-name" placeholder="e.g. Uniswap">
        </div>
        <div class="form-group">
            <label>GitHub Repository</label>
            <input type="text" id="wl-github" placeholder="https://github.com/org/repo">
        </div>
        <div class="form-group">
            <label>Snapshot Space</label>
            <input type="text" id="wl-snapshot" placeholder="e.g. uniswapgovernance.eth">
        </div>
        <div class="form-group">
            <label>X Account</label>
            <input type="text" id="wl-x" placeholder="@handle">
        </div>
        <div class="form-group">
            <label>Category</label>
            <select id="wl-category">
                <option value="DeFi">DeFi</option>
                <option value="GameFi">GameFi</option>
                <option value="RWA">RWA</option>
                <option value="ZK">ZK</option>
                <option value="L1-L2">L1-L2</option>
                <option value="Other">Other</option>
            </select>
        </div>
        <div class="form-group">
            <label>Client Type</label>
            <select id="wl-client-type">
                <option value="Mid-cap">Mid-cap</option>
                <option value="Khách cũ">Khách cũ</option>
                <option value="ZK Target">ZK Target</option>
                <option value="L2">L2</option>
            </select>
        </div>
        <div class="form-group">
            <label>Last Audit Date</label>
            <input type="date" id="wl-audit-date">
        </div>
        <div class="form-group">
            <label>Proxy Contracts <span style="color:var(--text-tertiary);font-weight:normal;">(for on-chain monitoring)</span></label>
            <div style="font-size:11px;color:var(--text-tertiary);margin-bottom:6px;">One per line: chain:address (e.g. ethereum:0xabc...)</div>
            <textarea id="wl-proxies" rows="3" placeholder="ethereum:0xabc...&#10;arbitrum:0xdef...&#10;base:0x123..."></textarea>
        </div>
        <div class="form-group">
            <label>Notes</label>
            <textarea id="wl-notes" rows="2" placeholder="Additional notes..."></textarea>
        </div>
        <div class="form-actions">
            <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
            <button class="btn btn-primary" onclick="addWatchlistProject()">Add Project</button>
        </div>
    `;
    openModal();
}

async function addWatchlistProject() {
    // Parse proxy contracts from textarea
    const proxyText = document.getElementById('wl-proxies').value.trim();
    const proxies = {};
    if (proxyText) {
        for (const line of proxyText.split('\n')) {
            const [chain, addr] = line.split(':').map(s => s.trim());
            if (chain && addr) {
                if (!proxies[chain]) proxies[chain] = [];
                proxies[chain].push(addr.toLowerCase());
            }
        }
    }

    const project = {
        name: document.getElementById('wl-name').value.trim(),
        github_repo: document.getElementById('wl-github').value.trim(),
        snapshot_space: document.getElementById('wl-snapshot').value.trim(),
        x_account: document.getElementById('wl-x').value.trim(),
        category: document.getElementById('wl-category').value,
        client_type: document.getElementById('wl-client-type').value,
        last_audit_date: document.getElementById('wl-audit-date').value,
        proxy_contracts: JSON.stringify(proxies),
        notes: document.getElementById('wl-notes').value.trim(),
    };

    if (!project.name) { toast('Project name is required', 'error'); return; }

    try {
        await api('/api/watchlist', { method: 'POST', body: project });
        toast('Project added to watchlist!', 'success');
        closeModal();
        loadWatchlist();
    } catch (e) {
        toast('Failed: ' + e.message, 'error');
    }
}

async function deleteWatchlistItem(id) {
    if (!confirm('Remove from watchlist?')) return;
    try {
        await api(`/api/watchlist/${id}`, { method: 'DELETE' });
        toast('Removed from watchlist', 'success');
        loadWatchlist();
    } catch (e) {
        toast('Delete failed: ' + e.message, 'error');
    }
}

// Store watchlist items for proxy editing
let watchlistItems = [];

async function showProxyContracts(itemId) {
    // Fetch fresh watchlist to get current data
    try {
        watchlistItems = await api('/api/watchlist');
    } catch (e) {
        toast('Failed to load watchlist', 'error');
        return;
    }
    const item = watchlistItems.find(i => i.id === itemId);
    if (!item) return;

    let proxies = {};
    try {
        proxies = typeof item.proxy_contracts === 'string'
            ? JSON.parse(item.proxy_contracts || '{}')
            : (item.proxy_contracts || {});
    } catch (e) { }

    // Convert to text format
    const lines = [];
    for (const [chain, addrs] of Object.entries(proxies)) {
        if (Array.isArray(addrs)) {
            addrs.forEach(a => lines.push(`${chain}:${a}`));
        }
    }

    const supportedChains = ['ethereum', 'arbitrum', 'base', 'optimism', 'polygon', 'bsc', 'avalanche', 'sonic'];

    document.getElementById('modal-title').textContent = `🔗 ${item.name} — Proxy Contracts`;
    document.getElementById('modal-body').innerHTML = `
        <div class="form-group">
            <label>On-chain Proxy Addresses</label>
            <div style="font-size:11px;color:var(--text-tertiary);margin-bottom:8px;">
                One per line: <code>chain:0xaddress</code><br>
                Supported chains: ${supportedChains.map(c => `<code>${c}</code>`).join(', ')}
            </div>
            <textarea id="proxy-edit" rows="6" style="font-family:monospace;font-size:12px;"
                placeholder="ethereum:0xabc...&#10;arbitrum:0xdef...">${lines.join('\n')}</textarea>
        </div>
        <div style="padding:10px 14px;background:rgba(99,102,241,0.08);border-radius:var(--radius-sm);border:1px solid rgba(99,102,241,0.2);margin-bottom:16px;">
            <div style="font-size:12px;color:#818cf8;">💡 Where to find proxy addresses</div>
            <div style="font-size:11px;color:var(--text-secondary);margin-top:4px;">
                Check the project's docs or Etherscan. Look for "Proxy" label on the contract page.
                Common proxies: TransparentProxy, UUPS, Beacon.
            </div>
        </div>
        <div class="form-actions">
            <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
            <button class="btn btn-primary" onclick="saveProxyContracts(${itemId})">Save</button>
        </div>
    `;
    openModal();
}

async function saveProxyContracts(itemId) {
    const text = document.getElementById('proxy-edit').value.trim();
    const proxies = {};
    if (text) {
        for (const line of text.split('\n')) {
            const trimmed = line.trim();
            if (!trimmed) continue;
            const colonIdx = trimmed.indexOf(':');
            if (colonIdx < 1) continue;
            const chain = trimmed.substring(0, colonIdx).trim().toLowerCase();
            const addr = trimmed.substring(colonIdx + 1).trim().toLowerCase();
            if (chain && addr && addr.startsWith('0x')) {
                if (!proxies[chain]) proxies[chain] = [];
                proxies[chain].push(addr);
            }
        }
    }

    try {
        await api(`/api/watchlist/${itemId}`, {
            method: 'PATCH',
            body: { proxy_contracts: JSON.stringify(proxies) }
        });
        toast('Proxy contracts saved!', 'success');
        closeModal();
        loadWatchlist();
    } catch (e) {
        toast('Save failed: ' + e.message, 'error');
    }
}

// ============================
//  Incidents
// ============================
async function loadIncidents() {
    try {
        const incidents = await api('/api/incidents');
        const container = document.getElementById('incidents-list');
        if (incidents.length === 0) {
            container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🛡️</div>No incidents detected. Click "Scan Incidents" to check.</div>';
            return;
        }
        container.innerHTML = incidents.map(inc => `
            <div class="incident-card">
                <h4>💥 ${esc(inc.project_name || inc.title)}</h4>
                <div class="incident-detail">📌 Category: ${esc(inc.category)}</div>
                <div class="incident-detail">💰 Lost: ${esc(inc.amount_lost || 'Unknown')}</div>
                <div class="incident-detail">🔍 Root cause: ${esc(inc.root_cause || 'Unknown')}</div>
                ${inc.link ? `<div class="incident-detail"><a href="${esc(inc.link)}" target="_blank">🔗 Read more</a></div>` : ''}
                ${inc.targets && inc.targets.length > 0 ? `
                    <div class="incident-targets">
                        <h5>🎯 Target Protocols</h5>
                        ${inc.targets.map(t => `<div style="font-size: 12px; padding: 2px 0;">• ${esc(t)}</div>`).join('')}
                    </div>
                ` : ''}
                ${inc.outreach_draft ? `
                    <div class="incident-draft">"${esc(inc.outreach_draft)}"</div>
                ` : ''}
                <div style="font-size: 11px; color: var(--text-muted); margin-top: 8px;">${inc.created_at || ''}</div>
            </div>
        `).join('');
    } catch (e) {
        toast('Failed to load incidents: ' + e.message, 'error');
    }
}

// ============================
//  Scan Triggers
// ============================
async function runScan(type) {
    const labels = { leads: 'Lead Scan', upgrades: 'Upgrade Scan', incidents: 'Incident Scan', rescore: 'Re-score Leads' };
    const statusEl = document.getElementById('scan-status');
    statusEl.innerHTML = '<div class="status-dot status-running"></div><span>Scanning...</span>';

    toast(`Starting ${labels[type]}...`, 'info');

    try {
        const result = await api(`/api/run-scan/${type}`, { method: 'POST' });
        toast(`${labels[type]} complete!`, 'success');

        // Refresh current tab
        const activeTab = document.querySelector('.nav-item.active')?.dataset.tab;
        if (activeTab) switchTab(activeTab);
    } catch (e) {
        toast(`Scan failed: ${e.message}`, 'error');
    } finally {
        statusEl.innerHTML = '<div class="status-dot status-idle"></div><span>System Idle</span>';
    }
}

// ============================
//  Scan Logs
// ============================
async function loadScanLogs() {
    await renderRecentScans('scan-logs-list', 20);
}

async function renderRecentScans(containerId, limit) {
    try {
        const logs = await api('/api/scan-logs');
        const container = document.getElementById(containerId);
        if (!logs || logs.length === 0) {
            container.innerHTML = '<div class="empty-state">No scans yet</div>';
            return;
        }
        container.innerHTML = logs.slice(0, limit).map(log => {
            const icons = { lead_hunter: '📡', upgrade_watcher: '🔍', incident_radar: '🚨' };
            const statusIcons = { completed: '✅', failed: '❌', running: '⏳' };
            return `
                <div class="scan-log-item ${log.status}">
                    <span>${icons[log.scan_type] || '⚡'}</span>
                    <span class="scan-log-type">${esc(log.scan_type)}</span>
                    <span class="scan-log-status">${statusIcons[log.status] || ''} ${log.status}${log.leads_found ? ` · ${log.leads_found} found` : ''}${log.hot_count ? ` · 🔴${log.hot_count}` : ''}</span>
                    <span class="scan-log-time">${log.started_at || ''}</span>
                </div>
            `;
        }).join('');
    } catch (e) {
        document.getElementById(containerId).innerHTML = '<div class="empty-state">Failed to load</div>';
    }
}

// ============================
//  Modal Helpers
// ============================
function openModal() {
    document.getElementById('modal-overlay').classList.add('open');
}

function closeModal() {
    document.getElementById('modal-overlay').classList.remove('open');
}

// Escape HTML
function esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

// ============================
//  Init
// ============================
document.addEventListener('DOMContentLoaded', () => {
    loadDashboard();
});

// Keyboard shortcut: Escape to close modal
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
});
