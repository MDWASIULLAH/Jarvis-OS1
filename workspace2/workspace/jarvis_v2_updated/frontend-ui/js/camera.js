/* ============================================================
   JARVIS — Camera Module
   Full camera modal with live preview, capture, and fallback
   ============================================================ */
'use strict';

const JARVIS_CAMERA = (() => {

  /* ----- State ----- */
  let stream = null;
  let facingMode = 'environment'; // 'environment' (rear) or 'user' (front)
  let captured = false;

  /* DOM cache */
  let modal = null;
  let video = null;
  let captureCanvas = null;
  let captureCtx = null;
  let previewContainer = null;
  let statusEl = null;

  /* Fallback file input */
  let fallbackInput = null;

  /* Callback */
  let onCapture = null; // (dataUrl: string, file: File) => void

  /* ----- Initialization ----- */
  function init(callback) {
    onCapture = callback;
    modal = document.getElementById('cameraModal');
    facingMode = JARVIS_UTILS.storageGet('cameraFacing', 'environment');
  }

  /* ----- Open Camera ----- */
  /**
   * Open the camera modal
   * Falls back to file picker if camera is unavailable
   */
  async function open() {
    if (!modal) {
      // No modal in DOM, use fallback
      openFallback();
      return;
    }

    // Check for camera support
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      JARVIS_UTILS.showToast('Camera not supported in this browser', 'warning');
      openFallback();
      return;
    }

    // Build modal content
    modal.innerHTML = `
      <div class="camera-preview" id="cameraPreviewContainer">
        <video id="cameraVideo" autoplay playsinline muted></video>
        <canvas id="cameraCanvas"></canvas>
        <div class="camera-flash" id="cameraFlash"></div>
      </div>
      <div class="camera-controls" id="cameraControls">
        <button class="camera-btn cancel" id="cameraCancelBtn" title="Cancel" aria-label="Cancel">✕</button>
        <button class="camera-btn capture" id="cameraCaptureBtn" title="Capture" aria-label="Capture">◉</button>
        <button class="camera-btn" id="cameraFlipBtn" title="Flip Camera" aria-label="Flip Camera">⟳</button>
      </div>
      <div class="camera-status" id="cameraStatus">INITIALIZING VISUAL ARRAY...</div>
    `;

    video = document.getElementById('cameraVideo');
    captureCanvas = document.getElementById('cameraCanvas');
    captureCtx = captureCanvas.getContext('2d');
    previewContainer = document.getElementById('cameraPreviewContainer');
    statusEl = document.getElementById('cameraStatus');
    captured = false;

    // Bind buttons
    document.getElementById('cameraCancelBtn').addEventListener('click', close);
    document.getElementById('cameraCaptureBtn').addEventListener('click', handleCapture);
    document.getElementById('cameraFlipBtn').addEventListener('click', flipCamera);

    // Keyboard: Escape to close
    const onKey = (e) => {
      if (e.key === 'Escape') {
        close();
        document.removeEventListener('keydown', onKey);
      }
    };
    document.addEventListener('keydown', onKey);

    // Show modal
    modal.classList.add('open');

    // Start camera stream
    try {
      await startStream();
    } catch (err) {
      console.warn('[JARVIS Camera] Failed to access camera:', err);
      handleCameraError(err);
    }
  }

  /* ----- Stream Management ----- */
  async function startStream() {
    // Stop any existing stream
    stopStream();

    const constraints = {
      video: {
        facingMode: facingMode,
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
      audio: false,
    };

    try {
      stream = await navigator.mediaDevices.getUserMedia(constraints);
      if (video) {
        video.srcObject = stream;
        video.onloadedmetadata = () => {
          // Set canvas dimensions to match video
          captureCanvas.width = video.videoWidth;
          captureCanvas.height = video.videoHeight;
          if (statusEl) statusEl.textContent = 'VISUAL ARRAY CONNECTED // READY';
        };
      }
      JARVIS_RENDERER.pulse(1.2);
    } catch (err) {
      throw err;
    }
  }

  function stopStream() {
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      stream = null;
    }
    if (video) {
      video.srcObject = null;
    }
  }

  /* ----- Camera Actions ----- */
  function handleCapture() {
    if (captured) {
      // Currently showing captured image — confirm it
      confirmCapture();
    } else {
      // Capture photo from live preview
      capturePhoto();
    }
  }

  function capturePhoto() {
    if (!video || !captureCtx) return;

    // Draw current video frame to canvas
    captureCtx.drawImage(video, 0, 0, captureCanvas.width, captureCanvas.height);
    captured = true;

    // Flash effect
    const flash = document.getElementById('cameraFlash');
    if (flash) {
      flash.classList.add('flash');
      setTimeout(() => flash.classList.remove('flash'), 300);
    }

    // Show captured image (swap video/canvas visibility via CSS class)
    if (previewContainer) previewContainer.classList.add('captured');
    if (statusEl) statusEl.textContent = 'IMAGE CAPTURED // CONFIRM OR RETAKE';

    // Update buttons
    const captureBtn = document.getElementById('cameraCaptureBtn');
    const flipBtn = document.getElementById('cameraFlipBtn');
    if (captureBtn) {
      captureBtn.innerHTML = '✓';
      captureBtn.classList.add('confirm');
      captureBtn.title = 'Confirm';
    }
    if (flipBtn) {
      flipBtn.innerHTML = '↺';
      flipBtn.title = 'Retake';
      flipBtn.onclick = retake;
    }

    JARVIS_RENDERER.pulse(1.5);
  }

  function retake() {
    captured = false;
    if (previewContainer) previewContainer.classList.remove('captured');
    if (statusEl) statusEl.textContent = 'VISUAL ARRAY CONNECTED // READY';

    // Restore buttons
    const captureBtn = document.getElementById('cameraCaptureBtn');
    const flipBtn = document.getElementById('cameraFlipBtn');
    if (captureBtn) {
      captureBtn.innerHTML = '◉';
      captureBtn.classList.remove('confirm');
      captureBtn.title = 'Capture';
    }
    if (flipBtn) {
      flipBtn.innerHTML = '⟳';
      flipBtn.title = 'Flip Camera';
      flipBtn.onclick = flipCamera;
    }
  }

  function confirmCapture() {
    // Get data URL from canvas
    const dataUrl = captureCanvas.toDataURL('image/jpeg', 0.92);

    // Convert to File object
    const blob = dataURLtoBlob(dataUrl);
    const file = new File([blob], `jarvis-capture-${Date.now()}.jpg`, {
      type: 'image/jpeg',
    });

    // Pass to callback
    if (onCapture) {
      onCapture(dataUrl, file);
    }

    JARVIS_UTILS.showToast('Photo captured', 'success');
    close();
  }

  async function flipCamera() {
    facingMode = facingMode === 'environment' ? 'user' : 'environment';
    JARVIS_UTILS.storageSet('cameraFacing', facingMode);
    if (statusEl) statusEl.textContent = 'SWITCHING CAMERA...';

    try {
      await startStream();
    } catch (err) {
      JARVIS_UTILS.showToast('Failed to switch camera', 'error');
      // Try switching back
      facingMode = facingMode === 'environment' ? 'user' : 'environment';
      try { await startStream(); } catch { /* ignore */ }
    }
  }

  /* ----- Close Modal ----- */
  function close() {
    stopStream();
    captured = false;
    if (modal) modal.classList.remove('open');
  }

  /* ----- Error Handling ----- */
  function handleCameraError(err) {
    let message = 'Camera access failed';
    let shouldFallback = true;

    if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
      message = 'Camera permission denied. Please allow camera access in your browser settings.';
      shouldFallback = true;
    } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
      message = 'No camera found on this device.';
      shouldFallback = true;
    } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
      message = 'Camera is being used by another application.';
      shouldFallback = true;
    } else if (err.name === 'OverconstrainedError') {
      message = 'Camera does not meet requirements. Trying fallback...';
      shouldFallback = true;
    }

    JARVIS_UTILS.showToast(message, 'warning');
    close();

    if (shouldFallback) {
      openFallback();
    }
  }

  /* ----- Fallback: Native File Picker with Camera Capture ----- */
  function openFallback() {
    if (!fallbackInput) {
      fallbackInput = document.createElement('input');
      fallbackInput.type = 'file';
      fallbackInput.accept = 'image/*';
      fallbackInput.capture = 'environment';

      fallbackInput.addEventListener('change', () => {
        const file = fallbackInput.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (e) => {
          if (onCapture) {
            onCapture(e.target.result, file);
          }
          JARVIS_UTILS.showToast('Photo selected', 'success');
        };
        reader.readAsDataURL(file);

        // Reset for next use
        fallbackInput.value = '';
      });
    }

    fallbackInput.click();
  }

  /* ----- Helpers ----- */
  function dataURLtoBlob(dataUrl) {
    const arr = dataUrl.split(',');
    const mime = arr[0].match(/:(.*?);/)[1];
    const bstr = atob(arr[1]);
    let n = bstr.length;
    const u8arr = new Uint8Array(n);
    while (n--) u8arr[n] = bstr.charCodeAt(n);
    return new Blob([u8arr], { type: mime });
  }

  /* ----- Public API ----- */
  return {
    init,
    open,
    close,
  };

})();
