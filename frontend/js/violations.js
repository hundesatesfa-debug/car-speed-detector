let allViolations = [];
let currentSort = { field: null, asc: true };

document.addEventListener('DOMContentLoaded', async function () {
    await loadCameraOptions();
    await loadViolations();
});

async function loadCameraOptions() {
    const data = await apiGet('/api/cameras');
    if (!data) return;
    const select = document.getElementById('filterCamera');
    const current = select.value;
    select.innerHTML = '<option value="">All Cameras</option>';
    (data.cameras || []).forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.id;
        opt.textContent = c.camera_name;
        if (String(c.id) === current) opt.selected = true;
        select.appendChild(opt);
    });
}

async function loadViolations() {
    closeSidebar();
    const params = new URLSearchParams();
    const camera = document.getElementById('filterCamera').value;
    const plate = document.getElementById('filterPlate').value.trim();
    const dateFrom = document.getElementById('filterDateFrom').value;
    const dateTo = document.getElementById('filterDateTo').value;
    const status = document.getElementById('filterStatus').value;

    if (camera) params.set('camera_id', camera);
    if (plate) params.set('plate', plate);
    if (dateFrom) params.set('date_from', dateFrom);
    if (dateTo) params.set('date_to', dateTo);
    if (status) params.set('status', status);

    const data = await apiGet('/api/violations?' + params.toString());
    if (!data) return;

    allViolations = data.violations || [];
    renderViolations(allViolations);
}

function renderViolations(violations) {
    const tbody = document.getElementById('violationsTable');
    if (!tbody) return;

    if (violations.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" class="no-results">No violations found</td></tr>';
        return;
    }

    tbody.innerHTML = violations.map(v => `
        <tr>
            <td>${v.id}</td>
            <td>${esc(v.camera_name || '-')}</td>
            <td>${esc(String(v.object_id || '-'))}</td>
            <td>${esc(v.vehicle_type || '-')}</td>
            <td>${esc(v.plate_number || 'N/A')}</td>
            <td style="color:#e74c3c;font-weight:600;">${esc(String(v.speed))} km/h</td>
            <td>${esc(String(v.speed_limit))} km/h</td>
            <td>${formatTime(v.violation_time)}</td>
            <td><span class="badge badge-${esc(v.status || 'pending')}">${esc(v.status || 'pending')}</span></td>
            <td>${v.evidence_path ? '<button class="btn btn-primary btn-sm" onclick="showImage(' + v.id + ')">View</button>' : '-'}</td>
        </tr>
    `).join('');
}

function sortTable(field) {
    if (currentSort.field === field) {
        currentSort.asc = !currentSort.asc;
    } else {
        currentSort.field = field;
        currentSort.asc = true;
    }

    document.querySelectorAll('th.sortable').forEach(th => {
        th.classList.remove('sort-asc', 'sort-desc');
    });

    const headers = document.querySelectorAll('th.sortable');
    headers.forEach(th => {
        if (th.textContent.trim().toLowerCase().includes(field.replace('_', ' '))) {
            th.classList.add(currentSort.asc ? 'sort-asc' : 'sort-desc');
        }
    });

    const sorted = [...allViolations].sort((a, b) => {
        let valA = a[field];
        let valB = b[field];

        if (valA == null) valA = '';
        if (valB == null) valB = '';

        if (field === 'speed' || field === 'id' || field === 'object_id') {
            valA = parseFloat(valA) || 0;
            valB = parseFloat(valB) || 0;
            return currentSort.asc ? valA - valB : valB - valA;
        }

        if (field === 'violation_time') {
            valA = new Date(valA).getTime() || 0;
            valB = new Date(valB).getTime() || 0;
            return currentSort.asc ? valA - valB : valB - valA;
        }

        valA = String(valA).toLowerCase();
        valB = String(valB).toLowerCase();
        if (valA < valB) return currentSort.asc ? -1 : 1;
        if (valA > valB) return currentSort.asc ? 1 : -1;
        return 0;
    });

    renderViolations(sorted);
}

function resetFilters() {
    document.getElementById('filterCamera').value = '';
    document.getElementById('filterPlate').value = '';
    document.getElementById('filterDateFrom').value = '';
    document.getElementById('filterDateTo').value = '';
    document.getElementById('filterStatus').value = '';
    currentSort = { field: null, asc: true };
    document.querySelectorAll('th.sortable').forEach(th => th.classList.remove('sort-asc', 'sort-desc'));
    loadViolations();
}

async function showImage(violationId) {
    const modal = document.getElementById('imageModal');
    const img = document.getElementById('modalImage');
    img.src = '';
    modal.style.display = 'flex';

    const res = await fetch('/api/violations/' + violationId + '/image?t=' + Date.now(), {
        headers: { 'Authorization': 'Bearer ' + getToken() },
    });
    if (res.ok) {
        const blob = await res.blob();
        img.src = URL.createObjectURL(blob);
    } else {
        img.alt = 'Failed to load image (HTTP ' + res.status + ')';
    }
}

function closeModal() {
    document.getElementById('imageModal').style.display = 'none';
}

function formatTime(ts) {
    if (!ts) return '-';
    const d = new Date(ts);
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString();
}
