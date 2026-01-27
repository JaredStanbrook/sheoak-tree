/**
 * static/js/dashboard.js
 * Scalable Card Renderer Architecture
 * Supports: Sensors, Relays, Environmental, Audio, Camera, and custom types
 */
import { Utils } from "./core.js";

// ============================================================
// CARD RENDERERS - Each hardware type gets its own renderer
// ============================================================

class CardRenderer {
  /**
   * Base class for card renderers
   * Override getFooter() and getHeader() for custom layouts
   */
  constructor(hw) {
    this.hw = hw;
    this.props = this.getRenderProps();
  }

  getRenderProps() {
    const ui = this.hw.ui || {
      text: "Loading...",
      color: "status-inactive",
      icon: "help-circle",
      active: false,
    };

    return {
      statusText: ui.text,
      statusClass: ui.color,
      iconName: ui.icon,
      timeAgo: this.hw.lastActivity ? Utils.timeAgo(this.hw.lastActivity) : "Never",
      cardActiveClass: ui.active ? "is-active" : "",
      isActive: ui.active,
      value: this.hw.value,
      unit: this.hw.unit || "",
    };
  }

  getHeader() {
    return `
      <div class="hardware-header">
        <div>
          <div class="hardware-name">${Utils.escape(this.hw.name)}</div>
          <div class="hardware-meta ${this.props.statusClass}">${this.props.statusText}</div>
        </div>
        <div class="hardware-icon">
          <i data-lucide="${this.props.iconName}"></i>
        </div>
      </div>
    `;
  }

  getFooter() {
    // Default: show last activity time
    return `
      <div class="hardware-footer-meta">
        <span class="text-muted text-xs">Last Event</span>
        <span class="text-xs js-time-ago">${this.props.timeAgo}</span>
      </div>
    `;
  }

  render() {
    return `
      ${this.getHeader()}
      <div class="hardware-footer-wrapper" id="hw-footer-${this.hw.hardware_id}">
        ${this.getFooter()}
      </div>
    `;
  }
}

// ============================================================
// SPECIALIZED RENDERERS
// ============================================================

class RelayCardRenderer extends CardRenderer {
  getFooter() {
    const btnClass = this.props.isActive ? "btn-primary" : "btn-primary";
    const btnText = this.props.isActive ? "Turn Off" : "Turn On";

    return `
      <button class="btn btn-sm btn-block ${btnClass} js-action-toggle" 
              data-id="${this.hw.hardware_id}">
        ${btnText}
      </button>
    `;
  }
}

class EnvironmentalCardRenderer extends CardRenderer {
  /**
   * For temperature, humidity, pressure, rain level, etc.
   * Shows a large numeric value with unit
   */
  getFooter() {
    const { value, unit } = this.props;
    const displayValue = this.formatValue(value, unit);

    return `
      <div class="hardware-footer-environmental">
        <div class="environmental-reading">
          <span class="reading-value">${displayValue}</span>
          <span class="reading-unit">${this.getUnitSymbol(unit)}</span>
        </div>
        <div class="environmental-timestamp">
          <span class="text-muted text-xs">Updated</span>
          <span class="text-xs js-time-ago">${this.props.timeAgo}</span>
        </div>
      </div>
    `;
  }

  formatValue(value, unit) {
    if (value === null || value === undefined) return "--";

    // Round to 1 decimal for most environmental readings
    if (["celsius", "fahrenheit", "humidity", "pressure"].includes(unit)) {
      return Number(value).toFixed(1);
    }

    return Number(value).toFixed(0);
  }

  getUnitSymbol(unit) {
    const symbols = {
      celsius: "°C",
      fahrenheit: "°F",
      humidity: "%",
      pressure: "hPa",
      rain_level: "mm",
      lux: "lx",
      decibels: "dB",
      percentage: "%",
    };
    return symbols[unit] || unit;
  }
}

