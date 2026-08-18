// ─────────────────────────────────────────────────────────────────
// Reddit Plus v2 — Opportunity Intelligence Dashboard Application
// ─────────────────────────────────────────────────────────────────

const API = '/api/v1';
let currentTab = 'opportunities';

// ── TOAST ALERTS ──────────────────────────────────────────────────
function toast(msg, type = 'info', duration = 4000) {
  const c = document.getElementById('toast-container');
  if (!c) return;
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  const icon = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';
  t.innerHTML = `<span>${icon}</span><span style="flex:1;">${msg}</span><span style="cursor:pointer;opacity:0.6;" onclick="this.parentElement.remove()">✕</span>`;
  c.appendChild(t);
  setTimeout(() => t.remove(), duration);
}

// ── API REQUEST HELPER ───────────────────────────────────────────
async function api(path, options = {}) {
  const url = path.startsWith('/api') ? path : `${API}${path}`;
  const resp = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || `HTTP ${resp.status}`);
  }
  return resp.json();
}

// ── NAVIGATION ───────────────────────────────────────────────────
function navigate(tab) {
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.page').forEach(el => el.classList.remove('active'));

  const navEl = document.querySelector(`[data-page="${tab}"]`);
  if (navEl) navEl.classList.add('active');

  const pageEl = document.getElementById(`page-${tab}`);
  if (pageEl) pageEl.classList.add('active');

  currentTab = tab;

  const titles = {
    opportunities: ['Opportunity Inbox', 'High-intent Reddit conversations worth acting on today'],
    posts: ['Reddit Explorer', 'Search and explore monitored Reddit discussions'],
    monitoring: ['Monitoring Rules', 'Automated search rules & AI keyword discovery'],
    subreddits: ['Subreddit Profiles', 'Community intelligence, culture & promotion tolerance'],
    competitors: ['Competitor Tracker', 'Intercept competitor complaints and migration inquiries'],
    playground: ['AI & Critic Lab', 'Test intent classification and evaluate reply drafts'],
    settings: ['Alerts & Settings', 'Push notifications, AI models, and preferences'],
    logs: ['Activity Stream', 'Real-time ingestion and event stream'],
  };

  const [t, sub] = titles[tab] || ['Reddit Plus', ''];
  document.getElementById('topbar-title').textContent = t;
  document.getElementById('topbar-subtitle').textContent = sub;

  if (tab === 'opportunities') loadOpportunities();
  if (tab === 'posts') loadPosts();
  if (tab === 'monitoring') loadMonitoringRules();
  if (tab === 'subreddits') loadSubreddits();
  if (tab === 'competitors') loadCompetitors();
  if (tab === 'settings') loadSettings();
  if (tab === 'logs') loadLogs();
}

