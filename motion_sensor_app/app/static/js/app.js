// Initialize Socket.IO connection
const socket = io({
    path: '/sheoak/socket.io'
});
let activityLog = [];
let frequencyChart = null;
const maxLogEntries = 100;

// Sensor type icons
const sensorIcons = {
    'motion': '👁️',
    'door': '🚪',
    'active': '🟢',
    'motion_active': '🚨',
    'door_active': '🟡'
};

// Sensor colors for frequency chart
const sensorColors = {
    'Living Room': {
        border: 'rgb(255, 99, 132)',
        background: 'rgba(255, 99, 132, 0.1)'
    },
    'Hallway': {
        border: 'rgb(54, 162, 235)',
        background: 'rgba(54, 162, 235, 0.1)'
    },
    'Door': {
        border: 'rgb(255, 205, 86)',
        background: 'rgba(255, 205, 86, 0.1)'
    },
    'Kitchen': {
        border: 'rgb(75, 192, 192)',
        background: 'rgba(75, 192, 192, 0.1)'
    }
};

// Connection status handling
socket.on('connect', function () {
    document.getElementById('connection-status').textContent = 'Connected';
    document.getElementById('status-indicator').className = 'status-indicator connected';

    // Request initial activity data
    socket.emit('request_activity_data', { hours: 24 });

    // Request initial frequency data if on graphs tab
    if (document.getElementById('graphs-tab').classList.contains('active')) {
        requestFrequencyData();
    }
});

socket.on('disconnect', function () {
    document.getElementById('connection-status').textContent = 'Disconnected';
    document.getElementById('status-indicator').className = 'status-indicator disconnected';
});

// Handle sensor updates
socket.on('sensor_update', function (data) {
    if (data.all_sensors) {
        updateSensorGrid(data.all_sensors);
    }
    if (data.sensor_name) {
        addToActivityLog(data);

        // Update frequency chart if currently viewing graphs
        if (document.getElementById('graphs-tab').classList.contains('active')) {
            // Debounce chart updates to avoid too frequent refreshes
            clearTimeout(window.chartUpdateTimeout);
            window.chartUpdateTimeout = setTimeout(() => {
                requestFrequencyData();
            }, 2000);
        }
    }
});

// Handle activity data for basic log
socket.on('activity_data', function (data) {
    // This is used for the activity log tab
    if (data.activity && data.activity.length > 0) {
        // Convert to our format and update log
        data.activity.forEach(entry => {
            if (entry.state === 1) { // Only show activations in the log
                const timestamp = new Date(entry.timestamp).toLocaleString('en-AU', {
                    timeZone: 'Australia/Perth',
                    hour12: true
                });

                const logEntry = {
                    sensor: entry.sensor_name,
                    type: entry.sensor_type,
                    event: entry.event,
                    timestamp: timestamp,
                    isActive: true
                };

                // Avoid duplicates
                if (!activityLog.some(existing =>
                    existing.sensor === logEntry.sensor &&
                    existing.timestamp === logEntry.timestamp &&
                    existing.event === logEntry.event)) {
                    activityLog.unshift(logEntry);
                }
            }
        });

        // Limit log size and update display
        if (activityLog.length > maxLogEntries) {
            activityLog = activityLog.slice(0, maxLogEntries);
        }
        updateActivityLog();
    }
});

// Handle frequency data for charts
socket.on('frequency_data', function (data) {
    updateFrequencyChart(data.frequency);
});

