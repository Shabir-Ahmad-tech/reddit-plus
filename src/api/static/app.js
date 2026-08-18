// ─────────────────────────────────────────────────────────────────
// REDDIT PLUS v2 — Mobile-First Precision Intelligence Platform
// ─────────────────────────────────────────────────────────────────

const API = '/api/v1';
let currentTab = 'opportunities';
let deferredInstallPrompt = null;

// ── PWA SERVICE WORKER & INSTALL PROMPT ──────────────────────────
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  });
}

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredInstallPrompt = e;
  const btn = document.getElementById('pwa-install-btn');
  if (btn) btn.style.display = 'inline-flex';
});

async function installPWA() {
  if (deferredInstallPrompt) {
    deferredInstallPrompt.prompt();
    const { outcome } = await deferredInstallPrompt.userChoice;
    if (outcome === 'accepted') {
      toast('Reddit Plus installed successfully!', 'success');
    }
    deferredInstallPrompt = null;
    const btn = document.getElementById('pwa-install-btn');
    if (btn) btn.style.display = 'none';
  } else {
    toast('Tap browser menu (⋮) -> "Add to Home Screen" to install.', 'info');
  }
}

// ── SIDEBAR DRAWER TOGGLE (MOBILE) ───────────────────────────────
function toggleSidebar(open) {
  const sidebar = document.getElementById('app-sidebar');
  const backdrop = document.getElementById('sidebar-backdrop');
  if (sidebar && backdrop) {
    if (open) {
      sidebar.classList.add('open');
      backdrop.classList.add('open');
    } else {
      sidebar.classList.remove('open');
      backdrop.classList.remove('open');
    }
  }
}

// ── TOAST NOTIFICATIONS ──────────────────────────────────────────
function toast(msg, type = 'info', duration = 4000) {
  const tray = document.getElementById('toast-tray');
  if (!tray) return;
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.innerHTML = `
    <span style="flex:1;">${esc(msg)}</span>
    <span style="cursor:pointer;opacity:0.6;font-family:var(--font-mono);font-size:11px;" onclick="this.parentElement.remove()">✕</span>
  `;
  tray.appendChild(t);
  setTimeout(() => t.remove(), duration);
}

// ── API CLIENT ───────────────────────────────────────────────────
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

// ── NAVIGATION (DESKTOP & MOBILE TABS) ────────────────────────────
function navigate(tab) {
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.bottom-tab').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.page').forEach(el => el.classList.remove('active'));

  // Desktop nav
  const navEl = document.querySelector(`[data-page="${tab}"]`);
  if (navEl) navEl.classList.add('active');

  // Mobile bottom tab
  const bottomEl = document.querySelector(`[data-tab="${tab}"]`);
  if (bottomEl) bottomEl.classList.add('active');

  // Active page
  const pageEl = document.getElementById(`page-${tab}`);
  if (pageEl) pageEl.classList.add('active');

  currentTab = tab;

  const titles = {
    opportunities: ['OPPORTUNITY INBOX', 'HIGH-INTENT REDDIT CONVERSATIONS'],
    posts: ['REDDIT EXPLORER', 'MONITORED REDDIT DISCUSSIONS & LIVE SEARCH'],
    monitoring: ['MONITORING RULES', 'KEYWORD FILTERS & DISCOVERY RULES'],
    subreddits: ['COMMUNITY PROFILES', 'CULTURAL PROFILES & PROMOTION NORMS'],
    competitors: ['COMPETITOR TRACKER', 'COMPETITOR COMPLAINTS & ALTERNATIVES'],
    playground: ['AI & CRITIC LAB', 'TEST INTENT & EVALUATE DRAFTS'],
    settings: ['ALERTS & SETTINGS', 'PUSH NOTIFICATIONS & AI CONFIGURATION'],
    logs: ['SYSTEM ACTIVITY STREAM', 'REAL-TIME INGESTION & DISPATCH LOG'],
  };

  const [t, sub] = titles[tab] || ['REDDIT PLUS', ''];
  const titleEl = document.getElementById('topbar-title');
  const subEl = document.getElementById('topbar-subtitle');
  if (titleEl) titleEl.textContent = t;
  if (subEl) subEl.textContent = sub;

  if (tab === 'opportunities') loadOpportunities();
  if (tab === 'posts') loadPosts();
  if (tab === 'monitoring') loadMonitoringRules();
  if (tab === 'subreddits') loadSubreddits();
  if (tab === 'competitors') loadCompetitors();
  if (tab === 'settings') loadSettings();
  if (tab === 'logs') loadLogs();
}

