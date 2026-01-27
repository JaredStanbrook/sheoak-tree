// Presence Dashboard JavaScript
class PresenceDashboard {
  constructor() {
    this.devices = [];
    this.status = null;
    this.presenceHistory = [];
    this.selectedDevice = null;
    this.autoRefresh = true;
    this.filterTracked = false;
    this.refreshInterval = null;
    this.currentTab = "home";

    this.init();
  }

  init() {
    this.setupEventListeners();
    this.loadData();
    this.startAutoRefresh();
  }

  setupEventListeners() {
    // Auto-refresh toggle
    document.getElementById("autoRefreshBtn").addEventListener("click", () => {
      this.toggleAutoRefresh();
    });

    // Filter tracked devices
    document.getElementById("filterTrackedBtn").addEventListener("click", () => {
      this.filterTracked = !this.filterTracked;
      this.updateFilterButton();
      this.renderAllDevicesTable();
    });

    // Tab navigation
    const dashboardNav = document.getElementById("dashboardTabs");

    if (dashboardNav) {
      dashboardNav.querySelectorAll(".nav-item").forEach((tab) => {
        tab.addEventListener("click", (e) => {
          e.preventDefault();
          const tabName = tab.dataset.tab;
          this.switchTab(tabName);
        });
      });
    }

    // Modal tracking toggle
    const toggleBtn = document.getElementById("modalToggleTracking");
    if (toggleBtn) {
      toggleBtn.addEventListener("click", () => {
        if (this.selectedDevice) {
          this.toggleTracking(this.selectedDevice.id, this.selectedDevice.track_presence);
        }
      });
    }
  }

  switchTab(tabName) {
    // 1. Get the container for the dashboard tabs
    const dashboardNav = document.getElementById("dashboardTabs");
    if (!dashboardNav) return; // Safety check

    // 2. ONLY remove 'active' from items INSIDE the dashboard container
    dashboardNav.querySelectorAll(".nav-item").forEach((item) => {
      item.classList.remove("active");
    });

    // 3. Add 'active' to the clicked tab (also scoped to the container)
    const activeTab = dashboardNav.querySelector(`[data-tab="${tabName}"]`);
    if (activeTab) {
      activeTab.classList.add("active");
    }

    // Update tab panes (remains the same as long as IDs are unique)
    document.querySelectorAll(".tab-pane").forEach((pane) => {
      pane.style.display = "none";
    });

    const targetPane = document.getElementById(`${tabName}Tab`);
    if (targetPane) {
      targetPane.style.display = "block";
    }

    this.currentTab = tabName;
  }

  toggleAutoRefresh() {
    this.autoRefresh = !this.autoRefresh;
    const btn = document.getElementById("autoRefreshBtn");
    const text = document.getElementById("autoRefreshText");

    if (this.autoRefresh) {
      btn.className = "btn btn-sm btn-primary";
      text.textContent = "Auto-refresh ON";
      this.startAutoRefresh();
    } else {
      btn.className = "btn btn-sm btn-secondary";
      text.textContent = "Auto-refresh OFF";
      this.stopAutoRefresh();
    }
  }

  startAutoRefresh() {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
    }

