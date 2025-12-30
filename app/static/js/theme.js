/**
 * ThemeController.js
 * Handles light/dark mode toggling with localStorage persistence
 * and OS preference detection.
 */
class ThemeController {
  constructor() {
    this.storageKey = "theme-preference";
    this.toggleBtn = document.getElementById("theme-toggle");
    this.root = document.documentElement;
    this.mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

    // Lucide Icons (Inline SVGs)
    this.icons = {
      sun: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>`,
      moon: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>`,
    };

    this.init();
  }

  init() {
    if (!this.toggleBtn) {
      console.warn("Theme toggle button (#theme-toggle) not found.");
      return;
    }

    // Event Listener for button
    this.toggleBtn.addEventListener("click", () => this.toggleTheme());

    // Event Listener for OS theme changes (only if no manual override)
    this.mediaQuery.addEventListener("change", (e) => {
      if (!localStorage.getItem(this.storageKey)) {
        this.applyTheme(e.matches ? "dark" : "light");
      }
    });

    // Initial Load
    this.loadTheme();
  }

  getPreferredTheme() {
    const stored = localStorage.getItem(this.storageKey);
    if (stored) return stored;
    return this.mediaQuery.matches ? "dark" : "light";
  }

  loadTheme() {
    const theme = this.getPreferredTheme();
    this.applyTheme(theme, false); // false = no animation on page load
  }

  applyTheme(theme, animate = true) {
    // 1. Set Attribute on HTML root
    this.root.setAttribute("data-theme", theme);

    // 2. Update Icon
    const isDark = theme === "dark";
    this.toggleBtn.innerHTML = isDark ? this.icons.sun : this.icons.moon;
    this.toggleBtn.setAttribute("aria-label", `Switch to ${isDark ? "light" : "dark"} mode`);

    // 3. Handle Animation Class
    if (animate) {
      this.toggleBtn.classList.add("theme-rotate");
      setTimeout(() => this.toggleBtn.classList.remove("theme-rotate"), 400);
    }
  }

  toggleTheme() {
    const current = this.root.getAttribute("data-theme");
    const newTheme = current === "dark" ? "light" : "dark";

    localStorage.setItem(this.storageKey, newTheme);
    this.applyTheme(newTheme);
  }
}

// Initialize on DOM ready
document.addEventListener("DOMContentLoaded", () => {
  window.themeController = new ThemeController();
});
