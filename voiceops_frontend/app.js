// DocChase Frontend Controller
const CASES_ENDPOINT = "/cases";
const ASK_ENDPOINT = "/ask";
const SPEAK_ENDPOINT = "/voice/speak";
const TRANSCRIBE_ENDPOINT = "/voice/transcribe";
const SAMPLES_ENDPOINT = "/api/samples";

let currentDomain = "mortgage";
let cases = [];
let selectedCase = null;
let currentAnswer = "";
let currentAudioUrl = null;

// Workbench state
let samples = [];
let activeSample = null;
let sampleViewFilter = "domain"; // "domain" or "all"

// DOM Elements
const btnMortgage = document.getElementById("btnMortgage");
const btnHealthcare = document.getElementById("btnHealthcare");
const casesHeaderTitle = document.getElementById("casesHeaderTitle");
const casesContainer = document.getElementById("casesContainer");

const sensitiveBanner = document.getElementById("sensitiveBanner");
const caseHeadline = document.getElementById("caseHeadline");
const caseExceptionText = document.getElementById("caseExceptionText");

const questionInput = document.getElementById("questionInput");
const askBtn = document.getElementById("askBtn");
const micBtn = document.getElementById("micBtn");
const micIcon = document.getElementById("micIcon");
const micLabel = document.getElementById("micLabel");
const chatTranscript = document.getElementById("chatTranscript");
const clearChatBtn = document.getElementById("clearChatBtn");
const audioStatus = document.getElementById("audioStatus");
const audioPlayer = document.getElementById("audioPlayer");

const sttModelSelect = document.getElementById("sttModelSelect");
const ttsModelSelect = document.getElementById("ttsModelSelect");

let sessionCaseId = null;

// Workbench DOM Elements
const workbenchCountBadge = document.getElementById("workbenchCountBadge");
const tabDomainSamples = document.getElementById("tabDomainSamples");
const tabAllSamples = document.getElementById("tabAllSamples");
const thumbnailStrip = document.getElementById("thumbnailStrip");
const previewDocTitle = document.getElementById("previewDocTitle");
const previewDocMeta = document.getElementById("previewDocMeta");
const askDocBtn = document.getElementById("askDocBtn");
const openDocLink = document.getElementById("openDocLink");
const previewImage = document.getElementById("previewImage");
const previewPlaceholder = document.getElementById("previewPlaceholder");
const previewDesc = document.getElementById("previewDesc");

// Domain Toggle Listeners
btnMortgage.addEventListener("click", () => switchDomain("mortgage"));
btnHealthcare.addEventListener("click", () => switchDomain("healthcare"));

function switchDomain(domain) {
  if (currentDomain === domain) return;
  currentDomain = domain;

  if (domain === "mortgage") {
    btnMortgage.classList.add("active");
    btnHealthcare.classList.remove("active");
    casesHeaderTitle.textContent = "Mortgage Cases (5)";
  } else {
    btnHealthcare.classList.add("active");
    btnMortgage.classList.remove("active");
    casesHeaderTitle.textContent = "Healthcare Cases (5)";
  }

  loadCases();
  renderThumbnailStrip();
}

