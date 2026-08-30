(() => {
  'use strict';

  const TOP_OF_MIND_ITEMS = Object.freeze([
    Object.freeze({ kind: 'Priority', text: 'Make the Feelings spectrum readable at a glance.', when: 'Now' }),
    Object.freeze({ kind: 'Thought', text: 'The soul should feel alive — never ornamental.', when: 'Just discussed' }),
    Object.freeze({ kind: 'Update', text: 'The breathing soul now follows all nine feeling bands.', when: 'Updated' }),
    Object.freeze({ kind: 'Decision', text: 'One slender call island. Captions stay in the chat.', when: 'Locked' }),
    Object.freeze({ kind: 'Next', text: 'Give Workers and Cortex full workspaces, not modals.', when: 'Up next' }),
  ]);

  function nextTopOfMindIndex(index, length, direction = 1) {
    const count = Math.max(0, Math.trunc(Number(length) || 0));
    if (!count) return -1;
    const current = Math.trunc(Number(index) || 0);
    const step = direction < 0 ? -1 : 1;
    return ((current + step) % count + count) % count;
  }

  function formatTopOfMindLabel(item, index, total) {
    return `${item.kind}. ${item.text} ${item.when}. Note ${index + 1} of ${total}. Show next note.`;
  }

  function mountTopOfMind(root, { items = TOP_OF_MIND_ITEMS, intervalMs = 6200 } = {}) {
    if (!root?.ownerDocument) throw new TypeError('A Top of mind root element is required.');

    const notes = items.filter((item) => item?.kind && item?.text && item?.when);
    if (!notes.length) throw new TypeError('At least one Top of mind note is required.');

    const ownerDocument = root.ownerDocument;
    const ownerWindow = ownerDocument.defaultView || window;
    const stack = root.querySelector('[data-top-of-mind-stack]');
    const count = root.querySelector('[data-top-of-mind-count]');
    const motionButton = root.querySelector('[data-top-of-mind-motion]');
    const status = root.querySelector('[data-top-of-mind-status]');
    const motionQuery = ownerWindow.matchMedia?.('(prefers-reduced-motion: reduce)');
    const holds = new Set();
    let reducedMotion = motionQuery?.matches === true;
    let autoPlaying = !reducedMotion;
    let index = 0;
    let timer = null;
    let transitioning = false;
    let observer = null;

    if (!stack || !count || !motionButton || !status) {
      throw new TypeError('The Top of mind surface is incomplete.');
    }

    function createCard(item) {
      const card = ownerDocument.createElement('span');
      card.className = 'top-thought-card';
      card.dataset.topOfMindCard = '';
      card.setAttribute('aria-hidden', 'true');

      const meta = ownerDocument.createElement('span');
      meta.className = 'top-thought-meta';
      const kind = ownerDocument.createElement('span');
      kind.className = 'top-thought-kind';
      kind.textContent = item.kind;
      const when = ownerDocument.createElement('span');
      when.textContent = item.when;
      meta.append(kind, when);

      const text = ownerDocument.createElement('strong');
      text.textContent = item.text;
      card.append(meta, text);
      return card;
    }

    function updateChrome({ announce = false } = {}) {
      const item = notes[index];
      count.textContent = `${index + 1} / ${notes.length}`;
      stack.setAttribute('aria-label', formatTopOfMindLabel(item, index, notes.length));
      if (announce) {
        status.textContent = '';
        ownerWindow.setTimeout(() => {
          status.textContent = `${item.kind}: ${item.text}`;
        }, 10);
      }
    }

    function updateMotionControl() {
      root.dataset.reducedMotion = String(reducedMotion);
      motionButton.hidden = reducedMotion;
      motionButton.dataset.motion = autoPlaying ? 'playing' : 'paused';
      motionButton.setAttribute('aria-label', autoPlaying ? 'Pause note rotation' : 'Resume note rotation');
      motionButton.setAttribute('aria-pressed', String(!autoPlaying));
      motionButton.querySelector('[aria-hidden="true"]').textContent = autoPlaying ? 'Ⅱ' : '▶';
    }

    function clearTimer() {
      if (timer === null) return;
      ownerWindow.clearTimeout(timer);
      timer = null;
    }

    function schedule() {
      clearTimer();
      if (!autoPlaying || reducedMotion || transitioning || holds.size) return;
      timer = ownerWindow.setTimeout(async () => {
        await advance(1);
        schedule();
      }, Math.max(4800, intervalMs));
    }

    async function show(nextIndex, { direction = 1, announce = false } = {}) {
      if (transitioning || nextIndex < 0 || nextIndex === index) return false;
      transitioning = true;
      clearTimer();

      const outgoing = stack.querySelector('[data-top-of-mind-card]');
      const incoming = createCard(notes[nextIndex]);
      index = nextIndex;
      updateChrome({ announce });

      if (reducedMotion || typeof incoming.animate !== 'function') {
        outgoing.replaceWith(incoming);
        transitioning = false;
        schedule();
        return true;
      }

      const travel = direction < 0 ? -1 : 1;
      incoming.style.zIndex = '3';
      outgoing.style.zIndex = '4';
      stack.appendChild(incoming);

      const outgoingAnimation = outgoing.animate(
        [
          { opacity: 1, transform: 'translate3d(0, 0, 0) rotate(0deg)' },
          { opacity: 0, transform: `translate3d(${-34 * travel}%, -8%, 0) rotate(${-5 * travel}deg)` },
        ],
        { duration: 420, easing: 'cubic-bezier(0.4, 0, 1, 1)', fill: 'forwards' },
      );
      const incomingAnimation = incoming.animate(
        [
          { opacity: 0, transform: `translate3d(${38 * travel}%, 10%, 0) rotate(${6 * travel}deg)` },
          { opacity: 1, transform: 'translate3d(0, 0, 0) rotate(0deg)' },
        ],
        { duration: 560, easing: 'cubic-bezier(0.16, 1, 0.3, 1)', fill: 'forwards' },
      );

      await Promise.allSettled([outgoingAnimation.finished, incomingAnimation.finished]);
      outgoing.remove();
      incomingAnimation.cancel();
      incoming.style.removeProperty('z-index');
      transitioning = false;
      schedule();
      return true;
    }

    function advance(direction = 1, { announce = false } = {}) {
      return show(nextTopOfMindIndex(index, notes.length, direction), { direction, announce });
    }

    function setHold(reason, held) {
      if (held) holds.add(reason);
      else holds.delete(reason);
      schedule();
    }

    function onMotionChange(event) {
      reducedMotion = event.matches;
      autoPlaying = !reducedMotion;
      updateMotionControl();
      schedule();
    }

    stack.replaceChildren(createCard(notes[index]));
    updateChrome();
    updateMotionControl();

    stack.addEventListener('click', () => {
      void advance(1, { announce: true });
    });
    stack.addEventListener('keydown', (event) => {
      if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
      event.preventDefault();
      void advance(event.key === 'ArrowLeft' ? -1 : 1, { announce: true });
    });
    motionButton.addEventListener('click', () => {
      autoPlaying = !autoPlaying;
      if (autoPlaying) {
        holds.delete('focus');
        holds.delete('pointer');
      }
      updateMotionControl();
      schedule();
    });
    root.addEventListener('pointerenter', () => setHold('pointer', true));
    root.addEventListener('pointerleave', () => setHold('pointer', false));
    root.addEventListener('focusin', () => setHold('focus', true));
    root.addEventListener('focusout', (event) => {
      if (!root.contains(event.relatedTarget)) setHold('focus', false);
    });
    ownerDocument.addEventListener('visibilitychange', () => setHold('page', ownerDocument.hidden));
    motionQuery?.addEventListener?.('change', onMotionChange);

    if (typeof ownerWindow.IntersectionObserver === 'function') {
      observer = new ownerWindow.IntersectionObserver(([entry]) => {
        setHold('surface', !entry?.isIntersecting);
      }, { threshold: 0.12 });
      observer.observe(root);
    }

    schedule();

    return Object.freeze({
      advance,
      pause: (reason = 'external') => setHold(reason, true),
      resume: (reason = 'external') => setHold(reason, false),
      getIndex: () => index,
      destroy: () => {
        clearTimer();
        observer?.disconnect();
        motionQuery?.removeEventListener?.('change', onMotionChange);
      },
    });
  }

  window.ViventiumTopOfMind = Object.freeze({
    TOP_OF_MIND_ITEMS,
    formatTopOfMindLabel,
    mountTopOfMind,
    nextTopOfMindIndex,
  });
})();