    this.refreshInterval = setInterval(() => {
      if (this.autoRefresh) {
        this.loadData();
      }
    }, 5000);
  }

  stopAutoRefresh() {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
      this.refreshInterval = null;
    }
  }

  updateFilterButton() {
    const text = document.getElementById("filterTrackedText");

    if (this.filterTracked) {
      text.textContent = "Tracked Only";
    } else {
      text.textContent = "All Devices";
    }
  }

  async loadData() {
    await Promise.all([this.fetchDevices(), this.fetchStatus(), this.fetchHistory()]);

    this.render();
  }

  async fetchDevices() {
    try {
      const response = await fetch("/api/devices/");
      const data = await response.json();
      if (data.success) {
        this.devices = data.devices;
      }
    } catch (error) {
      console.error("Error fetching devices:", error);
    }
  }

  async fetchStatus() {
    try {
      const response = await fetch("/api/devices/status");
      const data = await response.json();
      if (data.success) {
        this.status = data;
      }
    } catch (error) {
      console.error("Error fetching status:", error);
    }
  }

  async fetchHistory() {
    try {
      const response = await fetch("/api/devices/status");
      const data = await response.json();
      if (data.success && data.recent_events) {
        this.presenceHistory = data.recent_events;
      }
    } catch (error) {
      console.error("Error fetching history:", error);
    }
  }

  async toggleTracking(deviceId, currentState) {
    try {
      const response = await fetch(`/api/devices/${deviceId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ track_presence: !currentState }),
      });

      if (response.ok) {
        await this.fetchDevices();
        this.render();

        // Update modal if open
        if (this.selectedDevice && this.selectedDevice.id === deviceId) {
          this.selectedDevice = this.devices.find((d) => d.id === deviceId);
          this.updateModalTracking();
        }
      }
    } catch (error) {
      console.error("Error toggling tracking:", error);
    }
  }

  render() {
    this.renderStatusCards();
    this.renderHomeDevices();
    this.renderAwayDevices();
    this.renderAllDevicesTable();
    this.renderActivity();
  }

  renderStatusCards() {
    if (!this.status) return;

    const stats = this.status.statistics;
    const system = this.status.system;

    // System status
    const statusDot = document.getElementById("systemStatusDot");
    const statusText = document.getElementById("systemStatusText");
    const statusMeta = document.getElementById("systemStatus");

    if (system.monitor_running) {
      statusDot.classList.add("connected");
      statusText.textContent = "Active";
      statusMeta.textContent = "Active";
    } else {
      statusDot.classList.remove("connected");
      statusText.textContent = "Offline";
      statusMeta.textContent = "Offline";
    }

    // Devices home
    document.getElementById("devicesHomeCount").textContent =
      `${stats.currently_home} / ${stats.total_devices}`;

    // Tracked devices
    document.getElementById("trackedCount").textContent = stats.tracked_devices;

    // Scan count
    document.getElementById("scanCount").textContent = system.scan_count || 0;
  }

  renderHomeDevices() {
    const homeDevices = this.devices.filter((d) => d.is_home);
    const container = document.getElementById("homeDevicesList");
    const countEl = document.getElementById("homeDeviceCount");

    countEl.textContent = homeDevices.length;

    if (homeDevices.length === 0) {
      container.innerHTML = '<p class="text-muted text-center">No devices currently home</p>';
      return;
    }

    container.innerHTML = homeDevices
      .map(
        (device) => `
      <div class="log-item" onclick="window.presenceDashboard.showDeviceDetail(${
        device.id
      })" style="cursor: pointer;">
        <div class="log-content">
          <strong>
            <i class="${this.getDeviceIcon(device)}"></i>
            ${this.escapeHtml(device.name)}
          </strong>
          <span>
            ${device.owner ? this.escapeHtml(device.owner) + " • " : ""}
            ${device.last_ip || "No IP"}
            ${
              device.is_randomized_mac
                ? ' • <i class="bi bi-shield-check" title="Randomized MAC"></i>'
                : ""
            }
            ${
              device.linked_to_device_id
                ? ' • <i class="bi bi-link-45deg" title="Linked device"></i>'
                : ""
            }
          </span>
        </div>
        <div class="log-time">${this.formatTimestamp(device.last_seen)}</div>
      </div>
    `,
      )
      .join("");
  }

  renderAwayDevices() {
    const awayDevices = this.devices.filter((d) => !d.is_home && d.track_presence);
    const container = document.getElementById("awayDevicesList");
    const countEl = document.getElementById("awayDeviceCount");

    countEl.textContent = awayDevices.length;

    if (awayDevices.length === 0) {
      container.innerHTML = '<p class="text-muted text-center">Everyone is home!</p>';
      return;
    }

    container.innerHTML = awayDevices
      .map(
        (device) => `
      <div class="log-item" onclick="window.presenceDashboard.showDeviceDetail(${
        device.id
      })" style="cursor: pointer; opacity: 0.7;">
        <div class="log-content">
          <strong>
            <i class="${this.getDeviceIcon(device)}"></i>
            ${this.escapeHtml(device.name)}
          </strong>
          <span>
            ${device.owner ? this.escapeHtml(device.owner) + " • " : ""}
            Last seen ${this.formatTimestamp(device.last_seen)}
          </span>
        </div>
      </div>
    `,
      )
      .join("");
  }

  renderAllDevicesTable() {
    const displayDevices = this.filterTracked
      ? this.devices.filter((d) => d.track_presence)
      : this.devices;

    const tbody = document.getElementById("allDevicesTable");
    const countEl = document.getElementById("allDeviceCount");

    countEl.textContent = displayDevices.length;

    if (displayDevices.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="6" class="text-center text-muted">No devices found</td></tr>';
      return;
    }

    tbody.innerHTML = displayDevices
      .map(
        (device) => `
      <tr style="cursor: pointer;" onclick="window.presenceDashboard.showDeviceDetail(${
        device.id
      })">
        <td>
          <div style="display: flex; align-items: center; gap: 8px;">
            <i class="${this.getDeviceIcon(device)}"></i>
            <div>
              <div class="hardware-name" style="font-size: 0.9rem;">${this.escapeHtml(
                device.name,
              )}</div>
              ${
                device.owner
                  ? `<small class="text-muted">${this.escapeHtml(device.owner)}</small>`
                  : ""
              }
            </div>
          </div>
        </td>
        <td>
          <span class="badge ${device.is_home ? "status-active" : "status-safe"}">
            ${device.is_home ? "Home" : "Away"}
          </span>
        </td>
        <td>
          <div style="display: flex; align-items: center; gap: 6px;">
            <code class="text-mono">${device.mac_address}</code>
            ${device.is_randomized_mac ? '<i class="bi bi-shield-check"></i>' : ""}
            ${device.linked_to_device_id ? '<i class="bi bi-link-45deg"></i>' : ""}
          </div>
        </td>
        <td class="text-muted">${device.last_ip || "-"}</td>
        <td class="text-muted">${this.formatTimestamp(device.last_seen)}</td>
        <td class="text-right">
          <button 
            class="btn btn-sm ${device.track_presence ? "btn-primary" : "btn-secondary"}"
            onclick="event.stopPropagation(); window.presenceDashboard.toggleTracking(${
              device.id
            }, ${device.track_presence})"
          >
            ${device.track_presence ? "Enabled" : "Disabled"}
          </button>
        </td>
      </tr>
    `,
      )
      .join("");
  }

  renderActivity() {
    const container = document.getElementById("activityList");

    if (this.presenceHistory.length === 0) {
      container.innerHTML = '<p class="text-muted text-center">No recent activity</p>';
      return;
    }

    container.innerHTML = this.presenceHistory
      .map(
        (event) => `
      <div class="log-item type-${event.event_type === "arrived" ? "motion" : "door"}">
        <div class="log-content">
          <strong>
            <i class="bi ${event.event_type === "arrived" ? "bi-wifi" : "bi-wifi-off"}"></i>
            ${this.escapeHtml(event.device_name)}
          </strong>
          <span>
            ${event.event_type === "arrived" ? "Arrived home" : "Left home"}
            ${event.ip_address ? " • " + event.ip_address : ""}
          </span>
        </div>
        <div class="log-time">${this.formatTimestamp(event.timestamp)}</div>
      </div>
    `,
      )
      .join("");
  }

  showDeviceDetail(deviceId) {
    this.selectedDevice = this.devices.find((d) => d.id === deviceId);
    if (!this.selectedDevice) return;

    const modal = document.getElementById("deviceDetailModal");

    // Set basic info
    document.getElementById("modalDeviceName").textContent = this.selectedDevice.name;
    const ownerEl = document.getElementById("modalDeviceOwner");
    if (this.selectedDevice.owner) {
      ownerEl.textContent = this.selectedDevice.owner;
      ownerEl.style.display = "block";
    } else {
      ownerEl.style.display = "none";
    }

    // Status
    document.getElementById("modalStatus").textContent = this.selectedDevice.is_home
      ? "Home"
      : "Away";

    // Last seen
    document.getElementById("modalLastSeen").textContent = this.formatTimestamp(
      this.selectedDevice.last_seen,
    );

    // MAC
    document.getElementById("modalMac").textContent = this.selectedDevice.mac_address;

    // IP
    document.getElementById("modalIp").textContent = this.selectedDevice.last_ip || "Unknown";

    // Hostname
    if (this.selectedDevice.hostname) {
      document.getElementById("modalHostname").style.display = "block";
      document.getElementById("modalHostnameValue").textContent = this.selectedDevice.hostname;
    } else {
      document.getElementById("modalHostname").style.display = "none";
    }

    // Vendor
    if (this.selectedDevice.vendor) {
      document.getElementById("modalVendor").style.display = "block";
      document.getElementById("modalVendorValue").textContent = this.selectedDevice.vendor;
    } else {
      document.getElementById("modalVendor").style.display = "none";
    }

    // Random MAC warning
    if (this.selectedDevice.is_randomized_mac) {
      document.getElementById("modalRandomMacWarning").style.display = "flex";
      let warningText = "This device uses MAC address randomization for privacy.";
      if (this.selectedDevice.linked_to_device_id && this.selectedDevice.link_confidence) {
        warningText += ` Linked to primary device (confidence: ${(
          this.selectedDevice.link_confidence * 100
        ).toFixed(0)}%)`;
      }
      document.getElementById("modalRandomMacText").textContent = warningText;
    } else {
      document.getElementById("modalRandomMacWarning").style.display = "none";
    }

    // Linked MACs
    if (this.selectedDevice.linked_macs && this.selectedDevice.linked_macs.length > 0) {
      document.getElementById("modalLinkedMacs").style.display = "block";
      document.getElementById("linkedMacCount").textContent =
        this.selectedDevice.linked_macs.length;

      const linkedList = this.selectedDevice.linked_macs
        .map(
          (linked) => `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--border-subtle);">
          <code class="text-mono">${linked.mac}</code>
          <span class="text-muted text-xs">${(linked.confidence * 100).toFixed(
            0,
          )}% confidence</span>
        </div>
      `,
        )
        .join("");

      document.getElementById("linkedMacsList").innerHTML = linkedList;
    } else {
      document.getElementById("modalLinkedMacs").style.display = "none";
    }

    this.updateModalTracking();
    modal.classList.add("active");
  }

  closeModal() {
    document.getElementById("deviceDetailModal").classList.remove("active");
  }

  updateModalTracking() {
    const btn = document.getElementById("modalToggleTracking");
    if (this.selectedDevice.track_presence) {
      btn.textContent = "Disable Tracking";
      btn.className = "btn btn-primary btn-block";
    } else {
      btn.textContent = "Enable Tracking";
      btn.className = "btn btn-secondary btn-block";
    }
  }

  getDeviceIcon(device) {
    const hostname = (device.hostname || "").toLowerCase();
    const metadata = device.device_metadata || {};

    if (
      hostname.includes("iphone") ||
      hostname.includes("android") ||
      hostname.includes("galaxy")
    ) {
      return "bi bi-phone";
    }
    if (hostname.includes("macbook") || hostname.includes("laptop")) {
      return "bi bi-laptop";
    }
    if (hostname.includes("tv") || metadata.os === "Tizen") {
      return "bi bi-tv";
    }
    return "bi bi-question-circle";
  }

  formatTimestamp(timestamp) {
    if (!timestamp) return "Never";

    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return date.toLocaleDateString();
  }

  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }
}

// Initialize dashboard when DOM is ready
window.presenceDashboard = null;
document.addEventListener("DOMContentLoaded", () => {
  window.presenceDashboard = new PresenceDashboard();
});

// Cleanup on page unload
window.addEventListener("beforeunload", () => {
  if (window.presenceDashboard) {
    window.presenceDashboard.stopAutoRefresh();
  }
});
