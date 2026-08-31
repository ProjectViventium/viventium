(() => {
  'use strict';

  const TAU = Math.PI * 2;
  const SOUL_MODES = Object.freeze([
    'resting',
    'attending',
    'thinking',
    'reacting',
    'settling',
    'paused',
    'off',
  ]);

  const clamp = (value, min = 0, max = 1) => Math.min(max, Math.max(min, value));
  const lerp = (from, to, amount) => from + (to - from) * amount;

  function bandValue(bands, id, fallback = 0.5) {
    const band = bands.find((candidate) => candidate.id === id && candidate.enabled !== false);
    const value = Number(band?.current);
    return Number.isFinite(value) ? clamp(value / 100) : fallback;
  }

  function deriveSoulMetrics(bands = []) {
    const energy = bandValue(bands, 'energy');
    const mood = bandValue(bands, 'mood');
    const drive = bandValue(bands, 'drive');
    const curiosity = bandValue(bands, 'curiosity');
    const vigilance = bandValue(bands, 'vigilance');
    const care = bandValue(bands, 'care');
    const connection = bandValue(bands, 'connection');
    const openness = bandValue(bands, 'openness');
    const play = bandValue(bands, 'play');

    return Object.freeze({
      energy,
      mood,
      drive,
      curiosity,
      vigilance,
      care,
      connection,
      openness,
      play,
      breathHz: lerp(0.14, 0.29, energy),
      breathDepth: lerp(0.038, 0.112, energy),
      aura: lerp(0.1, 0.34, care),
      auraSpread: lerp(0.06, 0.2, openness),
      reach: lerp(0.1, 1, curiosity),
      edgeTension: lerp(0.12, 1, vigilance),
      irregularity: lerp(0.05, 1, play),
      cohesion: lerp(0.35, 1, connection),
      lean: lerp(-0.7, 0.9, drive),
      lift: lerp(0.85, -0.85, mood),
      tone: mood,
    });
  }

  function resolveSoulMode({
    power = true,
    paused = false,
    replyPending = false,
    callActive = false,
    callMuted = false,
    attention = false,
  } = {}) {
    if (!power) return 'off';
    if (paused) return 'paused';
    if (replyPending) return 'thinking';
    if ((callActive && !callMuted) || attention) return 'attending';
    return 'resting';
  }

  function modeShape(mode, progress) {
    const eased = 0.5 - Math.cos(clamp(progress) * Math.PI) / 2;
    switch (mode) {
      case 'attending':
        return { pace: 1.08, scale: 0.985, depth: 0.82, reach: 1.16, tension: 1.08 };
      case 'thinking':
        return { pace: 1.34, scale: 0.92, depth: 0.48, reach: 0.78, tension: 1.34 };
      case 'reacting':
        return { pace: 1.22, scale: 1 + Math.sin(eased * Math.PI) * 0.12, depth: 1.28, reach: 1.18, tension: 0.84 };
      case 'settling':
        return { pace: 0.92, scale: 1 + (1 - eased) * 0.06, depth: 0.7 + eased * 0.3, reach: 1, tension: 0.9 + eased * 0.1 };
      case 'paused':
        return { pace: 0, scale: 0.98, depth: 0, reach: 0.9, tension: 1.1 };
      case 'off':
        return { pace: 0, scale: 0.88, depth: 0, reach: 0.7, tension: 1.2 };
      default:
        return { pace: 1, scale: 1, depth: 1, reach: 1, tension: 1 };
    }
  }

  function splinePath(points) {
    const count = points.length;
    const first = points[0];
    let path = `M ${first.x.toFixed(2)} ${first.y.toFixed(2)}`;

    for (let index = 0; index < count; index += 1) {
      const previous = points[(index - 1 + count) % count];
      const current = points[index];
      const next = points[(index + 1) % count];
      const after = points[(index + 2) % count];
      const controlOne = {
        x: current.x + (next.x - previous.x) / 6,
        y: current.y + (next.y - previous.y) / 6,
      };
      const controlTwo = {
        x: next.x - (after.x - current.x) / 6,
        y: next.y - (after.y - current.y) / 6,
      };
      path += ` C ${controlOne.x.toFixed(2)} ${controlOne.y.toFixed(2)}, ${controlTwo.x.toFixed(2)} ${controlTwo.y.toFixed(2)}, ${next.x.toFixed(2)} ${next.y.toFixed(2)}`;
    }

    return `${path} Z`;
  }

  function createSoulPath(metrics, timeMs = 0, mode = 'resting', progress = 0) {
    const modeConfig = modeShape(mode, progress);
    const time = timeMs / 1000;
    const phase = modeConfig.pace === 0 ? 0 : time * metrics.breathHz * TAU * modeConfig.pace;
    const breath = Math.sin(phase - Math.PI / 2) * metrics.breathDepth * modeConfig.depth;
    const pointCount = 16;
    const centerX = 32 + metrics.lean * 0.42 + (mode === 'attending' ? 0.5 : 0);
    const centerY = 32 + metrics.lift * 0.35 + (mode === 'attending' ? 0.6 : 0);
    const baseRadius = 21.4 * modeConfig.scale;
    const points = [];

    for (let index = 0; index < pointCount; index += 1) {
      const angle = (index / pointCount) * TAU - Math.PI / 2;
      const upperReach = Math.max(0, -Math.sin(angle)) * metrics.reach * modeConfig.reach * 1.35;
      const pairedLobe = Math.sin(angle * 2 + phase * 0.32) * lerp(0.64, 1.42, metrics.cohesion);
      const playfulEdge = Math.sin(angle * 3 - phase * 0.46) * metrics.irregularity * 0.92;
      const alertEdge = Math.sin(angle * 5 + phase * 1.3) * metrics.edgeTension * modeConfig.tension * 0.17;
      const thinkingDraw = mode === 'thinking' ? Math.cos(angle - phase * 0.38) * 0.72 : 0;
      const radius = baseRadius * (1 + breath)
        + pairedLobe
        + playfulEdge
        + alertEdge
        + upperReach
        + thinkingDraw;
      const horizontalBias = Math.cos(angle) * metrics.lean * 0.2;
      const horizontalScale = 0.84 + metrics.connection * 0.07;
      const verticalScale = 1.045 + metrics.curiosity * 0.035;

      points.push({
        x: centerX + Math.cos(angle) * radius * horizontalScale + horizontalBias,
        y: centerY + Math.sin(angle) * radius * verticalScale,
      });
    }

    return splinePath(points);
  }

  let soulSequence = 0;

  function mountSoul(root, {
    getBands = () => [],
    getState = () => ({}),
    onStateChange = () => {},
  } = {}) {
    if (!root?.ownerDocument) throw new TypeError('A soul root element is required.');

    const ownerWindow = root.ownerDocument.defaultView || window;
    const soulId = `viventium-soul-${soulSequence += 1}`;
    const fillId = `${soulId}-fill`;
    const auraId = `${soulId}-aura`;
    const depthId = `${soulId}-depth`;

    root.innerHTML = `
      <svg class="soul-canvas" viewBox="0 0 64 64" focusable="false" aria-hidden="true">
        <defs>
          <radialGradient id="${fillId}" cx="44%" cy="40%" r="70%">
            <stop class="soul-stop-light" offset="0%" />
            <stop class="soul-stop-body" offset="43%" />
            <stop class="soul-stop-edge" offset="100%" />
          </radialGradient>
          <filter id="${auraId}" x="-60%" y="-60%" width="220%" height="220%">
            <feGaussianBlur stdDeviation="3.6" />
          </filter>
          <filter id="${depthId}" x="-45%" y="-45%" width="190%" height="190%">
            <feDropShadow dx="0" dy="1" stdDeviation="1.6" flood-color="var(--soul-color)" flood-opacity="0.28" />
          </filter>
        </defs>
        <path class="soul-aura" filter="url(#${auraId})" />
        <path class="soul-body" fill="url(#${fillId})" filter="url(#${depthId})" />
        <ellipse class="soul-core" />
        <circle class="soul-response" cx="32" cy="32" r="15" />
      </svg>`;

    const aura = root.querySelector('.soul-aura');
    const body = root.querySelector('.soul-body');
    const core = root.querySelector('.soul-core');
    const response = root.querySelector('.soul-response');
    const motionQuery = ownerWindow.matchMedia?.('(prefers-reduced-motion: reduce)');
    let reducedMotion = motionQuery?.matches === true;
    let animationFrame = null;
    let lastFrame = -Infinity;
    let lastMode = '';
    let attention = false;
    let reaction = null;
    let responseAnimation = null;

    function now() {
      return ownerWindow.performance?.now?.() ?? Date.now();
    }

    function reactionState(time) {
      if (!reaction) return null;
      const elapsed = time - reaction.startedAt;
      if (elapsed < reaction.arrivalMs) {
        return { mode: 'reacting', progress: clamp(elapsed / reaction.arrivalMs) };
      }
      if (elapsed < reaction.arrivalMs + reaction.settleMs) {
        return {
          mode: 'settling',
          progress: clamp((elapsed - reaction.arrivalMs) / reaction.settleMs),
        };
      }
      reaction = null;
      return null;
    }

    function resolvedState(time) {
      const systemState = { ...getState(), attention };
      const baseMode = resolveSoulMode(systemState);
      if (baseMode === 'off' || baseMode === 'paused' || baseMode === 'thinking') {
        return { mode: baseMode, progress: 0 };
      }
      return reactionState(time) || { mode: baseMode, progress: 0 };
    }

    function render(time, force = false) {
      if (!force && time - lastFrame < 32) return;
      lastFrame = time;

      const metrics = deriveSoulMetrics(getBands());
      const { mode, progress } = resolvedState(time);
      const motionTime = reducedMotion || mode === 'paused' || mode === 'off' ? 0 : time;
      const path = createSoulPath(metrics, motionTime, mode, progress);
      const breath = reducedMotion
        ? 0
        : Math.sin((motionTime / 1000) * metrics.breathHz * TAU) * metrics.breathDepth;
      const reactionLift = mode === 'reacting' ? Math.sin(progress * Math.PI) : 0;
      const coreX = 32 + metrics.lean * 0.5 + (mode === 'thinking' ? Math.sin(time / 260) * 0.9 : 0);
      const coreY = 32 + metrics.lift * 0.42 + (mode === 'attending' ? 1.1 : 0);
      const coreRadius = mode === 'off'
        ? 2
        : (4.6 + metrics.energy * 1.8 + breath * 3.4 + reactionLift * 1.2);
      const hue = Math.round(166 - metrics.tone * 10);
      const saturation = Math.round(58 + metrics.tone * 18);
      const lightness = Math.round(38 + metrics.tone * 10);
      const modeOpacity = mode === 'off' ? 0.2 : mode === 'paused' ? 0.58 : 0.96;
      const auraOpacity = mode === 'off'
        ? 0.025
        : mode === 'paused'
          ? metrics.aura * 0.32
          : metrics.aura + reactionLift * 0.12;

      aura.setAttribute('d', path);
      body.setAttribute('d', path);
      core.setAttribute('cx', coreX.toFixed(2));
      core.setAttribute('cy', coreY.toFixed(2));
      core.setAttribute('rx', Math.max(1.2, coreRadius * 0.72).toFixed(2));
      core.setAttribute('ry', Math.max(1.5, coreRadius).toFixed(2));
      root.style.setProperty('--soul-color', `hsl(${hue} ${saturation}% ${lightness}%)`);
      root.style.setProperty('--soul-aura-opacity', auraOpacity.toFixed(3));
      root.style.setProperty('--soul-aura-scale', (1.04 + metrics.auraSpread + reactionLift * 0.06).toFixed(3));
      root.style.setProperty('--soul-body-opacity', modeOpacity.toFixed(2));
      root.style.setProperty('--soul-core-opacity', mode === 'off' ? '0.08' : mode === 'paused' ? '0.48' : '0.92');
      root.dataset.soulState = mode;

      if (mode !== lastMode) {
        lastMode = mode;
        onStateChange(mode);
      }
    }

    function loop(time) {
      if (!root.isConnected) return;
      render(time);
      animationFrame = ownerWindow.requestAnimationFrame(loop);
    }

    function sync() {
      render(now(), true);
      if (!reducedMotion && animationFrame === null) {
        animationFrame = ownerWindow.requestAnimationFrame(loop);
      }
    }

    function react() {
      const systemMode = resolveSoulMode({ ...getState(), attention });
      if (systemMode === 'off' || systemMode === 'paused') return;
      reaction = { startedAt: now(), arrivalMs: 720, settleMs: 1680 };
      if (!reducedMotion && typeof response.animate === 'function') {
        responseAnimation?.cancel();
        responseAnimation = response.animate(
          [
            { opacity: 0.42, transform: 'scale(0.62)' },
            { opacity: 0.14, offset: 0.42, transform: 'scale(1)' },
            { opacity: 0, transform: 'scale(1.34)' },
          ],
          { duration: 920, easing: 'cubic-bezier(0.16, 0.8, 0.25, 1)' },
        );
      }
      sync();
    }

    function setAttention(nextAttention) {
      attention = Boolean(nextAttention);
      sync();
    }

    function handleMotionPreference(event) {
      reducedMotion = event.matches;
      if (reducedMotion && animationFrame !== null) {
        ownerWindow.cancelAnimationFrame(animationFrame);
        animationFrame = null;
      }
      sync();
    }

    function handleVisibility() {
      if (root.ownerDocument.hidden && animationFrame !== null) {
        ownerWindow.cancelAnimationFrame(animationFrame);
        animationFrame = null;
        return;
      }
      sync();
    }

    motionQuery?.addEventListener?.('change', handleMotionPreference);
    root.ownerDocument.addEventListener('visibilitychange', handleVisibility);
    sync();

    return {
      react,
      setAttention,
      sync,
      destroy() {
        if (animationFrame !== null) ownerWindow.cancelAnimationFrame(animationFrame);
        responseAnimation?.cancel();
        motionQuery?.removeEventListener?.('change', handleMotionPreference);
        root.ownerDocument.removeEventListener('visibilitychange', handleVisibility);
      },
    };
  }

  window.ViventiumSoul = {
    SOUL_MODES,
    createSoulPath,
    deriveSoulMetrics,
    mountSoul,
    resolveSoulMode,
  };
})();
