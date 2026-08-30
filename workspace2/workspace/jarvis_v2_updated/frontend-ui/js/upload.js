/* ============================================================
   JARVIS — Upload Module
   Photo picker, file upload, attachment bar management
   ============================================================ */
'use strict';

const JARVIS_UPLOAD = (() => {

  /* ----- State ----- */
  let attachments = []; // { id, file, name, type, size, category, dataUrl, element }
  let maxFileSize = JARVIS_UTILS.MAX_FILE_SIZE;

  /* DOM cache */
  let attachmentBar = null;
  let photoInput = null;
  let fileInput = null;

  /* ----- Initialization ----- */
  function init() {
    attachmentBar = document.getElementById('attachmentBar');
    maxFileSize = JARVIS_UTILS.storageGet('maxFileSize', JARVIS_UTILS.MAX_FILE_SIZE);

    // Create hidden file inputs
    createFileInputs();
  }

  function createFileInputs() {
    // Photo picker — images only, multiple selection
    photoInput = document.createElement('input');
    photoInput.type = 'file';
    photoInput.accept = 'image/*';
    photoInput.multiple = true;
    photoInput.hidden = true;
    photoInput.id = 'photoPickerInput';
    document.body.appendChild(photoInput);

    photoInput.addEventListener('change', () => {
      handleFiles(photoInput.files);
      photoInput.value = ''; // Reset for next use
    });

    // File picker — all supported types, multiple selection
    fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = JARVIS_UTILS.SUPPORTED_EXTENSIONS.join(',');
    fileInput.multiple = true;
    fileInput.hidden = true;
    fileInput.id = 'filePickerInput';
    document.body.appendChild(fileInput);

    fileInput.addEventListener('change', () => {
      handleFiles(fileInput.files);
      fileInput.value = ''; // Reset for next use
    });
  }

  /* ----- Pickers ----- */
  /**
   * Open the photo gallery picker
   */
  function openPhotoPicker() {
    if (photoInput) photoInput.click();
  }

  /**
   * Open the file upload picker
   */
  function openFilePicker() {
    if (fileInput) fileInput.click();
  }

  /* ----- Handle Files ----- */
  /**
   * Process selected files
   * @param {FileList} files
   */
  function handleFiles(files) {
    if (!files || files.length === 0) return;

    for (let i = 0; i < files.length; i++) {
      addFile(files[i]);
    }
  }

  /**
   * Add a single file to attachments
   * @param {File} file
   */
  function addFile(file) {
    // Validate
    const validation = JARVIS_UTILS.validateFile(file, maxFileSize);
    if (!validation.valid) {
      JARVIS_UTILS.showToast(validation.error, 'error');
      return;
    }

    const category = JARVIS_UTILS.getFileCategory(file);
    const id = JARVIS_UTILS.generateId('att');

    const attachment = {
      id,
      file,
      name: file.name,
      type: file.type,
      size: file.size,
      category,
      dataUrl: null,
      element: null,
    };

    attachments.push(attachment);

    // Read data URL for images (for preview and sending)
    if (category === 'image') {
      const reader = new FileReader();
      reader.onload = (e) => {
        attachment.dataUrl = e.target.result;
        renderAttachmentItem(attachment);
      };
      reader.readAsDataURL(file);
    } else {
      renderAttachmentItem(attachment);
    }

    updateBarVisibility();
    JARVIS_RENDERER.pulse(1.0);
    JARVIS_UTILS.showToast(`Added: ${file.name}`, 'info');
  }

  /**
   * Add a camera capture directly
   * @param {string} dataUrl - Image data URL
   * @param {File} file - Image file
   */
  function addCameraCapture(dataUrl, file) {
    const id = JARVIS_UTILS.generateId('att');
    const attachment = {
      id,
      file,
      name: file.name,
      type: file.type,
      size: file.size,
      category: 'image',
      dataUrl,
      element: null,
    };

    attachments.push(attachment);
    renderAttachmentItem(attachment);
    updateBarVisibility();
    JARVIS_RENDERER.pulse(1.0);
  }

  /* ----- Render Attachment Item ----- */
  function renderAttachmentItem(attachment) {
    if (!attachmentBar) return;

    const item = document.createElement('div');
    item.className = 'attachment-item';
    item.dataset.attachId = attachment.id;
    item.title = `${attachment.name} (${JARVIS_UTILS.formatFileSize(attachment.size)})`;

    if (attachment.category === 'image' && attachment.dataUrl) {
      const img = document.createElement('img');
      img.src = attachment.dataUrl;
      img.alt = attachment.name;
      item.appendChild(img);
    } else {
      const iconDiv = document.createElement('div');
      iconDiv.className = 'file-icon';
      const icon = JARVIS_UTILS.getFileIcon(attachment.category);
      const ext = attachment.name.split('.').pop().toUpperCase();
      iconDiv.innerHTML = `<span>${icon}</span><small>${ext}</small>`;
      item.appendChild(iconDiv);
    }

    // Remove button
    const removeBtn = document.createElement('button');
    removeBtn.className = 'attachment-remove';
    removeBtn.textContent = '×';
    removeBtn.title = 'Remove';
    removeBtn.setAttribute('aria-label', `Remove ${attachment.name}`);
    removeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      removeAttachment(attachment.id);
    });
    item.appendChild(removeBtn);

    // Progress bar (simulated)
    const progress = document.createElement('div');
    progress.className = 'progress-bar';
    progress.style.position = 'absolute';
    progress.style.bottom = '0';
    progress.style.left = '0';
    progress.style.right = '0';
    const fill = document.createElement('div');
    fill.className = 'progress-fill';
    fill.style.width = '0%';
    progress.appendChild(fill);
    item.appendChild(progress);

    attachmentBar.appendChild(item);
    attachment.element = item;

    // Animate progress
    requestAnimationFrame(() => {
      fill.style.width = '100%';
      setTimeout(() => {
        progress.style.opacity = '0';
        setTimeout(() => progress.remove(), 300);
      }, 600);
    });
  }

  /* ----- Remove Attachment ----- */
  /**
   * Remove an attachment by ID
   * @param {string} id
   */
  function removeAttachment(id) {
    const idx = attachments.findIndex(a => a.id === id);
    if (idx === -1) return;

    const attachment = attachments[idx];
    if (attachment.element) {
      attachment.element.remove();
    }
    attachments.splice(idx, 1);
    updateBarVisibility();
  }

  /* ----- Clear All Attachments ----- */
  /**
   * Clear all attachments (called after sending message)
   */
  function clearAll() {
    attachments.forEach(a => {
      if (a.element) a.element.remove();
    });
    attachments = [];
    updateBarVisibility();
  }

  /* ----- Get Attachments for Sending ----- */
  /**
   * Get all current attachments
   * @returns {Array<{name, type, size, dataUrl, category}>}
   */
  function getAttachments() {
    return attachments.map(a => ({
      name: a.name,
      type: a.type,
      size: a.size,
      dataUrl: a.dataUrl,
      category: a.category,
    }));
  }

  /**
   * Check if there are attachments
   * @returns {boolean}
   */
  function hasAttachments() {
    return attachments.length > 0;
  }

  /* ----- Bar Visibility ----- */
  function updateBarVisibility() {
    if (attachmentBar) {
      attachmentBar.classList.toggle('has-items', attachments.length > 0);
    }
  }

  /* ----- Drag & Drop Support ----- */
  function enableDragDrop(targetElement) {
    if (!targetElement) return;

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
      targetElement.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
      });
    });

    targetElement.addEventListener('dragenter', () => {
      targetElement.style.borderColor = 'var(--accent)';
    });

    targetElement.addEventListener('dragleave', () => {
      targetElement.style.borderColor = '';
    });

    targetElement.addEventListener('drop', (e) => {
      targetElement.style.borderColor = '';
      const files = e.dataTransfer?.files;
      if (files) handleFiles(files);
    });
  }

  /* ----- Public API ----- */
  return {
    init,
    openPhotoPicker,
    openFilePicker,
    addFile,
    addCameraCapture,
    removeAttachment,
    clearAll,
    getAttachments,
    hasAttachments,
    handleFiles,
    enableDragDrop,
  };

})();
