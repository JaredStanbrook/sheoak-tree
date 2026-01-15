/**
 * static/js/dashboard.js
 * Unified Architecture: Adapter Pattern + Defensive State Management
 */
import { Utils } from "./core.js";

// ============================================================
// HARDWARE ADAPTER CONFIGURATION
// Single source of truth for hardware type behavior
// ============================================================

const HARDWARE_DEFAULTS = {
  relay: {
    inactiveIcon: "power-off",
    activeIcon: "power",
    inactiveLabel: "Off",
    activeLabel: "On",
    colorOn: "status-active",
    colorOff: "status-inactive",
  },

  contact_sensor: {
    inactiveIcon: "rows-2",
    activeIcon: "rectangle-horizontal",
    inactiveLabel: "Secure",
    activeLabel: "Open",
    colorOn: "status-warning",
    colorOff: "status-safe",
  },

  motion_sensor: {
    inactiveIcon: "eye-off",
    activeIcon: "eye",
    inactiveLabel: "No Motion",
    activeLabel: "Motion Detected",
    colorOn: "status-danger",
    colorOff: "status-safe",
  },

  // Fallback
  __unknown__: {
    inactiveIcon: "help-circle",
    activeIcon: "help-circle",
    inactiveLabel: "Unknown",
    activeLabel: "Unknown",
    colorOn: "status-warning",
    colorOff: "status-inactive",
  },
};

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

    // State: Maps hardware ID -> Hardware Object
    this.state = new Map();

    // Bind methods to preserve 'this' context
    this.handleGridClick = this.handleGridClick.bind(this);
    this.handleHardwareUpdate = this.handleHardwareUpdate.bind(this);
    this.handlePresenceUpdate = this.handlePresenceUpdate.bind(this);
    this.refreshSummary = this.refreshSummary.bind(this);
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
    // Run every 1 second to keep "Xs ago" fresh
    setInterval(this.updateRelativeTimes, 1000);
  }

  updateRelativeTimes() {
    this.state.forEach((hw, id) => {
      // 1. Skip if no activity record
      if (!hw.lastActivity) return;

      // 2. Skip relays (they have buttons, not time text)
      if (hw.type === "relay") return;

      // 3. Find the specific DOM element
      const card = document.getElementById(`hw-card-${id}`);
      if (!card) return;

      const timeEl = card.querySelector(".js-time-ago");
      if (!timeEl) return;

      // 4. Calculate fresh string
      const newTimeStr = Utils.timeAgo(hw.lastActivity);

      // 5. Update only if changed (prevents unnecessary layout thrashing)
      if (timeEl.textContent !== newTimeStr) {
        timeEl.textContent = newTimeStr;
      }
    });
  }
  bindEvents() {
    // Event delegation for grid interactions
    if (this.elements.grid) {
      this.elements.grid.addEventListener("click", this.handleGridClick);
    }

    // Global event listeners for real-time updates
    window.addEventListener("hardware_update", this.handleHardwareUpdate);
    window.addEventListener("presence_update", this.handlePresenceUpdate);
  }
  // ============================================================
  // RENDER STRATEGIES
  // ============================================================

  /**
   * Generates render properties.
   * Relies on the 'ui' object sent from the Python backend.
   */
  getRenderProps(hw) {
    // 1. Defensively get the UI object (fallback provided for safety)
    const ui = hw.ui || {
      text: "Loading...",
      color: "status-inactive",
      icon: "help-circle",
      active: false,
    };

    const isActive = ui.active;

    return {
      statusText: ui.text,
      statusClass: ui.color,
      iconName: ui.icon,
      // Time calc remains client-side for "X seconds ago" accuracy
      timeAgo: hw.lastActivity ? Utils.timeAgo(hw.lastActivity) : "Never",
      cardActiveClass: isActive ? "is-active" : "",
      isActive: isActive,
    };
  }

  /**
   * Determines footer content based on adapter's render mode.
   */
  getCardFooter(hw) {
    const { type, id } = hw;
    // We still check type for the button interaction,
    // but visual state comes from getRenderProps
    if (type === "relay") {
      const isActive = hw.ui ? hw.ui.active : Boolean(hw.value);
      const btnClass = isActive ? "btn-primary" : "btn-secondary";
      const btnText = isActive ? "Turn Off" : "Turn On"; // Could also come from server if desired

      return `
          <button class="btn btn-sm btn-block ${btnClass} js-action-toggle" 
                  data-id="${id}">
            ${btnText}
          </button>`;
    }

    // Default Footer (Sensors)
    const props = this.getRenderProps(hw);
    return `
        <div class="hardware-footer-meta">
          <span class="text-muted text-xs">Last Event</span>
          <span class="text-xs js-time-ago">${props.timeAgo}</span>
        </div>`;
  }

  // ============================================================
  // DOM MANIPULATION
  // ============================================================
  refreshSummary() {
    let activeCount = 0;
    this.state.forEach((hw) => {
      // Use the server-provided 'active' flag if available
      const isActive = hw.ui ? hw.ui.active : Boolean(hw.value);

      if (isActive && hw.type !== "relay") {
        activeCount++;
      }
    });
    this.updateSystemSummary(activeCount);
  }

  async initGrid() {
    try {
      const data = await Utils.fetchJson("/api/hardwares");
      if (!data.hardwares || !Array.isArray(data.hardwares)) return;

      const currentIds = new Set();

      data.hardwares.forEach((raw) => {
        // Ensure timestamp is a Date object
        if (raw.lastActivity && typeof raw.lastActivity === "string") {
          raw.lastActivity = new Date(raw.lastActivity);
        }
        currentIds.add(raw.hardware_id);
        this.renderCard(raw);
        this.state.set(raw.hardware_id, raw);
      });

      // Cleanup
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
    const props = this.getRenderProps(hw);
    const footerHtml = this.getCardFooter(hw);

    const card = document.createElement("div");
    card.id = `hw-card-${hw.hardware_id}`;
    card.className = `card hardware-card ${props.cardActiveClass}`;
    card.dataset.type = hw.type;

    card.innerHTML = `
      <div class="hardware-header">
        <div>
          <div class="hardware-name">${Utils.escape(hw.name)}</div>
          <div class="hardware-meta ${props.statusClass}">${props.statusText}</div>
        </div>
        <div class="hardware-icon">
          <i data-lucide="${props.iconName}"></i>
        </div>
      </div>
      <div class="hardware-footer-wrapper" id="hw-footer-${hw.hardware_id}">
        ${footerHtml}
      </div>
    `;

    this.elements.grid.appendChild(card);
  }

  updateCard(card, hw) {
    const props = this.getRenderProps(hw);

    // 1. Active State
    if (props.isActive) {
      card.classList.add("is-active");
    } else {
      card.classList.remove("is-active");
    }

    // 2. Status Text & Color
    const statusEl = card.querySelector(".hardware-meta");
    if (statusEl) {
      statusEl.textContent = props.statusText;
      statusEl.className = `hardware-meta ${props.statusClass}`;
    }

    // 3. Icon
    const iconEl = card.querySelector("[data-lucide]");
    if (iconEl && iconEl.getAttribute("data-lucide") !== props.iconName) {
      iconEl.setAttribute("data-lucide", props.iconName);
      this.refreshIcons(card);
    }

    // 4. Footer (Button Text or Time)
    const footerWrapper = card.querySelector(`#hw-footer-${hw.hardware_id}`);
    if (footerWrapper) {
      if (hw.type === "relay") {
        const btn = footerWrapper.querySelector("button");
        if (btn) {
          const btnText = props.isActive ? "Turn Off" : "Turn On";
          btn.textContent = btnText;
          btn.className = `btn btn-sm btn-block js-action-toggle ${
            props.isActive ? "btn-primary" : "btn-secondary"
          }`;
        }
      } else {
        const timeEl = footerWrapper.querySelector(".js-time-ago");

        if (timeEl) timeEl.textContent = props.timeAgo;
      }
    }
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

  // ============================================================
  // EVENT HANDLERS
  // ============================================================

  async handleGridClick(e) {
    const btn = e.target.closest(".js-action-toggle");
    if (!btn || btn.disabled) return;

    const id = parseInt(btn.dataset.id, 10);
    if (isNaN(id)) return;

    await this.toggleHardware(id, btn);
  }

  async toggleHardware(id, btn) {
    const originalText = btn.textContent;
    btn.textContent = "...";
    btn.disabled = true;

    try {
      const res = await fetch(`/api/hardwares/${id}/toggle`, { method: "POST" });
      if (!res.ok) throw new Error("Toggle failed");
    } catch (err) {
      console.error("Toggle Error:", err);
      alert("Failed to toggle device");
      btn.textContent = originalText;
    } finally {
      btn.disabled = false;
    }
  }

  handleHardwareUpdate(e) {
    const data = e.detail; // Payload: { hardware_id, value, ui: {...}, timestamp }
    if (!data || !data.hardware_id) return;
    const hw = this.state.get(data.hardware_id);

    if (hw) {
      hw.value = data.value;

      if (data.ui) {
        hw.ui = data.ui;
      }

      if (data.timestamp) {
        hw.lastActivity = new Date(data.timestamp);
      }

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

      // Render known people
      data.people_home.forEach((person) => {
        if (!person || person === "Unknown") return;
        const chip = document.createElement("span");
        chip.className = "chip active";
        chip.textContent = `👤 ${person}`;
        this.elements.widgetList.appendChild(chip);
      });

      // Render unknown device count
      const knownCount = data.people_home.length;
      if (data.count > knownCount) {
        const diff = data.count - knownCount;
        const chip = document.createElement("span");
        chip.className = "chip";
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
