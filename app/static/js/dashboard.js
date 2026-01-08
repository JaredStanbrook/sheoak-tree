/**
 * static/js/dashboard.js
 */
import { Utils, CONFIG } from "./core.js";

class DashboardController {
  constructor() {
    this.elements = {
      grid: document.getElementById("hardwares-grid"),
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
    window.addEventListener("hardware_update", () => this.refreshGrid());
    window.addEventListener("presence_update", () => this.loadWhoIsHome());
  }

  async refreshGrid() {
    try {
      const data = await Utils.fetchJson("/api/hardwares");
      if (data.hardwares) this.renderSensorGrid(data.hardwares);
    } catch (e) {
      console.error(e);
    }
  }

  async toggleRelay(hardwareId) {
    try {
      // Optimistic UI update could go here (toggle button immediately)
      await fetch(`/api/hardwares/${hardwareId}/toggle`, { method: "POST" });
    } catch (e) {
      alert("Error communicating with device.");
    }
  }

  /**
   * Helper: Calculates view state (icons, text, classes) from data
   */
  getRenderProps(hardware) {
    const isActive = hardware.value === 1;

    // Normalize type
    let type = (hardware.type || "motion").toLowerCase();
    if (type.includes("contact")) type = "door";
    if (type.includes("pir")) type = "motion";

    let statusText = "Secure";
    let iconHtml = "";

    // Determine UI Props based on Type
    switch (type) {
      case "relay":
        statusText = isActive ? "Active" : "Off";
        iconHtml = "💡";
        break;
      case "door":
        statusText = isActive ? "Open" : "Secure";
        iconHtml = isActive ? CONFIG.icons.doorActive : CONFIG.icons.doorInactive;
        break;
      default: // Motion & others
        statusText = isActive ? "Detected" : "Secure";
        iconHtml = isActive ? CONFIG.icons.motionActive : CONFIG.icons.motionInactive;
        break;
    }

    return { type, isActive, statusText, iconHtml, hardware };
  }

  renderSensorGrid(hardwares) {
    if (!this.elements.grid) return;

    // 1. Update Summary
    const activeCount = hardwares.filter((s) => s.value === 1 && s.type !== "relay").length;
    this.updateSystemSummary(activeCount);

    // 2. Track processed IDs to handle removals
    const processedIds = new Set();

    hardwares.forEach((hardware) => {
      processedIds.add(hardware.id);
      const existingCard = document.getElementById(`card-${hardware.id}`);
      const props = this.getRenderProps(hardware);

      if (existingCard) {
        this.updateCard(existingCard, props);
      } else {
        this.createCard(props);
      }
    });

    // 3. Cleanup removed hardware
    // Convert HTMLCollection to Array to safely iterate while removing
    Array.from(this.elements.grid.children).forEach((child) => {
      const idStr = child.id.replace("card-", "");
      const id = parseInt(idStr, 10);
      if (!isNaN(id) && !processedIds.has(id)) {
        child.remove();
      }
    });
  }

  createCard(props) {
    const { hardware, type, isActive, statusText, iconHtml } = props;

    // Build Footer HTML
    let footerContent = "";
    if (type === "relay") {
      const btnLabel = isActive ? "Turn Off" : "Turn On";
      const btnClass = isActive ? "btn-primary" : "btn-secondary";
      footerContent = `
        <button class="btn btn-sm btn-block ${btnClass} js-relay-btn" 
          onclick="window.dashboard.toggleRelay(${hardware.id})">
          ${btnLabel}
        </button>`;
    } else {
      footerContent = `
        <div class="text-muted" style="display:flex; justify-content:space-between; font-size: 0.8rem;">
          <span>Last Event</span>
          <span class="js-time-ago">${Utils.timeAgo(hardware.last_activity)}</span>
        </div>`;
    }

    const html = `
      <div class="card ${isActive ? "is-active" : ""}" id="card-${hardware.id}">
        <div class="hardware-header">
          <div>
            <div class="hardware-name">${hardware.name}</div>
            <div class="hardware-meta" style="font-weight: ${isActive ? "600" : "400"}">
              ${statusText}
            </div>
          </div>
          <div class="hardware-icon">${iconHtml}</div>
        </div>
        <div class="hardware-footer" style="margin-top: auto; padding-top: 16px; border-top: 1px solid rgba(0,0,0,0.05);">
            ${footerContent}
        </div>
      </div>`;

    this.elements.grid.insertAdjacentHTML("beforeend", html);

    // OPTIMIZATION: Only render icons for this specific new card
    const newCard = this.elements.grid.lastElementChild;
    if (window.lucide) {
      window.lucide.createIcons({
        root: newCard,
        attrs: { class: "icon-svg" }, // Optional: Add default class to all icons
      });
    }
  }

  updateCard(card, props) {
    const { hardware, type, isActive, statusText, iconHtml } = props;

    // 1. Toggle Active Class
    if (isActive) card.classList.add("is-active");
    else card.classList.remove("is-active");

    // 2. Update Status Text
    const metaEl = card.querySelector(".hardware-meta");
    if (metaEl && metaEl.textContent !== statusText) {
      metaEl.textContent = statusText;
      metaEl.style.fontWeight = isActive ? "600" : "400";
    }

    // 3. Update Icon (Only if changed to avoid SVG flicker)
    const iconEl = card.querySelector(".hardware-icon");
    // Simple check: compare length or first few chars if strict equality is too heavy
    if (iconEl && iconEl.innerHTML !== iconHtml) {
      iconEl.innerHTML = iconHtml;
      if (window.lucide) {
        window.lucide.createIcons({ root: iconContainer });
      }
    }

    // 4. Update Footer
    if (type === "relay") {
      const btn = card.querySelector(".js-relay-btn");
      if (btn) {
        const newLabel = isActive ? "Turn Off" : "Turn On";
        const newClass = isActive ? "btn-primary" : "btn-secondary";
        const oldClass = isActive ? "btn-secondary" : "btn-primary";

        if (btn.textContent.trim() !== newLabel) btn.textContent = newLabel;
        if (btn.classList.contains(oldClass)) {
          btn.classList.replace(oldClass, newClass);
        }
      }
    } else {
      const timeEl = card.querySelector(".js-time-ago");
      if (timeEl) {
        // Always update time ago
        timeEl.textContent = Utils.timeAgo(hardware.last_activity);
      }
    }
  }

  updateSystemSummary(activeCount) {
    if (!this.elements.summary) return;
    // Don't rebuild if the count hasn't changed?
    // For simplicity, innerHTML is fine here as it's a small element.
    // ... (Keep existing summary logic) ...
    if (activeCount === 0) {
      this.elements.summary.innerHTML = `
          <div class="card" style="padding: 16px; display: flex; align-items: center; gap: 16px;">
              <div style="background: rgba(16, 185, 129, 0.1); color: #059669; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; border-radius: 50%;">✓</div>
              <div>
                  <div style="font-weight: 600;">System Secure</div>
                  <div class="text-muted" style="font-size: 0.9rem;">All hardwares are quiet</div>
              </div>
          </div>`;
    } else {
      this.elements.summary.innerHTML = `
          <div class="card" style="padding: 16px; display: flex; align-items: center; gap: 16px; border: 1px solid var(--color-danger);">
              <div style="background: var(--color-danger-bg); color: var(--color-danger); width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; border-radius: 50%;">!</div>
              <div>
                  <div style="font-weight: 600; color: var(--color-danger);">Activity Detected</div>
                  <div class="text-muted" style="font-size: 0.9rem;">${activeCount} hardware(s) currently active</div>
              </div>
          </div>`;
    }
  }

  async loadWhoIsHome() {
    // ... (Keep existing logic) ...
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
