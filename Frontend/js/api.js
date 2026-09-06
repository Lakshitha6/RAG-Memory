// ── API base ───────────────────────────────────────────────
const API_BASE = CONFIG.API_BASE;

function getToken() {
  return sessionStorage.getItem('access_token');
}

function authHeaders(extra = {}) {
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${getToken()}`,
    ...extra,
  };
}

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (res.status === 401) {
    // Token expired or invalid — clear session and redirect to login
    sessionStorage.clear();
    window.location.href = '/index.html';
    return;
  }
  return res;
}

// ── Auth ───────────────────────────────────────────────────
async function apiRegister(name, email, password) {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, email, password }),
  });
  return { ok: res.ok, data: await res.json() };
}

async function apiLogin(email, password) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  return { ok: res.ok, data: await res.json() };
}

async function apiLogout(sessionId) {
  await apiFetch('/auth/logout', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ session_id: sessionId }),
  });
}

// ── Sessions ───────────────────────────────────────────────
async function apiGetSessions() {
  const res = await apiFetch('/sessions', { headers: authHeaders() });
  if (!res || !res.ok) return [];
  const data = await res.json();
  return data.sessions || [];
}

async function apiGetSessionMessages(sessionId) {
  const res = await apiFetch(`/sessions/${sessionId}/messages`, {
    headers: authHeaders(),
  });
  if (!res || !res.ok) return [];
  const data = await res.json();
  return data.messages || [];
}

async function apiDeleteSession(sessionId) {
  const res = await apiFetch(`/sessions/${sessionId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
  return res && res.ok;
}

// ── Chat streaming ─────────────────────────────────────────
// Calls onSession(sessionId), onToken(chunk), onDone() as SSE events arrive.
async function apiStreamChat(question, sessionId, { onSession, onToken, onDone, onError }) {
  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ question, session_id: sessionId || null }),
    });

    if (res.status === 401) {
      sessionStorage.clear();
      window.location.href = '/index.html';
      return;
    }

    if (!res.ok) {
      onError && onError('Server error — please try again.');
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop(); // keep incomplete last chunk

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const raw = line.slice(6).trim();
        if (!raw) continue;

        try {
          const event = JSON.parse(raw);
          if (event.type === 'session') {
            onSession && onSession(event.session_id);
          } else if (event.type === 'token') {
            onToken && onToken(event.content);
          } else if (event.type === 'done') {
            onDone && onDone();
          } else if (event.type === 'error') {
            onError && onError(event.content);
          }
        } catch {
          // Ignore malformed lines
        }
      }
    }
  } catch (err) {
    onError && onError('Connection error — check if the server is running.');
  }
}