const API = '';

function getToken() {
    return localStorage.getItem('token');
}

function setToken(token) {
    localStorage.setItem('token', token);
}

function clearToken() {
    localStorage.removeItem('token');
}

function authHeaders() {
    return {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + getToken(),
    };
}

function esc(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
}

function logout() {
    const token = getToken();
    if (token) {
        fetch('/api/auth/logout', {
            method: 'POST',
            headers: { 'Authorization': 'Bearer ' + token },
        }).catch(() => {});
    }
    clearToken();
    localStorage.removeItem('user');
    window.location.href = '/login.html';
}

async function apiGet(url) {
    const res = await fetch(API + url, { headers: authHeaders() });
    if (res.status === 401) { logout(); return null; }
    if (res.status === 429) { alert('Too many requests. Please wait and try again.'); return null; }
    return res.json();
}

async function apiPost(url, data) {
    const res = await fetch(API + url, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify(data),
    });
    if (res.status === 401) { logout(); return null; }
    if (res.status === 429) { alert('Too many requests. Please wait and try again.'); return null; }
    return res.json();
}

async function apiPut(url, data) {
    const res = await fetch(API + url, {
        method: 'PUT',
        headers: authHeaders(),
        body: JSON.stringify(data),
    });
    if (res.status === 401) { logout(); return null; }
    if (res.status === 429) { alert('Too many requests. Please wait and try again.'); return null; }
    return res.json();
}

async function apiDelete(url) {
    const res = await fetch(API + url, {
        method: 'DELETE',
        headers: authHeaders(),
    });
    if (res.status === 401) { logout(); return null; }
    if (res.status === 429) { alert('Too many requests. Please wait and try again.'); return null; }
    return res.json();
}

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    sidebar.classList.toggle('open');
    if (overlay) overlay.style.display = sidebar.classList.contains('open') ? 'block' : 'none';
}

function closeSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    if (sidebar) sidebar.classList.remove('open');
    if (overlay) overlay.style.display = 'none';
}

if (!getToken()) {
    if (!window.location.pathname.includes('login.html')) {
        window.location.href = '/login.html';
    }
}
