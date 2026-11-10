const loginTab = document.querySelector("#login-tab");
const registerTab = document.querySelector("#register-tab");
const loginPanel = document.querySelector("#login-panel");
const registerPanel = document.querySelector("#register-panel");
const errorModal = document.querySelector("#error-modal");
const errorMessage = document.querySelector("#error-message");
const closeError = document.querySelector("#close-error");
const closeErrorAction = document.querySelector("#close-error-action");

function showError(message) {
  errorMessage.textContent = message;
  errorModal.hidden = false;
  closeErrorAction.focus();
}

function hideError() {
  errorModal.hidden = true;
}

closeError.addEventListener("click", hideError);
closeErrorAction.addEventListener("click", hideError);
errorModal.addEventListener("click", (event) => {
  if (event.target === errorModal) {
    hideError();
  }
});

function showPanel(panel) {
  const isLogin = panel === loginPanel;
  loginPanel.hidden = !isLogin;
  registerPanel.hidden = isLogin;
  loginTab.classList.toggle("auth-tab--active", isLogin);
  registerTab.classList.toggle("auth-tab--active", !isLogin);
  loginTab.setAttribute("aria-selected", String(isLogin));
  registerTab.setAttribute("aria-selected", String(!isLogin));
}

loginTab.addEventListener("click", () => showPanel(loginPanel));
registerTab.addEventListener("click", () => showPanel(registerPanel));

function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

loginPanel.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(loginPanel);
  const email = String(formData.get("email") || "").trim();
  const password = String(formData.get("password") || "");

  if (!email || !isValidEmail(email)) {
    showError("Please enter a valid email address.");
    return;
  }
  if (!password) {
    showError("Please enter your password.");
    return;
  }

  const response = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email,
      password,
    }),
  });

  const result = await response.json();
  if (!response.ok) {
    showError(result.detail || "Unable to log in.");
    return;
  }
  loginPanel.querySelector(".auth-message").textContent = "Login successful.";
  window.location.href = "/";
});

registerPanel.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(registerPanel);
  const name = String(formData.get("name") || "").trim();
  const email = String(formData.get("email") || "").trim();
  const password = String(formData.get("password") || "");

  if (!name) {
    showError("Please enter your full name.");
    return;
  }
  if (!email || !isValidEmail(email)) {
    showError("Please enter a valid email address.");
    return;
  }
  if (password.length < 8) {
    showError("Your password must be at least 8 characters long.");
    return;
  }

  const response = await fetch("/api/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      full_name: name,
      email,
      password,
    }),
  });

  const result = await response.json();
  if (!response.ok) {
    showError(result.detail || "Unable to register.");
    return;
  }
  registerPanel.querySelector(".auth-message").textContent =
    "Registration successful. You can now log in.";
  showPanel(loginPanel);
});