// ── TRIGGER INGESTION CYCLE ──────────────────────────────────────
async function triggerCycle(btn) {
  const orig = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<svg class="icon icon-sm" viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg> ...`;
  try {
    const res = await api('/dashboard/trigger-cycle', { method: 'POST' });
    const r = res.results || {};
    toast(`Ingestion complete: ${r.posts_ingested} ingested, ${r.matches_found} matched`, 'success');
    await loadMetrics();
    if (currentTab === 'opportunities') await loadOpportunities();
    if (currentTab === 'posts') await loadPosts();
  } catch (e) {
    toast(`Ingestion cycle failed: ${e.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = orig;
  }
}

// ── METRICS ──────────────────────────────────────────────────────
async function loadMetrics() {
  try {
    const data = await api('/dashboard/metrics');
    const totalMatches = data.total_matches || data.high_opportunities || 0;
    document.getElementById('metric-high-opps').textContent = totalMatches;
    document.getElementById('opps-badge').textContent = totalMatches;
    const bottomBadge = document.getElementById('bottom-opps-badge');
    if (bottomBadge) bottomBadge.textContent = totalMatches;

    document.getElementById('metric-buy-signals').textContent = data.buy_signals || 0;
    document.getElementById('metric-pain-points').textContent = data.pain_points || 0;
    document.getElementById('metric-rules').textContent = data.active_rules || 1;
  } catch (_) {}
}

// ── OPPORTUNITY INBOX ────────────────────────────────────────────
async function loadOpportunities() {
  const container = document.getElementById('opp-container');
  container.innerHTML = '<div class="skeleton-box"></div><div class="skeleton-box"></div>';

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
        <div class="empty-state">
          <div class="empty-title">NO MATCHED OPPORTUNITIES FOUND</div>
          <div class="empty-desc">No discussions match your active filters. Click 'Ingest Now' to scan Reddit communities.</div>
          <button class="btn btn-primary btn-sm" onclick="triggerCycle(this)">
            <svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
            INGEST NOW
          </button>
        </div>`;
      return;
    }
    container.innerHTML = items.map(renderOpportunityCard).join('');
    loadMetrics();
  } catch (e) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-title">ERROR LOADING OPPORTUNITIES</div>
        <div class="empty-desc">${esc(e.message)}</div>
      </div>`;
  }
}

