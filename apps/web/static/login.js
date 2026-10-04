const loginForm = document.getElementById('login-form');
const loginEmail = document.getElementById('email-input');
const loginPassword = document.getElementById('password-input');
const loginMessage = document.getElementById('login-message');
const loginHeading = document.getElementById('login-heading');
const loginSubmit = document.getElementById('login-submit');
const signInTab = document.getElementById('signin-tab');
const signUpTab = document.getElementById('signup-tab');
let authMode = 'login';

function setAuthMode(mode) {
  authMode = mode;
  const creatingAccount = mode === 'register';
  loginHeading.textContent = creatingAccount ? 'Create your account' : 'Welcome back';
  loginSubmit.textContent = creatingAccount ? 'Create account' : 'Sign in';
  loginPassword.autocomplete = creatingAccount ? 'new-password' : 'current-password';
  signInTab.classList.toggle('active', !creatingAccount);
  signUpTab.classList.toggle('active', creatingAccount);
  loginMessage.textContent = creatingAccount ? 'Your 7-day free trial starts when your account is created.' : '';
}

signInTab.addEventListener('click', () => setAuthMode('login'));
signUpTab.addEventListener('click', () => setAuthMode('register'));

loginForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  loginSubmit.disabled = true;
  loginMessage.textContent = authMode === 'register' ? 'Creating your account...' : 'Signing in...';
  try {
    const response = await fetch(`/api/auth/${authMode}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ email: loginEmail.value, password: loginPassword.value }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Could not authenticate.');
    window.location.assign('/');
  } catch (error) {
    loginMessage.textContent = error.message;
    loginSubmit.disabled = false;
  }
});

fetch('/api/auth/me', { credentials: 'same-origin' })
  .then((response) => response.json())
  .then((data) => {
    if (data.user) window.location.replace('/');
  })
  .catch(() => {
    loginMessage.textContent = 'Could not check your session. Please try signing in.';
  });