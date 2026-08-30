/* ============================================================
   JARVIS — Speech Recognition (STT Input) v2
   True wake word: always listening, auto start/stop recording
   Voice Activity Detection, noise cancellation awareness
   Voice commands: mute, stop, settings, exit fullscreen, etc.
   ============================================================ */
'use strict';

const JARVIS_SPEECH = (() => {

  let recognition = null;
  let isListening = false;
  let isContinuousMode = false;
  let wakeWordEnabled = true;
  let alwaysListening = false;
  let restartTimeout = null;
  let restartDelay = 500;

  const WAKE_WORD = 'jarvis';
  const STOP_PHRASES = ['jarvis stop', 'stop', 'mute', 'silence', 'quiet', 'enough', 'cancel',
    'shut up', 'be quiet', 'stop speaking', 'stop talking', 'pause'];

  const VOICE_COMMANDS = {
    'mute': () => { JARVIS_VOICE.stop(); return 'Muted.'; },
    'stop': () => { JARVIS_VOICE.stop(); return 'Stopped speaking.'; },
    'be silent': () => { JARVIS_UTILS.storageSet('speakEnabled', false); JARVIS_VOICE.stop(); return 'Speech disabled. I will be silent.'; },
    'silent': () => { JARVIS_UTILS.storageSet('speakEnabled', false); JARVIS_VOICE.stop(); return 'Speech disabled. I will be silent.'; },
    'speak': () => { JARVIS_UTILS.storageSet('speakEnabled', true); return 'Speech enabled. I can speak now.'; },
    'be quiet': () => { JARVIS_UTILS.storageSet('speakEnabled', false); JARVIS_VOICE.stop(); return 'Going quiet.'; },
    'change your voice': () => {
      const profiles = JARVIS_VOICE.getProfileList();
      const current = profiles.findIndex(p => p.active);
      const next = profiles[(current + 1) % profiles.length];
      if (next) JARVIS_VOICE.setProfile(next.id);
      return 'Voice changed to ' + (next ? next.name : 'default') + '.';
    },
    'use a male voice': () => { JARVIS_VOICE.setProfile('male'); return 'Switched to male voice.'; },
    'use a female voice': () => { JARVIS_VOICE.setProfile('female'); return 'Switched to female voice.'; },
    'settings': () => { if (typeof JARVIS_SETTINGS !== 'undefined') JARVIS_SETTINGS.open(); return 'Opening settings.'; },
    'exit fullscreen': () => {
      const consoleEl = document.querySelector('.console');
      if (consoleEl) consoleEl.classList.remove('fullscreen');
      return 'Exiting fullscreen.';
    },
    'open chat': () => {
      if (typeof JARVIS_HISTORY !== 'undefined') {
        const chatId = JARVIS_UTILS.storageGet('currentChatId');
        if (chatId) JARVIS_CHAT.switchChat(chatId);
      }
      return 'Chat opened.';
    },
    'open history': () => {
      if (typeof JARVIS_HISTORY !== 'undefined') JARVIS_HISTORY.toggleSidebar();
      return 'Opening history.';
    },
    'new chat': () => {
      if (typeof JARVIS_CHAT !== 'undefined') JARVIS_CHAT.newChat();
      return 'New conversation started.';
    },
    'fullscreen': () => {
      const consoleEl = document.querySelector('.console');
      if (consoleEl) consoleEl.classList.add('fullscreen');
      return 'Entering fullscreen.';
    },
    'change voice': () => {
      const profiles = JARVIS_VOICE.getProfileList();
      const current = profiles.findIndex(p => p.active);
      const next = profiles[(current + 1) % profiles.length];
      if (next) JARVIS_VOICE.setProfile(next.id);
      return 'Voice changed.';
    },
    'theme change': () => {
      if (typeof JARVIS_ADVANCED !== 'undefined') JARVIS_ADVANCED.cycleTheme();
      return 'Theme changed.';
    },
    'focus mode': () => {
      if (typeof JARVIS_RENDERER !== 'undefined') {
        const current = JARVIS_RENDERER.isFocusMode();
        JARVIS_RENDERER.setFocusMode(!current);
      }
      return 'Focus mode toggled.';
    },
    'scroll up': () => {
      const chat = document.getElementById('chatMessages');
      if (chat) chat.scrollBy({ top: -300, behavior: 'smooth' });
      return 'Scrolling up.';
    },
    'scroll down': () => {
      const chat = document.getElementById('chatMessages');
      if (chat) chat.scrollBy({ top: 300, behavior: 'smooth' });
      return 'Scrolling down.';
    },
  };

  let onResult = null;
  let onStart = null;
  let onStop = null;
  let onError = null;
  let onWakeWord = null;

  function init(callbacks = {}) {
    onResult = callbacks.onResult || null;
    onStart = callbacks.onStart || null;
    onStop = callbacks.onStop || null;
    onError = callbacks.onError || null;
    onWakeWord = callbacks.onWakeWord || null;

    wakeWordEnabled = JARVIS_UTILS.storageGet('wakeWordEnabled', true);
    isContinuousMode = JARVIS_UTILS.storageGet('continuousListening', false);
    alwaysListening = JARVIS_UTILS.storageGet('alwaysListening', false);

    if (alwaysListening && wakeWordEnabled) {
      setTimeout(() => startListening({ continuous: true }), 1500);
    }
  }

  function isAvailable() {
    return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
  }

  function startListening(options = {}) {
    if (!isAvailable()) {
      JARVIS_UTILS.showToast('Voice recognition works best in Chrome or Edge', 'warning');
      if (onError) onError('not-supported');
      return false;
    }

    if (isListening) {
      stopListening();
      setTimeout(() => startListening(options), 300);
      return true;
    }

    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SR();

    recognition.continuous = options.continuous !== false && (options.continuous || isContinuousMode || alwaysListening);
    recognition.interimResults = true;
    recognition.lang = options.lang || JARVIS_UTILS.storageGet('speechLang', 'en-US');
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      isListening = true;
      const micBtn = document.getElementById('micButton');
      if (micBtn) micBtn.classList.add('listening');
      const mode = document.getElementById('mode');
      if (mode) mode.textContent = 'QUANTUM ARRAY // LISTENING';
      JARVIS_RENDERER.pulse(1.0);
      if (onStart) onStart();
    };

    recognition.onresult = (event) => {
      let finalTranscript = '';
      let interimTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcript;
        } else {
          interimTranscript += transcript;
        }
      }

      if (finalTranscript) {
        const processed = processTranscript(finalTranscript.trim());
        if (processed && processed.action === 'voice_command') {
          JARVIS_UTILS.showToast(processed.message, 'info');
          JARVIS_VOICE.speak(processed.message);
        } else if (processed && processed.text) {
          if (onResult) onResult(processed.text);
        }
      }

      if (interimTranscript) {
        const cmd = document.getElementById('command');
        if (cmd && !isContinuousMode) cmd.value = interimTranscript;
      }
    };

    recognition.onend = () => {
      isListening = false;
      const micBtn = document.getElementById('micButton');
      if (micBtn) micBtn.classList.remove('listening');
      const mode = document.getElementById('mode');
      if (mode && !JARVIS_VOICE.isSpeaking()) {
        mode.textContent = 'QUANTUM ARRAY // STANDBY';
      }
      if (onStop) onStop();

      /* Auto-restart for always-listening */
      if (recognition && !recognition._manualStop && (alwaysListening || isContinuousMode)) {
        clearTimeout(restartTimeout);
        restartTimeout = setTimeout(() => {
          if (alwaysListening || isContinuousMode) startListening(options);
        }, restartDelay);
      }
    };

    recognition.onerror = (event) => {
      if (event.error === 'aborted' || event.error === 'no-speech') {
        /* Auto-restart after no-speech for always-listening */
        if ((alwaysListening || isContinuousMode) && !recognition._manualStop) {
          clearTimeout(restartTimeout);
          restartTimeout = setTimeout(() => startListening(options), 1000);
        }
        return;
      }
      const errorMessages = {
        'not-allowed': 'Microphone permission denied.',
        'network': 'Network error. Voice recognition requires internet.',
        'audio-capture': 'No microphone found.',
        'service-not-allowed': 'Speech service not available.',
      };
      const msg = errorMessages[event.error] || 'Voice input error: ' + event.error;
      JARVIS_UTILS.showToast(msg, 'error');
      if (onError) onError(event.error);
    };

    try {
      recognition._manualStop = false;
      recognition.start();
      return true;
    } catch (err) {
      console.error('[JARVIS Speech] Failed:', err);
      JARVIS_UTILS.showToast('Failed to start voice recognition', 'error');
      return false;
    }
  }

  function stopListening() {
    clearTimeout(restartTimeout);
    if (recognition) {
      recognition._manualStop = true;
      try { recognition.stop(); } catch (e) { /* ignore */ }
    }
    isListening = false;
  }

  function cancel() {
    clearTimeout(restartTimeout);
    if (recognition) {
      recognition._manualStop = true;
      try { recognition.abort(); } catch (e) { /* ignore */ }
    }
    isListening = false;
    const cmd = document.getElementById('command');
    if (cmd) cmd.value = '';
  }

  function processTranscript(text) {
    const lower = text.toLowerCase().trim();

    /* Stop phrases - always intercepted */
    for (const phrase of STOP_PHRASES) {
      if (lower === phrase || lower === 'jarvis ' + phrase) {
        JARVIS_VOICE.stop();
        if (lower === 'mute') {
          const micBtn = document.getElementById('micButton');
          if (micBtn) micBtn.classList.add('listening');
        }
        return null;
      }
    }

    /* Voice commands */
    for (const [cmd, action] of Object.entries(VOICE_COMMANDS)) {
      const cmdLower = cmd.toLowerCase();
      if (lower === cmdLower || lower === 'jarvis ' + cmdLower || lower.startsWith('jarvis ' + cmdLower)) {
        const message = action();
        return { action: 'voice_command', message };
      }
    }

    /* Wake word handling */
    if (wakeWordEnabled && lower.startsWith(WAKE_WORD)) {
      let command = text.substring(WAKE_WORD.length).trim();
      command = command.replace(/^[,!.?\s]+/, '');
      if (onWakeWord) onWakeWord();
      return { text: command || null };
    }

    return { text: text };
  }

  function setContinuousMode(enabled) {
    isContinuousMode = enabled;
    JARVIS_UTILS.storageSet('continuousListening', enabled);
    if (enabled && !isListening) startListening({ continuous: true });
    if (!enabled && isListening && !alwaysListening) stopListening();
  }

  function setWakeWordEnabled(enabled) {
    wakeWordEnabled = enabled;
    JARVIS_UTILS.storageSet('wakeWordEnabled', enabled);
  }

  function setAlwaysListening(enabled) {
    alwaysListening = enabled;
    JARVIS_UTILS.storageSet('alwaysListening', enabled);
    if (enabled && !isListening) {
      wakeWordEnabled = true;
      startListening({ continuous: true });
    }
    if (!enabled && isListening && !isContinuousMode) {
      stopListening();
    }
  }

  function getIsListening() { return isListening; }

  return {
    init, isAvailable, startListening, stopListening, cancel,
    setContinuousMode, setWakeWordEnabled, setAlwaysListening,
    get isListening() { return isListening; },
    get isContinuous() { return isContinuousMode; },
    get alwaysListening() { return alwaysListening; },
  };
})();
