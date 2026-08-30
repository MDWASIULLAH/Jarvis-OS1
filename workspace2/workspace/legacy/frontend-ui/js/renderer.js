/* ============================================================
   JARVIS — 3D Orbital Renderer
   Preserved from original + enhanced with voice reactivity
   CRITICAL: Animation loop NEVER stops, NEVER freezes
   ============================================================ */
'use strict';

const JARVIS_RENDERER = (() => {

  /* ----- DOM References ----- */
  let canvas, ctx;

  /* ----- State ----- */
  let width = 0, height = 0, dpr = 1;
  let time = 0;
  let rotationY = 0.55, rotationX = -0.18;
  let zoom = 1.48, renderZoom = 1.48;
  let energyPulse = 0;
  let voicePhase = 0, orbitPhase = 0;
  let dragActive = false, lastX = 0, lastY = 0;
  let pinchStartDistance = 0;

  /* Voice reactivity — additive layer, never blocks rendering */
  let voiceIntensity = 0;       // 0-1, smoothly interpolated
  let targetVoiceIntensity = 0; // target value from voice module
  let voiceAmplitude = 0;       // real-time amplitude from audio

  /* Performance */
  let animationId = null;
  let qualityLevel = 'high'; // 'high', 'medium', 'low'
  let fpsLimit = 0;           // 0 = unlimited
  let lastFrameTime = 0;
  let frameCount = 0;
  let fpsDisplay = 0;
  let fpsUpdateTime = 0;
  let showFps = false;
  let focusMode = false;

  /* ----- Scene Data ----- */
  const ribbons = [];
  const sparks = [];
  const nodes = [];
  const voiceBars = [];

  /* ----- Helpers ----- */
  const R = (a, b) => a + Math.random() * (b - a);

  /* ----- Initialization ----- */
  function init() {
    canvas = document.getElementById('stage');
    if (!canvas) {
      console.error('[JARVIS Renderer] Canvas #stage not found');
      return;
    }
    ctx = canvas.getContext('2d', { willReadFrequently: false });

    // Load quality settings
    const savedQuality = JARVIS_UTILS.storageGet('animationQuality', 'high');
    qualityLevel = savedQuality;
    fpsLimit = JARVIS_UTILS.storageGet('fpsLimit', 0);
    showFps = JARVIS_UTILS.storageGet('showFps', false);

    resizeCanvas();
    generateScene();
    initVoiceBars();
    bindEvents();

    // Start render loop — THIS NEVER STOPS
    lastFrameTime = performance.now();
    fpsUpdateTime = lastFrameTime;
    render();

    // Start voice bar animation
    animateVoiceBars();
  }

  /* ----- Canvas Resize ----- */
  function resizeCanvas() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);

    // Reduce resolution on low quality
    if (qualityLevel === 'low') dpr = Math.min(dpr, 1);
    else if (qualityLevel === 'medium') dpr = Math.min(dpr, 1.5);

    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = width + 'px';
    canvas.style.height = height + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  /* ----- Scene Generation (preserved exactly from original) ----- */
  function generateScene() {
    // Ribbons — 108 orbital ribbons with 88 points each
    for (let k = 0; k < 108; k++) {
      const ribbon = [];
      const phase = k / 108 * Math.PI * 2;
      const tilt = R(-1.7, 1.7);
      const orbitCount = R(1.4, 4.8);
      const baseRadius = R(2.5, 5.9);
      const waveA = R(0.08, 0.55);
      const waveB = R(0.08, 0.48);
      const heightScale = R(0.28, 0.98);

      for (let p = 0; p < 88; p++) {
        const progress = p / 87;
        const angle = phase + progress * Math.PI * 2 * orbitCount;
        const envelope = 0.22 + Math.sin(progress * Math.PI) * 0.98;
        const turb = Math.sin(progress * 13 + k * 0.78) * waveA +
                     Math.cos(progress * 25 + k * 1.24) * waveB;
        const radius = baseRadius * envelope + turb;
        const localX = Math.cos(angle) * radius;
        const localY = Math.sin(angle) * radius * heightScale +
                       Math.sin(progress * 8 + k) * 0.74;
        const localZ = Math.cos(angle * 1.7 + k * 0.21) * (0.5 + radius * 0.86);
        const tiltedY = localY * Math.cos(tilt) - localZ * Math.sin(tilt);
        const tiltedZ = localY * Math.sin(tilt) + localZ * Math.cos(tilt);

        ribbon.push({
          x: localX, y: tiltedY, z: tiltedZ,
          progress, seed: R(0, 10), thickness: R(0.4, 1.8),
        });

        // Spark from ribbon points (every 3rd point)
        if (p % 3 === 0) {
          sparks.push({
            x: localX, y: tiltedY, z: tiltedZ,
            progress, seed: R(0, 10), size: R(0.45, 1.7),
          });
        }
      }
      ribbons.push(ribbon);
    }

    // Scattered sparks — 4600 particles
    const sparkCount = qualityLevel === 'low' ? 1500 :
                       qualityLevel === 'medium' ? 3000 : 4600;
    for (let i = 0; i < sparkCount; i++) {
      const a = R(0, Math.PI * 2);
      const rad = Math.pow(Math.random(), 0.36) * R(0.5, 6.8);
      const hb = R(-2.6, 2.6);
      sparks.push({
        x: Math.cos(a) * rad,
        y: hb + Math.sin(a * 2.1) * rad * 0.2,
        z: Math.sin(a) * rad * R(0.45, 1.25),
        progress: R(0, 1), seed: R(0, 10), size: R(0.14, 0.9),
      });
    }

    // Structural nodes — 76 points
    for (let i = 0; i < 76; i++) {
      const a = i / 76 * Math.PI * 2;
      const rad = R(3.2, 6.4);
      nodes.push({
        x: Math.cos(a) * rad,
        y: R(-3.4, 3.4),
        z: Math.sin(a) * rad,
      });
    }
  }

  /* ----- Voice Bars ----- */
  function initVoiceBars() {
    const container = document.getElementById('voiceBars');
    if (!container) return;
    for (let i = 0; i < 32; i++) {
      const b = document.createElement('i');
      container.appendChild(b);
      voiceBars.push(b);
    }
  }

  function animateVoiceBars() {
    const isSpeaking = voiceIntensity > 0.05;
    voiceBars.forEach((bar, i) => {
      const amp = isSpeaking
        ? (0.25 + Math.abs(Math.sin(time * 8 + i * 0.71) *
           Math.sin(time * 4 + i * 0.23)) * 0.95 * voiceIntensity)
        : (0.06 + Math.abs(Math.sin(time * 2 + i)) * 0.08);
      bar.style.height = (2 + amp * 28) + 'px';
      bar.style.opacity = isSpeaking ? (0.56 + amp * 0.44) : 0.28;
    });
    requestAnimationFrame(animateVoiceBars);
  }

  /* ----- 3D Projection (preserved exactly) ----- */
  function project(p, ox = 0, oy = 0) {
    const cy = Math.cos(rotationY), sy = Math.sin(rotationY);
    const cx = Math.cos(rotationX), sx = Math.sin(rotationX);
    const X = p.x * cy - p.z * sy;
    let Z = p.x * sy + p.z * cy;
    const Y = p.y * cx - Z * sx;
    Z = p.y * sx + Z * cx;
    const s = 340 / (8 + Z) * renderZoom;
    return {
      x: width / 2 + ox + X * s,
      y: height * 0.42 + oy + Y * s,
      scale: s,
      depth: Z,
    };
  }

  /* ----- Drawing Functions (preserved exactly + voice enhancements) ----- */
  function drawTrail(points, alpha, w) {
    if (points.length < 2) return;
    // Voice enhancement: boost trail brightness during speech
    const voiceAlpha = alpha + voiceIntensity * 0.06;
    ctx.strokeStyle = 'rgba(255,' + Math.floor(90 + voiceAlpha * 150) + ',13,' + voiceAlpha + ')';
    ctx.lineWidth = w;
    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i++) {
      ctx.lineTo(points[i].x, points[i].y);
    }
    ctx.stroke();
  }

  function drawBrokenOrbit(rx, ry, rot, start, end, alpha, lw, ox = 0, oy = 0) {
    ctx.save();
    ctx.translate(width / 2 + ox, height * 0.42 + oy);
    ctx.rotate(rot);
    // Voice enhancement: expand ring radii during speech
    const voiceExpand = 1 + voiceIntensity * 0.08;
    const voiceAlpha = alpha + voiceIntensity * 0.02;
    ctx.strokeStyle = 'rgba(255,163,44,' + voiceAlpha + ')';
    ctx.lineWidth = lw + voiceIntensity * 0.3;
    ctx.beginPath();
    // Guard: ellipse() throws if radius is negative
    const erx = Math.abs(rx * renderZoom * voiceExpand) || 1;
    const ery = Math.abs(ry * renderZoom * voiceExpand) || 1;
    ctx.ellipse(0, 0, erx, ery, 0, start, end);
    ctx.stroke();
    ctx.restore();
  }

  function drawCoreEye(ox = 0, oy = 0) {
    const ex = width * 0.5 - 18 * renderZoom + ox;
    const ey = height * 0.42 - 10 * renderZoom + oy;
    // Voice enhancement: increase core glow intensity during speech
    const voiceGlow = 1 + voiceIntensity * 0.6;
    const r = (125 + energyPulse * 100) * renderZoom * voiceGlow;

    const glow = ctx.createRadialGradient(ex, ey, 0, ex, ey, r);
    if (focusMode) {
      glow.addColorStop(0, 'rgba(255,200,200,1)');
      glow.addColorStop(0.06, 'rgba(255,60,60,1)');
      glow.addColorStop(0.2, 'rgba(200,15,15,.94)');
      glow.addColorStop(0.46, 'rgba(180,0,0,.28)');
      glow.addColorStop(1, 'rgba(120,0,0,0)');
    } else {
      glow.addColorStop(0, 'rgba(255,255,205,1)');
      glow.addColorStop(0.06, 'rgba(255,206,72,1)');
      glow.addColorStop(0.2, 'rgba(255,138,15,.94)');
      glow.addColorStop(0.46, 'rgba(255,68,0,.28)');
      glow.addColorStop(1, 'rgba(255,45,0,0)');
    }
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(ex, ey, r, 0, Math.PI * 2);
    ctx.fill();

    // Inner bright core — pulses with voice
    const coreSize = 8 + energyPulse * 5 + voiceIntensity * 3;
    ctx.fillStyle = 'rgba(255,239,161,.98)';
    ctx.beginPath();
    ctx.arc(ex, ey, coreSize, 0, Math.PI * 2);
    ctx.fill();

    // Spinning rings around core
    ctx.save();
    ctx.translate(ex, ey);
    for (let i = 0; i < 16; i++) {
      ctx.rotate(time * (i % 2 ? 0.25 : -0.3) + i * 0.62);
      ctx.strokeStyle = 'rgba(255,194,64,' + (0.16 + i * 0.022 + voiceIntensity * 0.03) + ')';
      ctx.lineWidth = 0.9 + i * 0.12;
      ctx.beginPath();
      ctx.arc(0, 0, (22 + i * 15) * renderZoom,
              0.15, 5.0 + Math.sin(time + i) * 0.4);
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawShockwave(ox = 0, oy = 0) {
    if (energyPulse < 0.12) return;
    const r = Math.abs((165 + (1 - energyPulse) * 340) * renderZoom) || 1;
    ctx.strokeStyle = 'rgba(255,180,53,' + energyPulse * 0.25 + ')';
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    // Guard: ensure both radii are positive for ellipse()
    ctx.ellipse(width * 0.5 + ox, height * 0.42 + oy,
                r, Math.abs(r * 0.64) || 1, rotationY * 0.25, 0, Math.PI * 2);
    ctx.stroke();
  }

  /* ----- Bloom/Glow Post-Processing ----- */
  function drawBloomPass(ox, oy) {
    // Additive bloom around the core — lightweight glow simulation
    const bx = width * 0.5 + ox;
    const by = height * 0.42 + oy;
    const bloomRadius = (200 + voiceIntensity * 80) * renderZoom;
    const bloomGlow = ctx.createRadialGradient(bx, by, 0, bx, by, bloomRadius);
    bloomGlow.addColorStop(0, 'rgba(255,160,40,' + (0.04 + voiceIntensity * 0.03) + ')');
    bloomGlow.addColorStop(0.5, 'rgba(255,80,0,' + (0.015 + voiceIntensity * 0.01) + ')');
    bloomGlow.addColorStop(1, 'rgba(255,40,0,0)');
    ctx.fillStyle = bloomGlow;
    ctx.fillRect(0, 0, width, height);
  }

  /* ----- Main Render Loop — NEVER STOPS ----- */
  function render() {
    // FPS limiting
    const now = performance.now();
    if (fpsLimit > 0) {
      const interval = 1000 / fpsLimit;
      if (now - lastFrameTime < interval) {
        animationId = requestAnimationFrame(render);
        return;
      }
    }
    lastFrameTime = now;

    // FPS counter
    frameCount++;
    if (now - fpsUpdateTime >= 1000) {
      fpsDisplay = frameCount;
      frameCount = 0;
      fpsUpdateTime = now;
      const fpsEl = document.getElementById('fpsCounter');
      if (fpsEl && showFps) {
        fpsEl.textContent = fpsDisplay + ' FPS';
        fpsEl.classList.toggle('visible', showFps);
      }
    }

    // Guard: skip rendering if canvas hasn't been sized yet
    if (width <= 0 || height <= 0) {
      animationId = requestAnimationFrame(render);
      return;
    }

    // Time progression — always moves forward
    time += 0.011;

    // Energy pulse decay
    energyPulse *= 0.965;

    // Smooth voice intensity interpolation (never snaps, never freezes)
    voiceIntensity += (targetVoiceIntensity - voiceIntensity) * 0.12;

    // Voice phase — always progresses, faster when speaking
    const isSpeaking = voiceIntensity > 0.05;
    voicePhase += isSpeaking ? 0.2 : 0.03;
    orbitPhase += isSpeaking ? 0.08 : 0.008;

    // Rotation — always rotating, faster when speaking
    const baseRotSpeed = 0.0011;
    const voiceRotBoost = voiceIntensity * 0.005;
    rotationY += baseRotSpeed + voiceRotBoost;

    // Idle tilt oscillation
    const idleTilt = Math.sin(time * 0.55) * 0.05 - 0.1;
    if (!dragActive) {
      rotationX += (idleTilt - rotationX) * 0.03;
    }

    // Voice-reactive zoom (additive, never replaces base zoom)
    const voiceZoomEffect = isSpeaking
      ? (Math.sin(voicePhase) * 0.08 +
         Math.sin(voicePhase * 2.4) * 0.035 +
         Math.sin(voicePhase * 0.6) * 0.022) * voiceIntensity
      : 0;
    renderZoom += (zoom + voiceZoomEffect + energyPulse * 0.06 - renderZoom) * 0.16;

    // Orbital movement during speech (subtle vibration, not freezing)
    const orbitX = isSpeaking ? Math.cos(orbitPhase) * 34 * voiceIntensity : 0;
    const orbitY = isSpeaking ? Math.sin(orbitPhase * 1.08) * 24 * voiceIntensity : 0;

    // --- Clear & Draw ---
    ctx.clearRect(0, 0, width, height);

    // Ambient glow
    const ambient = ctx.createRadialGradient(
      width * 0.5 + orbitX, height * 0.42 + orbitY, 5,
      width * 0.5 + orbitX, height * 0.42 + orbitY, 520 * renderZoom
    );
    ambient.addColorStop(0, 'rgba(255,92,0,.18)');
    ambient.addColorStop(0.45, 'rgba(255,60,0,.05)');
    ambient.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = ambient;
    ctx.fillRect(0, 0, width, height);

    // Broken orbital rings — 18 rings
    for (let i = 0; i < 18; i++) {
      const start = i * 0.5 + time * (i % 2 ? -0.18 : 0.14);
      const arcSpan = 2.5 + Math.sin(time * 0.8 + i) * 0.95;
      drawBrokenOrbit(100 + i * 36, 58 + i * 20,
                      time * 0.08 + i * 0.5,
                      start, start + arcSpan,
                      0.04 + i * 0.008, 0.75 + i * 0.04,
                      orbitX, orbitY);
    }

    // Lighter blend for particles and ribbons
    ctx.globalCompositeOperation = 'lighter';

    // Ribbon pass 1 — base
    const ribbonStep = qualityLevel === 'low' ? 3 : qualityLevel === 'medium' ? 2 : 1;
    for (let i = 0; i < ribbons.length; i += ribbonStep) {
      drawTrail(ribbons[i].map(p => project(p, orbitX, orbitY)), 0.1, 1.1);
    }

    // Ribbon pass 2 — animated brightness
    for (let i = 0; i < ribbons.length; i += ribbonStep) {
      const pts = ribbons[i].map(p => project(p, orbitX, orbitY));
      const f = 0.5 + 0.5 * Math.sin(time * 2.4 + i * 0.8);
      drawTrail(pts, 0.12 + f * 0.08, 0.5);
    }

    // Structural nodes with connection lines
    nodes.forEach((n, i) => {
      const o = project(n, orbitX, orbitY);
      const inr = project({ x: n.x * 0.16, y: n.y * 0.16, z: n.z * 0.16 }, orbitX, orbitY);
      const int = 0.06 + Math.abs(Math.sin(time * 2 + i)) * 0.16;
      drawTrail([o, inr], int, 0.65);
      ctx.fillStyle = 'rgba(255,210,93,.82)';
      ctx.fillRect(o.x - 1.8, o.y - 1.8, 3.6, 3.6);
    });

    // Sparks
    const sparkStep = qualityLevel === 'low' ? 4 : qualityLevel === 'medium' ? 2 : 1;
    for (let i = 0; i < sparks.length; i += sparkStep) {
      const s = sparks[i];
      const q = project(s, orbitX, orbitY);

      // Skip off-screen particles for performance
      if (q.x < -20 || q.x > width + 20 || q.y < -20 || q.y > height + 20) continue;

      const f = 0.32 + 0.68 * Math.abs(Math.sin(time * 2.6 + s.seed));
      // Voice enhancement: increase particle brightness
      const voiceBright = 1 + voiceIntensity * 0.4;
      const a = (0.06 + (1 - s.progress) * 0.24) * f * (q.scale / 28) * voiceBright;
      const sz = Math.max(0.28, (s.size * q.scale) / 12);
      ctx.fillStyle = 'rgba(255,' + Math.floor(112 + f * 125) + ',18,' + a + ')';
      ctx.fillRect(q.x - sz / 2, q.y - sz / 2, sz, sz);
    }

    // Back to normal blend
    ctx.globalCompositeOperation = 'source-over';

    // Bloom pass
    drawBloomPass(orbitX, orbitY);

    // Core eye
    drawCoreEye(orbitX, orbitY);

    // Shockwave
    drawShockwave(orbitX, orbitY);

    // NEVER STOP — always request next frame
    animationId = requestAnimationFrame(render);
  }

  /* ----- Input Events ----- */
  function bindEvents() {
    // Resize
    window.addEventListener('resize', JARVIS_UTILS.debounce(resizeCanvas, 150));

    // Mouse wheel zoom — only when scrolling over the 3D canvas, NOT over UI elements
    window.addEventListener('wheel', (e) => {
      // Don't zoom when scrolling inside chat, settings, sidebar, or any scrollable UI
      const scrollableSelectors = ['#chatMessages', '#settingsModal', '#historySidebar', '.sheet', '.suggestions-dropdown', '.shortcuts-overlay'];
      const isInsideScrollable = scrollableSelectors.some(sel => {
        const el = document.querySelector(sel);
        return el && el.contains(e.target);
      });
      if (isInsideScrollable) return; // Let the element scroll normally

      e.preventDefault();
      setZoom(zoom + (e.deltaY < 0 ? 0.14 : -0.14));
    }, { passive: false });

    // Pointer drag rotation
    canvas.addEventListener('pointerdown', (e) => {
      dragActive = true;
      lastX = e.clientX;
      lastY = e.clientY;
    });
    window.addEventListener('pointerup', () => { dragActive = false; });
    window.addEventListener('pointermove', (e) => {
      if (!dragActive) return;
      rotationY += (e.clientX - lastX) * 0.009;
      rotationX += (e.clientY - lastY) * 0.006;
      rotationX = Math.max(-1.3, Math.min(1.3, rotationX));
      lastX = e.clientX;
      lastY = e.clientY;
    });

    // Pinch zoom
    window.addEventListener('touchstart', (e) => {
      if (e.touches.length === 2) {
        pinchStartDistance = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY
        );
      }
    }, { passive: true });

    window.addEventListener('touchmove', (e) => {
      if (e.touches.length === 2) {
        const n = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY
        );
        setZoom(zoom + (n - pinchStartDistance) / 200);
        pinchStartDistance = n;
      }
    }, { passive: true });
  }

  /* ----- Public API ----- */
  function setZoom(v) {
    zoom = Math.max(0.72, Math.min(4.0, v));
    const zoomEl = document.getElementById('zoomValue');
    if (zoomEl) zoomEl.textContent = Math.round(zoom * 100) + '%';
    energyPulse = Math.max(energyPulse, 0.8);
  }

  /**
   * Trigger an energy pulse (used when commands are processed)
   * @param {number} intensity - Pulse intensity (0-3)
   */
  function pulse(intensity = 1.5) {
    energyPulse = Math.max(energyPulse, intensity);
  }

  /**
   * Set voice intensity for animation sync
   * Called by voice module — smoothly interpolated, never freezes render
   * @param {number} intensity - 0 to 1
   */
  function setVoiceIntensity(intensity) {
    targetVoiceIntensity = Math.max(0, Math.min(1, intensity));
  }

  /**
   * Set voice amplitude for real-time reactivity
   * @param {number} amp - 0 to 1
   */
  function setVoiceAmplitude(amp) {
    voiceAmplitude = amp;
    // Boost energy pulse proportionally to amplitude
    if (amp > 0.3) {
      energyPulse = Math.max(energyPulse, amp * 1.5);
    }
  }

  /**
   * Set animation quality
   * @param {'high'|'medium'|'low'} quality
   */
  function setQuality(quality) {
    qualityLevel = quality;
    JARVIS_UTILS.storageSet('animationQuality', quality);
    // Note: spark count changes require scene regeneration
    // For now, quality affects rendering skip-rate
  }

  /**
   * Set FPS limit
   * @param {number} fps - 0 for unlimited
   */
  function setFpsLimit(fps) {
    fpsLimit = fps;
    JARVIS_UTILS.storageSet('fpsLimit', fps);
  }

  /**
   * Toggle FPS counter visibility
   * @param {boolean} visible
   */
  function setShowFps(visible) {
    showFps = visible;
    JARVIS_UTILS.storageSet('showFps', visible);
    const el = document.getElementById('fpsCounter');
    if (el) el.classList.toggle('visible', visible);
  }

  /**
   * Get current zoom level
   * @returns {number}
   */
  function getZoom() { return zoom; }

  /**
   * Toggle focus mode (red 3D)
   * @param {boolean} enabled
   */
  function setFocusMode(enabled) {
    focusMode = enabled;
    if (canvas) {
      canvas.style.filter = enabled
        ? 'hue-rotate(-30deg) saturate(2.5)'
        : 'none';
    }
  }

  function isFocusMode() { return focusMode; }

  return {
    init,
    setZoom,
    getZoom,
    pulse,
    setVoiceIntensity,
    setVoiceAmplitude,
    setQuality,
    setFpsLimit,
    setShowFps,
    setFocusMode,
    isFocusMode,
  };

})();
