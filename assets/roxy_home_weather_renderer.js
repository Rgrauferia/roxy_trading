/* Nexo atmosphere: a transparent illustration of fresh model data, never radar. */
(function (global) {
  'use strict';
  const instances = new WeakMap();
  const wetModes = new Set(['rain', 'storm', 'snow']);
  const modes = new Set(['rain', 'storm', 'snow', 'fog', 'sunny', 'clear-night', 'cloudy', 'partly-cloudy']);
  const clamp = (value, low, high) => Math.min(high, Math.max(low, value));
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const fresh = scene => {
    const now = Date.now();
    return scene?.fresh === true && modes.has(scene.mode) &&
      [scene.validAt, scene.fetchedAt].every(time => finite(time) && now - time >= -300000 && now - time < 2700000);
  };
  function random(seed) {
    let value = seed >>> 0;
    return () => {
      value = (Math.imul(value, 1664525) + 1013904223) >>> 0;
      return value / 4294967296;
    };
  }
  function insideViewport(root) {
    const box = root.getBoundingClientRect();
    return box.width > 0 && box.height > 0 && box.bottom > 0 && box.right > 0 &&
      box.top < global.innerHeight && box.left < global.innerWidth;
  }
  // Pre-render soft, tapered water trails once. The dark refractive edge makes
  // droplets readable on a light map without whitening the map underneath.
  function rainSprite(doc, near) {
    const sprite = doc.createElement('canvas');
    sprite.width = 16; sprite.height = 96;
    const ctx = sprite.getContext('2d');
    if (!ctx) return null;
    const shade = ctx.createLinearGradient(0, 0, 0, 96);
    shade.addColorStop(0, 'rgba(41,66,80,0)');
    shade.addColorStop(.64, 'rgba(41,66,80,.2)');
    shade.addColorStop(1, 'rgba(36,60,76,.5)');
    ctx.fillStyle = shade;
    ctx.beginPath(); ctx.moveTo(7, 1); ctx.lineTo(11, 86);
    ctx.quadraticCurveTo(10, 95, 7, 94); ctx.lineTo(5, 87); ctx.closePath(); ctx.fill();
    const light = ctx.createLinearGradient(0, 0, 0, 96);
    light.addColorStop(0, 'rgba(235,246,255,0)');
    light.addColorStop(.5, 'rgba(235,246,255,.28)');
    light.addColorStop(.91, near ? 'rgba(255,255,255,.95)' : 'rgba(243,251,255,.8)');
    light.addColorStop(1, 'rgba(232,246,255,.38)');
    ctx.fillStyle = light;
    ctx.beginPath(); ctx.moveTo(8, 1); ctx.lineTo(9.7, 85);
    ctx.quadraticCurveTo(9, 94, 7.5, 91); ctx.lineTo(6.6, 85); ctx.closePath(); ctx.fill();
    return sprite;
  }
  function snowSprite(doc) {
    const sprite = doc.createElement('canvas'); sprite.width = 24; sprite.height = 24;
    const ctx = sprite.getContext('2d'); if (!ctx) return null;
    const glow = ctx.createRadialGradient(11, 10, 1, 12, 12, 10);
    glow.addColorStop(0, 'rgba(255,255,255,.96)');
    glow.addColorStop(.4, 'rgba(246,251,255,.78)');
    glow.addColorStop(.72, 'rgba(225,238,245,.2)');
    glow.addColorStop(1, 'rgba(225,238,245,0)');
    ctx.fillStyle = glow; ctx.fillRect(0, 0, 24, 24); return sprite;
  }
  function stop(state) {
    if (state.frame !== null) global.cancelAnimationFrame(state.frame);
    state.frame = null; state.previousTime = null;
    if (state.ctx) state.ctx.clearRect(0, 0, state.canvas.width, state.canvas.height);
    state.root.dataset.weatherMotion = 'off';
  }
  function destroy(root) {
    const state = instances.get(root); if (!state) return;
    stop(state); global.clearTimeout(state.expiry);
    state.intersection?.disconnect(); state.resizeObserver?.disconnect(); state.removal?.disconnect();
    state.motion?.removeEventListener?.('change', state.sync);
    state.doc.removeEventListener('visibilitychange', state.sync);
    global.removeEventListener('resize', state.resize);
    global.removeEventListener('scroll', state.onScroll, {capture:true});
    global.removeEventListener('pagehide', state.onPageHide);
    global.removeEventListener('pageshow', state.onPageShow);
    state.canvas?.remove(); instances.delete(root);
  }
  function resetParticles(state) {
    const snow = state.scene.mode === 'snow';
    const intensity = finite(state.scene.intensity) ? clamp(state.scene.intensity, 0, 1) : .28;
    const area = state.width * state.height;
    const count = Math.round(snow ? clamp(area / 1800, 45, 160) * (.5 + intensity * .5) : clamp(area / 1050, 70, 320) * (.2 + intensity * .8));
    const rng = random(0x726f7879 + (snow ? 91 : 7));
    state.random = rng;
    state.particles = Array.from({length:count}, () => {
      const depth = Math.pow(rng(), 1.5), variation = rng();
      return {
        x:rng() * (state.width + 100) - 50, y:rng() * (state.height + 100) - 50,
        depth, speed:snow ? 14 + depth * 39 + variation * 9 : 320 + depth * 650 + variation * 180,
        length:7 + depth * 27 + variation * 9,
        width:.6 + depth * 1.4, alpha:snow ? .4 + depth * .48 : .24 + depth * .48,
        phase:rng() * Math.PI * 2, flutter:.5 + rng() * 1.5,
      };
    });
    // A few small water lenses at the edges suggest wetness, leaving the map's
    // central labels unobscured. No screen-wide blur or invented lightning.
    state.beads = !snow && intensity >= .6 ? Array.from({length:6}, (_, index) => ({
      x:index % 2 ? state.width - 3 - rng() * 24 : 3 + rng() * 24,
      y:rng() * state.height, radius:1.1 + rng() * 2.4,
      speed:.8 + rng() * 3, alpha:.2 + rng() * .16,
    })) : [];
    state.canvas.dataset.particleCount = String(count);
  }
  function resize(state) {
    if (!state.canvas) return;
    const box = state.root.getBoundingClientRect();
    const width = Math.round(box.width), height = Math.round(box.height);
    const dpr = clamp(global.devicePixelRatio || 1, 1, 1.5);
    if (state.width === width && state.height === height && state.dpr === dpr) return;
    state.width = width; state.height = height; state.dpr = dpr;
    state.canvas.width = Math.max(1, Math.round(width * dpr));
    state.canvas.height = Math.max(1, Math.round(height * dpr));
    if (width && height) resetParticles(state);
  }
  function drawBeads(state, dt) {
    const ctx = state.ctx;
    for (const bead of state.beads) {
      bead.y += bead.speed * dt;
      if (bead.y > state.height + 8) bead.y = -8;
      ctx.globalAlpha = bead.alpha;
      ctx.lineWidth = .65; ctx.strokeStyle = 'rgba(36,62,78,.65)';
      ctx.beginPath(); ctx.ellipse(bead.x, bead.y, bead.radius, bead.radius * 1.55, -.08, .2, Math.PI * 1.7); ctx.stroke();
      ctx.strokeStyle = 'rgba(255,255,255,.94)'; ctx.lineWidth = .8;
      ctx.beginPath(); ctx.ellipse(bead.x -.25, bead.y + .65, bead.radius * .72, bead.radius * 1.2, -.08, .1, Math.PI * .85); ctx.stroke();
    }
  }
  function frame(state, time) {
    state.frame = null;
    if (!state.root.isConnected) { destroy(state.root); return; }
    if (!fresh(state.scene)) { destroy(state.root); return; }
    if (state.paused || state.suspended || state.doc.hidden || state.motion?.matches || !state.inView) { stop(state); return; }
    const dt = state.previousTime === null ? 0 : clamp((time - state.previousTime) / 1000, 0, .05);
    state.previousTime = time;
    const ctx = state.ctx, dpr = state.dpr;
    ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.clearRect(0, 0, state.canvas.width, state.canvas.height);
    const snow = state.scene.mode === 'snow';
    const drift = finite(state.scene.drift) ? clamp(state.scene.drift, -132, 132) / 132 : 0;
    const gust = 1 + Math.sin(time * .00063) * .08 + Math.sin(time * .00117) * .04;
    for (const drop of state.particles) {
      const vx = snow ? drift * (12 + drop.depth * 29) * gust + Math.sin(time * .0007 * drop.flutter + drop.phase) * (6 + drop.depth * 14) : drop.speed * drift * .42 * gust;
      drop.x += vx * dt; drop.y += drop.speed * dt;
      if (drop.y > state.height + 55) { drop.y = -55 - state.random() * 50; drop.x = state.random() * (state.width + 120) - 60; }
      if (drop.x > state.width + 65) drop.x = -60;
      else if (drop.x < -65) drop.x = state.width + 60;
      ctx.globalAlpha = drop.alpha;
      if (snow) {
        const size = 2.4 + drop.depth * 7;
        ctx.setTransform(dpr, 0, 0, dpr, drop.x * dpr, drop.y * dpr);
        ctx.drawImage(state.snow, -size / 2, -size / 2, size, size);
      } else {
        const angle = -Math.atan2(vx, drop.speed), cos = Math.cos(angle), sin = Math.sin(angle);
        ctx.setTransform(cos * dpr, sin * dpr, -sin * dpr, cos * dpr, drop.x * dpr, drop.y * dpr);
        ctx.drawImage(state.rain[drop.depth > .65 ? 1 : 0], -drop.width * 2, -drop.length, drop.width * 4, drop.length);
      }
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0); drawBeads(state, dt);
    ctx.globalAlpha = 1; ctx.setTransform(1, 0, 0, 1, 0, 0);
    state.frame = global.requestAnimationFrame(time => frame(state, time));
  }
  function sync(state) {
    if (!state.root.isConnected || !fresh(state.scene)) { destroy(state.root); return; }
    if (state.paused || state.suspended || state.doc.hidden || state.motion?.matches || !state.inView) { stop(state); return; }
    state.root.dataset.weatherMotion = 'on';
    if (state.canvas && state.width && state.height && state.frame === null) {
      state.frame = global.requestAnimationFrame(time => frame(state, time));
    }
  }
  function create(root) {
    const doc = root.ownerDocument;
    const state = {root, doc, scene:null, canvas:null, ctx:null, frame:null, previousTime:null,
      particles:[], beads:[], width:0, height:0, dpr:1, paused:false, inView:insideViewport(root)};
    state.sync = () => sync(state);
    state.resize = () => { resize(state); state.inView = insideViewport(root); sync(state); };
    state.onScroll = () => { state.inView = insideViewport(root); sync(state); };
    state.onPageHide = () => { state.suspended = true; stop(state); };
    state.onPageShow = () => { state.suspended = false; sync(state); };
    state.motion = global.matchMedia?.('(prefers-reduced-motion: reduce)');
    state.motion?.addEventListener?.('change', state.sync);
    doc.addEventListener('visibilitychange', state.sync);
    global.addEventListener('resize', state.resize, {passive:true});
    global.addEventListener('pagehide', state.onPageHide);
    global.addEventListener('pageshow', state.onPageShow);
    if (global.IntersectionObserver) {
      state.intersection = new global.IntersectionObserver(entries => {
        state.inView = entries.some(entry => entry.isIntersecting); sync(state);
      });
      state.intersection.observe(root);
    } else global.addEventListener('scroll', state.onScroll, {passive:true, capture:true});
    if (global.ResizeObserver) {
      state.resizeObserver = new global.ResizeObserver(state.resize); state.resizeObserver.observe(root);
    }
    if (global.MutationObserver && doc.documentElement) {
      state.removal = new global.MutationObserver(() => { if (!root.isConnected) destroy(root); });
      state.removal.observe(doc.documentElement, {childList:true, subtree:true});
    }
    instances.set(root, state); return state;
  }
  function render(root, scene, options = {}) {
    if (!root) return;
    if (!fresh(scene)) { destroy(root); root.dataset.weatherMotion = 'off'; return; }
    const state = instances.get(root) || create(root);
    const oldSignature = state.signature;
    state.scene = {...scene}; state.paused = options.paused === true;
    state.signature = `${scene.mode}:${scene.intensity}`;
    if (wetModes.has(scene.mode) && !state.canvas) {
      const canvas = state.doc.createElement('canvas');
      canvas.className = 'family-weather-canvas'; canvas.setAttribute('aria-hidden', 'true');
      canvas.setAttribute('role', 'presentation');
      const ctx = canvas.getContext('2d', {alpha:true});
      if (!ctx) { destroy(root); root.dataset.weatherMotion = 'off'; return; }
      state.rain = [rainSprite(state.doc, false), rainSprite(state.doc, true)]; state.snow = snowSprite(state.doc);
      if (!state.snow || state.rain.some(sprite => !sprite)) { destroy(root); root.dataset.weatherMotion = 'off'; return; }
      state.canvas = canvas; state.ctx = ctx; root.replaceChildren(canvas); resize(state);
    } else if (!wetModes.has(scene.mode) && state.canvas) {
      stop(state); state.canvas.remove(); state.canvas = null; state.ctx = null;
      state.width = 0; state.height = 0; state.particles = []; state.beads = [];
    }
    if (state.canvas && state.signature !== oldSignature) resetParticles(state);
    global.clearTimeout(state.expiry);
    state.expiry = global.setTimeout(state.sync, Math.max(1, Math.min(scene.validAt, scene.fetchedAt) + 2700000 - Date.now()));
    sync(state);
  }
  global.RoxyWeatherRenderer = Object.freeze({render, destroy});
})(window);
