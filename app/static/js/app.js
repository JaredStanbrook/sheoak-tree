/**
 * Sheoak Sensor Dashboard
 * 2025 Refactored Version - Deep Slate Theme
 */

const CONFIG = {
    socketPath: '/sheoak/socket.io',
    maxLogEntries: 50, // Reduced slightly for performance
    timeZone: 'Australia/Perth',
    locale: 'en-AU',
    // Theme Colors matching CSS Variables
    theme: {
        primary: '#10b981',
        danger: '#ef4444',
        warn: '#f59e0b',
        text: '#f8fafc',
        textMuted: '#94a3b8',
        gridLines: 'rgba(255, 255, 255, 0.08)'
    },
    icons: {
        'motion': '<span style="font-size:1.2em">👁️</span>',
        'door': '<span style="font-size:1.2em">🚪</span>',
    }
};

const Utils = {
    /**
     * Standard Date Format: 05 Dec, 19:13
     */
    formatDate(isoString) {
        if (!isoString || isoString === 'None') return 'No activity';
        const date = new Date(isoString);
        return date.toLocaleString(CONFIG.locale, {
            timeZone: CONFIG.timeZone,
            month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit', hour12: false
        });
    },

    /**
     * Relative Time: "2 mins ago"
     */
    timeAgo(isoString) {
        if (!isoString || isoString === 'None') return 'Never';
        const date = new Date(isoString);
        const seconds = Math.floor((new Date() - date) / 1000);

        let interval = seconds / 31536000;
        if (interval > 1) return Math.floor(interval) + "y ago";
        interval = seconds / 2592000;
        if (interval > 1) return Math.floor(interval) + "mo ago";
        interval = seconds / 86400;
        if (interval > 1) return Math.floor(interval) + "d ago";
        interval = seconds / 3600;
        if (interval > 1) return Math.floor(interval) + "h ago";
        interval = seconds / 60;
        if (interval > 1) return Math.floor(interval) + "m ago";
        return Math.floor(seconds) + "s ago";
    },

    async fetchJson(url, options = {}) {
        try {
            const res = await fetch(url, options);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error("API Error:", err);
            throw err;
        }
    },
    escape(str) {
        if (!str) return '';
        // Replaces single quotes with an escaped version
        return String(str).replace(/'/g, "\\'");
    },
};

/**
 * Controller: Dashboard (Live Tab)
 */
class DashboardController {
    constructor() {
        this.activityLog = [];
        this.elements = {
            grid: document.getElementById('sensors-grid'),
            list: document.getElementById('activity-list'),
            summary: document.getElementById('system-summary'),
            connText: document.getElementById('connection-text'),
            connDot: document.querySelector('.status-dot')
        };

        // Expose this instance to the window so HTML onclick events can find it
        window.dashboard = this;
    }

    updateConnectionStatus(isConnected) {
        if (this.elements.connText) this.elements.connText.textContent = isConnected ? 'Connected' : 'Offline';
        if (this.elements.connDot) {
            this.elements.connDot.className = `status-dot ${isConnected ? 'connected' : ''}`;
            this.elements.connDot.parentElement.style.borderColor = isConnected ? 'var(--glass-border)' : 'var(--color-danger)';
        }
    }

    /**
     * Call the Backend API to toggle the relay
     */
    async toggleRelay(sensorId) {
        try {
            // Visual feedback handled by SocketIO update, but we can log here
            console.log(`Toggling sensor ${sensorId}...`);
            await fetch(`/api/sensors/${sensorId}/toggle`, { method: 'POST' });
        } catch (error) {
            console.error("Failed to toggle relay:", error);
            alert("Error communicating with device.");
        }
    }

    renderSensorGrid(sensors) {
        if (!this.elements.grid) return;

        // Calculate system summary
        // EXCLUDE relays from the "Security" count (lights on != intruder)
        const activeCount = sensors.filter(s => s.value === 1 && s.type !== 'relay').length;
        this.updateSystemSummary(activeCount, sensors.length);

        this.elements.grid.innerHTML = sensors.map(sensor => {
            const isActive = sensor.value === 1;

            // Normalize types
            let type = (sensor.type || 'motion').toLowerCase();
            if (type.includes('contact')) type = 'door';
            if (type.includes('pir')) type = 'motion';

            const activeClass = isActive ? 'active' : '';

            // --- RELAY RENDERING LOGIC ---
            if (type === 'relay') {
                const btnLabel = isActive ? 'TURN OFF' : 'TURN ON';
                const btnClass = isActive ? 'btn-active' : '';

                // Using a lightbulb icon for relay (SVG)
                const bulbIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-1 1.5-2 1.5-3.5a6 6 0 0 0-11 0c0 1.5.5 2.5 1.5 3.5.8.8 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/></svg>`;

                return `
                <div class="sensor-card relay ${activeClass}" id="card-${sensor.id}">
                    <div>
                        <div class="sensor-name">
                            ${sensor.name}
                            <div class="sensor-icon">${bulbIcon}</div>
                        </div>
                        <div class="sensor-status">${isActive ? 'ON' : 'OFF'}</div>
                    </div>

                    <div class="sensor-details" style="margin-top: 15px;">
                        <button
                            class="relay-toggle-btn ${btnClass}"
                            onclick="window.dashboard.toggleRelay(${sensor.id})"
                        >
                            ${btnLabel}
                        </button>
                    </div>
                </div>`;
            }

            // --- STANDARD SENSOR RENDERING LOGIC ---
            const typeClass = type === 'door' ? 'door' : 'motion';
            const iconHtml = type === 'door' ? CONFIG.icons.door : CONFIG.icons.motion; // Ensure CONFIG.icons exists

            let statusText = 'SECURE';
            if (isActive) statusText = type === 'door' ? 'OPEN' : 'DETECTED';

            return `
                <div class="sensor-card ${typeClass} ${activeClass}" id="card-${sensor.id}">
                    <div>
                        <div class="sensor-name">
                            ${sensor.name}
                            <div class="sensor-icon">${iconHtml}</div>
                        </div>
                        <div class="sensor-status">${statusText}</div>
                    </div>

                    <div class="sensor-details">
                        <div style="display:flex; justify-content:space-between;">
                            <span>Last Event:</span>
                            <strong>${Utils.timeAgo(sensor.last_activity)}</strong>
                        </div>
                        <div style="font-size:0.75rem; opacity:0.6; margin-top:4px;">
                            ${Utils.formatDate(sensor.last_activity)}
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    updateSystemSummary(activeCount, totalCount) {
        if (!this.elements.summary) return;

        if (activeCount === 0) {
            this.elements.summary.innerHTML = `
                <div class="summary-card">
                    <div>
                        <div style="font-weight: 700; font-size: 1.1rem;">System Secure</div>
                        <div style="font-size: 0.9rem; opacity: 0.7;">Sensors are quiet</div>
                    </div>
                </div>`;
        } else {
            this.elements.summary.innerHTML = `
                <div class="summary-card" style="border-color: var(--color-danger);">
                    <div class="icon-wrapper" style="background: rgba(239, 68, 68, 0.2); color: var(--color-danger);">🚨</div>
                    <div>
                        <div style="font-weight: 700; color: var(--color-danger); font-size: 1.1rem;">Activity Detected</div>
                        <div style="font-size: 0.9rem; opacity: 0.7;">${activeCount} security sensor(s) active</div>
                    </div>
                </div>`;
        }
    }

    addLogEntry(data) {
        const type = (data.type || 'motion').toLowerCase();

        // Don't log relay actions to the activity list if you find it spammy
        // remove this line if you WANT to see "Living Room Light: Relay Toggled" in the log
        // if (type === 'relay') return;

        const event = data.event || data.type;
        const sensor = data.sensor_name || data.name;
        const isDoor = type.includes('door') || type.includes('contact');

        const entry = {
            sensor: sensor,
            type: isDoor ? 'door' : (type === 'relay' ? 'relay' : 'motion'),
            event: event,
            timestamp: Utils.formatDate(data.timestamp),
            timeAgo: Utils.timeAgo(data.timestamp),
            rawTs: data.timestamp
        };

        const isDuplicate = this.activityLog.some(existing =>
            existing.sensor === entry.sensor && existing.rawTs === entry.rawTs
        );

        if (!isDuplicate) {
            this.activityLog.unshift(entry);
            if (this.activityLog.length > CONFIG.maxLogEntries) {
                this.activityLog.pop();
            }
            this.renderLog();
        }
    }

    setHistoricalLog(activityData) {
        if (!activityData) return;
        this.activityLog = [];

        [...activityData].reverse().forEach(item => {
            // Log if value is 1 (Active) OR if it is a relay change
            if (item.value === 1 || item.state === 1 || item.type === 'relay') {
                this.addLogEntry(item);
            }
        });
    }

    renderLog() {
        if (!this.elements.list) return;

        if (this.activityLog.length === 0) {
            this.elements.list.innerHTML = '<div class="empty-state">No recent activity.</div>';
            return;
        }

        this.elements.list.innerHTML = this.activityLog.map(entry => `
            <div class="log-entry ${entry.type}">
                <div class="log-info">
                    <strong>${entry.sensor}</strong>
                    <span>${entry.event}</span>
                </div>
                <div style="text-align:right">
                    <div class="timestamp">${entry.timestamp.split(', ')[1]}</div> <div style="font-size:0.7rem; opacity:0.5">${entry.timeAgo}</div>
                </div>
            </div>
        `).join('');
    }
}
/**
 * Controller: Charts (Frequency Tab)
 */
class ChartController {
    constructor(socket) {
        this.socket = socket;
        this.chart = null;
        this.elements = {
            ctx: document.getElementById('frequencyChart'),
            info: document.getElementById('chartInfo'),
            timeRange: document.getElementById('timeRange'),
            intervalRange: document.getElementById('intervalRange')
        };

        if (this.elements.timeRange) this.elements.timeRange.addEventListener('change', () => this.requestData());
        if (this.elements.intervalRange) this.elements.intervalRange.addEventListener('change', () => this.requestData());
    }

    init() {
        if (this.chart || !this.elements.ctx) return;
        if (typeof Chart === 'undefined') return console.error("Chart.js missing");

        Chart.defaults.color = CONFIG.theme.textMuted;
        Chart.defaults.borderColor = CONFIG.theme.gridLines;
        Chart.defaults.font.family = "'Inter', sans-serif";

        this.chart = new Chart(this.elements.ctx.getContext('2d'), {
            type: 'line',
            data: { labels: [], datasets: [] },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'nearest', axis: 'x', intersect: false },
                plugins: {
                    legend: { labels: { color: CONFIG.theme.text } },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.95)',
                        titleColor: '#fff',
                        bodyColor: '#cbd5e1',
                        borderColor: 'rgba(255,255,255,0.1)',
                        borderWidth: 1,
                        padding: 10,
                        cornerRadius: 8,
                        callbacks: {
                            title: (items) => {
                                // If hovering a door bar, use the dataset label as title
                                if (items[0].dataset.type === 'bar') {
                                    return items[0].dataset.label;
                                }
                                return items[0].label; // Default time bucket
                            },
                            label: (ctx) => {
                                const raw = ctx.raw;

                                // --- CUSTOM DOOR TOOLTIP ---
                                if (raw.x && Array.isArray(raw.x)) {
                                    const start = new Date(raw.x[0]);
                                    const end = new Date(raw.x[1]);

                                    // Calculate Duration
                                    const diffMs = end - start;
                                    const diffMins = Math.floor(diffMs / 60000);
                                    const diffSecs = Math.floor((diffMs % 60000) / 1000);
                                    const durationStr = diffMins > 0 ? `${diffMins}m ${diffSecs}s` : `${diffSecs}s`;

                                    const timeStr = start.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

                                    // Return Array for multi-line tooltip
                                    return [
                                        `Status: OPEN`,
                                        `Time:   ${timeStr}`,
                                        `Duration: ${durationStr}`
                                    ];
                                }

                                // --- STANDARD MOTION TOOLTIP ---
                                return `Events: ${raw}`;
                            }
                        }
                    },
                    annotation: {
                        // Optional: Draw a line separating the door lane from the graph
                        annotations: {
                            line1: {
                                type: 'line',
                                yMin: 0,
                                yMax: 0,
                                yScaleID: 'y1', // Use the door axis
                                borderColor: 'rgba(255, 255, 255, 0.05)',
                                borderWidth: 2,
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'time',
                        time: { unit: 'hour', displayFormats: { hour: 'HH:mm' } },
                        grid: { display: false }
                    },
                    // Main Axis (Motion)
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        beginAtZero: true,
                        title: { display: true, text: 'Motion Intensity' },
                        grid: { color: CONFIG.theme.gridLines },
                        stack: 'motionStack', // Separate stack
                        weight: 2 // Takes up more space
                    },
                    // Door Swimlane (Top Strip)
                    y1: {
                        type: 'linear',
                        display: false,
                        position: 'right',
                        min: 0,
                        max: 1, // Fixed range 0-1
                        weight: 0, // Doesn't affect layout much
                        offset: true,
                        grid: { display: false }
                    }
                }
            }
        });
    }

    requestData() {
        const hours = parseInt(this.elements.timeRange.value);
        const interval = parseInt(this.elements.intervalRange.value);
        this.socket.emit('request_frequency_data', { hours, interval });
    }

    /** * HELPER: Converts Open/Close events into Duration Blocks
     * Returns: Array of { x: [Start, End], y: 1 }
     */
    processDoorData(events) {
        const blocks = [];
        let openTime = null;

        events.forEach(evt => {
            if (evt.state === 'open') {
                openTime = evt.x; // Store the start time
            }
            else if (evt.state === 'closed' && openTime) {
                // We found a pair! Create a block.
                blocks.push({
                    x: [openTime, evt.x], // The Time Range
                    y: 1                  // The Height (Top of chart)
                });
                openTime = null; // Reset
            }
        });

        // Edge Case: Door is currently OPEN (No close event yet)
        if (openTime) {
            blocks.push({
                x: [openTime, new Date().toISOString()],
                y: 1
            });
        }

        return blocks;
    }

    update(data) {
        if (!this.chart) this.init();
        if (!this.chart) return;

        const { sensors, timestamps, interval_minutes } = data;
        const palette = ['#10b981', '#3b82f6', '#ec4899', '#8b5cf6'];
        let colorIdx = 0;
        const datasets = [];

        Object.keys(sensors).forEach(label => {
            const rawData = sensors[label];
            // Check if this is door data (array of objects with 'state')
            const isDoor = Array.isArray(rawData) && rawData.length > 0 && rawData[0].hasOwnProperty('state');

            if (isDoor) {
                // --- DOOR DATASET (Floating Bars) ---
                const durationBlocks = this.processDoorData(rawData);

                if (durationBlocks.length > 0) {
                    datasets.push({
                        label: label,
                        type: 'bar',       // Use BAR type
                        yAxisID: 'y1',     // Pin to secondary axis
                        data: durationBlocks,

                        // Styling for the "Highlighted Block"
                        backgroundColor: 'rgba(245, 158, 11, 0.5)', // Semi-transparent Amber
                        borderColor: '#f59e0b',                     // Solid Amber Border
                        borderWidth: 2,
                        borderRadius: 4,   // Rounded corners
                        borderSkipped: false,
                        barThickness: 15,  // Height of the horizontal bar

                        // This property tells Chart.js the bar goes horizontally across time
                        indexAxis: 'y'     // Crucial for horizontal time bars? No, actually...
                        // WAIT: Chart.js allows x: [start, end] on standard bars if X is time scale.
                        // We keep indexAxis default 'x', but provide a range for X.
                    });
                }
            } else {
                // --- MOTION DATASET (Standard Line) ---
                const color = palette[colorIdx++ % palette.length];
                datasets.push({
                    label: label,
                    type: 'line',
                    yAxisID: 'y',
                    data: rawData,
                    borderColor: color,
                    backgroundColor: color + '15',
                    fill: true,
                    tension: 0.4,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHitRadius: 20
                });
            }
        });

        this.chart.data.labels = timestamps;
        this.chart.data.datasets = datasets;
        this.chart.update();

        if (this.elements.info) {
            this.elements.info.innerHTML = `Motion grouped by <strong>${interval_minutes}m</strong>. Doors shown as <strong>duration blocks</strong>.`;
        }
    }
}


class PresenceController {
    constructor() {
        this.elements = {
            widgetList: document.getElementById('people-list'),
            widgetCount: document.getElementById('home-count'),
            tableBody: document.getElementById('device-list-body'),
            modal: document.getElementById('editDeviceModal'),
            inputs: {
                id: document.getElementById('edit-device-id'),
                name: document.getElementById('edit-device-name'),
                owner: document.getElementById('edit-device-owner')
            }
        };
    }

    async loadWhoIsHome() {
        if (!this.elements.widgetList) return;
        try {
            const data = await Utils.fetchJson('/api/presence/who-is-home');
            if (data.success && this.elements.widgetCount) {
                this.elements.widgetCount.textContent = data.count;
                this.elements.widgetList.innerHTML = '';

                if (data.count === 0) {
                    this.elements.widgetList.innerHTML = '<span class="text-muted">No one is home.</span>';
                    return;
                }

                // Show Named People
                data.people_home.forEach(person => {
                    if (person === 'Unknown') return;
                    const chip = document.createElement('span');
                    chip.className = 'person-chip home';
                    chip.innerHTML = `👤 ${person}`;
                    this.elements.widgetList.appendChild(chip);
                });

                // Fallback if only Unknown devices are home
                if (this.elements.widgetList.children.length === 0 && data.count > 0) {
                    this.elements.widgetList.innerHTML = `<span class="person-chip home">${data.count} Unknown Device(s)</span>`;
                }
            }
        } catch (e) { console.error("Presence Widget Error:", e); }
    }

    async loadDevices() {
        if (!this.elements.tableBody) return;
        this.elements.tableBody.innerHTML = '<tr><td colspan="6" class="text-center">Loading...</td></tr>';

        try {
            const data = await Utils.fetchJson('/api/presence/devices');
            this.elements.tableBody.innerHTML = '';

            if (data.success) {
                data.devices.forEach(device => {
                    const tr = document.createElement('tr');
                    const lastSeen = new Date(device.last_seen).toLocaleString(CONFIG.locale);
                    const statusClass = device.is_home ? 'online' : 'offline';

                    // Privacy Shield Icon if MAC is randomized
                    const privacyIcon = device.is_randomized_mac
                        ? '<span title="Private Wi-Fi Address (Randomized)" style="cursor:help">🛡️</span>'
                        : '';

                    // Vendor Text (e.g. "Apple")
                    const vendorTxt = device.vendor ? `<span class="badge-gray">${device.vendor}</span>` : '';

                    // Hostname (e.g. "Kaias-iPhone")
                    const hostnameTxt = device.hostname
                        ? `<div style="color:var(--color-primary); font-size:0.85rem;">${Utils.escape(device.hostname)}</div>`
                        : '<span style="opacity:0.3">-</span>';

                    // Safe Escaping
                    const safeName = Utils.escape(device.name);
                    const safeOwner = Utils.escape(device.owner || '');

                    tr.innerHTML = `
        <td>
            <div class="status-dot ${statusClass}"></div>
        </td>

        <td>
            <div style="font-weight: 600; color: var(--color-text);">${device.name}</div>
            <div style="font-size: 0.8rem; color: var(--color-text-muted);">${safeOwner || 'Unassigned'}</div>
        </td>

        <td>
            ${vendorTxt}
            <div class="mono" style="font-size: 0.75rem; margin-top:4px; opacity:0.7;">${device.last_ip || 'No IP'}</div>
        </td>

        <td>
            ${hostnameTxt}
            <div class="mono" style="font-size: 0.75rem; opacity: 0.6; display:flex; gap:6px;">
                ${device.mac_address} ${privacyIcon}
            </div>
        </td>

        <td style="font-size: 0.85rem; color: var(--color-text-muted);">
            ${lastSeen}
        </td>

        <td>
            <button class="btn btn-small btn-secondary"
                onclick="app.presence.openEditModal(${device.id}, '${safeName}', '${safeOwner}', ${device.track_presence})">
                Edit
            </button>
        </td>
    `;
                    this.elements.tableBody.appendChild(tr);
                });
            }
        } catch (e) {
            this.elements.tableBody.innerHTML = `<tr><td colspan="6" class="text-warning">Error: ${e.message}</td></tr>`;
        }
    }

    openEditModal(id, name, owner, track_presence) {
        this.elements.inputs.id.value = id;
        this.elements.inputs.name.value = name;
        this.elements.inputs.owner.value = owner;
        document.getElementById('edit-device-track').checked = (track_presence === true);
        this.elements.modal.classList.add('active');
    }

    async submitUpdate() {
        const id = this.elements.inputs.id.value;
        const name = this.elements.inputs.name.value;
        const owner = this.elements.inputs.owner.value;
        const track_presence = document.getElementById('edit-device-track').checked;
        const btn = document.querySelector('#editDeviceModal .btn-primary');

        btn.textContent = 'Saving...';
        try {
            const res = await Utils.fetchJson(`/api/presence/devices/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, owner, track_presence })
            });
            if (res.success) {
                this.elements.modal.classList.remove('active');
                this.loadDevices();
                this.loadWhoIsHome();
            } else {
                alert("Error: " + res.error);
            }
        } catch (e) { alert("Failed: " + e); }
        finally { btn.textContent = 'Save'; }
    }

    async deleteDevice() {
        const id = this.elements.inputs.id.value;
        if (!confirm("Stop monitoring this device? It will reappear if detected again.")) return;
        try {
            const res = await Utils.fetchJson(`/api/presence/devices/${id}`, { method: 'DELETE' });
            if (res.success) {
                this.elements.modal.classList.remove('active');
                this.loadDevices();
            }
        } catch (e) { alert("Delete failed"); }
    }
}
/**
 * Controller: Sequences (Review Tab)
 */
class SequenceController {
    constructor() {
        this.currentPage = 1;
        this.currentSequenceId = null;
        this.elements = {
            list: document.getElementById('sequenceList'),
            modal: document.getElementById('sequenceModal'),
            detail: document.getElementById('sequenceDetail'),
            pagination: document.getElementById('pagination'),
            stats: {
                total: document.getElementById('totalSequences'),
                labeled: document.getElementById('labeledSequences'),
                unlabeled: document.getElementById('unlabeledSequences')
            }
        };
    }

    async process(incremental) {
        const btnId = incremental ? 'incrementalProcessBtn' : 'fullProcessBtn';
        const btn = document.getElementById(btnId);

        this.setLoading(btn, true);
        try {
            const res = await Utils.fetchJson('/api/sequences/process', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    window_size: parseInt(document.getElementById('windowSize').value),
                    sequence_gap_threshold: parseInt(document.getElementById('gapThreshold').value),
                    incremental
                })
            });
            if (res.success) {
                // Show simple flash message (assuming CSS exists for it)
                alert(`Success: ${res.message}`);
                this.loadData();
            }
        } catch (e) {
            alert("Error: " + e.message);
        } finally {
            this.setLoading(btn, false);
        }
    }

    async loadData() {
        await this.loadStats();
        await this.loadList(1);
    }

    async loadStats() {
        try {
            const data = await Utils.fetchJson('/api/sequences/statistics');
            if (data.success && this.elements.stats.total) {
                this.elements.stats.total.textContent = data.statistics.total_sequences;
                this.elements.stats.labeled.textContent = data.statistics.labeled_sequences;
                this.elements.stats.unlabeled.textContent = data.statistics.unlabeled_sequences;
            }
        } catch (e) { console.warn(e); }
    }

    async loadList(page) {
        this.currentPage = page;
        if (this.elements.list) this.elements.list.innerHTML = '<div class="loading-state"><div class="spinner"></div><p>Loading sequences...</p></div>';

        try {
            const data = await Utils.fetchJson(`/api/sequences/list?page=${page}&per_page=15`);
            if (data.success) {
                this.renderList(data.sequences);
                this.updatePagination(data.pagination);
            }
        } catch (e) {
            this.elements.list.innerHTML = `<div class="empty-state">Error: ${e.message}</div>`;
        }
    }

    renderList(sequences) {
        if (!sequences || sequences.length === 0) {
            this.elements.list.innerHTML = '<div class="empty-state"><p>No sequences found.</p></div>';
            return;
        }

        this.elements.list.innerHTML = sequences.map(seq => `
            <div class="sequence-item" onclick="app.sequences.openModal(${seq.sequence_id})">
                <div class="sequence-header">
                    <span style="font-family:monospace; opacity:0.7">ID: ${seq.sequence_id}</span>
                    <span class="sequence-label ${seq.label ? 'labeled' : 'unlabeled'}">
                        ${seq.label || 'Unlabeled'}
                    </span>
                </div>
                <div class="sequence-meta">
                    <span style="display:flex; align-items:center; gap:6px;">📅 ${Utils.formatDate(seq.start_time)}</span>
                    <span style="display:flex; align-items:center; gap:6px;">⏱ ${seq.duration_minutes.toFixed(1)}m</span>
                </div>
            </div>
        `).join('');
    }

    updatePagination(pg) {
        if (!this.elements.pagination) return;
        if (pg.total_pages <= 1) {
            this.elements.pagination.style.display = 'none';
            return;
        }
        this.elements.pagination.style.display = 'flex';
        document.getElementById('pageInfo').textContent = `Page ${pg.page} of ${pg.total_pages}`;
        document.getElementById('prevBtn').disabled = !pg.has_prev;
        document.getElementById('nextBtn').disabled = !pg.has_next;
    }

    async openModal(id) {
        this.currentSequenceId = id;
        this.elements.modal.classList.add('active');
        this.elements.detail.innerHTML = '<div class="loading-state"><div class="spinner"></div></div>';

        try {
            const data = await Utils.fetchJson(`/api/sequences/${id}`);
            if (data.success) this.renderDetail(data.sequence);
        } catch (e) {
            this.elements.detail.innerHTML = '<p class="text-warning">Failed to load detail.</p>';
        }
    }

    renderDetail(seq) {
        const labels = ['Ignore', 'Activity', 'Bathroom', 'Kitchen', 'Sleeping', 'Away', 'Enter', 'Exit'];

        const eventsHtml = seq.raw_events.map(e => `
            <div class="event-item-small">
                <span class="mono">${e.timestamp.split('T')[1].split('.')[0]}</span>
                <strong style="color:var(--color-primary); margin-right:8px;">${e.sensor_name}</strong>
                <span>${e.event}</span>
            </div>
        `).join('');

        this.elements.detail.innerHTML = `
            <div style="margin-bottom:20px;">
                <h3 style="margin-bottom:5px;">Sequence #${seq.sequence_id}</h3>
                <span style="font-size:0.8rem; opacity:0.7">${Utils.formatDate(seq.start_time)}</span>
            </div>

            <div class="sequence-stats-grid">
                <div><span>Duration</span><strong>${seq.duration_minutes.toFixed(1)}m</strong></div>
                <div><span>Events</span><strong>${seq.raw_events.length}</strong></div>
                <div><span>Current</span><strong>${seq.label || '-'}</strong></div>
            </div>

            <h4 style="margin-bottom:10px; font-size:0.9rem;">Assign Label</h4>
            <div class="label-selector">
                ${labels.map(lbl => `
                    <button class="label-btn ${seq.label === lbl ? 'selected' : ''}"
                        onclick="app.sequences.selectLabel(this, '${lbl}')">${lbl}</button>
                `).join('')}
            </div>

            <button class="btn btn-primary full-width" onclick="app.sequences.saveLabel()">
                Save Classification
            </button>

            <hr class="divider">
            <h4 style="margin-bottom:10px; font-size:0.9rem;">Event Stream</h4>
            <div class="event-list-scroll">${eventsHtml}</div>
        `;
    }

    selectLabel(btn, label) {
        document.querySelectorAll('.label-btn').forEach(b => b.classList.remove('selected'));
        btn.classList.add('selected');
        btn.dataset.selectedLabel = label;
    }

    async saveLabel() {
        const btn = document.querySelector('.label-btn.selected');
        if (!btn) return;

        const label = btn.dataset.selectedLabel;
        const saveBtn = document.querySelector('.modal-body .btn-primary');

        const originalText = saveBtn.textContent;
        saveBtn.textContent = "Saving...";
        saveBtn.disabled = true;

        try {
            const res = await Utils.fetchJson(`/api/sequences/${this.currentSequenceId}/label`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ label })
            });

            if (res.success) {
                this.closeModal();
                this.loadList(this.currentPage); // Refresh list to show new label
                this.loadStats();
            }
        } catch (e) {
            alert("Failed: " + e.message);
            saveBtn.textContent = originalText;
            saveBtn.disabled = false;
        }
    }

    closeModal() {
        this.elements.modal.classList.remove('active');
        this.currentSequenceId = null;
    }

    setLoading(btn, isLoading) {
        if (!btn) return;
        btn.disabled = isLoading;
        if (isLoading) {
            btn.dataset.original = btn.innerHTML;
            btn.innerHTML = 'Processing...';
        } else {
            btn.innerHTML = btn.dataset.original || 'Action';
        }
    }
}

/**
 * Main Application Orchestrator
 */
class App {
    constructor() {
        console.log("Sheoak System: Initializing...");

        // Modules
        this.dashboard = new DashboardController();
        this.sequences = new SequenceController();
        this.presence = new PresenceController();
        this.socket = io({ path: CONFIG.socketPath });
        this.charts = new ChartController(this.socket);

        this._bindSocketEvents();
        this._bindGlobalEvents();

        // Initial Fetch
        this.loadInitialData();

        // Clock
        setInterval(() => {
            const el = document.getElementById('system-time');
            if (el) el.textContent = new Date().toLocaleTimeString(CONFIG.locale, { timeZone: CONFIG.timeZone });
        }, 1000);
    }

    _bindSocketEvents() {
        this.socket.on('connect', () => {
            this.dashboard.updateConnectionStatus(true);
            this.socket.emit('request_activity_data', { hours: 24 });
            // If we reconnected, refresh the grid to ensure no missed states
            this.refreshGrid();
        });

        this.socket.on('disconnect', () => {
            this.dashboard.updateConnectionStatus(false);
        });

        // Real-time Activity
        this.socket.on('sensor_event', (data) => {
            this.dashboard.addLogEntry(data);
            // Refresh grid to show active/inactive state accurately
            this.refreshGrid();
        });

        // Bulk Data
        this.socket.on('activity_data', (data) => {
            const list = data.activity || data;
            this.dashboard.setHistoricalLog(list);
        });

        this.socket.on('frequency_data', (data) => {
            if (data.frequency) this.charts.update(data.frequency);
        });
        this.socket.on('presence_update', (data) => {
            console.log("Presence Update:", data);
            this.presence.loadWhoIsHome();
            if (document.getElementById('presence-tab').classList.contains('active')) {
                this.presence.loadDevices();
            }
        });
    }

    _bindGlobalEvents() {
        // Tab Switching Logic
        window.switchTab = (tabName) => {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-button').forEach(el => el.classList.remove('active'));

            const targetContent = document.getElementById(`${tabName}-content`);
            const targetBtn = document.getElementById(`${tabName}-tab`);

            if (targetContent) targetContent.classList.add('active');
            if (targetBtn) targetBtn.classList.add('active');

            // Lazy Load / Resize
            if (tabName === 'graphs') {
                setTimeout(() => {
                    if (this.charts.chart) this.charts.chart.resize();
                    this.charts.requestData();
                }, 50);
            }
            if (tabName === 'review') this.sequences.loadData();
            if (tabName === 'presence') this.presence.loadDevices();
            if (tabName === 'live') this.presence.loadWhoIsHome();
        };

        // Expose helpers for HTML onclick events
        window.changePage = (d) => this.sequences.changePage(d);
        window.processSequences = (inc) => this.sequences.process(inc);
        window.loadProcessorState = () => this.sequences.loadData();
        window.closeSequenceModal = () => this.sequences.closeModal();
        window.loadPresenceDevices = () => this.presence.loadDevices();
        window.submitDeviceUpdate = () => this.presence.submitUpdate();
        window.deleteDevice = () => this.presence.deleteDevice();
    }

    async loadInitialData() {
        await this.refreshGrid();
        await this.presence.loadWhoIsHome();
    }

    async refreshGrid() {
        try {
            const data = await Utils.fetchJson('/api/sensors');
            if (data.sensors) this.dashboard.renderSensorGrid(data.sensors);
        } catch (e) {
            console.error("Grid refresh failed", e);
        }
    }
}

// Boot
document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
});
