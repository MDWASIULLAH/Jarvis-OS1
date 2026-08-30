/* ============================================================
   JARVIS — Image Viewer Module
   Responsive image viewer with zoom, pan, rotate, download
   Including pinch zoom, fullscreen, fit width/height/original
   ============================================================ */
'use strict';

const JARVIS_IMAGEVIEWER = (() => {

  let overlay = null;
  let imgEl = null;
  let currentImage = null;
  let scale = 1;
  let rotation = 0;
  let panX = 0, panY = 0;
  let isDragging = false;
  let dragStartX = 0, dragStartY = 0;
  let dragPanStartX = 0, dragPanStartY = 0;
  let pinchStartDist = 0;
  let pinchStartScale = 1;
  let images = [];
  let currentIndex = 0;
  let fitMode = 'fit-width';

  function init() {
    createOverlay();
  }

  function createOverlay() {
    if (overlay) return;
    overlay = document.createElement('div');
    overlay.className = 'img-viewer-overlay';
    overlay.innerHTML = `
      <div class="img-viewer-toolbar">
        <button class="iv-btn" data-action="prev" title="Previous">&#8249;</button>
        <button class="iv-btn" data-action="next" title="Next">&#8250;</button>
        <span class="iv-counter"></span>
        <div class="iv-spacer"></div>
        <button class="iv-btn" data-action="zoom-in" title="Zoom In">+</button>
        <button class="iv-btn" data-action="zoom-out" title="Zoom Out">-</button>
        <button class="iv-btn" data-action="fit-width" title="Fit Width">W</button>
        <button class="iv-btn" data-action="fit-height" title="Fit Height">H</button>
        <button class="iv-btn" data-action="original" title="Original Size">1:1</button>
        <button class="iv-btn" data-action="rotate-left" title="Rotate Left">&#8634;</button>
        <button class="iv-btn" data-action="rotate-right" title="Rotate Right">&#8635;</button>
        <button class="iv-btn" data-action="fullscreen" title="Fullscreen">&#9974;</button>
        <button class="iv-btn" data-action="download" title="Download">&#8615;</button>
        <button class="iv-btn iv-close" data-action="close" title="Close">&#10005;</button>
      </div>
      <div class="img-viewer-container">
        <img class="img-viewer-image" src="" alt="" draggable="false" />
      </div>
      <div class="img-viewer-info"></div>
    `;
    document.body.appendChild(overlay);

    imgEl = overlay.querySelector('.img-viewer-image');
    bindViewerEvents();
  }

  function bindViewerEvents() {
    overlay.querySelector('.iv-close').addEventListener('click', close);
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay || e.target.classList.contains('img-viewer-container')) close();
    });

    overlay.querySelectorAll('.iv-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const action = btn.dataset.action;
        handleAction(action);
      });
    });

    imgEl.addEventListener('pointerdown', onPointerDown);
    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);

    imgEl.addEventListener('wheel', onWheel, { passive: false });

    overlay.addEventListener('touchstart', onTouchStart, { passive: false });
    overlay.addEventListener('touchmove', onTouchMove, { passive: false });
    overlay.addEventListener('touchend', onTouchEnd);

    document.addEventListener('keydown', onKeyDown);
    document.addEventListener('fullscreenchange', onFullscreenChange);
  }

  function handleAction(action) {
    switch (action) {
      case 'prev': navigate(-1); break;
      case 'next': navigate(1); break;
      case 'zoom-in': zoomTo(scale * 1.25); break;
      case 'zoom-out': zoomTo(scale * 0.8); break;
      case 'fit-width': fitToWidth(); break;
      case 'fit-height': fitToHeight(); break;
      case 'original': zoomTo(1); panX = 0; panY = 0; fitMode = 'original'; applyTransform(); break;
      case 'rotate-left': rotation -= 90; applyTransform(); break;
      case 'rotate-right': rotation += 90; applyTransform(); break;
      case 'fullscreen': toggleFullscreen(); break;
      case 'download': downloadImage(); break;
      case 'close': close(); break;
    }
  }

  function open(imageSrc, opts = {}) {
    if (!overlay) createOverlay();
    images = opts.images || [imageSrc];
    currentIndex = opts.index || images.indexOf(imageSrc);
    if (currentIndex < 0) currentIndex = 0;
    loadImage(images[currentIndex]);
    overlay.classList.add('active');
    document.body.style.overflow = 'hidden';
    updateCounter();
  }

  function loadImage(src) {
    currentImage = src;
    imgEl.src = src;
    scale = 1;
    rotation = 0;
    panX = 0;
    panY = 0;
    fitMode = 'fit-width';
    imgEl.onload = () => fitToWidth();
    updateInfo();
  }

  function close() {
    overlay.classList.remove('active');
    document.body.style.overflow = '';
    if (document.fullscreenElement) document.exitFullscreen();
    currentImage = null;
  }

  function navigate(dir) {
    currentIndex = (currentIndex + dir + images.length) % images.length;
    loadImage(images[currentIndex]);
    updateCounter();
  }

  function zoomTo(newScale) {
    scale = Math.max(0.1, Math.min(20, newScale));
    fitMode = 'custom';
    applyTransform();
  }

  function fitToWidth() {
    fitMode = 'fit-width';
    const container = overlay.querySelector('.img-viewer-container');
    const cw = container.clientWidth;
    const iw = imgEl.naturalWidth || 800;
    scale = cw / iw;
    panX = 0;
    panY = 0;
    applyTransform();
  }

  function fitToHeight() {
    fitMode = 'fit-height';
    const container = overlay.querySelector('.img-viewer-container');
    const ch = container.clientHeight;
    const ih = imgEl.naturalHeight || 600;
    scale = ch / ih;
    panX = 0;
    panY = 0;
    applyTransform();
  }

  function applyTransform() {
    imgEl.style.transform = `translate(${panX}px, ${panY}px) scale(${scale}) rotate(${rotation}deg)`;
    imgEl.style.transformOrigin = 'center center';
    updateInfo();
  }

  function onPointerDown(e) {
    isDragging = true;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    dragPanStartX = panX;
    dragPanStartY = panY;
    imgEl.style.cursor = 'grabbing';
    e.preventDefault();
  }

  function onPointerMove(e) {
    if (!isDragging) return;
    panX = dragPanStartX + (e.clientX - dragStartX);
    panY = dragPanStartY + (e.clientY - dragStartY);
    fitMode = 'custom';
    applyTransform();
  }

  function onPointerUp() {
    isDragging = false;
    if (imgEl) imgEl.style.cursor = scale > 1 ? 'grab' : 'default';
  }

  function onWheel(e) {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.1 : 0.1;
    const newScale = scale * (1 + delta);
    const rect = imgEl.getBoundingClientRect();
    const mx = e.clientX - rect.left - rect.width / 2;
    const my = e.clientY - rect.top - rect.height / 2;
    const ratio = newScale / scale;
    panX = panX - mx * (ratio - 1);
    panY = panY - my * (ratio - 1);
    scale = Math.max(0.1, Math.min(20, newScale));
    fitMode = 'custom';
    applyTransform();
  }

  function onTouchStart(e) {
    if (e.touches.length === 2) {
      pinchStartDist = getPinchDistance(e.touches);
      pinchStartScale = scale;
      e.preventDefault();
    }
  }

  function onTouchMove(e) {
    if (e.touches.length === 2) {
      const dist = getPinchDistance(e.touches);
      scale = Math.max(0.1, Math.min(20, pinchStartScale * (dist / pinchStartDist)));
      fitMode = 'custom';
      applyTransform();
      e.preventDefault();
    }
  }

  function onTouchEnd() {
    pinchStartDist = 0;
  }

  function getPinchDistance(touches) {
    return Math.hypot(
      touches[0].clientX - touches[1].clientX,
      touches[0].clientY - touches[1].clientY
    );
  }

  function onKeyDown(e) {
    if (!overlay || !overlay.classList.contains('active')) return;
    switch (e.key) {
      case 'Escape': close(); break;
      case 'ArrowLeft': navigate(-1); break;
      case 'ArrowRight': navigate(1); break;
      case '+': case '=': zoomTo(scale * 1.25); break;
      case '-': zoomTo(scale * 0.8); break;
      case '0': zoomTo(1); panX = 0; panY = 0; fitMode = 'original'; applyTransform(); break;
      case 'f': case 'F': toggleFullscreen(); break;
      case 'w': case 'W': fitToWidth(); break;
      case 'h': case 'H': fitToHeight(); break;
      case 'r': case 'R': rotation = (rotation + 90) % 360; applyTransform(); break;
    }
  }

  function toggleFullscreen() {
    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else {
      overlay.requestFullscreen();
    }
  }

  function onFullscreenChange() {
    const btn = overlay.querySelector('[data-action="fullscreen"]');
    if (btn) btn.textContent = document.fullscreenElement ? '\u2BC0' : '\u26F4';
  }

  function downloadImage() {
    if (!currentImage) return;
    const a = document.createElement('a');
    a.href = currentImage;
    a.download = 'jarvis-image-' + Date.now() + '.png';
    a.click();
  }

  function updateCounter() {
    const counter = overlay.querySelector('.iv-counter');
    if (counter && images.length > 1) {
      counter.textContent = `${currentIndex + 1} / ${images.length}`;
      counter.style.display = 'inline';
    } else if (counter) {
      counter.style.display = 'none';
    }
    const prev = overlay.querySelector('[data-action="prev"]');
    const next = overlay.querySelector('[data-action="next"]');
    if (prev && next) {
      const show = images.length > 1;
      prev.style.display = show ? '' : 'none';
      next.style.display = show ? '' : 'none';
    }
  }

  function updateInfo() {
    const info = overlay.querySelector('.img-viewer-info');
    if (info) {
      const pct = Math.round(scale * 100);
      info.textContent = `${pct}% | Rot: ${rotation}deg | ${fitMode}`;
    }
  }

  function isOpen() {
    return overlay && overlay.classList.contains('active');
  }

  return { init, open, close, isOpen, loadImage };

})();