function updateSensorGrid(sensors) {
    const grid = document.getElementById('sensors-grid');
    grid.innerHTML = '';

    sensors.forEach((sensor, index) => {
        const card = document.createElement('div');
        const isActive = sensor.value === 1;
        const sensorClass = sensor.type === 'door' ? 'door' : 'motion';

        card.className = `sensor-card ${sensorClass} ${isActive ? 'active' : ''}`;

        const lastActivity = sensor.last_activity
            ? new Date(sensor.last_activity).toLocaleString('en-AU', {
                hour12: true
            })
            : 'No activity yet';

        let icon = sensorIcons[sensor.type];
        if (isActive) {
            icon = sensor.type === 'door' ? sensorIcons['door_active'] : sensorIcons['motion_active'];
        }

        let statusClass = 'inactive';
        if (sensor.type === 'door' && isActive) {
            statusClass = 'door-open';
        } else if (isActive) {
            statusClass = 'active';
        }

        card.innerHTML = `
            <div class="sensor-name">
                <span class="sensor-icon">${icon}</span>
                ${sensor.name}
            </div>
            <div class="sensor-status ${statusClass}">
                ${sensor.status}
            </div>
            <div class="sensor-details">
                <div><strong>Type:</strong> ${sensor.type.charAt(0).toUpperCase() + sensor.type.slice(1)}</div>
                <div><strong>GPIO Pin:</strong> ${sensor.gpio_pin}</div>
                <div><strong>Last Activity:</strong> ${lastActivity}</div>
            </div>
        `;

        grid.appendChild(card);
    });
}

function addToActivityLog(data) {
    const timestamp = new Date(data.timestamp).toLocaleString('en-AU', {
        hour12: true
    });

    const logEntry = {
        sensor: data.sensor_name,
        type: data.sensor_type,
        event: data.event,
        timestamp: timestamp,
        isActive: data.value === 1
    };

    // Add to beginning of log
    activityLog.unshift(logEntry);

    // Limit log size
    if (activityLog.length > maxLogEntries) {
        activityLog = activityLog.slice(0, maxLogEntries);
    }

    updateActivityLog();
}

function updateActivityLog() {
    const activityList = document.getElementById('activity-list');

    if (activityLog.length === 0) {
        activityList.innerHTML = '<p style="opacity: 0.6; text-align: center;">Waiting for sensor activity...</p>';
        return;
    }

    activityList.innerHTML = activityLog.map(entry => `
        <div class="log-entry ${entry.type}">
            <strong>${entry.sensor}</strong>: ${entry.event}
            <span class="timestamp">${entry.timestamp}</span>
        </div>
    `).join('');
}

function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });

    // Show selected tab
    document.getElementById(tabName + '-tab').classList.add('active');
    event.target.classList.add('active');

    // Initialize chart if switching to graphs tab
    if (tabName === 'graphs') {
        if (!frequencyChart) {
            initializeFrequencyChart();
        }
        requestFrequencyData();
    }
}

function initializeFrequencyChart() {
    const ctx = document.getElementById('frequencyChart').getContext('2d');

    frequencyChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: []
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: 'Sensor Activity Frequency (Activations per Time Interval)',
                    color: 'white',
                    font: {
                        size: 16
                    }
                },
                legend: {
                    labels: {
                        color: 'white',
                        usePointStyle: true,
                        pointStyle: 'circle'
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: 'white',
                    bodyColor: 'white',
                    borderColor: 'white',
                    borderWidth: 1,
                    callbacks: {
                        label: function (context) {
                            const activations = context.parsed.y;
                            const sensor = context.dataset.label;
                            return `${sensor}: ${activations} activation${activations !== 1 ? 's' : ''}`;
                        }
                    }
                },
                annotation: {
                    annotations: {}
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'hour', // or 'minute' if your intervals are small
                        displayFormats: {
                            hour: 'MMM d, h a'
                        }
                    },
                    title: {
                        display: true,
                        text: 'Time (Local Perth Time)',
                        color: 'white'
                    },
                    ticks: {
                        color: 'white',
                        maxTicksLimit: 12,
                        autoSkip: true
                    },
                    grid: {
                        color: 'rgba(255,255,255,0.1)'
                    }
                },
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Number of Activations',
                        color: 'white'
                    },
                    ticks: {
                        color: 'white',
                        callback: function (value) {
                            if (Number.isInteger(value)) {
                                return value;
                            }
                        }
                    },
                    grid: {
                        color: 'rgba(255,255,255,0.1)'
                    }
                }
            },
            interaction: {
                intersect: false,
                mode: 'index'
            },
            elements: {
                line: {
                    tension: 0.4
                },
                point: {
                    radius: 4,
                    hoverRadius: 8
                }
            }
        }
    });
}

function requestFrequencyData() {
    const hours = parseInt(document.getElementById('timeRange').value);
    const interval = parseInt(document.getElementById('intervalRange').value);

    socket.emit('request_frequency_data', {
        hours: hours,
        interval: interval
    });
}

