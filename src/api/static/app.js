// ── RedditPulse Dashboard JS ─────────────────────────────────────
// Modular, clean, no framework required.
// ────────────────────────────────────────────────────────────────

const API = '';
let _searchTimer = null;
let _currentPage = 'overview';
let _postsOffset = 0;
const _postsPerPage = 25;
let _totalPosts = 0;
let _subreddits = [];

// ── NAVIGATION ──────────────────────────────────────────────────

function navigate(page) {
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.page').forEach(el => el.classList.remove('active'));

  const navEl = document.querySelector(`[data-page="${page}"]`);
  if (navEl) navEl.classList.add('active');

  const pageEl = document.getElementById(`page-${page}`);
  if (pageEl) pageEl.classList.add('active');

  _currentPage = page;

  const titles = {
    overview: ['Overview', 'Reddit intelligence at a glance'],
    posts: ['Posts Feed', 'All monitored Reddit posts'],
    keywords: ['Keywords', 'Manage tracked keywords'],
    subreddits: ['Subreddits', 'Manage watched subreddits'],
    playground: ['AI Playground', 'Test AI features interactively'],
    logs: ['Activity Log', 'System events and polling history'],
    settings: ['Settings', 'Configure your intelligence platform'],
  };

  const [title, sub] = titles[page] || ['Dashboard', ''];
  document.getElementById('topbar-title').textContent = title;
  document.getElementById('topbar-subtitle').textContent = sub;

  if (page === 'overview') loadOverview();
  if (page === 'posts') { _postsOffset = 0; loadPosts(); }
  if (page === 'keywords') loadKeywords();
  if (page === 'subreddits') loadSubreddits();
  if (page === 'logs') loadLogs();
  if (page === 'settings') loadSettings();
}

// ── TOAST ────────────────────────────────────────────────────────

function toast(msg, type = 'info', duration = 4000) {
  const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
  const container = document.getElementById('toast-container');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.innerHTML = `<span class="toast-icon">${icons[type] || '•'}</span><span style="flex:1;">${msg}</span><span class="toast-dismiss" onclick="this.parentElement.remove()">✕</span>`;
  container.appendChild(t);
  setTimeout(() => t.remove(), duration);
}

// ── API HELPERS ──────────────────────────────────────────────────

async function apiFetch(url, options = {}) {
  const r = await fetch(API + url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(err.detail || `HTTP ${r.status}`);
  }
  return r.json();
}

// ── SCHEDULER ───────────────────────────────────────────────────

async function refreshSchedulerStatus() {
  try {
    const data = await apiFetch('/api/scheduler/status');
    const dot = document.getElementById('scheduler-dot');
    const label = document.getElementById('scheduler-sublabel');
    if (data.is_running) {
      dot.className = 'status-dot running';
      label.textContent = 'Running · ' + (data.next_poll_in || '');
    } else {
      dot.className = 'status-dot stopped';
      label.textContent = 'Stopped';
    }
  } catch (_) {}
}

async function controlScheduler(action) {
  try {
    await apiFetch(`/api/scheduler/${action}`, { method: 'POST' });
    toast(action === 'start' ? 'Scheduler started' : 'Scheduler stopped', 'success');
    refreshSchedulerStatus();
  } catch (e) {
    toast(`Scheduler error: ${e.message}`, 'error');
  }
}

