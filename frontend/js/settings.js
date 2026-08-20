document.addEventListener('DOMContentLoaded', async function () {
    await loadProfile();

    document.getElementById('profileForm').addEventListener('submit', handleUpdate);
});

async function loadProfile() {
    const data = await apiGet('/api/auth/me');
    if (!data || !data.user) return;

    const u = data.user;
    document.getElementById('userInfo').innerHTML =
        '<strong>Username:</strong> ' + esc(u.username) +
        ' &nbsp;|&nbsp; <strong>Role:</strong> ' + esc(u.role) +
        ' &nbsp;|&nbsp; <strong>Status:</strong> ' + esc(u.status) +
        ' &nbsp;|&nbsp; <strong>Joined:</strong> ' + new Date(u.created_at).toLocaleDateString();

    document.getElementById('newUsername').placeholder = u.username;
}

async function handleUpdate(e) {
    e.preventDefault();
    const errDiv = document.getElementById('msg');
    const okDiv = document.getElementById('successMsg');
    errDiv.style.display = 'none';
    okDiv.style.display = 'none';

    const currentPassword = document.getElementById('currentPassword').value;
    const newUsername = document.getElementById('newUsername').value.trim();
    const newPassword = document.getElementById('newPassword').value.trim();
    const confirmPassword = document.getElementById('confirmPassword').value.trim();

    if (newPassword && newPassword !== confirmPassword) {
        errDiv.textContent = 'New passwords do not match';
        errDiv.style.display = 'block';
        return;
    }

    const body = { current_password: currentPassword };
    if (newUsername) body.username = newUsername;
    if (newPassword) body.password = newPassword;

    const result = await apiPut('/api/auth/update-profile', body);
    if (!result) return;

    if (result.error) {
        errDiv.textContent = result.error;
        errDiv.style.display = 'block';
        return;
    }

    if (result.user) {
        localStorage.setItem('user', JSON.stringify(result.user));
    }

    okDiv.textContent = 'Profile updated successfully';
    okDiv.style.display = 'block';
    document.getElementById('currentPassword').value = '';
    document.getElementById('newPassword').value = '';
    document.getElementById('confirmPassword').value = '';

    await loadProfile();
}
