// Redirect if already logged in
if (sessionStorage.getItem('access_token')) {
    window.location.href = '/chat.html';
  }
  
  // ── Tab switching ──────────────────────────────────────────
  const tabs      = document.querySelectorAll('.auth-tab');
  const loginForm = document.getElementById('loginForm');
  const regForm   = document.getElementById('registerForm');
  
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const which = tab.dataset.tab;
      loginForm.classList.toggle('hidden', which !== 'login');
      regForm.classList.toggle('hidden',   which !== 'register');
      clearErrors();
    });
  });
  
  function clearErrors() {
    document.querySelectorAll('.auth-error').forEach(el => el.classList.remove('show'));
  }
  
  function showError(id, msg) {
    const el = document.getElementById(id);
    el.textContent = msg;
    el.classList.add('show');
  }
  
  function setLoading(btn, loading) {
    btn.disabled = loading;
    btn.textContent = loading ? 'Please wait…' : btn.dataset.label;
  }
  
  // ── Login ──────────────────────────────────────────────────
  const loginBtn = document.getElementById('loginBtn');
  loginBtn.dataset.label = loginBtn.textContent;
  
  loginBtn.addEventListener('click', async () => {
    clearErrors();
    const email    = document.getElementById('loginEmail').value.trim();
    const password = document.getElementById('loginPassword').value;
  
    if (!email || !password) {
      showError('loginError', 'Please fill in all fields.');
      return;
    }
  
    setLoading(loginBtn, true);
    const { ok, data } = await apiLogin(email, password);
    setLoading(loginBtn, false);
  
    if (!ok) {
      showError('loginError', data.detail || 'Login failed.');
      return;
    }
  
    sessionStorage.setItem('access_token', data.access_token);
    sessionStorage.setItem('user_id',      data.user_id);
    sessionStorage.setItem('user_name',    data.name);
    sessionStorage.setItem('user_email',   data.email);
    window.location.href = '/chat.html';
  });
  
  // ── Register ───────────────────────────────────────────────
  const regBtn = document.getElementById('registerBtn');
  regBtn.dataset.label = regBtn.textContent;
  
  regBtn.addEventListener('click', async () => {
    clearErrors();
    const name     = document.getElementById('regName').value.trim();
    const email    = document.getElementById('regEmail').value.trim();
    const password = document.getElementById('regPassword').value;
  
    if (!name || !email || !password) {
      showError('registerError', 'Please fill in all fields.');
      return;
    }
    if (password.length < 8) {
      showError('registerError', 'Password must be at least 8 characters.');
      return;
    }
  
    setLoading(regBtn, true);
    const { ok, data } = await apiRegister(name, email, password);
    setLoading(regBtn, false);
  
    if (!ok) {
      showError('registerError', data.detail || 'Registration failed.');
      return;
    }
  
    sessionStorage.setItem('access_token', data.access_token);
    sessionStorage.setItem('user_id',      data.user_id);
    sessionStorage.setItem('user_name',    data.name);
    sessionStorage.setItem('user_email',   data.email);
    window.location.href = '/chat.html';
  });
  
  // Submit on Enter key
  document.addEventListener('keydown', e => {
    if (e.key !== 'Enter') return;
    const activeTab = document.querySelector('.auth-tab.active').dataset.tab;
    if (activeTab === 'login')    loginBtn.click();
    if (activeTab === 'register') regBtn.click();
  });