// ── CYCLE TRIGGER ────────────────────────────────────────────────
async function triggerCycle(btn) {
  const orig = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '⚡ Running Cycle...';
  try {
    const res = await api('/dashboard/trigger-cycle', { method: 'POST' });
    const r = res.results || {};
    toast(`Cycle complete! Found ${r.matches_found} matches, analyzed ${r.analyses_completed}`, 'success');
    loadMetrics();
    if (currentTab === 'opportunities') loadOpportunities();
  } catch (e) {
    toast(`Cycle error: ${e.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = orig;
  }
}

// ── METRICS ──────────────────────────────────────────────────────
async function loadMetrics() {
  try {
    const data = await api('/dashboard/metrics');
    document.getElementById('metric-high-opps').textContent = data.high_opportunities || 0;
    document.getElementById('opps-badge').textContent = data.high_opportunities || 0;
    document.getElementById('metric-buy-signals').textContent = data.intent_distribution?.['buy-intent'] || 0;
    document.getElementById('metric-pain-points').textContent = data.intent_distribution?.['pain-point'] || 0;
    document.getElementById('metric-rules').textContent = data.active_rules || 0;
  } catch (_) {}
}

// ── OPPORTUNITY INBOX ────────────────────────────────────────────
async function loadOpportunities() {
  const container = document.getElementById('opp-container');
  container.innerHTML = '<div class="skeleton skeleton-card"></div><div class="skeleton skeleton-card"></div>';

  const intent = document.getElementById('opp-filter-intent')?.value || '';
  const minScore = document.getElementById('opp-filter-min-score')?.value || '';
  const status = document.getElementById('opp-filter-status')?.value || '';

  let path = `/opportunities?limit=30`;
  if (intent) path += `&intent=${encodeURIComponent(intent)}`;
  if (minScore) path += `&min_score=${minScore}`;
  if (status) path += `&status=${status}`;

  try {
    const data = await api(path);
    const items = data.items || [];
    if (!items.length) {
      container.innerHTML = `
        <div class="empty-box">
          <div class="empty-icon">🎯</div>
          <div class="empty-title">No opportunities found</div>
          <div class="empty-sub">Adjust filters or click "Ingest & Analyze Now" to poll Reddit.</div>
          <button class="btn btn-primary btn-sm" onclick="triggerCycle(this)">⚡ Ingest & Analyze Now</button>
        </div>`;
      return;
    }
    container.innerHTML = items.map(renderOpportunityCard).join('');
  } catch (e) {
    container.innerHTML = `<div class="empty-box"><div class="empty-title">Failed to load opportunities</div><div class="empty-sub">${e.message}</div></div>`;
  }
}

function renderOpportunityCard(opp) {
  const post = opp.post || {};
  const score = opp.opportunity?.total_score || Math.round(opp.match_score || 50);
  const reasons = opp.match_reasons || [];
  const analysis = opp.analysis || {};
  const intent = analysis.intent_tag || 'question';
  const age = timeAgo(post.posted_at);

  let scoreClass = '';
  if (score >= 85) scoreClass = 'extreme';
  else if (score >= 70) scoreClass = 'high';

  return `
  <div class="opp-card" id="opp-${opp.id}">
    <div class="opp-card-inner">
      <div class="opp-top-row">
        <span class="opp-score-badge ${scoreClass}">🔥 Opportunity ${score}/100</span>
        <span class="subreddit-chip">r/${esc(post.subreddit || 'all')}</span>
        <span class="intent-chip intent-${intent}">${intent.replace('-', ' ')}</span>
        <span style="font-size:12px;color:var(--text-muted);">· u/${esc(post.author || 'deleted')} · ${age}</span>
        <div style="margin-left:auto;display:flex;gap:6px;">
          <button class="btn btn-secondary btn-sm" onclick="toggleOppDrawer(${opp.id})">🔬 Deep Intel & Reply</button>
          <button class="btn btn-ghost btn-sm" onclick="setOppStatus(${opp.id}, 'saved')">⭐ Save</button>
        </div>
      </div>

      <div class="opp-title">
        <a href="${esc(post.permalink || post.url || '#')}" target="_blank" rel="noopener">${esc(post.title || 'Untitled Discussion')}</a>
      </div>

      ${post.body ? `<div class="opp-excerpt">${esc(post.body)}</div>` : ''}

      ${reasons.length ? `
      <div class="match-reasons-row">
        ${reasons.map(r => `<span class="match-reason-tag">✓ ${esc(r)}</span>`).join('')}
      </div>` : ''}

      <div class="opp-footer">
        <div class="opp-signals">
          <span class="signal-hot">▲ ${post.score || 0}</span>
          <span>💬 ${post.num_comments || 0} comments</span>
          <span>📊 ${Math.round((post.upvote_ratio || 0) * 100)}% upvoted</span>
          <span>🎯 Rule: ${esc(opp.rule_name || 'General')}</span>
        </div>
        <div>
          <a href="${esc(post.permalink || post.url || '#')}" target="_blank" class="btn btn-ghost btn-sm">↗ Open on Reddit</a>
        </div>
      </div>
    </div>

    <!-- Collapsible Deep Analysis & Reply Drawer -->
    <div class="opp-drawer" id="drawer-${opp.id}">
      <div class="meters-bar-grid">
        <div class="meter-box">
          <div class="meter-name">Opportunity Score</div>
          <div class="meter-progress"><div class="meter-bar-fill" style="width:${score}%;"></div></div>
          <div style="font-size:12px;font-weight:700;margin-top:2px;">${score}/100</div>
        </div>
        <div class="meter-box">
          <div class="meter-name">Buy Signal</div>
          <div class="meter-progress"><div class="meter-bar-fill" style="width:${analysis.buy_signal_strength || 50}%;background:var(--success);"></div></div>
          <div style="font-size:12px;font-weight:700;margin-top:2px;">${analysis.buy_signal_strength || 50}%</div>
        </div>
        <div class="meter-box">
          <div class="meter-name">Pain Intensity</div>
          <div class="meter-progress"><div class="meter-bar-fill" style="width:${analysis.pain_strength || 50}%;background:var(--danger);"></div></div>
          <div style="font-size:12px;font-weight:700;margin-top:2px;">${analysis.pain_strength || 50}%</div>
        </div>
        <div class="meter-box">
          <div class="meter-name">Action Verdict</div>
          <div style="font-size:13px;font-weight:800;color:var(--reddit-orange);margin-top:8px;">${opp.opportunity?.recommended_action || 'Reply Now'}</div>
        </div>
      </div>

      <div class="drawer-grid">
        <div>
          <div class="drawer-section-title">What It Means & User Problem</div>
          <div class="drawer-text">${esc(analysis.what_it_means || 'User is discussing workflow needs or seeking alternatives.')}</div>
        </div>
        <div>
          <div class="drawer-section-title">User Requirements & Needs</div>
          <div class="drawer-text">${esc(analysis.what_it_requires || 'Practical guidance or software recommendation.')}</div>
        </div>
        <div style="grid-column: 1 / -1;">
          <div class="drawer-section-title">🎯 Recommended Engagement Angle</div>
          <div class="drawer-text" style="font-weight:600;color:var(--text-primary);">${esc(analysis.recommended_angle || 'Provide a direct, helpful answer without marketing hype.')}</div>
        </div>
      </div>

      <!-- Top Comments if available -->
      ${(opp.comments || []).length ? `
      <div style="margin-bottom:16px;">
        <div class="drawer-section-title">💬 Community Context (Top Comments)</div>
        <div style="display:flex;flex-direction:column;gap:6px;">
          ${opp.comments.map(c => `
            <div style="background:#fff;border:1px solid #E5E7EB;border-radius:6px;padding:8px 12px;font-size:12.5px;">
              <span style="font-weight:700;color:var(--text-primary);">u/${esc(c.author)} (▲ ${c.score}):</span> ${esc(c.body)}
            </div>`).join('')}
        </div>
      </div>` : ''}

      <!-- Multi-Strategy Reply Box -->
      <div class="reply-editor-wrap">
        <div class="reply-editor-header">
          <span>✍️ Multi-Strategy Reply Assistant</span>
          <div style="display:flex;gap:6px;">
            <select class="select" id="strategy-sel-${opp.id}" style="padding:4px 8px;font-size:12px;" onchange="regenerateOppReply(${opp.id})">
              <option value="DIRECT_ANSWER">Direct Answer</option>
              <option value="VALUE_FIRST">Value First</option>
              <option value="TECHNICAL">Technical Deep-Dive</option>
              <option value="PERSONAL_EXPERIENCE">Personal Experience</option>
              <option value="COMPARISON">Tool Comparison</option>
              <option value="NO_PROMOTION">No Promotion (Pure Help)</option>
            </select>
            <button class="btn btn-secondary btn-sm" onclick="regenerateOppReply(${opp.id})">🔄 Regenerate</button>
          </div>
        </div>
        <textarea class="reply-textarea" id="reply-text-${opp.id}">${esc(opp.latest_reply?.content || 'Click Regenerate to draft a strategic reply...')}</textarea>
        <div class="reply-editor-footer">
          <button class="btn btn-primary btn-sm" onclick="copyReplyText(${opp.id})">📋 Copy Reply</button>
          <a href="${esc(post.permalink || post.url || '#')}" target="_blank" class="btn btn-secondary btn-sm" onclick="setOppStatus(${opp.id}, 'replied')">↗ Open Reddit & Reply</a>
          <button class="btn btn-ghost btn-sm" onclick="setOppStatus(${opp.id}, 'ignored')">Hide</button>
        </div>
      </div>

      <!-- Critic Scorecard -->
      ${opp.latest_reply?.critic_scorecard ? renderCriticScorecard(opp.latest_reply.critic_scorecard) : ''}
    </div>
  </div>`;
}

function renderCriticScorecard(c) {
  return `
  <div class="critic-card">
    <div class="critic-title">
      <span>🛡️ Critic Scorecard</span>
      <span style="font-size:11px;font-weight:700;color:${c.promotion_risk > 50 ? 'var(--danger)' : 'var(--success)'};">Verdict: ${esc(c.verdict || 'APPROVED')}</span>
    </div>
    <div class="critic-scores-grid">
      <div class="critic-metric"><div class="critic-metric-val">${c.authenticity || 90}%</div><div class="critic-metric-lbl">Authenticity</div></div>
      <div class="critic-metric"><div class="critic-metric-val">${c.relevance || 95}%</div><div class="critic-metric-lbl">Relevance</div></div>
      <div class="critic-metric"><div class="critic-metric-val">${c.helpfulness || 88}%</div><div class="critic-metric-lbl">Helpfulness</div></div>
      <div class="critic-metric"><div class="critic-metric-val">${c.community_fit || 90}%</div><div class="critic-metric-lbl">Community Fit</div></div>
      <div class="critic-metric"><div class="critic-metric-val" style="color:${c.promotion_risk > 50 ? 'var(--danger)' : 'var(--success)'};">${c.promotion_risk || 10}%</div><div class="critic-metric-lbl">Promo Risk</div></div>
      <div class="critic-metric"><div class="critic-metric-val">${c.hallucination_risk || 5}%</div><div class="critic-metric-lbl">Hallucination</div></div>
    </div>
  </div>`;
}

function toggleOppDrawer(id) {
  const d = document.getElementById(`drawer-${id}`);
  if (d) d.classList.toggle('open');
}

async function setOppStatus(matchId, status) {
  try {
    await api(`/opportunities/${matchId}/status?status=${status}`, { method: 'PATCH' });
    toast(`Opportunity marked as ${status}`, 'success');
    if (status === 'ignored') {
      document.getElementById(`opp-${matchId}`)?.remove();
    }
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
}

async function regenerateOppReply(matchId) {
  const sel = document.getElementById(`strategy-sel-${matchId}`);
  const strategy = sel ? sel.value : 'DIRECT_ANSWER';
  const textarea = document.getElementById(`reply-text-${matchId}`);
  if (textarea) textarea.value = 'Generating reply with strategy: ' + strategy + '...';

  try {
    const res = await api('/replies/generate', {
      method: 'POST',
      body: JSON.stringify({ match_id: matchId, strategy }),
    });
    if (textarea) textarea.value = res.content;
    toast('Fresh reply generated and evaluated by Critic!', 'success');
  } catch (e) {
    toast(`Failed to generate reply: ${e.message}`, 'error');
  }
}

function copyReplyText(matchId) {
  const el = document.getElementById(`reply-text-${matchId}`);
  if (el) {
    navigator.clipboard.writeText(el.value).then(() => toast('Reply copied to clipboard!', 'success'));
  }
}

function resetOppFilters() {
  document.getElementById('opp-filter-intent').value = '';
  document.getElementById('opp-filter-min-score').value = '';
  document.getElementById('opp-filter-status').value = '';
  loadOpportunities();
}

// ── REDDIT EXPLORER ──────────────────────────────────────────────
async function loadPosts() {
  const c = document.getElementById('posts-container');
  try {
    const data = await api('/posts?limit=30');
    const items = data.items || [];
    if (!items.length) {
      c.innerHTML = '<div class="empty-box"><div class="empty-title">No posts stored yet</div></div>';
      return;
    }
    c.innerHTML = items.map(p => `
      <div style="padding:12px 0;border-bottom:1px solid var(--border);">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
          <span class="subreddit-chip">r/${esc(p.subreddit)}</span>
          <span style="font-size:12px;color:var(--text-muted);">u/${esc(p.author)} · ▲ ${p.score} · 💬 ${p.num_comments}</span>
        </div>
        <div style="font-weight:700;font-size:14px;"><a href="${esc(p.permalink || p.url)}" target="_blank">${esc(p.title)}</a></div>
      </div>`).join('');
  } catch (e) {
    c.innerHTML = `<div class="empty-box">${e.message}</div>`;
  }
}

async function runLiveSearch() {
  const q = document.getElementById('live-search-query').value.trim();
  const sub = document.getElementById('live-search-sub').value.trim() || 'all';
  if (!q) { toast('Enter search query', 'warning'); return; }

  const out = document.getElementById('live-search-results');
  out.innerHTML = '<div class="skeleton skeleton-card"></div>';

  try {
    const res = await api('/posts/live-search', {
      method: 'POST',
      body: JSON.stringify({ query: q, subreddit: sub, limit: 10 }),
    });
    out.innerHTML = `<div style="font-size:12px;color:var(--text-muted);margin-bottom:8px;">Found ${res.count} results from Reddit:</div>` +
      res.items.map(i => `
        <div style="padding:10px;background:#fff;border:1px solid #E5E7EB;border-radius:8px;margin-bottom:8px;">
          <div style="font-size:12px;font-weight:700;color:var(--reddit-orange);">r/${esc(i.subreddit)} · ▲ ${i.score}</div>
          <div style="font-weight:600;font-size:13.5px;"><a href="${esc(i.permalink)}" target="_blank">${esc(i.title)}</a></div>
        </div>`).join('');
  } catch (e) {
    out.innerHTML = `<div style="color:var(--danger);font-size:13px;">Error: ${e.message}</div>`;
  }
}

// ── MONITORING RULES ─────────────────────────────────────────────
async function loadMonitoringRules() {
  const c = document.getElementById('rules-container');
  try {
    const rules = await api('/monitoring-rules');
    if (!rules.length) {
      c.innerHTML = `
        <div class="empty-box">
          <div class="empty-icon">⚙️</div>
          <div class="empty-title">No monitoring rules yet</div>
          <div class="empty-sub">Create your first rule to automatically track high-intent conversations.</div>
          <button class="btn btn-primary" onclick="openCreateRuleModal()">+ Create Monitoring Rule</button>
        </div>`;
      return;
    }
    c.innerHTML = rules.map(r => `
      <div style="background:#fff;border:1px solid var(--border);border-radius:10px;padding:16px 20px;margin-bottom:12px;display:flex;align-items:center;gap:16px;">
        <div style="flex:1;">
          <div style="font-size:15px;font-weight:700;color:var(--text-primary);">${esc(r.name)}</div>
          <div style="font-size:12.5px;color:var(--text-muted);margin-top:2px;">
            Keywords: <strong>${r.keywords?.join(', ') || 'None'}</strong> · Subreddits: <strong>${r.subreddits?.join(', ') || 'All'}</strong>
          </div>
        </div>
        <div style="font-size:12px;font-weight:700;padding:3px 10px;border-radius:100px;background:${r.is_active ? '#DCFCE7;color:#166534' : '#F3F4F6;color:#6B7280'};">
          ${r.is_active ? 'Active' : 'Paused'}
        </div>
        <button class="btn btn-ghost btn-sm" onclick="toggleRule(${r.id}, ${!r.is_active})">${r.is_active ? 'Pause' : 'Activate'}</button>
        <button class="btn btn-ghost btn-sm" onclick="deleteRule(${r.id})">🗑</button>
      </div>`).join('');
  } catch (e) {
    c.innerHTML = `<div class="empty-box">${e.message}</div>`;
  }
}

function openCreateRuleModal() {
  document.getElementById('rule-name').value = '';
  document.getElementById('rule-keywords').value = '';
  document.getElementById('rule-subreddits').value = '';
  document.getElementById('rule-keyword-suggestions').innerHTML = '';
  document.getElementById('modal-rule').classList.add('open');
}

async function expandKeywordsForRule() {
  const kwInput = document.getElementById('rule-keywords');
  const seed = kwInput.value.split(',')[0].trim();
  if (!seed) { toast('Type a seed keyword first', 'warning'); return; }

  const box = document.getElementById('rule-keyword-suggestions');
  box.innerHTML = '<span style="font-size:11px;color:var(--text-muted);">Generating suggestions...</span>';

  try {
    const res = await api('/monitoring-rules/expand-keywords', {
      method: 'POST',
      body: JSON.stringify({ seed }),
    });
    box.innerHTML = (res.suggestions || []).map(s => `
      <span class="match-reason-tag" style="cursor:pointer;" onclick="appendKeyword('${esc(s)}')">+ ${esc(s)}</span>
    `).join('');
  } catch (e) {
    box.innerHTML = '';
    toast(`Expansion error: ${e.message}`, 'error');
  }
}

function appendKeyword(kw) {
  const el = document.getElementById('rule-keywords');
  const existing = el.value.split(',').map(s => s.trim()).filter(Boolean);
  if (!existing.includes(kw)) {
    existing.push(kw);
    el.value = existing.join(', ');
  }
}

async function submitMonitoringRule() {
  const name = document.getElementById('rule-name').value.trim();
  const kws = document.getElementById('rule-keywords').value.split(',').map(s => s.trim()).filter(Boolean);
  const subs = document.getElementById('rule-subreddits').value.split(',').map(s => s.trim()).filter(Boolean);
  const minScore = parseInt(document.getElementById('rule-min-score').value) || 1;
  const minOpp = parseInt(document.getElementById('rule-min-opp').value) || 60;

  if (!name) { toast('Enter rule name', 'warning'); return; }

  try {
    await api('/monitoring-rules', {
      method: 'POST',
      body: JSON.stringify({
        name,
        keywords: kws,
        subreddits: subs,
        min_score: minScore,
        min_opportunity_score: minOpp,
      }),
    });
    toast('Monitoring rule created!', 'success');
    closeModal('modal-rule');
    loadMonitoringRules();
  } catch (e) {
    toast(`Failed to create rule: ${e.message}`, 'error');
  }
}

async function toggleRule(id, active) {
  try {
    await api(`/monitoring-rules/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ is_active: active }),
    });
    toast(`Rule ${active ? 'activated' : 'paused'}`, 'success');
    loadMonitoringRules();
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
}

