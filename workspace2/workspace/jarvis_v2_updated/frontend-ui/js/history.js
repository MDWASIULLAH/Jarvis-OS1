/* ============================================================
   JARVIS — Chat History & Sidebar
   ChatGPT-style history panel with local persistence
   ============================================================ */
'use strict';

const JARVIS_HISTORY = (() => {

  /* ----- State ----- */
  let chats = {};         // { chatId: { id, title, messages, pinned, archived, createdAt, updatedAt } }
  let sidebarOpen = false;

  /* DOM cache */
  let sidebar = null;
  let overlay = null;
  let chatList = null;
  let searchInput = null;

  /* ----- Initialization ----- */
  function init() {
    sidebar = document.getElementById('historySidebar');
    overlay = document.getElementById('sidebarOverlay');
    chatList = document.getElementById('chatList');
    searchInput = document.getElementById('chatSearchInput');

    // Load saved chats
    chats = JARVIS_UTILS.storageGet('chats', {});

    // Bind events
    bindEvents();

    // Render chat list
    renderChatList();
  }

  function bindEvents() {
    // Close sidebar on overlay click
    if (overlay) {
      overlay.addEventListener('click', closeSidebar);
    }
    
    // Close button
    const closeBtn = document.getElementById('closeSidebarBtn');
    if (closeBtn) {
      closeBtn.addEventListener('click', closeSidebar);
    }

    // New chat button
    const newChatBtn = document.getElementById('newChatBtn');
    if (newChatBtn) {
      newChatBtn.addEventListener('click', () => {
        JARVIS_CHAT.newChat();
        renderChatList();
        closeSidebar();
      });
    }

    // Search
    if (searchInput) {
      searchInput.addEventListener('input', JARVIS_UTILS.debounce(() => {
        renderChatList(searchInput.value.trim());
      }, 200));
    }

    // Sidebar footer buttons
    const importBtn = document.getElementById('importChatsBtn');
    const exportBtn = document.getElementById('exportChatsBtn');
    const clearBtn = document.getElementById('clearHistoryBtn');

    if (importBtn) importBtn.addEventListener('click', importChats);
    if (exportBtn) exportBtn.addEventListener('click', exportAllChats);
    if (clearBtn) clearBtn.addEventListener('click', clearAllHistory);

    // Keyboard: Escape closes sidebar
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && sidebarOpen) {
        closeSidebar();
      }
    });
  }

  /* ----- Sidebar Toggle ----- */
  function toggleSidebar() {
    sidebarOpen ? closeSidebar() : openSidebar();
  }

  function openSidebar() {
    sidebarOpen = true;
    renderChatList();
    if (sidebar) sidebar.classList.add('open');
    if (overlay) overlay.classList.add('open');
    if (searchInput) searchInput.focus();
  }

  function closeSidebar() {
    sidebarOpen = false;
    if (sidebar) sidebar.classList.remove('open');
    if (overlay) overlay.classList.remove('open');
  }

  /* ----- Chat CRUD ----- */
  /**
   * Create a new chat entry
   * @param {string} id
   * @param {string} title
   */
  function createChat(id, title) {
    chats[id] = {
      id,
      title,
      messages: [],
      pinned: false,
      archived: false,
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
    saveChats();
  }

  /**
   * Get a chat by ID
   * @param {string} id
   * @returns {Object|null}
   */
  function getChat(id) {
    return chats[id] || null;
  }

  /**
   * Update chat data
   * @param {string} id
   * @param {Object} data - Partial data to merge
   */
  function updateChat(id, data) {
    if (!chats[id]) return;
    Object.assign(chats[id], data, { updatedAt: Date.now() });
    saveChats();
  }

  /**
   * Rename a chat
   * @param {string} id
   * @param {string} title
   */
  function renameChat(id, title) {
    if (!chats[id]) return;
    chats[id].title = title;
    chats[id].updatedAt = Date.now();
    saveChats();
    renderChatList();
  }

  /**
   * Delete a chat
   * @param {string} id
   */
  async function deleteChat(id) {
    const confirmed = await JARVIS_UTILS.confirm('Delete this conversation?');
    if (!confirmed) return;

    delete chats[id];
    saveChats();
    renderChatList();

    // If deleting current chat, start new one
    if (id === JARVIS_CHAT.getCurrentChatId()) {
      JARVIS_CHAT.newChat();
    }

    JARVIS_UTILS.showToast('Conversation deleted', 'info');
  }

  /**
   * Toggle pin on a chat
   * @param {string} id
   */
  function togglePin(id) {
    if (!chats[id]) return;
    chats[id].pinned = !chats[id].pinned;
    chats[id].updatedAt = Date.now();
    saveChats();
    renderChatList();
  }

  /**
   * Archive a chat
   * @param {string} id
   */
  function archiveChat(id) {
    if (!chats[id]) return;
    chats[id].archived = true;
    chats[id].updatedAt = Date.now();
    saveChats();
    renderChatList();
    JARVIS_UTILS.showToast('Conversation archived', 'info');
  }

  /* ----- Rendering ----- */
  function renderChatList(searchQuery = '') {
    if (!chatList) return;

    const currentId = JARVIS_CHAT.getCurrentChatId();
    const query = searchQuery.toLowerCase();

    // Sort: pinned first, then by updatedAt
    let chatArray = Object.values(chats)
      .filter(c => !c.archived)
      .filter(c => {
        if (!query) return true;
        return c.title.toLowerCase().includes(query) ||
               (c.messages || []).some(m => m.content && m.content.toLowerCase().includes(query));
      })
      .sort((a, b) => {
        if (a.pinned !== b.pinned) return b.pinned ? 1 : -1;
        return b.updatedAt - a.updatedAt;
      });

    chatList.innerHTML = '';

    if (chatArray.length === 0) {
      chatList.innerHTML = `
        <div style="padding:20px;text-align:center;font-size:11px;color:rgba(255,210,130,.4);">
          ${query ? 'No matching conversations' : 'No conversations yet'}
        </div>`;
      return;
    }

    chatArray.forEach(chat => {
      const item = document.createElement('div');
      item.className = `chat-list-item${chat.id === currentId ? ' active' : ''}`;
      item.dataset.chatId = chat.id;

      item.innerHTML = `
        ${chat.pinned ? '<span class="pin-icon">📌</span>' : ''}
        <span class="chat-title" title="${JARVIS_UTILS.sanitizeHTML(chat.title)}">${JARVIS_UTILS.sanitizeHTML(chat.title)}</span>
        <div class="chat-list-actions">
          <button class="chat-list-action" data-action="pin" title="${chat.pinned ? 'Unpin' : 'Pin'}" aria-label="${chat.pinned ? 'Unpin' : 'Pin'}">📌</button>
          <button class="chat-list-action" data-action="rename" title="Rename" aria-label="Rename">✏️</button>
          <button class="chat-list-action" data-action="export" title="Export" aria-label="Export">📥</button>
          <button class="chat-list-action" data-action="archive" title="Archive" aria-label="Archive">📦</button>
          <button class="chat-list-action" data-action="delete" title="Delete" aria-label="Delete">🗑</button>
        </div>
      `;

      // Click to switch chat
      item.addEventListener('click', (e) => {
        if (e.target.closest('.chat-list-action')) return;
        JARVIS_CHAT.switchChat(chat.id);
        renderChatList();
        closeSidebar();
      });

      // Action buttons
      item.querySelectorAll('.chat-list-action').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          const action = btn.dataset.action;
          switch (action) {
            case 'pin': togglePin(chat.id); break;
            case 'rename': inlineRename(chat.id, item); break;
            case 'export': exportChat(chat.id); break;
            case 'archive': archiveChat(chat.id); break;
            case 'delete': deleteChat(chat.id); break;
          }
        });
      });

      chatList.appendChild(item);
    });
  }

  /* ----- Inline Rename ----- */
  function inlineRename(chatId, listItem) {
    const titleEl = listItem.querySelector('.chat-title');
    if (!titleEl) return;

    const currentTitle = chats[chatId]?.title || '';
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'chat-title-input';
    input.value = currentTitle;

    titleEl.replaceWith(input);
    input.focus();
    input.select();

    const commit = () => {
      const newTitle = input.value.trim() || currentTitle;
      renameChat(chatId, newTitle);
    };

    input.addEventListener('blur', commit);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        commit();
      }
      if (e.key === 'Escape') {
        renderChatList(); // Revert
      }
    });
  }

  /* ----- Import / Export ----- */
  /**
   * Export a single chat as JSON
   * @param {string} chatId
   */
  function exportChat(chatId) {
    const chat = chats[chatId];
    if (!chat) return;

    const data = JSON.stringify(chat, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `jarvis-chat-${chat.title.replace(/[^a-z0-9]/gi, '_').substring(0, 30)}.json`;
    a.click();
    URL.revokeObjectURL(url);
    JARVIS_UTILS.showToast('Chat exported', 'success');
  }

  /**
   * Export all chats as a single JSON file
   */
  function exportAllChats() {
    const data = JSON.stringify(chats, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `jarvis-history-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
    JARVIS_UTILS.showToast('All chats exported', 'success');
  }

  /**
   * Import chats from a JSON file
   */
  function importChats() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.addEventListener('change', () => {
      const file = input.files[0];
      if (!file) return;

      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const imported = JSON.parse(e.target.result);

          // Single chat import
          if (imported.id && imported.title && imported.messages) {
            chats[imported.id] = imported;
            saveChats();
            renderChatList();
            JARVIS_UTILS.showToast('Chat imported', 'success');
            return;
          }

          // Multi-chat import
          if (typeof imported === 'object') {
            let count = 0;
            for (const [id, chat] of Object.entries(imported)) {
              if (chat.id && chat.title) {
                chats[id] = chat;
                count++;
              }
            }
            saveChats();
            renderChatList();
            JARVIS_UTILS.showToast(`${count} chats imported`, 'success');
          }
        } catch (err) {
          JARVIS_UTILS.showToast('Invalid JSON file', 'error');
        }
      };
      reader.readAsText(file);
    });
    input.click();
  }

  /**
   * Clear all chat history
   */
  async function clearAllHistory() {
    const confirmed = await JARVIS_UTILS.confirm(
      'Delete ALL conversations? This cannot be undone.',
      'Delete All', 'Cancel'
    );
    if (!confirmed) return;

    chats = {};
    saveChats();
    JARVIS_CHAT.newChat();
    renderChatList();
    JARVIS_UTILS.showToast('All history cleared', 'info');
  }

  /* ----- Persistence ----- */
  function saveChats() {
    JARVIS_UTILS.storageSet('chats', chats);
  }

  /**
   * Get all chats (for settings export, etc.)
   * @returns {Object}
   */
  function getAllChats() { return { ...chats }; }

  /* ----- Public API ----- */
  return {
    init,
    toggleSidebar,
    openSidebar,
    closeSidebar,
    createChat,
    getChat,
    updateChat,
    renameChat,
    deleteChat,
    togglePin,
    archiveChat,
    exportChat,
    exportAllChats,
    importChats,
    clearAllHistory,
    getAllChats,
    get isOpen() { return sidebarOpen; },
  };

})();
