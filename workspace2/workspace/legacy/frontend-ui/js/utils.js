/* ============================================================
   JARVIS — Utility Module
   Safe DOM access, sanitization, helpers, toast system
   ============================================================ */
'use strict';

const JARVIS_UTILS = (() => {

  /* ----- Safe DOM Access ----- */
  /**
   * Safe getElementById — returns element or null with console warning
   * @param {string} id - Element ID
   * @returns {HTMLElement|null}
   */
  function $(id) {
    const el = document.getElementById(id);
    if (!el) {
      console.warn(`[JARVIS] Element #${id} not found in DOM`);
    }
    return el;
  }

  /**
   * Query selector shorthand
   * @param {string} selector - CSS selector
   * @param {HTMLElement} [parent=document] - Parent element
   * @returns {HTMLElement|null}
   */
  function qs(selector, parent = document) {
    return parent.querySelector(selector);
  }

  /**
   * Query selector all shorthand
   * @param {string} selector - CSS selector
   * @param {HTMLElement} [parent=document] - Parent element
   * @returns {NodeList}
   */
  function qsa(selector, parent = document) {
    return parent.querySelectorAll(selector);
  }

  /* ----- HTML Sanitization (XSS Protection) ----- */
  const SANITIZE_MAP = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#x27;',
    '/': '&#x2F;',
  };

  /**
   * Escapes HTML special characters to prevent XSS
   * @param {string} str - Raw string
   * @returns {string} Sanitized string
   */
  function sanitizeHTML(str) {
    if (typeof str !== 'string') return '';
    return str.replace(/[&<>"'/]/g, ch => SANITIZE_MAP[ch]);
  }

  /* ----- Formatting Helpers ----- */
  /**
   * Format bytes into human-readable file size
   * @param {number} bytes
   * @returns {string}
   */
  function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0) + ' ' + units[i];
  }

  /**
   * Format timestamp into relative or absolute time
   * @param {Date|number|string} date
   * @returns {string}
   */
  function formatTimestamp(date) {
    const d = new Date(date);
    const now = Date.now();
    const diff = Math.floor((now - d.getTime()) / 1000);
    if (diff < 10) return 'just now';
    if (diff < 60) return diff + 's ago';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    return d.toLocaleDateString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  }

  /* ----- Throttle & Debounce ----- */
  /**
   * Debounce — delays execution until pause in calls
   * @param {Function} fn
   * @param {number} ms
   * @returns {Function}
   */
  function debounce(fn, ms) {
    let timer;
    return function (...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), ms);
    };
  }

  /**
   * Throttle — limits execution rate
   * @param {Function} fn
   * @param {number} ms
   * @returns {Function}
   */
  function throttle(fn, ms) {
    let last = 0;
    return function (...args) {
      const now = Date.now();
      if (now - last >= ms) {
        last = now;
        fn.apply(this, args);
      }
    };
  }

  /* ----- ID Generator ----- */
  let idCounter = 0;
  /**
   * Generate a unique ID string
   * @param {string} [prefix='j']
   * @returns {string}
   */
  function generateId(prefix = 'j') {
    return prefix + '_' + Date.now().toString(36) + '_' + (idCounter++).toString(36);
  }

  /* ----- Network Status ----- */
  /**
   * Check if the browser is online
   * @returns {boolean}
   */
  function isOnline() {
    return navigator.onLine !== false;
  }

  /* ----- Toast Notification System ----- */
  const TOAST_DURATION = 4000;

  /**
   * Show a toast notification
   * @param {string} message - Toast message
   * @param {'info'|'success'|'warning'|'error'} [type='info'] - Toast type
   * @param {number} [duration=4000] - Auto-dismiss duration in ms
   */
  function showToast(message, type = 'info', duration = TOAST_DURATION) {
    const container = $('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'polite');
    container.appendChild(toast);

    // Auto-remove
    const removeTimer = setTimeout(() => {
      toast.classList.add('removing');
      setTimeout(() => toast.remove(), 300);
    }, duration);

    // Click to dismiss
    toast.addEventListener('click', () => {
      clearTimeout(removeTimer);
      toast.classList.add('removing');
      setTimeout(() => toast.remove(), 300);
    });
  }

  /* ----- Error Boundary Wrapper ----- */
  /**
   * Wraps a function in try-catch with fallback
   * @param {Function} fn - Function to execute
   * @param {*} [fallback=null] - Fallback return value on error
   * @param {string} [context=''] - Context label for error logging
   * @returns {*}
   */
  function tryCatch(fn, fallback = null, context = '') {
    try {
      return fn();
    } catch (err) {
      console.error(`[JARVIS${context ? ' | ' + context : ''}]`, err);
      return fallback;
    }
  }

  /**
   * Async error boundary wrapper
   * @param {Function} fn - Async function to execute
   * @param {*} [fallback=null]
   * @param {string} [context='']
   * @returns {Promise<*>}
   */
  async function tryCatchAsync(fn, fallback = null, context = '') {
    try {
      return await fn();
    } catch (err) {
      console.error(`[JARVIS${context ? ' | ' + context : ''}]`, err);
      return fallback;
    }
  }

  /* ----- Confirmation Dialog ----- */
  /**
   * Show a confirmation dialog and return a promise
   * @param {string} message
   * @param {string} [confirmText='Delete']
   * @param {string} [cancelText='Cancel']
   * @returns {Promise<boolean>}
   */
  function confirm(message, confirmText = 'Delete', cancelText = 'Cancel') {
    return new Promise(resolve => {
      const dialog = document.createElement('div');
      dialog.className = 'confirm-dialog';
      dialog.setAttribute('role', 'dialog');
      dialog.setAttribute('aria-modal', 'true');
      dialog.innerHTML = `
        <div class="confirm-box">
          <p>${sanitizeHTML(message)}</p>
          <div class="confirm-actions">
            <button class="confirm-no" aria-label="${sanitizeHTML(cancelText)}">${sanitizeHTML(cancelText)}</button>
            <button class="confirm-yes" aria-label="${sanitizeHTML(confirmText)}">${sanitizeHTML(confirmText)}</button>
          </div>
        </div>
      `;
      document.body.appendChild(dialog);

      // Focus the cancel button by default for safety
      const noBtn = dialog.querySelector('.confirm-no');
      const yesBtn = dialog.querySelector('.confirm-yes');
      noBtn.focus();

      const cleanup = (result) => {
        dialog.remove();
        resolve(result);
      };

      noBtn.onclick = () => cleanup(false);
      yesBtn.onclick = () => cleanup(true);

      // Click backdrop to cancel
      dialog.addEventListener('click', (e) => {
        if (e.target === dialog) cleanup(false);
      });

      // Escape to cancel
      const onKey = (e) => {
        if (e.key === 'Escape') {
          document.removeEventListener('keydown', onKey);
          cleanup(false);
        }
      };
      document.addEventListener('keydown', onKey);
    });
  }

  /* ----- File Validation ----- */
  const SUPPORTED_TYPES = {
    image: ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml', 'image/bmp'],
    document: [
      'application/pdf',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/vnd.ms-excel',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/vnd.ms-powerpoint',
      'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    ],
    text: ['text/plain', 'text/csv', 'application/json'],
    archive: ['application/zip', 'application/x-zip-compressed'],
    audio: ['audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/webm', 'audio/mp4'],
    video: ['video/mp4', 'video/webm', 'video/ogg'],
  };

  const SUPPORTED_EXTENSIONS = [
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.txt', '.csv', '.json',
    '.zip',
    '.mp3', '.wav', '.ogg',
    '.mp4', '.webm',
  ];

  const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25MB default

  /**
   * Validate a file for upload
   * @param {File} file
   * @param {number} [maxSize=MAX_FILE_SIZE]
   * @returns {{ valid: boolean, error?: string }}
   */
  function validateFile(file, maxSize = MAX_FILE_SIZE) {
    if (!file) return { valid: false, error: 'No file provided' };

    // Check file size
    if (file.size > maxSize) {
      return {
        valid: false,
        error: `File too large: ${formatFileSize(file.size)} (max ${formatFileSize(maxSize)})`,
      };
    }

    // Check extension
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!SUPPORTED_EXTENSIONS.includes(ext)) {
      return {
        valid: false,
        error: `Unsupported file type: ${ext}`,
      };
    }

    return { valid: true };
  }

  /**
   * Get file type category
   * @param {File} file
   * @returns {string} Category: 'image', 'document', 'text', 'archive', 'audio', 'video', 'unknown'
   */
  function getFileCategory(file) {
    for (const [category, mimes] of Object.entries(SUPPORTED_TYPES)) {
      if (mimes.includes(file.type)) return category;
    }
    // Fallback: check extension
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp'].includes(ext)) return 'image';
    if (['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'].includes(ext)) return 'document';
    if (['.txt', '.csv', '.json'].includes(ext)) return 'text';
    if (['.zip'].includes(ext)) return 'archive';
    if (['.mp3', '.wav', '.ogg'].includes(ext)) return 'audio';
    if (['.mp4', '.webm'].includes(ext)) return 'video';
    return 'unknown';
  }

  /**
   * Get icon for file category
   * @param {string} category
   * @returns {string} Unicode icon
   */
  function getFileIcon(category) {
    const icons = {
      image: '🖼',
      document: '📄',
      text: '📝',
      archive: '📦',
      audio: '🎵',
      video: '🎬',
      unknown: '📎',
    };
    return icons[category] || icons.unknown;
  }

  /* ----- Local Storage Helpers ----- */
  /**
   * Safe localStorage get with JSON parse
   * @param {string} key
   * @param {*} fallback
   * @returns {*}
   */
  function storageGet(key, fallback = null) {
    try {
      const raw = localStorage.getItem('jarvis_' + key);
      return raw !== null ? JSON.parse(raw) : fallback;
    } catch {
      return fallback;
    }
  }

  /**
   * Safe localStorage set with JSON stringify
   * @param {string} key
   * @param {*} value
   */
  function storageSet(key, value) {
    try {
      localStorage.setItem('jarvis_' + key, JSON.stringify(value));
    } catch (err) {
      console.warn('[JARVIS] localStorage write failed:', err);
    }
  }

  /**
   * Remove a localStorage item
   * @param {string} key
   */
  function storageRemove(key) {
    try {
      localStorage.removeItem('jarvis_' + key);
    } catch { /* ignore */ }
  }

  /* ----- Public API ----- */
  return {
    $, qs, qsa,
    sanitizeHTML,
    htmlEscape: sanitizeHTML,
    formatFileSize, formatTimestamp,
    debounce, throttle,
    generateId, isOnline,
    showToast, tryCatch, tryCatchAsync,
    confirm,
    validateFile, getFileCategory, getFileIcon,
    storageGet, storageSet, storageRemove,
    SUPPORTED_EXTENSIONS, MAX_FILE_SIZE,
  };

})();