class AudioCardRenderer extends CardRenderer {
  /**
   * For microphones, speakers, push-to-talk
   * Shows audio controls
   */
  getFooter() {
    const { value } = this.props;

    // For decibel sensors, show level bar
    if (this.hw.unit === "decibels") {
      const percentage = Math.min(100, (value / 100) * 100);
      return `
        <div class="hardware-footer-audio">
          <div class="audio-level-bar">
            <div class="audio-level-fill" style="width: ${percentage}%"></div>
          </div>
          <div class="audio-reading">
            <span>${value.toFixed(0)} dB</span>
            <span class="text-muted text-xs js-time-ago">${this.props.timeAgo}</span>
          </div>
        </div>
      `;
    }

    // For PTT speakers, show action button
    return `
      <button class="btn btn-sm btn-block btn-primary js-action-speak" 
              data-id="${this.hw.hardware_id}">
        <i data-lucide="mic"></i> Push to Talk
      </button>
    `;
  }
}

class CameraCardRenderer extends CardRenderer {
  /**
   * For cameras - shows snapshot preview
   */
  getHeader() {
    return `
      <div class="hardware-header hardware-header-camera">
        <div class="camera-preview" id="camera-preview-${this.hw.hardware_id}">
          <img src="/api/cameras/${this.hw.hardware_id}/snapshot" 
               alt="${Utils.escape(this.hw.name)}"
               onerror="this.src='/static/img/camera-offline.png'">
        </div>
        <div class="camera-overlay">
          <div class="hardware-name">${Utils.escape(this.hw.name)}</div>
          <div class="hardware-meta ${this.props.statusClass}">${this.props.statusText}</div>
        </div>
      </div>
    `;
  }

  getFooter() {
    return `
      <div class="hardware-footer-camera">
        <button class="btn btn-sm btn-primary js-action-view-feed" 
                data-id="${this.hw.hardware_id}">
          <i data-lucide="video"></i> View Live
        </button>
        <button class="btn btn-sm btn-primary js-action-capture" 
                data-id="${this.hw.hardware_id}">
          <i data-lucide="camera"></i> Capture
        </button>
      </div>
    `;
  }
}

class BinarySensorCardRenderer extends CardRenderer {
  /**
   * For motion sensors, door/window sensors
   * Standard sensor card with time tracking
   */
  // Uses default implementation, but included for clarity
}

// ============================================================
// RENDERER FACTORY
// ============================================================

class CardRendererFactory {
  static create(hw) {
    // Match by type first
    const typeMap = {
      relay: RelayCardRenderer,
      camera: CameraCardRenderer,
      thermostat: EnvironmentalCardRenderer,
    };

    if (typeMap[hw.type]) {
      return new typeMap[hw.type](hw);
    }

    // Match by unit (for environmental sensors)
    const unitMap = {
      celsius: EnvironmentalCardRenderer,
      fahrenheit: EnvironmentalCardRenderer,
      humidity: EnvironmentalCardRenderer,
      pressure: EnvironmentalCardRenderer,
      rain_level: EnvironmentalCardRenderer,
      lux: EnvironmentalCardRenderer,
      decibels: AudioCardRenderer,
    };

    if (hw.unit && unitMap[hw.unit]) {
      return new unitMap[hw.unit](hw);
    }

    // Default: binary sensor
    return new BinarySensorCardRenderer(hw);
  }
}

// ============================================================
// DASHBOARD CONTROLLER
// ============================================================

class DashboardController {
  constructor() {
    this.elements = {
      grid: document.getElementById("hardwares-grid"),
      summary: document.getElementById("system-summary"),
      widgetList: document.getElementById("people-list"),
      widgetCount: document.getElementById("home-count"),
    };

    this.state = new Map();
    this.handleGridClick = this.handleGridClick.bind(this);
    this.handleHardwareUpdate = this.handleHardwareUpdate.bind(this);
    this.handlePresenceUpdate = this.handlePresenceUpdate.bind(this);
    this.updateRelativeTimes = this.updateRelativeTimes.bind(this);

    this.init();
  }

  init() {
    this.bindEvents();
    this.initGrid();
    this.loadWhoIsHome();
    this.startTimers();
  }