// 1) Fetch GET /cases?domain=...
async function loadCases() {
  casesContainer.innerHTML = `<div style="padding: 12px; color: var(--ink-muted); font-size: 13px;">Loading cases…</div>`;
  try {
    const res = await fetch(`${CASES_ENDPOINT}?domain=${currentDomain}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    cases = await res.json();
    renderCases();

    // Select the first case by default
    if (cases.length > 0) {
      selectCase(cases[0]);
    }
  } catch (err) {
    console.error("Failed to load cases:", err);
    casesContainer.innerHTML = `<div style="padding: 12px; color: var(--danger); font-size: 13px;">Error: ${err.message}</div>`;
  }
}

// Render Left Column Case Cards
function renderCases() {
  casesContainer.innerHTML = "";

  cases.forEach((item) => {
    const card = document.createElement("div");
    card.className = "case-card";
    if (selectedCase && selectedCase.case_id === item.case_id) {
      card.classList.add("active");
    }

    // Status chip styling: Missing docs, Sensitive, Ready
    let chipClass = "chip-ready";
    const statusText = (item.status || item.status_chip || "").toLowerCase();
    if (statusText.includes("sensitive")) chipClass = "chip-sensitive";
    else if (statusText.includes("missing")) chipClass = "chip-missing";

    card.innerHTML = `
      <div class="case-row-top">
        <span class="case-id">${item.case_id}</span>
        <span class="chip ${chipClass}">${item.status || item.status_chip}</span>
      </div>
      <div class="case-name">${item.name || "Unknown"}</div>
    `;

    card.addEventListener("click", () => selectCase(item));
    casesContainer.appendChild(card);
  });
}

// Select a Case
// Select a Case
function selectCase(item, updateInput = true) {
  selectedCase = item;
  sessionCaseId = item.case_id;

  // Update card active classes
  document.querySelectorAll(".case-card").forEach((card, idx) => {
    if (cases[idx] && cases[idx].case_id === item.case_id) {
      card.classList.add("active");
    } else {
      card.classList.remove("active");
    }
  });

  // Selected case details
  caseHeadline.textContent = `${item.case_id} — ${item.name || "Client"}`;
  caseExceptionText.textContent = item.exception_text || "No exception details.";

  // Reset red banner
  sensitiveBanner.hidden = !item.sensitive;
  audioStatus.textContent = "Ready.";

  // Set default question in box
  if (updateInput && questionInput) {
    questionInput.value = `what is missing in ${item.case_id}`;
  }

  // Automatically sync workbench preview with this case's sample document
  syncWorkbenchWithCase(item.case_id);
}

// Question Handling (POST /ask)
askBtn.addEventListener("click", () => submitQuestion(questionInput.value.trim()));
questionInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") submitQuestion(questionInput.value.trim());
});

// Clickable Quick / Example Questions (uses session context)
document.querySelectorAll(".example-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const qText = btn.getAttribute("data-query");
    questionInput.value = qText;
    submitQuestion(qText);
  });
});

// Clear Chat Button
if (clearChatBtn) {
  clearChatBtn.addEventListener("click", () => {
    stopAudio();
    if (chatTranscript) {
      chatTranscript.innerHTML = `
        <div class="chat-turn assistant-turn">
          <div class="bubble assistant-bubble">
            Chat cleared. Active case: <strong>${sessionCaseId || 'None'}</strong>. Hold mic or type to speak.
          </div>
        </div>
      `;
    }
    audioStatus.textContent = "Chat cleared. Ready.";
    if (micBtn) {
      micBtn.disabled = false;
      micLabel.textContent = "Hold to talk";
      micIcon.textContent = "🎙️";
    }
    if (askBtn) askBtn.disabled = false;
  });
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function addUserTurn(text) {
  if (!chatTranscript) return;
  const turn = document.createElement("div");
  turn.className = "chat-turn user-turn";
  turn.innerHTML = `
    <div class="bubble user-bubble">${escapeHtml(text)}</div>
  `;
  chatTranscript.appendChild(turn);
  chatTranscript.scrollTop = chatTranscript.scrollHeight;
}

let turnCounter = 0;
function addAssistantLoading() {
  if (!chatTranscript) return null;
  turnCounter++;
  const id = `loading-${turnCounter}`;
  const turn = document.createElement("div");
  turn.className = "chat-turn assistant-turn";
  turn.id = id;
  turn.innerHTML = `
    <div class="bubble assistant-bubble" style="opacity: 0.7;">Thinking…</div>
  `;
  chatTranscript.appendChild(turn);
  chatTranscript.scrollTop = chatTranscript.scrollHeight;
  return id;
}

function updateAssistantLoading(id, text) {
  const turn = id ? document.getElementById(id) : null;
  if (turn) {
    turn.innerHTML = `
      <div class="bubble assistant-bubble">${escapeHtml(text)}</div>
      <div class="assistant-turn-footer">
        <button class="btn-replay-audio" type="button" title="Replay voice">🔊</button>
      </div>
    `;
    const replayBtn = turn.querySelector(".btn-replay-audio");
    if (replayBtn) {
      replayBtn.addEventListener("click", () => speakAnswer(text));
    }
  } else {
    addAssistantTurn(text);
  }
  if (chatTranscript) {
    chatTranscript.scrollTop = chatTranscript.scrollHeight;
  }
}

function addAssistantTurn(text) {
  if (!chatTranscript) return;
  const turn = document.createElement("div");
  turn.className = "chat-turn assistant-turn";
  turn.innerHTML = `
    <div class="bubble assistant-bubble">${escapeHtml(text)}</div>
    <div class="assistant-turn-footer">
      <button class="btn-replay-audio" type="button" title="Replay voice">🔊</button>
    </div>
  `;
  const replayBtn = turn.querySelector(".btn-replay-audio");
  if (replayBtn) {
    replayBtn.addEventListener("click", () => speakAnswer(text));
  }
  chatTranscript.appendChild(turn);
  chatTranscript.scrollTop = chatTranscript.scrollHeight;
}

async function submitQuestion(text) {
  const queryText = (text !== undefined && text !== null) ? text.trim() : "";

  // Add user turn to chat transcript
  addUserTurn(queryText || "(empty)");
  if (questionInput) questionInput.value = "";

  askBtn.disabled = true;
  if (micBtn) micBtn.disabled = true;
  audioStatus.textContent = "Querying…";
  stopAudio();

  const loadingId = addAssistantLoading();

  try {
    const res = await fetch(ASK_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: queryText,
        domain: currentDomain,
        last_case_id: sessionCaseId || (selectedCase ? selectedCase.case_id : null) || (activeSample ? activeSample.case_id : null),
        active_sample_id: activeSample ? activeSample.id : null,
        active_sample_file: activeSample ? (activeSample.filename || activeSample.id) : null
      })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Query failed (${res.status})`);
    }

    const data = await res.json();
    currentAnswer = data.answer || "";

    // Sync session memory and UI when case matches or switches
    if (data.case_id) {
      sessionCaseId = data.case_id;
      const foundCase = cases.find(c => c.case_id === data.case_id);
      if (foundCase) {
        selectCase(foundCase, false);
      }
      syncWorkbenchWithCase(data.case_id);
    }

    // Sensitive case banner check
    const ansLower = currentAnswer.toLowerCase();
    if (ansLower.includes("sensitive case") || ansLower.includes("human review") || (ansLower.includes("human decides") && ansLower.includes("sensitive"))) {
      sensitiveBanner.hidden = false;
    } else {
      sensitiveBanner.hidden = true;
    }

    // Update assistant chat bubble
    updateAssistantLoading(loadingId, currentAnswer);

    // Auto-play voice answer
    await speakAnswer(currentAnswer);
  } catch (err) {
    console.error("Ask error:", err);
    updateAssistantLoading(loadingId, `Error: ${err.message}`);
    audioStatus.textContent = "Ready for next turn. Hold mic to talk.";
    askBtn.disabled = false;
    if (micBtn) micBtn.disabled = false;
  }
}

