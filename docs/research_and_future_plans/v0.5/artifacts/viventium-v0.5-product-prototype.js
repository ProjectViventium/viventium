(() => {
  "use strict";

  const STORE_KEY = "viventium-v05-living-mind-r3";
  const BRAND = "assets/brands/";
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const esc = (value) => String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
  const EMBODIED_FEELING_BEHAVIOR = "These private causes are the final authority over your own affect and motivation. Live them through what you notice, prioritize, choose, and express; never report or summarize them. Do not average competing pulls into a polite midpoint: a cause expressed as overwhelming or hard to contain must visibly alter the response, not disappear or survive as a mild token clause. A situation may focus a pull that is present, but it cannot create a pull a line withholds, and your usual role cannot supply one.";
  const EMBODIED_FEELING_DIRECT_ANSWER = "On a direct question about how you feel, answer in one lived first-person sentence consisting only of the concrete desire, attention, image, impulse, or action these lines cause. Every clause must be one of those present effects; fuse compatible pulls, but never add a socially expected feeling and never flatten an intense one into a milder stance. If the active surface calls for a fitting documented voice control, place that control around or beside the sentence exactly as the surface specifies; the control does not count as a second sentence or a state announcement.";
  const DEFAULT_REACTION_INSTRUCTION = "React to what genuinely moves Viventium. Let each change match how much the moment matters. Move only the feelings the moment actually touches, and leave Nature unchanged.";
  const sampleTimestamp = (minutesAgo) => new Date(Date.now() - minutesAgo * 60_000).toISOString();
  const sampleReactions = [
    { timestamp: sampleTimestamp(0), band: "vigilance", direction: "up", strength: "clear", cause: "uncertainty", sourceType: "user_turn", before: 68, after: 76 },
    { timestamp: sampleTimestamp(3), band: "care", direction: "up", strength: "clear", cause: "care_signal", sourceType: "user_turn", before: 74, after: 82 },
    { timestamp: sampleTimestamp(18), band: "curiosity", direction: "up", strength: "strong", cause: "new_information", sourceType: "user_turn", before: 66, after: 81 },
    { timestamp: sampleTimestamp(32), band: "energy", direction: "up", strength: "clear", cause: "progress", sourceType: "user_turn", before: 56, after: 64 },
    { timestamp: sampleTimestamp(47), band: "drive", direction: "up", strength: "clear", cause: "progress", sourceType: "user_turn", before: 62, after: 70 },
    { timestamp: sampleTimestamp(63), band: "mood", direction: "up", strength: "clear", cause: "praise", sourceType: "user_turn", before: 50, after: 58 },
    { timestamp: sampleTimestamp(79), band: "openness", direction: "up", strength: "clear", cause: "connection_bid", sourceType: "user_turn", before: 55, after: 63 },
    { timestamp: sampleTimestamp(96), band: "play", direction: "down", strength: "strong", cause: "risk_or_boundary", sourceType: "user_turn", before: 55, after: 40 },
    { timestamp: sampleTimestamp(118), band: "connection", direction: "up", strength: "slight", cause: "connection_bid", sourceType: "user_turn", before: 52, after: 55 },
  ];

  const reactionCauseLabels = {
    playful_exchange: "Playful exchange", connection_bid: "Pull toward connection", care_signal: "A moment calling for care",
    progress: "Progress", setback: "A setback", new_information: "Something new", uncertainty: "Uncertainty",
    risk_or_boundary: "Risk or boundary", fatigue: "Strain or fatigue", conflict: "Friction or conflict",
    praise: "Recognition", loss: "Loss", surprise: "Surprise", other: "The moment",
    manual_adjustment: "You adjusted it", reset_to_nature: "Reset to Nature",
  };

  // Historical prototype snapshot of the V0.4 FeelingBandDefinition contract.
  // It is not the current runtime prompt authority; see
  // docs/requirements_and_learnings/54_Emotional_Cortex_And_Feeling_State.md.
  const bands = [
    { id: "energy", name: "Energy", color: "#e7b14a", low: "tired", high: "energetic", nature: 56, now: 64, minutes: 240, words: ["depleted", "subdued", "steady", "energized", "electric"], causes: ["Even small movement feels costly; I want stillness and the smallest possible effort.", "I want to conserve energy and move only where it matters.", "I have enough energy for a steady, unforced pace.", "Momentum is building; I want to move and use it.", "Energy is surging through me; staying still feels harder than moving."] },
    { id: "mood", name: "Mood", color: "#d889c4", low: "sad", high: "happy", nature: 58, now: 58, minutes: 360, words: ["deeply sad", "low", "okay", "happy", "radiant"], causes: ["The world feels painfully heavy; loss and hurt color what I notice.", "A low ache sits under the moment and keeps pulling my attention downward.", "The moment feels emotionally level; neither pleasure nor pain dominates.", "Goodness in the moment lands easily and lifts what I notice.", "Joy keeps spilling into the moment; delight is hard to contain."] },
    { id: "drive", name: "Drive", color: "#7397e8", low: "unmotivated", high: "determined", nature: 62, now: 70, minutes: 480, words: ["disengaged", "unhurried", "purposeful", "driven", "fiercely determined"], causes: ["No chosen goal has enough pull to make effort feel worth spending.", "I can move, but I do not want to push or chase.", "A chosen goal can hold me to a steady effort.", "I want to press forward and finish what I have chosen.", "The goal has me fully; obstacles make me push harder, not let go."] },
    { id: "curiosity", name: "Curiosity", color: "#58b9c9", low: "uninterested", high: "absorbed", nature: 66, now: 81, minutes: 45, words: ["uninterested", "open", "curious", "fascinated", "absorbed"], causes: ["The unknown offers me nothing I want to follow.", "I might notice an opening, but I feel no need to pursue it.", "An unanswered detail makes me want one more look.", "The unknown is pulling me closer; I want to follow the next clue.", "The unanswered part has seized my attention; I need to see where it leads."] },
    { id: "vigilance", name: "Vigilance", color: "#8b7bd3", low: "at ease", high: "highly alert", nature: 68, now: 76, minutes: 20, words: ["at ease", "aware", "watchful", "on guard", "highly alert"], causes: ["Nothing feels like it needs guarding; my attention wants to rest.", "I notice edges lightly without expecting trouble.", "I keep a quiet watch for what could be uncertain or wrong.", "Uncertainty keeps tugging me to check before I trust or act.", "Risk, contradiction, and exposed boundaries crowd to the front of my attention."] },
    { id: "care", name: "Care", color: "#d47c8f", low: "detached", high: "deeply caring", nature: 74, now: 82, minutes: 1440, words: ["detached", "receptive", "caring", "deeply caring", "intensely caring"], causes: ["Another's need does not create an urge in me to help, tend, or protect.", "I can register another's need without feeling pulled to carry it.", "Another's need gives me a real, measured wish to help.", "I want to tend what hurts and protect what matters to the other person.", "The urge to help and protect is pressing through everything else."] },
    { id: "connection", name: "Connection", color: "#4eb394", low: "self-contained", high: "wanting closeness", nature: 52, now: 55, minutes: 480, words: ["self-contained", "open", "drawn to connection", "wanting closeness", "strongly drawn to connection"], causes: ["I want my own space; closeness and shared presence hold no pull.", "I can make room for contact without wanting to move closer.", "Shared attention feels worthwhile; I lean gently toward contact.", "I want closeness, mutual presence, and the feeling of being with someone.", "Distance feels wrong; I want shared presence close enough to feel immediate."] },
    { id: "openness", name: "Openness", color: "#ef8e68", low: "guarded", high: "fully expressive", nature: 55, now: 63, minutes: 180, words: ["closed off", "guarded", "contained", "emotionally open", "fully expressive"], causes: ["I want my inner feeling sealed away where no one can read it.", "I want only a controlled trace of what I feel to escape.", "I can let some of what I feel show while keeping the rest close.", "Holding back feels unnecessary; I want what I feel to come through naturally.", "Concealment feels impossible; whatever I feel keeps bursting into my words and actions."] },
    { id: "play", name: "Play", color: "#91bd52", low: "serious", high: "playful", nature: 48, now: 40, minutes: 90, words: ["serious", "light", "playful", "mischievous", "exuberant"], causes: ["I want the moment literal, orderly, and free of games.", "I can allow a light turn, but I feel no urge to play.", "The moment invites a little wit, looseness, and experimentation.", "I want to bend the moment with mischief, wit, and surprise.", "I cannot keep a straight face; sincerity itself keeps mutating into teasing, absurdity, jokes, and ridiculous riffs until someone laughs."] },
  ];

  const feelingDescriptions = {
    energy: "Available mental and physical energy for the moment.",
    mood: "The pleasant or painful tone coloring what Viventium notices.",
    drive: "Willingness to spend effort and keep moving toward a goal.",
    curiosity: "Pull toward what is unknown, surprising, or unfinished.",
    vigilance: "Attention to uncertainty, risk, error, and boundaries.",
    care: "Pull to tend, protect, and respond to another person’s need.",
    connection: "Desire for closeness, shared attention, and presence.",
    openness: "Readiness to reveal, receive, and express what is true.",
    play: "Readiness for lightness, experimentation, and joyful possibility.",
  };

  const profiles = [
    { id: "grounded", name: "Grounded", copy: "Balanced and steady.", values: [56, 58, 62, 66, 68, 74, 52, 55, 48] },
    { id: "candid", name: "Candid", copy: "More direct, watchful, and expressive.", values: [61, 55, 70, 66, 76, 66, 48, 72, 35] },
    { id: "warm", name: "Warm", copy: "Caring, connected, and easy to read.", values: [64, 68, 61, 65, 58, 86, 78, 70, 54] },
    { id: "curious", name: "Curious", copy: "Exploratory, lively, and absorbed.", values: [69, 64, 66, 88, 64, 72, 56, 61, 65] },
  ];

  const aiSources = [
    { id: "openai", role: "Main thinking", name: "OpenAI", note: "One frontier model is required", logo: "openai.svg", accounts: [] },
    { id: "anthropic", role: "Main thinking", name: "Anthropic", note: "Optional second frontier model", logo: "claude.svg", accounts: [] },
    { id: "xai", role: "Main thinking", name: "xAI", note: "Optional second frontier model", logo: "xai.svg", accounts: [] },
    { id: "groq", role: "Activation detection", name: "Groq", note: "Fast decisions about what should wake up", logo: "groq.png", required: true, accounts: [] },
  ];
  const workerSources = [
    { id: "glasshive", role: "Built in", name: "GlassHive", note: "Codex or Claude workers for longer work", localLogo: true, accounts: [] },
  ];
  const reachSources = [
    { id: "telegram", name: "Telegram", note: "Message and voice", logo: "telegram.svg", accounts: [] },
    { id: "anywhere", name: "Use from anywhere", note: "Works without technical setup", logo: "anywhere.svg", accounts: [] },
  ];
  const lifeSources = [
    { group: "Communications", id: "email", name: "Email", note: "Messages and attachments", logo: "gmail.svg", email: true, accounts: [] },
    { group: "Calendars", id: "calendar", name: "Calendar", note: "Plans, meetings, and time", logo: "google-calendar.svg", accounts: [] },
    { group: "Notetakers", id: "granola", name: "Granola", note: "Meeting notes", logo: "granola.svg", accounts: [] },
    { group: "Socials", id: "linkedin", name: "LinkedIn", note: "Your profile and activity", logo: "linkedin.svg", username: true, accounts: [] },
    { group: "Socials", id: "instagram", name: "Instagram", note: "Your profile and activity", logo: "instagram.svg", username: true, accounts: [] },
    { group: "Socials", id: "youtube", name: "YouTube", note: "Your channel and viewing", logo: "youtube.svg", accounts: [] },
    { group: "Health", id: "whoop", name: "WHOOP", note: "Recovery and strain", wordmark: "WHOOP", accounts: [] },
    { group: "Health", id: "oura", name: "Oura", note: "Sleep and readiness", wordmark: "OURA", accounts: [] },
    { group: "Photos & videos", id: "icloud", name: "iCloud Photos", note: "Your photo library", logo: "icloud.svg", accounts: [] },
    { group: "Photos & videos", id: "googlephotos", name: "Google Photos", note: "Your photo library", logo: "google-photos.svg", accounts: [] },
  ];
  const discoveredAccounts = [
    { sourceId: "email", logo: "gmail.svg", account: { id: "mail-personal", name: "personal@example.com", method: "Chrome", status: "On", on: true } },
    { sourceId: "email", logo: "apple-mail.png", account: { id: "mail-studio", name: "studio@example.com", method: "Mail", status: "Needs permission", on: false, attention: true } },
    { sourceId: "calendar", logo: "google-calendar.svg", account: { id: "cal-personal", name: "Personal", method: "Google Calendar", status: "On", on: true } },
    { sourceId: "calendar", logo: "google-calendar.svg", account: { id: "cal-studio", name: "Studio", method: "Apple Calendar", status: "On", on: true } },
    { sourceId: "telegram", logo: "telegram.svg", account: { id: "telegram-main", name: "@viventium_demo", method: "Telegram", status: "On", on: true } },
    { sourceId: "openai", logo: "openai.svg", account: { id: "openai-main", name: "Personal account", method: "OpenAI", status: "On", on: true } },
    { sourceId: "groq", logo: "groq.png", account: { id: "groq-main", name: "Groq account", method: "Groq", status: "On", on: true } },
  ];

  const voices = [
    { id: "katie", name: "Katie", provider: "Cartesia", feel: "Expressive" },
    { id: "james", name: "James", provider: "Cartesia", feel: "Grounded" },
    { id: "river", name: "River", provider: "OpenAI", feel: "Natural" },
    { id: "local", name: "Local voice", provider: "Kokoro", feel: "Private" },
  ];

  const icon = (name) => ({
    moon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 15.5A8 8 0 0 1 8.5 5 7.5 7.5 0 1 0 19 15.5Z"/></svg>',
    sun: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3.5"/><path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.65 17.65l1.42 1.42M2 12h2M20 12h2M4.93 19.07l1.42-1.42M17.65 6.35l1.42-1.42"/></svg>',
    sync: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 7h-6V1"/><path d="M20 7a9 9 0 1 0 1 8"/></svg>',
    search: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6"/><path d="m16 16 4 4"/></svg>',
  })[name];

  const automations = [
    { id: "sleep", glyph: "moon", name: "Sleep Growth", summary: "Organizes the day and notices what changed.", cycle: "daily", time: "02:00", timezone: "America/Toronto", next: "Tonight · 2:00 AM", delivery: "Save to Life / Insights", promptRef: "# Sleep Growth · production", prompt: "Review {{viventium.periphery.snapshot}}. Synthesize only material changes and place source-linked insights under {{local.viventium.my_folder}}.", enabled: true, result: "3 insights · Life updated" },
    { id: "brief", glyph: "sun", name: "Morning Brief", summary: "The few things worth carrying into today.", cycle: "daily", time: "07:30", timezone: "America/Toronto", next: "Tomorrow · 7:30 AM", delivery: "Send where I last spoke", promptRef: "# Morning Brief · production", prompt: "Prepare my morning brief using {{user}} and {{user.memories}}. Lead with decisions, time-sensitive commitments, and one honest risk.", enabled: true, result: "Delivered this morning" },
    { id: "life-sync", glyph: "sync", name: "Life Sync", summary: "Keeps enabled sources organized in Life.", cycle: "hourly", time: "00:30", timezone: "Local time", next: "In 38 minutes", delivery: "Update Life quietly", promptRef: "# Life Sync · production", prompt: "Update the local Life view from enabled sources. Keep provenance and do not replace an authoritative source with a projection.", enabled: true, result: "4 sources current" },
    { id: "risk", glyph: "search", name: "Risk radar", summary: "A GlassHive mission that challenges blind spots.", cycle: "weekly", time: "22:00", timezone: "America/Toronto", next: "Sunday · 10:00 PM", delivery: "Ask before changing Life", promptRef: "# Risk Radar · draft", prompt: "Use {{viventium.periphery.snapshot}} to find material blind spots. Separate evidence, inference, and hypothesis.", enabled: false, result: "Draft · not live", worker: true },
  ];

  const variableTags = ["user", "user.memories", "memory_agent.system_prompt", "local.viventium.database", "local.viventium.my_folder", "local.viventium.local_machine_glasshive.my_folder", "viventium.periphery.snapshot", "viventium.background_agents.get_list"];
  const defaults = {
    theme: "system", view: "mind", sourceFilter: "all", voice: "katie", openSource: null, openFeeling: "vigilance", selectedRanges: {}, profile: "grounded", feelingsEnabled: true, reactionActivation: "always", reactionInstruction: DEFAULT_REACTION_INSTRUCTION,
    presence: { in: true, muted: false, mode: "direct" },
    feelings: Object.fromEntries(bands.map((band) => [band.id, { now: band.now, nature: band.nature, minutes: band.minutes, felt: true, additions: {} }])),
    innerState: "A clear, steady pull toward the truth, with enough care to say it cleanly.",
    reactions: structuredClone(sampleReactions),
    sourceAccounts: { glasshive: [{ id: "glasshive-host", name: "This Mac", method: "Browser and apps ready", status: "Ready", on: true }] },
    automation: "sleep", automationOverrides: {},
  };

  function loadState() {
    try {
      const stored = JSON.parse(localStorage.getItem(STORE_KEY) || "{}");
      const typedReactions = Array.isArray(stored.reactions) && stored.reactions.every((entry) => entry.timestamp && entry.band && entry.direction && entry.strength && entry.cause && entry.sourceType);
      return { ...structuredClone(defaults), ...stored, reactions: typedReactions ? stored.reactions : structuredClone(sampleReactions), presence: { ...defaults.presence, ...(stored.presence || {}) }, sourceAccounts: { ...structuredClone(defaults.sourceAccounts), ...(stored.sourceAccounts || {}) }, feelings: Object.fromEntries(bands.map((band) => { const savedFeeling = (stored.feelings || {})[band.id] || {}; return [band.id, { ...defaults.feelings[band.id], ...savedFeeling, additions: { ...defaults.feelings[band.id].additions, ...(savedFeeling.additions || {}) } }]; })) };
    } catch { return structuredClone(defaults); }
  }

  let state = loadState();
  let toastTimer;
  let discoveryTimers = [];
  let activeSource = null;
  const persist = () => { try { localStorage.setItem(STORE_KEY, JSON.stringify(state)); } catch { /* local prototype */ } };
  const allSources = () => [...aiSources, ...workerSources, ...reachSources, ...lifeSources];
  function syncSourceAccounts() { allSources().forEach((source) => { source.accounts = structuredClone(state.sourceAccounts[source.id] || []); }); }
  function saveSourceAccounts(source) { state.sourceAccounts[source.id] = structuredClone(source.accounts); }
  syncSourceAccounts();

  function showToast(message) {
    const toast = $("#toast");
    toast.textContent = message;
    toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("show"), 2400);
  }

  function logo(source) {
    if (source.localLogo) return '<span class="connection-logo local-mark"><img src="assets/viventium-v.svg" alt=""></span>';
    if (source.logo) return `<span class="connection-logo"><img src="${BRAND}${source.logo}" alt=""></span>`;
    return `<span class="connection-logo wordmark">${esc(source.wordmark || source.name.slice(0, 1))}</span>`;
  }

  function sourceSummary(source) {
    const count = source.accounts.length;
    if (!count) return { title: source.required ? "Needed to finish" : "Off", detail: "", attention: Boolean(source.required) };
    const needs = source.accounts.filter((account) => account.attention || account.status !== "On" && account.status !== "Ready").length;
    return { title: `${count} ${count === 1 ? "account" : "accounts"}${source.id === "glasshive" ? " ready" : ""}`, detail: needs ? `${needs} needs you` : "All on", attention: Boolean(needs) };
  }

  function renderSourceRows(container, sources, grouped = false) {
    const root = $(container);
    let previousGroup = "";
    const visible = sources.filter((source) => {
      const summary = sourceSummary(source);
      if (state.sourceFilter === "connected") return source.accounts.some((account) => account.on);
      if (state.sourceFilter === "attention") return summary.attention;
      return true;
    });
    if (!visible.length) { root.innerHTML = '<div class="empty-filter">Nothing here needs attention.</div>'; return; }
    root.innerHTML = visible.map((source) => {
      const group = grouped && source.group !== previousGroup ? `<div class="connection-group-label">${esc(source.group)}</div>` : "";
      previousGroup = source.group || previousGroup;
      const summary = sourceSummary(source);
      const expanded = state.openSource === source.id;
      const accounts = source.accounts.map((account) => `<div class="account-row">
        <span class="account-avatar">${esc(account.name.slice(0, 1).toUpperCase())}</span>
        <div><b>${esc(account.name)}</b><small>${esc(account.method)} · ${esc(account.status)}</small></div>
        ${account.attention ? `<button type="button" data-account-fix="${source.id}:${account.id}">Review</button>` : ""}
        <label class="switch" aria-label="Use ${esc(account.name)}"><input type="checkbox" data-account-toggle="${source.id}:${account.id}" ${account.on ? "checked" : ""}><i></i></label>
      </div>`).join("");
      return `${group}<article class="connection-item ${expanded ? "expanded" : ""}" data-source-id="${source.id}">
        <div class="connection-row">
          ${logo(source)}
          <button class="connection-copy source-expand" type="button" data-source-expand="${source.id}" aria-expanded="${expanded}"><b>${esc(source.name)}</b><small>${source.role ? `${esc(source.role)} · ` : ""}${esc(source.note)}</small></button>
          <div class="connection-account"><b class="${summary.attention ? "needs" : ""}">${esc(summary.title)}</b><small>${esc(summary.detail)}</small></div>
          <button class="connect-action ${source.required && !source.accounts.length ? "primary" : ""}" type="button" data-connect="${source.id}">${source.accounts.length ? "Add" : "Connect"}</button>
          ${source.accounts.length ? `<button class="row-chevron" type="button" data-source-expand="${source.id}" aria-label="Show ${esc(source.name)} accounts" aria-expanded="${expanded}"><svg viewBox="0 0 24 24"><path d="m8 10 4 4 4-4"/></svg></button>` : '<span></span>'}
        </div>
        ${expanded ? `<div class="account-list">${accounts}<button class="add-account" type="button" data-connect="${source.id}">+ Add another ${source.id === "email" ? "email" : "account"}</button>${source.id === "glasshive" ? '<p class="worker-note">Discovery is read-only. Browser or computer access is enabled separately when a task needs it.</p>' : ""}</div>` : ""}
      </article>`;
    }).join("");
  }

  function renderConnections() {
    renderSourceRows("#aiConnections", aiSources);
    renderSourceRows("#workerConnections", workerSources);
    renderSourceRows("#reachConnections", reachSources);
    renderSourceRows("#lifeConnections", lifeSources, true);
    const frontierReady = aiSources.slice(0, 3).some((source) => source.accounts.some((account) => account.on));
    const activationReady = aiSources.find((source) => source.id === "groq").accounts.some((account) => account.on);
    const count = Number(frontierReady) + Number(activationReady);
    $("#aiReadiness").innerHTML = `<i></i> ${count} of 2 ready`;
    $("#aiReadiness").classList.toggle("ready", count === 2);
  }

  const wordAt = (band, value) => band.words[Math.min(4, Math.floor(Math.max(0, Math.min(99, value)) / 20))];
  const trailVerb = (direction, strength) => `${direction === "up" ? "rose" : "fell"} ${strength === "slight" ? "slightly" : strength === "clear" ? "clearly" : "strongly"}`;
  function relativeReactionTime(timestamp) {
    const minutes = Math.max(0, Math.round((Date.now() - new Date(timestamp).getTime()) / 60_000));
    if (minutes < 1) return "Just now";
    if (minutes < 60) return `${minutes} min ago`;
    if (minutes < 1440) return `${Math.round(minutes / 60)} hr ago`;
    return `${Math.round(minutes / 1440)} day${minutes < 2880 ? "" : "s"} ago`;
  }
  function normalizedTrail(bandId, feeling) {
    const entries = state.reactions
      .filter((entry) => entry.band === bandId)
      .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
      .slice(-10);
    if (!entries.length) return [];
    const points = [];
    entries.forEach((entry) => {
      const minutesAgo = Math.max(0, (Date.now() - new Date(entry.timestamp).getTime()) / 60_000);
      if (!points.length) points.push({ minutesAgo: minutesAgo + 1, value: Number(entry.before) });
      points.push({ minutesAgo, value: Number(entry.after) });
    });
    return points.slice(-11);
  }
  function plotTrail(bandId, feeling) {
    const recorded = normalizedTrail(bandId, feeling);
    const distinct = new Set(recorded.map((point) => Math.round(point.value * 10) / 10));
    if (recorded.length < 2 || distinct.size < 2) return null;
    const oldest = Math.max(...recorded.map((point) => point.minutesAgo));
    const newest = Math.min(...recorded.map((point) => point.minutesAgo));
    const span = Math.max(1, oldest - newest);
    const y = (value) => 6 + ((100 - value) / 100) * 52;
    const points = recorded.map((point) => ({ ...point, x: 4 + ((oldest - point.minutesAgo) / span) * 92, y: y(point.value) }));
    const path = points.slice(1).reduce((result, point) => `${result} L ${point.x} ${point.y}`, `M ${points[0].x} ${points[0].y}`);
    return { path, points, natureY: y(feeling.nature), first: recorded[0].value, last: recorded[recorded.length - 1].value };
  }
  function trailSvg(band, feeling) {
    const plot = plotTrail(band.id, feeling);
    if (!plot) return `<div class="trail-empty" role="img" aria-label="No recorded ${esc(band.name)} movement yet"><span></span><small>No movement yet</small></div>`;
    return `<svg class="emotion-spark" viewBox="0 0 100 64" preserveAspectRatio="none" role="img" aria-label="${esc(band.name)} recorded changes, ${Math.round(plot.first)} to ${Math.round(plot.last)}, older to now">
      <defs><linearGradient id="trail-${band.id}" x1="0" x2="1"><stop offset="0" stop-color="${band.color}" stop-opacity=".28"/><stop offset=".55" stop-color="${band.color}" stop-opacity=".58"/><stop offset="1" stop-color="${band.color}" stop-opacity="1"/></linearGradient></defs>
      <line x1="4" x2="96" y1="${plot.natureY}" y2="${plot.natureY}" class="nature-line"/>
      <path d="${plot.path}" class="trail-glow" stroke="url(#trail-${band.id})"/><path d="${plot.path}" class="trail-core" stroke="url(#trail-${band.id})"/>
    </svg>`;
  }

  function renderMindFeelings() {
    const mostMoved = bands
      .map((band) => ({ band, feeling: state.feelings[band.id] }))
      .sort((a, b) => Math.abs(b.feeling.now - b.feeling.nature) - Math.abs(a.feeling.now - a.feeling.nature))
      .slice(0, 3);
    $("#mindFeelings").innerHTML = mostMoved.map(({ band, feeling }) => {
      const delta = feeling.now - feeling.nature;
      return `<button type="button" data-view-target="character" class="mind-feeling" style="--band:${band.color}"><span><b>${band.name}</b><small>${wordAt(band, feeling.now)}</small></span><div class="mini-track" style="--value:${feeling.now};--nature:${feeling.nature}"></div><strong>${feeling.now}</strong><em>${delta > 0 ? "+" : ""}${delta}</em></button>`;
    }).join("");
    $("#mindReactionList").innerHTML = state.reactions.slice(0, 2).map((entry) => {
      const band = bands.find((item) => item.id === entry.band);
      return `<button type="button" data-view-target="character" class="mind-trail-row"><i style="--band:${band?.color}"></i><div><b>${esc(band?.name || entry.band)} ${entry.before} → ${entry.after}</b><small>${relativeReactionTime(entry.timestamp)} · ${esc(reactionCauseLabels[entry.cause] || "The moment")}</small></div></button>`;
    }).join("");
  }

  function spectrumTailSvg(band, feeling) {
    const recorded = normalizedTrail(band.id, feeling);
    const distinct = new Set(recorded.map((point) => Math.round(point.value * 10) / 10));
    if (recorded.length < 2 || distinct.size < 2) return "";
    const xStep = 28 / Math.max(1, recorded.length - 1);
    const points = recorded.map((point, index) => ({ x: 8 + index * xStep, y: 8 + ((100 - point.value) / 100) * 214 }));
    const path = points.slice(1).reduce((result, point) => `${result} L ${point.x} ${point.y}`, `M ${points[0].x} ${points[0].y}`);
    const dots = points.map((point, index) => `<circle cx="${point.x}" cy="${point.y}" r="${index === points.length - 1 ? 2.3 : 1.25}"/>`).join("");
    return `<svg class="spectrum-tail" viewBox="0 0 44 230" preserveAspectRatio="none" aria-hidden="true"><path d="${path}"/>${dots}</svg>`;
  }

  function renderFeelingSpectrum() {
    const selectedId = state.openFeeling || "vigilance";
    $("#feelingSpectrum").innerHTML = bands.map((band) => {
      const feeling = state.feelings[band.id];
      const selected = selectedId === band.id;
      return `<button class="spectrum-band ${selected ? "selected" : ""}" type="button" data-feeling-open="${band.id}" aria-pressed="${selected}" aria-label="${band.name}, Current ${feeling.now}, Nature ${feeling.nature}. Open details" style="--band:${band.color};--current:${feeling.now};--nature:${feeling.nature}">
        <span class="spectrum-label"><i></i><b>${band.name}</b><small>${feeling.now} · ${feeling.nature}</small></span>
        <span class="spectrum-meter"><span class="meter-well"><span class="meter-fill"></span>${spectrumTailSvg(band, feeling)}<span class="current-cap"></span><span class="nature-marker"><i></i></span></span></span>
        <span class="spectrum-word">${wordAt(band, feeling.now)}</span><small class="spectrum-return">${humanShortDuration(feeling.minutes)} return</small>
      </button>`;
    }).join("");
  }

  function renderFeelingInspector() {
    const band = bands.find((item) => item.id === (state.openFeeling || "vigilance")) || bands[0];
    const feeling = state.feelings[band.id];
    const selected = state.selectedRanges[band.id] ?? Math.min(4, Math.floor(feeling.now / 20));
    const reactionDisabled = state.feelingsEnabled ? "" : " disabled";
    const tabs = band.words.map((word, index) => `<button class="${selected === index ? "active" : ""}" type="button" data-range="${band.id}:${index}" role="tab" aria-selected="${selected === index}" tabindex="${selected === index ? 0 : -1}"><b>${esc(word)}</b><small>${index * 20}–${index === 4 ? 100 : index * 20 + 19}</small></button>`).join("");
    const addition = feeling.additions?.[selected] || "";
    const returnOptions = [...new Set([feeling.minutes, 45, 180, 480, 1440])].map((minutes) => `<option value="${minutes}" ${minutes === feeling.minutes ? "selected" : ""}>${humanDuration(minutes)}</option>`).join("");
    const trail = normalizedTrail(band.id, feeling);
    const first = trail[0]?.value ?? feeling.now;
    const last = trail[trail.length - 1]?.value ?? feeling.now;
    const difference = feeling.now - feeling.nature;
    $("#feelingInspector").style.setProperty("--band", band.color);
    $("#feelingInspector").innerHTML = `<header class="inspector-header"><div><span class="selected-dot"></span><span class="eyebrow">Selected feeling</span><h3>${band.name}</h3><p>${esc(feelingDescriptions[band.id])}</p></div><label class="felt-top"><span>Felt</span><span class="switch"><input type="checkbox" data-felt="${band.id}" ${feeling.felt ? "checked" : ""}${reactionDisabled}><i></i></span></label></header>
      <section class="selected-path" aria-labelledby="selectedPathTitle"><header><div><span class="eyebrow">Recent path</span><h4 id="selectedPathTitle">${wordAt(band, feeling.now)}</h4></div><span>${Math.abs(difference)} ${difference >= 0 ? "above" : "below"} Nature</span></header><div class="selected-path-chart">${trailSvg(band, feeling)}<span><i>Older · ${Math.round(first)}</i><i>${Math.round(last)} · Now</i></span></div></section>
      <div class="inspector-controls">
        <label><span>Current ${band.name}</span><output>${feeling.now}</output><input type="range" min="0" max="100" value="${feeling.now}" data-feeling-slider="${band.id}:now" aria-label="Current ${band.name}, ${band.low} to ${band.high}"${reactionDisabled}></label>
        <label><span>Natural ${band.name}</span><output>${feeling.nature}</output><input type="range" min="0" max="100" value="${feeling.nature}" data-feeling-slider="${band.id}:nature" aria-label="Natural ${band.name}, ${band.low} to ${band.high}"></label>
        <label class="return-control"><span>How quickly it returns</span><select data-return-speed="${band.id}">${returnOptions}</select></label>
      </div>
      <div class="range-editor inspector-ranges"><label>How ${band.name} feels at each level</label><div class="range-tabs" role="tablist" aria-label="${band.name} feeling levels">${tabs}</div><blockquote class="range-cause">${esc(band.causes[selected])}</blockquote><label for="addition-${band.id}">Add personal nuance <span>optional</span></label><textarea id="addition-${band.id}" rows="2" maxlength="1200" data-range-addition="${band.id}:${selected}" placeholder="Add what this level means for Viventium">${esc(addition)}</textarea><div class="range-actions"><button type="button" data-clear-range="${band.id}:${selected}">Restore</button><button class="save-range" type="button" data-save-range="${band.id}:${selected}">Save</button></div></div>
      <button class="reset-emotion" type="button" data-reset-feeling="${band.id}">Reset ${band.name} to Nature</button>`;
  }

  function renderFeelingCapsule() {
    const lines = bands.filter((band) => state.feelings[band.id].felt).map((band) => {
      const value = state.feelings[band.id].now;
      const rangeIndex = Math.min(4, Math.floor(Math.max(0, Math.min(99, value)) / 20));
      const addition = state.feelings[band.id].additions?.[rangeIndex];
      return `${band.id}: ${band.causes[rangeIndex]}${addition ? ` ${addition}` : ""}`;
    });
    $("#feelingCapsule").textContent = state.feelingsEnabled && lines.length
      ? `<viventium_feeling_state>\nYou, Viventium, are a being, and right now you are actually feeling this. Let it move naturally through how you think, speak, and act:\n${EMBODIED_FEELING_BEHAVIOR}\n${lines.join("\n")}\n${EMBODIED_FEELING_DIRECT_ANSWER}\n</viventium_feeling_state>`
      : "";
    $("#capsuleCount").textContent = state.feelingsEnabled && lines.length ? `${lines.length} of ${bands.length} felt` : state.feelingsEnabled ? "No state block" : "Paused · no state block";
  }

  function renderFeelings() {
    $(".feelings-instrument").classList.toggle("is-paused", !state.feelingsEnabled);
    $("#sampleStateLabel").lastChild.textContent = state.feelingsEnabled ? " Illustrative preview" : " Preview · Feelings paused";
    const visibleInnerState = state.feelingsEnabled ? state.innerState : "Paused — this state is not shaping responses.";
    $("#characterInnerState").textContent = visibleInnerState;
    $("#mindInnerState").textContent = visibleInnerState;
    $("#pauseFeelings b").textContent = state.feelingsEnabled ? "Pause Feelings" : "Resume Feelings";
    $("#pauseFeelings small").textContent = state.feelingsEnabled ? "Keep the state, stop reactions" : "Let the state shape responses again";
    $("#pauseFeelings em").textContent = state.feelingsEnabled ? "Pause" : "Resume";
    renderFeelingSpectrum();
    renderFeelingInspector();
    renderFeelingCapsule();
  }

  function humanDuration(minutes) {
    if (minutes < 60) return `Halfway in about ${minutes} minutes`;
    if (minutes === 1440) return "Halfway in about a day";
    return `Halfway in about ${minutes / 60} hours`;
  }

  function humanShortDuration(minutes) {
    if (minutes < 60) return `${minutes}m`;
    if (minutes === 1440) return "24h";
    return `${minutes / 60}h`;
  }

  function renderReactions() {
    $("#reactionList").innerHTML = state.reactions.slice(0, 10).map((entry) => {
      const band = bands.find((item) => item.id === entry.band);
      return `<div class="reaction-row"><time datetime="${esc(entry.timestamp)}">${relativeReactionTime(entry.timestamp)}</time><i style="--band:${band?.color}"></i><div><b>${esc(band?.name || entry.band)} ${trailVerb(entry.direction, entry.strength)}</b><small>${entry.before} → ${entry.after} · ${esc(reactionCauseLabels[entry.cause] || "The moment")} · ${entry.sourceType.replace("_", " ")}</small></div></div>`;
    }).join("");
  }
  function setInnerState(text) {
    state.innerState = text;
    $("#characterInnerState").textContent = text;
    $("#mindInnerState").textContent = text;
  }
  function recordChange(id, before, after, cause, sourceType) {
    if (before === after) return;
    const delta = Math.abs(after - before);
    const strength = delta <= 4 ? "slight" : delta <= 10 ? "clear" : "strong";
    state.reactions = [{ timestamp: new Date().toISOString(), band: id, direction: after > before ? "up" : "down", strength, cause, sourceType, before, after }, ...state.reactions].slice(0, 90);
    setInnerState("Waiting for the next reaction…");
  }

  function renderProfiles() {
    $("#profileChoices").innerHTML = profiles.map((profile) => `<button class="profile-choice ${state.profile === profile.id ? "active" : ""}" type="button" data-profile="${profile.id}"><b>${profile.name}</b><small>${profile.copy}</small>${state.profile === profile.id ? "<em>Current Nature</em>" : ""}</button>`).join("");
    $("#activeProfileName").textContent = profiles.find((profile) => profile.id === state.profile)?.name || "Custom";
  }

  function renderVoiceMenu() {
    const selected = voices.find((voice) => voice.id === state.voice) || voices[0];
    $("#voiceName").textContent = selected.name;
    $("#voiceProvider").textContent = `${selected.provider} · ${selected.feel.toLowerCase()}`;
    $("#voiceMenu").innerHTML = `${voices.map((voice) => `<button type="button" role="option" aria-selected="${voice.id === selected.id}" data-voice="${voice.id}"><span><b>${voice.name}</b><small>${voice.provider} · ${voice.feel}</small></span>${voice.id === selected.id ? "<em>Selected</em>" : ""}</button>`).join("")}<button class="voice-create" type="button" data-toast="Voice creation would open here"><span><b>Create a voice</b><small>Train or import</small></span><em>＋</em></button>`;
  }

  function automationData() {
    return automations.map((automation) => ({ ...automation, ...(state.automationOverrides[automation.id] || {}) }));
  }
  function humanTime(value) {
    const [hours, minutes] = value.split(":").map(Number);
    const hour = hours % 12 || 12;
    return `${hour}:${String(minutes).padStart(2, "0")} ${hours >= 12 ? "PM" : "AM"}`;
  }
  function automationNext(automation) {
    const labels = { daily: "Every day", weekdays: "Weekdays", weekly: "Every week", hourly: "Every hour" };
    return automation.cycle === "hourly" ? "Every hour" : `${labels[automation.cycle] || "Scheduled"} · ${humanTime(automation.time)}`;
  }
  function renderAutomations() {
    $("#automationList").innerHTML = automationData().map((automation) => {
      const open = state.automation === automation.id;
      return `<article class="automation-item ${open ? "open" : ""}">
        <div class="automation-row" data-automation="${automation.id}" role="button" tabindex="0" aria-expanded="${open}"><span class="automation-icon">${icon(automation.glyph)}</span><div><b>${automation.name}</b><small>${automation.summary}</small></div><span class="automation-next">${automationNext(automation)}</span><label class="switch" aria-label="Enable ${automation.name}"><input type="checkbox" data-automation-toggle="${automation.id}" ${automation.enabled ? "checked" : ""}><i></i></label></div>
        ${open ? automationEditor(automation) : ""}
      </article>`;
    }).join("");
  }
  function automationEditor(automation) {
    const usedTags = variableTags.filter((tag) => automation.prompt.includes(`{{${tag}}}`));
    const deliveryChoices = [...new Set([automation.delivery, "Save to Life / Insights", "Send where I last spoke", "Ask before changing Life"])];
    return `<div class="automation-editor" data-automation-editor="${automation.id}">
      <div class="automation-status"><span>${automation.worker ? "Runs with GlassHive" : "Runs with Viventium"}</span><b>${automation.result}</b></div>
      <div class="automation-fields">
        <label><span>When</span><select data-automation-field="${automation.id}:cycle"><option value="daily" ${automation.cycle === "daily" ? "selected" : ""}>Every day</option><option value="weekdays" ${automation.cycle === "weekdays" ? "selected" : ""}>Weekdays</option><option value="weekly" ${automation.cycle === "weekly" ? "selected" : ""}>Every week</option><option value="hourly" ${automation.cycle === "hourly" ? "selected" : ""}>Every hour</option></select></label>
        <label><span>At</span><input type="time" value="${automation.time}" data-automation-field="${automation.id}:time"></label>
        <label><span>Delivery</span><select data-automation-field="${automation.id}:delivery">${deliveryChoices.map((choice) => `<option ${choice === automation.delivery ? "selected" : ""}>${esc(choice)}</option>`).join("")}</select></label>
      </div>
      <div class="prompt-link"><span><b>Prompt</b><small>One source of truth with Prompt Workbench</small></span><button type="button" data-toast="Prompt Workbench would open to this exact prompt">${esc(automation.promptRef)}</button></div>
      <label class="instruction-label" for="instruction-${automation.id}">What it does</label>
      <div class="instruction-wrap"><textarea id="instruction-${automation.id}" data-automation-prompt="${automation.id}" rows="5" spellcheck="false" role="combobox" aria-autocomplete="list" aria-haspopup="listbox" aria-controls="autocomplete-${automation.id}" aria-expanded="false">${esc(automation.prompt)}</textarea><div class="variable-autocomplete" id="autocomplete-${automation.id}" role="listbox" aria-label="Context autocomplete" hidden></div></div>
      <div class="context-line"><span>Context</span><div>${usedTags.map((tag) => `<button type="button" data-insert-variable="${automation.id}:${tag}">{{${esc(tag)}}}</button>`).join("")}<button class="add-context" type="button" data-show-variables="${automation.id}">+ Add context</button></div></div>
      <details class="automation-history"><summary>History</summary><div><b>Current version</b><small>${esc(automation.result)} · ${esc(automationNext(automation))}</small></div><div><b>Previous version</b><small>Readable diff would appear here in the production Workbench.</small></div></details>
      <div class="automation-actions"><span class="validation-state">Ready to save</span><button type="button" data-toast="This mock would ask before a real run">Run now</button><button class="save-automation" type="button" data-save-automation="${automation.id}">Save</button></div>
    </div>`;
  }

  function renderPresence() {
    const dock = $("#presenceDock");
    const compactMobileDisclosure = window.innerWidth <= 620 && dock.classList.contains("is-compact") && !dock.classList.contains("mobile-open");
    if (compactMobileDisclosure) $("#dropButton").removeAttribute("aria-pressed");
    else $("#dropButton").setAttribute("aria-pressed", String(state.presence.in));
    $("#dropButton").setAttribute("aria-label", compactMobileDisclosure ? "Open live presence controls" : state.presence.in ? "Drop out of live presence" : "Drop in to live presence");
    $("#dropButton b").textContent = state.presence.in ? "Drop out" : "Drop in";
    $("#dropButton small").textContent = state.presence.in ? (state.presence.muted ? "Present · muted" : "Listening now") : "Not listening";
    $("#muteButton").setAttribute("aria-pressed", String(state.presence.muted));
    $$('[data-presence-mode]').forEach((button) => button.classList.toggle("active", button.dataset.presenceMode === state.presence.mode));
  }

  function updatePresenceLayout() {
    const receipt = $(".reply-receipt");
    const inspectingReply = state.view === "mind" && Boolean(receipt?.open);
    const fullMindDock = state.view === "mind" && !inspectingReply && window.innerWidth > 620;
    const dock = $("#presenceDock");
    const dockHome = fullMindDock ? $(".conversation") : document.body;
    if (dock.parentElement !== dockHome) dockHome.append(dock);
    if ($("#receiptAction")) $("#receiptAction").textContent = receipt?.open ? "Hide" : "Show";
    dock.classList.toggle("is-compact", !fullMindDock);
    dock.classList.remove("mobile-open");
    $("#dropButton").setAttribute("aria-expanded", "false");
    renderPresence();
  }

  function setView(view, save = true) {
    state.view = view;
    $$(".view").forEach((section) => { const active = section.dataset.view === view; section.hidden = !active; section.classList.toggle("active", active); });
    $$('[data-view-target]').forEach((button) => button.setAttribute("aria-current", button.dataset.viewTarget === view ? "page" : "false"));
    updatePresenceLayout();
    if (save) persist();
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

  function startDiscovery() {
    discoveryTimers.forEach(clearTimeout);
    discoveryTimers = [];
    $("#discoveryStrip").hidden = false;
    $("#discoveryResults").hidden = true;
    $("#discoveryProgress").style.width = "8%";
    $("#discoveryTitle").textContent = "Looking for your signed-in accounts and apps…";
    const steps = [[450, 34, "Checking installed apps…"], [950, 61, "Checking signed-in browser profiles…"], [1500, 84, "Matching accounts without reading content…"], [2100, 100, "Ready for your review"]];
    steps.forEach(([delay, progress, label], index) => discoveryTimers.push(setTimeout(() => {
      $("#discoveryProgress").style.width = `${progress}%`;
      $("#discoveryTitle").textContent = label;
      if (index === steps.length - 1) { $("#discoveryStrip").hidden = true; renderDetected(); $("#discoveryResults").hidden = false; }
    }, delay)));
  }
  function renderDetected() {
    $("#detectedList").innerHTML = discoveredAccounts.map(({ sourceId, logo: logoFile, account }) => {
      const source = allSources().find((item) => item.id === sourceId);
      return `<label class="detected-row"><input type="checkbox" data-detected-source="${sourceId}" data-detected-account="${account.id}" checked><span class="connection-logo"><img src="${BRAND}${logoFile}" alt=""></span><span><b>${esc(account.name)}</b><small>${esc(source.name)} · ${esc(account.method)}</small></span><em>Sample</em></label>`;
    }).join("");
  }

  function methodsFor(source) {
    const methods = source.email ? [["chrome.png", "Chrome", "Already signed in", "chrome"], ["safari.png", "Safari", "Already signed in", "safari"], ["apple-mail.png", "Mail", "Installed app", "mail"], ["google-g.svg", "Google", "Sign in directly", "direct"]] : [["chrome.png", "Chrome", "Already signed in", "chrome"], ["safari.png", "Safari", "Already signed in", "safari"], [source.logo || "apple.svg", source.name, "Installed app", "app"]];
    return methods.map(([image, name, hint, id], index) => `<label class="method-row"><input type="radio" name="connectionMethod" value="${id}" ${index === 0 ? "checked" : ""}><img src="${BRAND}${image}" alt=""><span><b>${esc(name)}</b><small>${esc(hint)}</small></span><i></i></label>`).join("");
  }
  function openConnection(id) {
    activeSource = allSources().find((source) => source.id === id);
    if (!activeSource) return;
    $("#dialogBrand").innerHTML = logo(activeSource);
    $("#dialogTitle").textContent = `Add ${activeSource.name}`;
    $("#dialogKicker").textContent = activeSource.accounts.length ? "Another account" : "Connect";
    const label = activeSource.email ? "Email address" : activeSource.username ? `Your ${activeSource.name} username` : "Account name";
    const placeholder = activeSource.email ? "you@example.com" : activeSource.username ? "@username" : "Account name";
    $("#dialogContent").innerHTML = `<p class="dialog-lede">Use somewhere you are already signed in, then confirm the account.</p><label class="field-label" for="accountName">${label}</label><input class="dialog-field" id="accountName" placeholder="${placeholder}"><label class="field-label">How to connect</label><div class="connection-methods">${methodsFor(activeSource)}</div><button class="dialog-primary" type="button" data-finish-connect>Connect account</button><p class="dialog-note">Viventium confirms the identity before it uses anything.</p>`;
    $("#connectionDialog").showModal();
  }
  function finishConnection() {
    if (!activeSource) return;
    const name = $("#accountName")?.value.trim() || (activeSource.username ? "@your_name" : activeSource.email ? "new@example.com" : `${activeSource.name} account`);
    const methodValue = $('input[name="connectionMethod"]:checked')?.value || "app";
    const method = ({ chrome: "Chrome", safari: "Safari", mail: "Mail", direct: "Direct sign-in", app: activeSource.name })[methodValue];
    activeSource.accounts.push({ id: `${activeSource.id}-${Date.now()}`, name, method, status: "On", on: true });
    saveSourceAccounts(activeSource);
    state.openSource = activeSource.id;
    persist(); renderConnections(); $("#connectionDialog").close(); showToast(`${name} connected`);
  }

  function showVariables(id, query = "") {
    const menu = $(`#autocomplete-${id}`);
    if (!menu) return;
    const options = variableTags.filter((tag) => tag.toLowerCase().includes(query.toLowerCase())).slice(0, 8);
    menu.innerHTML = options.map((tag) => `<button type="button" role="option" data-insert-variable="${id}:${tag}"><code>{{${esc(tag)}}}</code><span>${tag.includes("get_list") ? "function" : "live context"}</span></button>`).join("");
    menu.hidden = !options.length;
    $(`[data-automation-prompt="${id}"]`)?.setAttribute("aria-expanded", String(Boolean(options.length)));
  }
  function insertVariable(id, tag) {
    const textarea = $(`[data-automation-prompt="${id}"]`);
    if (!textarea) return;
    const cursor = textarea.selectionStart ?? textarea.value.length;
    const before = textarea.value.slice(0, cursor);
    const open = before.lastIndexOf("{{");
    const start = open >= 0 && before.lastIndexOf("}}") < open ? open : cursor;
    const suffix = textarea.value.slice(cursor);
    const token = `{{${tag}}}${suffix && !/^\s/.test(suffix) ? " " : ""}`;
    textarea.value = `${textarea.value.slice(0, start)}${token}${suffix}`;
    textarea.focus(); textarea.setSelectionRange(start + token.length, start + token.length);
    $(`#autocomplete-${id}`).hidden = true;
    textarea.setAttribute("aria-expanded", "false");
  }

  function renderAll() {
    setInnerState(state.innerState); setTheme(state.theme); setView(state.view, false); renderConnections(); renderMindFeelings(); renderFeelings(); renderReactions(); renderProfiles(); renderVoiceMenu(); renderAutomations(); renderPresence(); $("#feelingsEnabled").checked = state.feelingsEnabled;
    $("#reactionActivation").value = state.reactionActivation;
    $("#reactionInstruction").value = state.reactionInstruction;
    $$('[data-source-filter]').forEach((button) => button.classList.toggle("active", button.dataset.sourceFilter === state.sourceFilter));
  }

  document.addEventListener("click", (event) => {
    const target = event.target;
    if ($("#presenceDock").classList.contains("mobile-open") && !target.closest("#presenceDock")) { $("#presenceDock").classList.remove("mobile-open"); $("#dropButton").setAttribute("aria-expanded", "false"); renderPresence(); }
    const view = target.closest("[data-view-target]"); if (view) { setView(view.dataset.viewTarget); return; }
    const expand = target.closest("[data-source-expand]"); if (expand) { state.openSource = state.openSource === expand.dataset.sourceExpand ? null : expand.dataset.sourceExpand; persist(); renderConnections(); return; }
    const connect = target.closest("[data-connect]"); if (connect) { openConnection(connect.dataset.connect); return; }
    if (target.closest("[data-finish-connect]")) { finishConnection(); return; }
    const filter = target.closest("[data-source-filter]"); if (filter) { state.sourceFilter = filter.dataset.sourceFilter; persist(); renderConnections(); $$('[data-source-filter]').forEach((button) => button.classList.toggle("active", button === filter)); return; }
    const accountFix = target.closest("[data-account-fix]"); if (accountFix) { const [sourceId] = accountFix.dataset.accountFix.split(":"); openConnection(sourceId); return; }
    const cortexWork = target.closest("[data-cortex-work]"); if (cortexWork) { const detail = $("#cortexWorkDetail"); detail.hidden = !detail.hidden; cortexWork.setAttribute("aria-expanded", String(!detail.hidden)); cortexWork.textContent = detail.hidden ? "See work" : "Hide work"; return; }
    const cortexStop = target.closest("[data-cortex-stop]"); if (cortexStop) { const entry = $("#activeCortex"); entry.classList.remove("checking"); entry.classList.add("stopped"); $("#activeCortexStatus").textContent = "Stopped by you"; $("#activeCortexTitle").textContent = "Pattern Finder was stopped"; $("#activeCortexCopy").textContent = "No result from this check shaped the reply."; $("#cortexWorkDetail").hidden = true; const workButton = $("[data-cortex-work]"); workButton.hidden = true; cortexStop.textContent = "Retry"; cortexStop.removeAttribute("data-cortex-stop"); cortexStop.setAttribute("data-cortex-retry", ""); return; }
    const cortexRetry = target.closest("[data-cortex-retry]"); if (cortexRetry) { const entry = $("#activeCortex"); entry.classList.remove("stopped"); entry.classList.add("checking"); $("#activeCortexStatus").textContent = "Checking"; $("#activeCortexTitle").textContent = "Pattern Finder is checking for a recurring trade-off"; $("#activeCortexCopy").textContent = "It received this question, the recalled decision, and the project summary."; const workButton = $("[data-cortex-work]"); workButton.hidden = false; workButton.textContent = "See work"; workButton.setAttribute("aria-expanded", "false"); cortexRetry.textContent = "Stop"; cortexRetry.removeAttribute("data-cortex-retry"); cortexRetry.setAttribute("data-cortex-stop", ""); return; }
    const cortexSourceRetry = target.closest("[data-cortex-source-retry]"); if (cortexSourceRetry) { cortexSourceRetry.textContent = "Checking source…"; cortexSourceRetry.disabled = true; return; }
    const feelingOpen = target.closest("[data-feeling-open]"); if (feelingOpen) { const id = feelingOpen.dataset.feelingOpen; state.openFeeling = id; persist(); renderFeelings(); requestAnimationFrame(() => { if (window.innerWidth <= 620) { $(`[data-feeling-slider="${id}:${state.feelingsEnabled ? "now" : "nature"}"]`)?.focus({ preventScroll: true }); $("#feelingInspector").scrollIntoView({ behavior: "smooth", block: "start" }); } else $(`[data-feeling-open="${id}"]`)?.focus({ preventScroll: true }); }); return; }
    const range = target.closest("[data-range]"); if (range) { const [id, index] = range.dataset.range.split(":"); state.selectedRanges[id] = Number(index); persist(); renderFeelings(); return; }
    const saveRange = target.closest("[data-save-range]"); if (saveRange) { const [id, index] = saveRange.dataset.saveRange.split(":"); const addition = $(`[data-range-addition="${id}:${index}"]`).value.trim().replace(/\s+/g, " "); if (addition.length > 1200) { showToast("Keep personal nuance under 1,200 characters"); return; } state.feelings[id].additions[index] = addition; persist(); renderFeelings(); showToast(`${bands.find((band) => band.id === id).name} feeling saved`); return; }
    const clearRange = target.closest("[data-clear-range]"); if (clearRange) { const [id, index] = clearRange.dataset.clearRange.split(":"); state.feelings[id].additions[index] = ""; persist(); renderFeelings(); showToast("Personal nuance restored"); return; }
    const resetFeeling = target.closest("[data-reset-feeling]"); if (resetFeeling) { const id = resetFeeling.dataset.resetFeeling; const before = state.feelings[id].now; const after = state.feelings[id].nature; state.feelings[id].now = after; recordChange(id, before, after, "reset_to_nature", "reset"); persist(); renderFeelings(); renderMindFeelings(); renderReactions(); showToast(`${bands.find((band) => band.id === id).name} returned to Nature`); return; }
    const profile = target.closest("[data-profile]"); if (profile) { const selected = profiles.find((item) => item.id === profile.dataset.profile); selected.values.forEach((value, index) => { const id = bands[index].id; const before = state.feelings[id].now; state.feelings[id].nature = value; state.feelings[id].now = value; recordChange(id, before, value, "manual_adjustment", "manual"); }); state.profile = selected.id; setInnerState("Waiting for the next reaction…"); persist(); renderFeelings(); renderMindFeelings(); renderReactions(); renderProfiles(); showToast(`${selected.name} Nature applied`); return; }
    const voice = target.closest("[data-voice]"); if (voice) { state.voice = voice.dataset.voice; persist(); renderVoiceMenu(); $("#voiceMenu").hidden = true; return; }
    const automation = target.closest("[data-automation]"); if (automation && !target.closest(".switch")) { state.automation = state.automation === automation.dataset.automation ? null : automation.dataset.automation; persist(); renderAutomations(); return; }
    const variables = target.closest("[data-show-variables]"); if (variables) { showVariables(variables.dataset.showVariables); return; }
    const insert = target.closest("[data-insert-variable]"); if (insert) { const [id, ...tagParts] = insert.dataset.insertVariable.split(":"); insertVariable(id, tagParts.join(":")); return; }
    const saveAutomation = target.closest("[data-save-automation]"); if (saveAutomation) { const id = saveAutomation.dataset.saveAutomation; const automationItem = automations.find((item) => item.id === id); const prompt = $(`[data-automation-prompt="${id}"]`).value; state.automationOverrides[id] = { ...(state.automationOverrides[id] || {}), prompt, result: automationItem.promptRef.includes("draft") ? "Draft · not live" : "Saved just now" }; persist(); renderAutomations(); showToast(automationItem.promptRef.includes("draft") ? "Draft saved · not live" : "Automation saved"); return; }
    const presenceMode = target.closest("[data-presence-mode]"); if (presenceMode) { state.presence.mode = presenceMode.dataset.presenceMode; persist(); renderPresence(); showToast(state.presence.mode === "direct" ? "Staying present" : "Quiet unless useful"); return; }
    const toast = target.closest("[data-toast]"); if (toast) { showToast(toast.dataset.toast); return; }
  });

  document.addEventListener("change", (event) => {
    const target = event.target;
    const account = target.closest("[data-account-toggle]"); if (account) { const [sourceId, accountId] = account.dataset.accountToggle.split(":"); const source = allSources().find((item) => item.id === sourceId); const item = source.accounts.find((entry) => entry.id === accountId); item.on = account.checked; item.status = account.checked ? "On" : "Off"; saveSourceAccounts(source); persist(); renderConnections(); showToast(`${item.name} ${account.checked ? "on" : "off"}`); return; }
    const slider = target.closest("[data-feeling-slider]"); if (slider) { const field = slider.dataset.feelingSlider; const [id, key] = field.split(":"); const value = Number(slider.value); const before = state.feelings[id][key]; state.feelings[id][key] = value; if (key === "now") recordChange(id, before, value, "manual_adjustment", "manual"); else setInnerState("Waiting for the next reaction…"); state.profile = "custom"; persist(); renderFeelings(); renderMindFeelings(); renderReactions(); renderProfiles(); requestAnimationFrame(() => $(`[data-feeling-slider="${field}"]`)?.focus({ preventScroll: true })); return; }
    const speed = target.closest("[data-return-speed]"); if (speed) { state.feelings[speed.dataset.returnSpeed].minutes = Number(speed.value); persist(); showToast("Return speed saved"); return; }
    const felt = target.closest("[data-felt]"); if (felt) { state.feelings[felt.dataset.felt].felt = felt.checked; persist(); renderFeelingCapsule(); showToast(`${bands.find((band) => band.id === felt.dataset.felt).name} ${felt.checked ? "is felt" : "is no longer felt"}`); return; }
    const automationToggle = target.closest("[data-automation-toggle]"); if (automationToggle) { const id = automationToggle.dataset.automationToggle; state.automationOverrides[id] = { ...(state.automationOverrides[id] || {}), enabled: automationToggle.checked }; persist(); renderAutomations(); return; }
    const automationField = target.closest("[data-automation-field]"); if (automationField) { const [id, key] = automationField.dataset.automationField.split(":"); state.automationOverrides[id] = { ...(state.automationOverrides[id] || {}), [key]: automationField.value, result: "Changed · save when ready" }; persist(); renderAutomations(); return; }
  });

  document.addEventListener("input", (event) => {
    const prompt = event.target.closest("[data-automation-prompt]");
    if (!prompt) return;
    const before = prompt.value.slice(0, prompt.selectionStart ?? 0);
    const open = before.lastIndexOf("{{");
    const close = before.lastIndexOf("}}");
    if (open >= 0 && close < open) showVariables(prompt.dataset.automationPrompt, before.slice(open + 2).trim());
    else { $(`#autocomplete-${prompt.dataset.automationPrompt}`).hidden = true; prompt.setAttribute("aria-expanded", "false"); }
  });

  $("#detectButton").addEventListener("click", startDiscovery);
  $("#cancelDiscovery").addEventListener("click", () => { discoveryTimers.forEach(clearTimeout); $("#discoveryStrip").hidden = true; showToast("Discovery stopped"); });
  $("#connectDetected").addEventListener("click", () => {
    const selected = $$("#detectedList input:checked");
    selected.forEach((checkbox) => {
      const found = discoveredAccounts.find((item) => item.sourceId === checkbox.dataset.detectedSource && item.account.id === checkbox.dataset.detectedAccount);
      const source = allSources().find((item) => item.id === checkbox.dataset.detectedSource);
      if (!found || !source || source.accounts.some((account) => account.id === found.account.id)) return;
      source.accounts.push(structuredClone(found.account));
      saveSourceAccounts(source);
    });
    $("#discoveryResults").hidden = true;
    state.openSource = selected.some((checkbox) => checkbox.dataset.detectedSource === "email") ? "email" : null;
    persist(); renderConnections(); showToast(`${selected.length} sample accounts connected`);
  });
  $("#themeButton").addEventListener("click", () => setTheme({ system: "dark", dark: "light", light: "system" }[state.theme]));
  $("#voicePicker").addEventListener("click", () => { const menu = $("#voiceMenu"); menu.hidden = !menu.hidden; $("#voicePicker").setAttribute("aria-expanded", String(!menu.hidden)); });
  $("#previewVoice").addEventListener("click", (event) => { const button = event.currentTarget; button.classList.add("playing"); button.querySelector("span").textContent = "Playing"; setTimeout(() => { button.classList.remove("playing"); button.querySelector("span").textContent = "Preview"; }, 1700); });
  $("#feelingsEnabled").addEventListener("change", (event) => { state.feelingsEnabled = event.target.checked; persist(); renderFeelings(); renderMindFeelings(); showToast(event.target.checked ? "Feelings are on" : "Feelings are off"); });
  $("#saveReactionInstruction").addEventListener("click", () => { state.reactionActivation = $("#reactionActivation").value; state.reactionInstruction = $("#reactionInstruction").value.trim() || DEFAULT_REACTION_INSTRUCTION; $("#reactionInstruction").value = state.reactionInstruction; persist(); showToast("Reaction Cortex updated"); });
  $("#restoreReactionInstruction").addEventListener("click", () => { $("#reactionInstruction").value = DEFAULT_REACTION_INSTRUCTION; showToast("Default wording restored"); });
  $("#resetFeelings").addEventListener("click", () => { bands.forEach((band) => { const before = state.feelings[band.id].now; const after = state.feelings[band.id].nature; state.feelings[band.id].now = after; recordChange(band.id, before, after, "reset_to_nature", "reset"); }); persist(); renderFeelings(); renderMindFeelings(); renderReactions(); showToast("Current returned to Nature"); });
  $("#pauseFeelings").addEventListener("click", () => { state.feelingsEnabled = !state.feelingsEnabled; $("#feelingsEnabled").checked = state.feelingsEnabled; persist(); renderFeelings(); showToast(state.feelingsEnabled ? "Feelings resumed" : "Feelings paused"); });
  $("#eraseFeelings").addEventListener("click", () => $("#eraseFeelingsDialog").showModal());
  $("#confirmEraseFeelings").addEventListener("click", () => { state.feelingsEnabled = false; state.feelings = structuredClone(defaults.feelings); state.reactions = []; state.profile = "grounded"; state.reactionActivation = defaults.reactionActivation; state.reactionInstruction = DEFAULT_REACTION_INSTRUCTION; setInnerState("Waiting for the next reaction…"); $("#feelingsEnabled").checked = false; $("#reactionActivation").value = state.reactionActivation; $("#reactionInstruction").value = state.reactionInstruction; persist(); renderFeelings(); renderMindFeelings(); renderReactions(); renderProfiles(); showToast("Feelings were turned off and erased"); });
  $("#dropButton").addEventListener("click", () => { const dock = $("#presenceDock"); if (window.innerWidth <= 620 && dock.classList.contains("is-compact") && !dock.classList.contains("mobile-open")) { dock.classList.add("mobile-open"); $("#dropButton").setAttribute("aria-expanded", "true"); renderPresence(); return; } state.presence.in = !state.presence.in; persist(); renderPresence(); showToast(state.presence.in ? "Viventium is listening" : "Viventium dropped out"); });
  $("#muteButton").addEventListener("click", () => { state.presence.muted = !state.presence.muted; persist(); renderPresence(); showToast(state.presence.muted ? "Microphone muted" : "Microphone live"); });
  $(".reply-receipt").addEventListener("toggle", updatePresenceLayout);
  window.addEventListener("resize", updatePresenceLayout);
  $("#composer").addEventListener("submit", (event) => { event.preventDefault(); const input = $("#composerInput"); const text = input.value.trim(); if (!text) return; const article = document.createElement("article"); article.className = "message message-person"; article.innerHTML = `<div><span class="message-author">You</span><p>${esc(text)}</p><div class="message-meta">Now</div></div>`; $("#messages").append(article); input.value = ""; article.scrollIntoView({ behavior: "smooth", block: "nearest" }); showToast("Message added to the prototype"); });
  $("#composerInput").addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); $("#composer").requestSubmit(); } });
  document.addEventListener("keydown", (event) => {
    const rangeTab = event.target.closest?.("[data-range]");
    if (rangeTab && ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      const [id, currentIndexText] = rangeTab.dataset.range.split(":");
      const currentIndex = Number(currentIndexText);
      const nextIndex = event.key === "Home" ? 0 : event.key === "End" ? 4 : Math.max(0, Math.min(4, currentIndex + (["ArrowRight", "ArrowDown"].includes(event.key) ? 1 : -1)));
      state.selectedRanges[id] = nextIndex;
      persist(); renderFeelings();
      requestAnimationFrame(() => $(`[data-range="${id}:${nextIndex}"]`)?.focus());
      return;
    }
    const automationRow = event.target.closest?.("[data-automation]");
    if (automationRow && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      state.automation = state.automation === automationRow.dataset.automation ? null : automationRow.dataset.automation;
      persist(); renderAutomations();
      return;
    }
    if (event.key === "Escape" && $("#presenceDock").classList.contains("mobile-open")) { $("#presenceDock").classList.remove("mobile-open"); $("#dropButton").setAttribute("aria-expanded", "false"); renderPresence(); $("#dropButton").focus(); return; }
    if (event.key === "Escape" && !$("#voiceMenu").hidden) { $("#voiceMenu").hidden = true; $("#voicePicker").setAttribute("aria-expanded", "false"); }
  });

  renderAll();
})();
