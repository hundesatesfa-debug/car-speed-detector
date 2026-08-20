document.addEventListener('DOMContentLoaded', async function () {
    await loadReports();
});

async function loadReports() {
    const data = await apiGet('/api/reports');
    if (!data) return;

    const s = data.summary || {};
    setText('totalViolations', s.total_violations || 0);
    setText('totalCameras', s.total_cameras || 0);
    setText('activeCameras', s.active_cameras || 0);
    setText('avgSpeed', (s.average_speed || 0) + ' km/h');

    renderBarChart('byCameraChart', data.by_camera || [], 'name', 'violation_count');
    renderBarChart('byTypeChart', data.by_vehicle_type || [], 'vehicle_type', 'count');

    const topPlates = data.top_plates || [];
    const topEl = document.getElementById('topPlates');
    if (topEl) {
        topEl.innerHTML = topPlates.length === 0
            ? '<tr><td colspan="3" style="text-align:center;color:#888;">No data</td></tr>'
            : topPlates.map(p => `<tr><td>${esc(p.plate_number)}</td><td>${p.count}</td><td>${esc(String(p.max_speed))} km/h</td></tr>`).join('');
    }

    const recent = data.recent_violations || [];
    const recentEl = document.getElementById('recentViolations');
    if (recentEl) {
        recentEl.innerHTML = recent.length === 0
            ? '<tr><td colspan="6" style="text-align:center;color:#888;">No data</td></tr>'
            : recent.map(v => `
                <tr>
                    <td>${v.id}</td>
                    <td>${esc(v.camera_name || '-')}</td>
                    <td>${esc(v.plate_number || 'N/A')}</td>
                    <td style="color:#e74c3c;font-weight:600;">${esc(String(v.speed))} km/h</td>
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

function renderBarChart(containerId, items, labelKey, valueKey) {
    const container = document.getElementById(containerId);
    if (!container) return;
    if (items.length === 0) {
        container.innerHTML = '<div style="text-align:center;color:#888;padding:40px;">No data</div>';
        return;
    }
    const maxVal = Math.max(...items.map(i => i[valueKey] || 0), 1);
    container.innerHTML = items.map(item => {
        const val = item[valueKey] || 0;
        const height = Math.max(4, (val / maxVal) * 180);
        return `<div class="bar-wrapper">
            <div class="bar-value">${val}</div>
            <div class="bar" style="height:${height}px;"></div>
            <div class="bar-label">${esc(item[labelKey] || '')}</div>
        </div>`;
    }).join('');
}

function formatTime(ts) {
    if (!ts) return '-';
    const d = new Date(ts);
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString();
}
