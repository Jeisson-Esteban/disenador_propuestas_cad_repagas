/* Autenticacion compartida entre paginas (home, formulario, historico, admin).
 *
 * URL del backend se lee desde `window.APP_CONFIG.API_URL` definido en
 * `config.js` (copia `config.js.example` -> `config.js` antes de servir).
 * Si `config.js` no esta cargado, asumimos backend local.
 */

const API_URL = (window.APP_CONFIG && window.APP_CONFIG.API_URL) || "http://localhost:8000";

function apiUrl(path) {
  return API_URL + path;
}

function checkAuth() {
  if (sessionStorage.getItem("repagas_auth") === "ok") {
    const login = document.getElementById("loginScreen");
    const app = document.getElementById("appContainer");
    if (login) login.style.display = "none";
    if (app) app.style.display = "";
    return true;
  }
  return false;
}

function logout() {
  sessionStorage.removeItem("repagas_auth");
  window.location.href = "index.html";
}

document.addEventListener("DOMContentLoaded", () => {
  checkAuth();

  const btnLogin = document.getElementById("btnLogin");
  if (btnLogin) {
    btnLogin.addEventListener("click", doLogin);
    document.getElementById("loginPass").addEventListener("keydown", (e) => {
      if (e.key === "Enter") doLogin();
    });
    document.getElementById("loginUser").addEventListener("keydown", (e) => {
      if (e.key === "Enter") document.getElementById("loginPass").focus();
    });
  }
});

async function doLogin() {
  const user = document.getElementById("loginUser").value.trim();
  const pass = document.getElementById("loginPass").value;
  const btn = document.getElementById("btnLogin");
  btn.disabled = true;
  btn.textContent = "Verificando...";
  try {
    const resp = await fetch(apiUrl("/login"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user, pass }),
    });
    if (resp.ok) {
      sessionStorage.setItem("repagas_auth", "ok");
      document.getElementById("loginScreen").style.display = "none";
      document.getElementById("appContainer").style.display = "";
      document.getElementById("loginError").style.display = "none";
    } else {
      document.getElementById("loginError").style.display = "";
      document.getElementById("loginPass").value = "";
      document.getElementById("loginPass").focus();
    }
  } catch (e) {
    const err = document.getElementById("loginError");
    err.textContent = "No se pudo conectar al servidor";
    err.style.display = "";
  } finally {
    btn.disabled = false;
    btn.textContent = "Entrar";
  }
}