function handleIntervalChange() {
    requestFrequencyData();
}

function updateFrequencyChart(frequencyData) {
    if (!frequencyChart || !frequencyData) return;
    console.log('Updating frequency chart with data:', frequencyData);
    const { sensors, timestamps, interval_minutes, total_intervals, door_events } = frequencyData;
    // Build datasets
    const datasets = Object.keys(sensors)
        .filter(sensorName => !sensorName.toLowerCase().includes("door")) // exclude doors
        .map(sensorName => {
            const colorConfig = sensorColors[sensorName] || {
                border: 'rgb(255, 255, 255)',
                background: 'rgba(255, 255, 255, 0.1)'
            };

            return {
                label: sensorName,
                data: sensors[sensorName],
                borderColor: colorConfig.border,
                backgroundColor: colorConfig.background,
                tension: 0.4,
                fill: false,
                pointBackgroundColor: colorConfig.border,
                pointBorderColor: 'white',
                pointBorderWidth: 2,
                pointRadius: 4,
                pointHoverRadius: 8
            };
        });

    // Update chart labels and datasets
    frequencyChart.data.labels = timestamps;
    frequencyChart.data.datasets = datasets;

    // Find door events
    const doorEvents = sensors["Door"]?.map((val, idx) => val > 0 ? idx : null).filter(idx => idx !== null) || [];

    // Build annotation objects
    const annotations = {};
    doorEvents.forEach((idx, i) => {
        annotations[`doorOpen${i}`] = {
            type: 'line',
            xMin: timestamps[idx],
            xMax: timestamps[idx],
            borderColor: sensorColors.Door.border,
            borderWidth: 2,
            borderDash: [6, 6],
        };
    });

    // Inject into chart options
    frequencyChart.options.plugins.annotation.annotations = annotations;

    frequencyChart.update();

    // Info panel
    const totalActivations = Object.values(sensors).reduce((total, sensorData) =>
        total + sensorData.reduce((sum, count) => sum + count, 0), 0);

    const mostActiveTime = findMostActiveTime(sensors, timestamps);
    const mostActiveSensor = findMostActiveSensor(sensors);

    document.getElementById('chartInfo').innerHTML = `
        <strong>Analysis Summary:</strong><br>
        Time Range: ${interval_minutes} minute intervals over ${total_intervals} periods<br>
        Total Activations: ${totalActivations}<br>
        Most Active Time: ${mostActiveTime}<br>
        Most Active Sensor: ${mostActiveSensor}<br>
        <em>Times shown in local Perth time (12-hour format)</em>
    `;
}

function findMostActiveTime(sensors, timestamps) {
    if (!timestamps.length) return 'No data';

    const timeActivitySums = timestamps.map((time, index) => {
        const totalActivity = Object.values(sensors).reduce((sum, sensorData) =>
            sum + (sensorData[index] || 0), 0);
        return { time, activity: totalActivity };
    });

    const mostActive = timeActivitySums.reduce((max, current) =>
        current.activity > max.activity ? current : max);

    return mostActive.activity > 0 ?
        `${mostActive.time} (${mostActive.activity} activations)` :
        'No activity recorded';
}

function findMostActiveSensor(sensors) {
    if (!Object.keys(sensors).length) return 'No data';

    const sensorTotals = Object.entries(sensors).map(([name, data]) => ({
        name,
        total: data.reduce((sum, count) => sum + count, 0)
    }));

    const mostActive = sensorTotals.reduce((max, current) =>
        current.total > max.total ? current : max);

    return mostActive.total > 0 ?
        `${mostActive.name} (${mostActive.total} activations)` :
        'No activity recorded';
}
// ============ REVIEW TAB FUNCTIONS ============