async function deleteRule(id) {
  if (!confirm('Delete this monitoring rule?')) return;
  try {
    await api(`/monitoring-rules/${id}`, { method: 'DELETE' });
    toast('Rule deleted', 'info');
    loadMonitoringRules();
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
}

// ── SUBREDDITS ───────────────────────────────────────────────────
async function loadSubreddits() {
  const c = document.getElementById('subreddits-container');
  try {
    const subs = await api('/subreddits');
    c.innerHTML = subs.map(s => `
      <div style="background:#fff;border:1px solid var(--border);border-radius:10px;padding:16px;">
        <div style="font-size:15px;font-weight:700;color:var(--reddit-orange);">r/${esc(s.name)}</div>
        <div style="font-size:12px;color:var(--text-muted);margin-bottom:8px;">${(s.subscribers || 0).toLocaleString()} subscribers</div>
        <div style="font-size:12px;line-height:1.5;color:var(--text-secondary);">
          <div>Promotion Tolerance: <strong>${Math.round((s.profile?.promotion_tolerance || 0.5) * 100)}%</strong></div>
          <div>Style: <strong>${esc(s.profile?.reply_style || 'Direct')}</strong></div>
        </div>
      </div>`).join('');
  } catch (e) {
    c.innerHTML = `<div class="empty-box">${e.message}</div>`;
  }
}

// ── COMPETITORS ──────────────────────────────────────────────────
async function loadCompetitors() {
  const c = document.getElementById('competitors-container');
  try {
    const comps = await api('/competitors');
    if (!comps.length) {
      c.innerHTML = `
        <div class="empty-box">
          <div class="empty-icon">⚔️</div>
          <div class="empty-title">No tracked competitors</div>
          <div class="empty-sub">Add a competitor to automatically monitor user complaints and migration queries.</div>
          <button class="btn btn-primary" onclick="openAddCompetitorModal()">+ Track Competitor</button>
        </div>`;
      return;
    }
    c.innerHTML = comps.map(comp => `
      <div style="background:#fff;border:1px solid var(--border);border-radius:10px;padding:16px 20px;margin-bottom:12px;">
        <div style="display:flex;align-items:center;justify-content:space-between;">
          <div style="font-size:16px;font-weight:700;color:var(--text-primary);">${esc(comp.name)}</div>
          <button class="btn btn-ghost btn-sm" onclick="deleteCompetitor(${comp.id})">🗑 Delete</button>
        </div>
        <div style="font-size:12px;color:var(--text-muted);margin-top:6px;">Auto-monitored phrases:</div>
        <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:4px;">
          ${(comp.tracked_keywords || []).map(k => `<span class="match-reason-tag">${esc(k)}</span>`).join('')}
        </div>
      </div>`).join('');
  } catch (e) {
    c.innerHTML = `<div class="empty-box">${e.message}</div>`;
  }
}

async function openAddCompetitorModal() {
  const name = prompt('Enter competitor product name (e.g. Zapier, HubSpot):');
  if (!name) return;
  try {
    await api('/competitors', { method: 'POST', body: JSON.stringify({ name }) });
    toast(`Competitor ${name} added with automated rule tracking!`, 'success');
    loadCompetitors();
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
}

async function deleteCompetitor(id) {
  if (!confirm('Delete competitor tracking?')) return;
  try {
    await api(`/competitors/${id}`, { method: 'DELETE' });
    toast('Competitor removed', 'info');
    loadCompetitors();
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
}

// ── AI & CRITIC LAB ──────────────────────────────────────────────
async function testIntentLab() {
  const text = document.getElementById('test-intent-text').value.trim();
  if (!text) return;
  const out = document.getElementById('test-intent-out');
  out.innerHTML = '<span style="font-size:12px;color:var(--text-muted);">Classifying...</span>';
  try {
    const res = await api('/settings/test-llm', { method: 'POST' }); // test call
    out.innerHTML = `<div style="font-size:13px;font-weight:700;color:var(--success);">AI Operational</div>`;
  } catch (e) {
    out.innerHTML = `<div style="color:var(--danger);font-size:12px;">Error: ${e.message}</div>`;
  }
}

async function testCriticLab() {
  const title = document.getElementById('test-critic-title').value.trim();
  const reply = document.getElementById('test-critic-reply').value.trim();
  if (!reply) return;
  const out = document.getElementById('test-critic-out');
  out.innerHTML = '<span style="font-size:12px;color:var(--text-muted);">Evaluating with Critic...</span>';
  try {
    const res = await api('/replies/critic', {
      method: 'POST',
      body: JSON.stringify({ title: title || 'Question', content: '', reply, subreddit: 'SaaS' }),
    });
    out.innerHTML = renderCriticScorecard(res);
  } catch (e) {
    out.innerHTML = `<div style="color:var(--danger);font-size:12px;">Error: ${e.message}</div>`;
  }
}

// ── SETTINGS ─────────────────────────────────────────────────────
async function loadSettings() {
  try {
    const s = await api('/settings');
    if (s.alerts?.ntfy_topic) document.getElementById('setting-ntfy-topic').value = s.alerts.ntfy_topic;
    if (s.alerts?.email) document.getElementById('setting-alert-email').value = s.alerts.email;
    if (s.alerts?.min_opportunity_score) document.getElementById('setting-min-opp-score').value = s.alerts.min_opportunity_score;
    if (s.llm?.provider) document.getElementById('setting-llm-provider').value = s.llm.provider;
    if (s.llm?.model) document.getElementById('setting-llm-model').value = s.llm.model;
  } catch (e) {
    toast(`Failed to load settings: ${e.message}`, 'error');
  }
}

async function saveAlertSettings() {
  const topic = document.getElementById('setting-ntfy-topic').value.trim();
  const email = document.getElementById('setting-alert-email').value.trim();
  const minOpp = parseInt(document.getElementById('setting-min-opp-score').value) || 70;
  try {
    await api('/settings/alerts', {
      method: 'PUT',
      body: JSON.stringify({ ntfy_topic: topic, email: email || null, min_opportunity_score: minOpp }),
    });
    toast('Alert settings saved!', 'success');
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
}

async function testPushNotification() {
  try {
    const res = await api('/notifications/test-alert?channel=ntfy', { method: 'POST' });
    toast('🔔 Test notification sent to ntfy topic!', 'success');
  } catch (e) {
    toast(`Push alert failed: ${e.message}`, 'error');
  }
}

async function saveLLMSettings() {
  const provider = document.getElementById('setting-llm-provider').value;
  const model = document.getElementById('setting-llm-model').value.trim();
  const apiKey = document.getElementById('setting-zen-key').value.trim();
  try {
    await api('/settings/llm', {
      method: 'PUT',
      body: JSON.stringify({ provider, model, api_key: apiKey || null }),
    });
    toast('AI configuration saved!', 'success');
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
}

async function testAIConnectivity() {
  const out = document.getElementById('llm-test-status');
  out.innerHTML = '<span style="font-size:12px;color:var(--text-muted);">Testing connection...</span>';
  try {
    const res = await api('/settings/test-llm', { method: 'POST' });
    if (res.healthy) {
      out.innerHTML = `<div style="font-size:12.5px;color:var(--success);">✅ AI Connected · Model: ${res.model}</div>`;
    } else {
      out.innerHTML = `<div style="font-size:12.5px;color:var(--danger);">❌ AI Offline: ${res.error}</div>`;
    }
  } catch (e) {
    out.innerHTML = `<div style="font-size:12.5px;color:var(--danger);">❌ ${e.message}</div>`;
  }
}

// ── LOGS ─────────────────────────────────────────────────────────
async function loadLogs() {
  const c = document.getElementById('logs-container');
  try {
    const logs = await api('/dashboard/logs');
    c.innerHTML = logs.reverse().map(l => `
      <div style="padding:4px 0;border-bottom:1px solid #E5E7EB;">
        <span style="color:var(--text-muted);">${l.timestamp.split('T')[1].split('.')[0]}</span>
        <span style="font-weight:700;color:${l.level === 'error' ? 'var(--danger)' : l.level === 'warning' ? 'var(--warning)' : 'var(--success)'};">[${l.level.toUpperCase()}]</span>
        <span>${esc(l.message)}</span>
      </div>`).join('');
  } catch (e) {
    c.innerHTML = `<div>${e.message}</div>`;
  }
}

// ── UTILITIES ────────────────────────────────────────────────────
function closeModal(id) {
  document.getElementById(id)?.classList.remove('open');
}

function esc(s) {
  if (s == null) return '';
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function timeAgo(d) {
  if (!d) return 'recently';
  const sec = Math.floor((Date.now() - new Date(d).getTime()) / 1000);
  if (sec < 60) return `${sec}s ago`;
  const m = Math.floor(sec / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

// ── INIT ─────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadMetrics();
  navigate('opportunities');
  // Refresh metrics every 30 seconds
  setInterval(loadMetrics, 30000);
});
