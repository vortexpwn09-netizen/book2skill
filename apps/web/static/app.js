const compileForm = document.getElementById('compile-form');
const resultOutput = document.getElementById('result-output');
const apiStatus = document.getElementById('api-status');
const titleInput = document.getElementById('title-input');
const textInput = document.getElementById('text-input');
const compileSampleButton = document.getElementById('compile-sample');
const pdfInput = document.getElementById('pdf-input');
const choosePdfButton = document.getElementById('choose-pdf');
const fileName = document.getElementById('file-name');
const downloadOutput = document.getElementById('download-output');
const downloadHeader = document.getElementById('download-header');
const accountButton = document.getElementById('account-button');
const accountStatus = document.getElementById('account-status');
const authDialog = document.getElementById('auth-dialog');
const authForm = document.getElementById('auth-form');
const authTitle = document.getElementById('auth-title');
const authEmail = document.getElementById('auth-email');
const authPassword = document.getElementById('auth-password');
const authMessage = document.getElementById('auth-message');
const authSubmit = document.getElementById('auth-submit');
const loginTab = document.getElementById('login-tab');
const registerTab = document.getElementById('register-tab');
const premiumPrice = document.getElementById('premium-price');
const freePlanPrice = document.getElementById('free-plan-price');
const trialPolicy = document.getElementById('trial-policy');
const upgradeButton = document.getElementById('upgrade-button');
let skillMarkdown = '';
let currentUser = null;
let authMode = 'login';
let freeTrialDays = 7;
let ipTrialCooldownDays = 365;
let checkoutConfigured = false;

function setDownloadReady(ready) {
  downloadOutput.disabled = !ready;
  downloadHeader.disabled = !ready;
}

pdfInput.addEventListener('change', () => {
  const file = pdfInput.files[0];
  fileName.textContent = file ? `${file.name} (${(file.size / 1024 / 1024).toFixed(1)} MB)` : 'Choose a searchable PDF (up to 25 MB)';
});

choosePdfButton.addEventListener('click', () => {
  if (!currentUser) {
    openAuth('login', 'Sign in or create an account before uploading a PDF.');
    return;
  }
  pdfInput.click();
});

function setAuthMode(mode) {
  authMode = mode;
  const registering = mode === 'register';
  authTitle.textContent = registering ? 'Create your account' : 'Sign in';
  authSubmit.textContent = registering ? 'Create account' : 'Sign in';
  authPassword.autocomplete = registering ? 'new-password' : 'current-password';
  loginTab.classList.toggle('active', !registering);
  registerTab.classList.toggle('active', registering);
}

function openAuth(mode = 'login', message = '') {
  setAuthMode(mode);
  authMessage.textContent = message;
  if (!authDialog.open) authDialog.showModal();
}

function updateAccountUI() {
  accountButton.textContent = currentUser ? 'Sign out' : 'Sign in';
  freePlanPrice.textContent = `${freeTrialDays} days free`;
  trialPolicy.textContent = `One free trial per network address every ${ipTrialCooldownDays} days. We store a protected one-way fingerprint, not the raw IP address.`;
  if (!currentUser) {
    accountStatus.textContent = 'Sign in to use the compiler.';
    upgradeButton.textContent = 'Subscribe to Premium';
    upgradeButton.disabled = false;
    return;
  }

  const planName = currentUser.plan === 'premium'
    ? 'Premium'
    : currentUser.plan === 'trial'
      ? 'Free trial'
      : 'Trial ended';
  const usage = currentUser.plan === 'premium'
    ? 'Unlimited compilations'
    : currentUser.plan === 'trial'
      ? `${currentUser.trial_days_remaining} days remaining`
      : 'Upgrade to Premium to continue compiling';
  accountStatus.textContent = `${currentUser.email} · ${planName} · ${usage}`;
  upgradeButton.textContent = currentUser.plan === 'premium' ? 'Manage subscription' : 'Subscribe to Premium';
  upgradeButton.disabled = false;
}

async function refreshSession() {
  const response = await fetch('/api/auth/me', { credentials: 'same-origin' });
  const data = await response.json();
  currentUser = data.user;
  freeTrialDays = data.free_trial_days || freeTrialDays;
  ipTrialCooldownDays = data.ip_trial_cooldown_days || ipTrialCooldownDays;
  premiumPrice.textContent = data.premium_price_label || 'Premium subscription';
  updateAccountUI();
}

async function loadBillingPlans() {
  try {
    const response = await fetch('/api/billing/plans');
    const plans = await response.json();
    freeTrialDays = plans.free_trial_days || freeTrialDays;
    ipTrialCooldownDays = plans.ip_trial_cooldown_days || ipTrialCooldownDays;
    premiumPrice.textContent = plans.premium_price_label || 'Premium subscription';
    checkoutConfigured = Boolean(plans.checkout_configured);
    updateAccountUI();
  } catch (error) {
    accountStatus.textContent = 'Could not load plan details.';
  }
}

