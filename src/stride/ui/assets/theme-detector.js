// OS Theme Detection for STRIDE Dashboard
// Detects user's OS color scheme preference and applies initial theme

(function () {
  "use strict";

  // Default to light (daytime) theme
  function getOSThemePreference() {
    // Detect OS theme preference using window.matchMedia
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  }

  // Apply theme to all relevant elements
  function applyTheme(isDark) {
    const theme = isDark ? "dark-theme" : "light-theme";

    // Update root element
    const root = document.querySelector("body").parentElement;
    if (root) {
      root.className = theme;
    }

    // Update page content
    const pageContent = document.getElementById("page-content");
    if (pageContent) {
      pageContent.className = "page-content " + theme;
    }

    // Update sidebar
    const sidebar = document.getElementById("sidebar");
    if (sidebar) {
      sidebar.className = "sidebar-nav " + theme;
    }

    // NOTE: Do NOT set themeToggle.checked here — that would desync
    // the DOM from Dash's React state and break the toggle callback.
    // Dash manages the toggle value via dbc.Switch(value=...).

    console.log("STRIDE Theme applied:", theme);
  }

  // Apply theme on page load
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      const prefersDark = getOSThemePreference();
      applyTheme(prefersDark);
    });
  } else {
    // DOM already loaded
    const prefersDark = getOSThemePreference();
    applyTheme(prefersDark);
  }

  // OS theme change listener removed - we default to light theme
  // Users can manually toggle theme using the theme toggle switch
})();
