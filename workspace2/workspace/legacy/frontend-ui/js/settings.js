/* ============================================================
   JARVIS — Settings Panel
   Full configuration UI with live preview
   ============================================================ */
'use strict';

const JARVIS_SETTINGS = (() => {

  /* ----- State ----- */
  let isOpen = false;

  /* DOM cache */
  let modal = null;

  /* ----- Initialization ----- */
  function init() {
    modal = document.getElementById('settingsModal');
  }

  /* ----- Open / Close ----- */
  function open() {
    if (!modal) return;
    isOpen = true;

    modal.innerHTML = buildSettingsHTML();
    modal.classList.add('open');

    bindSettingsEvents();

    // Focus the close button
    const closeBtn = modal.querySelector('#settingsCloseBtn');
    if (closeBtn) closeBtn.focus();
  }

  function close() {
    if (!modal) return;
    isOpen = false;
    modal.classList.remove('open');
  }

  function toggle() {
    isOpen ? close() : open();
  }

  /* ----- Build Settings HTML ----- */
  function buildSettingsHTML() {
    const apiConfig = JARVIS_API.getConfig();
    const voiceSettings = JARVIS_VOICE.settings;
    const quality = JARVIS_UTILS.storageGet('animationQuality', 'high');
    const fpsLimit = JARVIS_UTILS.storageGet('fpsLimit', 0);
    const showFps = JARVIS_UTILS.storageGet('showFps', false);
    const contextSize = JARVIS_UTILS.storageGet('contextSize', 20);
    const wakeWord = JARVIS_UTILS.storageGet('wakeWordEnabled', true);
    const continuous = JARVIS_UTILS.storageGet('continuousListening', false);
    const speakEnabled = JARVIS_UTILS.storageGet('speakEnabled', true);
    const bg3dEnabled = JARVIS_UTILS.storageGet('bg3dEnabled', true);
    const perfMode = JARVIS_UTILS.storageGet('perfMode', false);
    const devMode = JARVIS_UTILS.storageGet('devMode', false);
    const theme = JARVIS_UTILS.storageGet('theme', 'default');

    return `
      <div class="settings-container">
        <div class="settings-header">
          <h2>SETTINGS</h2>
          <button class="x" id="settingsCloseBtn" title="Close" aria-label="Close settings">✕</button>
        </div>

        <!-- AI Model -->
        <div class="settings-section">
          <h3>AI MODEL</h3>
          <div class="setting-row">
            <div class="setting-label">
              Backend URL
              <small>Your local JARVIS backend (uvicorn app.main:app)</small>
            </div>
            <div class="setting-control">
              <input type="text" id="settingBackendUrl" value="${JARVIS_UTILS.sanitizeHTML(JARVIS_UTILS.storageGet('apiConfig', {}).backendUrl || 'http://localhost:8000')}" placeholder="http://localhost:8000">
            </div>
          </div>
          <div class="setting-row">
            <div class="setting-label">
              Provider
              <small>Cloud only answers if the backend owner opted in server-side</small>
            </div>
            <div class="setting-control">
              <select id="settingProvider">
                <option value="local" selected>Local (default, private)</option>
                <option value="cloud">Cloud (opt-in on backend)</option>
              </select>
            </div>
          </div>
          <div class="setting-row">
            <div class="setting-label">Connection</div>
            <div class="setting-control">
              <button id="settingTestBackend" class="btn-secondary">Test Connection</button>
              <small id="backendStatus"></small>
            </div>
          </div>
        </div>


        <!-- Voice -->
        <div class="settings-section">
          <h3>VOICE</h3>
          <div class="setting-row">
            <div class="setting-label">Voice Profile</div>
            <div class="setting-control">
              <select id="settingVoiceProfile">
                ${JARVIS_VOICE.getProfileList().map(p =>
                  `<option value="${p.id}" ${p.active ? 'selected' : ''}>${p.name}</option>`
                ).join('')}
              </select>
            </div>
          </div>
          <div class="setting-row">
            <div class="setting-label">Voice</div>
            <div class="setting-control">
              <select id="settingVoice">
                <option value="">Auto-detect</option>
              </select>
            </div>
          </div>
          <div class="setting-row">
            <div class="setting-label">Rate</div>
            <div class="setting-control">
              <input type="range" id="settingVoiceRate" min="0.5" max="2" step="0.1" value="${voiceSettings.rate}">
              <small id="rateValue">${voiceSettings.rate}</small>
            </div>
          </div>
          <div class="setting-row">
            <div class="setting-label">Pitch</div>
            <div class="setting-control">
              <input type="range" id="settingVoicePitch" min="0" max="2" step="0.1" value="${voiceSettings.pitch}">
              <small id="pitchValue">${voiceSettings.pitch}</small>
            </div>
          </div>
          <div class="setting-row">
            <div class="setting-label">Volume</div>
            <div class="setting-control">
              <input type="range" id="settingVoiceVolume" min="0" max="1" step="0.1" value="${voiceSettings.volume}">
              <small id="volumeValue">${voiceSettings.volume}</small>
            </div>
          </div>
          <div class="setting-row">
            <div class="setting-label">Test Voice</div>
            <div class="setting-control">
              <button id="settingTestVoice" class="btn-secondary">Test</button>
            </div>
          </div>
        </div>

        <!-- Microphone -->
        <div class="settings-section">
          <h3>MICROPHONE</h3>
          <div class="setting-row">
            <div class="setting-label">
              Wake Word
              <small>Say "Jarvis" to activate</small>
            </div>
            <div class="setting-control">
              <div class="toggle ${wakeWord ? '' : 'off'}" id="settingWakeWord"></div>
            </div>
          </div>
          <div class="setting-row">
            <div class="setting-label">
              Always Listening
              <small>Listen continuously, auto-restart</small>
            </div>
            <div class="setting-control">
              <div class="toggle ${JARVIS_SPEECH.alwaysListening ? '' : 'off'}" id="settingAlwaysListen"></div>
            </div>
          </div>
          <div class="setting-row">
            <div class="setting-label">
              Continuous Listening
              <small>Keep listening after result</small>
            </div>
            <div class="setting-control">
              <div class="toggle ${continuous ? '' : 'off'}" id="settingContinuous"></div>
            </div>
          </div>
        </div>

        <!-- Animation -->
        <div class="settings-section">
          <h3>ANIMATION</h3>
          <div class="setting-row">
            <div class="setting-label">Quality</div>
            <div class="setting-control">
              <select id="settingQuality">
                <option value="high" ${quality === 'high' ? 'selected' : ''}>High</option>
                <option value="medium" ${quality === 'medium' ? 'selected' : ''}>Medium</option>
                <option value="low" ${quality === 'low' ? 'selected' : ''}>Low</option>
              </select>
            </div>
          </div>
          <div class="setting-row">
            <div class="setting-label">FPS Limit</div>
            <div class="setting-control">
              <select id="settingFps">
                <option value="0" ${fpsLimit === 0 ? 'selected' : ''}>Unlimited</option>
                <option value="60" ${fpsLimit === 60 ? 'selected' : ''}>60 FPS</option>
                <option value="30" ${fpsLimit === 30 ? 'selected' : ''}>30 FPS</option>
              </select>
            </div>
          </div>
          <div class="setting-row">
            <div class="setting-label">Show FPS Counter</div>
            <div class="setting-control">
              <div class="toggle ${showFps ? '' : 'off'}" id="settingShowFps"></div>
            </div>
          </div>
        </div>

        <!-- Memory -->
        <div class="settings-section">
          <h3>MEMORY</h3>
          <div class="setting-row">
            <div class="setting-label">
              Context Window
              <small>Messages sent to AI for context</small>
            </div>
            <div class="setting-control">
              <input type="number" id="settingContext" value="${contextSize}" min="1" max="50" style="width:60px;">
            </div>
          </div>
        </div>

        <!-- Web Search -->
        <div class="settings-section">
          <h3>WEB SEARCH</h3>
          <div class="setting-row">
            <div class="setting-label">
              Instant answers
              <small>Real, keyless, via the local backend (DuckDuckGo Instant Answer) -- answers direct factual questions, not general web search</small>
            </div>
          </div>
        </div>

        <!-- Privacy -->
        <div class="settings-section">
          <h3>PRIVACY & DATA</h3>
          <div class="setting-row">
            <div class="setting-label">
              Export All Data
              <small>Download chats, settings as JSON</small>
            </div>
            <div class="setting-control">
              <button class="setting-btn" id="settingExportAll">Export</button>
            </div>
          </div>
          <div class="setting-row">
            <div class="setting-label">
              Clear All Data
              <small>Delete all chats, settings, and cache</small>
            </div>
            <div class="setting-control">
              <button class="setting-btn danger" id="settingClearAll">Clear All</button>
            </div>
          </div>
        </div>

        <!-- Speech -->
        <div class="settings-section">
          <h3>SPEECH MODE</h3>
          <div class="setting-row">
            <div class="setting-label">
              Speak Responses
              <small>JARVIS speaks responses aloud</small>
            </div>
            <div class="setting-control">
              <div class="toggle ${speakEnabled ? '' : 'off'}" id="settingSpeakToggle"></div>
            </div>
          </div>
        </div>

        <!-- Visual -->
        <div class="settings-section">
          <h3>VISUAL</h3>
          <div class="setting-row">
            <div class="setting-label">
              3D Background
              <small>Orbital visualization on canvas</small>
            </div>
            <div class="setting-control">
              <div class="toggle ${bg3dEnabled ? '' : 'off'}" id="setting3DBgToggle"></div>
            </div>
          </div>
          <div class="setting-row">
            <div class="setting-label">Theme</div>
            <div class="setting-control">
              <select id="settingTheme">
                <option value="default" ${theme === 'default' ? 'selected' : ''}>Default (Dark Orange)</option>
                <option value="midnight" ${theme === 'midnight' ? 'selected' : ''}>Midnight Blue</option>
                <option value="cyber" ${theme === 'cyber' ? 'selected' : ''}>Cyber Neon Green</option>
                <option value="crimson" ${theme === 'crimson' ? 'selected' : ''}>Crimson Red</option>
                <option value="light" ${theme === 'light' ? 'selected' : ''}>Light Mode</option>
              </select>
            </div>
          </div>
          <div class="setting-row">
            <div class="setting-label">
              Performance Mode
              <small>Reduce visual effects for smoother performance</small>
            </div>
            <div class="setting-control">
              <div class="toggle ${perfMode ? '' : 'off'}" id="settingPerfToggle"></div>
            </div>
          </div>
        </div>

        <!-- Developer -->
        <div class="settings-section">
          <h3>DEVELOPER</h3>
          <div class="setting-row">
            <div class="setting-label">
              Developer Mode
              <small>Show raw API responses and debug info</small>
            </div>
            <div class="setting-control">
              <div class="toggle ${devMode ? '' : 'off'}" id="settingDevModeToggle"></div>
            </div>
          </div>
        </div>

        <div style="text-align:center;padding:16px 0;font-size:9px;letter-spacing:2px;color:rgba(255,210,130,.3);">
          J.A.R.V.I.S. // JUST A RATHER VERY INTELLIGENT SYSTEM
        </div>
      </div>
    `;
  }

  /* ----- Bind Settings Events ----- */
  function bindSettingsEvents() {
    if (!modal) return;

    // Close button
    const closeBtn = modal.querySelector('#settingsCloseBtn');
    if (closeBtn) closeBtn.addEventListener('click', close);

    // Escape to close
    const onKey = (e) => {
      if (e.key === 'Escape' && isOpen) {
        close();
        document.removeEventListener('keydown', onKey);
      }
    };
    document.addEventListener('keydown', onKey);

    // --- API Settings ---
    const bindInput = (id, callback) => {
      const el = modal.querySelector('#' + id);
      if (el) el.addEventListener('change', () => callback(el.value));
    };

    bindInput('settingBackendUrl', (v) => JARVIS_API.setConfig({ backendUrl: v }));

    const providerSelect = modal.querySelector('#settingProvider');
    if (providerSelect) {
      providerSelect.value = JARVIS_API.getConfig().provider || 'local';
      providerSelect.addEventListener('change', () => JARVIS_API.setConfig({ provider: providerSelect.value }));
    }

    const testBtn = modal.querySelector('#settingTestBackend');
    const statusEl = modal.querySelector('#backendStatus');
    if (testBtn && statusEl) {
      testBtn.addEventListener('click', async () => {
        statusEl.textContent = 'Checking…';
        JARVIS_API.setConfig({}); // invalidate cached reachability without changing values
        const ok = await JARVIS_API.checkBackend();
        statusEl.textContent = ok ? '✅ Connected' : '⚠ Not reachable';
      });
    }

    // --- Voice Settings ---
    // Populate voice select
    const voiceSelect = modal.querySelector('#settingVoice');
    if (voiceSelect) {
      const voices = JARVIS_VOICE.getVoices();
      const currentVoice = JARVIS_VOICE.settings.voiceName;
      voices.forEach(v => {
        const opt = document.createElement('option');
        opt.value = v.name;
        opt.textContent = `${v.name} (${v.lang})`;
        if (v.name === currentVoice) opt.selected = true;
        voiceSelect.appendChild(opt);
      });
      voiceSelect.addEventListener('change', () => JARVIS_VOICE.setVoice(voiceSelect.value));
    }

    // Voice sliders
    const bindSlider = (sliderId, valueId, param) => {
      const slider = modal.querySelector('#' + sliderId);
      const display = modal.querySelector('#' + valueId);
      if (slider) {
        slider.addEventListener('input', () => {
          if (display) display.textContent = slider.value;
          JARVIS_VOICE.setParams({ [param]: parseFloat(slider.value) });
        });
      }
    };
    bindSlider('settingVoiceRate', 'rateValue', 'rate');
    bindSlider('settingVoicePitch', 'pitchValue', 'pitch');
    bindSlider('settingVoiceVolume', 'volumeValue', 'volume');

    // --- Toggles ---
    const bindToggle = (toggleId, callback) => {
      const el = modal.querySelector('#' + toggleId);
      if (el) {
        el.addEventListener('click', () => {
          el.classList.toggle('off');
          callback(!el.classList.contains('off'));
        });
      }
    };

    bindToggle('settingWakeWord', (v) => JARVIS_SPEECH.setWakeWordEnabled(v));
    bindToggle('settingContinuous', (v) => JARVIS_SPEECH.setContinuousMode(v));
    bindToggle('settingShowFps', (v) => JARVIS_RENDERER.setShowFps(v));

    // Always listening toggle
    bindToggle('settingAlwaysListen', (v) => JARVIS_SPEECH.setAlwaysListening(v));

    // Voice profile selector
    const profileSelect = modal.querySelector('#settingVoiceProfile');
    if (profileSelect) {
      profileSelect.addEventListener('change', () => {
        JARVIS_VOICE.setProfile(profileSelect.value);
        // Update sliders to reflect new profile settings
        const s = JARVIS_VOICE.settings;
        const rateSlider = modal.querySelector('#settingVoiceRate');
        const pitchSlider = modal.querySelector('#settingVoicePitch');
        const volSlider = modal.querySelector('#settingVoiceVolume');
        const rateVal = modal.querySelector('#rateValue');
        const pitchVal = modal.querySelector('#pitchValue');
        const volVal = modal.querySelector('#volumeValue');
        if (rateSlider) { rateSlider.value = s.rate; if (rateVal) rateVal.textContent = s.rate; }
        if (pitchSlider) { pitchSlider.value = s.pitch; if (pitchVal) pitchVal.textContent = s.pitch; }
        if (volSlider) { volSlider.value = s.volume; if (volVal) volVal.textContent = s.volume; }
      });
    }

    // Test voice button
    const testVoiceBtn = modal.querySelector('#settingTestVoice');
    if (testVoiceBtn) {
      testVoiceBtn.addEventListener('click', () => {
        const profile = JARVIS_VOICE.activeProfile.replace('-', ' ');
        JARVIS_VOICE.speak(`Hello, I am JARVIS. Currently using the ${profile} voice profile.`, true);
      });
    }

    // --- Animation Quality ---
    bindInput('settingQuality', (v) => JARVIS_RENDERER.setQuality(v));

    // --- FPS Limit ---
    bindInput('settingFps', (v) => JARVIS_RENDERER.setFpsLimit(parseInt(v, 10)));

    // --- Context Size ---
    const contextInput = modal.querySelector('#settingContext');
    if (contextInput) {
      contextInput.addEventListener('change', () => {
        JARVIS_UTILS.storageSet('contextSize', parseInt(contextInput.value, 10) || 20);
      });
    }

    // --- Export All ---
    const exportBtn = modal.querySelector('#settingExportAll');
    if (exportBtn) {
      exportBtn.addEventListener('click', () => {
        JARVIS_HISTORY.exportAllChats();
      });
    }

    // --- Clear All ---
    const clearBtn = modal.querySelector('#settingClearAll');
    if (clearBtn) {
      clearBtn.addEventListener('click', async () => {
        const confirmed = await JARVIS_UTILS.confirm(
          'This will delete ALL conversations, settings, and cached data. This cannot be undone.',
          'Delete Everything', 'Cancel'
        );
        if (!confirmed) return;

        // Clear all localStorage items
        const keys = Object.keys(localStorage).filter(k => k.startsWith('jarvis_'));
        keys.forEach(k => localStorage.removeItem(k));

        JARVIS_UTILS.showToast('All data cleared. Reloading...', 'info');
        setTimeout(() => window.location.reload(), 1500);
      });
    }

    // --- Speak / Silent Toggle ---
    bindToggle('settingSpeakToggle', (v) => {
      JARVIS_UTILS.storageSet('speakEnabled', v);
      if (!v) {
        JARVIS_VOICE.stop();
        JARVIS_UTILS.showToast('Voice responses muted', 'info');
      } else {
        JARVIS_UTILS.showToast('Voice responses enabled', 'info');
      }
    });

    // --- 3D Background Toggle ---
    bindToggle('setting3DBgToggle', (v) => {
      JARVIS_UTILS.storageSet('bg3dEnabled', v);
      const canvas = document.getElementById('stage');
      if (canvas) canvas.style.display = v ? 'block' : 'none';
      const vignette = document.querySelector('.vignette');
      const scanlines = document.querySelector('.scanlines');
      if (vignette) vignette.style.display = v ? 'block' : 'none';
      if (scanlines) scanlines.style.display = v ? 'block' : 'none';
      JARVIS_UTILS.showToast(v ? '3D background enabled' : '3D background disabled', 'info');
    });

    // --- Theme Switcher ---
    const themeSelect = modal.querySelector('#settingTheme');
    if (themeSelect) {
      themeSelect.addEventListener('change', () => {
        const t = themeSelect.value;
        JARVIS_UTILS.storageSet('theme', t);
        document.body.className = document.body.className.replace(/theme-\w+/g, '');
        if (t !== 'default') document.body.classList.add('theme-' + t);
        JARVIS_UTILS.showToast('Theme: ' + themeSelect.options[themeSelect.selectedIndex].text, 'info');
      });
    }

    // --- Performance Mode Toggle ---
    bindToggle('settingPerfToggle', (v) => {
      JARVIS_UTILS.storageSet('perfMode', v);
      if (JARVIS_RENDERER) JARVIS_RENDERER.setQuality(v ? 'low' : JARVIS_UTILS.storageGet('animationQuality', 'high'));
      const scanlines = document.querySelector('.scanlines');
      if (scanlines) scanlines.style.display = v ? 'none' : 'block';
      JARVIS_UTILS.showToast(v ? 'Performance mode enabled' : 'Performance mode disabled', 'info');
    });

    // --- Developer Mode Toggle ---
    bindToggle('settingDevModeToggle', (v) => {
      JARVIS_UTILS.storageSet('devMode', v);
      const devIndicator = document.createElement('div');
      devIndicator.id = 'devModeIndicator';
      devIndicator.style.cssText = 'position:fixed;top:4px;right:4px;background:#ff0;color:#000;padding:2px 6px;font-size:9px;z-index:99999;border-radius:2px;pointer-events:none;';
      devIndicator.textContent = 'DEV MODE';
      if (v) {
        if (!document.getElementById('devModeIndicator')) document.body.appendChild(devIndicator);
        JARVIS_UTILS.showToast('Developer mode enabled', 'info');
      } else {
        const existing = document.getElementById('devModeIndicator');
        if (existing) existing.remove();
        JARVIS_UTILS.showToast('Developer mode disabled', 'info');
      }
    });
  }

  /* ----- Public API ----- */
  return {
    init,
    open,
    close,
    toggle,
    get isOpen() { return isOpen; },
  };

})();