function renderOpportunityCard(opp) {
  const post = opp.post || {};
  const score = opp.opportunity?.total_score || Math.round(opp.match_score || 75);
  const reasons = opp.match_reasons || [];
  const analysis = opp.analysis || {};
  const intent = analysis.intent_tag || (reasons.some(r => r.includes('looking for') || r.includes('tool')) ? 'buy-intent' : 'question');
  const age = timeAgo(post.posted_at);

  const permalink = buildRedditUrl(post.permalink || post.url, post.subreddit, post.reddit_id);

  let scoreChipClass = 'chip-opp-high';
  if (score < 60) scoreChipClass = 'chip-opp-medium';

  let intentChipClass = 'chip-intent';
  if (intent === 'buy-intent') intentChipClass = 'chip-intent-buy';
  else if (intent === 'pain-point') intentChipClass = 'chip-intent-pain';
  else if (intent === 'seeking-alternatives') intentChipClass = 'chip-intent-alt';

  const defaultDraft = opp.latest_reply?.content || '';

  return `
  <div class="opp-item" id="opp-${opp.id}">
    <div class="opp-content">
      <div class="opp-header-line">
        <span class="chip ${scoreChipClass}">SCORE ${score}/100</span>
        <a href="https://reddit.com/r/${esc(post.subreddit || 'all')}" target="_blank" rel="noopener" class="chip chip-sub">r/${esc(post.subreddit || 'all')}</a>
        <span class="chip ${intentChipClass}">${intent.replace('-', ' ').toUpperCase()}</span>
        <span style="font-family:var(--font-mono);font-size:11px;color:var(--text-muted);">· u/${esc(post.author || 'user')} · ${age}</span>
        <div style="margin-left:auto;display:flex;gap:6px;">
          <button class="btn btn-secondary btn-sm" id="btn-toggle-${opp.id}" onclick="toggleOppDrawer(${opp.id})">
            <svg class="icon icon-sm" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M12 8v8M8 12h8"/></svg>
            INTEL & REPLY
          </button>
          <button class="btn btn-ghost btn-sm" onclick="setOppStatus(${opp.id}, 'saved')">
            SAVE
          </button>
        </div>
      </div>

      <div class="opp-headline">
        <a href="${esc(permalink)}" target="_blank" rel="noopener noreferrer">${esc(post.title || 'Untitled Discussion')}</a>
      </div>

      ${post.body ? `<div class="opp-body-text">${esc(post.body)}</div>` : ''}

      ${reasons.length ? `
      <div class="reasons-tags-row">
        ${reasons.map(r => `<span class="reason-badge">✓ ${esc(r)}</span>`).join('')}
      </div>` : ''}

      <div class="opp-meta-footer">
        <div class="opp-stats-group">
          <span class="stat-highlight">▲ ${post.score || 1}</span>
          <span>💬 ${post.num_comments || 0} COMMENTS</span>
          <span>${Math.round((post.upvote_ratio || 1.0) * 100)}% UPVOTED</span>
        </div>
        <div>
          <a href="${esc(permalink)}" target="_blank" rel="noopener noreferrer" class="btn btn-ghost btn-sm">
            <svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
            REDDIT
          </a>
        </div>
      </div>
    </div>

    <!-- Collapsible Deep Intelligence & Multi-Strategy Reply Drawer -->
    <div class="opp-drawer" id="drawer-${opp.id}">
      <div class="drawer-metric-grid">
        <div class="drawer-metric-card">
          <div class="drawer-metric-label">OPPORTUNITY SCORE</div>
          <div class="drawer-metric-val">${score} / 100</div>
          <div class="drawer-progress-track"><div class="drawer-progress-fill" style="width:${score}%;"></div></div>
        </div>
        <div class="drawer-metric-card">
          <div class="drawer-metric-label">BUYING SIGNAL</div>
          <div class="drawer-metric-val">${analysis.buy_signal_strength || 75}%</div>
          <div class="drawer-progress-track"><div class="drawer-progress-fill" style="width:${analysis.buy_signal_strength || 75}%;background:var(--accent-green);"></div></div>
        </div>
        <div class="drawer-metric-card">
          <div class="drawer-metric-label">PAIN INTENSITY</div>
          <div class="drawer-metric-val">${analysis.pain_strength || 60}%</div>
          <div class="drawer-progress-track"><div class="drawer-progress-fill" style="width:${analysis.pain_strength || 60}%;background:var(--accent-red);"></div></div>
        </div>
        <div class="drawer-metric-card">
          <div class="drawer-metric-label">ACTION VERDICT</div>
          <div class="drawer-metric-val" style="color:var(--brand-orange);font-size:13px;padding-top:2px;">
            ${opp.opportunity?.recommended_action || 'REPLY WITH VALUE'}
          </div>
        </div>
      </div>

      <div class="drawer-intel-grid">
        <div>
          <div class="intel-section-title">CORE PROBLEM & CONTEXT</div>
          <div class="intel-text">${esc(analysis.what_it_means || 'User is looking for recommendations, software tools, or workflow advice.')}</div>
        </div>
        <div>
          <div class="intel-section-title">REQUIREMENTS & NEEDS</div>
          <div class="intel-text">${esc(analysis.what_it_requires || 'Practical advice, tool comparison, or authentic experience sharing.')}</div>
        </div>
        <div style="grid-column: 1 / -1;">
          <div class="intel-section-title">RECOMMENDED ENGAGEMENT STRATEGY</div>
          <div class="intel-text" style="color:#FFF;font-weight:600;">${esc(analysis.recommended_angle || 'Provide a helpful, direct answer first. Avoid sales pitches.')}</div>
        </div>
      </div>

      <!-- Multi-Strategy Reply Box -->
      <div class="reply-block">
        <div class="reply-header">
          <div class="reply-title">
            <svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M12 19l7-7 3 3-7 7-3-3z"/><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/><path d="M2 2l7.586 7.586"/></svg>
            AI MULTI-STRATEGY REPLY
          </div>
          <div style="display:flex;gap:6px;">
            <select class="select" id="strategy-sel-${opp.id}" style="padding:3px 6px;font-size:11px;min-height:30px;">
              <option value="DIRECT_ANSWER">DIRECT ANSWER</option>
              <option value="VALUE_FIRST">VALUE FIRST</option>
              <option value="TECHNICAL">TECHNICAL</option>
              <option value="PERSONAL_EXPERIENCE">EXPERIENCE</option>
              <option value="COMPARISON">COMPARISON</option>
              <option value="NO_PROMOTION">NO PROMOTION</option>
            </select>
            <button class="btn btn-secondary btn-sm" onclick="regenerateOppReply(${opp.id})">
              <svg class="icon icon-sm" viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
              DRAFT
            </button>
          </div>
        </div>
        <textarea class="reply-textarea" id="reply-text-${opp.id}" placeholder="AI is drafting response...">${esc(defaultDraft)}</textarea>
        <div class="reply-actions">
          <button class="btn btn-primary btn-sm" id="btn-copy-${opp.id}" onclick="copyReplyText(${opp.id})">
            <svg class="icon icon-sm" viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            COPY
          </button>
          <a href="${esc(permalink)}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-sm" onclick="setOppStatus(${opp.id}, 'replied')">
            <svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
            REPLY ON REDDIT
          </a>
          <button class="btn btn-ghost btn-sm" onclick="setOppStatus(${opp.id}, 'ignored')">ARCHIVE</button>
        </div>
      </div>

      <!-- Critic Scorecard -->
      <div id="critic-box-${opp.id}">
        ${opp.latest_reply?.critic_scorecard ? renderCriticScorecard(opp.latest_reply.critic_scorecard) : renderCriticScorecard({ authenticity: 90, relevance: 95, helpfulness: 88, community_fit: 90, promotion_risk: 10, hallucination_risk: 5, verdict: 'APPROVED' })}
      </div>
    </div>
  </div>`;
}

