/**
 * static/js/dashboard.js
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
    this.bindEvents();
    this.refreshGrid();
    this.loadWhoIsHome();
    window.dashboard = this;
  }

  bindEvents() {
    socket.on("sensor_update", (data) => {
      if (data.all_sensors) this.renderSensorGrid(data.all_sensors);
      else this.refreshGrid();
    });
    socket.on("presence_update", () => this.loadWhoIsHome());
  }

  async refreshGrid() {
    try {
      const data = await Utils.fetchJson("/api/sensors");
      if (data.sensors) this.renderSensorGrid(data.sensors);
    } catch (e) {
      console.error(e);
    }
  }

  async toggleRelay(sensorId) {
    try {
      await fetch(`/api/sensors/${sensorId}/toggle`, { method: "POST" });
    } catch (e) {
      alert("Error communicating with device.");
    }
  }

  renderSensorGrid(sensors) {
    if (!this.elements.grid) return;
    const activeCount = sensors.filter((s) => s.value === 1 && s.type !== "relay").length;
    this.updateSystemSummary(activeCount);

    this.elements.grid.innerHTML = sensors
      .map((sensor) => {
        const isActive = sensor.value === 1;
        let type = (sensor.type || "motion").toLowerCase();
        if (type.includes("contact")) type = "door";
        if (type.includes("pir")) type = "motion";

        // --- RELAY CARD ---
        if (type === "relay") {
          const activeClass = isActive ? "active-relay" : "";
          const btnLabel = isActive ? "Turn Off" : "Turn On";
          // We add the 'active-relay' class to the main card if it is active
          return `
            <div class="glass-card ${activeClass}" id="card-${sensor.id}">
                <div class="sensor-header">
                   <div>
                      <div class="sensor-name">${sensor.name}</div>
                      <div class="sensor-meta">${isActive ? "Active" : "Off"}</div>
                   </div>
                   <div class="sensor-icon">💡</div>
                </div>
                <div style="margin-top: auto;">
                    <button class="btn btn-sm btn-block ${
                      isActive ? "btn-primary" : "btn-secondary"
                    }" 
                        onclick="window.dashboard.toggleRelay(${sensor.id})">${btnLabel}</button>
                </div>
            </div>`;
        }

        // --- SENSOR CARD (Motion/Door) ---
        let iconHtml = "";
        if (type === "door") {
          iconHtml = isActive ? CONFIG.icons.doorActive : CONFIG.icons.doorInactive;
        } else {
          iconHtml = isActive ? CONFIG.icons.motionActive : CONFIG.icons.motionInactive;
        }
        const activeClass = isActive ? `active-${type}` : "";
        const statusText = isActive ? (type === "door" ? "Open" : "Detected") : "Secure";

        return `
            <div class="glass-card ${activeClass}" id="card-${sensor.id}">
                <div class="sensor-header">
                    <div>
                        <div class="sensor-name">${sensor.name}</div>
                        <div class="sensor-meta" style="color: ${
                          isActive ? "inherit" : "var(--color-text-muted)"
                        }; font-weight: ${isActive ? "600" : "400"}">
                            ${statusText}
                        </div>
                    </div>
                    <div class="sensor-icon">${iconHtml}</div>
                </div>
                
                <div style="margin-top: auto; padding-top: 16px; border-top: 1px solid rgba(0,0,0,0.05);">
                    <div style="display:flex; justify-content:space-between; font-size: 0.8rem;" class="text-muted">
                        <span>Last Event</span>
                        <span>${Utils.timeAgo(sensor.last_activity)}</span>
                    </div>
                </div>
            </div>`;
      })
      .join("");
    if (window.lucide) {
      window.lucide.createIcons({
        root: this.elements.grid,
      });
    }
  }

  updateSystemSummary(activeCount) {
    if (!this.elements.summary) return;
    if (activeCount === 0) {
      this.elements.summary.innerHTML = `
        <div class="glass-panel" style="padding: 16px; display: flex; align-items: center; gap: 16px;">
            <div style="background: rgba(16, 185, 129, 0.1); color: #059669; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; border-radius: 50%;">✓</div>
            <div>
                <div style="font-weight: 600;">System Secure</div>
                <div class="text-muted" style="font-size: 0.9rem;">All sensors are quiet</div>
            </div>
        </div>`;
    } else {
      this.elements.summary.innerHTML = `
        <div class="glass-panel" style="padding: 16px; display: flex; align-items: center; gap: 16px; border: 1px solid var(--color-danger);">
            <div style="background: var(--color-danger-bg); color: var(--color-danger); width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; border-radius: 50%;">!</div>
            <div>
                <div style="font-weight: 600; color: var(--color-danger);">Activity Detected</div>
                <div class="text-muted" style="font-size: 0.9rem;">${activeCount} sensor(s) currently active</div>
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
          this.elements.widgetList.innerHTML =
            '<span class="text-muted" style="font-size: 0.9rem;">No one is home.</span>';
          return;
        }
        data.people_home.forEach((person) => {
          if (person === "Unknown") return;
          const chip = document.createElement("span");
          chip.className = "chip active";
          chip.innerHTML = `👤 ${person}`;
          this.elements.widgetList.appendChild(chip);
        });
        // Unknowns
        if (data.count > data.people_home.length) {
          const diff = data.count - data.people_home.length;
          if (diff > 0) {
            const chip = document.createElement("span");
            chip.className = "chip";
            chip.innerHTML = `${diff} Unknown Device(s)`;
            this.elements.widgetList.appendChild(chip);
          }
        }
      }
    } catch (e) {
      console.error(e);
    }
  }
}
window.dashboard = new DashboardController();
