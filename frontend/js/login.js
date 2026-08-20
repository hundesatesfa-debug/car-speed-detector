document.addEventListener('DOMContentLoaded', async function () {
    const form = document.getElementById('loginForm');
    if (form) {
        form.addEventListener('submit', async function (e) {
            e.preventDefault();
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            const errDiv = document.getElementById('error');

            if (!username || !password) {
                errDiv.textContent = 'Username and password are required';
                errDiv.style.display = 'block';
                return;
            }

            try {
                const res = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password }),
                });
                const data = await res.json();
                if (res.ok && data.token) {
                    localStorage.setItem('token', data.token);
                    localStorage.setItem('user', JSON.stringify(data.user));
                    window.location.href = '/pages/dashboard.html';
                } else if (res.status === 429) {
                    errDiv.textContent = data.error || 'Too many attempts. Please wait.';
                    errDiv.style.display = 'block';
                } else {
                    errDiv.textContent = data.error || 'Invalid credentials';
                    errDiv.style.display = 'block';
                }
            } catch (err) {
                errDiv.textContent = 'Connection error';
                errDiv.style.display = 'block';
            }
        });
    }
});
