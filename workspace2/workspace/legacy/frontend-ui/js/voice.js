/* ============================================================
   JARVIS — Voice Synthesis (TTS Output) v2
   Natural voice with multiple profiles: male, female, Tony Stark,
   calm, friendly, professional. Instant switching via "Change voice".
   Stop immediately on "Stop/Mute/Silence/Quiet/Enough/Cancel"
   ============================================================ */
'use strict';

const JARVIS_VOICE = (() => {

  let speaking = false;
  let voiceQueue = [];
  let currentUtterance = null;

  const PROFILES = {
    'tony-stark': { rate: 0.92, pitch: 0.68, volume: 0.95, voiceKeywords: ['male', 'david', 'james', 'daniel', 'british', 'jarvis'] },
    'male': { rate: 0.9, pitch: 0.85, volume: 0.9, voiceKeywords: ['male', 'guy', 'mark', 'daniel'] },
    'female': { rate: 0.95, pitch: 1.2, volume: 0.9, voiceKeywords: ['female', 'samantha', 'karen', 'susan', 'lisa'] },
    'calm': { rate: 0.78, pitch: 1.0, volume: 0.75, voiceKeywords: ['female', 'calm', 'serena'] },
    'friendly': { rate: 1.0, pitch: 1.05, volume: 0.9, voiceKeywords: ['female', 'friendly', 'natural'] },
    'professional': { rate: 0.95, pitch: 1.0, volume: 0.85, voiceKeywords: ['male', 'professional', 'david', 'mark'] },
  };

  let activeProfile = 'tony-stark';
  let settings = { ...PROFILES['tony-stark'] };
  let selectedVoice = null;
  let allVoices = [];

  let amplitudeAnimId = null;
  let lastSpeakTime = 0;

  /* Stop phrases that must immediately halt TTS */
  const STOP_PHRASES = ['stop', 'mute', 'silence', 'quiet', 'enough', 'cancel',
    'shut up', 'be quiet', 'stop speaking', 'stop talking', 'pause'];

  function init() {
    const savedProfile = JARVIS_UTILS.storageGet('voiceProfile', 'tony-stark');
    const savedSettings = JARVIS_UTILS.storageGet('voiceSettings', null);

    if (savedSettings) {
      settings = { ...settings, ...savedSettings };
    }
    activeProfile = savedProfile;
    if (PROFILES[activeProfile]) {
      settings = { ...settings, ...PROFILES[activeProfile] };
    }

    if ('speechSynthesis' in window) {
      window.speechSynthesis.onvoiceschanged = () => {
        allVoices = window.speechSynthesis.getVoices();
        selectBestVoice();
      };
      allVoices = window.speechSynthesis.getVoices();
      selectBestVoice();
    }
  }

  function selectBestVoice() {
    if (allVoices.length === 0) return;
    if (settings.voiceName) {
      const pref = allVoices.find(v => v.name === settings.voiceName);
      if (pref) { selectedVoice = pref; return; }
    }

    const langVoices = allVoices.filter(v =>
      v.lang.startsWith('en') || v.lang.startsWith('hi') || v.lang.startsWith('es') ||
      v.lang.startsWith('fr') || v.lang.startsWith('de') || v.lang.startsWith('ar') ||
      v.lang.startsWith('bn') || v.lang.startsWith('ta') || v.lang.startsWith('te') ||
      v.lang.startsWith('mr') || v.lang.startsWith('pa') || v.lang.startsWith('ur')
    );

    const englishVoices = langVoices.filter(v => v.lang.startsWith('en'));
    const keywords = settings.voiceKeywords || ['male'];

    for (const kw of keywords) {
      const match = englishVoices.find(v => v.name.toLowerCase().includes(kw));
      if (match) { selectedVoice = match; return; }
    }

    selectedVoice = englishVoices[0] || langVoices[0] || allVoices[0];
  }

  function getVoices() {
    return allVoices.length ? allVoices : window.speechSynthesis?.getVoices() || [];
  }

  function setVoice(voiceName) {
    settings.voiceName = voiceName;
    const match = getVoices().find(v => v.name === voiceName);
    if (match) selectedVoice = match;
    saveSettings();
  }

  function setProfile(profileName) {
    if (!PROFILES[profileName]) return false;
    activeProfile = profileName;
    settings = { ...settings, ...PROFILES[profileName] };
    JARVIS_UTILS.storageSet('voiceProfile', profileName);
    selectBestVoice();
    saveSettings();
    JARVIS_UTILS.showToast('Voice: ' + profileName.replace('-', ' '), 'info');
    return true;
  }

  function setParams(params) {
    if (params.rate !== undefined) settings.rate = params.rate;
    if (params.pitch !== undefined) settings.pitch = params.pitch;
    if (params.volume !== undefined) settings.volume = params.volume;
    if (params.voiceKeywords !== undefined) settings.voiceKeywords = params.voiceKeywords;
    saveSettings();
  }

  function saveSettings() {
    JARVIS_UTILS.storageSet('voiceSettings', settings);
    JARVIS_UTILS.storageSet('voiceProfile', activeProfile);
  }

  function getProfileList() {
    return Object.keys(PROFILES).map(k => ({
      id: k,
      name: k.replace('-', ' ').replace(/\b\w/g, c => c.toUpperCase()),
      active: k === activeProfile,
    }));
  }

  /* Speak with language detection */
  function speak(message, immediate = false) {
    return new Promise((resolve) => {
      if (!('speechSynthesis' in window)) { resolve(); return; }

      if (!JARVIS_UTILS.storageGet('speakEnabled', true)) { resolve(); return; }

      /* Check if message is a stop command */
      const cleanText = cleanupTextForSpeech(message);
      if (STOP_PHRASES.some(p => cleanText === p || cleanText.includes('jarvis ' + p))) {
        stop();
        resolve();
        return;
      }
      if (!cleanText) { resolve(); return; }

      if (immediate) stop();
      lastSpeakTime = Date.now();

      const utterance = new SpeechSynthesisUtterance(cleanText);
      utterance.rate = settings.rate;
      utterance.pitch = settings.pitch;
      utterance.volume = settings.volume;
      if (selectedVoice) utterance.voice = selectedVoice;

      /* Auto-detect language for voice matching */
      const detectedLang = detectLanguage(message);
      if (detectedLang && detectedLang !== 'en') {
        const langVoices = getVoices().filter(v => v.lang.startsWith(detectedLang));
        if (langVoices.length > 0) {
          utterance.voice = langVoices[0];
          utterance.lang = detectedLang;
        }
      }

      utterance.onstart = () => {
        speaking = true;
        currentUtterance = utterance;
        JARVIS_RENDERER.setVoiceIntensity(1.0);
        JARVIS_RENDERER.pulse(2.4);
        updateModeText('SPEAKING');
        startAmplitudeTracking();
        showStopButton();
      };

      utterance.onboundary = (e) => {
        if (e.name === 'word') JARVIS_RENDERER.pulse(1.3);
      };

      utterance.onend = () => {
        finishSpeaking();
        resolve();
      };

      utterance.onerror = (e) => {
        if (e.error !== 'interrupted' && e.error !== 'canceled') {
          console.warn('[JARVIS Voice] Error:', e.error);
        }
        finishSpeaking();
        resolve();
      };

      if (speaking && !immediate) {
        voiceQueue.push(utterance);
      } else {
        window.speechSynthesis.speak(utterance);
      }
    });
  }

  function cleanupTextForSpeech(text) {
    let cleaned = text.replace(/<[^>]*>/g, '');

    // Remove markdown bold/italic
    cleaned = cleaned.replace(/\*\*([^*]+)\*\*/g, '$1');
    cleaned = cleaned.replace(/\*([^*]+)\*/g, '$1');
    cleaned = cleaned.replace(/__([^_]+)__/g, '$1');
    cleaned = cleaned.replace(/_([^_]+)_/g, '$1');

    // Replace URLs with "a link" instead of reading each character
    cleaned = cleaned.replace(/https?:\/\/[^\s)]+/g, 'a link');

    // Remove code blocks entirely
    cleaned = cleaned.replace(/```[\s\S]*?```/g, '');
    cleaned = cleaned.replace(/`([^`]+)`/g, ' $1 ');

    // Remove common markdown formatting
    cleaned = cleaned.replace(/^#{1,6}\s+/gm, '');
    cleaned = cleaned.replace(/^[-*+]\s+/gm, '');
    cleaned = cleaned.replace(/^>\s+/gm, '');
    cleaned = cleaned.replace(/^(\d+\.)\s+/gm, '');
    cleaned = cleaned.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
    cleaned = cleaned.replace(/!\[([^\]]*)\]\([^)]+\)/g, '');
    cleaned = cleaned.replace(/~~([^~]+)~~/g, '$1');

    // Pronounce JARVIS as one word (remove dots/spaces)
    cleaned = cleaned.replace(/J\.\s*A\.\s*R\.\s*V\.\s*I\.\s*S\.?\s*/gi, 'Jarvis');
    cleaned = cleaned.replace(/J\s*A\s*R\s*V\s*I\s*S/gi, 'Jarvis');

    // Remove pipe tables
    cleaned = cleaned.replace(/^\|.*\|$/gm, '');
    cleaned = cleaned.replace(/^[-|:\s]+$/gm, '');

    // Remove horizontal rules
    cleaned = cleaned.replace(/^[-*_]{3,}\s*$/gm, '');

    // Collapse whitespace
    cleaned = cleaned.replace(/\s+/g, ' ').trim();

    return cleaned;
  }

  function finishSpeaking() {
    speaking = false;
    currentUtterance = null;
    JARVIS_RENDERER.setVoiceIntensity(0);
    updateModeText('STANDBY');
    stopAmplitudeTracking();
    hideStopButton();
    processQueue();
  }

  function processQueue() {
    if (voiceQueue.length > 0 && !speaking) {
      const next = voiceQueue.shift();
      window.speechSynthesis.speak(next);
    }
  }

  function stop() {
    voiceQueue = [];
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    speaking = false;
    currentUtterance = null;
    JARVIS_RENDERER.setVoiceIntensity(0);
    updateModeText('STANDBY');
    stopAmplitudeTracking();
    hideStopButton();
  }

  function isSpeaking() {
    return speaking && (Date.now() - lastSpeakTime < 300000);
  }

  /* Quick language detection for voice selection */
  function detectLanguage(text) {
    const langPatterns = {
      'hi': /[\u0900-\u097F]/,   // Hindi/Devanagari
      'bn': /[\u0980-\u09FF]/,   // Bengali
      'ta': /[\u0B80-\u0BFF]/,   // Tamil
      'te': /[\u0C00-\u0C7F]/,   // Telugu
      'mr': /[\u0900-\u097F]/,   // Marathi (Devanagari)
      'pa': /[\u0A00-\u0A7F]/,   // Punjabi/Gurmukhi
      'ar': /[\u0600-\u06FF]/,   // Arabic
      'ur': /[\u0600-\u06FF]/,   // Urdu (Arabic script)
      'es': /\b(h[oa]la|gracias|buenos|adi[oó]s|por favor|qu[eé])\b/i,
      'fr': /\b(bonjour|merci|salut|au revoir|s'il vous pla[iî]t)\b/i,
      'de': /\b(hallo|danke|tsch[üu]ss|guten tag|bitte)\b/i,
    };
    for (const [lang, pattern] of Object.entries(langPatterns)) {
      if (pattern.test(text)) return lang;
    }
    return 'en';
  }

  function updateModeText(status) {
    const mode = document.getElementById('mode');
    if (mode) mode.textContent = 'QUANTUM ARRAY // ' + status;
  }

  function startAmplitudeTracking() {
    if (amplitudeAnimId) return;
    function track() {
      if (!speaking) { JARVIS_RENDERER.setVoiceAmplitude(0); return; }
      const t = performance.now() / 1000;
      const amp = 0.4 + Math.abs(Math.sin(t * 6.5)) * 0.3 +
        Math.abs(Math.sin(t * 11.2)) * 0.15 + Math.abs(Math.sin(t * 2.8)) * 0.15;
      JARVIS_RENDERER.setVoiceAmplitude(Math.min(1, amp));
      amplitudeAnimId = requestAnimationFrame(track);
    }
    track();
  }

  function stopAmplitudeTracking() {
    if (amplitudeAnimId) { cancelAnimationFrame(amplitudeAnimId); amplitudeAnimId = null; }
    JARVIS_RENDERER.setVoiceAmplitude(0);
  }

  function showStopButton() {
    const btn = document.getElementById('stopSpeakingBtn');
    if (btn) btn.classList.add('visible');
  }

  function hideStopButton() {
    const btn = document.getElementById('stopSpeakingBtn');
    if (btn) btn.classList.remove('visible');
  }

  return {
    init, speak, stop, isSpeaking, getVoices, setVoice, setParams,
    setProfile, getProfileList, get activeProfile() { return activeProfile; },
    get settings() { return { ...settings }; },
    detectLanguage, cleanupTextForSpeech,
  };
})();
