/* ============================================================
   JARVIS — Main Application Orchestrator
   Boots all modules, manages global state, event delegation
   ============================================================ */
'use strict';

const JARVIS_APP = (() => {

  /* ----- Global State ----- */
  let initialized = false;

  /* ----- Boot Sequence ----- */
  function boot() {
    if (initialized) return;
    initialized = true;

    console.log('%c[J.A.R.V.I.S.] System boot sequence initiated', 'color:#ffb53d;font-weight:bold');

    // Install global error handlers FIRST
    installErrorHandlers();

    // Initialize modules in dependency order
    try {
      // 1. Renderer — starts the 3D animation loop immediately
      JARVIS_RENDERER.init();
      console.log('[J.A.R.V.I.S.] Renderer online');

      // 2. Voice — speech synthesis setup
      JARVIS_VOICE.init();
      console.log('[J.A.R.V.I.S.] Voice systems online');

      // 3. API — load saved config
      JARVIS_API.init();
      console.log('[J.A.R.V.I.S.] API client online');

      // 4. History — load saved chats (must be before Chat)
      JARVIS_HISTORY.init();
      console.log('[J.A.R.V.I.S.] History loaded');

      // 5. Chat — conversation system
      JARVIS_CHAT.init();
      console.log('[J.A.R.V.I.S.] Chat system online');

      // 6. Upload — file handling
      JARVIS_UPLOAD.init();
      console.log('[J.A.R.V.I.S.] Upload systems online');

      // 7. Camera — init with upload callback
      JARVIS_CAMERA.init((dataUrl, file) => {
        JARVIS_UPLOAD.addCameraCapture(dataUrl, file);
      });
      console.log('[J.A.R.V.I.S.] Camera systems online');

      // 8. Web Search — toggle state
      JARVIS_WEBSEARCH.init();
      console.log('[J.A.R.V.I.S.] Web search online');

      // 9. Speech Recognition — mic input
      JARVIS_SPEECH.init({
        onResult: (transcript) => {
          const cmd = document.getElementById('command');
          if (cmd) cmd.value = transcript;
          processCommand();
        },
        onStart: () => {
          closeSheet();
        },
        onError: (err) => {
          // Errors are handled inside the speech module
        },
      });
      console.log('[J.A.R.V.I.S.] Speech recognition online');

      // 10. Settings — panel
      JARVIS_SETTINGS.init();
      console.log('[J.A.R.V.I.S.] Settings online');

      // 11. Advanced features — slash commands, themes, sounds, etc.
      JARVIS_ADVANCED.init();
      JARVIS_ADVANCED.loadSavedTheme();
      console.log('[J.A.R.V.I.S.] Advanced systems online');

      // 12. Image Viewer
      JARVIS_IMAGEVIEWER.init();
      console.log('[J.A.R.V.I.S.] Image viewer online');

    } catch (err) {
      console.error('[J.A.R.V.I.S.] Boot error:', err);
      JARVIS_UTILS.showToast('System initialization error. Some features may be unavailable.', 'error');
    }

    // Bind all UI event handlers
    bindUIEvents();

    // Start clock
    startClock();

    // Enable drag & drop on console area
    const consoleEl = document.querySelector('.console');
    if (consoleEl) {
      JARVIS_UPLOAD.enableDragDrop(consoleEl);
    }

    // Network status monitoring
    window.addEventListener('online', () => {
      JARVIS_UTILS.showToast('Connection restored', 'success');
    });
    window.addEventListener('offline', () => {
      JARVIS_UTILS.showToast('No internet connection', 'warning');
    });

    console.log('%c[J.A.R.V.I.S.] All systems operational', 'color:#4dff88;font-weight:bold');
  }

  /* ----- Global Error Handlers ----- */
  function installErrorHandlers() {
    // Catch unhandled JS errors
    window.onerror = (message, source, lineno, colno, error) => {
      // Filter out third-party/extension errors
      if (source && !source.includes('jarvis') && !source.includes('src/js')) return;
      console.error('[J.A.R.V.I.S. Error]', message, source, lineno);
      return true; // Prevent default error handling (don't crash)
    };

    // Catch unhandled promise rejections
    window.addEventListener('unhandledrejection', (event) => {
      console.error('[J.A.R.V.I.S. Unhandled Promise]', event.reason);
      event.preventDefault(); // Prevent default error handling
    });
  }

  /* ----- UI Event Binding ----- */
  function bindUIEvents() {

    /* --- Visual Viewport (Mobile Keyboard Handling) --- */
    if (window.visualViewport) {
      const consoleEl = document.querySelector('.console');
      window.visualViewport.addEventListener('resize', () => {
        if (!consoleEl || consoleEl.classList.contains('fullscreen')) return;
        
        // Calculate offset if keyboard opens
        // Default bottom is usually 18px (desktop) or 10px (mobile)
        const viewportHeight = window.visualViewport.height;
        const windowHeight = window.innerHeight;
        
        if (viewportHeight < windowHeight - 50) {
          // Keyboard is likely open
          const offset = windowHeight - viewportHeight;
          consoleEl.style.bottom = `${offset + 10}px`;
        } else {
          // Keyboard is closed
          consoleEl.style.bottom = ''; // Revert to CSS default
        }
      });
      
      // Also handle scrolling which sometimes triggers viewport changes
      window.visualViewport.addEventListener('scroll', () => {
        if (!consoleEl || consoleEl.classList.contains('fullscreen')) return;
        const offset = window.innerHeight - window.visualViewport.height - window.visualViewport.offsetTop;
        if (offset > 50) {
          consoleEl.style.bottom = `${offset + 10}px`;
        }
      });
    }

    /* --- Stop Speaking Button --- */
    const stopSpeakingBtn = document.getElementById('stopSpeakingBtn');
    if (stopSpeakingBtn) {
      stopSpeakingBtn.addEventListener('click', () => {
        JARVIS_VOICE.stop();
        stopSpeakingBtn.classList.remove('visible');
        JARVIS_UTILS.showToast('Speech stopped', 'info');
      });
    }

    // Monitor speaking state to show/hide stop button
    setInterval(() => {
      if (stopSpeakingBtn) {
        stopSpeakingBtn.classList.toggle('visible', JARVIS_VOICE.isSpeaking());
      }
    }, 300);

    /* --- Scroll Buttons + Fullscreen --- */
    const chatMessages = document.getElementById('chatMessages');
    const scrollTopBtn = document.getElementById('scrollTopBtn');
    const scrollBottomBtn = document.getElementById('scrollBottomBtn');
    const fullscreenBtn = document.getElementById('fullscreenBtn');
    const consoleEl = document.querySelector('.console');

    if (chatMessages && scrollTopBtn && scrollBottomBtn) {
      scrollTopBtn.addEventListener('click', () => {
        chatMessages.scrollTo({ top: 0, behavior: 'smooth' });
      });
      scrollBottomBtn.addEventListener('click', () => {
        chatMessages.scrollTo({ top: chatMessages.scrollHeight, behavior: 'smooth' });
      });

      // Show/hide scroll buttons based on scroll position
      chatMessages.addEventListener('scroll', () => {
        const { scrollTop, scrollHeight, clientHeight } = chatMessages;
        const hasScroll = scrollHeight > clientHeight + 30;
        const atTop = scrollTop < 30;
        const atBottom = scrollTop + clientHeight >= scrollHeight - 30;

        scrollTopBtn.classList.toggle('visible', hasScroll && !atTop);
        scrollBottomBtn.classList.toggle('visible', hasScroll && !atBottom);
      });
    }

    // Fullscreen toggle
    const exitFsBtn = document.getElementById('exitFullscreenBtn');
    function toggleFullscreen(enable) {
      if (!consoleEl) return;
      const isFs = enable !== undefined ? enable : !consoleEl.classList.contains('fullscreen');
      consoleEl.classList.toggle('fullscreen', isFs);
      if (exitFsBtn) exitFsBtn.style.display = isFs ? 'grid' : 'none';
      if (fullscreenBtn) fullscreenBtn.style.display = isFs ? 'none' : 'grid';
      if (isFs) {
        JARVIS_UTILS.showToast('Fullscreen mode — press Escape or ✕ to exit', 'info');
      }
    }
    if (fullscreenBtn) {
      fullscreenBtn.addEventListener('click', () => toggleFullscreen(true));
    }
    if (exitFsBtn) {
      exitFsBtn.addEventListener('click', () => toggleFullscreen(false));
    }

    // Focus Mode toggle
    const focusModeBtn = document.getElementById('focusModeBtn');
    if (focusModeBtn) {
      focusModeBtn.addEventListener('click', () => {
        const isActive = document.body.classList.toggle('focus-mode');
        focusModeBtn.classList.toggle('active', isActive);
        JARVIS_RENDERER.setFocusMode(isActive);
        JARVIS_UTILS.showToast(
          isActive ? 'Focus Mode activated - all systems red' : 'Focus Mode deactivated - normal mode',
          isActive ? 'warning' : 'success'
        );
      });
    }

    /* --- Image Click → Image Viewer --- */
    if (chatMessages) {
      chatMessages.addEventListener('click', (e) => {
        const img = e.target.closest('img');
        if (!img || !img.src) return;
        if (img.closest('.img-viewer-overlay')) return;
        const allImages = Array.from(
          chatMessages.querySelectorAll('img:not(.img-viewer-overlay img)')
        ).filter(el => el.src).map(el => el.src);
        const idx = allImages.indexOf(img.src);
        JARVIS_IMAGEVIEWER.open(img.src, { images: allImages, index: idx >= 0 ? idx : 0 });
      });
    }

    /* --- Sheet (Add-to-Chat) Behavior --- */
    // All sheet close scenarios as specified:
    // 1. Close button
    const sheetClose = document.getElementById('sheetClose');
    if (sheetClose) sheetClose.addEventListener('click', closeSheet);

    // 2. Top Menu button toggles sidebar
    const topMenuBtn = document.getElementById('menuButtonTop');
    if (topMenuBtn) {
      topMenuBtn.addEventListener('click', () => {
        JARVIS_HISTORY.toggleSidebar();
      });
    }

    // 3. Attach button opens sheet
    const attachButton = document.getElementById('attachButton');
    if (attachButton) {
      attachButton.addEventListener('click', () => {
        toggleSheet();
      });
    }

    // 4. Camera button in bar — direct camera open
    const cameraButton = document.getElementById('cameraButton');
    if (cameraButton) {
      cameraButton.addEventListener('click', () => {
        closeSheet();
        JARVIS_CAMERA.open();
      });
    }

    /* --- Sheet Tile Actions --- */
    // Camera tile
    const btnCamera = document.getElementById('btnCamera');
    if (btnCamera) {
      btnCamera.addEventListener('click', () => {
        closeSheet();
        JARVIS_CAMERA.open();
      });
    }

    // Photos tile
    const btnPhotos = document.getElementById('btnPhotos');
    if (btnPhotos) {
      btnPhotos.addEventListener('click', () => {
        closeSheet();
        JARVIS_UPLOAD.openPhotoPicker();
      });
    }

    // Files tile
    const btnFiles = document.getElementById('btnFiles');
    if (btnFiles) {
      btnFiles.addEventListener('click', () => {
        closeSheet();
        JARVIS_UPLOAD.openFilePicker();
      });
    }

    // Tool Access tile
    const btnToolAccess = document.getElementById('btnToolAccess');
    if (btnToolAccess) {
      btnToolAccess.addEventListener('click', () => {
        closeSheet();
        JARVIS_CONNECTORS.open('tools');
      });
    }

    // Connectors tile
    const btnConnectors = document.getElementById('btnConnectors');
    if (btnConnectors) {
      btnConnectors.addEventListener('click', () => {
        closeSheet();
        JARVIS_CONNECTORS.open('connect');
      });
    }

    /* --- Send / Enter --- */
    const sendButton = document.getElementById('sendButton');
    if (sendButton) {
      sendButton.addEventListener('click', () => {
        closeSheet();
        processCommand();
      });
    }

    const commandInput = document.getElementById('command');
    if (commandInput) {
      // Auto-resize logic for textarea
      commandInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
      });

      commandInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          closeSheet();
          processCommand();
        }
      });

      // Focus trap: Tab from command input to send button
      commandInput.addEventListener('focus', () => {
        closeSheet();
      });
    }

    /* --- Microphone --- */
    const micButton = document.getElementById('micButton');
    if (micButton) {
      micButton.addEventListener('click', () => {
        closeSheet();
        if (JARVIS_SPEECH.isListening) {
          JARVIS_SPEECH.stopListening();
        } else {
          JARVIS_SPEECH.startListening();
        }
      });
    }

    /* --- Settings Button (brand/logo click) --- */
    const brand = document.querySelector('.brand');
    if (brand) {
      brand.addEventListener('click', () => {
        JARVIS_SETTINGS.toggle();
      });
    }

    /* --- Click Outside Sheet to Close --- */
    document.addEventListener('pointerdown', (e) => {
      const sheet = document.getElementById('sheet');
      if (!sheet || !sheet.classList.contains('open')) return;

      // Don't close if clicking inside the sheet
      if (sheet.contains(e.target)) return;

      // Don't close if clicking buttons that open the sheet
      const ignoreIds = ['attachButton', 'cameraButton', 'btnHistory', 'sheet'];
      for (const id of ignoreIds) {
        const el = document.getElementById(id);
        if (el && el.contains(e.target)) return;
      }

      closeSheet();
    });

    /* --- Keyboard Navigation --- */
    document.addEventListener('keydown', (e) => {
      // Don't capture shortcuts when typing in input fields
      const isTyping = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName);

      // Escape closes open modals/sheets in priority order
      if (e.key === 'Escape') {
        // Fullscreen exit first
        const consoleFull = document.querySelector('.console.fullscreen');
        if (consoleFull) {
          toggleFullscreen(false);
          return;
        }
        const shortcutsOverlay = document.getElementById('shortcutsOverlay');
        if (shortcutsOverlay?.classList.contains('open')) {
          shortcutsOverlay.classList.remove('open');
        } else if (JARVIS_SETTINGS.isOpen) {
          JARVIS_SETTINGS.close();
        } else if (JARVIS_HISTORY.isOpen) {
          JARVIS_HISTORY.closeSidebar();
        } else if (isSheetOpen()) {
          closeSheet();
        }
      }

      // Ctrl/Cmd + N for new chat
      if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
        e.preventDefault();
        JARVIS_CHAT.newChat();
        JARVIS_HISTORY.closeSidebar();
        JARVIS_UTILS.showToast('New conversation started', 'info');
      }

      // Ctrl/Cmd + , for settings
      if ((e.ctrlKey || e.metaKey) && e.key === ',') {
        e.preventDefault();
        JARVIS_SETTINGS.toggle();
      }

      // ? key for keyboard shortcuts overlay (only when not typing)
      if (e.key === '?' && !isTyping) {
        const shortcutsOverlay = document.getElementById('shortcutsOverlay');
        if (shortcutsOverlay) {
          shortcutsOverlay.classList.toggle('open');
        }
      }
    });

    // Shortcuts overlay close button
    const shortcutsClose = document.getElementById('shortcutsClose');
    if (shortcutsClose) {
      shortcutsClose.addEventListener('click', () => {
        const overlay = document.getElementById('shortcutsOverlay');
        if (overlay) overlay.classList.remove('open');
      });
    }
  }

  /* ----- Sheet Management ----- */
  function isSheetOpen() {
    const sheet = document.getElementById('sheet');
    return sheet && sheet.classList.contains('open');
  }

  function openSheet() {
    const sheet = document.getElementById('sheet');
    if (sheet) sheet.classList.add('open');
  }

  function closeSheet() {
    const sheet = document.getElementById('sheet');
    if (sheet) sheet.classList.remove('open');
  }

  function toggleSheet() {
    isSheetOpen() ? closeSheet() : openSheet();
  }

  /* ----- Command Processing ----- */
  function processCommand() {
    const commandInput = document.getElementById('command');
    if (!commandInput) return;

    const text = commandInput.value.trim();
    const attachments = JARVIS_UPLOAD.getAttachments();

    if (!text && attachments.length === 0) return;

    // Clear input and reset height
    commandInput.value = '';
    commandInput.style.height = 'auto';

    // Clear attachments
    JARVIS_UPLOAD.clearAll();

    // Close sheet if open
    closeSheet();

    // Play send sound
    JARVIS_ADVANCED.playSound('send');

    // Check for slash commands first
    if (text.startsWith('/') && JARVIS_ADVANCED.processSlashCommand(text)) {
      return; // Slash command handled
    }

    // Process through chat system
    JARVIS_CHAT.processUserInput(text, attachments);
  }

  /* ----- Clock ----- */
  function startClock() {
    const clockEl = document.getElementById('clock');
    if (!clockEl) return;

    function updateClock() {
      clockEl.textContent = new Date().toLocaleTimeString() + ' // SYSTEM ONLINE';
    }
    updateClock();
    setInterval(updateClock, 1000);
  }

  /* ----- Public API ----- */
  return {
    boot,
    closeSheet,
    processCommand,
  };

})();

/* ----- Auto-boot on DOM ready ----- */
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', JARVIS_APP.boot);
} else {
  JARVIS_APP.boot();
}
