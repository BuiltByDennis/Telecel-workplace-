document.addEventListener('DOMContentLoaded', () => {
  const backendStatusEl = document.getElementById('backendStatus');
  const apiUrlInput = document.getElementById('apiUrlInput');
  const btnSaveApiUrl = document.getElementById('btnSaveApiUrl');
  const subnetInput = document.getElementById('subnetInput');
  const btnScan = document.getElementById('btnScan');
  const btnShowAddModal = document.getElementById('btnShowAddModal');
  const addStreamSection = document.getElementById('addStreamSection');
  const btnAddStream = document.getElementById('btnAddStream');
  const scanResultsSection = document.getElementById('scanResultsSection');
  const discoveredList = document.getElementById('discoveredList');
  const streamsContainer = document.getElementById('streamsContainer');
  const logsContainer = document.getElementById('logsContainer');
  const btnRefreshLogs = document.getElementById('btnRefreshLogs');

  // Load configured API base URL
  let apiBaseUrl = localStorage.getItem('cctv_api_url') || window.location.origin;
  if (apiBaseUrl.endsWith('/')) {
    apiBaseUrl = apiBaseUrl.slice(0, -1);
  }
  apiUrlInput.value = apiBaseUrl;

  btnSaveApiUrl.addEventListener('click', () => {
    let val = apiUrlInput.value.trim();
    if (!val) val = window.location.origin;
    if (val.endsWith('/')) val = val.slice(0, -1);
    apiBaseUrl = val;
    localStorage.setItem('cctv_api_url', apiBaseUrl);
    checkHealth();
    loadActiveStreams();
    fetchLogs();
  });

  let activeStreams = [];

  // Check Backend Health
  async function checkHealth() {
    try {
      const res = await fetch(`${apiBaseUrl}/api/health`);
      if (res.ok) {
        backendStatusEl.textContent = 'Online';
        backendStatusEl.classList.add('online');
      } else {
        backendStatusEl.textContent = 'Error';
        backendStatusEl.classList.remove('online');
      }
    } catch (e) {
      backendStatusEl.textContent = 'Offline';
      backendStatusEl.classList.remove('online');
    }
  }

  // Toggle Add Stream Form
  btnShowAddModal.addEventListener('click', () => {
    addStreamSection.classList.toggle('hidden');
  });

  // Add Stream Handler
  btnAddStream.addEventListener('click', async () => {
    const streamId = document.getElementById('streamIdInput').value.trim();
    const streamUrl = document.getElementById('streamUrlInput').value.trim();

    if (!streamId || !streamUrl) {
      alert('Please enter both Stream ID and Stream URL');
      return;
    }

    try {
      const res = await fetch(`${apiBaseUrl}/api/streams/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stream_id: streamId, url: streamUrl })
      });
      if (res.ok) {
        document.getElementById('streamIdInput').value = '';
        document.getElementById('streamUrlInput').value = '';
        addStreamSection.classList.add('hidden');
        loadActiveStreams();
      } else {
        alert('Failed to add stream.');
      }
    } catch (e) {
      console.error(e);
      alert('Error connecting to backend server.');
    }
  });

  // Scan Local Network for CCTV Cameras
  btnScan.addEventListener('click', async () => {
    btnScan.disabled = true;
    btnScan.textContent = '⏳ Scanning Local Network...';
    discoveredList.innerHTML = '<li>Scanning network for ONVIF & RTSP devices...</li>';
    scanResultsSection.classList.remove('hidden');

    const targetSubnet = subnetInput.value.trim() || '192.168.1';

    try {
      const res = await fetch(`${apiBaseUrl}/api/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subnet_prefix: targetSubnet })
      });
      const data = await res.json();
      discoveredList.innerHTML = '';

      if (data.devices && data.devices.length > 0) {
        data.devices.forEach((dev) => {
          const li = document.createElement('li');
          li.className = 'discovered-item';
          li.innerHTML = `
            <div>
              <strong>${dev.ip}</strong> (${dev.type})<br>
              <small>${dev.rtsp_url}</small>
            </div>
            <button class="btn btn-sm btn-success" onclick="quickAddStream('cam_${dev.ip.replace(/\./g, '_')}', '${dev.rtsp_url}')">Connect</button>
          `;
          discoveredList.appendChild(li);
        });
      } else {
        discoveredList.innerHTML = `<li class="empty-state">No active CCTV devices found on subnet prefix <strong>${targetSubnet}.x</strong>.<br><br>• Check if your router uses a different subnet (e.g. 192.168.0, 192.168.8, 10.0.0).<br>• Ensure the AI Engine backend is running locally on the same physical Wi-Fi/LAN as the cameras.<br>• If you know the camera's RTSP stream URL, click "Add Custom Stream URL" above.</li>`;
      }
    } catch (e) {
      discoveredList.innerHTML = '<li class="empty-state">Error performing network scan. Make sure your local AI Engine server is online and accessible.</li>';
    } finally {
      btnScan.disabled = false;
      btnScan.textContent = '🔍 Scan Local Network';
    }
  });

  // Quick Add Stream helper
  window.quickAddStream = async (id, url) => {
    try {
      await fetch(`${apiBaseUrl}/api/streams/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stream_id: id, url: url })
      });
      loadActiveStreams();
    } catch (e) {
      alert('Failed to connect to stream ' + url);
    }
  };

  // Remove Stream
  window.removeStream = async (streamId) => {
    if (!confirm(`Are you sure you want to stop stream ${streamId}?`)) return;
    try {
      await fetch(`${apiBaseUrl}/api/streams/${streamId}`, { method: 'DELETE' });
      loadActiveStreams();
    } catch (e) {
      console.error(e);
    }
  };

  // Load Active Streams
  async function loadActiveStreams() {
    try {
      const res = await fetch(`${apiBaseUrl}/api/streams`);
      const data = await res.json();
      activeStreams = data.streams || [];

      if (activeStreams.length === 0) {
        streamsContainer.innerHTML = '<div class="empty-state">No camera streams active. Scan network or add RTSP stream above.</div>';
        return;
      }

      streamsContainer.innerHTML = '';
      activeStreams.forEach(stream => {
        const streamCard = document.createElement('div');
        streamCard.className = 'stream-card';
        streamCard.innerHTML = `
          <div class="stream-header">
            <span>📷 ${stream.stream_id}</span>
            <button class="btn btn-sm btn-danger" onclick="removeStream('${stream.stream_id}')">Remove</button>
          </div>
          <div class="stream-video-wrap">
            <img class="stream-video" src="${apiBaseUrl}/api/streams/${stream.stream_id}/video" alt="Live Feed ${stream.stream_id}" loading="lazy">
          </div>
          <div class="stream-meta" id="meta_${stream.stream_id}">
            <div class="meta-badges">
              <span class="badge badge-person" id="badge_person_${stream.stream_id}">Persons: 0</span>
              <span class="badge badge-computer" id="badge_comp_${stream.stream_id}">Computers: 0</span>
              <span class="badge badge-movement" id="badge_move_${stream.stream_id}">Movements: 0</span>
            </div>
            <div id="activity_text_${stream.stream_id}" style="font-size: 0.8rem; color: #94a3b8;">Activities: Monitoring...</div>
          </div>
        `;
        streamsContainer.appendChild(streamCard);
      });
    } catch (e) {
      console.error(e);
    }
  }

  // Update Metadata for streams periodically
  async function updateMetadata() {
    for (const stream of activeStreams) {
      try {
        const res = await fetch(`${apiBaseUrl}/api/streams/${stream.stream_id}/metadata`);
        if (res.ok) {
          const meta = await res.json();
          const pBadge = document.getElementById(`badge_person_${stream.stream_id}`);
          const cBadge = document.getElementById(`badge_comp_${stream.stream_id}`);
          const mBadge = document.getElementById(`badge_move_${stream.stream_id}`);
          const actText = document.getElementById(`activity_text_${stream.stream_id}`);

          if (pBadge) pBadge.textContent = `Persons: ${meta.summary?.persons_count || 0}`;
          if (cBadge) cBadge.textContent = `Computers: ${meta.summary?.computers_count || 0}`;
          if (mBadge) mBadge.textContent = `Movements: ${meta.summary?.total_movements || 0}`;
          if (actText && meta.environment_activities) {
            actText.textContent = meta.environment_activities.length > 0
              ? 'Activities: ' + meta.environment_activities.join(', ')
              : 'Activities: Area clear';
          }
        }
      } catch (e) {
        // stream metadata pending
      }
    }
  }

  // Fetch Event Logs
  async function fetchLogs() {
    try {
      const res = await fetch(`${apiBaseUrl}/api/logs`);
      const data = await res.json();
      const logs = data.logs || [];

      if (logs.length === 0) {
        logsContainer.innerHTML = '<div class="empty-state">No structured events logged yet.</div>';
        return;
      }

      logsContainer.innerHTML = '';
      logs.slice(-20).reverse().forEach(log => {
        const item = document.createElement('div');
        item.className = 'log-item';
        item.innerHTML = `
          <div class="log-time">⏱️ ${log.timestamp} | Stream: ${log.stream_id}</div>
          <div><strong>Activities:</strong> ${log.activities ? log.activities.join('; ') : 'None'}</div>
          <div><small>Persons: ${log.summary?.persons_count || 0} | Computers: ${log.summary?.computers_count || 0} | Movements: ${log.summary?.total_movements || 0}</small></div>
        `;
        logsContainer.appendChild(item);
      });
    } catch (e) {
      console.error(e);
    }
  }

  btnRefreshLogs.addEventListener('click', fetchLogs);

  // Initialize
  checkHealth();
  loadActiveStreams();
  fetchLogs();

  // Polling loops
  setInterval(updateMetadata, 1500);
  setInterval(fetchLogs, 5000);
});
