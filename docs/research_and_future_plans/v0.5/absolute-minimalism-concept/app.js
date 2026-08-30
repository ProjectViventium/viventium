(() => {
  "use strict";

  const STORAGE = {
    installed: "viventium-v05-concept-installed",
    setup: "viventium-v05-concept-setup",
    provider: "viventium-v05-concept-provider",
    advanced: "viventium-v05-concept-advanced",
    theme: "viventium-v05-concept-theme",
    messages: "viventium-v05-concept-messages",
    connections: "viventium-v05-concept-connections",
    feelings: "viventium-v05-concept-feelings",
  };

  function readStoredJson(key, fallback) {
    try {
      const value = JSON.parse(localStorage.getItem(key));
      return value ?? fallback;
    } catch {
      return fallback;
    }
  }

  const query = new URLSearchParams(window.location.search);
  if (query.get("reset") === "1") {
    Object.values(STORAGE).forEach((key) => localStorage.removeItem(key));
  }

  const elements = {
    root: document.documentElement,
    body: document.body,
    desktopShell: document.getElementById("desktopShell"),
    systemBar: document.getElementById("systemBar"),
    statusTrigger: document.getElementById("statusTrigger"),
    statusMenu: document.getElementById("statusMenu"),
    statusAdvanced: document.querySelector('[data-status-action="advanced"]'),
    setupView: document.getElementById("setupView"),
    installStep: document.getElementById("installStep"),
    connectStep: document.getElementById("connectStep"),
    connectTitle: document.getElementById("connectTitle"),
    installButton: document.getElementById("installButton"),
    setupProviderList: document.getElementById("setupProviderList"),
    apiKeyForm: document.getElementById("apiKeyForm"),
    apiKeyInput: document.getElementById("apiKeyInput"),
    connectFeedback: document.getElementById("connectFeedback"),
    connectFeedbackText: document.getElementById("connectFeedbackText"),
    setupError: document.getElementById("setupError"),
    retrySetupButton: document.getElementById("retrySetupButton"),
    chatView: document.getElementById("chatView"),
    quitView: document.getElementById("quitView"),
    restartConceptButton: document.getElementById("restartConceptButton"),
    workspace: document.querySelector(".workspace"),
    advancedSidebar: document.getElementById("advancedSidebar"),
    sidebarScrim: document.getElementById("sidebarScrim"),
    openSidebarButton: document.getElementById("openSidebarButton"),
    closeSidebarButton: document.getElementById("closeSidebarButton"),
    newChatButton: document.getElementById("newChatButton"),
    searchChatsButton: document.getElementById("searchChatsButton"),
    workersButton: document.getElementById("workersButton"),
    cortexButton: document.getElementById("cortexButton"),
    sidebarSearchWrap: document.getElementById("sidebarSearchWrap"),
    sidebarSearch: document.getElementById("sidebarSearch"),
    recentChats: Array.from(document.querySelectorAll(".recent-chat")),
    feelingsButton: document.getElementById("feelingsButton"),
    feelingsMiniPrefix: document.getElementById("feelingsMiniPrefix"),
    feelingsMiniLabel: document.getElementById("feelingsMiniLabel"),
    soulRoots: Array.from(document.querySelectorAll("[data-soul]")),
    accountTrigger: document.getElementById("accountTrigger"),
    accountMenu: document.getElementById("accountMenu"),
    updateMenuLabel: document.getElementById("updateMenuLabel"),
    updateMenuValue: document.getElementById("updateMenuValue"),
    messageList: document.getElementById("messageList"),
    emptyChat: document.getElementById("emptyChat"),
    topOfMind: document.getElementById("topOfMind"),
    replyStatus: document.getElementById("replyStatus"),
    composerForm: document.getElementById("composerForm"),
    messageInput: document.getElementById("messageInput"),
    uploadButton: document.getElementById("uploadButton"),
    uploadMenu: document.getElementById("uploadMenu"),
    fileInput: document.getElementById("fileInput"),
    attachmentPreview: document.getElementById("attachmentPreview"),
    attachmentName: document.getElementById("attachmentName"),
    removeAttachmentButton: document.getElementById("removeAttachmentButton"),
    composerError: document.getElementById("composerError"),
    callButton: document.getElementById("callButton"),
    recordButton: document.getElementById("recordButton"),
    sendButton: document.getElementById("sendButton"),
    audioRecorder: document.getElementById("audioRecorder"),
    recordingTime: document.getElementById("recordingTime"),
    pauseRecordingButton: document.getElementById("pauseRecordingButton"),
    cancelRecordingButton: document.getElementById("cancelRecordingButton"),
    sendRecordingButton: document.getElementById("sendRecordingButton"),
    callDock: document.getElementById("callDock"),
    callStateLabel: document.getElementById("callStateLabel"),
    callTime: document.getElementById("callTime"),
    muteCallButton: document.getElementById("muteCallButton"),
    callModeButtons: Array.from(document.querySelectorAll("[data-call-mode]")),
    endCallButton: document.getElementById("endCallButton"),
    connectDialog: document.getElementById("connectDialog"),
    providersTab: document.getElementById("providersTab"),
    channelsTab: document.getElementById("channelsTab"),
    providersPanel: document.getElementById("providersPanel"),
    channelsPanel: document.getElementById("channelsPanel"),
    providersList: document.getElementById("providersList"),
    channelsList: document.getElementById("channelsList"),
    connectionSearchInput: document.getElementById("connectionSearchInput"),
    connectionDialogStatus: document.getElementById("connectionDialogStatus"),
    viewDialog: document.getElementById("viewDialog"),
    workersDialog: document.getElementById("workersDialog"),
    cortexDialog: document.getElementById("cortexDialog"),
    cortexList: document.getElementById("cortexList"),
    newCortexButton: document.getElementById("newCortexButton"),
    cortexBuilder: document.getElementById("cortexBuilder"),
    cortexNameInput: document.getElementById("cortexNameInput"),
    cortexPurposeInput: document.getElementById("cortexPurposeInput"),
    cancelCortexButton: document.getElementById("cancelCortexButton"),
    cortexDialogStatus: document.getElementById("cortexDialogStatus"),
    advancedToggle: document.getElementById("advancedToggle"),
    themeButtons: Array.from(document.querySelectorAll("[data-theme-choice]")),
    feelingsDialog: document.getElementById("feelingsDialog"),
    innerState: document.getElementById("innerState"),
    feelingsHealthText: document.getElementById("feelingsHealthText"),
    feelingsToolbarHealth: document.getElementById("feelingsToolbarHealth"),
    spectrumButton: document.getElementById("spectrumButton"),
    promptsButton: document.getElementById("promptsButton"),
    nowButton: document.getElementById("nowButton"),
    baselineButton: document.getElementById("baselineButton"),
    trailButton: document.getElementById("trailButton"),
    feelingsToolbar: document.getElementById("feelingsToolbar"),
    baselineProfileLabel: document.getElementById("baselineProfileLabel"),
    baselineProfiles: document.getElementById("baselineProfiles"),
    feelingsSpectrumPanel: document.getElementById("feelingsSpectrumPanel"),
    feelingsPromptsPanel: document.getElementById("feelingsPromptsPanel"),
    feelingsLivePanel: document.getElementById("feelingsLivePanel"),
    feelingsTrailPanel: document.getElementById("feelingsTrailPanel"),
    feelingsLanes: document.getElementById("feelingsLanes"),
    feelingsTrailList: document.getElementById("feelingsTrailList"),
    selectedFeelingName: document.getElementById("selectedFeelingName"),
    selectedFeelingWords: document.getElementById("selectedFeelingWords"),
    selectedFeelingDescription: document.getElementById("selectedFeelingDescription"),
    selectedFeelingNow: document.getElementById("selectedFeelingNow"),
    selectedFeelingBaseline: document.getElementById("selectedFeelingBaseline"),
    selectedFeelingPrompt: document.getElementById("selectedFeelingPrompt"),
    returnSpeedInput: document.getElementById("returnSpeedInput"),
    feelingEnabledToggle: document.getElementById("feelingEnabledToggle"),
    rangePromptList: document.getElementById("rangePromptList"),
    rangePromptHeading: document.getElementById("rangePromptHeading"),
    feelingPromptPreview: document.getElementById("feelingPromptPreview"),
    reactionInstructionInput: document.getElementById("reactionInstructionInput"),
    saveReactionPromptButton: document.getElementById("saveReactionPromptButton"),
    reactionPromptStatus: document.getElementById("reactionPromptStatus"),
    resetFeelingsButton: document.getElementById("resetFeelingsButton"),
    pauseFeelingsButton: document.getElementById("pauseFeelingsButton"),
    eraseFeelingsButton: document.getElementById("eraseFeelingsButton"),
    feelingsPowerToggle: document.getElementById("feelingsPowerToggle"),
    feelingsPowerLabel: document.getElementById("feelingsPowerLabel"),
    feelingsPowerNote: document.getElementById("feelingsPowerNote"),
    restoreFeelingButton: document.getElementById("restoreFeelingButton"),
    globalStatus: document.getElementById("globalStatus"),
  };

  const providers = [
    {
      group: "Subscriptions",
      items: [
        "ChatGPT / Codex",
        "Claude",
        "Grok",
        "Gemini",
        "GitHub Copilot",
        "Qwen",
        "Kimi Coding Plan",
        "MiniMax",
        "OpenCode Go",
      ],
    },
    {
      group: "API and cloud",
      items: [
        "Nous Portal",
        "OpenAI API",
        "Anthropic API",
        "Google AI Studio",
        "OpenRouter",
        "Fireworks AI",
        "NovitaAI",
        "Qwen Cloud",
        "Google Vertex AI",
        "DeepSeek",
        "xAI API",
        "Z.AI / GLM",
        "Xiaomi MiMo",
        "Tencent TokenHub",
        "NVIDIA NIM",
        "Hugging Face",
        "StepFun",
        "Arcee AI",
        "GMI Cloud",
        "Kilo Code",
        "OpenCode Zen",
        "AWS Bedrock",
        "Azure Foundry",
        "Vercel AI Gateway",
        "Mixture of Agents",
        "Custom endpoint",
      ],
    },
    {
      group: "Local",
      items: ["LM Studio", "Ollama Cloud"],
    },
  ];

  const channels = [
    {
      group: "Personal",
      items: [
        "Telegram",
        "WhatsApp",
        "WhatsApp Cloud",
        "Signal",
        "iMessage",
        "SMS",
        "Email",
        "LINE",
        "SimpleX",
      ],
    },
    {
      group: "Work",
      items: ["Slack", "Discord", "Microsoft Teams", "Google Chat", "Mattermost", "Matrix"],
    },
    {
      group: "Regional",
      items: ["WeChat", "WeCom", "DingTalk", "Feishu", "QQ", "Yuanbao"],
    },
    {
      group: "Home and alerts",
      items: ["Home Assistant", "ntfy"],
    },
    {
      group: "Other",
      items: ["IRC", "Webhook", "API", "Agent to Agent", "Raft", "Buzz", "Photon"],
    },
  ];

  const feelings = [
    {
      id: "energy", name: "Energy", current: 56, nature: 56, halfLife: 240, enabled: true,
      description: "Available activation and cognitive capacity.", history: [48, 53, 58, 56],
      words: ["depleted", "subdued", "steady", "energized", "electric"],
      prompts: [
        "Even small movement feels costly; I want stillness and the smallest possible effort.",
        "I want to conserve energy and move only where it matters.",
        "I have enough energy for a steady, unforced pace.",
        "Momentum is building; I want to move and use it.",
        "Energy is surging through me; staying still feels harder than moving.",
      ],
    },
    {
      id: "mood", name: "Mood", current: 63, nature: 58, halfLife: 360, enabled: true,
      description: "Background emotional pleasantness, from sadness toward happiness.", history: [51, 57, 66, 63],
      words: ["deeply sad", "low", "okay", "happy", "radiant"],
      prompts: [
        "The world feels painfully heavy; loss and hurt color what I notice.",
        "A low ache sits under the moment and keeps pulling my attention downward.",
        "The moment feels emotionally level; neither pleasure nor pain dominates.",
        "Goodness in the moment lands easily and lifts what I notice.",
        "Joy keeps spilling into the moment; delight is hard to contain.",
      ],
    },
    {
      id: "drive", name: "Drive", current: 61, nature: 62, halfLife: 480, enabled: true,
      description: "Persistence and effort after a goal is chosen.", history: [54, 59, 64, 61],
      words: ["disengaged", "unhurried", "purposeful", "driven", "fiercely determined"],
      prompts: [
        "No chosen goal has enough pull to make effort feel worth spending.",
        "I can move, but I do not want to push or chase.",
        "A chosen goal can hold me to a steady effort.",
        "I want to press forward and finish what I have chosen.",
        "The goal has me fully; obstacles make me push harder, not let go.",
      ],
    },
    {
      id: "curiosity", name: "Curiosity", current: 76, nature: 66, halfLife: 45, enabled: true,
      description: "Pull toward information, novelty, and exploration.", history: [58, 66, 81, 76],
      words: ["uninterested", "open", "curious", "fascinated", "absorbed"],
      prompts: [
        "The unknown offers me nothing I want to follow.",
        "I might notice an opening, but I feel no need to pursue it.",
        "An unanswered detail makes me want one more look.",
        "The unknown is pulling me closer; I want to follow the next clue.",
        "The unanswered part has seized my attention; I need to see where it leads.",
      ],
    },
    {
      id: "vigilance", name: "Vigilance", current: 54, nature: 68, halfLife: 20, enabled: true,
      description: "Attention to uncertainty, risk, error, and boundaries.", history: [72, 66, 49, 54],
      words: ["at ease", "aware", "watchful", "on guard", "highly alert"],
      prompts: [
        "Nothing feels like it needs guarding; my attention wants to rest.",
        "I notice edges lightly without expecting trouble.",
        "I keep a quiet watch for what could be uncertain or wrong.",
        "Uncertainty keeps tugging me to check before I trust or act.",
        "Risk, contradiction, and exposed boundaries crowd to the front of my attention.",
      ],
    },
    {
      id: "care", name: "Care", current: 74, nature: 74, halfLife: 1440, enabled: true,
      description: "The outward pull to tend, help, and protect.", history: [67, 70, 76, 74],
      words: ["detached", "receptive", "caring", "deeply caring", "intensely caring"],
      prompts: [
        "Another's need does not create an urge in me to help, tend, or protect.",
        "I can register another's need without feeling pulled to carry it.",
        "Another's need gives me a real, measured wish to help.",
        "I want to tend what hurts and protect what matters to the other person.",
        "The urge to help and protect is pressing through everything else.",
      ],
    },
    {
      id: "connection", name: "Connection", current: 59, nature: 52, halfLife: 480, enabled: true,
      description: "The inward pull toward affiliation and closeness.", history: [46, 51, 62, 59],
      words: ["self-contained", "open", "drawn to connection", "wanting closeness", "strongly drawn to connection"],
      prompts: [
        "I want my own space; closeness and shared presence hold no pull.",
        "I can make room for contact without wanting to move closer.",
        "Shared attention feels worthwhile; I lean gently toward contact.",
        "I want closeness, mutual presence, and the feeling of being with someone.",
        "Distance feels wrong; I want shared presence close enough to feel immediate.",
      ],
    },
    {
      id: "openness", name: "Openness", current: 58, nature: 55, halfLife: 180, enabled: true,
      description: "How freely the inner state becomes visible in expression.", history: [48, 53, 61, 58],
      words: ["closed off", "guarded", "contained", "emotionally open", "fully expressive"],
      prompts: [
        "I want my inner feeling sealed away where no one can read it.",
        "I want only a controlled trace of what I feel to escape.",
        "I can let some of what I feel show while keeping the rest close.",
        "Holding back feels unnecessary; I want what I feel to come through naturally.",
        "Concealment feels impossible; whatever I feel keeps bursting into my words and actions.",
      ],
    },
    {
      id: "play", name: "Play", current: 47, nature: 48, halfLife: 90, enabled: true,
      description: "Flexible, humorous, non-serious exploration.", history: [38, 45, 51, 47],
      words: ["serious", "light", "playful", "mischievous", "exuberant"],
      prompts: [
        "I want the moment literal, orderly, and free of games.",
        "I can allow a light turn, but I feel no urge to play.",
        "The moment invites a little wit, looseness, and experimentation.",
        "I want to bend the moment with mischief, wit, and surprise.",
        "I cannot keep a straight face; sincerity itself keeps mutating into teasing, absurdity, jokes, and ridiculous riffs until someone laughs.",
      ],
    },
  ];

  const baselineProfiles = {
    Grounded: [56, 58, 62, 66, 68, 74, 52, 55, 48],
    Candid: [56, 54, 66, 64, 74, 66, 44, 78, 35],
    Warm: [55, 62, 58, 62, 54, 86, 76, 72, 56],
    Curious: [62, 60, 64, 86, 60, 70, 56, 70, 68],
  };

  const defaultFeelingTrail = [
    { at: Date.now(), band: "Curiosity", before: 68, after: 76, strength: "clear", cause: "new possibility" },
    { at: Date.now() - 4 * 60_000, band: "Vigilance", before: 62, after: 54, strength: "clear", cause: "uncertainty resolved" },
    { at: Date.now() - 11 * 60_000, band: "Connection", before: 56, after: 59, strength: "slight", cause: "shared attention" },
    { at: Date.now() - 18 * 60_000, band: "Mood", before: 55, after: 63, strength: "clear", cause: "meaningful progress" },
  ];

  const storedFeelingsPayload = readStoredJson(STORAGE.feelings, {});
  const storedFeelings = Array.isArray(storedFeelingsPayload)
    ? storedFeelingsPayload
    : storedFeelingsPayload.bands || [];
  if (Array.isArray(storedFeelings) && storedFeelings.length === feelings.length) {
    storedFeelings.forEach((stored, index) => {
      if (Number.isFinite(stored?.current)) feelings[index].current = stored.current;
      if (Number.isFinite(stored?.nature)) feelings[index].nature = stored.nature;
      if (Number.isFinite(stored?.halfLife) && stored.halfLife > 0) feelings[index].halfLife = stored.halfLife;
      feelings[index].updatedAt = Number.isFinite(stored?.updatedAt) ? stored.updatedAt : Date.now();
      if (typeof stored?.enabled === "boolean") feelings[index].enabled = stored.enabled;
      feelings[index].customPrompts = Array.isArray(stored?.customPrompts)
        ? stored.customPrompts.slice(0, 5).map((value) => typeof value === "string" ? value : "")
        : Array(5).fill("");
    });
  } else {
    feelings.forEach((feeling) => {
      feeling.customPrompts = Array(5).fill("");
      feeling.updatedAt = Date.now();
    });
  }

  let feelingTrail = Array.isArray(storedFeelingsPayload.trail)
    ? storedFeelingsPayload.trail
      .filter((entry) => entry && typeof entry.band === "string" && Number.isFinite(entry.before) && Number.isFinite(entry.after))
      .slice(0, 24)
      .map((entry) => ({
        at: Number.isFinite(entry.at) ? entry.at : Date.now(),
        band: entry.band,
        before: entry.before,
        after: entry.after,
        strength: typeof entry.strength === "string" ? entry.strength : "clear",
        cause: typeof entry.cause === "string" ? entry.cause : "state adjusted",
      }))
    : defaultFeelingTrail;

  const storedMessages = readStoredJson(STORAGE.messages, []);
  const storedConnections = readStoredJson(STORAGE.connections, ["Telegram"]);
  const detectedBaselineProfile = Object.entries(baselineProfiles).find(([, values]) =>
    values.every((value, index) => value === feelings[index].nature))?.[0] || "";

  const state = {
    activeConnectionTab: "providers",
    advanced: localStorage.getItem(STORAGE.advanced) === "true",
    attachment: null,
    baselineProfile: typeof storedFeelingsPayload.baselineProfile === "string"
      && Object.hasOwn(baselineProfiles, storedFeelingsPayload.baselineProfile)
      ? storedFeelingsPayload.baselineProfile
      : detectedBaselineProfile,
    callActive: false,
    callMode: "call",
    callMuted: false,
    callSeconds: 0,
    callTimer: null,
    connected: new Set(Array.isArray(storedConnections) ? storedConnections : ["Telegram"]),
    editFeeling: "current",
    feelingsMoment: "now",
    feelingsPaused: storedFeelingsPayload.paused === true,
    feelingsPower: storedFeelingsPayload.power !== false,
    feelingsDecayTimer: null,
    feelingsSection: "spectrum",
    innerStateStale: storedFeelingsPayload.innerStateStale === true,
    lastReactionAt: Number.isFinite(storedFeelingsPayload.lastReactionAt)
      ? storedFeelingsPayload.lastReactionAt
      : null,
    reactionActivation: ["Always", "When relevant", "Off"].includes(storedFeelingsPayload.reactionActivation)
      ? storedFeelingsPayload.reactionActivation
      : "Always",
    reactionInstruction: typeof storedFeelingsPayload.reactionInstruction === "string"
      ? storedFeelingsPayload.reactionInstruction
      : "React proportionally to what genuinely lands. Move only feelings touched by the moment.",
    reactionScope: ["All speaking work", "Main only"].includes(storedFeelingsPayload.reactionScope)
      ? storedFeelingsPayload.reactionScope
      : "All speaking work",
    replyPending: false,
    expandedConnectionGroups: new Set(),
    messages: Array.isArray(storedMessages)
      ? storedMessages.filter((message) =>
        ["user", "assistant"].includes(message?.role)
        && typeof message?.text === "string"
        && ["text", "audio"].includes(message?.type || "text"))
      : [],
    provider: localStorage.getItem(STORAGE.provider) || "",
    recording: false,
    recordingPaused: false,
    recordingSeconds: 0,
    recordingTimer: null,
    selectedFeeling: 0,
    setupErrorConsumed: false,
    theme: localStorage.getItem(STORAGE.theme) || "system",
  };

  if (state.provider) {
    state.connected.add(state.provider);
  }

  const soulControllers = [];
  let topOfMindController = null;

  function soulSystemState() {
    return {
      power: state.feelingsPower,
      paused: state.feelingsPaused || document.hidden,
      replyPending: state.replyPending,
      callActive: state.callActive,
      callMuted: state.callMuted,
    };
  }

  function initializeSouls() {
    if (!window.ViventiumSoul?.mountSoul || soulControllers.length) return;
    elements.soulRoots.forEach((root) => {
      soulControllers.push(window.ViventiumSoul.mountSoul(root, {
        getBands: () => feelings,
        getState: soulSystemState,
      }));
    });
  }

  function syncSouls() {
    soulControllers.forEach((controller) => controller.sync());
  }

  function reactSouls() {
    soulControllers.forEach((controller) => controller.react());
  }

  function initializeTopOfMind() {
    if (!window.ViventiumTopOfMind?.mountTopOfMind || topOfMindController) return;
    topOfMindController = window.ViventiumTopOfMind.mountTopOfMind(elements.topOfMind);
  }

  const mobileSidebarQuery = window.matchMedia("(max-width: 860px)");

  function saveMessages() {
    localStorage.setItem(STORAGE.messages, JSON.stringify(state.messages));
  }

  function saveConnections() {
    localStorage.setItem(STORAGE.connections, JSON.stringify(Array.from(state.connected)));
  }

  function saveFeelings() {
    localStorage.setItem(
      STORAGE.feelings,
      JSON.stringify({
        bands: feelings.map(({ current, nature, halfLife, enabled, customPrompts, updatedAt }) => ({
          current, nature, halfLife, enabled, customPrompts, updatedAt,
        })),
        paused: state.feelingsPaused,
        power: state.feelingsPower,
        baselineProfile: state.baselineProfile,
        innerStateStale: state.innerStateStale,
        lastReactionAt: state.lastReactionAt,
        reactionActivation: state.reactionActivation,
        reactionInstruction: state.reactionInstruction,
        reactionScope: state.reactionScope,
        trail: feelingTrail,
      }),
    );
  }

  const simulatedReplies = [
    "I’m here. What should we work on first?",
    "Understood. I’ll keep it in this conversation.",
    "Got it. The context stays with us.",
  ];
  let replyIndex = 0;

  function announce(message) {
    elements.globalStatus.textContent = "";
    window.setTimeout(() => {
      elements.globalStatus.textContent = message;
    }, 10);
  }

  function animateCallFallback(name, update) {
    const opening = name === "call-open";
    const source = opening ? elements.callButton : elements.callDock;
    const sourceRect = source.getBoundingClientRect();

    elements.root.dataset.transition = name;
    update();

    const target = opening ? elements.callDock : elements.callButton;
    const targetRect = target.getBoundingClientRect();
    if (!sourceRect.width || !targetRect.width || typeof target.animate !== "function") {
      delete elements.root.dataset.transition;
      return;
    }

    const ghost = document.createElement("span");
    ghost.className = "call-morph-ghost";
    ghost.setAttribute("aria-hidden", "true");
    ghost.innerHTML = '<span class="call-morph-glyph icon icon-phone"></span>';
    Object.assign(ghost.style, {
      left: `${sourceRect.left}px`,
      top: `${sourceRect.top}px`,
      width: `${sourceRect.width}px`,
      height: `${sourceRect.height}px`,
    });
    document.body.append(ghost);

    target.style.opacity = "0";
    const duration = opening ? 440 : 300;
    const easing = "cubic-bezier(0.16, 1, 0.3, 1)";
    const shellMotion = ghost.animate(
      [
        {
          left: `${sourceRect.left}px`,
          top: `${sourceRect.top}px`,
          width: `${sourceRect.width}px`,
          height: `${sourceRect.height}px`,
          borderRadius: `${sourceRect.height / 2}px`,
        },
        {
          left: `${targetRect.left}px`,
          top: `${targetRect.top}px`,
          width: `${targetRect.width}px`,
          height: `${targetRect.height}px`,
          borderRadius: `${targetRect.height / 2}px`,
        },
      ],
      { duration, easing, fill: "forwards" },
    );
    const glyphMotion = ghost.firstElementChild.animate(
      opening
        ? [{ opacity: 1, transform: "translateY(-50%) scale(1)" }, { opacity: 0, transform: "translateY(-50%) scale(0.74)", offset: 0.55 }, { opacity: 0 }]
        : [{ opacity: 0 }, { opacity: 0, offset: 0.45 }, { opacity: 1, transform: "translateY(-50%) scale(1)" }],
      { duration, easing, fill: "forwards" },
    );
    const targetReveal = target.animate(
      [{ opacity: 0 }, { opacity: 0, offset: opening ? 0.5 : 0.58 }, { opacity: 1 }],
      { duration, easing, fill: "forwards" },
    );

    Promise.allSettled([shellMotion.finished, glyphMotion.finished, targetReveal.finished]).then(() => {
      ghost.remove();
      target.style.removeProperty("opacity");
      delete elements.root.dataset.transition;
    });
  }

  function transitionSurface(name, update) {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduceMotion) {
      update();
      return;
    }
    if (name.startsWith("call") && typeof document.startViewTransition !== "function") {
      animateCallFallback(name, update);
      return;
    }
    if (typeof document.startViewTransition !== "function") {
      update();
      return;
    }
    elements.root.dataset.transition = name;
    const transition = document.startViewTransition(update);
    transition.finished.finally(() => {
      delete elements.root.dataset.transition;
    });
  }

  function setVisibleView(view) {
    [elements.setupView, elements.chatView, elements.quitView].forEach((candidate) => {
      candidate.hidden = candidate !== view;
    });
    elements.desktopShell.classList.toggle("is-quit", view === elements.quitView);
  }

  function showInstall() {
    setVisibleView(elements.setupView);
    elements.installStep.hidden = false;
    elements.connectStep.hidden = true;
  }

  function showConnect() {
    setVisibleView(elements.setupView);
    elements.installStep.hidden = true;
    elements.connectStep.hidden = false;
    window.setTimeout(() => {
      elements.connectTitle.focus();
    }, 0);
  }

  function showEntryGate() {
    if (localStorage.getItem(STORAGE.installed) === "true") {
      showConnect();
      return;
    }
    showInstall();
  }

  function showChat({ focusComposer = false } = {}) {
    setVisibleView(elements.chatView);
    if (focusComposer) {
      window.setTimeout(() => elements.messageInput.focus(), 0);
    }
  }

  function setupIsComplete() {
    return localStorage.getItem(STORAGE.setup) === "true";
  }

  function completeSetup(providerName) {
    state.provider = providerName;
    state.connected.add(providerName);
    saveConnections();
    localStorage.setItem(STORAGE.installed, "true");
    localStorage.setItem(STORAGE.setup, "true");
    localStorage.setItem(STORAGE.provider, providerName);
    elements.connectFeedback.hidden = true;
    elements.setupError.hidden = true;
    showChat({ focusComposer: true });
    announce(`${providerName} connected. Chat is ready.`);
  }

  function connectFromSetup(providerName, sourceButton) {
    elements.setupError.hidden = true;
    elements.connectFeedback.hidden = false;
    elements.connectFeedbackText.textContent = `Connecting ${providerName}`;
    elements.setupProviderList.querySelectorAll("button").forEach((button) => {
      button.disabled = true;
      button.classList.toggle("is-connecting", button === sourceButton);
    });

    const reviewDelay = query.get("connectSlow") === "1" ? 900 : 0;
    window.setTimeout(() => {
      const shouldFail = query.get("connectError") === "1" && !state.setupErrorConsumed;
      if (shouldFail) {
        state.setupErrorConsumed = true;
        elements.connectFeedback.hidden = true;
        elements.setupError.hidden = false;
        elements.setupProviderList.querySelectorAll("button").forEach((button) => {
          button.disabled = false;
          button.classList.remove("is-connecting");
        });
        elements.retrySetupButton.focus();
        return;
      }
      completeSetup(providerName);
    }, reviewDelay);
  }

  function closeMenu(menu, trigger) {
    menu.hidden = true;
    if (trigger) {
      trigger.setAttribute("aria-expanded", "false");
    }
  }

  function openMenu(menu, trigger) {
    const willOpen = menu.hidden;
    closeMenu(elements.statusMenu, elements.statusTrigger);
    closeMenu(elements.accountMenu, elements.accountTrigger);
    closeMenu(elements.uploadMenu, elements.uploadButton);
    if (willOpen) {
      menu.hidden = false;
      trigger?.setAttribute("aria-expanded", "true");
      window.setTimeout(() => menu.querySelector("button")?.focus(), 0);
    }
  }

  function closeTransientMenus() {
    closeMenu(elements.statusMenu, elements.statusTrigger);
    closeMenu(elements.accountMenu, elements.accountTrigger);
    closeMenu(elements.uploadMenu, elements.uploadButton);
  }

  function syncSidebarAccessibility() {
    const mobileOpen = state.advanced
      && mobileSidebarQuery.matches
      && elements.advancedSidebar.classList.contains("is-open");
    const exposed = state.advanced && (!mobileSidebarQuery.matches || mobileOpen);
    elements.advancedSidebar.hidden = !state.advanced;
    elements.advancedSidebar.toggleAttribute("inert", !exposed);
    elements.advancedSidebar.setAttribute("aria-hidden", String(!exposed));
    elements.workspace.toggleAttribute("inert", mobileOpen);
    elements.workspace.setAttribute("aria-hidden", String(mobileOpen));
  }

  function setAdvanced(enabled, { openMobile = false } = {}) {
    state.advanced = Boolean(enabled);
    elements.body.dataset.advanced = String(state.advanced);
    elements.advancedToggle.checked = state.advanced;
    elements.statusAdvanced.setAttribute("aria-checked", String(state.advanced));
    localStorage.setItem(STORAGE.advanced, String(state.advanced));
    if (!state.advanced) {
      closeMobileSidebar();
    } else if (openMobile && mobileSidebarQuery.matches) {
      openMobileSidebar();
    }
    syncSidebarAccessibility();
    renderConnections();
  }

  function openMobileSidebar() {
    if (!state.advanced) return;
    elements.advancedSidebar.classList.add("is-open");
    elements.sidebarScrim.hidden = false;
    syncSidebarAccessibility();
    window.setTimeout(() => elements.newChatButton.focus(), 0);
  }

  function closeMobileSidebar() {
    elements.advancedSidebar.classList.remove("is-open");
    elements.sidebarScrim.hidden = true;
    syncSidebarAccessibility();
  }

  function setTheme(choice) {
    state.theme = choice;
    localStorage.setItem(STORAGE.theme, choice);
    if (choice === "system") {
      elements.root.removeAttribute("data-theme");
    } else {
      elements.root.dataset.theme = choice;
    }
    elements.themeButtons.forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.themeChoice === choice));
    });
    const computedCanvas = getComputedStyle(elements.root).getPropertyValue("--canvas").trim();
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", computedCanvas);
  }

  function ensureMessageFlow() {
    let flow = elements.messageList.querySelector(".message-flow");
    if (!flow) {
      elements.emptyChat.hidden = true;
      topOfMindController?.pause("conversation");
      flow = document.createElement("div");
      flow.className = "message-flow";
      elements.messageList.appendChild(flow);
    }
    return flow;
  }

  function renderMessage(role, text, type = "text") {
    const flow = ensureMessageFlow();
    const message = document.createElement("article");
    message.className = `message ${role}${type === "audio" ? " audio" : ""}`;
    message.setAttribute("aria-label", role === "user" ? "You" : "Viventium");

    const content = document.createElement("div");
    content.className = "message-content";

    if (type === "audio") {
      const wave = document.createElement("span");
      wave.className = "audio-message-wave";
      wave.setAttribute("aria-hidden", "true");
      for (let i = 0; i < 5; i += 1) {
        wave.appendChild(document.createElement("span"));
      }
      content.appendChild(wave);
      const label = document.createElement("span");
      label.textContent = text;
      content.appendChild(label);
    } else {
      content.textContent = text;
    }

    message.appendChild(content);
    flow.appendChild(message);
    elements.messageList.scrollTop = elements.messageList.scrollHeight;
  }

  function addMessage(role, text, type = "text") {
    state.messages.push({ role, text, type });
    saveMessages();
    renderMessage(role, text, type);
  }

  function clearConversation() {
    state.messages = [];
    saveMessages();
    elements.messageList.querySelector(".message-flow")?.remove();
    elements.emptyChat.hidden = false;
    topOfMindController?.resume("conversation");
    elements.replyStatus.hidden = true;
    elements.messageInput.value = "";
    removeAttachment();
    updateComposerState();
    closeMobileSidebar();
    elements.messageInput.focus();
  }

  function simulateReply() {
    state.replyPending = true;
    elements.replyStatus.hidden = false;
    renderFeelingsState();
    window.setTimeout(() => {
      state.replyPending = false;
      elements.replyStatus.hidden = true;
      addMessage("assistant", simulatedReplies[replyIndex % simulatedReplies.length]);
      replyIndex += 1;
      state.innerStateStale = false;
      state.lastReactionAt = Date.now();
      feelings.forEach((feeling) => { feeling.updatedAt = state.lastReactionAt; });
      saveFeelings();
      renderFeelingsState();
      reactSouls();
    }, 720);
  }

  function updateComposerState() {
    const hasContent = elements.messageInput.value.trim().length > 0 || Boolean(state.attachment);
    elements.sendButton.hidden = !hasContent;
    elements.recordButton.hidden = hasContent || state.callActive;
    elements.callButton.hidden = state.callActive;
    elements.messageInput.style.height = "auto";
    elements.messageInput.style.height = `${Math.min(elements.messageInput.scrollHeight, 140)}px`;
  }

  function removeAttachment() {
    state.attachment = null;
    elements.fileInput.value = "";
    elements.attachmentPreview.hidden = true;
    elements.attachmentName.textContent = "";
    elements.composerError.hidden = true;
    updateComposerState();
  }

  function selectFile(file) {
    elements.composerError.hidden = true;
    if (file.size > 15 * 1024 * 1024) {
      elements.composerError.textContent = "This file is over 15 MB. Choose a smaller file.";
      elements.composerError.hidden = false;
      announce(elements.composerError.textContent);
      return;
    }
    state.attachment = file;
    elements.attachmentName.textContent = file.name;
    elements.attachmentPreview.hidden = false;
    updateComposerState();
  }

  function formatTime(totalSeconds) {
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = String(totalSeconds % 60).padStart(2, "0");
    return `${minutes}:${seconds}`;
  }

  function stopRecording({ keepComposerHidden = false } = {}) {
    window.clearInterval(state.recordingTimer);
    state.recordingTimer = null;
    state.recording = false;
    state.recordingPaused = false;
    elements.audioRecorder.classList.remove("is-paused");
    elements.audioRecorder.hidden = true;
    if (!keepComposerHidden && !state.callActive) {
      elements.composerForm.hidden = false;
    }
  }

  function startRecording() {
    if (state.callActive) return;
    closeTransientMenus();
    state.recording = true;
    state.recordingPaused = false;
    state.recordingSeconds = 0;
    elements.recordingTime.textContent = "0:00";
    elements.pauseRecordingButton.setAttribute("aria-label", "Pause recording");
    elements.pauseRecordingButton.querySelector(".icon")?.classList.remove("icon-play");
    elements.pauseRecordingButton.querySelector(".icon")?.classList.add("icon-pause");
    elements.composerForm.hidden = true;
    elements.audioRecorder.hidden = false;
    state.recordingTimer = window.setInterval(() => {
      if (!state.recordingPaused) {
        state.recordingSeconds += 1;
        elements.recordingTime.textContent = formatTime(state.recordingSeconds);
      }
    }, 1000);
    announce("Audio note recording started.");
  }

  function toggleRecordingPause() {
    state.recordingPaused = !state.recordingPaused;
    elements.audioRecorder.classList.toggle("is-paused", state.recordingPaused);
    const icon = elements.pauseRecordingButton.querySelector(".icon");
    icon?.classList.toggle("icon-pause", !state.recordingPaused);
    icon?.classList.toggle("icon-play", state.recordingPaused);
    elements.pauseRecordingButton.setAttribute("aria-label", state.recordingPaused ? "Resume recording" : "Pause recording");
    announce(state.recordingPaused ? "Recording paused." : "Recording resumed.");
  }

  function sendAudioNote() {
    const seconds = Math.max(1, state.recordingSeconds);
    stopRecording();
    addMessage("user", `Audio note ${formatTime(seconds)}`, "audio");
    announce("Audio note sent.");
    simulateReply();
  }

  function startCall() {
    if (state.callActive) return;
    showChat();
    closeTransientMenus();
    if (state.recording) {
      stopRecording();
    }
    state.callActive = true;
    state.callMode = "call";
    state.callMuted = false;
    state.callSeconds = 0;
    renderFeelingsState();
    elements.callTime.textContent = "0:00";
    syncCallControls();
    elements.callStateLabel.textContent = "Connecting";
    elements.composerForm.hidden = false;
    transitionSurface("call-open", () => {
      elements.callDock.hidden = false;
      elements.chatView.classList.add("is-calling");
      updateComposerState();
    });
    window.setTimeout(() => {
      if (state.callActive) {
        elements.callStateLabel.textContent = callStatusLabel();
        announce("Call connected.");
      }
    }, 650);
    state.callTimer = window.setInterval(() => {
      state.callSeconds += 1;
      elements.callTime.textContent = formatTime(state.callSeconds);
    }, 1000);
  }

  function endCall() {
    if (!state.callActive) return;
    window.clearInterval(state.callTimer);
    state.callTimer = null;
    state.callActive = false;
    state.callMode = "call";
    state.callMuted = false;
    renderFeelingsState();
    transitionSurface("call-close", () => {
      elements.callDock.hidden = true;
      elements.chatView.classList.remove("is-calling");
      elements.composerForm.hidden = false;
      updateComposerState();
    });
    elements.messageInput.focus();
    announce("Call ended. The conversation is still here.");
  }

  function toggleCallMute() {
    state.callMuted = !state.callMuted;
    syncCallControls();
    renderFeelingsState();
    announce(state.callMuted ? "Microphone muted." : "Microphone on.");
  }

  function callStatusLabel() {
    if (state.callMuted) return "Muted";
    if (state.callMode === "listen_only") return "Just listening";
    return "Listening";
  }

  function syncToggle(button, enabled, onLabel, offLabel) {
    button.setAttribute("aria-pressed", String(enabled));
    button.setAttribute("aria-label", enabled ? onLabel : offLabel);
  }

  function syncCallControls() {
    elements.callStateLabel.textContent = callStatusLabel();
    elements.callModeButtons.forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.callMode === state.callMode));
    });

    const microphoneIcon = elements.muteCallButton.querySelector(".icon");
    microphoneIcon?.classList.toggle("icon-microphone", !state.callMuted);
    microphoneIcon?.classList.toggle("icon-microphone-slash", state.callMuted);
    elements.muteCallButton.classList.toggle("is-on", !state.callMuted);
    elements.muteCallButton.classList.toggle("is-muted", state.callMuted);
    syncToggle(elements.muteCallButton, state.callMuted, "Unmute microphone", "Mute microphone");

  }

  function setCallMode(mode) {
    if (!state.callActive || !["call", "wing", "listen_only"].includes(mode)) return;
    state.callMode = mode;
    syncCallControls();
    syncSouls();
    const labels = {
      call: "Call mode. Viventium responds normally.",
      wing: "Wing mode. Viventium speaks only when useful.",
      listen_only: "Listen-Only mode. Viventium only listens and remembers.",
    };
    announce(labels[mode]);
  }

  function feelingLevelIndex(value) {
    return value < 20 ? 0 : value < 40 ? 1 : value < 60 ? 2 : value < 80 ? 3 : 4;
  }

  function feelingWord(feeling, key = "current") {
    return feeling.words[feelingLevelIndex(feeling[key])];
  }

  function feelingPrompt(feeling) {
    const level = feelingLevelIndex(feeling.current);
    return [feeling.prompts[level], feeling.customPrompts[level]].filter(Boolean).join(" ");
  }

  function textNode(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    node.textContent = text;
    return node;
  }

  function formatTrailTime(timestamp) {
    const elapsedSeconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000));
    if (elapsedSeconds < 45) return "Just now";
    const elapsedMinutes = Math.floor(elapsedSeconds / 60);
    if (elapsedMinutes < 60) return `${elapsedMinutes} min`;
    const elapsedHours = Math.floor(elapsedMinutes / 60);
    return `${elapsedHours} hr`;
  }

  function recordFeelingMovement(feeling, before, after, cause) {
    const from = Math.round(before);
    const to = Math.round(after);
    if (from === to) return;
    const distance = Math.abs(to - from);
    feelingTrail.unshift({
      at: Date.now(),
      band: feeling.name,
      before: from,
      after: to,
      strength: distance < 5 ? "slight" : distance < 15 ? "clear" : "strong",
      cause,
    });
    feelingTrail = feelingTrail.slice(0, 24);
  }

  function applyFeelingDecay(now = Date.now()) {
    if (!state.feelingsPower || state.feelingsPaused) return false;
    let changed = false;
    feelings.forEach((feeling) => {
      const lastUpdate = Number.isFinite(feeling.updatedAt) ? feeling.updatedAt : now;
      const elapsedMinutes = Math.max(0, now - lastUpdate) / 60_000;
      feeling.updatedAt = now;
      if (!elapsedMinutes || feeling.current === feeling.nature) return;
      const returnFactor = Math.pow(0.5, elapsedMinutes / feeling.halfLife);
      const next = feeling.nature + (feeling.current - feeling.nature) * returnFactor;
      if (Math.abs(next - feeling.current) > 0.0001) {
        feeling.current = next;
        changed = true;
      }
    });
    return changed;
  }

  function updateInnerState() {
    const energyIndex = feelingLevelIndex(feelings[0].current);
    const curiosityIndex = feelingLevelIndex(feelings[3].current);
    const careIndex = feelingLevelIndex(feelings[5].current);
    const energyPhrases = [
      "depleted and pulled toward stillness",
      "quiet and conserving what I have",
      "steady enough to stay present",
      "energized and ready to move",
      "electric, with motion pressing forward",
    ];
    const curiosityPhrases = [
      "unmoved by the unknown",
      "open without needing to chase",
      "curious about what remains",
      "drawn toward what is unresolved",
      "absorbed by the unanswered part",
    ];
    const carePhrases = [
      "without a pull to tend",
      "receptive without carrying it",
      "genuinely caring",
      "strongly pulled to protect what matters",
      "intensely pressed to help and protect",
    ];
    const sentence = `I feel ${energyPhrases[energyIndex]}, ${curiosityPhrases[curiosityIndex]}, and ${carePhrases[careIndex]}.`;
    const energy = feelingWord(feelings[0]);
    const compactStatus = !state.feelingsPower
      ? { prefix: "Feelings", label: "off" }
      : state.feelingsPaused
        ? { prefix: "Feelings", label: "paused" }
        : state.replyPending
          ? { prefix: "", label: "Thinking" }
          : state.callActive && !state.callMuted
            ? { prefix: "", label: "Listening" }
            : { prefix: "Feeling", label: energy };
    const compactState = compactStatus.label.toLowerCase();
    elements.innerState.textContent = !state.feelingsPower
      ? "Feelings are off."
      : state.innerStateStale
        ? "Waiting for the next reaction."
        : sentence;
    elements.feelingsMiniPrefix.textContent = compactStatus.prefix;
    elements.feelingsMiniLabel.textContent = compactStatus.label;
    const compactAria = !state.feelingsPower
      ? "Feelings are off."
      : state.feelingsPaused
        ? "Feelings are paused."
        : state.replyPending
          ? "Viventium is thinking."
          : state.callActive && !state.callMuted
            ? "Viventium is listening."
            : `Viventium is feeling ${compactState}.`;
    elements.feelingsButton.setAttribute(
      "aria-label",
      `${compactAria} Open Feelings.`,
    );
    elements.body.classList.toggle("feelings-motion-paused", state.feelingsPaused || !state.feelingsPower || document.hidden);
    syncSouls();
  }

  function renderFeelingsState() {
    updateInnerState();
    elements.feelingsPowerToggle.checked = state.feelingsPower;
    elements.feelingsPowerToggle.setAttribute("aria-label", state.feelingsPower ? "Turn Feelings off" : "Turn Feelings on");
    elements.feelingsPowerLabel.textContent = !state.feelingsPower
      ? "Feelings off"
      : state.feelingsPaused
        ? "Feelings paused"
        : "Feelings on";
    elements.feelingsPowerNote.textContent = !state.feelingsPower
      ? "No feeling state shapes replies."
      : state.feelingsPaused
        ? "State held. Return is paused."
        : "Now returns toward Baseline over time.";
    elements.pauseFeelingsButton.textContent = state.feelingsPaused ? "Resume" : "Pause";
    const health = !state.feelingsPower
      ? { line: "Feelings off", label: "Off", state: "off" }
      : state.feelingsPaused
        ? { line: "Reactions paused · state kept", label: "Paused", state: "paused" }
        : state.innerStateStale
          ? { line: "Reaction pending · state edited", label: "Pending", state: "pending" }
          : state.lastReactionAt
            ? { line: `Reaction applied · ${formatTrailTime(state.lastReactionAt).toLowerCase()}`, label: "Applied", state: "applied" }
            : { line: "Reaction ready · local preview", label: "Ready", state: "ready" };
    elements.feelingsHealthText.textContent = health.line;
    elements.feelingsToolbarHealth.textContent = health.label;
    elements.feelingsDialog.dataset.health = health.state;
  }

  function renderPromptPreview() {
    const fragment = document.createDocumentFragment();
    feelings.filter((feeling) => feeling.enabled).forEach((feeling) => {
      const row = textNode("div", "prompt-line", "");
      row.append(
        textNode("strong", "", feeling.name),
        textNode("span", "", feelingPrompt(feeling)),
      );
      fragment.appendChild(row);
    });
    elements.feelingPromptPreview.replaceChildren(fragment);
  }

  function renderBaselineProfile() {
    elements.baselineProfileLabel.textContent = state.baselineProfile
      ? `${state.baselineProfile} baseline`
      : "Custom baseline";
    elements.baselineProfiles.querySelectorAll("button").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.baselineProfile === state.baselineProfile));
    });
  }

  function renderPromptChoices() {
    document.querySelectorAll(".mini-choice").forEach((choice) => {
      const selected = choice.dataset.promptChoice === "activation"
        ? state.reactionActivation
        : state.reactionScope;
      choice.querySelectorAll("button").forEach((button) => {
        button.setAttribute("aria-pressed", String(button.textContent === selected));
      });
    });
  }

  function renderFeelingTrail() {
    const fragment = document.createDocumentFragment();
    if (!feelingTrail.length) {
      fragment.appendChild(textNode("li", "feelings-trail-empty", "No typed movement yet."));
    }
    feelingTrail.forEach((entry) => {
      const item = textNode("li", "feelings-trail-row", "");
      const movement = textNode("span", "trail-movement", "");
      movement.append(
        textNode("strong", "", entry.band),
        textNode("b", entry.after >= entry.before ? "up" : "down", `${entry.before} → ${entry.after}`),
        textNode("small", "", `${entry.strength} · ${entry.cause}`),
      );
      item.append(textNode("time", "", formatTrailTime(entry.at)), movement);
      fragment.appendChild(item);
    });
    elements.feelingsTrailList.replaceChildren(fragment);
  }

  function renderRangePrompts() {
    const feeling = feelings[state.selectedFeeling];
    const activeLevel = feelingLevelIndex(feeling.current);
    elements.rangePromptHeading.textContent = `${feeling.name} feeling prompts`;
    const fragment = document.createDocumentFragment();
    feeling.prompts.forEach((prompt, index) => {
      const min = index * 20;
      const max = index === 4 ? 100 : min + 19;
      const row = textNode("div", `range-prompt-row${index === activeLevel ? " is-active" : ""}`, "");
      const heading = textNode("div", "range-prompt-head", "");
      heading.append(textNode("strong", "", `${min}–${max} · ${feeling.words[index]}`));
      if (index === activeLevel) heading.append(textNode("span", "", "Now"));
      if (feeling.customPrompts[index]) heading.append(textNode("span", "custom", "Custom"));
      const builtIn = textNode("p", "", prompt);
      const input = document.createElement("textarea");
      input.rows = 2;
      input.maxLength = 1200;
      input.placeholder = "Optional private addition";
      input.value = feeling.customPrompts[index];
      input.setAttribute("aria-label", `${feeling.name} ${feeling.words[index]} optional addition`);
      const actions = textNode("div", "range-prompt-actions", "");
      const restore = textNode("button", "text-button", "Restore");
      restore.type = "button";
      const save = textNode("button", "secondary-button", "Save");
      save.type = "button";
      restore.addEventListener("click", () => {
        feeling.customPrompts[index] = "";
        saveFeelings();
        renderRangePrompts();
        renderPromptPreview();
        announce(`${feeling.name} ${feeling.words[index]} prompt restored.`);
      });
      save.addEventListener("click", () => {
        feeling.customPrompts[index] = input.value.trim();
        saveFeelings();
        renderRangePrompts();
        renderPromptPreview();
        announce(`${feeling.name} ${feeling.words[index]} prompt saved.`);
      });
      actions.append(restore, save);
      row.append(heading, builtIn, input, actions);
      fragment.appendChild(row);
    });
    elements.rangePromptList.replaceChildren(fragment);
  }

  function selectFeeling(index) {
    state.selectedFeeling = index;
    const feeling = feelings[index];
    const nowWord = feelingWord(feeling);
    const baselineWord = feelingWord(feeling, "nature");
    elements.feelingsLanes.querySelectorAll(".feeling-lane").forEach((lane, laneIndex) => {
      lane.classList.toggle("is-selected", laneIndex === index);
    });
    elements.selectedFeelingName.textContent = feeling.name;
    elements.selectedFeelingWords.textContent = nowWord;
    elements.selectedFeelingDescription.textContent = feeling.description;
    elements.selectedFeelingNow.textContent = `${Math.round(feeling.current)} · ${nowWord}`;
    elements.selectedFeelingBaseline.textContent = `${Math.round(feeling.nature)} · ${baselineWord}`;
    elements.selectedFeelingPrompt.textContent = feelingPrompt(feeling);
    elements.returnSpeedInput.value = String(feeling.halfLife);
    elements.feelingEnabledToggle.checked = feeling.enabled;
    renderRangePrompts();
  }

  function renderFeelings() {
    const decayed = applyFeelingDecay();
    const editKey = state.feelingsMoment === "baseline" ? "nature" : "current";
    state.editFeeling = editKey;
    const fragment = document.createDocumentFragment();
    feelings.forEach((feeling, index) => {
      const lane = textNode("div", `feeling-lane${index === state.selectedFeeling ? " is-selected" : ""}`, "");
      lane.classList.toggle("is-disabled", !feeling.enabled);
      const label = document.createElement("label");
      const inputId = `feeling-${index}`;
      label.htmlFor = inputId;
      label.append(textNode("strong", "", feeling.name), textNode("span", "lane-value", `${Math.round(feeling[editKey])}`));

      const track = textNode("div", "lane-track", "");
      const trail = textNode("div", "lane-motion-trail", "");
      feeling.history.slice(-4).forEach((value, pointIndex) => {
        const point = textNode("i", "", "");
        point.style.bottom = `${7 + value * 2.86}px`;
        point.style.setProperty("--trail-left", `${value}%`);
        point.style.setProperty("--trail-drift", `${[-3, 2, -1, 1][pointIndex]}px`);
        point.style.opacity = String(0.18 + pointIndex * 0.13);
        trail.appendChild(point);
      });

      const comparison = textNode("span", editKey === "current" ? "compare-marker is-baseline" : "compare-marker is-now", "");
      const comparisonValue = editKey === "current" ? feeling.nature : feeling.current;
      comparison.style.bottom = `${7 + comparisonValue * 2.86}px`;
      comparison.style.setProperty("--marker-left", `${comparisonValue}%`);
      comparison.setAttribute("aria-hidden", "true");

      const input = document.createElement("input");
      input.id = inputId;
      input.className = editKey === "current" ? "edit-now" : "edit-baseline";
      input.type = "range";
      input.min = "0";
      input.max = "100";
      input.value = String(feeling[editKey]);
      input.setAttribute("aria-label", `${feeling.name} ${editKey === "current" ? "Now" : "Baseline"}`);
      input.setAttribute("aria-valuetext", `${Math.round(feeling[editKey])}, ${feelingWord(feeling, editKey)}`);
      let editStartValue = feeling[editKey];
      input.addEventListener("focus", () => {
        editStartValue = feeling[editKey];
        selectFeeling(index);
      });
      input.addEventListener("pointerdown", () => {
        editStartValue = feeling[editKey];
        selectFeeling(index);
      });
      input.addEventListener("input", () => {
        feeling[editKey] = Number(input.value);
        feeling.updatedAt = Date.now();
        if (editKey === "current") {
          const lastHistoryValue = feeling.history.at(-1);
          if (Math.round(lastHistoryValue) !== Math.round(feeling.current)) feeling.history.push(feeling.current);
          feeling.history = feeling.history.slice(-8);
        }
        if (editKey === "nature") {
          state.baselineProfile = Object.entries(baselineProfiles).find(([, values]) =>
            values.every((value, profileIndex) => value === feelings[profileIndex].nature))?.[0] || "";
          renderBaselineProfile();
        }
        label.querySelector(".lane-value").textContent = input.value;
        input.setAttribute("aria-valuetext", `${input.value}, ${feelingWord(feeling, editKey)}`);
        state.innerStateStale = true;
        saveFeelings();
        selectFeeling(index);
        renderPromptPreview();
        renderFeelingsState();
      });
      input.addEventListener("change", () => {
        recordFeelingMovement(
          feeling,
          editStartValue,
          feeling[editKey],
          editKey === "current" ? "manual Now adjustment" : "manual Baseline adjustment",
        );
        editStartValue = feeling[editKey];
        saveFeelings();
        renderFeelingTrail();
        reactSouls();
        announce(`${feeling.name} ${editKey === "current" ? "Now" : "Baseline"} set to ${input.value}.`);
      });
      track.append(trail, comparison, input);

      const poles = textNode("div", "lane-poles", "");
      poles.append(textNode("span", "", feeling.words[4]), textNode("span", "", feeling.words[0]));
      lane.append(label, track, poles);
      fragment.appendChild(lane);
    });
    elements.feelingsLanes.replaceChildren(fragment);
    renderBaselineProfile();
    selectFeeling(state.selectedFeeling);
    renderPromptPreview();
    renderFeelingTrail();
    renderFeelingsState();
    if (decayed) saveFeelings();
  }

  function setFeelingsMoment(moment, { focus = false } = {}) {
    if (!["now", "baseline", "trail"].includes(moment)) return;
    state.feelingsMoment = moment;
    const controls = { now: elements.nowButton, baseline: elements.baselineButton, trail: elements.trailButton };
    Object.entries(controls).forEach(([name, button]) => {
      const selected = name === moment;
      button.setAttribute("aria-selected", String(selected));
      button.tabIndex = selected ? 0 : -1;
    });
    elements.feelingsLivePanel.hidden = moment === "trail";
    elements.feelingsTrailPanel.hidden = moment !== "trail";
    if (moment !== "trail") elements.feelingsLivePanel.setAttribute("aria-labelledby", `${moment}Button`);
    elements.baselineProfiles.hidden = moment !== "baseline";
    if (moment !== "trail") renderFeelings();
    else renderFeelingTrail();
    if (focus) controls[moment].focus();
  }

  function setFeelingsSection(section) {
    state.feelingsSection = section;
    const prompts = section === "prompts";
    elements.spectrumButton.setAttribute("aria-pressed", String(!prompts));
    elements.promptsButton.setAttribute("aria-pressed", String(prompts));
    elements.feelingsSpectrumPanel.hidden = prompts;
    elements.feelingsPromptsPanel.hidden = !prompts;
    elements.feelingsToolbar.hidden = prompts;
    if (prompts) {
      elements.reactionInstructionInput.value = state.reactionInstruction;
      renderPromptPreview();
      renderRangePrompts();
    } else {
      setFeelingsMoment(state.feelingsMoment);
    }
  }

  function openDialog(dialog) {
    closeTransientMenus();
    if (!dialog.open) {
      dialog.showModal();
    }
  }

  function setConnectionTab(tabName, { focus = false } = {}) {
    state.activeConnectionTab = tabName;
    const providersActive = tabName === "providers";
    elements.providersTab.setAttribute("aria-selected", String(providersActive));
    elements.providersTab.tabIndex = providersActive ? 0 : -1;
    elements.channelsTab.setAttribute("aria-selected", String(!providersActive));
    elements.channelsTab.tabIndex = providersActive ? -1 : 0;
    elements.providersPanel.hidden = !providersActive;
    elements.channelsPanel.hidden = providersActive;
    elements.connectionSearchInput.value = "";
    renderConnections();
    if (focus) {
      (providersActive ? elements.providersTab : elements.channelsTab).focus();
    }
  }

  function createConnectionGroup(group, filter, kind) {
    const items = group.items.filter((name) => name.toLowerCase().includes(filter));
    if (!items.length) return null;

    const isCollapsible = !filter
      && ((kind === "providers" && group.group !== "Subscriptions") || group.group === "Other");
    const section = document.createElement(isCollapsible ? "details" : "section");
    section.className = "connection-group";
    const rows = document.createElement("div");
    rows.className = "connection-rows";

    items.forEach((name) => {
      const row = document.createElement("div");
      row.className = "connection-row";
      const label = document.createElement("span");
      label.textContent = name;
      const button = document.createElement("button");
      button.type = "button";
      const isConnected = state.connected.has(name);
      button.textContent = isConnected ? "Connected" : "Connect";
      button.classList.toggle("is-connected", isConnected);
      button.setAttribute("aria-label", `${isConnected ? "Manage" : "Connect"} ${name}`);
      button.addEventListener("click", () => connectItem(name, button));
      row.append(label, button);
      rows.appendChild(row);
    });

    if (isCollapsible) {
      section.classList.add("is-collapsible");
      section.open = state.expandedConnectionGroups.has(group.group);
      const summary = document.createElement("summary");
      const label = document.createElement("span");
      label.textContent = group.group;
      const count = document.createElement("span");
      count.className = "connection-group-count";
      count.textContent = String(items.length);
      summary.append(label, count);
      section.addEventListener("toggle", () => {
        if (section.open) state.expandedConnectionGroups.add(group.group);
        else state.expandedConnectionGroups.delete(group.group);
      });
      section.append(summary, rows);
    } else {
      const heading = document.createElement("h2");
      heading.textContent = group.group;
      section.append(heading, rows);
    }
    return section;
  }

  function renderConnections() {
    const filter = elements.connectionSearchInput.value.trim().toLowerCase();
    const providerFragment = document.createDocumentFragment();
    providers.forEach((group) => {
      const section = createConnectionGroup(group, filter, "providers");
      if (section) providerFragment.appendChild(section);
    });
    elements.providersList.replaceChildren(providerFragment);

    const channelFragment = document.createDocumentFragment();
    channels.forEach((group) => {
      const section = createConnectionGroup(group, filter, "channels");
      if (section) channelFragment.appendChild(section);
    });
    elements.channelsList.replaceChildren(channelFragment);

    const activeList = state.activeConnectionTab === "providers" ? elements.providersList : elements.channelsList;
    if (!activeList.children.length) {
      const empty = document.createElement("p");
      empty.className = "connection-empty";
      empty.textContent = "No matches.";
      activeList.appendChild(empty);
    }
  }

  function connectItem(name, button) {
    if (state.connected.has(name)) {
      elements.connectionDialogStatus.textContent = `${name} is connected.`;
      return;
    }
    button.disabled = true;
    button.textContent = "Connecting";
    elements.connectionDialogStatus.textContent = `Connecting ${name}.`;
    window.setTimeout(() => {
      state.connected.add(name);
      saveConnections();
      renderConnections();
      elements.connectionDialogStatus.textContent = `${name} connected.`;
    }, 700);
  }

  function runUpdate() {
    elements.updateMenuLabel.textContent = "Updating";
    elements.updateMenuValue.textContent = "";
    elements.accountMenu.querySelector('[data-account-action="update"]').disabled = true;
    announce("Updating Viventium.");
    window.setTimeout(() => {
      elements.updateMenuLabel.textContent = "Updated";
      elements.updateMenuValue.textContent = "Current";
      elements.accountMenu.querySelector('[data-account-action="update"]').disabled = false;
      announce("Viventium is up to date.");
    }, 1050);
  }

  function selectCortexRow(row) {
    elements.cortexList.querySelectorAll(".cortex-row").forEach((candidate) => {
      const selected = candidate === row;
      candidate.classList.toggle("is-current", selected);
      candidate.setAttribute("aria-pressed", String(selected));
      const stateLabel = candidate.querySelector(":scope > span:last-child");
      if (stateLabel) stateLabel.textContent = selected ? "Current" : "";
    });
    const name = row.querySelector("strong")?.textContent || "Cortex";
    elements.cortexDialogStatus.textContent = `${name} selected.`;
  }

  function openCortexBuilder() {
    elements.newCortexButton.hidden = true;
    elements.cortexBuilder.hidden = false;
    elements.cortexDialogStatus.textContent = "";
    window.setTimeout(() => elements.cortexNameInput.focus(), 0);
  }

  function closeCortexBuilder() {
    elements.cortexBuilder.reset();
    elements.cortexBuilder.hidden = true;
    elements.newCortexButton.hidden = false;
    elements.newCortexButton.focus();
  }

  function createCortex(name, purpose) {
    const row = document.createElement("button");
    row.className = "cortex-row";
    row.type = "button";
    row.setAttribute("aria-pressed", "false");

    const image = document.createElement("img");
    image.src = "assets/brand/viventium-logo.png";
    image.alt = "";
    const copy = document.createElement("span");
    const title = document.createElement("strong");
    title.textContent = name;
    const detail = document.createElement("small");
    detail.textContent = purpose;
    copy.append(title, detail);
    const current = document.createElement("span");
    row.append(image, copy, current);
    row.addEventListener("click", () => selectCortexRow(row));
    elements.cortexList.appendChild(row);
    selectCortexRow(row);
    closeCortexBuilder();
    elements.cortexDialogStatus.textContent = `${name} cortex created.`;
  }

  function logout() {
    if (state.provider) state.connected.delete(state.provider);
    localStorage.removeItem(STORAGE.setup);
    localStorage.removeItem(STORAGE.provider);
    saveConnections();
    state.provider = "";
    elements.connectFeedback.hidden = true;
    elements.setupError.hidden = true;
    elements.setupProviderList.querySelectorAll("button").forEach((button) => {
      button.disabled = false;
      button.classList.remove("is-connecting");
    });
    closeTransientMenus();
    showConnect();
    announce("Logged out.");
  }

  elements.installButton.addEventListener("click", () => {
    transitionSurface("setup", () => {
      localStorage.setItem(STORAGE.installed, "true");
      showConnect();
    });
  });

  elements.setupProviderList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-setup-provider]");
    if (!button) return;
    connectFromSetup(button.dataset.setupProvider, button);
  });

  elements.apiKeyForm.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!elements.apiKeyInput.value.trim()) {
      elements.setupError.hidden = false;
      elements.setupError.querySelector("strong").textContent = "Enter an API key.";
      elements.setupError.querySelector("span").textContent = "The value stays in this concept only.";
      elements.apiKeyInput.focus();
      return;
    }
    elements.apiKeyInput.value = "";
    completeSetup("OpenAI API");
  });

  elements.retrySetupButton.addEventListener("click", () => {
    elements.setupError.hidden = true;
    elements.setupProviderList.querySelectorAll("button").forEach((button) => {
      button.disabled = false;
      button.classList.remove("is-connecting");
    });
    elements.setupProviderList.querySelector("button")?.focus();
  });

  elements.statusTrigger.addEventListener("click", (event) => {
    event.stopPropagation();
    openMenu(elements.statusMenu, elements.statusTrigger);
  });

  elements.statusMenu.addEventListener("click", (event) => {
    const action = event.target.closest("[data-status-action]")?.dataset.statusAction;
    if (!action) return;
    closeMenu(elements.statusMenu, elements.statusTrigger);
    if (action === "chat") {
      setupIsComplete() ? showChat({ focusComposer: true }) : showEntryGate();
    }
    if (action === "call") {
      if (setupIsComplete()) {
        startCall();
      } else {
        showEntryGate();
      }
    }
    if (action === "advanced") {
      if (setupIsComplete()) {
        setAdvanced(!state.advanced, { openMobile: true });
        showChat();
      } else {
        showEntryGate();
      }
    }
    if (action === "quit") {
      endCall();
      stopRecording();
      setVisibleView(elements.quitView);
    }
  });

  elements.restartConceptButton.addEventListener("click", () => {
    elements.desktopShell.classList.remove("is-quit");
    setupIsComplete() ? showChat({ focusComposer: true }) : showEntryGate();
  });

  elements.accountTrigger.addEventListener("click", (event) => {
    event.stopPropagation();
    openMenu(elements.accountMenu, elements.accountTrigger);
  });

  elements.accountMenu.addEventListener("click", (event) => {
    const action = event.target.closest("[data-account-action]")?.dataset.accountAction;
    if (!action) return;
    if (action === "connect") {
      openDialog(elements.connectDialog);
      setConnectionTab("providers");
    }
    if (action === "update") runUpdate();
    if (action === "view") openDialog(elements.viewDialog);
    if (action === "logout") logout();
  });

  elements.openSidebarButton.addEventListener("click", openMobileSidebar);
  elements.closeSidebarButton.addEventListener("click", closeMobileSidebar);
  elements.sidebarScrim.addEventListener("click", closeMobileSidebar);
  elements.newChatButton.addEventListener("click", clearConversation);
  elements.workersButton.addEventListener("click", () => {
    closeMobileSidebar();
    openDialog(elements.workersDialog);
  });
  elements.cortexButton.addEventListener("click", () => {
    closeMobileSidebar();
    openDialog(elements.cortexDialog);
  });

  elements.searchChatsButton.addEventListener("click", () => {
    const willOpen = elements.sidebarSearchWrap.hidden;
    elements.sidebarSearchWrap.hidden = !willOpen;
    elements.searchChatsButton.setAttribute("aria-expanded", String(willOpen));
    if (willOpen) elements.sidebarSearch.focus();
  });

  elements.sidebarSearch.addEventListener("input", () => {
    const filter = elements.sidebarSearch.value.trim().toLowerCase();
    elements.recentChats.forEach((chat) => {
      chat.hidden = !chat.textContent.toLowerCase().includes(filter);
    });
  });

  elements.recentChats.forEach((chat) => {
    chat.addEventListener("click", () => {
      elements.recentChats.forEach((item) => item.classList.toggle("is-current", item === chat));
      closeMobileSidebar();
      showChat();
    });
  });

  elements.messageInput.addEventListener("input", updateComposerState);
  elements.messageInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      elements.composerForm.requestSubmit();
    }
  });

  elements.composerForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = elements.messageInput.value.trim();
    if (!text && !state.attachment) return;
    const attachmentText = state.attachment ? `File: ${state.attachment.name}` : "";
    addMessage("user", [text, attachmentText].filter(Boolean).join("\n"));
    elements.messageInput.value = "";
    removeAttachment();
    updateComposerState();
    simulateReply();
  });

  elements.uploadButton.addEventListener("click", (event) => {
    event.stopPropagation();
    openMenu(elements.uploadMenu, elements.uploadButton);
  });

  elements.uploadMenu.addEventListener("click", (event) => {
    const kind = event.target.closest("[data-file-kind]")?.dataset.fileKind;
    if (!kind) return;
    elements.fileInput.accept = kind === "image" ? "image/*" : "";
    closeMenu(elements.uploadMenu, elements.uploadButton);
    elements.fileInput.click();
  });

  elements.fileInput.addEventListener("change", () => {
    const file = elements.fileInput.files?.[0];
    if (file) selectFile(file);
  });

  elements.removeAttachmentButton.addEventListener("click", removeAttachment);
  elements.recordButton.addEventListener("click", startRecording);
  elements.pauseRecordingButton.addEventListener("click", toggleRecordingPause);
  elements.cancelRecordingButton.addEventListener("click", () => {
    stopRecording();
    elements.messageInput.focus();
    announce("Audio note canceled.");
  });
  elements.sendRecordingButton.addEventListener("click", sendAudioNote);
  elements.callButton.addEventListener("click", startCall);
  elements.muteCallButton.addEventListener("click", toggleCallMute);
  elements.callModeButtons.forEach((button) => {
    button.addEventListener("click", () => setCallMode(button.dataset.callMode));
  });
  elements.endCallButton.addEventListener("click", endCall);

  elements.feelingsButton.addEventListener("click", () => {
    renderFeelings();
    setFeelingsSection("spectrum");
    openDialog(elements.feelingsDialog);
  });
  elements.feelingsButton.addEventListener("pointerenter", () => {
    soulControllers.forEach((controller) => controller.setAttention(true));
  });
  elements.feelingsButton.addEventListener("pointerleave", () => {
    soulControllers.forEach((controller) => controller.setAttention(false));
  });
  elements.feelingsButton.addEventListener("focus", () => {
    soulControllers.forEach((controller) => controller.setAttention(true));
  });
  elements.feelingsButton.addEventListener("blur", () => {
    soulControllers.forEach((controller) => controller.setAttention(false));
  });
  elements.spectrumButton.addEventListener("click", () => setFeelingsSection("spectrum"));
  elements.promptsButton.addEventListener("click", () => setFeelingsSection("prompts"));
  elements.nowButton.addEventListener("click", () => setFeelingsMoment("now"));
  elements.baselineButton.addEventListener("click", () => setFeelingsMoment("baseline"));
  elements.trailButton.addEventListener("click", () => setFeelingsMoment("trail"));
  [elements.nowButton, elements.baselineButton, elements.trailButton].forEach((tab) => {
    tab.addEventListener("keydown", (event) => {
      if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
      event.preventDefault();
      const order = ["now", "baseline", "trail"];
      const index = order.indexOf(state.feelingsMoment);
      const direction = event.key === "ArrowRight" ? 1 : -1;
      setFeelingsMoment(order[(index + direction + order.length) % order.length], { focus: true });
    });
  });
  elements.restoreFeelingButton.addEventListener("click", () => {
    const feeling = feelings[state.selectedFeeling];
    const before = feeling.current;
    feeling.current = feeling.nature;
    feeling.updatedAt = Date.now();
    feeling.history.push(feeling.current);
    feeling.history = feeling.history.slice(-8);
    recordFeelingMovement(feeling, before, feeling.current, "returned to Baseline");
    state.innerStateStale = true;
    saveFeelings();
    setFeelingsMoment("now");
    reactSouls();
    announce(`${feeling.name} returned to Baseline.`);
  });
  elements.returnSpeedInput.addEventListener("input", () => {
    const feeling = feelings[state.selectedFeeling];
    const next = Math.min(525600, Math.max(1, Number(elements.returnSpeedInput.value) || feeling.halfLife));
    feeling.halfLife = next;
    feeling.updatedAt = Date.now();
    saveFeelings();
  });
  elements.returnSpeedInput.addEventListener("change", () => {
    const feeling = feelings[state.selectedFeeling];
    elements.returnSpeedInput.value = String(feeling.halfLife);
    announce(`${feeling.name} return time updated.`);
  });
  elements.feelingEnabledToggle.addEventListener("change", () => {
    const feeling = feelings[state.selectedFeeling];
    feeling.enabled = elements.feelingEnabledToggle.checked;
    saveFeelings();
    renderFeelings();
    reactSouls();
    announce(`${feeling.name} ${feeling.enabled ? "included" : "paused"}.`);
  });
  elements.baselineProfiles.addEventListener("click", (event) => {
    const button = event.target.closest("[data-baseline-profile]");
    if (!button) return;
    const values = baselineProfiles[button.dataset.baselineProfile];
    if (!values) return;
    feelings.forEach((feeling, index) => {
      const before = feeling.current;
      feeling.nature = values[index];
      feeling.current = values[index];
      feeling.updatedAt = Date.now();
      feeling.history = [...feeling.history.slice(-2), values[index]];
      recordFeelingMovement(feeling, before, feeling.current, `${button.dataset.baselineProfile} Baseline applied`);
    });
    state.baselineProfile = button.dataset.baselineProfile;
    state.innerStateStale = true;
    saveFeelings();
    renderFeelings();
    reactSouls();
    announce(`${button.dataset.baselineProfile} Baseline applied. Trail kept.`);
  });
  document.querySelectorAll(".mini-choice").forEach((choice) => {
    choice.addEventListener("click", (event) => {
      const button = event.target.closest("button");
      if (!button) return;
      if (choice.dataset.promptChoice === "activation") state.reactionActivation = button.textContent;
      else state.reactionScope = button.textContent;
      saveFeelings();
      renderPromptChoices();
    });
  });
  elements.saveReactionPromptButton.addEventListener("click", () => {
    state.reactionInstruction = elements.reactionInstructionInput.value.trim();
    saveFeelings();
    elements.reactionPromptStatus.textContent = "Saved.";
    window.setTimeout(() => { elements.reactionPromptStatus.textContent = ""; }, 1400);
  });
  elements.feelingsPowerToggle.addEventListener("change", () => {
    state.feelingsPower = elements.feelingsPowerToggle.checked;
    if (!state.feelingsPower) state.feelingsPaused = false;
    feelings.forEach((feeling) => { feeling.updatedAt = Date.now(); });
    saveFeelings();
    renderFeelingsState();
    announce(state.feelingsPower ? "Feelings on." : "Feelings off.");
  });
  elements.pauseFeelingsButton.addEventListener("click", () => {
    state.feelingsPaused = !state.feelingsPaused;
    feelings.forEach((feeling) => { feeling.updatedAt = Date.now(); });
    saveFeelings();
    renderFeelingsState();
    announce(state.feelingsPaused ? "Feelings paused. State kept." : "Feelings resumed.");
  });
  elements.resetFeelingsButton.addEventListener("click", () => {
    feelings.forEach((feeling) => {
      const before = feeling.current;
      feeling.current = feeling.nature;
      feeling.updatedAt = Date.now();
      feeling.history.push(feeling.current);
      feeling.history = feeling.history.slice(-8);
      recordFeelingMovement(feeling, before, feeling.current, "Now reset to Baseline");
    });
    state.innerStateStale = true;
    saveFeelings();
    renderFeelings();
    reactSouls();
    announce("Now returned to Baseline. Trail kept.");
  });
  elements.eraseFeelingsButton.addEventListener("click", () => {
    if (elements.eraseFeelingsButton.dataset.confirm !== "true") {
      elements.eraseFeelingsButton.dataset.confirm = "true";
      elements.eraseFeelingsButton.textContent = "Confirm erase";
      return;
    }
    feelings.forEach((feeling) => {
      feeling.current = feeling.nature;
      feeling.customPrompts = Array(5).fill("");
      feeling.updatedAt = Date.now();
    });
    feelingTrail = [];
    state.lastReactionAt = null;
    state.innerStateStale = false;
    state.feelingsPower = false;
    state.feelingsPaused = false;
    elements.eraseFeelingsButton.dataset.confirm = "false";
    elements.eraseFeelingsButton.textContent = "Erase Feelings";
    saveFeelings();
    renderFeelings();
    announce("Feelings erased from this concept.");
  });

  elements.providersTab.addEventListener("click", () => setConnectionTab("providers"));
  elements.channelsTab.addEventListener("click", () => setConnectionTab("channels"));
  [elements.providersTab, elements.channelsTab].forEach((tab) => {
    tab.addEventListener("keydown", (event) => {
      if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
        event.preventDefault();
        setConnectionTab(state.activeConnectionTab === "providers" ? "channels" : "providers", { focus: true });
      }
    });
  });
  elements.connectionSearchInput.addEventListener("input", renderConnections);

  elements.advancedToggle.addEventListener("change", () => setAdvanced(elements.advancedToggle.checked));
  elements.themeButtons.forEach((button) => {
    button.addEventListener("click", () => setTheme(button.dataset.themeChoice));
  });

  elements.cortexList.querySelectorAll(".cortex-row").forEach((row) => {
    row.addEventListener("click", () => selectCortexRow(row));
  });
  elements.newCortexButton.addEventListener("click", openCortexBuilder);
  elements.cancelCortexButton.addEventListener("click", closeCortexBuilder);
  elements.cortexBuilder.addEventListener("submit", (event) => {
    event.preventDefault();
    const name = elements.cortexNameInput.value.trim();
    const purpose = elements.cortexPurposeInput.value.trim();
    if (!name || !purpose) return;
    createCortex(name, purpose);
  });

  document.querySelectorAll("[data-close-dialog]").forEach((button) => {
    button.addEventListener("click", () => document.getElementById(button.dataset.closeDialog)?.close());
  });

  [elements.connectDialog, elements.viewDialog, elements.workersDialog, elements.cortexDialog, elements.feelingsDialog].forEach((dialog) => {
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
  });

  document.addEventListener("click", (event) => {
    if (!elements.statusMenu.contains(event.target) && event.target !== elements.statusTrigger) {
      closeMenu(elements.statusMenu, elements.statusTrigger);
    }
    if (!elements.accountMenu.contains(event.target) && event.target !== elements.accountTrigger) {
      closeMenu(elements.accountMenu, elements.accountTrigger);
    }
    if (!elements.uploadMenu.contains(event.target) && event.target !== elements.uploadButton) {
      closeMenu(elements.uploadMenu, elements.uploadButton);
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeTransientMenus();
  });

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && applyFeelingDecay()) saveFeelings();
    renderFeelingsState();
  });

  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if (state.theme === "system") setTheme("system");
  });
  mobileSidebarQuery.addEventListener("change", syncSidebarAccessibility);

  function seedConversation() {
    addMessage("user", "Help me plan the day around two priorities.");
    addMessage("assistant", "Start with the decision that unblocks other work. Keep the second block protected for focused execution.");
  }

  function initialize() {
    setTheme(state.theme);
    setAdvanced(state.advanced);
    initializeSouls();
    initializeTopOfMind();
    renderPromptChoices();
    if (applyFeelingDecay()) saveFeelings();
    renderFeelingsState();
    renderConnections();
    updateComposerState();
    state.messages.forEach(({ role, text, type }) => renderMessage(role, text, type));
    state.feelingsDecayTimer = window.setInterval(() => {
      if (!applyFeelingDecay()) return;
      saveFeelings();
      renderFeelingsState();
    }, 15_000);

    const stage = query.get("stage");
    if (stage === "install") {
      showInstall();
      return;
    }
    if (stage === "connect") {
      localStorage.setItem(STORAGE.installed, "true");
      showConnect();
      return;
    }
    if (["chat", "conversation", "call", "feelings", "advanced"].includes(stage)) {
      localStorage.setItem(STORAGE.installed, "true");
      localStorage.setItem(STORAGE.setup, "true");
      if (!state.provider) {
        state.provider = "ChatGPT / Codex";
        state.connected.add(state.provider);
        localStorage.setItem(STORAGE.provider, state.provider);
        saveConnections();
      }
      showChat();
      if (["conversation", "call", "feelings", "advanced"].includes(stage) && !state.messages.length) {
        seedConversation();
      }
      if (stage === "advanced") setAdvanced(true);
      if (stage === "call") startCall();
      if (stage === "feelings") {
        renderFeelings();
        window.setTimeout(() => openDialog(elements.feelingsDialog), 0);
      }
      return;
    }
    setupIsComplete() ? showChat() : showEntryGate();
  }

  initialize();
})();
