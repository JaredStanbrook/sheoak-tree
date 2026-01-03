/**
 * static/js/core.js
 * Shared utilities and Socket connection
 */
export const CONFIG = {
  socketPath: "/sheoak/socket.io",
  maxLogEntries: 50, // Reduced slightly for performance
  timeZone: "Australia/Perth",
  locale: "en-AU",
  // Theme Colors matching CSS Variables
  theme: {
    primary: "#10b981",
    danger: "#ef4444",
    warn: "#f59e0b",
    text: "#f8fafc",
    textMuted: "#94a3b8",
    gridLines: "rgba(255, 255, 255, 0.08)",
  },
  icons: {
    motionActive: '<i data-lucide="eye"></i>',
    motionInactive: '<i data-lucide="eye-off"></i>',
    doorActive: '<i data-lucide="door-open"></i>',
    doorInactive: '<i data-lucide="door-closed"></i>',
  },
};

export const Utils = {
  /**
   * Standard Date Format: 05 Dec, 19:13
   */
  formatDate(isoString) {
    if (!isoString || isoString === "None") return "No activity";
    const date = new Date(isoString);
    return date.toLocaleString(CONFIG.locale, {
      timeZone: CONFIG.timeZone,
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  },

  /**
   * Relative Time: "2 mins ago"
   */
  timeAgo(isoString) {
    if (!isoString || isoString === "None") return "Never";
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
    if (!str) return "";
    // Replaces single quotes with an escaped version
    return String(str).replace(/'/g, "\\'");
  },
};

// --- Shared Socket Instance ---
// We expose this so page-specific scripts can listen to events
export const socket = io({ path: CONFIG.socketPath });

socket.on("connect", () => {
  updateConnectionStatus(true);
});

socket.on("disconnect", () => {
  updateConnectionStatus(false);
});

function updateConnectionStatus(isConnected) {
  const text = document.getElementById("connection-text");
  const dot = document.querySelector(".status-dot");
  if (text) text.textContent = isConnected ? "Connected" : "Offline";
  if (dot) {
    dot.className = `status-dot ${isConnected ? "connected" : ""}`;
  }
}
const updateTime = () => {
  const el = document.getElementById("system-time");
  if (el) {
    el.textContent = new Date().toLocaleTimeString(CONFIG.locale, {
      timeZone: CONFIG.timeZone,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      //fractionalSecondDigits: 2, Adds the milliseconds (2 digits)
    });
  }
};
document.addEventListener("DOMContentLoaded", () => {
  updateTime();
  setInterval(updateTime, 1000);
  if (window.lucide) window.lucide.createIcons();
});
