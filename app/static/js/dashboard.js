/**
 * static/js/dashboard.js
 * Handles the "Live" page: Sensor Grid and Presence Widget
 */
import { socket, Utils, CONFIG } from "./core.js";

class DashboardController {
  constructor() {
    this.elements = {
      grid: document.getElementById("sensors-grid"),
      summary: document.getElementById("system-summary"),
      widgetList: document.getElementById("people-list"),
      widgetCount: document.getElementById("home-count"),
    };

    // 1. Bind Socket Events specific to this page
    this.bindEvents();

    // 2. Trigger Initial Data Load
    this.refreshGrid();
    this.loadWhoIsHome();

    // Expose instance for HTML onclick events (like toggleRelay)
    window.dashboard = this;
  }

  bindEvents() {
    // When the server sends a sensor update, refresh the grid
    socket.on("sensor_update", (data) => {
      // If data.all_sensors exists, it's a full refresh
      if (data.all_sensors) {
        this.renderSensorGrid(data.all_sensors);
      }
      // If it's a single event, we might want to re-fetch or handle partial updates
      // For simplicity, we re-fetch to ensure sync
      else {
        this.refreshGrid();
      }
    });

    // When someone arrives/leaves, refresh the presence widget
    socket.on("presence_update", () => {
      this.loadWhoIsHome();
    });
  }

  async refreshGrid() {
    try {
      const data = await Utils.fetchJson("/api/sensors");
      if (data.sensors) this.renderSensorGrid(data.sensors);
    } catch (e) {
      console.error("Grid load failed", e);
    }
  }

  async toggleRelay(sensorId) {
    try {
      console.log(`Toggling sensor ${sensorId}...`);
      await fetch(`/api/sensors/${sensorId}/toggle`, { method: "POST" });
    } catch (error) {
      console.error("Failed to toggle relay:", error);
      alert("Error communicating with device.");
    }
  }

  renderSensorGrid(sensors) {
    if (!this.elements.grid) return;

    // Calculate system summary (Lights/Relays don't count as security alerts)
    const activeCount = sensors.filter((s) => s.value === 1 && s.type !== "relay").length;
    this.updateSystemSummary(activeCount);

    this.elements.grid.innerHTML = sensors
      .map((sensor) => {
        const isActive = sensor.value === 1;
        let type = (sensor.type || "motion").toLowerCase();

        // Normalize types
        if (type.includes("contact")) type = "door";
        if (type.includes("pir")) type = "motion";

        const activeClass = isActive ? "active" : "";

        // --- RELAY CARD ---
        if (type === "relay") {
          const btnLabel = isActive ? "TURN OFF" : "TURN ON";
          const btnClass = isActive ? "btn-active" : "";
          // Lightbulb SVG
          const bulbIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-1 1.5-2 1.5-3.5a6 6 0 0 0-11 0c0 1.5.5 2.5 1.5 3.5.8.8 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/></svg>`;

          return `
                <div class="sensor-card relay ${activeClass}" id="card-${sensor.id}">
                    <div>
                        <div class="sensor-name">
                            ${sensor.name}
                            <div class="sensor-icon">${bulbIcon}</div>
                        </div>
                        <div class="sensor-status">${isActive ? "ON" : "OFF"}</div>
                    </div>
                    <div class="sensor-details" style="margin-top: 15px;">
                        <button class="relay-toggle-btn ${btnClass}" onclick="window.dashboard.toggleRelay(${
            sensor.id
          })">
                            ${btnLabel}
                        </button>
                    </div>
                </div>`;
        }

        // --- SENSOR CARD ---
        const typeClass = type === "door" ? "door" : "motion";
        // Use icons from Core Config
        const iconHtml = type === "door" ? CONFIG.icons.door : CONFIG.icons.motion;

        let statusText = "SECURE";
        if (isActive) statusText = type === "door" ? "OPEN" : "DETECTED";

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
            </div>`;
      })
      .join("");
  }

  updateSystemSummary(activeCount) {
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

  async loadWhoIsHome() {
    if (!this.elements.widgetList) return;
    try {
      const data = await Utils.fetchJson("/api/presence/who-is-home");
      if (data.success && this.elements.widgetCount) {
        this.elements.widgetCount.textContent = data.count;
        this.elements.widgetList.innerHTML = "";

        if (data.count === 0) {
          this.elements.widgetList.innerHTML = '<span class="text-muted">No one is home.</span>';
          return;
        }

        data.people_home.forEach((person) => {
          if (person === "Unknown") return;
          const chip = document.createElement("span");
          chip.className = "person-chip home";
          chip.innerHTML = `👤 ${person}`;
          this.elements.widgetList.appendChild(chip);
        });

        if (this.elements.widgetList.children.length === 0 && data.count > 0) {
          this.elements.widgetList.innerHTML = `<span class="person-chip home">${data.count} Unknown Device(s)</span>`;
        }
      }
    } catch (e) {
      console.error("Presence Widget Error:", e);
    }
  }
}

// Initialize on page load
window.dashboard = new DashboardController();