  startTimers() {
    setInterval(this.updateRelativeTimes, 1000);
  }

  updateRelativeTimes() {
    this.state.forEach((hw, id) => {
      if (!hw.lastActivity) return;

      const card = document.getElementById(`hw-card-${id}`);
      if (!card) return;

      const timeEl = card.querySelector(".js-time-ago");
      if (!timeEl) return;

      const newTimeStr = Utils.timeAgo(hw.lastActivity);
      if (timeEl.textContent !== newTimeStr) {
        timeEl.textContent = newTimeStr;
      }
    });
  }

  bindEvents() {
    if (this.elements.grid) {
      this.elements.grid.addEventListener("click", this.handleGridClick);
    }

    window.addEventListener("hardware_update", this.handleHardwareUpdate);
    window.addEventListener("presence_update", this.handlePresenceUpdate);
  }

  // ============================================================
  // DOM MANIPULATION
  // ============================================================

  async initGrid() {
    try {
      const data = await Utils.fetchJson("/api/hardwares");
      if (!data.hardwares || !Array.isArray(data.hardwares)) return;

      const currentIds = new Set();

      data.hardwares.forEach((raw) => {
        if (raw.lastActivity && typeof raw.lastActivity === "string") {
          raw.lastActivity = new Date(raw.lastActivity);
        }
        currentIds.add(raw.hardware_id);
        this.renderCard(raw);
        this.state.set(raw.hardware_id, raw);
      });

      this.state.forEach((_, id) => {
        if (!currentIds.has(id)) this.removeCard(id);
      });

      this.refreshSummary();
      this.refreshIcons();
    } catch (e) {
      console.error("Dashboard Sync Failed:", e);
    }
  }

  renderCard(hw) {
    if (!this.elements.grid) return;
    const existingCard = document.getElementById(`hw-card-${hw.hardware_id}`);

    if (existingCard) {
      this.updateCard(existingCard, hw);
    } else {
      this.createCard(hw);
    }
  }

  createCard(hw) {
    const renderer = CardRendererFactory.create(hw);
    const card = document.createElement("div");

    card.id = `hw-card-${hw.hardware_id}`;
    card.className = `card hardware-card ${renderer.props.cardActiveClass}`;
    card.dataset.type = hw.type;
    card.dataset.unit = hw.unit || "";
    card.innerHTML = renderer.render();

    this.elements.grid.appendChild(card);
  }

  updateCard(card, hw) {
    // Full re-render for simplicity (could optimize later)
    const renderer = CardRendererFactory.create(hw);

    // Update active state
    if (renderer.props.isActive) {
      card.classList.add("is-active");
    } else {
      card.classList.remove("is-active");
    }

    // Re-render content
    card.innerHTML = renderer.render();
    this.refreshIcons(card);
  }

  removeCard(id) {
    const card = document.getElementById(`hw-card-${id}`);
    if (card) card.remove();
    this.state.delete(id);
  }

  refreshIcons(rootNode) {
    if (window.lucide) {
      window.lucide.createIcons({
        root: rootNode,
        nameAttr: "data-lucide",
      });
    }
  }

  refreshSummary() {
    let activeCount = 0;
    this.state.forEach((hw) => {
      const isActive = hw.ui ? hw.ui.active : Boolean(hw.value);
      if (isActive && hw.type !== "relay") {
        activeCount++;
      }
    });
    this.updateSystemSummary(activeCount);
  }

  // ============================================================
  // EVENT HANDLERS
  // ============================================================

  async handleGridClick(e) {
    // Toggle handler
    const toggleBtn = e.target.closest(".js-action-toggle");
    if (toggleBtn && !toggleBtn.disabled) {
      const id = parseInt(toggleBtn.dataset.id, 10);
      if (!isNaN(id)) await this.toggleHardware(id, toggleBtn);
      return;
    }

    // Camera feed handler
    const viewFeedBtn = e.target.closest(".js-action-view-feed");
    if (viewFeedBtn) {
      const id = parseInt(viewFeedBtn.dataset.id, 10);
      window.location.href = `/cameras/${id}/live`;
      return;
    }

    // PTT handler
    const speakBtn = e.target.closest(".js-action-speak");
    if (speakBtn && !speakBtn.disabled) {
      const id = parseInt(speakBtn.dataset.id, 10);
      await this.handlePushToTalk(id, speakBtn);
      return;
    }
  }

