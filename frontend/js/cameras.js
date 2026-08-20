document.addEventListener('DOMContentLoaded', async function () {
    const editForm = document.getElementById('editCameraForm');
    if (editForm) {
        editForm.addEventListener('submit', handleEditCamera);
        await loadCameraForEdit();
        return;
    }

    const addForm = document.getElementById('addCameraForm');
    if (addForm) {
        addForm.addEventListener('submit', handleAddCamera);
        return;
    }

    await loadCameras();
});

async function loadCameras() {
    const data = await apiGet('/api/cameras');
    if (!data) return;

    const cameras = data.cameras || [];
    const tbody = document.getElementById('camerasTable');

    if (cameras.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#888;">No cameras configured. Add one to get started.</td></tr>';
        return;
    }

    tbody.innerHTML = cameras.map(c => `
        <tr>
            <td>${c.id}</td>
            <td>${esc(c.camera_name)}</td>
            <td>${esc(c.location || '-')}</td>
            <td>${esc(String(c.speed_limit))} km/h</td>
            <td><span class="badge badge-${c.status === 'active' ? 'active' : 'inactive'}">${esc(c.status)}</span></td>
            <td style="max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${esc(c.camera_code || '-')}">${esc(c.camera_code || '-')}</td>
            <td>
                <button class="btn btn-primary btn-sm" onclick="runDetection(${c.id})">Detect</button>
                <button class="btn btn-warning btn-sm" onclick="window.location.href='/pages/edit-camera.html?id=${c.id}'">Edit</button>
                <button class="btn btn-danger btn-sm" onclick="deleteCamera(${c.id})">Delete</button>
            </td>
        </tr>
    `).join('');
}

async function loadCameraForEdit() {
    const params = new URLSearchParams(window.location.search);
    const id = params.get('id');
    if (!id) { window.location.href = '/pages/cameras.html'; return; }

    const data = await apiGet('/api/cameras/' + id);
    if (!data || !data.camera) { alert('Camera not found'); return; }

    const c = data.camera;
    document.getElementById('cameraId').value = c.id;
    document.getElementById('name').value = c.camera_name || '';
    document.getElementById('location').value = c.location || '';
    document.getElementById('speed_limit').value = c.speed_limit || 50;
    document.getElementById('distance_meters').value = c.measurement_distance || 10;
    document.getElementById('status').value = c.status || 'active';
}

async function handleEditCamera(e) {
    e.preventDefault();
    const msgDiv = document.getElementById('msg');
    const id = document.getElementById('cameraId').value;

    const data = {
        camera_name: document.getElementById('name').value,
        location: document.getElementById('location').value,
        speed_limit: parseInt(document.getElementById('speed_limit').value),
        measurement_distance: parseFloat(document.getElementById('distance_meters').value),
        status: document.getElementById('status').value,
    };

    const result = await apiPut('/api/cameras/' + id, data);
    if (result && result.camera) {
        window.location.href = '/pages/cameras.html';
    } else {
        msgDiv.textContent = result.error || 'Failed to update camera';
        msgDiv.style.display = 'block';
    }
}

async function handleAddCamera(e) {
    e.preventDefault();
    const msgDiv = document.getElementById('msg');

    const data = {
        name: document.getElementById('name').value,
        location: document.getElementById('location').value,
        speed_limit: parseInt(document.getElementById('speed_limit').value),
        measurement_distance: parseFloat(document.getElementById('distance_meters').value),
    };

    const result = await apiPost('/api/cameras', data);
    if (result && result.camera) {
        window.location.href = '/pages/cameras.html';
    } else {
        msgDiv.textContent = result.error || 'Failed to add camera';
        msgDiv.style.display = 'block';
    }
}

async function runDetection(cameraId) {
    const vs = prompt('Enter video source path (leave blank for default):', 'videos/trash.mp4');
    if (vs === null) return;

    const body = vs ? { video_source: vs } : {};
    const result = await apiPost('/api/cameras/' + cameraId + '/detect', body);

    if (!result || result.error) {
        alert('Failed: ' + (result ? result.error : 'Unknown error'));
        return;
    }

    const runId = result.run_id;
    if (!runId) {
        alert('Detection started but no run ID returned.');
        return;
    }

    showDetectionPanel();
    pollDetectionStatus(runId);
}

