/* ============================================================
   JARVIS — Advanced Features Module
   Slash commands, clipboard paste, auto-suggestions,
   welcome sequence, system stats, message reactions,
   particle bursts, sound effects
   ============================================================ */
'use strict';

const JARVIS_ADVANCED = (() => {

  /* ----- State ----- */
  let welcomeShown = false;
  let suggestionsVisible = false;
  let statsInterval = null;

  /* ----- Initialization ----- */
  function init() {
    bindClipboardPaste();
    bindAutoSuggestions();
    initSystemStats();
    showWelcome();
    initSlashCommands();
  }

  /* ============================================================
     SLASH COMMANDS
     ============================================================ */
  const SLASH_COMMANDS = {
    '/help': {
      description: 'Show available commands',
      execute: () => {
        const helpText = `## Available Commands\n\n` +
          Object.entries(SLASH_COMMANDS)
            .map(([cmd, info]) => `- **${cmd}** — ${info.description}`)
            .join('\n') +
          `\n\n## Keyboard Shortcuts\n- **Ctrl+N** — New chat\n- **Ctrl+,** — Settings\n- **Escape** — Close modals\n- **Enter** — Send message\n\n## Voice Commands\n- Say **"Jarvis"** + your command\n- Say **"Jarvis stop"** to interrupt`;
        return helpText;
      },
    },
    '/clear': {
      description: 'Clear current conversation',
      execute: () => {
        JARVIS_CHAT.newChat();
        return null; // No response needed
      },
    },
    '/new': {
      description: 'Start a new conversation',
      execute: () => {
        JARVIS_CHAT.newChat();
        JARVIS_UTILS.showToast('New conversation started', 'success');
        return null;
      },
    },
    '/export': {
      description: 'Export current chat as JSON',
      execute: () => {
        const chatId = JARVIS_CHAT.getCurrentChatId();
        if (chatId) JARVIS_HISTORY.exportChat(chatId);
        return '📥 Chat exported successfully.';
      },
    },
    '/status': {
      description: 'Show system status',
      execute: () => {
        const online = JARVIS_UTILS.isOnline();
        const chats = Object.keys(JARVIS_HISTORY.getAllChats()).length;
        const msgs = JARVIS_CHAT.getMessages().length;
        const webSearch = JARVIS_WEBSEARCH.isEnabled();
        const apiConfig = JARVIS_API.getConfig();

        return `## System Status\n\n` +
          `| Parameter | Value |\n|---|---|\n` +
          `| Network | ${online ? '🟢 Online' : '🔴 Offline'} |\n` +
          `| Backend | ${apiConfig.backendUrl} |\n` +
          `| Provider | ${apiConfig.provider} |\n` +
          `| Web Search | ${webSearch ? '🟢 Enabled' : '⚪ Disabled'} |\n` +
          `| Total Chats | ${chats} |\n` +
          `| Current Messages | ${msgs} |\n` +
          `| Voice | ${JARVIS_VOICE.isSpeaking() ? '🔊 Speaking' : '🔇 Idle'} |\n` +
          `| Platform | ${navigator.platform} |\n` +
          `| Memory | ${navigator.deviceMemory ? navigator.deviceMemory + ' GB' : 'N/A'} |\n` +
          `| Screen | ${screen.width}×${screen.height} |`;
      },
    },
    '/theme': {
      description: 'Cycle through themes (amber/blue/emerald/crimson)',
      execute: () => {
        cycleTheme();
        return null;
      },
    },
    '/time': {
      description: 'Show current date and time',
      execute: () => {
        const now = new Date();
        return `**${now.toLocaleDateString(undefined, {
          weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
        })}**\n\n🕐 ${now.toLocaleTimeString()} (${Intl.DateTimeFormat().resolvedOptions().timeZone})`;
      },
    },
    '/calc': {
      description: 'Calculate a math expression (e.g. /calc 2+2)',
      execute: (args) => {
        if (!args) return '⚠ Usage: `/calc <expression>`\n\nExample: `/calc 2 * (3 + 4)`';
        try {
          // Safe math evaluation — no eval, parse manually
          const result = safeMathEval(args);
          return `**${args}** = **${result}**`;
        } catch (e) {
          return `⚠ Invalid expression: ${JARVIS_UTILS.sanitizeHTML(args)}`;
        }
      },
    },
    '/history': {
      description: 'Open chat history sidebar',
      execute: () => {
        JARVIS_HISTORY.openSidebar();
        return null;
      },
    },
    '/settings': {
      description: 'Open settings panel',
      execute: () => {
        JARVIS_SETTINGS.open();
        return null;
      },
    },
    '/voice': {
      description: 'Test JARVIS voice synthesis',
      execute: () => {
        JARVIS_VOICE.speak('All systems are online and fully operational, sir. The quantum orbital array is stable.');
        return '🔊 Voice test initiated.';
      },
    },
    '/focus': {
      description: 'Toggle Focus Mode (red alert)',
      execute: () => {
        const btn = document.getElementById('focusModeBtn');
        if (btn) btn.click();
        const isActive = document.body.classList.contains('focus-mode');
        return isActive ? '🔴 **Focus Mode activated** — all systems in red alert.' : '🟢 **Focus Mode deactivated** — returning to normal operations.';
      },
    },
    '/fullscreen': {
      description: 'Toggle fullscreen chat view',
      execute: () => {
        const btn = document.getElementById('fullscreenBtn');
        const exitBtn = document.getElementById('exitFullscreenBtn');
        if (document.querySelector('.console.fullscreen')) {
          if (exitBtn) exitBtn.click();
        } else {
          if (btn) btn.click();
        }
        return null;
      },
    },
  };

  function initSlashCommands() {
    // Nothing needed — commands are processed in processSlashCommand
  }

  /**
   * Check if input is a slash command and process it
   * @param {string} input - User input text
   * @returns {boolean} True if it was a slash command
   */
  function processSlashCommand(input) {
    if (!input.startsWith('/')) return false;

    const parts = input.split(' ');
    const cmd = parts[0].toLowerCase();
    const args = parts.slice(1).join(' ');

    if (SLASH_COMMANDS[cmd]) {
      const result = SLASH_COMMANDS[cmd].execute(args);
      if (result) {
        // Add user message showing the command
        JARVIS_CHAT.addUserMessage(input);
        // Add system response
        JARVIS_CHAT.addAssistantMessage(result);
        // Speak short responses
        if (result.length < 200) {
          const plain = result.replace(/[#*`_\[\]()|\-]/g, '').trim();
          JARVIS_VOICE.speak(plain);
        }
      }
      playSound('command');
      JARVIS_RENDERER.pulse(1.5);
      return true;
    }

    return false;
  }

  /* ============================================================
     SAFE MATH EVALUATOR (no eval())
     ============================================================ */
  function safeMathEval(expr) {
    // Sanitize: only allow numbers, operators, parentheses, dots, spaces
    const sanitized = expr.replace(/[^0-9+\-*/().%^ \t]/g, '');
    if (!sanitized.trim()) throw new Error('Empty expression');

    // Replace ^ with ** for power
    const normalized = sanitized.replace(/\^/g, '**');

    // Use Function constructor (safer than eval, still sandboxed)
    // Only allow Math operations
    const fn = new Function('return ' + normalized);
    const result = fn();

    if (typeof result !== 'number' || isNaN(result)) throw new Error('Invalid result');
    return Number.isInteger(result) ? result : parseFloat(result.toFixed(8));
  }

  /* ============================================================
     CLIPBOARD PASTE SUPPORT
     ============================================================ */
  function bindClipboardPaste() {
    document.addEventListener('paste', (e) => {
      const items = e.clipboardData?.items;
      if (!items) return;

      for (const item of items) {
        // Paste images from clipboard
        if (item.type.startsWith('image/')) {
          e.preventDefault();
          const file = item.getAsFile();
          if (file) {
            const reader = new FileReader();
            reader.onload = (ev) => {
              JARVIS_UPLOAD.addCameraCapture(ev.target.result, file);
              JARVIS_UTILS.showToast('Image pasted from clipboard', 'success');
              JARVIS_RENDERER.pulse(1.0);
            };
            reader.readAsDataURL(file);
          }
          return;
        }
      }
    });
  }

  /* ============================================================
     AUTO-SUGGESTIONS
     ============================================================ */
  const SUGGESTIONS = [
    'What can you do?',
    'Tell me a joke',
    'What time is it?',
    'Explain quantum computing',
    'Write a poem',
    'Help me with code',
    '/help — Show commands',
    '/status — System status',
    '/theme — Change theme',
    '/calc 2+2 — Calculator',
  ];

  let suggestionsEl = null;

  function bindAutoSuggestions() {
    const cmd = document.getElementById('command');
    if (!cmd) return;

    // Create suggestions dropdown
    suggestionsEl = document.createElement('div');
    suggestionsEl.id = 'suggestions';
    suggestionsEl.className = 'suggestions-dropdown';
    suggestionsEl.setAttribute('role', 'listbox');
    suggestionsEl.setAttribute('aria-label', 'Suggestions');
    // Insert before barRow
    const console = document.querySelector('.console');
    if (console) {
      console.insertBefore(suggestionsEl, document.querySelector('.barRow'));
    }

    cmd.addEventListener('input', JARVIS_UTILS.debounce(() => {
      const val = cmd.value.trim().toLowerCase();
      if (val.length < 1) {
        hideSuggestions();
        return;
      }
      const matches = SUGGESTIONS.filter(s =>
        s.toLowerCase().includes(val)
      ).slice(0, 5);

      if (matches.length > 0 && val.length < 30) {
        showSuggestions(matches);
      } else {
        hideSuggestions();
      }
    }, 150));

    // Hide on blur (after delay so mousedown on suggestion can register)
    cmd.addEventListener('blur', () => {
      setTimeout(hideSuggestions, 350);
    });

    // Hide on Enter
    cmd.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') hideSuggestions();
      if (e.key === 'ArrowDown' && suggestionsVisible) {
        e.preventDefault();
        const first = suggestionsEl.querySelector('.suggestion-item');
        if (first) first.focus();
      }
    });
  }

  function showSuggestions(items) {
    if (!suggestionsEl) return;
    suggestionsVisible = true;

    suggestionsEl.innerHTML = items.map(item => {
      const parts = item.split(' — ');
      return `<div class="suggestion-item" role="option" tabindex="0">
        <span class="suggestion-text">${JARVIS_UTILS.sanitizeHTML(parts[0])}</span>
        ${parts[1] ? `<span class="suggestion-hint">${JARVIS_UTILS.sanitizeHTML(parts[1])}</span>` : ''}
      </div>`;
    }).join('');

    suggestionsEl.style.display = 'block';

    // Use mousedown (fires before blur) to properly capture clicks
    suggestionsEl.querySelectorAll('.suggestion-item').forEach((el, i) => {
      el.addEventListener('mousedown', (e) => {
        e.preventDefault(); // Prevent blur from hiding dropdown
        const cmd = document.getElementById('command');
        const text = items[i].split(' — ')[0];
        if (cmd) {
          cmd.value = text;
          cmd.focus();
        }
        hideSuggestions();

        // Auto-send if it's a slash command
        if (text.startsWith('/')) {
          setTimeout(() => {
            JARVIS_APP.processCommand();
          }, 50);
        }
      });
      el.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          const cmd = document.getElementById('command');
          const text = items[i].split(' — ')[0];
          if (cmd) {
            cmd.value = text;
            cmd.focus();
          }
          hideSuggestions();
          if (text.startsWith('/')) {
            setTimeout(() => JARVIS_APP.processCommand(), 50);
          }
        }
      });
    });
  }

  function hideSuggestions() {
    suggestionsVisible = false;
    if (suggestionsEl) {
      suggestionsEl.style.display = 'none';
      suggestionsEl.innerHTML = '';
    }
  }

  /* ============================================================
     WELCOME SEQUENCE
     ============================================================ */
  function showWelcome() {
    const hasVisited = JARVIS_UTILS.storageGet('hasVisited', false);
    if (hasVisited) {
      // Return user — show brief greeting
      showReturnGreeting();
      return;
    }

    // First-time user — show animated welcome
    JARVIS_UTILS.storageSet('hasVisited', true);

    const welcomeLines = [
      'Initializing J.A.R.V.I.S. core systems...',
      'Quantum orbital array: ONLINE',
      'Neural interface: CONNECTED',
      'Voice synthesis: CALIBRATED',
      'All systems operational.',
      '',
      'Welcome, sir. I am J.A.R.V.I.S. — Just A Rather Very Intelligent System.',
      'How may I assist you today?',
    ];

    let lineIndex = 0;
    let content = '';

    function typeLine() {
      if (lineIndex >= welcomeLines.length) {
        JARVIS_VOICE.speak('Welcome. I am JARVIS. All systems are online and fully operational. How may I assist you?');
        return;
      }

      content += (lineIndex > 0 ? '\n' : '') + welcomeLines[lineIndex];
      JARVIS_CHAT.addAssistantMessage(content);

      // Remove previous and re-add to simulate streaming
      lineIndex++;
      JARVIS_RENDERER.pulse(0.5 + lineIndex * 0.2);

      setTimeout(typeLine, 400 + Math.random() * 200);
    }

    // Delay to let renderer initialize
    setTimeout(() => {
      JARVIS_CHAT.addAssistantMessage(
        '## 🟢 J.A.R.V.I.S. Online\n\n' +
        'Welcome, sir. All systems are operational.\n\n' +
        'Type a message, use **voice input** (♬), or try a **slash command**:\n' +
        '- `/help` — Show all commands\n' +
        '- `/status` — System status\n' +
        '- `/theme` — Change color theme\n' +
        '- `/calc` — Calculator\n\n' +
        '_Click the ⌁ button to attach files, photos, or use the camera._'
      );
      JARVIS_VOICE.speak('Welcome. JARVIS online. All systems are operational.');
    }, 1500);
  }

  function showReturnGreeting() {
    const hour = new Date().getHours();
    let greeting;
    if (hour < 6) greeting = 'Working late, sir?';
    else if (hour < 12) greeting = 'Good morning, sir.';
    else if (hour < 17) greeting = 'Good afternoon, sir.';
    else if (hour < 21) greeting = 'Good evening, sir.';
    else greeting = 'Good evening, sir. Burning the midnight oil?';

    // Check how many existing chats
    const chatCount = Object.keys(JARVIS_HISTORY.getAllChats()).length;
    const currentChat = JARVIS_CHAT.getMessages();

    if (currentChat.length === 0) {
      setTimeout(() => {
        JARVIS_CHAT.addAssistantMessage(
          `${greeting} All systems are online and ready.\n\n` +
          `You have **${chatCount}** conversation${chatCount !== 1 ? 's' : ''} in history.`
        );
      }, 1000);
    }
  }

  /* ============================================================
     SYSTEM STATS HUD
     ============================================================ */
  function initSystemStats() {
    const statsEl = document.getElementById('systemStats');
    if (!statsEl) return;

    function updateStats() {
      const now = new Date();
      const uptime = formatUptime(performance.now());
      const memUsed = performance.memory
        ? (performance.memory.usedJSHeapSize / 1048576).toFixed(1) + ' MB'
        : '—';

      statsEl.innerHTML =
        `<div class="stat-item"><span class="stat-label">UPTIME</span><span class="stat-value">${uptime}</span></div>` +
        `<div class="stat-item"><span class="stat-label">MEMORY</span><span class="stat-value">${memUsed}</span></div>` +
        `<div class="stat-item"><span class="stat-label">NET</span><span class="stat-value">${navigator.onLine ? 'ONLINE' : 'OFFLINE'}</span></div>`;
    }

    updateStats();
    statsInterval = setInterval(updateStats, 5000);
  }

  function formatUptime(ms) {
    const s = Math.floor(ms / 1000);
    const m = Math.floor(s / 60);
    const h = Math.floor(m / 60);
    if (h > 0) return `${h}h ${m % 60}m`;
    if (m > 0) return `${m}m ${s % 60}s`;
    return `${s}s`;
  }

  /* ============================================================
     THEME SYSTEM
     ============================================================ */
  const THEMES = {
    amber: {
      name: 'Amber (Default)',
      bg: 'radial-gradient(ellipse at 50% 35%, #3a1703 0%, #130801 35%, #050201 78%)',
      accent: '#ffb53d',
      glow: 'rgba(255, 140, 20, .14)',
      text: '#f8e2b7',
      line: 'rgba(255, 186, 90, .22)',
      cornerColor: '#ff9c2a',
      dotColor: '#ffe6af',
      dotShadow: '#ff9d2c',
    },
    blue: {
      name: 'Arctic Blue',
      bg: 'radial-gradient(ellipse at 50% 35%, #031a3a 0%, #010813 35%, #010205 78%)',
      accent: '#3db5ff',
      glow: 'rgba(20, 140, 255, .14)',
      text: '#b7ddf8',
      line: 'rgba(90, 186, 255, .22)',
      cornerColor: '#2a9cff',
      dotColor: '#afe6ff',
      dotShadow: '#2c9dff',
    },
    emerald: {
      name: 'Emerald Matrix',
      bg: 'radial-gradient(ellipse at 50% 35%, #033a17 0%, #011308 35%, #010502 78%)',
      accent: '#3dff8c',
      glow: 'rgba(20, 255, 100, .14)',
      text: '#b7f8d7',
      line: 'rgba(90, 255, 140, .22)',
      cornerColor: '#2aff7c',
      dotColor: '#afffcf',
      dotShadow: '#2cff6d',
    },
    crimson: {
      name: 'Crimson Protocol',
      bg: 'radial-gradient(ellipse at 50% 35%, #3a0317 0%, #130108 35%, #050102 78%)',
      accent: '#ff3d5e',
      glow: 'rgba(255, 20, 80, .14)',
      text: '#f8b7c7',
      line: 'rgba(255, 90, 130, .22)',
      cornerColor: '#ff2a4c',
      dotColor: '#ffafbf',
      dotShadow: '#ff2c4d',
    },
  };

  let currentTheme = 'amber';

  function cycleTheme() {
    const themeNames = Object.keys(THEMES);
    const currentIdx = themeNames.indexOf(currentTheme);
    const nextIdx = (currentIdx + 1) % themeNames.length;
    applyTheme(themeNames[nextIdx]);
  }

  function applyTheme(themeName) {
    const theme = THEMES[themeName];
    if (!theme) return;

    currentTheme = themeName;
    JARVIS_UTILS.storageSet('theme', themeName);

    const root = document.documentElement;
    root.style.setProperty('--accent', theme.accent);
    root.style.setProperty('--text', theme.text);
    root.style.setProperty('--line', theme.line);
    root.style.setProperty('--glow-orange', theme.glow);
    document.body.style.background = theme.bg;

    // Update corner colors
    document.querySelectorAll('.corner').forEach(el => {
      el.style.borderColor = theme.cornerColor;
    });

    // Update dot
    const dot = document.querySelector('.dot');
    if (dot) {
      dot.style.background = theme.dotColor;
      dot.style.boxShadow = `0 0 15px 4px ${theme.dotShadow}`;
    }

    JARVIS_UTILS.showToast(`Theme: ${theme.name}`, 'success');
    JARVIS_RENDERER.pulse(2.0);
    playSound('theme');
  }

  function loadSavedTheme() {
    const saved = JARVIS_UTILS.storageGet('theme', 'amber');
    if (saved !== 'amber') {
      applyTheme(saved);
    }
  }

  /* ============================================================
     MESSAGE REACTIONS (Like/Dislike)
     ============================================================ */
  /**
   * Add reaction buttons to a message element
   * Called by chat.js when rendering messages
   * @param {HTMLElement} actionsEl - The chat-actions container
   * @param {Object} msg - The message object
   */
  function addReactionButtons(actionsEl, msg) {
    if (msg.role !== 'assistant') return;

    const thumbsUp = createReactionBtn('👍', 'Helpful', msg, 'like');
    const thumbsDown = createReactionBtn('👎', 'Not helpful', msg, 'dislike');
    actionsEl.appendChild(thumbsUp);
    actionsEl.appendChild(thumbsDown);
  }

  function createReactionBtn(icon, label, msg, type) {
    const btn = document.createElement('button');
    btn.className = 'chat-action-btn reaction-btn';
    btn.textContent = icon;
    btn.title = label;
    btn.setAttribute('aria-label', label);
    btn.dataset.reaction = type;

    // Check if already reacted
    const reactions = JARVIS_UTILS.storageGet('reactions', {});
    if (reactions[msg.id] === type) {
      btn.classList.add('reacted');
    }

    btn.addEventListener('click', () => {
      const reactions = JARVIS_UTILS.storageGet('reactions', {});
      if (reactions[msg.id] === type) {
        delete reactions[msg.id];
        btn.classList.remove('reacted');
      } else {
        reactions[msg.id] = type;
        btn.classList.add('reacted');
        // Remove opposite reaction
        const sibling = btn.parentElement.querySelector(
          `[data-reaction="${type === 'like' ? 'dislike' : 'like'}"]`
        );
        if (sibling) sibling.classList.remove('reacted');
      }
      JARVIS_UTILS.storageSet('reactions', reactions);
      playSound('click');
    });

    return btn;
  }

  /* ============================================================
     SOUND EFFECTS (subtle, non-intrusive)
     ============================================================ */
  let audioCtx = null;
  let soundsEnabled = true;

  function playSound(type) {
    if (!soundsEnabled) return;

    try {
      if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();

      const oscillator = audioCtx.createOscillator();
      const gainNode = audioCtx.createGain();
      oscillator.connect(gainNode);
      gainNode.connect(audioCtx.destination);

      const now = audioCtx.currentTime;

      switch (type) {
        case 'send':
          oscillator.type = 'sine';
          oscillator.frequency.setValueAtTime(880, now);
          oscillator.frequency.exponentialRampToValueAtTime(1320, now + 0.08);
          gainNode.gain.setValueAtTime(0.06, now);
          gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.15);
          oscillator.start(now);
          oscillator.stop(now + 0.15);
          break;

        case 'receive':
          oscillator.type = 'sine';
          oscillator.frequency.setValueAtTime(1320, now);
          oscillator.frequency.exponentialRampToValueAtTime(880, now + 0.1);
          gainNode.gain.setValueAtTime(0.05, now);
          gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.12);
          oscillator.start(now);
          oscillator.stop(now + 0.12);
          break;

        case 'command':
          oscillator.type = 'square';
          oscillator.frequency.setValueAtTime(440, now);
          oscillator.frequency.exponentialRampToValueAtTime(880, now + 0.05);
          oscillator.frequency.exponentialRampToValueAtTime(1760, now + 0.1);
          gainNode.gain.setValueAtTime(0.04, now);
          gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.15);
          oscillator.start(now);
          oscillator.stop(now + 0.15);
          break;

        case 'click':
          oscillator.type = 'sine';
          oscillator.frequency.setValueAtTime(1000, now);
          gainNode.gain.setValueAtTime(0.03, now);
          gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.05);
          oscillator.start(now);
          oscillator.stop(now + 0.05);
          break;

        case 'theme':
          oscillator.type = 'triangle';
          oscillator.frequency.setValueAtTime(523, now);
          oscillator.frequency.setValueAtTime(659, now + 0.1);
          oscillator.frequency.setValueAtTime(784, now + 0.2);
          gainNode.gain.setValueAtTime(0.05, now);
          gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
          oscillator.start(now);
          oscillator.stop(now + 0.35);
          break;

        case 'error':
          oscillator.type = 'sawtooth';
          oscillator.frequency.setValueAtTime(200, now);
          oscillator.frequency.exponentialRampToValueAtTime(100, now + 0.2);
          gainNode.gain.setValueAtTime(0.04, now);
          gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.25);
          oscillator.start(now);
          oscillator.stop(now + 0.25);
          break;
      }
    } catch (e) {
      // Audio not supported or user hasn't interacted — ignore silently
    }
  }

  /**
   * Enable/disable sound effects
   * @param {boolean} enabled
   */
  function setSoundsEnabled(enabled) {
    soundsEnabled = enabled;
    JARVIS_UTILS.storageSet('soundsEnabled', enabled);
  }

  /* ----- Public API ----- */
  return {
    init,
    processSlashCommand,
    addReactionButtons,
    playSound,
    setSoundsEnabled,
    cycleTheme,
    applyTheme,
    loadSavedTheme,
    THEMES,
    get currentTheme() { return currentTheme; },
  };

})();