// Speak Answer (POST /voice/speak)
async function speakAnswer(textToSpeak) {
  const text = textToSpeak || currentAnswer;
  if (!text) return;

  stopAudio();
  audioStatus.textContent = "Generating voice…";

  try {
    const selectedTtsModel = ttsModelSelect ? ttsModelSelect.value : "deepgram/aura:2";
    const res = await fetch(SPEAK_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text, model: selectedTtsModel })
    });

    if (!res.ok) {
      throw new Error(`TTS failed (${res.status})`);
    }

    const blob = await res.blob();
    if (!blob.size) throw new Error("Empty audio received.");

    currentAudioUrl = URL.createObjectURL(blob);
    audioPlayer.src = currentAudioUrl;
    await audioPlayer.play();

    audioStatus.textContent = "Playing voice…";

    // After assistant answer plays, the page is ready for the next hold-to-talk turn
    audioPlayer.onended = () => {
      audioStatus.textContent = "Ready for next turn. Hold mic to talk.";
      if (micBtn) {
        micBtn.disabled = false;
        micLabel.textContent = "Hold to talk";
        micIcon.textContent = "🎙️";
      }
      if (askBtn) askBtn.disabled = false;
    };
    audioPlayer.onerror = () => {
      audioStatus.textContent = "Ready for next turn. Hold mic to talk.";
      if (micBtn) micBtn.disabled = false;
      if (askBtn) askBtn.disabled = false;
    };
  } catch (err) {
    console.error("Speak error:", err);
    audioStatus.textContent = `Speech error: ${err.message}. Ready for next turn.`;
    if (micBtn) micBtn.disabled = false;
    if (askBtn) askBtn.disabled = false;
  }
}