  async toggleHardware(id, btn) {
    const originalText = btn.textContent;
    btn.textContent = "...";
    btn.disabled = true;

    try {
      const res = await fetch(`/hardwares/${id}/toggle`, { method: "POST" });
      if (!res.ok) throw new Error("Toggle failed");

      // Get the new state from response
      const data = await res.json();

      // Update state
      const hw = this.state.get(id);
      if (hw && data.hardware) {
        // Merge the updated hardware data
        hw.value = data.hardware.value;
        if (data.hardware.ui) {
          hw.ui = data.hardware.ui;
        }
        hw.lastActivity = new Date();

        // Re-render
        this.renderCard(hw);
        this.refreshSummary();
      }
    } catch (err) {
      console.error("Toggle Error:", err);
      alert("Failed to toggle device");
      btn.textContent = originalText;
    } finally {
      btn.disabled = false;
    }
  }

  async handlePushToTalk(id, btn) {
    // Placeholder for PTT implementation
    console.log("Push to talk for hardware:", id);
    alert("Push to talk feature coming soon!");
  }

  handleHardwareUpdate(e) {
    const data = e.detail;
    if (!data || !data.hardware_id) return;

    const hw = this.state.get(data.hardware_id);
    if (hw) {
      hw.value = data.value;
      hw.unit = data.unit || hw.unit;
      if (data.ui) hw.ui = data.ui;
      if (data.timestamp) hw.lastActivity = new Date(data.timestamp);

      this.renderCard(hw);
      this.refreshSummary();
    }
  }

  handlePresenceUpdate() {
    this.loadWhoIsHome();
  }

  // ============================================================
  // AUXILIARY WIDGETS
  // ============================================================

  updateSystemSummary(activeCount) {
    if (!this.elements.summary) return;

    if (activeCount === 0) {
      this.elements.summary.innerHTML = `
        <div class="card status-card-safe">
          <div>
            <div class="font-bold">System Secure</div>
            <div class="text-muted text-sm">All sensors are quiet</div>
          </div>
        </div>`;
    } else {
      this.elements.summary.innerHTML = `
        <div class="card is-active">
          <div>
            <div class="font-bold text-danger">Activity Detected</div>
            <div class="text-muted text-sm">${activeCount} sensor(s) active</div>
          </div>
        </div>`;
    }
  }

  async loadWhoIsHome() {
    if (!this.elements.widgetList) return;

    try {
      const data = await Utils.fetchJson("/api/devices/home");
      if (!data.success) return;

      if (this.elements.widgetCount) {
        this.elements.widgetCount.textContent = data.count;
      }

      this.elements.widgetList.innerHTML = "";

      if (data.count === 0) {
        this.elements.widgetList.innerHTML =
          '<span class="text-muted text-sm">No one is home.</span>';
        return;
      }

      data.people_home.forEach((person) => {
        if (!person || person === "Unknown") return;
        const chip = document.createElement("button");
        chip.className = "btn btn-sm btn-primary";
        chip.textContent = `👤 ${person}`;
        this.elements.widgetList.appendChild(chip);
      });

      const knownCount = data.people_home.length;
      if (data.count > knownCount) {
        const diff = data.count - knownCount;
        const chip = document.createElement("button");
        chip.className = "btn btn-sm btn-primary";
        chip.addEventListener("click", () => (window.location.href = "/presence"));
        chip.textContent = `${diff} Unknown Device(s)`;
        this.elements.widgetList.appendChild(chip);
      }
    } catch (e) {
      console.error("Presence Load Error:", e);
    }
  }
}

// Initialize when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  new DashboardController();
});
