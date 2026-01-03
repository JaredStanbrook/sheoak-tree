/**
 * ThemeController.js
 * Handles theme toggling and UI synchronization.
 * Note: Initial theme application is handled by the inline script in base.html
 * to prevent flashing.
 */
class ThemeController {
  constructor() {
    this.storageKey = "theme-preference";
    this.root = document.documentElement;
    this.toggleBtn = document.getElementById("theme-toggle");
    this.mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

    this.icons = {
      sun: `<i data-lucide="sun"></i>`,
      moon: `<i data-lucide="moon"></i>`,
    };

    // Bind context
    this.toggle = this.toggle.bind(this);
    this.handleSystemChange = this.handleSystemChange.bind(this);

    this.init();
  }

  init() {
    // 1. Hydrate UI: Sync button with the state set by the head script
    const currentTheme = this.root.getAttribute("data-theme") || "light";
    this.updateButton(currentTheme, false);

    // 2. Bind Click Event
    if (this.toggleBtn) {
      this.toggleBtn.addEventListener("click", this.toggle);
    }

    // 3. Bind System Change Event
    // Only auto-switch if the user hasn't manually set a preference
    this.mediaQuery.addEventListener("change", this.handleSystemChange);
  }

  /**
   * Applies theme to DOM and updates storage
   */
  setTheme(theme) {
    // Update DOM
    this.root.setAttribute("data-theme", theme);

    // Update Storage
    localStorage.setItem(this.storageKey, theme);

    // Update UI
    this.updateButton(theme, true);
  }

  /**
   * Updates the toggle button icon and aria-label
   */
  updateButton(theme, animate = true) {
    if (!this.toggleBtn) return;

    const isDark = theme === "dark";
    this.toggleBtn.innerHTML = isDark ? this.icons.sun : this.icons.moon;
    this.toggleBtn.setAttribute("aria-label", `Switch to ${isDark ? "light" : "dark"} mode`);

    if (window.lucide) {
      window.lucide.createIcons({
        root: this.toggleBtn,
        nameAttr: "data-lucide",
      });
    }
    if (animate) {
      this.toggleBtn.classList.remove("theme-rotate");
      void this.toggleBtn.offsetWidth; // Force reflow to restart animation
      this.toggleBtn.classList.add("theme-rotate");
    }
  }

  toggle() {
    const current = this.root.getAttribute("data-theme") === "dark" ? "dark" : "light";
    const newTheme = current === "dark" ? "light" : "dark";
    this.setTheme(newTheme);
  }

  handleSystemChange(e) {
    if (!localStorage.getItem(this.storageKey)) {
      this.setTheme(e.matches ? "dark" : "light");
    }
  }
}

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  window.themeController = new ThemeController();
});
