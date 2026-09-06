// ── Session sidebar ────────────────────────────────────────
let _sessions = [];
let _activeSessionId = null;

const sessionsList = document.getElementById('sessionsList');

function formatDate(iso) {
  const d = new Date(iso);
  const now = new Date();
  const diff = now - d;
  if (diff < 60000)             return 'Just now';
  if (diff < 3600000)           return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000)          return `${Math.floor(diff / 3600000)}h ago`;
  if (diff < 604800000)         return `${Math.floor(diff / 86400000)}d ago`;
  return d.toLocaleDateString();
}

async function loadSessions() {
  _sessions = await apiGetSessions();
  renderSessions();
}

function renderSessions() {
  if (_sessions.length === 0) {
    sessionsList.innerHTML = `
      <div class="sessions-empty">
        No conversations yet.<br>Start a new chat to begin.
      </div>`;
    return;
  }

  sessionsList.innerHTML = _sessions.map(s => `
    <div class="session-item ${s.session_id === _activeSessionId ? 'active' : ''}"
         data-id="${s.session_id}">
      <span class="session-icon">💬</span>
      <div class="session-info">
        <div class="session-title">${escapeHtml(s.title || 'Untitled')}</div>
        <div class="session-date">${formatDate(s.started_at)}</div>
      </div>
      <button class="session-delete" data-id="${s.session_id}" title="Delete">✕</button>
    </div>
  `).join('');

  // Click session → load it
  sessionsList.querySelectorAll('.session-item').forEach(el => {
    el.addEventListener('click', e => {
      if (e.target.classList.contains('session-delete')) return;
      loadSession(el.dataset.id);
    });
  });

  // Delete session
  sessionsList.querySelectorAll('.session-delete').forEach(btn => {
    btn.addEventListener('click', async e => {
      e.stopPropagation();
      const id = btn.dataset.id;
      if (!confirm('Delete this conversation?')) return;
      const ok = await apiDeleteSession(id);
      if (ok) {
        _sessions = _sessions.filter(s => s.session_id !== id);
        if (_activeSessionId === id) {
          _activeSessionId = null;
          startNewChat();
        }
        renderSessions();
      }
    });
  });
}

function setActiveSession(sessionId) {
  _activeSessionId = sessionId;
  // Update sidebar highlight without full re-render
  sessionsList.querySelectorAll('.session-item').forEach(el => {
    el.classList.toggle('active', el.dataset.id === sessionId);
  });
}

function prependSession(sessionId, title) {
  // Add new session to top of list without refetching
  const exists = _sessions.find(s => s.session_id === sessionId);
  if (!exists) {
    _sessions.unshift({
      session_id: sessionId,
      title: title,
      started_at: new Date().toISOString(),
      is_active: true,
    });
    renderSessions();
  }
  setActiveSession(sessionId);
}

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}