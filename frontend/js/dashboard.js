document.addEventListener('DOMContentLoaded', async function () {
    await loadDashboard();
    setInterval(loadDashboard, 30000);
});

async function loadDashboard() {
    const data = await apiGet('/api/reports');
    if (!data) return;

    const s = data.summary || {};
    setText('totalViolations', s.total_violations || 0);
    setText('todayViolations', s.today_violations || 0);
    setText('totalCameras', s.total_cameras || 0);
    setText('activeCameras', s.active_cameras || 0);
    setText('highestSpeed', (s.highest_speed || 0) + ' km/h');

    const recent = data.recent_violations || [];
    const tbody = document.getElementById('recentViolations');
    if (!tbody) return;

    if (recent.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:#888;">No violations yet</td></tr>';
    } else {
        tbody.innerHTML = recent.map(v => `
            <tr>
                <td>${v.id}</td>
                <td>${esc(v.camera_name || '-')}</td>
                <td>${esc(v.vehicle_type || '-')}</td>
                <td>${esc(v.plate_number || 'N/A')}</td>
                <td style="color:#e74c3c;font-weight:600;">${esc(String(v.speed))} km/h</td>
                <td>${esc(String(v.speed_limit))} km/h</td>
                <td>${formatTime(v.violation_time)}</td>
                <td><span class="badge badge-${esc(v.status || 'pending')}">${esc(v.status || 'pending')}</span></td>
            </tr>
        `).join('');
    }
}

function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function formatTime(ts) {
    if (!ts) return '-';
    const d = new Date(ts);
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString();
}