async function processSequences(incremental) {
    const windowSize = parseInt(document.getElementById('windowSize').value);
    const gapThreshold = parseInt(document.getElementById('gapThreshold').value);
    const btn = incremental ? document.getElementById('incrementalProcessBtn') : document.getElementById('fullProcessBtn');

    btn.disabled = true;
    btn.textContent = incremental ? 'Processing...' : 'Processing...';

    try {
        const response = await fetch('/api/sequences/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                window_size: windowSize,
                sequence_gap_threshold: gapThreshold,
                incremental: incremental
            })
        });

        const data = await response.json();

        if (data.success) {
            alert(`Processing completed! Result: ${JSON.stringify(data.result)}`);
            await loadStatistics();
            await loadSequences(1);
        } else {
            alert(`Error: ${data.error}`);
        }
    } catch (error) {
        alert(`Error processing sequences: ${error.message}`);
    } finally {
        btn.disabled = false;
        btn.textContent = incremental ? 'Incremental Process' : 'Full Process';
    }
}

async function loadProcessorState() {
    const btn = document.getElementById('loadStateBtn');
    btn.disabled = true;
    btn.textContent = 'Loading...';

    try {
        await loadStatistics();
        await loadSequences(1);
        alert('State loaded successfully!');
    } catch (error) {
        alert(`Error loading state: ${error.message}`);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Load State';
    }
}

async function loadStatistics() {
    try {
        const response = await fetch('/api/sequences/statistics');
        const data = await response.json();

        if (data.success) {
            const stats = data.statistics;
            document.getElementById('totalSequences').textContent = stats.total_sequences || 0;
            document.getElementById('labeledSequences').textContent = stats.labeled_sequences || 0;
            document.getElementById('unlabeledSequences').textContent = stats.unlabeled_sequences || 0;
        }
    } catch (error) {
        console.error('Error loading statistics:', error);
    }
}

async function loadSequences(page) {
    currentPage = page;
    const listEl = document.getElementById('sequenceList');
    listEl.innerHTML = '<div class="loading"><div class="spinner"></div> Loading sequences...</div>';

    try {
        const response = await fetch(`/api/sequences/list?page=${page}&per_page=20`);
        const data = await response.json();

        if (data.success) {
            displaySequences(data.sequences);
            updatePagination(data.pagination);
        } else {
            listEl.innerHTML = `<div class="loading">Error: ${data.error}</div>`;
        }
    } catch (error) {
        listEl.innerHTML = `<div class="loading">Error loading sequences: ${error.message}</div>`;
    }
}

function displaySequences(sequences) {
    const listEl = document.getElementById('sequenceList');

    if (sequences.length === 0) {
        listEl.innerHTML = '<div class="loading">No sequences found. Process data to create sequences.</div>';
        return;
    }

    listEl.innerHTML = sequences.map(seq => {
        const startTime = new Date(seq.start_time).toLocaleString('en-AU', {
            timeZone: 'Australia/Perth',
            hour12: true
        });
        const endTime = new Date(seq.end_time).toLocaleString('en-AU', {
            timeZone: 'Australia/Perth',
            hour12: true
        });

        const labelClass = seq.label ? 'labeled' : 'unlabeled';
        const labelText = seq.label || 'Not Labeled';

        return `
            <div class="sequence-item" onclick="openSequenceModal(${seq.sequence_id})">
                <div class="sequence-header">
                    <div class="sequence-id">Sequence #${seq.sequence_id}</div>
                    <div class="sequence-label ${labelClass}">${labelText}</div>
                </div>
                <div class="sequence-info">
                    <div><strong>Start:</strong> ${startTime}</div>
                    <div><strong>End:</strong> ${endTime}</div>
                    <div><strong>Duration:</strong> ${seq.duration_minutes.toFixed(1)} min</div>
                    <div><strong>Windows:</strong> ${seq.window_count}</div>
                    <div><strong>Gap:</strong> ${seq.time_since_last_seq_hours.toFixed(1)} hrs</div>
                </div>
            </div>
        `;
    }).join('');
}

function updatePagination(pagination) {
    const paginationEl = document.getElementById('pagination');
    const pageInfo = document.getElementById('pageInfo');
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');

    if (pagination.total_pages > 1) {
        paginationEl.style.display = 'flex';
        pageInfo.textContent = `Page ${pagination.page} of ${pagination.total_pages}`;
        prevBtn.disabled = !pagination.has_prev;
        nextBtn.disabled = !pagination.has_next;
        totalPages = pagination.total_pages;
    } else {
        paginationEl.style.display = 'none';
    }
}