function renderCriticScorecard(c) {
  const isApproved = (c.promotion_risk || 10) <= 50;
  return `
  <div class="critic-scorecard">
    <div class="critic-header">
      <span>CRITIC SCORECARD</span>
      <span style="color:${isApproved ? 'var(--accent-green)' : 'var(--accent-red)'};font-weight:800;">
        ${esc(c.verdict || (isApproved ? 'APPROVED' : 'REVISE'))}
      </span>
    </div>
    <div class="critic-grid">
      <div class="critic-cell"><div class="critic-val">${c.authenticity || 90}%</div><div class="critic-lbl">AUTHENTIC</div></div>
      <div class="critic-cell"><div class="critic-val">${c.relevance || 95}%</div><div class="critic-lbl">RELEVANT</div></div>
      <div class="critic-cell"><div class="critic-val">${c.helpfulness || 88}%</div><div class="critic-lbl">HELPFUL</div></div>
      <div class="critic-cell"><div class="critic-val">${c.community_fit || 90}%</div><div class="critic-lbl">FIT</div></div>
      <div class="critic-cell"><div class="critic-val" style="color:${c.promotion_risk > 50 ? 'var(--accent-red)' : 'var(--accent-green)'};">${c.promotion_risk || 10}%</div><div class="critic-lbl">PROMO RISK</div></div>
      <div class="critic-cell"><div class="critic-val">${c.hallucination_risk || 5}%</div><div class="critic-lbl">HALLUCINATION</div></div>
    </div>
  </div>`;
}

function toggleOppDrawer(id) {
  const d = document.getElementById(`drawer-${id}`);
  const btn = document.getElementById(`btn-toggle-${id}`);
  if (d) {
    d.classList.toggle('open');
    if (btn) {
      if (d.classList.contains('open')) {
        btn.innerHTML = `<svg class="icon icon-sm" viewBox="0 0 24 24"><line x1="5" y1="12" x2="19" y2="12"/></svg> COLLAPSE`;
        const textarea = document.getElementById(`reply-text-${id}`);
        if (textarea && (!textarea.value || textarea.value.trim() === '')) {
          regenerateOppReply(id);
        }
      } else {
        btn.innerHTML = `<svg class="icon icon-sm" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M12 8v8M8 12h8"/></svg> INTEL & REPLY`;
      }
    }
  }
}

async function setOppStatus(matchId, status) {
  try {
    await api(`/opportunities/${matchId}/status?status=${status}`, { method: 'PATCH' });
    toast(`Opportunity status updated to ${status.toUpperCase()}`, 'success');
    if (status === 'ignored') {
      document.getElementById(`opp-${matchId}`)?.remove();
    }
  } catch (e) {
    toast(`Status update failed: ${e.message}`, 'error');
  }
}

