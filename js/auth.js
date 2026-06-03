(function () {
  const isLoginPage = location.pathname.endsWith("login.html") || location.pathname.endsWith("/login.html") || document.getElementById("loginForm");
  const protectedPage = document.body.dataset.protected === "true";

  function logout() {
    sessionStorage.removeItem("nexaSession");
    location.href = "login.html";
  }

  function readSession() {
    try {
      return JSON.parse(sessionStorage.getItem("nexaSession") || "null");
    } catch (e) {
      return null;
    }
  }

  if (protectedPage) {
    const session = readSession();
    if (!session) {
      location.href = "login.html";
      return;
    }

    const welcome = document.getElementById("welcomeUser");
    const lastLogin = document.getElementById("lastLogin");
    if (welcome) welcome.textContent = "Hello, " + (session.customerId || "Customer");
    if (lastLogin) lastLogin.textContent = "Last login: " + session.loginTime;

    document.getElementById("logoutBtn")?.addEventListener("click", logout);
    document.getElementById("sidebarLogout")?.addEventListener("click", (e) => {
      e.preventDefault();
      logout();
    });
  }

  if (!isLoginPage) return;

  const loginTabs = document.querySelectorAll(".tab-btn");
  const loginForm = document.getElementById("loginForm");
  const customerId = document.getElementById("customerId");
  const password = document.getElementById("password");
  const togglePassword = document.getElementById("togglePassword");
  const loginBtn = document.getElementById("loginBtn");
  const demoBtn = document.getElementById("demoBtn");
  const loginMsg = document.getElementById("loginMsg");

  let accountType = "Personal";

  loginTabs.forEach((btn) => {
    btn.addEventListener("click", () => {
      loginTabs.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      accountType = btn.dataset.type;
    });
  });

  togglePassword?.addEventListener("click", () => {
    const reveal = password.type === "password";
    password.type = reveal ? "text" : "password";
    togglePassword.textContent = reveal ? "Hide" : "Show";
  });

  function completeLogin(id) {
    const session = {
      customerId: id,
      accountType,
      loginTime: new Date().toLocaleString()
    };
    sessionStorage.setItem("nexaSession", JSON.stringify(session));
    location.href = "dashboard.html";
  }

  loginForm?.addEventListener("submit", (e) => {
    e.preventDefault();
    const id = customerId.value.trim();
    const pass = password.value.trim();
    if (!id || !pass) {
      loginMsg.textContent = "Please enter both Customer ID and Password.";
      loginMsg.style.color = "#b91c1c";
      return;
    }

    loginBtn.disabled = true;
    loginBtn.innerHTML = '<span class="loading"></span> Verifying...';
    loginMsg.textContent = "";

    setTimeout(() => {
      completeLogin(id);
    }, 1800);
  });

  demoBtn?.addEventListener("click", () => {
    completeLogin("DemoUser01");
  });
})();