async function triggerPoll(btn) {
  const orig = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="loading-spinner"></span> Polling...';
  try {
    const res = await apiFetch('/api/scheduler/trigger-poll', { method: 'POST' });
    toast(`Poll complete: ${res.result?.new_mentions ?? 0} new posts`, 'success');
    if (_currentPage === 'overview') loadOverview();
    if (_currentPage === 'posts') loadPosts();
  } catch (e) {
    toast(`Poll failed: ${e.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = orig;
  }
}

async function triggerFullCycle(btn) {
  const orig = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="loading-spinner"></span> Running...';
  try {
    const res = await apiFetch('/api/scheduler/trigger-cycle', { method: 'POST' });
    const r = res.cycle_results || {};
    toast(`Cycle done · ${r.new_mentions ?? 0} new posts · ${r.processed ?? 0} analyzed`, 'success');
    if (_currentPage === 'overview') loadOverview();
    if (_currentPage === 'posts') loadPosts();
  } catch (e) {
    toast(`Cycle failed: ${e.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = orig;
  }
}

async function reclassifyAll(btn) {
  const orig = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="loading-spinner dark"></span> Re-classifying...';
  toast('Re-classifying all posts with fresh AI — this may take a minute...', 'info', 8000);
  try {
    const res = await apiFetch('/api/scheduler/reclassify', { method: 'POST' });
    toast(`✅ ${res.message}`, 'success', 6000);
    if (_currentPage === 'overview') loadOverview();
    if (_currentPage === 'posts') loadPosts();
  } catch (e) {
    toast(`Re-classify failed: ${e.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = orig;
  }
}


// ── OVERVIEW ────────────────────────────────────────────────────

async function loadOverview() {
  try {
    const [stats, mentionsData, kwData] = await Promise.all([
      apiFetch('/api/stats'),
      apiFetch('/api/mentions?limit=5&offset=0'),
      apiFetch('/api/keywords'),
    ]);

    const byTag = stats.by_intent_tag || {};
    const total = stats.total_mentions || 0;

    setEl('stat-total', total);
    setEl('stat-buy', byTag['buy-intent'] || 0);
    setEl('stat-pain', byTag['pain-point'] || 0);
    setEl('stat-analyzed', stats.analyzed_mentions || stats.total_mentions || 0);
    setEl('stat-questions', byTag['question'] || 0);
    setEl('stat-alternatives', byTag['seeking-alternatives'] || 0);
    setEl('stat-keywords', kwData.filter(k => k.active).length);
    document.getElementById('sidebar-count').textContent = total;

    // Render latest posts
    const container = document.getElementById('overview-latest');
    if (!mentionsData.items?.length) {
      container.innerHTML = `<div class="empty-state"><div class="empty-icon">📭</div><div class="empty-title">No posts yet</div><div class="empty-desc">Add keywords and click "Poll Now" to start monitoring Reddit</div><button class="btn btn-primary" onclick="navigate('keywords')">Add Keywords</button></div>`;
    } else {
      container.innerHTML = mentionsData.items.map(renderPostCard).join('');
    }
  } catch (e) {
    console.error('Overview load error:', e);
    toast('Failed to load overview: ' + e.message, 'error');
  }
}

function setEl(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

// ── POSTS FEED ───────────────────────────────────────────────────

async function loadPosts() {
  const container = document.getElementById('posts-container');
  container.innerHTML = `<div class="skeleton skeleton-card"></div><div class="skeleton skeleton-card"></div><div class="skeleton skeleton-card"></div>`;

  const tag = document.getElementById('filter-tag')?.value || '';
  const hours = document.getElementById('filter-hours')?.value || '';
  const query = document.getElementById('search-input')?.value || '';
  const subFilter = document.getElementById('filter-subreddit')?.value || '';

  let url = `/api/mentions?limit=${_postsPerPage}&offset=${_postsOffset}`;
  if (tag) url += `&tag=${encodeURIComponent(tag)}`;
  if (hours) url += `&hours=${hours}`;
  if (query) url += `&query=${encodeURIComponent(query)}`;
  if (subFilter) url += `&subreddit=${encodeURIComponent(subFilter)}`;  // filtered server-side if supported, else handled below

  try {
    const data = await apiFetch(url);
    _totalPosts = data.total;

    let items = data.items || [];
    // Client-side subreddit filter if backend doesn't support it
    if (subFilter) {
      items = items.filter(m => (m.subreddit || '').toLowerCase() === subFilter.toLowerCase());
    }

    if (!items.length) {
      container.innerHTML = `<div class="empty-state"><div class="empty-icon">🔍</div><div class="empty-title">No posts found</div><div class="empty-desc">Try adjusting your filters or add more keywords</div></div>`;
    } else {
      container.innerHTML = `<div class="posts-list">${items.map(renderPostCard).join('')}</div>`;
    }

    renderPagination();

    // Update subreddit filter options
    await updateSubredditFilter();
  } catch (e) {
    container.innerHTML = `<div class="empty-state"><div class="empty-icon">⚠️</div><div class="empty-title">Failed to load posts</div><div class="empty-desc">${e.message}</div></div>`;
  }
}

async function updateSubredditFilter() {
  try {
    const data = await apiFetch('/api/mentions?limit=500&offset=0');
    const subs = [...new Set((data.items || []).map(m => m.subreddit).filter(Boolean))].sort();
    const sel = document.getElementById('filter-subreddit');
    if (!sel) return;
    const current = sel.value;
    sel.innerHTML = '<option value="">All Subreddits</option>' + subs.map(s => `<option value="${s}" ${s === current ? 'selected' : ''}>r/${s}</option>`).join('');
  } catch (_) {}
}

function renderPagination() {
  const container = document.getElementById('pagination');
  if (!container) return;
  const totalPages = Math.ceil(_totalPosts / _postsPerPage);
  const currentPageNum = Math.floor(_postsOffset / _postsPerPage) + 1;

  if (totalPages <= 1) { container.innerHTML = ''; return; }

  let html = `<button class="page-btn" onclick="goToPage(${currentPageNum - 1})" ${currentPageNum === 1 ? 'disabled' : ''}>← Prev</button>`;
  html += `<span class="page-info">Page ${currentPageNum} of ${totalPages} · ${_totalPosts} posts</span>`;
  html += `<button class="page-btn" onclick="goToPage(${currentPageNum + 1})" ${currentPageNum === totalPages ? 'disabled' : ''}>Next →</button>`;
  container.innerHTML = html;
}

function goToPage(page) {
  _postsOffset = (page - 1) * _postsPerPage;
  loadPosts();
}

function debounceSearch() {
  clearTimeout(_searchTimer);
  _searchTimer = setTimeout(() => { _postsOffset = 0; loadPosts(); }, 350);
}

function resetFilters() {
  document.getElementById('search-input').value = '';
  document.getElementById('filter-tag').value = '';
  document.getElementById('filter-hours').value = '';
  document.getElementById('filter-subreddit').value = '';
  _postsOffset = 0;
  loadPosts();
}

// ── POST CARD RENDERER ───────────────────────────────────────────

function renderPostCard(post) {
  const tag = post.primary_tag || 'other';
  const confidence = post.primary_confidence || 0;
  const analysis = post.ai_analysis || {};
  const oppScore = analysis.opportunity_score || 0;
  const buySignal = analysis.buy_signal_strength || 0;
  const hasAnalysis = Object.keys(analysis).length > 0;

  const age = timeAgo(post.posted_at);
  const subreddit = post.subreddit || 'unknown';
  const excerpt = (post.content || post.title || '').replace(/\n+/g, ' ').substring(0, 320);
  const postType = post.post_type || 'text';
  const score = post.score || 0;
  const numComments = post.num_comments || 0;
  const upvoteRatio = post.upvote_ratio ? `${Math.round(post.upvote_ratio * 100)}%` : '';
  const flair = post.post_flair;
  const awards = post.awards_count || 0;

  return `
<div class="post-card" id="post-${post.id}">
  <div class="post-card-inner">
    <div class="post-meta-row">
      <span class="subreddit-badge">r/${escHtml(subreddit)}</span>
      <span class="post-author">u/${escHtml(post.author || 'deleted')}</span>
      <span class="post-age text-muted">· ${age}</span>
      ${flair ? `<span class="flair-chip">${escHtml(flair)}</span>` : ''}
      <span class="post-type-chip post-type-${postType}">${postType}</span>
      ${awards > 0 ? `<span class="text-xs" title="${awards} awards">🏅 ${awards}</span>` : ''}
      <span class="intent-badge intent-${tag}" style="margin-left:auto;">${intentLabel(tag)}</span>
    </div>

    <div class="post-title">
      <a href="${escHtml(post.url || '#')}" target="_blank" rel="noopener">${escHtml(post.title || 'Untitled')}</a>
    </div>

    ${excerpt ? `<div class="post-excerpt">${escHtml(excerpt)}</div>` : ''}

    <div class="post-signals">
      <div class="signal upvotes">
        <span class="signal-icon">▲</span>
        <span>${score.toLocaleString()}</span>
      </div>
      <div class="signal">
        <span class="signal-icon">💬</span>
        <span>${numComments.toLocaleString()} comments</span>
      </div>
      ${upvoteRatio ? `<div class="signal"><span class="signal-icon">📊</span><span>${upvoteRatio} upvoted</span></div>` : ''}
      ${confidence ? `<div class="signal"><span class="signal-icon">🎯</span><span>${confidence}% confidence</span></div>` : ''}
      ${oppScore > 0 ? `
        <div class="opportunity-bar-wrap" title="Opportunity Score: ${oppScore}/100">
          <span class="signal-icon">⭐</span>
          <div class="opportunity-bar"><div class="opportunity-fill" style="width:${oppScore}%"></div></div>
          <span style="font-size:11px;font-weight:600;color:var(--text-secondary);">${oppScore}</span>
        </div>` : ''}
      <div class="post-actions">
        ${hasAnalysis
          ? `<button class="btn btn-secondary btn-sm" onclick="toggleAnalysis(${post.id})">🔬 Analysis</button>`
          : `<button class="btn btn-ghost btn-sm" onclick="analyzePost(${post.id})">Analyze</button>`}
        <a href="${escHtml(post.url || '#')}" target="_blank" class="btn btn-ghost btn-sm">↗ View</a>
        <button class="btn btn-ghost btn-sm" onclick="deletePost(${post.id})" title="Delete">🗑</button>
      </div>
    </div>
  </div>

  ${hasAnalysis ? renderAnalysisDrawer(post) : ''}
  ${post.latest_reply ? renderReplyBox(post) : ''}
</div>`;
}

function renderAnalysisDrawer(post) {
  const a = post.ai_analysis || {};
  const products = (a.mentioned_products || []);
  const painKws = (a.pain_keywords || []);

  return `
<div class="analysis-drawer" id="analysis-${post.id}">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
    <span style="font-size:13px;font-weight:700;color:var(--text-primary);">🔬 AI Deep Analysis</span>
    <div style="display:flex;gap:8px;align-items:center;">
      <span class="text-xs text-muted">${a.is_fallback ? '(heuristic)' : '(AI-generated)'}</span>
      <button class="btn btn-primary btn-sm" onclick="openReplyGenerator(${post.id})">✍️ Draft Reply</button>
    </div>
  </div>

  <div class="signal-meters">
    <div class="meter-item">
      <span class="meter-label">Opportunity</span>
      <div class="meter-bar"><div class="meter-fill opportunity" style="width:${a.opportunity_score || 0}%"></div></div>
      <span class="meter-value">${a.opportunity_score || 0}/100</span>
    </div>
    <div class="meter-item">
      <span class="meter-label">Buy Signal</span>
      <div class="meter-bar"><div class="meter-fill buy-signal" style="width:${a.buy_signal_strength || 0}%"></div></div>
      <span class="meter-value">${a.buy_signal_strength || 0}/100</span>
    </div>
    <div class="meter-item">
      <span class="meter-label">Engagement</span>
      <div class="meter-bar"><div class="meter-fill engagement" style="width:${a.engagement_potential || 0}%"></div></div>
      <span class="meter-value">${a.engagement_potential || 0}/100</span>
    </div>
    <div class="meter-item" style="margin-left:16px;">
      <span class="meter-label">Urgency</span>
      <span class="meter-value" style="font-size:13px;">${urgencyBadge(a.urgency)}</span>
    </div>
    <div class="meter-item">
      <span class="meter-label">Sentiment</span>
      <span class="meter-value" style="font-size:13px;">${a.sentiment || '—'}</span>
    </div>
  </div>

  <div class="analysis-grid" style="margin-top:14px;">
    <div class="analysis-section">
      <div class="analysis-label">Summary</div>
      <div class="analysis-text">${escHtml(a.summary || '—')}</div>
    </div>
    <div class="analysis-section">
      <div class="analysis-label">What It Means</div>
      <div class="analysis-text">${escHtml(a.what_it_means || '—')}</div>
    </div>
    <div class="analysis-section">
      <div class="analysis-label">What They Need</div>
      <div class="analysis-text">${escHtml(a.what_it_requires || a.what_it_does || '—')}</div>
    </div>
    <div class="analysis-section">
      <div class="analysis-label">Reddit Context</div>
      <div class="analysis-text">${escHtml(a.reddit_context || '—')}</div>
    </div>
    ${products.length ? `
    <div class="analysis-section">
      <div class="analysis-label">Mentioned Products</div>
      <div class="tag-pills">${products.map(p => `<span class="pill product">${escHtml(p)}</span>`).join('')}</div>
    </div>` : ''}
    ${painKws.length ? `
    <div class="analysis-section">
      <div class="analysis-label">Pain Keywords</div>
      <div class="tag-pills">${painKws.map(k => `<span class="pill pain">${escHtml(k)}</span>`).join('')}</div>
    </div>` : ''}
    <div class="analysis-section analysis-full">
      <div class="analysis-label">🎯 Recommended Engagement Angle</div>
      <div class="analysis-text" style="color:var(--text-primary);font-weight:500;">${escHtml(a.recommended_angle || '—')}</div>
    </div>
    ${a.community_signals ? `
    <div class="analysis-section analysis-full">
      <div class="analysis-label">Community Signals</div>
      <div class="analysis-text">${escHtml(a.community_signals)}</div>
    </div>` : ''}
  </div>
</div>`;
}

function renderReplyBox(post) {
  const reply = post.latest_reply;
  if (!reply) return '';
  return `
<div class="reply-box" id="reply-box-${post.id}">
  <div class="reply-box-header">
    <span>✍️ AI Draft Reply</span>
    <span class="text-xs text-muted">${reply.model || 'AI'} · ${reply.sent ? '✅ Marked sent' : 'Draft'}</span>
  </div>
  <div class="reply-content" id="reply-content-${reply.id}">${escHtml(reply.content)}</div>
  <div class="reply-actions">
    <button class="btn btn-ghost btn-sm" onclick="copyReply(${reply.id})">📋 Copy</button>
    <button class="btn btn-ghost btn-sm" onclick="markReplySent(${post.id}, ${reply.id})">${reply.sent ? '↩ Unmark' : '✅ Mark Sent'}</button>
    <button class="btn btn-secondary btn-sm" onclick="regenerateReply(${post.id})">🔄 Regenerate</button>
  </div>
</div>`;
}

function toggleAnalysis(postId) {
  const el = document.getElementById(`analysis-${postId}`);
  if (el) el.classList.toggle('open');
}

// ── POST ACTIONS ─────────────────────────────────────────────────

async function analyzePost(postId) {
  const btn = document.querySelector(`#post-${postId} .btn-ghost`);
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="loading-spinner dark"></span>'; }
  try {
    const res = await apiFetch(`/api/mentions/${postId}/analyze`, { method: 'POST' });
    toast('Analysis complete!', 'success');
    // Re-render just this card
    const data = await apiFetch(`/api/mentions/${postId}`);
    const card = document.getElementById(`post-${postId}`);
    if (card) card.outerHTML = renderPostCard(data);
    const newDrawer = document.getElementById(`analysis-${postId}`);
    if (newDrawer) newDrawer.classList.add('open');
  } catch (e) {
    toast(`Analysis failed: ${e.message}`, 'error');
    if (btn) { btn.disabled = false; btn.innerHTML = 'Analyze'; }
  }
}

async function regenerateReply(postId) {
  try {
    const tone = 'casual';
    const res = await apiFetch(`/api/mentions/${postId}/regenerate-reply`, {
      method: 'POST',
      body: JSON.stringify({ tone }),
    });
    toast('Reply regenerated!', 'success');
    const data = await apiFetch(`/api/mentions/${postId}`);
    const card = document.getElementById(`post-${postId}`);
    if (card) {
      const analysisWasOpen = document.getElementById(`analysis-${postId}`)?.classList.contains('open');
      card.outerHTML = renderPostCard(data);
      if (analysisWasOpen) {
        const newDrawer = document.getElementById(`analysis-${postId}`);
        if (newDrawer) newDrawer.classList.add('open');
      }
    }
  } catch (e) {
    toast(`Regenerate failed: ${e.message}`, 'error');
  }
}

async function openReplyGenerator(postId) {
  await regenerateReply(postId);
}

function copyReply(replyId) {
  const el = document.getElementById(`reply-content-${replyId}`);
  if (el) {
    navigator.clipboard.writeText(el.textContent).then(() => toast('Reply copied to clipboard!', 'success'));
  }
}

async function markReplySent(postId, replyId) {
  try {
    await apiFetch(`/api/mentions/${postId}/reply`, {
      method: 'PUT',
      body: JSON.stringify({ content: '', sent: true }),
    });
    toast('Marked as sent!', 'success');
    const data = await apiFetch(`/api/mentions/${postId}`);
    const card = document.getElementById(`post-${postId}`);
    if (card) card.outerHTML = renderPostCard(data);
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
}

async function deletePost(postId) {
  if (!confirm('Delete this post?')) return;
  try {
    await apiFetch(`/api/mentions/${postId}`, { method: 'DELETE' });
    document.getElementById(`post-${postId}`)?.remove();
    toast('Post deleted', 'info');
  } catch (e) {
    toast(`Delete failed: ${e.message}`, 'error');
  }
}

// ── KEYWORDS ────────────────────────────────────────────────────

async function loadKeywords() {
  const container = document.getElementById('keywords-list');
  container.innerHTML = '<div class="skeleton skeleton-card"></div>';
  try {
    const keywords = await apiFetch('/api/keywords');
    if (!keywords.length) {
      container.innerHTML = `<div class="empty-state"><div class="empty-icon">🏷</div><div class="empty-title">No keywords yet</div><div class="empty-desc">Add keywords to start monitoring Reddit posts</div><button class="btn btn-primary" onclick="openKeywordModal()">+ Add First Keyword</button></div>`;
      return;
    }
    container.innerHTML = keywords.map(kw => `
      <div class="keyword-item">
        <div style="flex:1;">
          <div class="keyword-name">🏷 ${escHtml(kw.keyword)}</div>
          <div class="keyword-subs">${kw.subreddits?.length ? 'r/' + kw.subreddits.join(', r/') : 'All watched subreddits'} · Min score: ${kw.min_score}</div>
        </div>
        <label class="toggle" title="${kw.active ? 'Active' : 'Inactive'}">
          <input type="checkbox" ${kw.active ? 'checked' : ''} onchange="toggleKeyword(${kw.id}, this.checked)">
          <span class="toggle-slider"></span>
        </label>
        <span class="keyword-status ${kw.active ? 'keyword-active' : 'keyword-inactive'}">${kw.active ? 'Active' : 'Paused'}</span>
        <button class="btn btn-ghost btn-sm" onclick="deleteKeyword(${kw.id})">🗑</button>
      </div>`).join('');
  } catch (e) {
    container.innerHTML = `<div class="empty-state"><div class="empty-title">Error loading keywords</div><div class="empty-desc">${e.message}</div></div>`;
  }
}

function openKeywordModal() {
  document.getElementById('kw-input').value = '';
  document.getElementById('kw-subreddits').value = '';
  document.getElementById('kw-min-score').value = '1';
  openModal('modal-keyword');
}

async function addKeyword() {
  const keyword = document.getElementById('kw-input').value.trim();
  if (!keyword) { toast('Enter a keyword first', 'warning'); return; }
  const subsRaw = document.getElementById('kw-subreddits').value;
  const subreddits = subsRaw ? subsRaw.split(',').map(s => s.trim()).filter(Boolean) : null;
  const minScore = parseInt(document.getElementById('kw-min-score').value) || 1;
  try {
    await apiFetch('/api/keywords', {
      method: 'POST',
      body: JSON.stringify({ keyword, sources: ['reddit'], subreddits, min_score: minScore }),
    });
    toast(`Keyword "${keyword}" added!`, 'success');
    closeModal('modal-keyword');
    loadKeywords();
  } catch (e) {
    toast(`Failed to add keyword: ${e.message}`, 'error');
  }
}

async function toggleKeyword(id, active) {
  try {
    await apiFetch(`/api/keywords/${id}/toggle`, {
      method: 'PUT',
      body: JSON.stringify({ active }),
    });
    toast(`Keyword ${active ? 'enabled' : 'paused'}`, 'success');
    loadKeywords();
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
}

async function deleteKeyword(id) {
  if (!confirm('Delete this keyword?')) return;
  try {
    await apiFetch(`/api/keywords/${id}`, { method: 'DELETE' });
    toast('Keyword deleted', 'info');
    loadKeywords();
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
}

// ── SUBREDDITS ───────────────────────────────────────────────────

async function loadSubreddits() {
  try {
    const config = await apiFetch('/api/config');
    _subreddits = (config.reddit?.subreddits || ['all']);
    renderSubredditChips();
  } catch (e) {
    toast('Error loading subreddits: ' + e.message, 'error');
  }
}

function renderSubredditChips() {
  const container = document.getElementById('subreddit-chips');
  if (!container) return;
  if (!_subreddits.length) {
    container.innerHTML = '<span class="text-sm text-muted">No subreddits configured</span>';
    return;
  }
  container.innerHTML = _subreddits.map(s => `
    <span class="subreddit-chip">
      r/${escHtml(s)}
      <span class="chip-remove" onclick="removeSubreddit('${escHtml(s)}')">×</span>
    </span>`).join('');
}

function addSubreddit() {
  const input = document.getElementById('add-subreddit-input');
  const val = input.value.trim().replace(/^r\//i, '');
  if (!val) return;
  if (_subreddits.includes(val)) { toast('Already watching that subreddit', 'warning'); return; }
  _subreddits.push(val);
  renderSubredditChips();
  input.value = '';
  toast(`Added r/${val}. Note: Update config.yaml or restart to persist.`, 'info', 6000);
}

function removeSubreddit(name) {
  _subreddits = _subreddits.filter(s => s !== name);
  renderSubredditChips();
}

async function testLiveSearch() {
  const keyword = document.getElementById('test-keyword-input').value.trim();
  const subreddit = document.getElementById('test-subreddit-input').value.trim() || 'all';
  if (!keyword) { toast('Enter a keyword to test', 'warning'); return; }

  const container = document.getElementById('test-results');
  container.innerHTML = '<div class="skeleton skeleton-line w-full"></div><div class="skeleton skeleton-line w-full"></div>';

  try {
    const data = await apiFetch('/api/keywords/test-search', {
      method: 'POST',
      body: JSON.stringify({ keyword, source: 'reddit', subreddit, limit: 10 }),
    });

    if (!data.items?.length) {
      container.innerHTML = '<div class="text-sm text-muted" style="margin-top:8px;">No posts found. Try a broader keyword.</div>';
      return;
    }

    container.innerHTML = `
      <div style="margin-top:12px;font-size:12px;color:var(--text-muted);margin-bottom:8px;">Found ${data.count} results from Reddit:</div>
      <div class="posts-list">${data.items.slice(0, 6).map(item => `
        <div class="post-card" style="margin-bottom:8px;">
          <div class="post-card-inner" style="padding:12px 16px;">
            <div class="post-meta-row" style="margin-bottom:6px;">
              <span class="subreddit-badge">r/${escHtml(item.subreddit || 'unknown')}</span>
              <span class="post-age text-muted">· ${timeAgo(item.posted_at)}</span>
              <span class="signal upvotes" style="margin-left:auto;font-size:12px;">▲ ${item.score || 0}</span>
              <span class="signal" style="font-size:12px;">💬 ${item.num_comments || 0}</span>
            </div>
            <div class="post-title" style="font-size:13px;"><a href="${escHtml(item.url || '#')}" target="_blank">${escHtml(item.title || 'Untitled')}</a></div>
          </div>
        </div>`).join('')}
      </div>`;
  } catch (e) {
    container.innerHTML = `<div class="text-sm" style="color:var(--danger);margin-top:8px;">Error: ${e.message}</div>`;
  }
}

// ── SETTINGS ─────────────────────────────────────────────────────

async function loadSettings() {
  try {
    const config = await apiFetch('/api/config');

    // Alert config
    const alerts = config.alerts || {};
    const el = (id) => document.getElementById(id);
    if (el('ntfy-topic')) el('ntfy-topic').value = alerts.ntfy_topic || '';
    if (el('alert-email')) el('alert-email').value = alerts.email || '';
    if (el('min-confidence')) {
      const pct = Math.round((alerts.min_confidence || 0.7) * 100);
      el('min-confidence').value = pct;
      el('confidence-val').textContent = pct + '%';
    }
    if (el('alert-frequency')) el('alert-frequency').value = alerts.frequency || 'immediate';

    // Alert tags
    const activeTags = alerts.tags_to_alert || ['buy-intent', 'pain-point', 'competitor-complaint'];
    document.querySelectorAll('#alert-tags-filter .tag-btn').forEach(btn => {
      const tag = btn.dataset.tag;
      btn.classList.toggle('active', activeTags.includes(tag));
      btn.onclick = () => btn.classList.toggle('active');
    });

    // LLM config
    const llm = config.llm || {};
    if (el('llm-provider')) el('llm-provider').value = llm.provider || 'opencode_zen';
    if (el('zen-model')) el('zen-model').value = llm.opencode_zen?.model || 'deepseek-v4-flash-free';
    if (el('ollama-host')) el('ollama-host').value = llm.ollama?.host || 'http://localhost:11434';
    if (el('ollama-model')) el('ollama-model').value = llm.ollama?.model || 'llama3.1:8b';
    updateLLMProviderUI();

    // Reddit config
    const reddit = config.reddit || {};
    if (el('reddit-client-id')) el('reddit-client-id').value = reddit.client_id || 'Not configured';
    if (el('reddit-user-agent')) el('reddit-user-agent').value = reddit.user_agent || '';

  } catch (e) {
    toast('Error loading settings: ' + e.message, 'error');
  }
}

function updateLLMProviderUI() {
  const provider = document.getElementById('llm-provider')?.value;
  const zenConfig = document.getElementById('zen-config');
  const ollamaConfig = document.getElementById('ollama-config');
  if (zenConfig) zenConfig.style.display = provider === 'opencode_zen' ? 'block' : 'none';
  if (ollamaConfig) ollamaConfig.style.display = provider === 'ollama' ? 'block' : 'none';
}

async function saveAlertConfig() {
  const el = (id) => document.getElementById(id);
  const activeTags = [...document.querySelectorAll('#alert-tags-filter .tag-btn.active')].map(b => b.dataset.tag);
  const payload = {
    ntfy_topic: el('ntfy-topic')?.value?.trim() || null,
    email: el('alert-email')?.value?.trim() || null,
    min_intent_confidence: parseFloat(el('min-confidence')?.value || '70') / 100,
    tags_to_alert: activeTags,
    frequency: el('alert-frequency')?.value || 'immediate',
  };
  try {
    await apiFetch('/api/config/alerts', { method: 'PUT', body: JSON.stringify(payload) });
    toast('Alert configuration saved!', 'success');
  } catch (e) {
    toast('Failed to save alert config: ' + e.message, 'error');
  }
}

async function saveLLMConfig() {
  const provider = document.getElementById('llm-provider')?.value;
  const model = provider === 'opencode_zen'
    ? document.getElementById('zen-model')?.value
    : document.getElementById('ollama-model')?.value;
  const apiKey = document.getElementById('zen-api-key')?.value?.trim() || null;
  try {
    await apiFetch('/api/config/llm', { method: 'PUT', body: JSON.stringify({ provider, model, api_key: apiKey }) });
    toast('AI configuration saved!', 'success');
  } catch (e) {
    toast('Failed to save AI config: ' + e.message, 'error');
  }
}

async function testLLMConnection() {
  const resultEl = document.getElementById('llm-test-result');
  resultEl.classList.remove('hidden');
  resultEl.innerHTML = '<span class="loading-spinner dark"></span> Testing connection...';
  try {
    const res = await apiFetch('/api/config/test-llm', { method: 'POST' });
    resultEl.innerHTML = res.healthy
      ? `✅ Connected · Provider: ${res.provider} · Model: ${res.model}<br><em>${escHtml(res.sample_response || '')}</em>`
      : `❌ Not connected · ${JSON.stringify(res.details)}`;
  } catch (e) {
    resultEl.innerHTML = `❌ Error: ${e.message}`;
  }
}

async function testRedditConnection() {
  const el = document.getElementById('reddit-test-result');
  el.textContent = 'Testing...';
  try {
    const res = await apiFetch('/api/config/test-reddit', { method: 'POST' });
    el.textContent = res.connected ? '✅ Connected' : '❌ Not connected';
    el.style.color = res.connected ? 'var(--success)' : 'var(--danger)';
  } catch (e) {
    el.textContent = '❌ Error: ' + e.message;
    el.style.color = 'var(--danger)';
  }
}

async function sendTestAlert() {
  const ntfyTopic = document.getElementById('ntfy-topic')?.value?.trim();
  try {
    const res = await apiFetch('/api/config/test-alert', {
      method: 'POST',
      body: JSON.stringify({ push: true, email: false, ntfy_topic: ntfyTopic }),
    });
    const d = res.details || {};
    if (d.push_sent) toast('📲 Test push notification sent!', 'success');
    else if (d.push_error) toast('Push error: ' + d.push_error, 'error');
    else toast('Alert test result: ' + JSON.stringify(d), 'info');
  } catch (e) {
    toast('Test alert failed: ' + e.message, 'error');
  }
}

// ── AI PLAYGROUND ────────────────────────────────────────────────

async function testIntent() {
  const text = document.getElementById('intent-text')?.value?.trim();
  if (!text) { toast('Enter some text first', 'warning'); return; }
  const resultEl = document.getElementById('intent-result');
  resultEl.classList.remove('hidden');
  resultEl.innerHTML = '<span class="loading-spinner dark"></span> Classifying...';
  try {
    const res = await apiFetch('/api/ai/test-intent', { method: 'POST', body: JSON.stringify({ text }) });
    resultEl.innerHTML = `
      <div class="flex items-center gap-2 mb-2">
        <span class="intent-badge intent-${res.tag}">${intentLabel(res.tag)}</span>
        <span class="text-sm text-muted">${res.confidence_percent}% confidence</span>
        ${res.is_fallback ? '<span class="text-xs text-muted">(heuristic)</span>' : '<span class="text-xs" style="color:var(--success);">(AI)</span>'}
      </div>
      <div class="text-sm text-muted">Intent tag: <strong>${res.tag}</strong></div>`;
  } catch (e) {
    resultEl.innerHTML = `❌ Error: ${e.message}`;
  }
}

async function testReply() {
  const title = document.getElementById('reply-title')?.value || '';
  const content = document.getElementById('reply-content')?.value?.trim() || '';
  const intent = document.getElementById('reply-intent')?.value || 'question';
  const tone = document.getElementById('reply-tone')?.value || 'casual';
  if (!content) { toast('Enter post content first', 'warning'); return; }
  const resultEl = document.getElementById('reply-result');
  resultEl.classList.remove('hidden');
  resultEl.innerHTML = '<span class="loading-spinner dark"></span> Generating reply...';
  try {
    const res = await apiFetch('/api/ai/test-reply', {
      method: 'POST',
      body: JSON.stringify({ source: 'reddit', title, content, intent_tag: intent, tone }),
    });
    resultEl.innerHTML = `
      <div class="text-xs text-muted mb-2">Generated by ${escHtml(res.model || 'AI')} ${res.is_fallback ? '(fallback template)' : ''}</div>
      <div style="font-size:13.5px;line-height:1.7;color:var(--text-primary);">${escHtml(res.reply)}</div>`;
  } catch (e) {
    resultEl.innerHTML = `❌ Error: ${e.message}`;
  }
}

async function testAnalyze() {
  const title = document.getElementById('analyze-title')?.value || '';
  const content = document.getElementById('analyze-content')?.value?.trim() || '';
  const subreddit = document.getElementById('analyze-subreddit')?.value?.trim() || '';
  if (!content && !title) { toast('Enter a post title or content', 'warning'); return; }
  const resultEl = document.getElementById('analyze-result');
  resultEl.classList.remove('hidden');
  resultEl.innerHTML = '<span class="loading-spinner dark"></span> Running deep analysis...';
  try {
    const res = await apiFetch('/api/ai/test-analyze', {
      method: 'POST',
      body: JSON.stringify({ source: 'reddit', title, content }),
    });
    resultEl.innerHTML = `<pre>${escHtml(JSON.stringify(res, null, 2))}</pre>`;
  } catch (e) {
    resultEl.innerHTML = `❌ Error: ${e.message}`;
  }
}

// ── LOGS ─────────────────────────────────────────────────────────

async function loadLogs() {
  const container = document.getElementById('log-list');
  try {
    const logs = await apiFetch('/api/logs?limit=100');
    if (!logs.length) {
      container.innerHTML = '<div class="text-sm text-muted">No activity logged yet.</div>';
      return;
    }
    container.innerHTML = logs.reverse().map(log => `
      <div class="log-item">
        <span class="log-time">${new Date(log.timestamp || Date.now()).toLocaleTimeString()}</span>
        <span class="log-msg ${log.level === 'error' ? 'error' : log.level === 'success' ? 'success' : ''}">${escHtml(log.message || JSON.stringify(log))}</span>
      </div>`).join('');
  } catch (e) {
    container.innerHTML = `<div class="text-sm" style="color:var(--danger);">Error: ${e.message}</div>`;
  }
}

// ── MODALS ────────────────────────────────────────────────────────

function openModal(id) { document.getElementById(id)?.classList.add('open'); }
function closeModal(id) { document.getElementById(id)?.classList.remove('open'); }

// Close modal on overlay click
document.querySelectorAll('.modal-overlay').forEach(overlay => {
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) overlay.classList.remove('open');
  });
});

// ── UTILITIES ─────────────────────────────────────────────────────

function escHtml(str) {
  if (str == null) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function timeAgo(isoStr) {
  if (!isoStr) return 'unknown';
  const ms = Date.now() - new Date(isoStr).getTime();
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

function intentLabel(tag) {
  const labels = {
    'buy-intent': '🎯 Buy Intent',
    'pain-point': '⚡ Pain Point',
    'competitor-complaint': '⚔️ Competitor',
    'question': '❓ Question',
    'praise': '👍 Praise',
    'seeking-alternatives': '🔀 Alternatives',
    'venting': '😤 Venting',
    'success-story': '✅ Success',
    'tool-review': '🔬 Review',
    'hiring': '💼 Hiring',
    'other': '• Other',
  };
  return labels[tag] || tag || 'Unknown';
}

function urgencyBadge(urgency) {
  const map = { High: '🔴 High', Medium: '🟡 Medium', Low: '🟢 Low' };
  return map[urgency] || urgency || '—';
}

// ── INIT ──────────────────────────────────────────────────────────

async function init() {
  await refreshSchedulerStatus();
  navigate('overview');

  // Refresh scheduler status every 30s
  setInterval(refreshSchedulerStatus, 30000);
}

document.addEventListener('DOMContentLoaded', init);