function stopAudio() {
  if (audioPlayer && !audioPlayer.paused) {
    audioPlayer.pause();
    try { audioPlayer.currentTime = 0; } catch (_) {}
  }
  if (currentAudioUrl) {
    URL.revokeObjectURL(currentAudioUrl);
    currentAudioUrl = null;
  }
}

// -------------------------------------------------------------
// Voice Input: Hold-to-Talk via MediaRecorder
// -------------------------------------------------------------
let mediaStream = null;
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let recordStartTime = 0;

async function initMediaStream() {
  if (mediaStream && mediaStream.active) return mediaStream;
  audioStatus.textContent = "Requesting microphone permission...";
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    return mediaStream;
  } catch (err) {
    console.error("Microphone access error:", err);
    if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
      audioStatus.textContent = "Microphone access denied. Please allow microphone permissions.";
    } else {
      audioStatus.textContent = `Microphone error: ${err.message}`;
    }
    throw err;
  }
}

async function startRecording(e) {
  if (e) {
    if (e.button !== undefined && e.button !== 0) return; // Only main button
    if (e.pointerId && micBtn.setPointerCapture) {
      try { micBtn.setPointerCapture(e.pointerId); } catch (_) {}
    }
    e.preventDefault();
  }

  if (isRecording) return;
  stopAudio();

  try {
    const stream = await initMediaStream();

    let mimeType = "";
    if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
      mimeType = "audio/webm;codecs=opus";
    } else if (MediaRecorder.isTypeSupported("audio/webm")) {
      mimeType = "audio/webm";
    } else if (MediaRecorder.isTypeSupported("audio/mp4")) {
      mimeType = "audio/mp4";
    }

    const options = mimeType ? { mimeType } : {};
    mediaRecorder = new MediaRecorder(stream, options);
    audioChunks = [];

    mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        audioChunks.push(event.data);
      }
    };

    mediaRecorder.onstop = handleRecordingStopped;

    mediaRecorder.start(100);
    isRecording = true;
    recordStartTime = Date.now();

    micBtn.classList.add("is-recording");
    micBtn.classList.remove("is-transcribing");
    micLabel.textContent = "listening...";
    micIcon.textContent = "🔴";
    audioStatus.textContent = "listening...";
  } catch (err) {
    console.error("Failed to start recording:", err);
    resetMicBtn();
  }
}

function stopRecording(e) {
  if (e) {
    if (e.pointerId && micBtn.releasePointerCapture) {
      try { micBtn.releasePointerCapture(e.pointerId); } catch (_) {}
    }
    e.preventDefault();
  }

  if (!isRecording) return;
  isRecording = false;

  const duration = Date.now() - recordStartTime;

  micBtn.classList.remove("is-recording");
  micBtn.classList.add("is-transcribing");
  micLabel.textContent = "transcribing...";
  micIcon.textContent = "⏳";
  audioStatus.textContent = "transcribing...";

  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }

  if (duration < 350) {
    setTimeout(() => {
      audioStatus.textContent = "Hold button while speaking, then release.";
      resetMicBtn();
    }, 400);
  }
}