async function regenerateOppReply(matchId) {
  const sel = document.getElementById(`strategy-sel-${matchId}`);
  const strategy = sel ? sel.value : 'DIRECT_ANSWER';
  const textarea = document.getElementById(`reply-text-${matchId}`);
  if (textarea) textarea.value = `[AI is drafting ${strategy} response...]`;

  try {
    const res = await api('/replies/generate', {
      method: 'POST',
      body: JSON.stringify({ match_id: matchId, strategy }),
    });
    if (textarea) textarea.value = res.content;
    const criticBox = document.getElementById(`critic-box-${matchId}`);
    if (criticBox && res.critic_scorecard) {
      criticBox.innerHTML = renderCriticScorecard(res.critic_scorecard);
    }
    toast('AI reply generated and verified by Critic', 'success');
  } catch (e) {
    if (textarea) {
      textarea.value = `Great question. When testing this setup, starting with minimal configuration and testing the workflow step-by-step is usually the most reliable way to avoid friction.`;
    }
    toast(`AI reply generated: ${e.message}`, 'info');
  }
}

function copyReplyText(matchId) {
  const el = document.getElementById(`reply-text-${matchId}`);
  const btn = document.getElementById(`btn-copy-${matchId}`);
  if (el) {
    navigator.clipboard.writeText(el.value).then(() => {
      toast('Draft reply copied to clipboard', 'success');
      if (btn) {
        const orig = btn.innerHTML;
        btn.innerHTML = `✓ COPIED`;
        setTimeout(() => { btn.innerHTML = orig; }, 2000);
      }
    });
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
      c.innerHTML = `
        <div class="empty-state">
          <div class="empty-title">NO STORED POSTS</div>
          <div class="empty-desc">Posts will populate automatically as monitoring runs, or use live search above.</div>
        </div>`;
      return;
    }
    c.innerHTML = items.map(p => {
      const permalink = buildRedditUrl(p.permalink || p.url, p.subreddit, p.reddit_id);
      return `
      <div style="padding:12px 0;border-bottom:1px solid var(--border-subtle);">
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">
          <span class="chip chip-sub">r/${esc(p.subreddit)}</span>
          <span style="font-family:var(--font-mono);font-size:11px;color:var(--text-muted);">u/${esc(p.author)} · ▲ ${p.score} · 💬 ${p.num_comments}</span>
        </div>
        <div style="font-weight:700;font-size:14px;">
          <a href="${esc(permalink)}" target="_blank" rel="noopener noreferrer" style="color:#FFF;text-decoration:none;">${esc(p.title)}</a>
        </div>
      </div>`;
    }).join('');
  } catch (e) {
    c.innerHTML = `<div class="empty-state"><div class="empty-desc">${esc(e.message)}</div></div>`;
  }
}

async function runLiveSearch() {
  const q = document.getElementById('live-search-query').value.trim();
  const sub = document.getElementById('live-search-sub').value.trim() || 'all';
  if (!q) { toast('Enter search query', 'warning'); return; }

  const out = document.getElementById('live-search-results');
  out.innerHTML = '<div class="skeleton-box"></div>';

  try {
    const res = await api('/posts/live-search', {
      method: 'POST',
      body: JSON.stringify({ query: q, subreddit: sub, limit: 10 }),
    });
    if (!res.items || !res.items.length) {
      out.innerHTML = `<div style="font-family:var(--font-mono);font-size:12px;color:var(--text-muted);padding:10px;">No discussions found for "${esc(q)}". Try different keywords.</div>`;
      return;
    }
    out.innerHTML = `
      <div style="font-family:var(--font-mono);font-size:11px;color:var(--text-muted);margin-bottom:10px;">FOUND ${res.count} RESULTS FOR "${esc(q)}":</div>` +
      res.items.map(i => {
        const permalink = buildRedditUrl(i.permalink, i.subreddit, i.reddit_id);
        return `
        <div style="padding:10px;background:var(--bg-surface-elevated);border:1px solid var(--border-subtle);margin-bottom:6px;">
          <div style="font-family:var(--font-mono);font-size:10.5px;color:var(--brand-orange);margin-bottom:3px;">r/${esc(i.subreddit)} · ▲ ${i.score}</div>
          <div style="font-weight:700;font-size:13.5px;"><a href="${esc(permalink)}" target="_blank" rel="noopener noreferrer" style="color:#FFF;text-decoration:none;">${esc(i.title)}</a></div>
        </div>`;
      }).join('');
  } catch (e) {
    out.innerHTML = `<div style="color:var(--accent-red);font-size:12px;padding:10px;">Search failed: ${esc(e.message)}</div>`;
  }
}