function changePage(direction) {
    const newPage = currentPage + direction;
    if (newPage >= 1 && newPage <= totalPages) {
        loadSequences(newPage);
    }
}

async function openSequenceModal(sequenceId) {
    currentSequenceId = sequenceId;
    const modal = document.getElementById('sequenceModal');
    const detailEl = document.getElementById('sequenceDetail');

    modal.classList.add('active');
    detailEl.innerHTML = '<div class="loading"><div class="spinner"></div> Loading sequence details...</div>';

    try {
        const response = await fetch(`/api/sequences/${sequenceId}`);
        const data = await response.json();

        if (data.success) {
            displaySequenceDetail(data.sequence);
        } else {
            detailEl.innerHTML = `<div class="loading">Error: ${data.error}</div>`;
        }
    } catch (error) {
        detailEl.innerHTML = `<div class="loading">Error loading sequence: ${error.message}</div>`;
    }
}

function displaySequenceDetail(seq) {
    const detailEl = document.getElementById('sequenceDetail');
    const startTime = new Date(seq.start_time).toLocaleString('en-AU', {
        timeZone: 'Australia/Perth',
        hour12: true
    });
    const endTime = new Date(seq.end_time).toLocaleString('en-AU', {
        timeZone: 'Australia/Perth',
        hour12: true
    });

    const labels = ['Ignore', 'Activity', 'Bathroom', 'Kitchen', 'Sleeping', 'Away'];

    detailEl.innerHTML = `
        <div>
            <h3>Sequence #${seq.sequence_id}</h3>
            <div class="sequence-info" style="margin: 20px 0;">
                <div><strong>Start Time:</strong> ${startTime}</div>
                <div><strong>End Time:</strong> ${endTime}</div>
                <div><strong>Duration:</strong> ${seq.duration_minutes.toFixed(1)} minutes</div>
                <div><strong>Windows:</strong> ${seq.window_count}</div>
                <div><strong>Gap from Previous:</strong> ${seq.time_since_last_seq_hours.toFixed(1)} hours</div>
                <div><strong>Current Label:</strong> ${seq.label || 'Not Labeled'}</div>
            </div>

            <h4>Assign Label:</h4>
            <div class="label-selector">
                ${labels.map(label => `
                    <button class="label-btn ${seq.label === label ? 'selected' : ''}"
                            onclick="selectLabel('${label}')"
                            data-label="${label}">
                        ${label}
                    </button>
                `).join('')}
            </div>

            <button class="action-btn" onclick="saveLabel()" style="margin: 20px 0;">
                Save Label
            </button>

            <h4>Raw Events (${seq.raw_events.length}):</h4>
            <div class="event-list">
                ${seq.raw_events.map(event => {
        const eventTime = new Date(event.timestamp).toLocaleString('en-AU', {
            timeZone: 'Australia/Perth',
            hour12: true,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        return `
                        <div class="event-item">
                            <strong>${eventTime}</strong> - ${event.sensor_name}: ${event.event}
                        </div>
                    `;
    }).join('')}
            </div>
        </div>
    `;
}

function selectLabel(label) {
    document.querySelectorAll('.label-btn').forEach(btn => {
        btn.classList.remove('selected');
    });
    event.target.classList.add('selected');
}

async function saveLabel() {
    const selectedBtn = document.querySelector('.label-btn.selected');
    if (!selectedBtn) {
        alert('Please select a label');
        return;
    }

    const label = selectedBtn.dataset.label;

    try {
        const response = await fetch(`/api/sequences/${currentSequenceId}/label`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ label: label })
        });

        const data = await response.json();

        if (data.success) {
            alert('Label saved successfully!');
            closeModal();
            await loadStatistics();
            await loadSequences(currentPage);
        } else {
            alert(`Error: ${data.error}`);
        }
    } catch (error) {
        alert(`Error saving label: ${error.message}`);
    }
}

function closeModal() {
    document.getElementById('sequenceModal').classList.remove('active');
    currentSequenceId = null;
}

// Initial load
fetch('/api/sensors')
    .then(response => response.json())
    .then(data => updateSensorGrid(data.sensors))
    .catch(error => console.error('Error loading sensors:', error));