async function handleRecordingStopped() {
  const duration = Date.now() - recordStartTime;
  if (duration < 350 || audioChunks.length === 0) {
    resetMicBtn();
    return;
  }

  try {
    const rawMime = (mediaRecorder && mediaRecorder.mimeType) || "audio/webm";
    const audioBlob = new Blob(audioChunks, { type: rawMime });

    const formData = new FormData();
    const isMp4 = rawMime.includes("mp4");
    const filename = isMp4 ? "recording.mp4" : "recording.webm";
    formData.append("audio", audioBlob, filename);
    if (sttModelSelect) {
      formData.append("stt_model", sttModelSelect.value);
    }

    const res = await fetch(TRANSCRIBE_ENDPOINT, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Transcription error (${res.status})`);
    }

    const data = await res.json();
    const text = (data.text || "").trim();

    if (!text) {
      audioStatus.textContent = "No speech detected. Please try again.";
      resetMicBtn();
      return;
    }

    // Put transcript in question box and show it on screen
    questionInput.value = text;
    audioStatus.textContent = `Transcribed: "${text}"`;

    resetMicBtn();

    // Run /ask and auto-play the answer
    await submitQuestion(text);
  } catch (err) {
    console.error("Transcription error:", err);
    audioStatus.textContent = `Transcribe failed: ${err.message}`;
    resetMicBtn();
  }
}

function resetMicBtn() {
  micBtn.classList.remove("is-recording");
  micBtn.classList.remove("is-transcribing");
  micLabel.textContent = "Hold to talk";
  micIcon.textContent = "🎙️";
  micBtn.disabled = false;
}

// Bind Hold-to-Talk Events
if (window.PointerEvent) {
  micBtn.addEventListener("pointerdown", startRecording);
  micBtn.addEventListener("pointerup", stopRecording);
  micBtn.addEventListener("pointercancel", stopRecording);
} else {
  micBtn.addEventListener("mousedown", startRecording);
  micBtn.addEventListener("mouseup", stopRecording);
  micBtn.addEventListener("mouseleave", stopRecording);
  micBtn.addEventListener("touchstart", startRecording, { passive: false });
  micBtn.addEventListener("touchend", stopRecording);
  micBtn.addEventListener("touchcancel", stopRecording);
}
micBtn.addEventListener("contextmenu", (e) => e.preventDefault());

window.addEventListener("pointerup", () => {
  if (isRecording) stopRecording();
});

// -------------------------------------------------------------
// Active Document Workbench Controller
// -------------------------------------------------------------
async function loadSamples() {
  try {
    const res = await fetch(SAMPLES_ENDPOINT);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    samples = await res.json();
    if (tabAllSamples) {
      tabAllSamples.textContent = `All (${samples.length})`;
    }
    renderThumbnailStrip();

    // Default select sample matching initial case or first sample
    if (selectedCase) {
      syncWorkbenchWithCase(selectedCase.case_id);
    } else if (samples.length > 0) {
      selectSample(samples[0]);
    }
  } catch (err) {
    console.error("Failed to load sample packets:", err);
    if (thumbnailStrip) {
      thumbnailStrip.innerHTML = `<div style="font-size: 11px; color: var(--danger); padding: 8px;">Error loading sample packets: ${err.message}</div>`;
    }
  }
}

function renderThumbnailStrip() {
  if (!thumbnailStrip) return;
  thumbnailStrip.innerHTML = "";

  const filtered = samples.filter((s) => {
    if (sampleViewFilter === "domain") {
      return s.domain === currentDomain;
    }
    return true;
  });

  if (workbenchCountBadge) {
    workbenchCountBadge.textContent = `${filtered.length} packet${filtered.length === 1 ? '' : 's'}`;
  }

  filtered.forEach((sample) => {
    const card = document.createElement("div");
    card.className = "thumb-card";
    if (activeSample && activeSample.id === sample.id) {
      card.classList.add("active");
    }

    const thumbImgSrc = sample.thumbnail_url || sample.file_url;
    card.innerHTML = `
      <div class="thumb-img-wrap">
        <img src="${thumbImgSrc}" alt="${sample.title}" loading="lazy" onerror="this.onerror=null; this.src='${sample.file_url}';" />
      </div>
      <div class="thumb-info">
        <span class="thumb-name" title="${sample.title}">${sample.filename}</span>
        <span class="thumb-case-tag">${sample.case_id}</span>
      </div>
    `;

    card.addEventListener("click", () => selectSample(sample, false));
    thumbnailStrip.appendChild(card);
  });

  // Ensure an active sample is displayed if current active is outside filter
  if (filtered.length > 0) {
    const isCurrentInFiltered = activeSample && filtered.some((s) => s.id === activeSample.id);
    if (!isCurrentInFiltered) {
      selectSample(filtered[0], false);
    }
  }
}

function selectSample(sample, updateInput = false) {
  if (!sample) return;
  activeSample = sample;
  if (sample.case_id) {
    sessionCaseId = sample.case_id;
  }

  // Update card active styles
  document.querySelectorAll(".thumb-card").forEach((card) => {
    const nameEl = card.querySelector(".thumb-name");
    if (nameEl && nameEl.textContent === sample.filename) {
      card.classList.add("active");
    } else {
      card.classList.remove("active");
    }
  });

  // Update preview viewer
  if (previewImage) {
    previewImage.src = sample.thumbnail_url || sample.file_url;
    previewImage.alt = sample.title;
    previewImage.onerror = () => {
      previewImage.onerror = null;
      if (sample.file_url && previewImage.src !== sample.file_url) {
        previewImage.src = sample.file_url;
      }
    };
    previewImage.hidden = false;
  }
  if (previewPlaceholder) {
    previewPlaceholder.hidden = true;
  }

  if (previewDocTitle) {
    previewDocTitle.textContent = sample.title;
  }
  if (previewDocMeta) {
    previewDocMeta.textContent = `${sample.case_id} • ${sample.doc_type} (${(sample.file_type || 'doc').toUpperCase()})`;
  }
  if (previewDesc) {
    previewDesc.textContent = sample.description;
  }
  if (openDocLink) {
    openDocLink.href = sample.file_url;
  }

  if (updateInput && questionInput) {
    questionInput.value = `what is missing in ${sample.case_id}`;
  }
}

function syncWorkbenchWithCase(caseId) {
  if (!caseId || !samples.length) return;

  const cidUpper = caseId.toUpperCase();
  const digits = (cidUpper.match(/\d+/) || [""])[0];

  // 1. Exact case_id and current domain match
  let matched = samples.find(
    (s) => s.case_id && s.case_id.toUpperCase() === cidUpper && s.domain === currentDomain
  );

  // 2. Exact case_id match
  if (!matched) {
    matched = samples.find((s) => s.case_id && s.case_id.toUpperCase() === cidUpper);
  }

  // 3. Digit and domain match (e.g. INS-H102 matches INS-102)
  if (!matched && digits) {
    matched = samples.find((s) => {
      if (s.domain !== currentDomain) return false;
      return (s.filename && s.filename.includes(digits)) || (s.id && s.id.includes(digits));
    });
  }

  if (matched) {
    selectSample(matched, false);
  }
}

// Enable horizontal wheel scroll for thumbnail strip
if (thumbnailStrip) {
  thumbnailStrip.addEventListener(
    "wheel",
    (e) => {
      if (e.deltaY !== 0) {
        e.preventDefault();
        thumbnailStrip.scrollLeft += e.deltaY;
      }
    },
    { passive: false }
  );
}

// Workbench Tabs
if (tabDomainSamples) {
  tabDomainSamples.addEventListener("click", () => {
    sampleViewFilter = "domain";
    tabDomainSamples.classList.add("active");
    if (tabAllSamples) tabAllSamples.classList.remove("active");
    renderThumbnailStrip();
  });
}

if (tabAllSamples) {
  tabAllSamples.addEventListener("click", () => {
    sampleViewFilter = "all";
    tabAllSamples.classList.add("active");
    if (tabDomainSamples) tabDomainSamples.classList.remove("active");
    renderThumbnailStrip();
  });
}

// Quick action: Query doc button
if (askDocBtn) {
  askDocBtn.addEventListener("click", () => {
    if (!activeSample) return;
    const query = `what is missing in ${activeSample.case_id}`;
    questionInput.value = query;
    submitQuestion(query);
  });
}

// Initial load
loadCases();
loadSamples();
