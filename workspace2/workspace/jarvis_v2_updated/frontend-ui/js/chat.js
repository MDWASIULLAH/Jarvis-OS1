/* ============================================================
   JARVIS — Chat System
   Full conversation with markdown rendering, message actions
   Messages are APPENDED, never overwritten
   ============================================================ */
'use strict';

const JARVIS_CHAT = (() => {

  /* ----- State ----- */
  /* Confirmation tokens are one-shot and held in backend memory, so any token
     issued before this page load is already dead (spent, or lost to a restart).
     Stamping each reply with the session it arrived in lets restored history
     render those prompts as expired instead of offering a button that can only
     ever fail. */
  const SESSION_ID = JARVIS_UTILS.generateId('session');

  let messages = [];        // Current conversation messages
  let currentChatId = null;
  let isProcessing = false;
  let typingIndicator = null;

  /* DOM cache */
  let chatContainer = null;

  /* ----- Initialization ----- */
  function init() {
    chatContainer = document.getElementById('chatMessages');
    if (!chatContainer) {
      console.error('[JARVIS Chat] #chatMessages not found');
      return;
    }

    // Load current chat or create new
    currentChatId = JARVIS_UTILS.storageGet('currentChatId', null);
    if (currentChatId) {
      const chat = JARVIS_HISTORY.getChat(currentChatId);
      if (chat) {
        messages = chat.messages || [];
        renderAllMessages();
      } else {
        newChat();
      }
    } else {
      newChat();
    }
  }

  /* ----- New Chat ----- */
  function newChat() {
    currentChatId = JARVIS_UTILS.generateId('chat');
    messages = [];
    clearChatUI();
    JARVIS_UTILS.storageSet('currentChatId', currentChatId);

    // Register with history
    JARVIS_HISTORY.createChat(currentChatId, 'New Conversation');
  }

  /**
   * Switch to a different chat
   * @param {string} chatId
   */
  function switchChat(chatId) {
    // Save current chat first
    saveCurrentChat();

    const chat = JARVIS_HISTORY.getChat(chatId);
    if (!chat) {
      JARVIS_UTILS.showToast('Chat not found', 'error');
      return;
    }

    currentChatId = chatId;
    messages = chat.messages || [];
    JARVIS_UTILS.storageSet('currentChatId', currentChatId);
    clearChatUI();
    renderAllMessages();
  }

  /* ----- Message Management ----- */
  /**
   * Add a user message to the conversation
   * @param {string} content - Message text
   * @param {Array} [attachments=[]] - File attachments
   */
  function addUserMessage(content, attachments = []) {
    const msg = {
      id: JARVIS_UTILS.generateId('msg'),
      role: 'user',
      content,
      timestamp: Date.now(),
      attachments: attachments.map(a => ({
        name: a.name,
        type: a.type,
        size: a.size,
        dataUrl: a.dataUrl || null,
        category: JARVIS_UTILS.getFileCategory(a),
      })),
      edited: false,
    };

    messages.push(msg);
    renderMessage(msg);
    scrollToBottom();

    // Auto-title the chat from first user message
    if (messages.filter(m => m.role === 'user').length === 1) {
      const title = content.substring(0, 40) + (content.length > 40 ? '…' : '');
      JARVIS_HISTORY.renameChat(currentChatId, title);
    }

    saveCurrentChat();
    return msg;
  }

  /**
   * Add an assistant message to the conversation
   * @param {string} content - Message text (can be markdown)
   * @param {Object} [meta={}] - Optional metadata (searchSources, etc.)
   */
  function addAssistantMessage(content, meta = {}) {
    const msg = {
      id: JARVIS_UTILS.generateId('msg'),
      role: 'assistant',
      content,
      timestamp: Date.now(),
      attachments: [],
      meta: { ...meta, sessionId: SESSION_ID },
    };

    messages.push(msg);
    removeTypingIndicator();
    renderMessage(msg);
    scrollToBottom();
    saveCurrentChat();

    // Sound + visual feedback on receive
    if (typeof JARVIS_ADVANCED !== 'undefined') {
      JARVIS_ADVANCED.playSound('receive');
    }

    return msg;
  }

  /**
   * Show typing indicator while waiting for response
   */
  function showTypingIndicator() {
    if (typingIndicator) return;

    typingIndicator = document.createElement('div');
    typingIndicator.className = 'chat-msg assistant';
    typingIndicator.id = 'typingIndicator';
    typingIndicator.innerHTML = `
      <div class="chat-bubble">
        <div class="typing-indicator">
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
        </div>
      </div>
    `;
    chatContainer.appendChild(typingIndicator);
    scrollToBottom();
  }

  function removeTypingIndicator() {
    if (typingIndicator) {
      typingIndicator.remove();
      typingIndicator = null;
    }
  }

  /* ----- Stream Response (typewriter effect) ----- */
  /**
   * Stream assistant response character by character
   * @param {string} fullContent - Complete response text
   * @param {Object} [meta={}] - Optional metadata
   * @returns {Promise<Object>} The created message
   */
  async function streamAssistantMessage(fullContent, meta = {}) {
    removeTypingIndicator();

    const msg = {
      id: JARVIS_UTILS.generateId('msg'),
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      attachments: [],
      meta: { ...meta, sessionId: SESSION_ID },
    };
    messages.push(msg);

    // Create the bubble element
    const msgEl = createMessageElement(msg);
    chatContainer.appendChild(msgEl);
    const bubble = msgEl.querySelector('.chat-bubble');

    // Typewriter effect
    let index = 0;
    const chunkSize = 3; // characters per tick
    const delay = 15;    // ms per chunk

    return new Promise(resolve => {
      function typeNext() {
        if (index < fullContent.length) {
          index = Math.min(index + chunkSize, fullContent.length);
          msg.content = fullContent.substring(0, index);
          bubble.innerHTML = renderMarkdown(msg.content);
          scrollToBottom();
          setTimeout(typeNext, delay);
        } else {
          // Final render with actions
          msg.content = fullContent;
          renderMessageInPlace(msgEl, msg);
          saveCurrentChat();
          resolve(msg);
        }
      }
      typeNext();
    });
  }

  /* ----- Message Rendering ----- */
  function renderAllMessages() {
    clearChatUI();
    messages.forEach(msg => {
      if (!msg.deleted) renderMessage(msg);
    });
    scrollToBottom();
  }

  function renderMessage(msg) {
    const el = createMessageElement(msg);
    chatContainer.appendChild(el);
  }

  function createMessageElement(msg) {
    const el = document.createElement('div');
    el.className = `chat-msg ${msg.role}`;
    el.dataset.msgId = msg.id;

    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble';

    // Render attachments
    if (msg.attachments && msg.attachments.length > 0) {
      const attachHtml = msg.attachments.map(a => {
        if (a.category === 'image' && a.dataUrl) {
          return `<img src="${JARVIS_UTILS.sanitizeHTML(a.dataUrl)}" alt="${JARVIS_UTILS.sanitizeHTML(a.name)}" style="max-width:200px;margin:4px 0;">`;
        }
        return `<div style="padding:4px 8px;border-radius:6px;background:rgba(255,186,90,.1);border:1px solid rgba(255,186,90,.15);font-size:11px;margin:4px 0;">
          ${JARVIS_UTILS.getFileIcon(a.category)} ${JARVIS_UTILS.sanitizeHTML(a.name)}
          <small style="color:rgba(255,210,130,.5);margin-left:6px;">${JARVIS_UTILS.formatFileSize(a.size)}</small>
        </div>`;
      }).join('');
      bubble.innerHTML = attachHtml;
    }

    // Render content
    if (msg.content) {
      bubble.innerHTML += renderMarkdown(msg.content);
    }

    el.appendChild(bubble);

    // Meta row (timestamp + actions)
    const meta = document.createElement('div');
    meta.className = 'chat-meta';

    const timeEl = document.createElement('span');
    timeEl.className = 'chat-time';
    timeEl.textContent = JARVIS_UTILS.formatTimestamp(msg.timestamp);
    meta.appendChild(timeEl);

    const actions = document.createElement('div');
    actions.className = 'chat-actions';

    // Copy button
    actions.appendChild(createActionBtn('📋', 'Copy', () => {
      navigator.clipboard.writeText(msg.content || '').then(() => {
        JARVIS_UTILS.showToast('Copied to clipboard', 'success');
      }).catch(() => {
        JARVIS_UTILS.showToast('Failed to copy', 'error');
      });
    }));

    // Delete button
    actions.appendChild(createActionBtn('🗑', 'Delete', async () => {
      const confirmed = await JARVIS_UTILS.confirm('Delete this message?');
      if (confirmed) {
        deleteMessage(msg.id);
      }
    }));

    // Role-specific actions
    if (msg.role === 'user') {
      // Edit button
      actions.appendChild(createActionBtn('✏️', 'Edit', () => {
        editMessage(msg.id);
      }));
    } else if (msg.role === 'assistant') {
      // Regenerate button
      actions.appendChild(createActionBtn('🔄', 'Regenerate', () => {
        regenerateMessage(msg.id);
      }));
      // Like/Dislike reactions (from advanced module)
      if (typeof JARVIS_ADVANCED !== 'undefined') {
        JARVIS_ADVANCED.addReactionButtons(actions, msg);
      }
    }

    meta.appendChild(actions);
    el.appendChild(meta);

    // Media, citations, tool trace and confirmation prompts sit between the
    // bubble and the meta row.
    attachTrace(el, msg);

    return el;
  }

  function renderMessageInPlace(el, msg) {
    const bubble = el.querySelector('.chat-bubble');
    if (bubble) {
      let html = '';
      // Re-render attachments
      if (msg.attachments && msg.attachments.length > 0) {
        html += msg.attachments.map(a => {
          if (a.category === 'image' && a.dataUrl) {
            return `<img src="${JARVIS_UTILS.sanitizeHTML(a.dataUrl)}" alt="${JARVIS_UTILS.sanitizeHTML(a.name)}" style="max-width:200px;margin:4px 0;">`;
          }
          return `<div style="padding:4px 8px;border-radius:6px;background:rgba(255,186,90,.1);border:1px solid rgba(255,186,90,.15);font-size:11px;margin:4px 0;">
            ${JARVIS_UTILS.getFileIcon(a.category)} ${JARVIS_UTILS.sanitizeHTML(a.name)}
            <small style="color:rgba(255,210,130,.5);margin-left:6px;">${JARVIS_UTILS.formatFileSize(a.size)}</small>
          </div>`;
        }).join('');
      }
      html += renderMarkdown(msg.content);
      bubble.innerHTML = html;
    }
    // The streaming path builds the bubble before the trace exists, so the
    // trace is attached here once the reply has finished typing.
    attachTrace(el, msg);
  }

  /* ----- Brain trace rendering -----
     The backend returns a full trace per turn (media, sources, tool calls,
     confirmation prompts). Rendering it is what separates "chatbot that claims
     it did something" from "assistant that shows what it actually did". */

  /**
   * Build the extra blocks that sit under an assistant reply.
   * @param {Object} meta - meta from JARVIS_API.sendMessage
   * @returns {HTMLElement|null}
   */
  function buildTraceElement(meta) {
    if (!meta) return null;
    const media = meta.media || [];
    const sources = meta.sources || [];
    // The backend emits {tool, ok, detail}. `name`/`summary` are accepted too so
    // a future rename cannot silently blank the trace out.
    const tools = (meta.tools || [])
      .filter(t => t && (t.tool || t.name))
      .map(t => ({
        name: t.tool || t.name,
        ok: t.ok !== false,
        detail: t.detail || t.summary || t.error || '',
      }));
    const confirmation = meta.confirmation;

    if (!media.length && !sources.length && !tools.length && !confirmation) return null;

    const wrap = document.createElement('div');
    wrap.className = 'msg-trace';

    /* --- Media gallery (real images the backend fetched or generated) --- */
    if (media.length) {
      const gallery = document.createElement('div');
      gallery.className = 'trace-gallery';
      media.slice(0, 8).forEach(item => {
        const url = item.url || item.path || item.data_url;
        if (!url) return;
        const fig = document.createElement('figure');
        fig.className = 'trace-media';

        const img = document.createElement('img');
        img.src = url;
        img.loading = 'lazy';
        img.alt = item.caption || item.title || item.prompt || 'Image returned by JARVIS';
        // A broken thumbnail is worse than an honest gap.
        img.addEventListener('error', () => { fig.remove(); });
        fig.appendChild(img);

        const caption = item.caption || item.title || item.source;
        if (caption) {
          const cap = document.createElement('figcaption');
          cap.textContent = caption;
          fig.appendChild(cap);
        }
        if (item.link || item.source_url) {
          const a = document.createElement('a');
          a.href = item.link || item.source_url;
          a.target = '_blank';
          a.rel = 'noopener noreferrer';
          a.appendChild(fig);
          gallery.appendChild(a);
        } else {
          gallery.appendChild(fig);
        }
      });
      if (gallery.children.length) wrap.appendChild(gallery);
    }

    /* --- Confirmation prompt for destructive/system actions --- */
    if (confirmation) {
      const box = document.createElement('div');
      box.className = 'trace-confirm';

      // Backend keys are confirmation_id / description / reason.
      const confirmId = confirmation.confirmation_id || confirmation.token || confirmation.id;

      const q = document.createElement('div');
      q.className = 'trace-confirm-q';
      // `description` is markdown-ish ("open **chrome**"); render the bold only.
      q.innerHTML = JARVIS_UTILS.sanitizeHTML(
        confirmation.description || confirmation.question || 'this action'
      ).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
      box.appendChild(q);

      if (confirmation.reason) {
        const why = document.createElement('div');
        why.className = 'trace-note';
        why.textContent = confirmation.reason;
        box.appendChild(why);
      }

      const row = document.createElement('div');
      row.className = 'trace-confirm-row';

      // A token from an earlier page session can no longer be redeemed, so show
      // that plainly instead of a button whose only outcome is failure. A live
      // prompt always carries the current stamp, so a missing one means the
      // message came from storage (or a build before stamping existed).
      const stale = meta.sessionId !== SESSION_ID;

      if (stale) {
        row.innerHTML = '<span class="trace-note">This request expired when the page reloaded. Ask me again to run it.</span>';
      } else {
        const yes = document.createElement('button');
        yes.className = 'trace-btn trace-btn-go';
        yes.textContent = 'Confirm';
        yes.addEventListener('click', async () => {
          row.innerHTML = '<span class="trace-note">Running…</span>';
          const res = await JARVIS_API.confirmAction(confirmId, true);
          // Surface the backend's own explanation -- it names the executable it
          // could not find, which a generic failure line would throw away.
          const note = res.message || (res.ok ? 'Done.' : 'Could not run it.');
          row.innerHTML = `<span class="trace-note">${JARVIS_UTILS.sanitizeHTML(note)}</span>`;
        });

        const no = document.createElement('button');
        no.className = 'trace-btn';
        no.textContent = 'Cancel';
        no.addEventListener('click', () => {
          // No network call: declining just leaves the token unredeemed.
          row.innerHTML = '<span class="trace-note">Cancelled.</span>';
        });

        row.appendChild(yes);
        row.appendChild(no);
      }

      box.appendChild(row);
      wrap.appendChild(box);
    }

    /* --- Citations --- */
    if (sources.length) {
      const list = document.createElement('div');
      list.className = 'trace-sources';
      const label = document.createElement('div');
      label.className = 'trace-label';
      label.textContent = `Sources (${sources.length})`;
      list.appendChild(label);

      sources.slice(0, 6).forEach(s => {
        const row = document.createElement('div');
        row.className = 'trace-source';
        if (s.url) {
          const a = document.createElement('a');
          a.href = s.url;
          a.target = '_blank';
          a.rel = 'noopener noreferrer';
          a.textContent = s.title || s.url;
          row.appendChild(a);
        } else {
          row.textContent = s.title || String(s);
        }
        list.appendChild(row);
      });
      wrap.appendChild(list);
    }

    /* --- Collapsed "what actually ran" trace --- */
    if (tools.length || meta.intent) {
      const det = document.createElement('details');
      det.className = 'trace-tools';

      const sum = document.createElement('summary');
      const okCount = tools.filter(t => t.ok).length;
      const bits = [];
      if (meta.intent) bits.push(meta.intent);
      if (tools.length) bits.push(`${okCount}/${tools.length} tools`);
      sum.textContent = bits.join(' · ') || 'trace';
      det.appendChild(sum);

      const body = document.createElement('div');
      body.className = 'trace-tools-body';

      if (meta.intent) {
        const conf = typeof meta.confidence === 'number' ? ` (${(meta.confidence * 100).toFixed(0)}%)` : '';
        const src = meta.intentSource ? ` via ${meta.intentSource}` : '';
        body.innerHTML += `<div class="trace-row"><b>intent</b> ${JARVIS_UTILS.sanitizeHTML(meta.intent)}${conf}${src}</div>`;
      }
      (meta.plan || []).forEach((step, i) => {
        body.innerHTML += `<div class="trace-row"><b>${i + 1}.</b> ${JARVIS_UTILS.sanitizeHTML(step)}</div>`;
      });
      tools.forEach(t => {
        const mark = t.ok ? '✓' : '✕';
        const cls = t.ok ? 'trace-ok' : 'trace-fail';
        body.innerHTML += `<div class="trace-row ${cls}">${mark} <b>${JARVIS_UTILS.sanitizeHTML(t.name)}</b> ${JARVIS_UTILS.sanitizeHTML(String(t.detail))}</div>`;
      });
      if (meta.reflection) {
        body.innerHTML += `<div class="trace-row trace-note">${JARVIS_UTILS.sanitizeHTML(meta.reflection)}</div>`;
      }

      det.appendChild(body);
      wrap.appendChild(det);
    }

    return wrap.children.length ? wrap : null;
  }

  function attachTrace(el, msg) {
    if (msg.role !== 'assistant') return;
    const existing = el.querySelector('.msg-trace');
    if (existing) existing.remove();
    const trace = buildTraceElement(msg.meta);
    if (!trace) return;
    const bubble = el.querySelector('.chat-bubble');
    if (bubble) bubble.insertAdjacentElement('afterend', trace);
    else el.appendChild(trace);
  }

  function createActionBtn(icon, title, onClick) {
    const btn = document.createElement('button');
    btn.className = 'chat-action-btn';
    btn.textContent = icon;
    btn.title = title;
    btn.setAttribute('aria-label', title);
    btn.addEventListener('click', onClick);
    return btn;
  }

  /* ----- Message Actions ----- */
  function deleteMessage(msgId) {
    const idx = messages.findIndex(m => m.id === msgId);
    if (idx === -1) return;
    messages[idx].deleted = true;
    const el = chatContainer.querySelector(`[data-msg-id="${msgId}"]`);
    if (el) el.remove();
    saveCurrentChat();
  }

  function editMessage(msgId) {
    const msg = messages.find(m => m.id === msgId);
    if (!msg) return;

    // Put message content back into input for editing
    const cmd = document.getElementById('command');
    if (cmd) {
      cmd.value = msg.content;
      cmd.focus();
    }

    // Remove this message and all subsequent messages
    const idx = messages.findIndex(m => m.id === msgId);
    const removed = messages.splice(idx);
    removed.forEach(m => {
      const el = chatContainer.querySelector(`[data-msg-id="${m.id}"]`);
      if (el) el.remove();
    });
    saveCurrentChat();
  }

  function regenerateMessage(msgId) {
    const idx = messages.findIndex(m => m.id === msgId);
    if (idx === -1) return;

    // Find the user message before this assistant message
    let userMsg = null;
    for (let i = idx - 1; i >= 0; i--) {
      if (messages[i].role === 'user') {
        userMsg = messages[i];
        break;
      }
    }

    // Remove assistant message
    messages[idx].deleted = true;
    const el = chatContainer.querySelector(`[data-msg-id="${msgId}"]`);
    if (el) el.remove();

    // Re-process the user message
    if (userMsg) {
      processUserInput(userMsg.content, userMsg.attachments || []);
    }
  }

  /* ----- Process User Input ----- */
  /**
   * Process a user command/message
   * @param {string} text - User input text
   * @param {Array} [attachments=[]] - File attachments
   */
  async function processUserInput(text, attachments = []) {
    if (!text.trim() && attachments.length === 0) return;
    if (isProcessing) return;

    isProcessing = true;

    // Add user message
    addUserMessage(text, attachments);

    // Update HUD
    const mode = document.getElementById('mode');
    if (mode) mode.textContent = 'QUANTUM ARRAY // ANALYZING';
    JARVIS_RENDERER.pulse(1.7);

    // Zoom effect
    const currentZoom = JARVIS_RENDERER.getZoom();
    JARVIS_RENDERER.setZoom(Math.min(4.0, currentZoom + 0.36));
    setTimeout(() => JARVIS_RENDERER.setZoom(currentZoom), 500);

    // Show typing indicator
    showTypingIndicator();

    try {
      // Check if web search is enabled
      const webSearchOn = JARVIS_UTILS.storageGet('webSearchOn', true);

      // Call AI API
      const context = buildContext();
      const response = await JARVIS_API.sendMessage(text, context, {
        attachments,
        webSearch: webSearchOn,
      });

      if (response && response.content) {
        // Stream the response
        await streamAssistantMessage(response.content, response.meta || {});

        // Speak the response (non-blocking)
        const plainText = response.content.replace(/[#*`_\[\]()]/g, '').substring(0, 500);
        JARVIS_VOICE.speak(plainText);
      } else {
        addAssistantMessage('I received your command but encountered an issue generating a response. Please try again.');
      }
    } catch (err) {
      removeTypingIndicator();
      console.error('[JARVIS Chat] Process error:', err);

      if (!JARVIS_UTILS.isOnline()) {
        addAssistantMessage('⚠ No internet connection detected. Please check your network and try again.');
      } else {
        addAssistantMessage('⚠ I encountered an error processing your request. Please verify the API configuration in Settings.');
      }
    } finally {
      isProcessing = false;
      if (mode && !JARVIS_VOICE.isSpeaking()) {
        mode.textContent = 'QUANTUM ARRAY // STANDBY';
      }
    }
  }

  /**
   * Build conversation context for API
   * @returns {Array} Messages array for API
   */
  function buildContext() {
    const contextSize = JARVIS_UTILS.storageGet('contextSize', 20);
    const recent = messages
      .filter(m => !m.deleted)
      .slice(-contextSize)
      .map(m => ({
        role: m.role,
        content: m.content,
      }));
    return recent;
  }

  /* ----- Markdown Renderer ----- */
  /**
   * Render markdown to safe HTML
   * @param {string} text - Markdown text
   * @returns {string} HTML string
   */
  function renderMarkdown(text) {
    if (!text) return '';

    let html = JARVIS_UTILS.sanitizeHTML(text);

    // Code blocks (``` ... ```)
    html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, (match, lang, code) => {
      const langLabel = lang ? `<small style="color:rgba(255,210,130,.4);font-size:9px;position:absolute;top:4px;left:8px;">${lang}</small>` : '';
      return `<pre>${langLabel}<button class="code-copy-btn" onclick="navigator.clipboard.writeText(this.parentElement.querySelector('code').textContent).then(()=>JARVIS_UTILS.showToast('Copied','success'))">📋</button><code>${code.trim()}</code></pre>`;
    });

    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Bold
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // Italic
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

    // Strikethrough
    html = html.replace(/~~(.+?)~~/g, '<del>$1</del>');

    // Headers
    html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

    // Blockquotes
    html = html.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>');

    // Unordered lists
    html = html.replace(/^[*-] (.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

    // Ordered lists
    html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');

    // Links
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

    // Images
    html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1">');

    // Horizontal rules
    html = html.replace(/^---$/gm, '<hr style="border:0;border-top:1px solid rgba(255,186,90,.15);margin:8px 0;">');

    // Tables (pipe-delimited)
    html = html.replace(/^\|(.+)\|$/gm, (match, row) => {
      const cells = row.split('|').map(c => c.trim());
      const isHeader = cells.every(c => /^[-:]+$/.test(c));
      if (isHeader) return ''; // Skip separator row
      const tag = 'td';
      return '<tr>' + cells.map(c => `<${tag}>${c}</${tag}>`).join('') + '</tr>';
    });
    // Wrap table rows
    if (html.includes('<tr>')) {
      html = html.replace(/(<tr>[\s\S]*?<\/tr>)+/g, '<table>$&</table>');
    }

    // Line breaks
    html = html.replace(/\n/g, '<br>');

    // Clean up double <br>
    html = html.replace(/<br><br>/g, '<br>');

    return html;
  }

  /* ----- Helpers ----- */
  function clearChatUI() {
    if (!chatContainer) return;
    // Preserve the sticky chat-controls div
    const controls = chatContainer.querySelector('.chat-controls');
    chatContainer.innerHTML = '';
    if (controls) chatContainer.appendChild(controls);
  }

  function scrollToBottom() {
    if (!chatContainer) return;
    // Double rAF ensures DOM has painted before scrolling
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        chatContainer.scrollTop = chatContainer.scrollHeight + 500;
      });
    });
  }

  function saveCurrentChat() {
    if (currentChatId) {
      JARVIS_HISTORY.updateChat(currentChatId, { messages });
    }
  }

  /**
   * Get current chat ID
   * @returns {string|null}
   */
  function getCurrentChatId() { return currentChatId; }

  /**
   * Get current messages
   * @returns {Array}
   */
  function getMessages() { return messages; }

  /**
   * Check if currently processing
   * @returns {boolean}
   */
  function getIsProcessing() { return isProcessing; }

  /* ----- Public API ----- */
  return {
    init,
    newChat,
    switchChat,
    addUserMessage,
    addAssistantMessage,
    streamAssistantMessage,
    processUserInput,
    showTypingIndicator,
    removeTypingIndicator,
    renderMarkdown,
    getCurrentChatId,
    getMessages,
    get isProcessing() { return isProcessing; },
  };

})();
