/**
 * workspace.js — Coding Workspace with Monaco Editor, File Tree, and Live Preview
 *
 * Dependencies: JARVIS_UTILS, JARVIS_API
 * Provides:    JARVIS_WORKSPACE
 */
var JARVIS_WORKSPACE = (function () {
  'use strict';

  var editor = null;
  var monacoReady = false;
  var currentFilePath = null;
  var isOpen = false;
  var fileTreeData = {};
  var resizing = null;
  var startX = 0, startY = 0, startWidth = 0;

  // DOM cache
  var panel, fileTree, previewFrame, previewUrl, currentFileLabel;
  var sidebar, editorContainer, previewContainer, resizerV, resizerH;

  // ==========================================================================
  // Monaco boot
  // ==========================================================================

  function bootMonaco() {
    if (typeof monaco !== 'undefined') {
      initEditor();
      return;
    }
    if (typeof require === 'undefined') {
      setTimeout(bootMonaco, 200);
      return;
    }
    try {
      require.config({
        paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs' },
      });
      require(['vs/editor/editor.main'], function () {
        monacoReady = true;
        initEditor();
      });
    } catch (e) {
      console.warn('[workspace] Monaco boot failed, retrying...', e);
      setTimeout(bootMonaco, 500);
    }
  }

  function initEditor() {
    if (editor) return;
    var el = document.getElementById('wsEditor');
    if (!el) return;
    editor = monaco.editor.create(el, {
      value: '',
      language: 'plaintext',
      theme: 'vs-dark',
      automaticLayout: true,
      fontSize: 13,
      fontFamily: "'Cascadia Code', 'Fira Code', 'Consolas', monospace",
      minimap: { enabled: true, scale: 1 },
      scrollBeyondLastLine: false,
      wordWrap: 'on',
      tabSize: 2,
      renderWhitespace: 'selection',
      bracketPairColorization: { enabled: true },
      guides: { bracketPairs: true },
    });

    // Ctrl+S save
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, function () {
      saveCurrentFile();
    });
  }

  function getLanguageFromPath(path) {
    if (!path) return 'plaintext';
    var ext = path.split('.').pop().toLowerCase();
    var map = {
      html: 'html', htm: 'html', css: 'css', js: 'javascript', mjs: 'javascript',
      jsx: 'javascript', ts: 'typescript', tsx: 'typescript', json: 'json',
      py: 'python', rb: 'ruby', php: 'php', java: 'java', c: 'c', cpp: 'cpp',
      h: 'c', go: 'go', rs: 'rust', swift: 'swift', kt: 'kotlin', scala: 'scala',
      xml: 'xml', yaml: 'yaml', yml: 'yaml', toml: 'toml', ini: 'ini',
      md: 'markdown', sql: 'sql', sh: 'shell', bash: 'shell', zsh: 'shell',
      ps1: 'powershell', dockerfile: 'dockerfile', makefile: 'makefile',
    };
    return map[ext] || 'plaintext';
  }

  // ==========================================================================
  // Init
  // ==========================================================================

  function init() {
    panel = document.getElementById('workspacePanel');
    fileTree = document.getElementById('wsFileTree');
    previewFrame = document.getElementById('wsPreviewFrame');
    previewUrl = document.getElementById('wsPreviewUrl');
    currentFileLabel = document.getElementById('wsCurrentFile');
    sidebar = document.getElementById('wsSidebar');
    editorContainer = document.getElementById('wsEditorContainer');
    previewContainer = document.getElementById('wsPreviewContainer');
    resizerV = document.getElementById('wsResizerV');
    resizerH = document.getElementById('wsResizerH');

    bindToolbar();
    bindResizer();
    bindKeyboard();
  }

  // ==========================================================================
  // Open / Close
  // ==========================================================================

  function open() {
    if (isOpen) return;
    isOpen = true;
    panel.classList.add('open');
    panel.style.display = 'flex';
    refreshFileTree();
    if (monacoReady && editor) {
      editor.layout();
    } else {
      requestAnimationFrame(function () {
        if (monacoReady && editor) editor.layout();
      });
    }
    layoutResizer();
    updatePreview();
  }

  function close() {
    if (!isOpen) return;
    isOpen = true;  // disable save-current check for now
    isOpen = false;
    panel.classList.remove('open');
    panel.style.display = 'none';
    stopResize();
  }

  function toggle() {
    if (isOpen) {
      close();
    } else {
      open();
    }
  }

  function isWorkspaceOpen() {
    return isOpen;
  }

  // ==========================================================================
  // File tree
  // ==========================================================================

  function getWorkspaceUrl(path) {
    return '/v1/workspace' + (path || '');
  }

  function refreshFileTree() {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', getWorkspaceUrl('/files'), true);
    xhr.onload = function () {
      if (xhr.status !== 200) {
        fileTree.innerHTML = '<div class="ws-empty">Could not load files</div>';
        return;
      }
      try {
        var files = JSON.parse(xhr.responseText);
        fileTreeData = {};
        files.forEach(function (f) {
          fileTreeData[f.path] = f;
        });
        renderFileTree(files);
      } catch (e) {
        fileTree.innerHTML = '<div class="ws-empty">Error loading files</div>';
      }
    };
    xhr.onerror = function () {
      fileTree.innerHTML = '<div class="ws-empty">No connection to server</div>';
    };
    xhr.send();
  }

  function renderFileTree(files) {
    if (!files || files.length === 0) {
      fileTree.innerHTML = '<div class="ws-empty">No files yet — click + File to create</div>';
      return;
    }

    // Build tree structure from flat path list
    var tree = {};
    files.forEach(function (f) {
      var parts = f.path.split('/');
      var current = tree;
      for (var i = 0; i < parts.length; i++) {
        var part = parts[i];
        var isLast = i === parts.length - 1;
        if (!current[part]) {
          current[part] = {
            name: part,
            path: parts.slice(0, i + 1).join('/'),
            isFile: isLast,
            children: isLast ? null : {},
            _entry: isLast ? f : null,
          };
        }
        current = current[part].children || {};
      }
    });

    var html = '';
    function render(node, depth) {
      // Sort: directories first, then files, alphabetically
      var keys = Object.keys(node).sort(function (a, b) {
        var na = node[a], nb = node[b];
        if (!na.isFile && nb.isFile) return -1;
        if (na.isFile && !nb.isFile) return 1;
        return a.toLowerCase().localeCompare(b.toLowerCase());
      });
      keys.forEach(function (key) {
        var item = node[key];
        var icon = item.isFile ? '&#128196;' : '&#128193;';
        var activeClass = currentFilePath === item.path ? ' active' : '';
        html += '<div class="ws-tree-item' + activeClass + '" style="--depth:' + depth + '" data-path="' + item.path + '" data-kind="' + (item.isFile ? 'file' : 'dir') + '">';
        html += '<span class="ws-tree-icon">' + icon + '</span>';
        html += '<span class="ws-tree-name">' + item.name + '</span>';
        html += '<span class="ws-tree-actions">';
        html += '<button data-action="rename" title="Rename">R</button>';
        html += '<button data-action="delete" title="Delete">X</button>';
        html += '</span>';
        html += '</div>';
        if (!item.isFile && item.children) {
          render(item.children, depth + 1);
        }
      });
    }
    render(tree, 0);
    fileTree.innerHTML = html;
    bindTreeEvents();
  }

  function bindTreeEvents() {
    var items = fileTree.querySelectorAll('.ws-tree-item');
    items.forEach(function (item) {
      item.addEventListener('click', function (e) {
        var actionBtn = e.target.closest('[data-action]');
        if (actionBtn) return;
        var path = item.getAttribute('data-path');
        var kind = item.getAttribute('data-kind');
        if (kind === 'file') {
          openFile(path);
        }
      });
    });

    var actionBtns = fileTree.querySelectorAll('[data-action]');
    actionBtns.forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var action = btn.getAttribute('data-action');
        var path = btn.closest('.ws-tree-item').getAttribute('data-path');
        if (action === 'rename') {
          promptRename(path);
        } else if (action === 'delete') {
          confirmDelete(path);
        }
      });
    });
  }

  // ==========================================================================
  // File operations
  // ==========================================================================

  function openFile(path) {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', getWorkspaceUrl('/files/read?path=' + encodeURIComponent(path)), true);
    xhr.onload = function () {
      if (xhr.status !== 200) {
        JARVIS_UTILS.toast('Failed to open: ' + path, 'error');
        return;
      }
      try {
        var data = JSON.parse(xhr.responseText);
        currentFilePath = path;
        currentFileLabel.textContent = path.replace(/^.*[\\/]/, '');
        setEditorLanguage(getLanguageFromPath(path));
        editor.setValue(data.content);
        refreshFileTree();
      } catch (e) {
        JARVIS_UTILS.toast('Error reading file', 'error');
      }
    };
    xhr.onerror = function () {
      JARVIS_UTILS.toast('Connection error opening file', 'error');
    };
    xhr.send();
  }

  function saveCurrentFile() {
    if (!currentFilePath) {
      promptNewFile();
      return;
    }
    var content = editor.getValue();
    var xhr = new XMLHttpRequest();
    xhr.open('PUT', getWorkspaceUrl('/files/' + encodeURIComponent(currentFilePath)), true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.onload = function () {
      if (xhr.status === 200) {
        updatePreview();
        refreshFileTree();
      } else {
        JARVIS_UTILS.toast('Save failed', 'error');
      }
    };
    xhr.onerror = function () {
      JARVIS_UTILS.toast('Connection error saving', 'error');
    };
    xhr.send(JSON.stringify({ content: content }));
  }

  function createFile(name, initialContent) {
    var xhr = new XMLHttpRequest();
    xhr.open('POST', getWorkspaceUrl('/files'), true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.onload = function () {
      if (xhr.status === 200 || xhr.status === 201) {
        try {
          var data = JSON.parse(xhr.responseText);
          refreshFileTree();
          openFile(data.path);
          if (initialContent && editor) {
            setTimeout(function () { editor.setValue(initialContent); saveCurrentFile(); }, 100);
          }
        } catch (e) { refreshFileTree(); }
      } else {
        JARVIS_UTILS.toast('Failed to create: ' + name, 'error');
      }
    };
    xhr.onerror = function () {
      JARVIS_UTILS.toast('Connection error creating file', 'error');
    };
    xhr.send(JSON.stringify({ name: name, content: initialContent || '' }));
  }

  function createFolder(name) {
    var xhr = new XMLHttpRequest();
    xhr.open('POST', getWorkspaceUrl('/directories?path=' + encodeURIComponent(name)), true);
    xhr.onload = function () {
      if (xhr.status === 200) {
        refreshFileTree();
      } else {
        JARVIS_UTILS.toast('Failed to create folder', 'error');
      }
    };
    xhr.onerror = function () {
      JARVIS_UTILS.toast('Connection error creating folder', 'error');
    };
    xhr.send();
  }

  function promptNewFile() {
    var name = prompt('File name:', 'index.html');
    if (!name) return;
    currentFilePath = null;
    editor.setValue('');
    setEditorLanguage(getLanguageFromPath(name));
    createFile(name, '');
  }

  function promptNewFolder() {
    var name = prompt('Folder name:');
    if (!name) return;
    createFolder(name);
  }

  function promptRename(path) {
    var oldName = path.split('/').pop();
    var newName = prompt('New name:', oldName);
    if (!newName || newName === oldName) return;
    var xhr = new XMLHttpRequest();
    xhr.open('PUT', getWorkspaceUrl('/files/' + encodeURIComponent(path) + '/rename'), true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.onload = function () {
      if (xhr.status === 200) {
        var data = JSON.parse(xhr.responseText);
        if (currentFilePath === path) {
          currentFilePath = data.new_path;
          currentFileLabel.textContent = data.new_path.replace(/^.*[\\/]/, '');
        }
        refreshFileTree();
      } else {
        JARVIS_UTILS.toast('Rename failed', 'error');
      }
    };
    xhr.onerror = function () {
      JARVIS_UTILS.toast('Connection error renaming', 'error');
    };
    xhr.send(JSON.stringify({ name: newName }));
  }

  function confirmDelete(path) {
    if (!confirm('Delete "' + path + '"?')) return;
    var xhr = new XMLHttpRequest();
    xhr.open('DELETE', getWorkspaceUrl('/files/' + encodeURIComponent(path)), true);
    xhr.onload = function () {
      if (xhr.status === 200) {
        if (currentFilePath === path) {
          currentFilePath = null;
          currentFileLabel.textContent = 'untitled';
          editor.setValue('');
        }
        refreshFileTree();
      } else {
        JARVIS_UTILS.toast('Delete failed', 'error');
      }
    };
    xhr.onerror = function () {
      JARVIS_UTILS.toast('Connection error deleting', 'error');
    };
    xhr.send();
  }

  function setEditorLanguage(lang) {
    if (!editor || !monacoReady) return;
    var model = editor.getModel();
    if (model) {
      monaco.editor.setModelLanguage(model, lang);
    }
  }

  // ==========================================================================
  // Preview
  // ==========================================================================

  function updatePreview() {
    var previewPath = getWorkspaceUrl('/preview/');
    previewUrl.textContent = previewPath;
    previewFrame.src = previewPath + '?_t=' + Date.now();
  }

  function setViewportWidth(size) {
    var frame = previewFrame;
    if (size === '100%') {
      frame.classList.remove('fixed-width');
      frame.style.removeProperty('--preview-width');
    } else {
      frame.classList.add('fixed-width');
      frame.style.setProperty('--preview-width', size);
    }

    var btns = document.querySelectorAll('#wsViewportBtns button');
    btns.forEach(function (b) {
      b.classList.toggle('active', b.getAttribute('data-size') === size);
    });
  }

  // ==========================================================================
  // Download ZIP
  // ==========================================================================

  function downloadZip() {
    var a = document.createElement('a');
    a.href = getWorkspaceUrl('/export');
    a.download = 'workspace.zip';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  // ==========================================================================
  // Toolbar binding
  // ==========================================================================

  function bindToolbar() {
    var newFileBtn = document.getElementById('wsNewFileBtn');
    var newFolderBtn = document.getElementById('wsNewFolderBtn');
    var saveBtn = document.getElementById('wsSaveBtn');
    var refreshBtn = document.getElementById('wsRefreshFilesBtn');
    var zipBtn = document.getElementById('wsDownloadZipBtn');
    var closeBtn = document.getElementById('wsCloseBtn');
    var refreshPreviewBtn = document.getElementById('wsRefreshPreviewBtn');

    if (newFileBtn) newFileBtn.addEventListener('click', promptNewFile);
    if (newFolderBtn) newFolderBtn.addEventListener('click', promptNewFolder);
    if (saveBtn) saveBtn.addEventListener('click', saveCurrentFile);
    if (refreshBtn) refreshBtn.addEventListener('click', refreshFileTree);
    if (zipBtn) zipBtn.addEventListener('click', downloadZip);
    if (closeBtn) closeBtn.addEventListener('click', close);
    if (refreshPreviewBtn) refreshPreviewBtn.addEventListener('click', updatePreview);

    // Viewport buttons
    var vpBtns = document.querySelectorAll('#wsViewportBtns button');
    vpBtns.forEach(function (btn) {
      btn.addEventListener('click', function () {
        setViewportWidth(btn.getAttribute('data-size'));
      });
    });
  }

  // ==========================================================================
  // Resizer
  // ==========================================================================

  function layoutResizer() {
    if (!resizerV) return;
    var rect = previewContainer.getBoundingClientRect();
    resizerV.style.left = (rect.left - 2) + 'px';
    resizerV.style.top = rect.top + 'px';
    resizerV.style.bottom = (window.innerHeight - rect.bottom) + 'px';
  }

  function bindResizer() {
    if (!resizerV) return;

    resizerV.addEventListener('mousedown', function (e) {
      resizing = 'v';
      startX = e.clientX;
      startWidth = previewContainer.offsetWidth;
      resizerV.classList.add('active');
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
      e.preventDefault();
    });

    document.addEventListener('mousemove', function (e) {
      if (!resizing) return;
      if (resizing === 'v') {
        var dx = startX - e.clientX;
        var newWidth = Math.max(200, Math.min(startWidth + dx, window.innerWidth - 300));
        previewContainer.style.width = newWidth + 'px';
      }
    });

    document.addEventListener('mouseup', function () {
      stopResize();
    });

    window.addEventListener('resize', function () {
      if (isOpen) layoutResizer();
    });
  }

  function stopResize() {
    if (resizing) {
      resizerV.classList.remove('active');
      resizing = null;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      if (editor && monacoReady) editor.layout();
      layoutResizer();
    }
  }

  // ==========================================================================
  // Keyboard
  // ==========================================================================

  function bindKeyboard() {
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && isOpen) {
        close();
        e.preventDefault();
      }
    });
  }

  // ==========================================================================
  // Programmatic file creation (used by agent chaining)
  // ==========================================================================

  function createProject(files) {
    // files = { "index.html": "<html>...", "style.css": "..." }
    var fileNames = Object.keys(files);
    if (fileNames.length === 0) return;

    function writeNext(idx) {
      if (idx >= fileNames.length) {
        refreshFileTree();
        // Open first generated file
        if (fileNames.length > 0) {
          setTimeout(function () { openFile(fileNames[0]); }, 200);
        }
        return;
      }
      var name = fileNames[idx];
      var content = files[name];
      createFile(name, content);
      // Wait and write next
      setTimeout(function () { writeNext(idx + 1); }, 300);
    }

    writeNext(0);
  }

  // ==========================================================================
  // Public API
  // ==========================================================================

  bootMonaco();

  return {
    init: init,
    open: open,
    close: close,
    toggle: toggle,
    isOpen: isWorkspaceOpen,
    createProject: createProject,
    updatePreview: updatePreview,
    refreshFileTree: refreshFileTree,
  };
})();