loginTab.addEventListener('click', () => setAuthMode('login'));
registerTab.addEventListener('click', () => setAuthMode('register'));
document.getElementById('auth-close').addEventListener('click', () => authDialog.close());

authForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  authMessage.textContent = authMode === 'register' ? 'Creating account...' : 'Signing in...';
  try {
    const response = await fetch(`/api/auth/${authMode}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ email: authEmail.value, password: authPassword.value }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Account request failed.');
    await refreshSession();
    authDialog.close();
    authForm.reset();
  } catch (error) {
    authMessage.textContent = error.message;
  }
});

accountButton.addEventListener('click', async () => {
  if (!currentUser) {
    openAuth('login');
    return;
  }
  await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' });
  currentUser = null;
  updateAccountUI();
  window.location.assign('/login');
});

upgradeButton.addEventListener('click', async () => {
  if (!currentUser) {
    openAuth('register', 'Create a free account first, then choose Premium.');
    return;
  }
  if (currentUser.plan === 'premium') {
    try {
      const response = await fetch('/api/billing/portal', { method: 'POST', credentials: 'same-origin' });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Could not open subscription management.');
      window.location.assign(data.portal_url);
    } catch (error) {
      accountStatus.textContent = error.message;
    }
    return;
  }
  if (!checkoutConfigured) {
    accountStatus.textContent = 'Premium checkout is not configured yet. Add Stripe keys to the server environment.';
    return;
  }
  upgradeButton.disabled = true;
  try {
    const response = await fetch('/api/billing/checkout', {
      method: 'POST',
      credentials: 'same-origin',
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Could not start checkout.');
    window.location.assign(data.checkout_url);
  } catch (error) {
    accountStatus.textContent = error.message;
    upgradeButton.disabled = false;
  }
});

async function checkApi() {
  try {
    const response = await fetch('/health');
    if (response.ok) {
      const payload = await response.json();
      apiStatus.textContent = payload.status === 'ok' ? 'API online' : 'API check';
      apiStatus.style.color = '#aaf7d3';
    } else {
      throw new Error('Health check failed');
    }
  } catch (error) {
    apiStatus.textContent = 'API offline';
    apiStatus.style.color = '#ffd3d3';
  }
}

function renderPackageSummary(payload) {
  const conceptCount = payload.concepts?.length ?? 0;
  const principleCount = payload.principles?.length ?? 0;
  const methodCount = payload.methods?.length ?? 0;

  resultOutput.textContent = JSON.stringify(
    {
      title: payload.title,
      concepts: payload.concepts?.slice(0, 5) ?? [],
      principles: payload.principles?.slice(0, 5) ?? [],
      methods: payload.methods?.slice(0, 5) ?? [],
      summary: {
        conceptCount,
        principleCount,
        methodCount,
      },
    },
    null,
    2,
  );
}

async function compileDocument(event) {
  event.preventDefault();
  if (!currentUser) {
    openAuth('login', 'Sign in to compile a PDF or source text.');
    return;
  }
  const file = pdfInput.files[0];
  resultOutput.textContent = file ? 'Reading PDF and compiling knowledge...' : 'Compiling knowledge package...';
  skillMarkdown = '';
  setDownloadReady(false);

  try {
    let response;
    if (file) {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('title', titleInput.value.trim());
      response = await fetch('/compile/pdf', { method: 'POST', body: formData });
    } else {
      response = await fetch('/compile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: titleInput.value.trim() || 'Untitled Knowledge Source',
          text: textInput.value.trim(),
          max_items: 10,
        }),
      });
    }

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Compilation failed');
    }

    const data = await response.json();
    const packageData = data.package || data;
    skillMarkdown = data.skill_markdown || '';
    setDownloadReady(Boolean(skillMarkdown));
    renderPackageSummary(packageData);
    await refreshSession();
  } catch (error) {
    resultOutput.textContent = `Compilation error: ${error.message}`;
    if (error.message.includes('free trial')) {
      accountStatus.textContent = error.message;
      document.getElementById('pricing').scrollIntoView({ behavior: 'smooth' });
    }
  }
}

function downloadSkill() {
  if (!skillMarkdown) return;
  const blob = new Blob([skillMarkdown], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'SKILL.md';
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

downloadOutput.addEventListener('click', downloadSkill);
downloadHeader.addEventListener('click', downloadSkill);

compileForm.addEventListener('submit', compileDocument);
compileSampleButton.addEventListener('click', () => {
  titleInput.value = 'Deep Work';
  textInput.value = 'AI agents use context and memory. Principle: keep actions focused. Method: plan first, then execute with discipline.';
  compileDocument(new Event('submit'));
});

checkApi();
refreshSession().catch(() => {
  accountStatus.textContent = 'Could not check your account session.';
});
loadBillingPlans();
