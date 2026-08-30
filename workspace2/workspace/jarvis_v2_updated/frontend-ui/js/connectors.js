/* ============================================================
   JARVIS — Connectors & Tools Panel
   Manages external service connections (Gmail, GitHub, etc.)
   and toggles JARVIS capabilities (image gen, web browse, etc.)
   ============================================================ */
'use strict';

const JARVIS_CONNECTORS = (() => {

  let isOpen = false;
  let tab = 'connect'; // 'connect' | 'tools'
  let connectors = [];
  let tools = [];
  let modal = null;

  function init() {
    modal = document.getElementById('settingsModal');
  }

  /* ----- Tabs ----- */

  function open(t = 'connect') {
    if (!modal) modal = document.getElementById('settingsModal');
    if (!modal) return;
    tab = t;
    isOpen = true;
    render();
  }

  function close() {
    if (!modal) return;
    isOpen = false;
    modal.classList.remove('open');
  }

  function toggle() {
    isOpen ? close() : open();
  }

  /* ----- Fetch & Render ----- */

  async function render() {
    modal.classList.add('open');
    modal.innerHTML = buildShellHTML();
    bindShellEvents();

    if (tab === 'connect') {
      await loadConnectors();
    } else {
      await loadTools();
    }
  }

  async function switchTab(t) {
    tab = t;
    await render();
  }

  /* ----- Shell HTML ----- */

  function buildShellHTML() {
    const connActive = tab === 'connect' ? 'active' : '';
    const toolActive = tab === 'tools' ? 'active' : '';
    return `
      <div class="settings-container">
        <div class="settings-header">
          <h2>${tab === 'connect' ? 'CONNECTORS' : 'TOOLS'}</h2>
          <button class="x" id="connCloseBtn" title="Close" aria-label="Close panel">&times;</button>
        </div>
        <div class="conn-tabs">
          <button class="conn-tab ${connActive}" id="connTabConnect">Connectors</button>
          <button class="conn-tab ${toolActive}" id="connTabTools">Tool Access</button>
        </div>
        <div class="settings-body" id="connBody">
          <div class="loading-spinner">Loading...</div>
        </div>
      </div>`;
  }

  function bindShellEvents() {
    const closeBtn = document.getElementById('connCloseBtn');
    if (closeBtn) {
      closeBtn.addEventListener('click', close);
      closeBtn.focus();
    }
    const connTab = document.getElementById('connTabConnect');
    if (connTab) connTab.addEventListener('click', () => switchTab('connect'));
    const toolTab = document.getElementById('connTabTools');
    if (toolTab) toolTab.addEventListener('click', () => switchTab('tools'));
  }

  /* ----- Connectors Tab ----- */

  async function loadConnectors() {
    const body = document.getElementById('connBody');
    if (!body) return;

    const data = await JARVIS_API.getConnectors();
    connectors = data.connectors || [];

    const cats = {};
    for (const c of connectors) {
      if (!cats[c.category]) cats[c.category] = [];
      cats[c.category].push(c);
    }

    let html = '';
    for (const [cat, items] of Object.entries(cats)) {
      html += `<div class="conn-category"><h3>${cat}</h3>`;
      for (const c of items) {
        const dot = c.connected ? 'dot-green' : 'dot-red';
        const label = c.connected ? 'Connected' : (c.from_environment ? 'From env' : 'Not connected');
        const testInfo = c.last_test
          ? `<div class="conn-test-info ${c.last_test.ok ? 'test-ok' : 'test-fail'}">${c.last_test.ok ? 'Passed' : 'Failed'}: ${JARVIS_UTILS.htmlEscape(c.last_test.message)}</div>`
          : '';

        html += `
          <div class="conn-card">
            <div class="conn-card-header">
              <span class="conn-dot ${dot}"></span>
              <strong>${JARVIS_UTILS.htmlEscape(c.name)}</strong>
              <span class="conn-status">${label}</span>
              <button class="conn-expand-btn" data-conn="${JARVIS_UTILS.htmlEscape(c.id)}" aria-label="Toggle details">&blacktriangledown;</button>
            </div>
            <div class="conn-summary">${JARVIS_UTILS.htmlEscape(c.summary)}</div>
            ${testInfo}
            <div class="conn-details" id="conn-detail-${JARVIS_UTILS.htmlEscape(c.id)}" style="display:none">
              <form class="conn-form" data-conn="${JARVIS_UTILS.htmlEscape(c.id)}">
                ${buildFieldsHTML(c)}
                <div class="conn-actions">
                  <button type="submit" class="btn btn-primary btn-sm">Save</button>
                  <button type="button" class="btn btn-outline btn-sm conn-test-btn" data-conn="${JARVIS_UTILS.htmlEscape(c.id)}">Test</button>
                  ${c.connected ? `<button type="button" class="btn btn-danger btn-sm conn-delete-btn" data-conn="${JARVIS_UTILS.htmlEscape(c.id)}">Remove</button>` : ''}
                </div>
              </form>
              ${c.docs_url ? `<a href="${JARVIS_UTILS.htmlEscape(c.docs_url)}" target="_blank" rel="noopener" class="conn-docs-link">Setup instructions</a>` : ''}
              ${c.note ? `<div class="conn-note">${JARVIS_UTILS.htmlEscape(c.note)}</div>` : ''}
            </div>
          </div>`;
      }
      html += '</div>';
    }

    body.innerHTML = html;
    bindConnectorEvents();
  }

  function buildFieldsHTML(conn) {
    return (conn.fields || []).map(f => `
      <label class="conn-field">
        <span>${JARVIS_UTILS.htmlEscape(f.label)}${f.required ? ' *' : ''}</span>
        <input type="${f.secret ? 'password' : 'text'}"
               name="${JARVIS_UTILS.htmlEscape(f.key)}"
               placeholder="${JARVIS_UTILS.htmlEscape(f.placeholder || '')}"
               autocomplete="off"
               value="${JARVIS_UTILS.htmlEscape((conn.values && conn.values[f.key]) || '')}" />
        ${f.help ? `<small>${JARVIS_UTILS.htmlEscape(f.help)}</small>` : ''}
      </label>
    `).join('');
  }

  function bindConnectorEvents() {
    document.querySelectorAll('.conn-expand-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const id = btn.dataset.conn;
        const detail = document.getElementById(`conn-detail-${id}`);
        if (detail) {
          const visible = detail.style.display !== 'none';
          detail.style.display = visible ? 'none' : 'block';
          btn.innerHTML = visible ? '&#9650;' : '&#9660;';
        }
      });
    });

    document.querySelectorAll('.conn-form').forEach(form => {
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const connId = form.dataset.conn;
        const values = {};
        form.querySelectorAll('input').forEach(inp => {
          const val = inp.value.trim();
          if (val) values[inp.name] = val;
        });
        const btn = form.querySelector('button[type="submit"]');
        btn.disabled = true;
        btn.textContent = 'Saving...';
        const result = await JARVIS_API.saveConnector(connId, values);
        btn.disabled = false;
        btn.textContent = 'Save';
        if (result.error) {
          JARVIS_UTILS.showToast(`Save failed: ${result.error}`, 'error');
        } else {
          JARVIS_UTILS.showToast(`${result.message || 'Saved'}`, 'success');
          await loadConnectors();
        }
      });
    });

    document.querySelectorAll('.conn-test-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const connId = btn.dataset.conn;
        const form = document.querySelector(`.conn-form[data-conn="${connId}"]`);
        const values = {};
        if (form) {
          form.querySelectorAll('input').forEach(inp => {
            const val = inp.value.trim();
            if (val) values[inp.name] = val;
          });
        }
        btn.disabled = true;
        btn.textContent = 'Testing...';
        const result = await JARVIS_API.testConnector(connId, values);
        btn.disabled = false;
        btn.textContent = 'Test';
        if (result.ok) {
          JARVIS_UTILS.showToast(`Connected! ${result.message}`, 'success');
        } else {
          JARVIS_UTILS.showToast(`Failed: ${result.message}`, 'error');
        }
        await loadConnectors();
      });
    });

    document.querySelectorAll('.conn-delete-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const connId = btn.dataset.conn;
        if (!confirm(`Remove saved credentials for this connector?`)) return;
        btn.disabled = true;
        const result = await JARVIS_API.deleteConnector(connId);
        btn.disabled = false;
        if (result.error) {
          JARVIS_UTILS.showToast(`Remove failed: ${result.error}`, 'error');
        } else {
          JARVIS_UTILS.showToast('Credentials removed', 'success');
          await loadConnectors();
        }
      });
    });
  }

  /* ----- Tools Tab ----- */

  async function loadTools() {
    const body = document.getElementById('connBody');
    if (!body) return;

    const data = await JARVIS_API.getTools();
    tools = data.tools || [];

    const cats = {};
    for (const t of tools) {
      if (!cats[t.category]) cats[t.category] = [];
      cats[t.category].push(t);
    }

    let html = '';
    for (const [cat, items] of Object.entries(cats)) {
      html += `<div class="conn-category"><h3>${cat}</h3>`;
      for (const t of items) {
        html += `
          <div class="tool-row">
            <div class="tool-info">
              <strong>${JARVIS_UTILS.htmlEscape(t.name)}</strong>
              <span class="tool-desc">${JARVIS_UTILS.htmlEscape(t.description)}</span>
            </div>
            <label class="switch">
              <input type="checkbox" ${t.enabled ? 'checked' : ''} data-tool="${JARVIS_UTILS.htmlEscape(t.id)}" class="tool-toggle" />
              <span class="slider"></span>
            </label>
          </div>`;
      }
      html += '</div>';
    }

    body.innerHTML = html;
    bindToolEvents();
  }

  function bindToolEvents() {
    document.querySelectorAll('.tool-toggle').forEach(cb => {
      cb.addEventListener('change', async () => {
        const toolId = cb.dataset.tool;
        const enabled = cb.checked;
        const result = await JARVIS_API.toggleTool(toolId, enabled);
        if (result.error) {
          JARVIS_UTILS.showToast(`Failed: ${result.error}`, 'error');
          cb.checked = !enabled;
        } else {
          JARVIS_UTILS.showToast(`${result.name} ${enabled ? 'enabled' : 'disabled'}`, 'info');
        }
      });
    });
  }

  /* ----- Public ----- */

  return {
    init,
    open,
    close,
    toggle,
  };

})();