function showDetectionPanel() {
    let panel = document.getElementById('detectionPanel');
    if (!panel) {
        panel = document.createElement('div');
        panel.id = 'detectionPanel';
        panel.style.cssText = 'position:fixed;top:20px;right:20px;width:380px;background:#1a1a2e;color:white;border-radius:12px;padding:20px;z-index:999;box-shadow:0 8px 30px rgba(0,0,0,0.4);font-family:Segoe UI,sans-serif;';
        document.body.appendChild(panel);
    }
    panel.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
            <strong style="font-size:16px;">Detection Running...</strong>
            <span id="detStatus" class="badge badge-active">processing</span>
        </div>
        <div style="margin-bottom:8px;">Frames: <span id="detFrames">0</span></div>
        <div style="margin-bottom:8px;">Vehicles: <span id="detVehicles">0</span></div>
        <div style="margin-bottom:8px;">Speeds calculated: <span id="detSpeeds">0</span></div>
        <div style="margin-bottom:12px;color:#e74c3c;font-weight:bold;">Violations: <span id="detViolations">0</span></div>
        <div id="detSpeedList" style="max-height:200px;overflow-y:auto;font-size:12px;border-top:1px solid rgba(255,255,255,0.1);padding-top:8px;"></div>
        <div id="detComplete" style="display:none;margin-top:12px;padding:10px;background:rgba(39,174,96,0.2);border-radius:8px;text-align:center;">
        </div>
    `;
    panel.style.display = 'block';
}

function pollDetectionStatus(runId) {
    const interval = setInterval(async () => {
        const data = await apiGet('/api/cameras/detection-status/' + runId);
        if (!data) { clearInterval(interval); return; }

        const el = (id) => document.getElementById(id);
        if (el('detStatus')) el('detStatus').textContent = data.status;
        if (el('detFrames')) el('detFrames').textContent = data.frames;
        if (el('detVehicles')) el('detVehicles').textContent = data.vehicles;
        if (el('detSpeeds')) el('detSpeeds').textContent = (data.speeds || []).length;
        if (el('detViolations')) el('detViolations').textContent = data.violations;

        const list = el('detSpeedList');
        if (list && data.speeds && data.speeds.length > 0) {
            const limit = data.speed_limit || 50;
            list.innerHTML = data.speeds.map(s => {
                const color = s.speed > limit ? '#e74c3c' : '#27ae60';
                const marker = s.speed > limit ? 'VIOLATION' : '';
                return `<div style="margin-bottom:3px;">
                    <span style="color:${color};">${esc(s.vehicle_type)} #${esc(String(s.object_id))}: ${esc(String(s.speed))} km/h</span>
                    ${marker ? '<span style="color:#e74c3c;font-weight:bold;margin-left:6px;">' + marker + '</span>' : ''}
                </div>`;
            }).join('');
        }

        if (data.status === 'completed' || data.status === 'failed') {
            clearInterval(interval);
            if (el('detStatus')) el('detStatus').textContent = data.status;
            const complete = el('detComplete');
            if (complete) {
                complete.style.display = 'block';
                if (data.status === 'completed') {
                    complete.innerHTML = 'Detection complete! ' +
                        data.vehicles + ' vehicles, ' +
                        (data.speeds || []).length + ' speeds, ' +
                        data.violations + ' violations. &nbsp;|&nbsp; ' +
                        '<a href="/pages/violations.html" style="color:#27ae60;font-weight:bold;">View Violations</a> &nbsp;|&nbsp; ' +
                        '<a href="/pages/reports.html" style="color:#3498db;font-weight:bold;">View Reports</a>';
                } else {
                    complete.innerHTML = '<span style="color:#e74c3c;">Detection failed.</span>';
                }
            }
        }
    }, 2000);
}

async function deleteCamera(cameraId) {
    if (!confirm('Delete this camera?')) return;
    await apiDelete('/api/cameras/' + cameraId);
    await loadCameras();
}
