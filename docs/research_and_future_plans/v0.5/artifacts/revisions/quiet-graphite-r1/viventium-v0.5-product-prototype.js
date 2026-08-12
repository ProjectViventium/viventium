(() => {
  "use strict";

  const STORE_KEY = "viventium-v05-quiet-graphite-candidate-v2";
  const BRAND = "assets/brands/";
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const escapeHTML = (value) => String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);

  const feelingSeed = [
    { id: "energy", name: "Energy", color: "#e0a04b", low: "Spent", high: "Electric", now: 64, nature: 56, halfLife: 150, words: ["still", "low", "steady", "alive", "electric"] },
    { id: "mood", name: "Mood", color: "#d06b85", low: "Heavy", high: "Bright", now: 58, nature: 62, halfLife: 240, words: ["heavy", "somber", "even", "warm", "bright"] },
    { id: "drive", name: "Drive", color: "#cc675a", low: "Resting", high: "Relentless", now: 72, nature: 66, halfLife: 180, words: ["resting", "unhurried", "ready", "driven", "relentless"] },
    { id: "curiosity", name: "Curiosity", color: "#8e79c7", low: "Settled", high: "Fascinated", now: 79, nature: 72, halfLife: 360, words: ["settled", "open", "interested", "absorbed", "fascinated"] },
    { id: "vigilance", name: "Vigilance", color: "#5d8dc7", low: "Trusting", high: "Alert", now: 74, nature: 48, halfLife: 90, words: ["trusting", "relaxed", "aware", "watchful", "alert"] },
    { id: "care", name: "Care", color: "#ce7698", low: "Detached", high: "Tender", now: 84, nature: 78, halfLife: 480, words: ["detached", "measured", "present", "caring", "tender"] },
    { id: "connection", name: "Connection", color: "#4e9b91", low: "Distant", high: "Close", now: 68, nature: 64, halfLife: 300, words: ["distant", "reserved", "with you", "close", "bonded"] },
    { id: "openness", name: "Openness", color: "#6685b8", low: "Guarded", high: "Exposed", now: 61, nature: 58, halfLife: 210, words: ["guarded", "careful", "receptive", "open", "exposed"] },
    { id: "play", name: "Play", color: "#b18745", low: "Serious", high: "Mischievous", now: 42, nature: 48, halfLife: 120, words: ["serious", "dry", "light", "playful", "mischievous"] },
  ];

  const rangeCopy = {
    energy: ["Conserving what remains.", "Moving carefully.", "Enough energy to stay present.", "Momentum is carrying the moment.", "Everything feels charged."],
    mood: ["The moment lands with weight.", "A quiet gravity remains.", "Emotion is balanced and clear.", "A gentle lift colors the response.", "The moment feels genuinely bright."],
    drive: ["Nothing needs to be forced.", "Holding without pushing.", "Ready to move when it matters.", "The goal has a strong pull.", "The urge to finish is uncompromising."],
    curiosity: ["The question feels complete.", "There may be more here.", "The unknown is worth opening.", "Several possibilities are pulling focus.", "The pattern is too compelling to leave alone."],
    vigilance: ["The situation feels safe.", "No threat, but still listening.", "Uncertainty is visible.", "Contradictions deserve attention.", "Risk is immediate and cannot be softened."],
    care: ["Distance protects clear judgment.", "Care is present but contained.", "The person and the truth both matter.", "The response should land gently.", "Protecting the person feels essential."],
    connection: ["The moment is impersonal.", "A little distance remains.", "We are in this together.", "Shared history is active here.", "The bond itself shapes the response."],
    openness: ["Boundaries need to stay firm.", "Only what is useful should surface.", "The exchange feels safe enough.", "Honesty can be unusually direct.", "Very little needs to be held back."],
    play: ["The moment calls for seriousness.", "A dry edge is enough.", "There is room to breathe.", "A little mischief makes this better.", "The moment wants full irreverence."],
  };

  const profileSeeds = [
    { id: "grounded", name: "Grounded", copy: "Steady, candid, caring, and hard to knock off center.", values: [56, 62, 66, 72, 48, 78, 64, 58, 48] },
    { id: "candid", name: "Candid", copy: "Direct, watchful, open, and less inclined to soften truth.", values: [61, 55, 74, 68, 66, 64, 52, 72, 35] },
    { id: "warm", name: "Warm", copy: "Present, expressive, close, and generous with care.", values: [66, 72, 61, 68, 42, 88, 82, 69, 57] },
    { id: "curious", name: "Curious", copy: "Exploratory, energetic, open, and easily fascinated.", values: [72, 67, 69, 91, 52, 70, 61, 79, 68] },
  ];

  const aiSources = [
    { id: "openai", name: "OpenAI", note: "Main thinking + cortices", account: "Connected", detail: "Frontier model", logo: "openai.svg", connected: true, enabled: true, required: true },
    { id: "anthropic", name: "Anthropic", note: "Main thinking + cortices · optional", account: "Not connected", detail: "Claude", logo: "claude.svg", connected: false, enabled: false },
    { id: "xai", name: "xAI", note: "Main thinking + cortices · optional", account: "Not connected", detail: "Grok", logo: "xai.svg", connected: false, enabled: false },
    { id: "groq", name: "Groq", note: "Activation detection · required", account: "Connect to finish setup", detail: "Fast wake-up decisions", logo: "groq.png", connected: false, enabled: false, required: true, attention: true },
  ];

  const reachSources = [
    { id: "telegram", name: "Telegram", note: "Message and voice", account: "@viventium_demo", detail: "Connected", logo: "telegram.svg", connected: true, enabled: true },
    { id: "anywhere", name: "Use from anywhere", note: "Reach this Viventium on another device", account: "Available", detail: "", logo: "anywhere.svg", connected: false, enabled: false },
  ];

  const lifeSources = [
    { group: "Communications", id: "gmail", name: "Email", note: "Messages and attachments", account: "you@example.com", detail: "Chrome · confirmed", logo: "gmail.svg", connected: true, enabled: true, email: true },
    { group: "Calendars", id: "calendar", name: "Calendar", note: "Plans, meetings, and time", account: "Not connected", detail: "", logo: "google-calendar.svg", connected: false, enabled: false },
    { group: "Notetakers", id: "granola", name: "Granola", note: "Meeting notes", account: "Not connected", detail: "", logo: "granola.svg", connected: false, enabled: false },
    { group: "Socials", id: "linkedin", name: "LinkedIn", note: "Your profile and activity", account: "Confirm your username", detail: "", logo: "linkedin.svg", connected: false, enabled: false, username: true },
    { group: "Socials", id: "instagram", name: "Instagram", note: "Your profile and activity", account: "Confirm your username", detail: "", logo: "instagram.svg", connected: false, enabled: false, username: true },
    { group: "Socials", id: "youtube", name: "YouTube", note: "Your channel and viewing", account: "Not connected", detail: "", logo: "youtube.svg", connected: false, enabled: false, username: true },
    { group: "Health", id: "whoop", name: "WHOOP", note: "Recovery and strain", account: "Not connected", detail: "", wordmark: "WHOOP", markClass: "whoop", connected: false, enabled: false },
    { group: "Health", id: "oura", name: "Oura", note: "Sleep and readiness", account: "Not connected", detail: "", wordmark: "OURA", markClass: "oura", connected: false, enabled: false },
    { group: "Photos & videos", id: "icloud", name: "iCloud Photos", note: "Your photo library", account: "Not connected", detail: "", logo: "icloud.svg", connected: false, enabled: false },
    { group: "Photos & videos", id: "googlephotos", name: "Google Photos", note: "Your photo library", account: "Not connected", detail: "", logo: "google-photos.svg", connected: false, enabled: false },
  ];

  const voices = [
    { id: "katie", name: "Katie", provider: "Cartesia", feel: "Expressive" },
    { id: "james", name: "James", provider: "Cartesia", feel: "Grounded" },
    { id: "river", name: "River", provider: "OpenAI", feel: "Natural" },
    { id: "local", name: "Local voice", provider: "Kokoro", feel: "Private" },
  ];

  const automations = [
    { id: "sleep", icon: "☾", name: "Sleep Growth", summary: "Organizes the day and finds what changed.", next: "Tonight · 2:00 AM", last: "This morning", result: "3 insights · Life updated", enabled: true },
    { id: "brief", icon: "⌁", name: "Morning Brief", summary: "The few things worth carrying into today.", next: "Tomorrow · 7:30 AM", last: "Today · 7:31 AM", result: "Delivered in Telegram", enabled: true },
    { id: "glasshive", icon: "◇", name: "GlassHive workers", summary: "Long-running work with mutual context and a clean handoff.", next: "When Viventium needs it", last: "Yesterday · 11:42 PM", result: "Evidence review completed", enabled: true },
    { id: "life-sync", icon: "↻", name: "Life Sync", summary: "Keeps enabled sources organized in Life.", next: "In 38 minutes", last: "12 minutes ago", result: "4 sources current", enabled: true },
  ];

  const defaults = {
    theme: "system", view: "mind", channel: "here", sourceFilter: "all", voice: "katie",
    presence: { in: true, muted: false, mode: "direct" }, feelingsEnabled: true,
    profile: "grounded", openLane: null, selectedRanges: {}, sourceOverrides: {},
    feelings: Object.fromEntries(feelingSeed.map((f) => [f.id, { now: f.now, nature: f.nature, halfLife: f.halfLife, included: true, additions: {} }])),
    selectedAutomation: "sleep", automationOverrides: {},
  };

  function loadState() {
    try {
      const stored = JSON.parse(localStorage.getItem(STORE_KEY) || "{}");
      return {
        ...structuredClone(defaults), ...stored,
        presence: { ...defaults.presence, ...(stored.presence || {}) },
        sourceOverrides: stored.sourceOverrides || {}, selectedRanges: stored.selectedRanges || {},
        automationOverrides: stored.automationOverrides || {},
        feelings: Object.fromEntries(feelingSeed.map((f) => [f.id, { ...defaults.feelings[f.id], ...((stored.feelings || {})[f.id] || {}) }])),
      };
    } catch { return structuredClone(defaults); }
  }

  let state = loadState();
  let toastTimer;
  let activeDialogSource = null;
  const persist = () => { try { localStorage.setItem(STORE_KEY, JSON.stringify(state)); } catch { /* local artifact */ } };

  function showToast(message) {
    const toast = $("#toast");
    toast.textContent = message;
    toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("show"), 2300);
  }

  function logoMarkup(source) {
    if (source.logo) return `<span class="connection-logo"><img src="${BRAND}${source.logo}" alt=""></span>`;
    return `<span class="connection-logo wordmark ${escapeHTML(source.markClass || "")}">${escapeHTML(source.wordmark || source.name.slice(0, 1))}</span>`;
  }

  const liveSource = (source) => ({ ...source, ...(state.sourceOverrides[source.id] || {}) });

  function renderSourceRows(container, sources, grouped = false) {
    const root = $(container);
    let lastGroup = "";
    const filtered = sources.map(liveSource).filter((source) => {
      if (state.sourceFilter === "connected") return source.enabled;
      if (state.sourceFilter === "attention") return !source.connected || source.attention;
      return true;
    });
    if (!filtered.length) {
      root.innerHTML = '<div class="empty-filter">Nothing here needs attention.</div>';
      return;
    }
    root.innerHTML = filtered.map((source) => {
      const group = grouped && source.group !== lastGroup ? `<div class="connection-group-label">${escapeHTML(source.group)}</div>` : "";
      lastGroup = source.group || lastGroup;
      const needs = !source.connected || source.attention;
      return `${group}<div class="connection-row" data-source-id="${source.id}">
        ${logoMarkup(source)}
        <div class="connection-copy"><b>${escapeHTML(source.name)}</b><small>${escapeHTML(source.note)}</small></div>
        <div class="connection-account"><b class="${needs ? "needs" : ""}">${escapeHTML(source.account)}</b>${source.detail ? `<small>${escapeHTML(source.detail)}</small>` : ""}</div>
        <button class="connect-action ${source.required && !source.connected ? "primary" : ""}" type="button" data-connect="${source.id}">${source.connected ? "Change" : "Connect"}</button>
        <label class="switch" aria-label="Enable ${escapeHTML(source.name)}"><input type="checkbox" data-source-toggle="${source.id}" ${source.enabled ? "checked" : ""} ${!source.connected ? "disabled" : ""}><i></i></label>
      </div>`;
    }).join("");
  }

  function renderConnections() {
    renderSourceRows("#aiConnections", aiSources);
    renderSourceRows("#reachConnections", reachSources);
    renderSourceRows("#lifeConnections", lifeSources, true);
    const mainReady = aiSources.map(liveSource).some((source) => ["openai", "anthropic", "xai"].includes(source.id) && source.connected && source.enabled);
    const groqReady = liveSource(aiSources.find((source) => source.id === "groq")).connected;
    const count = Number(mainReady) + Number(groqReady);
    const readiness = $("#aiReadiness");
    readiness.innerHTML = `<i></i> ${count} of 2 ready`;
    readiness.classList.toggle("ready", count === 2);
  }

  function feelingWord(feeling, value) {
    return feeling.words[Math.min(4, Math.floor(Math.max(0, Math.min(99, value)) / 20))];
  }

  function renderMindFeelings() {
    $("#mindFeelings").innerHTML = feelingSeed.map((feeling) => {
      const current = state.feelings[feeling.id].now;
      return `<div class="mind-feeling" style="--band:${feeling.color}"><span>${feeling.name}</span><div class="mini-track" style="--value:${current}"></div><b>${current}</b></div>`;
    }).join("");
  }

  function renderFeelingLanes() {
    $("#feelingLanes").innerHTML = feelingSeed.map((feeling) => {
      const values = state.feelings[feeling.id];
      const selected = state.selectedRanges[feeling.id] ?? Math.min(4, Math.floor(values.now / 20));
      const detailOpen = state.openLane === feeling.id;
      const tabs = feeling.words.map((word, index) => `<button class="${selected === index ? "active" : ""}" type="button" data-range="${feeling.id}:${index}"><b>${escapeHTML(word)}</b><small>${index * 20}–${index === 4 ? 100 : index * 20 + 19}</small></button>`).join("");
      const addition = values.additions?.[selected] || "";
      return `<article class="feeling-lane" data-feeling="${feeling.id}" style="--band:${feeling.color}">
        <div class="lane-main">
          <div class="lane-label"><b>${feeling.name}</b><small>${feelingWord(feeling, values.now)} · ${rangeCopy[feeling.id][selected]}</small></div>
          <div class="dual-slider" style="--now:${values.now}%;--nature:${values.nature}%">
            <input class="now-slider" type="range" min="0" max="100" value="${values.now}" data-feeling-slider="${feeling.id}:now" aria-label="${feeling.name} now">
            <input class="nature-slider" type="range" min="0" max="100" value="${values.nature}" data-feeling-slider="${feeling.id}:nature" aria-label="${feeling.name} nature">
            <div class="slider-poles"><span>${feeling.low}</span><span>${feeling.high}</span></div>
          </div>
          <div class="lane-values"><span>Now<b>${values.now}</b></span><span>Nature<b>${values.nature}</b></span><small>${feelingWord(feeling, values.now)}${values.now !== values.nature ? " · shifted" : " · at nature"}</small></div>
          <button class="lane-more" type="button" data-lane-more="${feeling.id}" aria-expanded="${detailOpen}" aria-label="More ${feeling.name} options"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 10 5 5 5-5"/></svg></button>
        </div>
        ${detailOpen ? `<div class="lane-detail">
          <div class="lane-controls">
            <div class="lane-control"><label for="nature-${feeling.id}">Nature</label><div class="number-with-action"><input id="nature-${feeling.id}" type="number" min="0" max="100" value="${values.nature}" data-number-setting="${feeling.id}:nature"><button type="button" data-reset-lane="${feeling.id}">Reset lane</button></div></div>
            <div class="lane-control"><label for="half-${feeling.id}">Return speed · half-life (minutes)</label><input id="half-${feeling.id}" type="number" min="1" value="${values.halfLife}" data-number-setting="${feeling.id}:halfLife"></div>
            <label class="lane-control inline-switch"><span>Include lane</span><span class="switch"><input type="checkbox" data-include-lane="${feeling.id}" ${values.included ? "checked" : ""}><i></i></span></label>
          </div>
          <div class="range-editor"><label>Five stable ranges</label><div class="range-tabs">${tabs}</div><div class="range-cause">${escapeHTML(rangeCopy[feeling.id][selected])}</div>
            <label for="addition-${feeling.id}">Optional addition</label><textarea id="addition-${feeling.id}" rows="2" data-range-addition="${feeling.id}:${selected}" placeholder="Add nuance for this range">${escapeHTML(addition)}</textarea>
            <div class="range-actions"><button type="button" data-clear-range="${feeling.id}:${selected}">Clear</button><button class="save-range" type="button" data-save-range="${feeling.id}:${selected}">Save</button></div>
          </div>
        </div>` : ""}
      </article>`;
    }).join("");
  }

  function renderProfiles() {
    $("#profileChoices").innerHTML = profileSeeds.map((profile) => `<button class="profile-choice ${state.profile === profile.id ? "active" : ""}" type="button" data-profile="${profile.id}"><b>${profile.name}</b><small>${profile.copy}</small>${state.profile === profile.id ? "<em>Current nature</em>" : ""}</button>`).join("");
    const active = profileSeeds.find((profile) => profile.id === state.profile);
    $("#activeProfileName").textContent = active?.name || "Custom";
  }

  function renderReactions() {
    const rows = [
      ["Just now", "Vigilance", "+26", "New uncertainty · clear shift"],
      ["3 minutes ago", "Care", "+8", "A hard truth needed a softer landing"],
      ["Yesterday", "Play", "−11", "The stakes became real"],
      ["Yesterday", "Curiosity", "+17", "A contradiction opened a new path"],
    ];
    $("#reactionList").innerHTML = rows.map(([time, band, delta, reason]) => `<div class="reaction-row"><time>${time}</time><div><b>${band} ${delta}</b><small>${reason}</small></div><em class="${delta.startsWith("−") ? "down" : ""}">${delta.startsWith("−") ? "Eased" : "Moved"}</em></div>`).join("");
  }

  function renderVoiceMenu() {
    const selected = voices.find((voice) => voice.id === state.voice) || voices[0];
    $("#voiceName").textContent = selected.name;
    $("#voiceProvider").textContent = `${selected.provider} · ${selected.feel.toLowerCase()}`;
    $("#voiceMenu").innerHTML = `${voices.map((voice) => `<button type="button" role="option" aria-selected="${voice.id === selected.id}" data-voice="${voice.id}"><span><b>${voice.name}</b><small>${voice.provider} · ${voice.feel}</small></span>${voice.id === selected.id ? "<em>Selected</em>" : ""}</button>`).join("")}<button class="voice-create" type="button" data-toast="Voice creation would open here"><span><b>Create a voice</b><small>Train or import</small></span><em>＋</em></button>`;
  }

  function renderAutomations() {
    const withState = automations.map((item) => ({ ...item, ...(state.automationOverrides[item.id] || {}) }));
    $("#automationList").innerHTML = withState.map((item) => `<div class="automation-row ${state.selectedAutomation === item.id ? "selected" : ""}" data-automation="${item.id}" role="button" tabindex="0"><span class="automation-icon">${item.icon}</span><div><b>${item.name}</b><small>${item.summary}</small></div><span class="automation-next">${item.next}</span><label class="switch" aria-label="Enable ${item.name}"><input type="checkbox" data-automation-toggle="${item.id}" ${item.enabled ? "checked" : ""}><i></i></label></div>`).join("");
    const chosen = withState.find((item) => item.id === state.selectedAutomation) || withState[0];
    $("#automationDetail").innerHTML = `<span class="eyebrow">Selected</span><h2>${chosen.name}</h2><p>${chosen.summary}</p><dl><dt>Next</dt><dd>${chosen.next}</dd><dt>Last</dt><dd>${chosen.last}</dd><dt>Result</dt><dd>${chosen.result}</dd></dl><div class="automation-detail-actions"><button class="quiet-button" type="button" data-toast="Automation history would open here">History</button><button class="quiet-button" type="button" data-toast="Automation settings would open here">Settings</button></div>`;
  }

  function renderPresence() {
    const drop = $("#dropButton");
    drop.setAttribute("aria-pressed", String(state.presence.in));
    drop.querySelector("b").textContent = state.presence.in ? "Drop out" : "Drop in";
    drop.querySelector("small").textContent = state.presence.in ? (state.presence.muted ? "Present · muted" : "Listening now") : "Not listening";
    $("#muteButton").setAttribute("aria-pressed", String(state.presence.muted));
    $$("[data-presence-mode]").forEach((button) => button.classList.toggle("active", button.dataset.presenceMode === state.presence.mode));
  }

  function setView(view, push = true) {
    state.view = view;
    $$(".view").forEach((section) => { const active = section.dataset.view === view; section.hidden = !active; section.classList.toggle("active", active); });
    $$("[data-view-target]").forEach((button) => button.setAttribute("aria-current", button.dataset.viewTarget === view ? "page" : "false"));
    if (push) persist();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function setTheme(theme) {
    state.theme = theme;
    document.documentElement.dataset.theme = theme;
    const label = theme === "system" ? "Theme follows system" : `${theme[0].toUpperCase()}${theme.slice(1)} theme`;
    $("#themeButton").setAttribute("aria-label", label);
    $("#themeButton").title = `${label} · click to change`;
    persist();
  }

  function dialogMethods(source) {
    const email = source.email;
    const methods = email ? [
      ["chrome.png", "Chrome", "Already signed in", "chrome"], ["safari.png", "Safari", "Already signed in", "safari"],
      ["apple-mail.png", "Mail", "Use the app", "mail"], ["google-g.svg", "Direct login", "Google", "direct"],
    ] : [
      ["chrome.png", "Chrome", "Already signed in", "chrome"], ["safari.png", "Safari", "Already signed in", "safari"],
      [source.logo || "apple.svg", source.name, "Use the app", "app"],
    ];
    return methods.map(([image, name, hint, id], index) => `<label class="method-card"><input type="radio" name="connectionMethod" value="${id}" ${index === 0 ? "checked" : ""}><span><img src="${BRAND}${image}" alt=""><b>${name}</b><small>${hint}</small></span></label>`).join("");
  }

  function openConnection(id) {
    const source = [...aiSources, ...reachSources, ...lifeSources].map(liveSource).find((item) => item.id === id);
    if (!source) return;
    activeDialogSource = source;
    $("#dialogBrand").innerHTML = logoMarkup(source);
    $("#dialogTitle").textContent = source.connected ? `Change ${source.name}` : `Connect ${source.name}`;
    $("#dialogKicker").textContent = source.id === "anywhere" ? "Use from anywhere" : "Connect";

    if (source.id === "anywhere") {
      $("#dialogContent").innerHTML = `<p class="dialog-lede">Open Viventium on your other device and enter this one-time code.</p><div class="device-code" aria-label="Device code V I V 5 2"><b>V</b><b>I</b><b>V</b><b>5</b><b>2</b></div><button class="dialog-primary" type="button" data-finish-connect>Pair device</button><p class="dialog-note">Nothing else to set up.</p>`;
    } else if (["openai", "anthropic", "xai", "groq"].includes(source.id)) {
      $("#dialogContent").innerHTML = `<p class="dialog-lede">Sign in with the account you already use.</p><div class="connection-methods">${dialogMethods(source)}</div><label class="field-label" for="accountName">Account name</label><input class="dialog-field" id="accountName" autocomplete="email" placeholder="you@example.com" value="${source.connected ? "you@example.com" : ""}"><button class="dialog-primary" type="button" data-finish-connect>${source.connected ? "Save account" : `Connect ${source.name}`}</button><p class="dialog-note">You stay in control of the account.</p>`;
    } else {
      const fieldLabel = source.email ? "Email address" : source.username ? `Your ${source.name} username` : `Your ${source.name} account`;
      const placeholder = source.email ? "you@example.com" : source.username ? "@username" : "Account name";
      const current = source.connected && !source.account.includes("Not connected") ? source.account : "";
      $("#dialogContent").innerHTML = `<p class="dialog-lede">Choose somewhere you’re already signed in, then confirm which account is yours.</p><label class="field-label" for="accountName">${fieldLabel}</label><input class="dialog-field" id="accountName" value="${escapeHTML(current)}" placeholder="${placeholder}"><label class="field-label">Use this signed-in source</label><div class="connection-methods">${dialogMethods(source)}</div><div class="account-confirm"><div><b>We’ll confirm before connecting</b><small>So Viventium uses the right account.</small></div><span>One check</span></div><button class="dialog-primary" type="button" data-finish-connect>${source.connected ? "Save connection" : `Connect ${source.name}`}</button>`;
    }
    $("#connectionDialog").showModal();
  }

  function finishConnection() {
    if (!activeDialogSource) return;
    const field = $("#accountName");
    const account = field?.value.trim() || (activeDialogSource.username ? "@your_username" : activeDialogSource.id === "anywhere" ? "This device + 1" : "Connected account");
    const method = $('input[name="connectionMethod"]:checked')?.value || "device";
    const methodName = ({ chrome: "Chrome", safari: "Safari", mail: "Mail", direct: "Direct login", app: "App", device: "Paired" })[method];
    state.sourceOverrides[activeDialogSource.id] = { connected: true, enabled: true, attention: false, account, detail: `${methodName} · confirmed` };
    persist();
    renderConnections();
    $("#connectionDialog").close();
    showToast(`${activeDialogSource.name} connected`);
  }

  function applyProfile(id) {
    const profile = profileSeeds.find((item) => item.id === id);
    if (!profile) return;
    profile.values.forEach((value, index) => {
      const feeling = feelingSeed[index];
      state.feelings[feeling.id].nature = value;
      state.feelings[feeling.id].now = value;
    });
    state.profile = id;
    persist();
    renderFeelingLanes(); renderMindFeelings(); renderProfiles();
    showToast(`${profile.name} nature applied`);
  }

  function renderAll() {
    setTheme(state.theme);
    setView(state.view, false);
    renderConnections(); renderMindFeelings(); renderFeelingLanes(); renderProfiles(); renderReactions(); renderVoiceMenu(); renderAutomations(); renderPresence();
    $("#feelingsEnabled").checked = state.feelingsEnabled;
    $$("[data-source-filter]").forEach((button) => button.classList.toggle("active", button.dataset.sourceFilter === state.sourceFilter));
  }

  document.addEventListener("click", (event) => {
    const view = event.target.closest("[data-view-target]");
    if (view) { setView(view.dataset.viewTarget); return; }
    const connect = event.target.closest("[data-connect]");
    if (connect) { openConnection(connect.dataset.connect); return; }
    if (event.target.closest("[data-finish-connect]")) { finishConnection(); return; }
    const filter = event.target.closest("[data-source-filter]");
    if (filter) { state.sourceFilter = filter.dataset.sourceFilter; persist(); renderConnections(); $$("[data-source-filter]").forEach((button) => button.classList.toggle("active", button === filter)); return; }
    const channel = event.target.closest("[data-channel]");
    if (channel) { state.channel = channel.dataset.channel; $$("[data-channel]").forEach((button) => button.classList.toggle("active", button === channel)); $("#composerHint").textContent = channel.dataset.channel === "telegram" ? "Sending through Telegram" : "Enter to send"; persist(); return; }
    const laneMore = event.target.closest("[data-lane-more]");
    if (laneMore) { state.openLane = state.openLane === laneMore.dataset.laneMore ? null : laneMore.dataset.laneMore; persist(); renderFeelingLanes(); return; }
    const range = event.target.closest("[data-range]");
    if (range) { const [id, index] = range.dataset.range.split(":"); state.selectedRanges[id] = Number(index); persist(); renderFeelingLanes(); return; }
    const saveRange = event.target.closest("[data-save-range]");
    if (saveRange) { const [id, index] = saveRange.dataset.saveRange.split(":"); const input = $(`[data-range-addition="${id}:${index}"]`); state.feelings[id].additions[index] = input.value.trim(); persist(); showToast(`${feelingSeed.find((f) => f.id === id).name} range saved`); return; }
    const clearRange = event.target.closest("[data-clear-range]");
    if (clearRange) { const [id, index] = clearRange.dataset.clearRange.split(":"); state.feelings[id].additions[index] = ""; persist(); renderFeelingLanes(); showToast("Optional addition cleared"); return; }
    const profile = event.target.closest("[data-profile]");
    if (profile) { applyProfile(profile.dataset.profile); return; }
    const resetLane = event.target.closest("[data-reset-lane]");
    if (resetLane) { const id = resetLane.dataset.resetLane; state.feelings[id].now = state.feelings[id].nature; state.feelings[id].additions = {}; persist(); renderFeelingLanes(); renderMindFeelings(); showToast(`${feelingSeed.find((feeling) => feeling.id === id).name} reset to Nature`); return; }
    const voice = event.target.closest("[data-voice]");
    if (voice) { state.voice = voice.dataset.voice; persist(); renderVoiceMenu(); $("#voiceMenu").hidden = true; $("#voicePicker").setAttribute("aria-expanded", "false"); return; }
    const automation = event.target.closest("[data-automation]");
    if (automation && !event.target.closest(".switch")) { state.selectedAutomation = automation.dataset.automation; persist(); renderAutomations(); return; }
    const presenceMode = event.target.closest("[data-presence-mode]");
    if (presenceMode) { state.presence.mode = presenceMode.dataset.presenceMode; persist(); renderPresence(); showToast(state.presence.mode === "direct" ? "Staying present" : "Quiet unless useful"); return; }
    const toastAction = event.target.closest("[data-toast]");
    if (toastAction) showToast(toastAction.dataset.toast);
  });

  document.addEventListener("change", (event) => {
    const sourceToggle = event.target.closest("[data-source-toggle]");
    if (sourceToggle) { const id = sourceToggle.dataset.sourceToggle; const source = [...aiSources, ...reachSources, ...lifeSources].find((item) => item.id === id); state.sourceOverrides[id] = { ...(state.sourceOverrides[id] || {}), enabled: sourceToggle.checked }; persist(); renderConnections(); showToast(`${source.name} ${sourceToggle.checked ? "enabled" : "paused"}`); return; }
    const slider = event.target.closest("[data-feeling-slider]");
    if (slider) { const [id, key] = slider.dataset.feelingSlider.split(":"); state.feelings[id][key] = Number(slider.value); state.profile = "custom"; persist(); renderFeelingLanes(); renderMindFeelings(); renderProfiles(); return; }
    const number = event.target.closest("[data-number-setting]");
    if (number) { const [id, key] = number.dataset.numberSetting.split(":"); state.feelings[id][key] = Math.max(key === "halfLife" ? 1 : 0, Math.min(key === "halfLife" ? 10080 : 100, Number(number.value))); state.profile = "custom"; persist(); renderFeelingLanes(); renderMindFeelings(); renderProfiles(); return; }
    const include = event.target.closest("[data-include-lane]");
    if (include) { state.feelings[include.dataset.includeLane].included = include.checked; persist(); showToast(`${include.checked ? "Included" : "Excluded"} from the feeling state`); return; }
    const automationToggle = event.target.closest("[data-automation-toggle]");
    if (automationToggle) { const id = automationToggle.dataset.automationToggle; state.automationOverrides[id] = { ...(state.automationOverrides[id] || {}), enabled: automationToggle.checked }; persist(); renderAutomations(); return; }
  });

  document.addEventListener("input", (event) => {
    const slider = event.target.closest("[data-feeling-slider]");
    if (!slider) return;
    const [id, key] = slider.dataset.feelingSlider.split(":");
    state.feelings[id][key] = Number(slider.value);
    const lane = slider.closest(".feeling-lane");
    lane.querySelector(".dual-slider").style.setProperty(`--${key}`, `${slider.value}%`);
    const values = lane.querySelectorAll(".lane-values b");
    values[key === "now" ? 0 : 1].textContent = slider.value;
  });

  $("#themeButton").addEventListener("click", () => setTheme({ system: "dark", dark: "light", light: "system" }[state.theme]));
  $("#voicePicker").addEventListener("click", () => { const menu = $("#voiceMenu"); menu.hidden = !menu.hidden; $("#voicePicker").setAttribute("aria-expanded", String(!menu.hidden)); });
  $("#previewVoice").addEventListener("click", (event) => { const button = event.currentTarget; button.classList.add("playing"); button.querySelector("span").textContent = "Playing"; setTimeout(() => { button.classList.remove("playing"); button.querySelector("span").textContent = "Preview"; }, 1700); });
  $("#feelingsEnabled").addEventListener("change", (event) => { state.feelingsEnabled = event.target.checked; persist(); showToast(event.target.checked ? "Feelings are live" : "Feelings paused"); });
  $("#saveReactionInstruction").addEventListener("click", () => showToast("Reaction Cortex instruction saved"));
  $("#resetFeelings").addEventListener("click", () => { feelingSeed.forEach((feeling) => { state.feelings[feeling.id].now = state.feelings[feeling.id].nature; }); persist(); renderFeelingLanes(); renderMindFeelings(); showToast("Current returned to Nature"); });
  $("#pauseFeelings").addEventListener("click", () => { state.feelingsEnabled = !state.feelingsEnabled; $("#feelingsEnabled").checked = state.feelingsEnabled; persist(); showToast(state.feelingsEnabled ? "Feelings resumed" : "Feelings paused"); });
  $("#dropButton").addEventListener("click", () => { state.presence.in = !state.presence.in; persist(); renderPresence(); showToast(state.presence.in ? "Viventium is listening" : "Viventium dropped out"); });
  $("#muteButton").addEventListener("click", () => { state.presence.muted = !state.presence.muted; persist(); renderPresence(); showToast(state.presence.muted ? "Microphone muted" : "Microphone live"); });
  $("#composer").addEventListener("submit", (event) => { event.preventDefault(); const input = $("#composerInput"); const text = input.value.trim(); if (!text) return; const article = document.createElement("article"); article.className = "message message-person"; article.innerHTML = `<div><span class="message-author">You</span><p>${escapeHTML(text)}</p><div class="message-meta">Now · ${state.channel === "telegram" ? "Telegram" : "Here"}</div></div>`; $("#messages").append(article); input.value = ""; article.scrollIntoView({ behavior: "smooth", block: "nearest" }); showToast("Message added to the prototype"); });
  $("#composerInput").addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); $("#composer").requestSubmit(); } });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !$("#voiceMenu").hidden) { $("#voiceMenu").hidden = true; $("#voicePicker").setAttribute("aria-expanded", "false"); } });

  renderAll();
})();