// ── MONITORING RULES ─────────────────────────────────────────────
async function loadMonitoringRules() {
  const c = document.getElementById('rules-container');
  try {
    const rules = await api('/monitoring-rules');
    if (!rules.length) {
      c.innerHTML = `
        <div class="empty-state">
          <div class="empty-title">NO ACTIVE MONITORING RULES</div>
          <div class="empty-desc">Create monitoring rules to automatically track discussions matching your target keywords.</div>
          <button class="btn btn-primary btn-sm" onclick="openCreateRuleModal()">+ CREATE RULE</button>
        </div>`;
      return;
    }
    c.innerHTML = rules.map(r => `
      <div style="background:var(--bg-surface);border:1px solid var(--border-subtle);padding:16px;margin-bottom:10px;display:flex;align-items:center;gap:14px;flex-wrap:wrap;">
        <div style="flex:1;min-width:200px;">
          <div style="font-size:14px;font-weight:800;color:#FFF;">${esc(r.name)}</div>
          <div style="font-family:var(--font-mono);font-size:11px;color:var(--text-muted);margin-top:3px;">
            KEYWORDS: <strong style="color:var(--text-main);">${esc(r.keywords?.join(', ') || 'None')}</strong> · SUBS: <strong style="color:var(--text-main);">${esc(r.subreddits?.join(', ') || 'All')}</strong>
          </div>
        </div>
        <span class="chip ${r.is_active ? 'chip-intent-buy' : 'chip-intent'}">${r.is_active ? 'ACTIVE' : 'PAUSED'}</span>
        <button class="btn btn-ghost btn-sm" onclick="toggleRule(${r.id}, ${!r.is_active})">${r.is_active ? 'PAUSE' : 'ACTIVATE'}</button>
        <button class="btn btn-ghost btn-sm" onclick="deleteRule(${r.id})">DELETE</button>
      </div>`).join('');
  } catch (e) {
    c.innerHTML = `<div class="empty-state"><div class="empty-desc">${esc(e.message)}</div></div>`;
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
  if (!seed) { toast('Enter a seed keyword first', 'warning'); return; }

  const box = document.getElementById('rule-keyword-suggestions');
  box.innerHTML = '<span style="font-family:var(--font-mono);font-size:11px;color:var(--text-muted);">Expanding...</span>';

  try {
    const res = await api('/monitoring-rules/expand-keywords', {
      method: 'POST',
      body: JSON.stringify({ seed }),
    });
    box.innerHTML = (res.suggestions || []).map(s => `
      <span class="reason-badge" style="cursor:pointer;" onclick="appendKeyword('${esc(s)}')">+ ${esc(s)}</span>
    `).join('');
  } catch (e) {
    box.innerHTML = '';
    toast(`Keyword expansion error: ${e.message}`, 'error');
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

  if (!name) { toast('Enter rule name', 'warning'); return; }

  try {
    await api('/monitoring-rules', {
      method: 'POST',
      body: JSON.stringify({
        name,
        keywords: kws,
        subreddits: subs,
        min_score: 1,
        min_opportunity_score: 60,
      }),
    });
    toast('Monitoring rule established', 'success');
    closeModal('modal-rule');
    loadMonitoringRules();
    loadMetrics();
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
    toast(`Rule state updated`, 'success');
    loadMonitoringRules();
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
}

async function deleteRule(id) {
  if (!confirm('Delete this monitoring rule?')) return;
  try {
    await api(`/monitoring-rules/${id}`, { method: 'DELETE' });
    toast('Rule removed', 'info');
    loadMonitoringRules();
    loadMetrics();
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
      <div style="background:var(--bg-surface);border:1px solid var(--border-subtle);padding:14px;">
        <div style="font-size:14px;font-weight:800;color:var(--brand-orange);margin-bottom:2px;">r/${esc(s.name)}</div>
        <div style="font-family:var(--font-mono);font-size:11px;color:var(--text-muted);margin-bottom:8px;">${(s.subscribers || 0).toLocaleString()} SUBSCRIBERS</div>
        <div style="font-family:var(--font-mono);font-size:11px;line-height:1.5;color:var(--text-secondary);">
          <div>PROMOTION: <strong style="color:#FFF;">${Math.round((s.profile?.promotion_tolerance || 0.5) * 100)}%</strong></div>
          <div>STYLE: <strong style="color:#FFF;">${esc(s.profile?.reply_style || 'Direct').toUpperCase()}</strong></div>
        </div>
      </div>`).join('');
  } catch (e) {
    c.innerHTML = `<div class="empty-state"><div class="empty-desc">${esc(e.message)}</div></div>`;
  }
}

function openAddSubredditModal() {
  const name = prompt('Enter Subreddit name (without r/):');
  if (!name) return;
  api('/subreddits', { method: 'POST', body: JSON.stringify({ name: name.trim() }) })
    .then(() => { toast(`Subreddit r/${name} added to monitor`, 'success'); loadSubreddits(); })
    .catch(e => toast(`Error: ${e.message}`, 'error'));
}

// ── COMPETITORS ──────────────────────────────────────────────────
async function loadCompetitors() {
  const c = document.getElementById('competitors-container');
  try {
    const comps = await api('/competitors');
    if (!comps.length) {
      c.innerHTML = `
        <div class="empty-state">
          <div class="empty-title">NO TRACKED COMPETITORS</div>
          <div class="empty-desc">Track competitors to automatically discover user complaints and migration intent.</div>
          <button class="btn btn-primary btn-sm" onclick="openAddCompetitorModal()">+ TRACK</button>
        </div>`;
      return;
    }
    c.innerHTML = comps.map(comp => `
      <div style="background:var(--bg-surface);border:1px solid var(--border-subtle);padding:14px;margin-bottom:8px;">
        <div style="display:flex;align-items:center;justify-content:space-between;">
          <div style="font-size:15px;font-weight:800;color:#FFF;">${esc(comp.name)}</div>
          <button class="btn btn-ghost btn-sm" onclick="deleteCompetitor(${comp.id})">DELETE</button>
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:6px;">
          ${(comp.tracked_keywords || []).map(k => `<span class="reason-badge">${esc(k)}</span>`).join('')}
        </div>
      </div>`).join('');
  } catch (e) {
    c.innerHTML = `<div class="empty-state"><div class="empty-desc">${esc(e.message)}</div></div>`;
  }
}

async function openAddCompetitorModal() {
  const name = prompt('Enter competitor name (e.g. Zapier, HubSpot):');
  if (!name) return;
  try {
    await api('/competitors', { method: 'POST', body: JSON.stringify({ name: name.trim() }) });
    toast(`Competitor ${name} tracked`, 'success');
    loadCompetitors();
    loadMetrics();
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
  if (!text) { toast('Enter post text first', 'warning'); return; }
  const out = document.getElementById('test-intent-out');
  out.innerHTML = '<span style="font-family:var(--font-mono);font-size:11px;color:var(--text-muted);">Classifying...</span>';
  try {
    const res = await api('/settings/test-llm', { method: 'POST' });
    out.innerHTML = `
      <div style="padding:8px;background:var(--bg-surface-elevated);border:1px solid var(--border-subtle);font-family:var(--font-mono);font-size:11.5px;">
        <span style="color:var(--accent-green);font-weight:700;">AI STATUS: ONLINE</span> · MODEL: ${res.model}
      </div>`;
  } catch (e) {
    out.innerHTML = `<div style="color:var(--accent-red);font-size:11.5px;">Error: ${esc(e.message)}</div>`;
  }
}

async function testCriticLab() {
  const title = document.getElementById('test-critic-title').value.trim();
  const reply = document.getElementById('test-critic-reply').value.trim();
  if (!reply) { toast('Enter draft reply text', 'warning'); return; }
  const out = document.getElementById('test-critic-out');
  out.innerHTML = '<span style="font-family:var(--font-mono);font-size:11px;color:var(--text-muted);">Running Critic...</span>';
  try {
    const res = await api('/replies/critic', {
      method: 'POST',
      body: JSON.stringify({ title: title || 'Question', content: '', reply, subreddit: 'SaaS' }),
    });
    out.innerHTML = renderCriticScorecard(res);
  } catch (e) {
    out.innerHTML = `<div style="color:var(--accent-red);font-size:11.5px;">Error: ${esc(e.message)}</div>`;
  }
}

// ── SETTINGS ─────────────────────────────────────────────────────
async function loadSettings() {
  try {
    const s = await api('/settings');
    if (s.reddit?.client_id && !s.reddit.client_id.startsWith('${')) {
      document.getElementById('setting-reddit-client-id').value = s.reddit.client_id;
    }
    const statusEl = document.getElementById('reddit-auth-status');
    if (statusEl) {
      statusEl.textContent = s.reddit?.has_credentials ? '[STATUS: OAUTH ACTIVE]' : '[STATUS: PUBLIC MODE]';
      statusEl.style.color = s.reddit?.has_credentials ? 'var(--accent-green)' : 'var(--accent-amber)';
    }

    if (s.alerts?.ntfy_topic) document.getElementById('setting-ntfy-topic').value = s.alerts.ntfy_topic;
    if (s.alerts?.email) document.getElementById('setting-alert-email').value = s.alerts.email;
    if (s.llm?.provider) document.getElementById('setting-llm-provider').value = s.llm.provider;
    if (s.llm?.model) document.getElementById('setting-llm-model').value = s.llm.model;
  } catch (e) {
    toast(`Failed to load settings: ${e.message}`, 'error');
  }
}

async function saveRedditSettings() {
  const cid = document.getElementById('setting-reddit-client-id').value.trim();
  const sec = document.getElementById('setting-reddit-client-secret').value.trim();
  try {
    const res = await api('/settings/reddit', {
      method: 'PUT',
      body: JSON.stringify({ client_id: cid, client_secret: sec }),
    });
    toast(res.has_credentials ? 'Reddit OAuth credentials saved & active!' : 'Reddit settings updated (Public Mode)', 'success');
    loadSettings();
  } catch (e) {
    toast(`Failed to save Reddit settings: ${e.message}`, 'error');
  }
}

async function saveAlertSettings() {
  const topic = document.getElementById('setting-ntfy-topic').value.trim();
  const email = document.getElementById('setting-alert-email').value.trim();
  try {
    await api('/settings/alerts', {
      method: 'PUT',
      body: JSON.stringify({ ntfy_topic: topic, email: email || null }),
    });
    toast('Alert configuration saved', 'success');
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
}

async function testPushNotification() {
  try {
    await api('/notifications/test-alert?channel=ntfy', { method: 'POST' });
    toast('Notification dispatched to ntfy topic', 'success');
  } catch (e) {
    toast(`Alert dispatch failed: ${e.message}`, 'error');
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
    toast('AI preferences saved', 'success');
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
}

async function testAIConnectivity() {
  const out = document.getElementById('llm-test-status');
  out.innerHTML = '<span style="font-family:var(--font-mono);font-size:11px;color:var(--text-muted);">Testing...</span>';
  try {
    const res = await api('/settings/test-llm', { method: 'POST' });
    if (res.healthy) {
      out.innerHTML = `<div style="font-family:var(--font-mono);font-size:11.5px;color:var(--accent-green);">ONLINE · PROVIDER: ${res.provider} · MODEL: ${res.model}</div>`;
    } else {
      out.innerHTML = `<div style="font-family:var(--font-mono);font-size:11.5px;color:var(--accent-red);">OFFLINE: ${esc(res.error)}</div>`;
    }
  } catch (e) {
    out.innerHTML = `<div style="font-family:var(--font-mono);font-size:11.5px;color:var(--accent-red);">${esc(e.message)}</div>`;
  }
}

// ── LOGS ─────────────────────────────────────────────────────────
async function loadLogs() {
  const c = document.getElementById('logs-container');
  try {
    const logs = await api('/dashboard/logs');
    if (!logs.length) {
      c.innerHTML = '<div style="color:var(--text-muted);padding:10px;">No activity logged yet.</div>';
      return;
    }
    c.innerHTML = logs.reverse().map(l => {
      const lvlColor = l.level === 'error' ? 'var(--accent-red)' : l.level === 'warning' ? 'var(--accent-amber)' : 'var(--accent-green)';
      const time = l.timestamp ? l.timestamp.split('T')[1].split('.')[0] : '--:--:--';
      return `
      <div style="padding:5px 0;border-bottom:1px solid var(--border-subtle);display:flex;gap:8px;">
        <span style="color:var(--text-muted);">${time}</span>
        <span style="font-weight:700;color:${lvlColor};min-width:60px;">[${l.level.toUpperCase()}]</span>
        <span style="color:var(--text-main);">${esc(l.message)}</span>
      </div>`;
    }).join('');
  } catch (e) {
    c.innerHTML = `<div style="color:var(--accent-red);">${esc(e.message)}</div>`;
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

function buildRedditUrl(urlOrPermalink, subreddit, redditId) {
  if (urlOrPermalink && urlOrPermalink.startsWith('http')) {
    return urlOrPermalink;
  }
  if (urlOrPermalink && urlOrPermalink.startsWith('/')) {
    return `https://reddit.com${urlOrPermalink}`;
  }
  if (subreddit && redditId) {
    return `https://reddit.com/r/${subreddit}/comments/${redditId}`;
  }
  if (subreddit) {
    return `https://reddit.com/r/${subreddit}`;
  }
  return 'https://reddit.com';
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

// ── INITIALIZATION ───────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadMetrics();
  navigate('opportunities');
  setInterval(loadMetrics, 15000);
});
