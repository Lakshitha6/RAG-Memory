// Guard — redirect to login if not authenticated
if (!sessionStorage.getItem('access_token')) {
    window.location.href = '/index.html';
  }
  
  // ── State ──────────────────────────────────────────────────
  let currentSessionId = null;
  let isStreaming      = false;
  
  // ── DOM refs ───────────────────────────────────────────────
  const messagesArea   = document.getElementById('messagesArea');
  const messagesInner  = document.getElementById('messagesInner');
  const messageInput   = document.getElementById('messageInput');
  const sendBtn        = document.getElementById('sendBtn');
  const chatTitle      = document.getElementById('chatTitle');
  const welcomeState   = document.getElementById('welcomeState');
  const userName       = document.getElementById('userName');
  const userEmail      = document.getElementById('userEmail');
  const userAvatar     = document.getElementById('userAvatar');
  const logoutBtn      = document.getElementById('logoutBtn');
  const newChatBtn     = document.getElementById('newChatBtn');
  
  // ── Init ───────────────────────────────────────────────────
  function init() {
    const name  = sessionStorage.getItem('user_name')  || 'User';
    const email = sessionStorage.getItem('user_email') || '';
  
    userName.textContent  = name;
    userEmail.textContent = email;
    userAvatar.textContent = name.charAt(0).toUpperCase();
  
    loadSessions();
    showWelcome();
  }
  
  // ── Welcome state ──────────────────────────────────────────
  function showWelcome() {
    welcomeState.classList.remove('hidden');
    messagesInner.innerHTML = '';
    chatTitle.textContent   = 'Student Handbook Assistant';
    currentSessionId        = null;
  }
  
  function hideWelcome() {
    welcomeState.classList.add('hidden');
  }
  
  // ── New chat ───────────────────────────────────────────────
  function startNewChat() {
    if (isStreaming) return;
    showWelcome();
    setActiveSession(null);
  }
  
  newChatBtn.addEventListener('click', startNewChat);
  
  // ── Load existing session ──────────────────────────────────
  async function loadSession(sessionId) {
    if (isStreaming) return;
  
    const messages = await apiGetSessionMessages(sessionId);
    currentSessionId = sessionId;
  
    const session = _sessions.find(s => s.session_id === sessionId);
    chatTitle.textContent = session?.title || 'Conversation';
  
    hideWelcome();
    messagesInner.innerHTML = '';
  
    messages.forEach(m => appendMessage(m.role, m.content, false));
    scrollToBottom();
    setActiveSession(sessionId);
  }
  
  // ── Message rendering ──────────────────────────────────────
  function appendMessage(role, content, animate = true) {
    const isUser = role === 'user';
    const label  = isUser ? 'You' : 'Assistant';
    const icon   = isUser ? '👤' : '🎓';
  
    const el = document.createElement('div');
    el.className = `message ${role}`;
    if (!animate) el.style.animation = 'none';
  
    el.innerHTML = `
      <div class="msg-avatar">${icon}</div>
      <div class="msg-body">
        <div class="msg-role">${label}</div>
        <div class="msg-content">${escapeHtml(content)}</div>
      </div>
    `;
  
    messagesInner.appendChild(el);
    scrollToBottom();
    return el;
  }
  
  function appendStreamingMessage() {
    // Creates an empty assistant bubble that gets filled token by token
    const el = document.createElement('div');
    el.className = 'message assistant';
    el.innerHTML = `
      <div class="msg-avatar">🎓</div>
      <div class="msg-body">
        <div class="msg-role">Assistant</div>
        <div class="msg-content"><span class="cursor"></span></div>
      </div>
    `;
    messagesInner.appendChild(el);
    scrollToBottom();
    return el.querySelector('.msg-content');
  }
  
  function scrollToBottom() {
    messagesArea.scrollTop = messagesArea.scrollHeight;
  }
  
  // ── Send message ───────────────────────────────────────────
  async function sendMessage() {
    const question = messageInput.value.trim();
    if (!question || isStreaming) return;
  
    hideWelcome();
    messageInput.value = '';
    messageInput.style.height = 'auto';
    setStreaming(true);
  
    // Show user message immediately
    appendMessage('user', question);
  
    // Create streaming assistant bubble
    const contentEl = appendStreamingMessage();
    let fullResponse = '';
    let sessionReceived = false;
  
    await apiStreamChat(question, currentSessionId, {
      onSession(sessionId) {
        // First event — store session and update sidebar
        if (!sessionReceived) {
          sessionReceived = true;
          const isNew = currentSessionId !== sessionId;
          currentSessionId = sessionId;
  
          if (isNew) {
            const shortTitle = question.length > 30
              ? question.slice(0, 30) + '...'
              : question;
            chatTitle.textContent = shortTitle;
            prependSession(sessionId, shortTitle);
          } else {
            setActiveSession(sessionId);
          }
        }
      },
  
      onToken(chunk) {
        fullResponse += chunk;
        // Remove cursor, set text, re-add cursor
        contentEl.innerHTML = escapeHtml(fullResponse) + '<span class="cursor"></span>';
        scrollToBottom();
      },
  
      onDone() {
        // Remove cursor, finalize
        contentEl.innerHTML = escapeHtml(fullResponse);
        contentEl.style.whiteSpace = 'pre-wrap';
        setStreaming(false);
      },
  
      onError(msg) {
        contentEl.innerHTML = `<span style="color:var(--danger)">${escapeHtml(msg)}</span>`;
        setStreaming(false);
      },
    });
  }
  
  function setStreaming(state) {
    isStreaming      = state;
    sendBtn.disabled = state;
    messageInput.disabled = state;
    if (!state) messageInput.focus();
  }
  
  // ── Input handling ─────────────────────────────────────────
  sendBtn.addEventListener('click', sendMessage);
  
  messageInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
  
  // Auto-resize textarea
  messageInput.addEventListener('input', () => {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 160) + 'px';
  });
  
  // ── Suggestion chips ───────────────────────────────────────
  document.querySelectorAll('.suggestion-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      messageInput.value = chip.textContent;
      sendMessage();
    });
  });
  
  // ── Logout ─────────────────────────────────────────────────
  logoutBtn.addEventListener('click', async () => {
    await apiLogout(currentSessionId);
    sessionStorage.clear();
    window.location.href = '/index.html';
  });


  // ── Mobile sidebar drawer ──────────────────────────────────
const sidebar         = document.querySelector('.sidebar');
const menuBtn         = document.getElementById('menuBtn');
const sidebarBackdrop = document.getElementById('sidebarBackdrop');

function openSidebar() {
  sidebar.classList.add('open');
  sidebarBackdrop.classList.add('show');
  document.body.style.overflow = 'hidden';
}

function closeSidebar() {
  sidebar.classList.remove('open');
  sidebarBackdrop.classList.remove('show');
  document.body.style.overflow = '';
}

menuBtn.addEventListener('click', openSidebar);
sidebarBackdrop.addEventListener('click', closeSidebar);

// Auto-close drawer when session or new chat tapped on mobile
document.getElementById('sessionsList').addEventListener('click', () => {
  if (window.innerWidth <= 640) closeSidebar();
});
document.getElementById('newChatBtn').addEventListener('click', () => {
  if (window.innerWidth <= 640) closeSidebar();
});
  
  // ── Start ──────────────────────────────────────────────────
  init();