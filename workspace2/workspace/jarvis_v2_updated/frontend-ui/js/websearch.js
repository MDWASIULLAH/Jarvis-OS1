/* ============================================================
   JARVIS — Web Search Module
   Toggle, state persistence, search execution
   ============================================================ */
'use strict';

const JARVIS_WEBSEARCH = (() => {

  /* ----- State ----- */
  let enabled = true;

  /* DOM cache */
  let toggleEl = null;

  /* ----- Initialization ----- */
  function init() {
    enabled = JARVIS_UTILS.storageGet('webSearchOn', true);
    toggleEl = document.getElementById('webToggle');

    updateToggleUI();
    bindEvents();
  }

  function bindEvents() {
    // Toggle click (on the toggle element itself)
    if (toggleEl) {
      toggleEl.addEventListener('click', (e) => {
        e.stopPropagation();
        toggle();
      });
    }

    // Web row click (the parent row)
    const webRow = document.getElementById('webRow');
    if (webRow) {
      webRow.addEventListener('click', (e) => {
        // Don't toggle if clicking the toggle itself (handled above)
        if (e.target === toggleEl || toggleEl?.contains(e.target)) return;
        toggle();
      });
    }
  }

  /* ----- Toggle ----- */
  /**
   * Toggle web search on/off
   */
  function toggle() {
    enabled = !enabled;
    JARVIS_UTILS.storageSet('webSearchOn', enabled);
    updateToggleUI();
    JARVIS_UTILS.showToast(
      `Web search ${enabled ? 'enabled' : 'disabled'}`,
      enabled ? 'success' : 'info'
    );
    JARVIS_RENDERER.pulse(0.8);
  }

  /**
   * Set web search state explicitly
   * @param {boolean} on
   */
  function setEnabled(on) {
    enabled = on;
    JARVIS_UTILS.storageSet('webSearchOn', enabled);
    updateToggleUI();
  }

  /* ----- UI ----- */
  function updateToggleUI() {
    if (toggleEl) {
      toggleEl.classList.toggle('off', !enabled);
    }
  }

  /**
   * Check if web search is enabled
   * @returns {boolean}
   */
  function isEnabled() {
    return enabled;
  }

  /**
   * Create a search indicator element for the chat
   * @param {string} query
   * @returns {HTMLElement}
   */
  function createSearchIndicator(query) {
    const indicator = document.createElement('div');
    indicator.className = 'web-search-indicator';
    indicator.innerHTML = `
      <div class="loading-spinner"></div>
      <span>Searching the web for "${JARVIS_UTILS.sanitizeHTML(query)}"...</span>
    `;
    return indicator;
  }

  /**
   * Create search sources display element
   * @param {Array} sources - [{title, url, snippet}]
   * @returns {HTMLElement}
   */
  function createSourcesDisplay(sources) {
    if (!sources || sources.length === 0) return null;

    const container = document.createElement('div');
    container.className = 'search-sources';

    let expanded = false;
    const titleEl = document.createElement('div');
    titleEl.className = 'search-sources-title';
    titleEl.textContent = `📎 ${sources.length} web sources ▸`;
    titleEl.addEventListener('click', () => {
      expanded = !expanded;
      titleEl.textContent = `📎 ${sources.length} web sources ${expanded ? '▾' : '▸'}`;
      itemsContainer.style.display = expanded ? 'block' : 'none';
    });
    container.appendChild(titleEl);

    const itemsContainer = document.createElement('div');
    itemsContainer.style.display = 'none';
    sources.forEach(source => {
      const item = document.createElement('div');
      item.className = 'search-source-item';
      item.innerHTML = `
        <a href="${JARVIS_UTILS.sanitizeHTML(source.url)}" target="_blank" rel="noopener noreferrer">
          ${JARVIS_UTILS.sanitizeHTML(source.title)}
        </a>
        ${source.snippet ? `<br><small style="color:rgba(255,210,130,.4)">${JARVIS_UTILS.sanitizeHTML(source.snippet.substring(0, 120))}</small>` : ''}
      `;
      itemsContainer.appendChild(item);
    });
    container.appendChild(itemsContainer);

    return container;
  }

  /* ----- Public API ----- */
  return {
    init,
    toggle,
    setEnabled,
    isEnabled,
    createSearchIndicator,
    createSourcesDisplay,
  };

})();
