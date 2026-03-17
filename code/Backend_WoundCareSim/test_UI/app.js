// ── Scripted history conversations ───────────────────────────────────────────
const HISTORY_SCRIPTS = {
    focused_history: [
        "Hello, I am here to ask a few questions before wound care.",
        "Can you tell me your name and age?",
        "Do you have any allergies?",
        "What surgery did you have and when was it done?",
        "Are you having any pain at the moment?"
    ],
    short_history: [
        "What procedure did you have?",
        "Do you have any allergies?",
        "How is your pain right now?"
    ]
};

// ── Cleaning procedure actions ───────────────────────────────────────────────
const PROCEDURE_ACTIONS = [
    { code: "hand_hygiene_initial",  label: "Initial Hand Hygiene",           backendActionType: "action_initial_hand_hygiene" },
    { code: "clean_trolley",         label: "Clean Trolley",                  backendActionType: "action_clean_trolley" },
    { code: "hand_hygiene_again",    label: "Hand Hygiene After Cleaning",    backendActionType: "action_hand_hygiene_after_cleaning" },
    { code: "select_solution",       label: "Select Solution",                backendActionType: "action_select_solution" },
    { code: "verify_solution",       label: "Verify Solution",                backendActionType: "action_verify_solution" },
    { code: "select_dressing",       label: "Select Dressing",                backendActionType: "action_select_dressing" },
    { code: "verify_dressing",       label: "Verify Dressing",                backendActionType: "action_verify_dressing" },
    { code: "arrange_materials",     label: "Arrange Materials",              backendActionType: "action_arrange_materials" },
    { code: "bring_trolley",         label: "Bring Trolley",                  backendActionType: "action_bring_trolley" }
];

// ── App state ────────────────────────────────────────────────────────────────
const state = {
    apiBaseUrl:    "http://127.0.0.1:8000",
    wsBaseUrl:     "ws://127.0.0.1:8000",
    activeSession: null,
    sessionInfo:   null,
    ws:            null,
    wsConnected:   false,
    logEntries:    [],
    lastStructuredResponse: null,
    currentStep:   null,
    selectedMcqAnswers: {},
    completedActions:   new Set(),
    patientMessages:    [],   // newest first
    nurseMessages:      [],   // newest first
    historyTransitionPendingConfirmation: false,
    autoPollHandle: null,
    scriptRunning:  false,

    // Audio
    audioContext:   null,
    ttsQueue:       [],
    ttsPlaying:     false,

    // STT
    mediaRecorder:  null,
    sttChunks:      [],
    sttRecording:   false
};

// ── Helpers ──────────────────────────────────────────────────────────────────
const qs = id => document.getElementById(id);

function sanitize(v) {
    return String(v ?? "")
        .replace(/&/g, "&amp;").replace(/</g, "&lt;")
        .replace(/>/g, "&gt;").replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

function getApiBase() { return qs("apiBaseUrl").value.trim().replace(/\/$/, ""); }
function getWsBase()  { return qs("wsBaseUrl").value.trim().replace(/\/$/, ""); }

async function apiCall(path, opts = {}) {
    const res = await fetch(`${state.apiBaseUrl}${path}`, opts);
    if (!res.ok) {
        let detail = res.statusText;
        try { const d = await res.json(); detail = d.detail || JSON.stringify(d); } catch {}
        throw new Error(detail);
    }
    return res.json();
}

// ── Audio: TTS playback ───────────────────────────────────────────────────────
function ensureAudioContext() {
    if (!state.audioContext) {
        state.audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    // Resume if suspended (browser autoplay policy)
    if (state.audioContext.state === "suspended") {
        state.audioContext.resume();
    }
    return state.audioContext;
}

function setAudioStatus(mode, label) {
    const el = qs("audioStatus");
    const iconEl = qs("audioIcon");
    const labelEl = qs("audioLabel");
    el.className = "audio-status " + (mode || "");
    labelEl.textContent = label;
    const icons = { playing: "♫", recording: "●", "": "♪" };
    iconEl.textContent = icons[mode] ?? "♪";
}

async function playTtsAudio(base64wav, role) {
    // Enqueue
    state.ttsQueue.push({ base64wav, role });
    if (!state.ttsPlaying) drainTtsQueue();
}

async function drainTtsQueue() {
    if (!state.ttsQueue.length) {
        state.ttsPlaying = false;
        setAudioStatus("", "Audio ready");
        return;
    }
    state.ttsPlaying = true;
    const { base64wav, role } = state.ttsQueue.shift();

    const roleLabel = {
        patient:    "Patient speaking…",
        staff_nurse:"Nurse speaking…",
        nurse:      "Nurse speaking…",
        feedback:   "Feedback narrating…",
        assessment_feedback: "Assessment feedback…",
        realtime_feedback:   "Feedback narrating…"
    }[role] || "Playing audio…";

    setAudioStatus("playing", roleLabel);

    try {
        const ctx = ensureAudioContext();
        const binary = atob(base64wav);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
        const buffer = await ctx.decodeAudioData(bytes.buffer);
        const src = ctx.createBufferSource();
        src.buffer = buffer;
        src.connect(ctx.destination);
        await new Promise(resolve => {
            src.onended = resolve;
            src.start(0);
        });
    } catch (err) {
        console.warn("TTS playback error:", err);
    }
    drainTtsQueue();
}

// Extract TTS audio from server event data and play it
function tryPlayTtsFromEvent(data) {
    const audioField = data?.staff_nurse_audio || data?.feedback_audio || data?.patient_audio || data?.audio;
    const base64 = audioField?.audio_base64 || (typeof audioField === "string" ? audioField : null);
    if (!base64) return;
    const role = data?.role || data?.staff_nurse_audio ? "staff_nurse" : "feedback";
    playTtsAudio(base64, role);
}

// ── Audio: STT recording ──────────────────────────────────────────────────────
async function startSttRecording() {
    if (state.sttRecording) return;
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        state.sttChunks = [];
        state.mediaRecorder = new MediaRecorder(stream);
        state.mediaRecorder.ondataavailable = e => {
            if (e.data.size > 0) state.sttChunks.push(e.data);
        };
        state.mediaRecorder.onstop = handleSttResult;
        state.mediaRecorder.start();
        state.sttRecording = true;
        qs("sttBtn").classList.add("recording");
        qs("micIcon").textContent = "⏹";
        setAudioStatus("recording", "Recording…");
    } catch (err) {
        console.warn("Microphone access denied:", err);
        setAudioStatus("", "Mic access denied");
    }
}

function stopSttRecording() {
    if (!state.sttRecording || !state.mediaRecorder) return;
    state.mediaRecorder.stop();
    state.mediaRecorder.stream.getTracks().forEach(t => t.stop());
    state.sttRecording = false;
    qs("sttBtn").classList.remove("recording");
    qs("micIcon").textContent = "🎤";
    setAudioStatus("", "Processing speech…");
}

async function handleSttResult() {
    if (!state.sttChunks.length) {
        setAudioStatus("", "Audio ready");
        return;
    }
    const blob = new Blob(state.sttChunks, { type: "audio/webm" });
    const formData = new FormData();
    formData.append("file", blob, "recording.webm");

    try {
        const res = await fetch(`${state.apiBaseUrl}/audio/transcribe`, {
            method: "POST",
            body: formData
        });
        if (res.ok) {
            const data = await res.json();
            const text = data.transcript || data.text || "";
            if (text) {
                qs("historyMessageInput").value = text;
                setAudioStatus("", "Transcribed — press Send");
            } else {
                setAudioStatus("", "No speech detected");
            }
        } else {
            setAudioStatus("", "Transcription failed");
        }
    } catch (err) {
        console.warn("STT error:", err);
        setAudioStatus("", "STT unavailable");
    }
}

// ── Session strip & connection UI ────────────────────────────────────────────
function updateConnectionUi() {
    const c = state.wsConnected;
    qs("wsStatus").textContent = c ? "Online" : "Offline";
    qs("wsStatus").className = `meta-val ws-badge ${c ? "connected" : "disconnected"}`;
    qs("connectSessionBtn").disabled    = c || !state.activeSession?.session_id;
    qs("disconnectSessionBtn").disabled = !c;
}

function updateSessionStrip() {
    const a = state.activeSession;
    const i = state.sessionInfo;
    qs("sessionId").textContent   = (a?.session_id  || i?.session_id  || "—").slice(0, 22);
    qs("scenarioId").textContent  = a?.scenario_id  || i?.scenario_id  || "—";
    qs("currentStep").textContent = state.currentStep || i?.current_step || "—";
}

function renderActiveSessionStatus(msg) {
    qs("activeSessionStatus").textContent = msg;
}

// ── Step tab rendering ───────────────────────────────────────────────────────
function setPanelState(step) {
    const map = {
        history:               { tabId: "tab-history",    stateId: "historyStepState",    panelId: "historyPanel" },
        assessment:            { tabId: "tab-assessment",  stateId: "assessmentStepState", panelId: "assessmentPanel" },
        cleaning_and_dressing: { tabId: "tab-cleaning",   stateId: "cleaningStepState",   panelId: "cleaningPanel" }
    };

    Object.entries(map).forEach(([key, { tabId, stateId, panelId }]) => {
        const isActive = step === key;
        const tab   = qs(tabId);
        const state = qs(stateId);
        const panel = qs(panelId);
        tab.classList.toggle("active", isActive);
        state.textContent = isActive ? "Active" : "Inactive";
        panel.classList.toggle("hidden", !isActive);
    });
}

// ── Chat bubble rendering ────────────────────────────────────────────────────
function appendBubble(containerId, role, text) {
    const container = qs(containerId);
    const empty = container.querySelector(".chat-empty");
    if (empty) empty.remove();

    const bubble = document.createElement("div");
    const cls = role === "student" ? "bubble-student" : role === "nurse" ? "bubble-nurse" : "bubble-patient";
    bubble.className = `bubble ${cls}`;
    const roleLabel = role === "student" ? "You" : role.charAt(0).toUpperCase() + role.slice(1);
    bubble.innerHTML = `<div class="bubble-role">${sanitize(roleLabel)}</div>${sanitize(text)}`;

    // Insert at top of column-reverse container (visually bottom)
    container.insertBefore(bubble, container.firstChild);
}

function renderChatFromArray(containerId, items, emptyMsg) {
    const container = qs(containerId);
    if (!items.length) {
        container.innerHTML = `<div class="chat-empty">${sanitize(emptyMsg)}</div>`;
        return;
    }
    container.innerHTML = items.slice().reverse().map(item => {
        const cls = item.role === "student" ? "bubble-student" : item.role === "nurse" ? "bubble-nurse" : "bubble-patient";
        const label = item.role === "student" ? "You" : item.role.charAt(0).toUpperCase() + item.role.slice(1);
        return `<div class="bubble ${cls}"><div class="bubble-role">${sanitize(label)}</div>${sanitize(item.text)}</div>`;
    }).join("");
}

// ── Feedback card rendering ──────────────────────────────────────────────────
function renderFeedbackCard(containerId, payload) {
    const container = qs(containerId);
    if (!payload) {
        container.innerHTML = '<div class="feedback-empty">No data yet.</div>';
        return;
    }

    const rows = Object.entries(payload).map(([key, value]) => {
        let valStr = typeof value === "object" ? JSON.stringify(value, null, 2) : String(value);
        let valClass = "feedback-val";
        const v = String(value).toLowerCase();
        if (v === "true" || v === "complete" || v === "appropriate") valClass += " ok";
        else if (v === "false" || v.includes("missing") || v === "inappropriate") valClass += " err";
        else if (v.includes("partial")) valClass += " warn";
        return `<div class="feedback-row">
            <div class="feedback-key">${sanitize(key)}</div>
            <div class="${valClass}">${sanitize(valStr)}</div>
        </div>`;
    }).join("");

    container.innerHTML = rows;
}

// ── MCQ rendering ────────────────────────────────────────────────────────────
function renderMcqs() {
    const container = qs("mcqContainer");
    const questions = state.sessionInfo?.scenario_metadata?.assessment_questions || [];

    if (!questions.length) {
        container.innerHTML = '<div class="feedback-empty">No assessment questions available.</div>';
        return;
    }

    container.innerHTML = questions.map((q, idx) => {
        const selected = state.selectedMcqAnswers[q.id]?.answer;
        const result   = state.selectedMcqAnswers[q.id]?.result;
        const cardCls  = result?.status || "";
        return `<div class="mcq-card ${sanitize(cardCls)}" id="mcq-${sanitize(q.id)}">
            <p class="mcq-question">${idx + 1}. ${sanitize(q.question)}</p>
            <div class="mcq-options">
                ${q.options.map(opt => `
                    <button class="mcq-option ${selected === opt ? "selected" : ""}"
                        data-question-id="${sanitize(q.id)}"
                        data-answer="${sanitize(opt)}">
                        ${sanitize(opt)}
                    </button>`).join("")}
            </div>
            <div class="mcq-feedback">
                ${result
                    ? `<strong>${result.is_correct ? "✓ Correct." : "✗ Incorrect."}</strong> ${sanitize(result.explanation || "")}`
                    : "Awaiting answer."}
            </div>
        </div>`;
    }).join("");

    container.querySelectorAll(".mcq-option").forEach(btn => {
        btn.addEventListener("click", () => submitMcqAnswer(btn.dataset.questionId, btn.dataset.answer));
    });
}

// ── Action button rendering ──────────────────────────────────────────────────
function renderActionButtons() {
    const container = qs("actionGrid");
    container.innerHTML = PROCEDURE_ACTIONS.map(a => {
        const done = state.completedActions.has(a.backendActionType);
        return `<button class="action-button ${done ? "completed" : ""}"
                    data-action-code="${sanitize(a.code)}"
                    data-action-type="${sanitize(a.backendActionType)}">
                <span class="action-label">${sanitize(a.label)}</span>
                <span class="action-code">${sanitize(a.code)}</span>
            </button>`;
    }).join("");

    container.querySelectorAll(".action-button").forEach(btn => {
        btn.addEventListener("click", () => submitAction(btn.dataset.actionCode, btn.dataset.actionType));
    });
}

// ── Session polling & connection ─────────────────────────────────────────────
async function refreshActiveSession() {
    state.apiBaseUrl = getApiBase();
    state.wsBaseUrl  = getWsBase();
    try {
        const active = await apiCall("/session/active");
        state.activeSession = active?.session_id ? active : null;
        renderActiveSessionStatus(
            state.activeSession
                ? `Session ready: ${state.activeSession.session_id}`
                : "Waiting for teacher to start a session…"
        );
    } catch (err) {
        renderActiveSessionStatus(`Cannot reach server: ${err.message}`);
    }
    updateSessionStrip();
    updateConnectionUi();
}

async function refreshSessionDetails() {
    const id = state.activeSession?.session_id || state.sessionInfo?.session_id;
    if (!id) return;
    try {
        const info = await apiCall(`/session/${id}`);
        state.sessionInfo  = info;
        state.currentStep  = info.current_step;
        updateSessionStrip();
        setPanelState(state.currentStep);
        renderMcqs();
        renderActionButtons();
    } catch {}
}

function connectToActiveSession() {
    const active = state.activeSession;
    if (!active?.session_id || !active?.session_token) {
        renderActiveSessionStatus("No connectable session found.");
        return;
    }
    if (state.ws && [WebSocket.OPEN, WebSocket.CONNECTING].includes(state.ws.readyState)) return;

    // Unlock AudioContext on first user interaction
    ensureAudioContext();

    const url = `${state.wsBaseUrl}/ws/session/${encodeURIComponent(active.session_id)}?token=${encodeURIComponent(active.session_token)}`;
    state.ws = new WebSocket(url);

    state.ws.onopen = async () => {
        state.wsConnected = true;
        updateConnectionUi();
        await refreshSessionDetails();
    };

    state.ws.onmessage = async event => {
        try {
            const payload = JSON.parse(event.data);
            state.lastStructuredResponse = payload;
            await handleServerMessage(payload);
        } catch {}
    };

    state.ws.onerror = () => {};

    state.ws.onclose = () => {
        state.wsConnected = false;
        updateConnectionUi();
    };
}

function disconnectSession() {
    if (state.ws) state.ws.close();
    state.ws = null;
    state.wsConnected = false;
    updateConnectionUi();
}

// ── WS send ──────────────────────────────────────────────────────────────────
function sendEvent(eventName, data = {}) {
    if (!state.wsConnected || !state.ws || state.ws.readyState !== WebSocket.OPEN) return false;
    state.ws.send(JSON.stringify({ type: "event", event: eventName, data }));
    // track log entry for export
    state.logEntries.push({ ts: new Date().toISOString(), dir: "sent", event: eventName, data });
    return true;
}

// ── Server message handler ───────────────────────────────────────────────────
async function handleServerMessage(message) {
    if (message.type === "error") return;

    const data = message.data || {};
    // Track for export
    state.logEntries.push({ ts: new Date().toISOString(), dir: "received", event: message.event || message.type, data });

    switch (message.event) {
        case "nurse_message": {
            // ── Play TTS audio ──
            const audioPayload = data?.tts_audio || data;
            const base64 = audioPayload?.audio_bytes || audioPayload?.audio_base64 ||
                           data?.patient_audio?.audio_base64 || data?.staff_nurse_audio?.audio_base64;
            if (base64) playTtsAudio(base64, data.role || "patient");

            // ── Render bubble ──
            const text = data.text || "";
            if (data.role === "patient") {
                state.patientMessages.unshift({ role: "patient", text });
                renderChatFromArray("historyResponses", state.patientMessages, "Patient responses will appear here.");
            } else if (text) {
                state.nurseMessages.unshift({ role: data.role || "nurse", text });
                renderChatFromArray("nurseResponses", state.nurseMessages, "Nurse responses appear here.");
            }
            break;
        }

        case "tts_audio": {
            // Dedicated TTS audio event from WebSocket
            const base64 = data?.audio_bytes || data?.audio_base64;
            if (base64) playTtsAudio(base64, data.role || "feedback");
            break;
        }

        case "mcq_answer_result":
            state.selectedMcqAnswers[data.question_id] = {
                ...(state.selectedMcqAnswers[data.question_id] || {}),
                result: data
            };
            renderMcqs();
            break;

        case "real_time_feedback": {
            if (data.action_recorded && data.action_type) {
                state.completedActions.add(data.action_type);
                renderActionButtons();
            }
            // TTS for cleaning feedback
            const feedAudio = data?.feedback_audio?.audio_base64 || data?.staff_nurse_audio?.audio_base64;
            if (feedAudio) playTtsAudio(feedAudio, "staff_nurse");
            renderFeedbackCard("cleaningFeedback", data.feedback || data);
            break;
        }

        case "final_feedback": {
            state.historyTransitionPendingConfirmation = true;
            qs("confirmHistoryTransitionBtn").disabled = false;
            // TTS for narrated feedback
            const narAudio = data?.feedback_audio?.audio_base64 || data?.narrated_feedback_audio?.audio_base64;
            if (narAudio) playTtsAudio(narAudio, "feedback");
            renderFeedbackCard("historyFeedback", data);
            break;
        }

        case "assessment_summary": {
            const sumAudio = data?.feedback_audio?.audio_base64;
            if (sumAudio) playTtsAudio(sumAudio, "assessment_feedback");
            renderFeedbackCard("assessmentSummary", data);
            break;
        }

        case "step_complete":
            state.historyTransitionPendingConfirmation = false;
            qs("confirmHistoryTransitionBtn").disabled = true;
            if (data.next_step) {
                state.currentStep = data.next_step;
                if (data.next_step === "completed") {
                    renderFeedbackCard("assessmentSummary", {
                        status: "completed",
                        message: "All steps complete. Session finished."
                    });
                }
            }
            await refreshSessionDetails();
            break;

        case "session_end":
            state.currentStep = "completed";
            if (state.sessionInfo) state.sessionInfo.current_step = "completed";
            updateSessionStrip();
            setPanelState("completed");
            break;
    }
}

// ── Step interactions ────────────────────────────────────────────────────────
async function submitHistoryMessage() {
    if (state.currentStep !== "history") return;
    const input = qs("historyMessageInput");
    const text  = input.value.trim();
    if (!text) return;
    const sent = sendEvent("text_message", { text });
    if (sent) {
        // Show student bubble immediately
        state.patientMessages.unshift({ role: "student", text });
        renderChatFromArray("historyResponses", state.patientMessages, "Patient responses will appear here.");
        input.value = "";
    }
}

function submitMcqAnswer(questionId, answer) {
    if (state.currentStep !== "assessment") return;
    state.selectedMcqAnswers[questionId] = { ...(state.selectedMcqAnswers[questionId] || {}), answer };
    renderMcqs();
    sendEvent("mcq_answer", { question_id: questionId, answer });
}

function submitAction(actionCode, backendActionType) {
    if (state.currentStep !== "cleaning_and_dressing") return;
    sendEvent("action_performed", { action_type: backendActionType, action: actionCode });
}

function completeCurrentStep() {
    if (!state.currentStep) return;
    sendEvent("step_complete", { step: state.currentStep });
}

function confirmHistoryTransition() {
    if (!state.historyTransitionPendingConfirmation) return;
    sendEvent("confirm_step_transition");
}

// ── Scripted automation ──────────────────────────────────────────────────────
async function loadHistoryScript() {
    const lines = HISTORY_SCRIPTS[qs("historyScriptSelect").value] || [];
    qs("historyScriptEditor").value = lines.join("\n");
}

async function runHistoryScript() {
    if (state.currentStep !== "history" || state.scriptRunning) return;
    const lines = qs("historyScriptEditor").value.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
    if (!lines.length) return;
    state.scriptRunning = true;
    try {
        for (const line of lines) {
            qs("historyMessageInput").value = line;
            await submitHistoryMessage();
            await sleep(700);
        }
    } finally {
        state.scriptRunning = false;
    }
}

async function runMcqScript(mode) {
    if (state.currentStep !== "assessment") return;
    const questions = state.sessionInfo?.scenario_metadata?.assessment_questions || [];
    for (const q of questions) {
        const answer = mode === "correct" ? q.correct_answer : q.options?.[0];
        if (answer) { submitMcqAnswer(q.id, answer); await sleep(250); }
    }
}

async function runActionSequence() {
    if (state.currentStep !== "cleaning_and_dressing") return;
    for (const action of PROCEDURE_ACTIONS) {
        submitAction(action.code, action.backendActionType);
        await sleep(350);
    }
}

// ── Export ───────────────────────────────────────────────────────────────────
async function exportSessionLog() {
    const sessionId = state.activeSession?.session_id || state.sessionInfo?.session_id;
    let backendLog = null;
    if (sessionId) {
        try { backendLog = await apiCall(`/session/${sessionId}/log`); }
        catch (err) { backendLog = { error: err.message }; }
    }
    const payload = {
        exported_at: new Date().toISOString(),
        active_session: state.activeSession,
        session_info: state.sessionInfo,
        current_step: state.currentStep,
        selected_mcq_answers: state.selectedMcqAnswers,
        completed_actions: Array.from(state.completedActions),
        websocket_log: state.logEntries,
        last_structured_response: state.lastStructuredResponse,
        backend_session_log: backendLog
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url  = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url; link.download = `${sessionId || "session"}-log.json`;
    document.body.appendChild(link); link.click(); link.remove();
    URL.revokeObjectURL(url);
}

// ── Auto-poll ────────────────────────────────────────────────────────────────
function startAutoPoll() {
    if (state.autoPollHandle) clearInterval(state.autoPollHandle);
    state.autoPollHandle = setInterval(() => {
        if (!state.wsConnected) refreshActiveSession();
    }, 5000);
}

// ── Event binding ────────────────────────────────────────────────────────────
function bindEvents() {
    qs("refreshActiveSessionBtn").addEventListener("click", refreshActiveSession);
    qs("connectSessionBtn").addEventListener("click", connectToActiveSession);
    qs("disconnectSessionBtn").addEventListener("click", disconnectSession);
    qs("refreshSessionDetailsBtn").addEventListener("click", refreshSessionDetails);
    qs("exportJsonBtn").addEventListener("click", exportSessionLog);

    // History
    qs("sendHistoryMessageBtn").addEventListener("click", submitHistoryMessage);
    qs("historyMessageInput").addEventListener("keydown", e => {
        if (e.key === "Enter") { e.preventDefault(); submitHistoryMessage(); }
    });
    qs("completeHistoryBtn").addEventListener("click", completeCurrentStep);
    qs("confirmHistoryTransitionBtn").addEventListener("click", confirmHistoryTransition);
    qs("loadHistoryScriptBtn").addEventListener("click", loadHistoryScript);
    qs("runHistoryScriptBtn").addEventListener("click", runHistoryScript);

    // STT mic — click to toggle
    qs("sttBtn").addEventListener("click", () => {
        if (state.sttRecording) stopSttRecording();
        else startSttRecording();
    });

    // Assessment
    qs("answerAllCorrectBtn").addEventListener("click", () => runMcqScript("correct"));
    qs("answerAllFirstBtn").addEventListener("click",   () => runMcqScript("first"));
    qs("completeAssessmentBtn").addEventListener("click", completeCurrentStep);

    // Cleaning
    qs("runActionSequenceBtn").addEventListener("click", runActionSequence);
    qs("completeCleaningBtn").addEventListener("click",  completeCurrentStep);

    // URL changes
    qs("apiBaseUrl").addEventListener("change", refreshActiveSession);
    qs("wsBaseUrl").addEventListener("change",  refreshActiveSession);
}

// ── Init ─────────────────────────────────────────────────────────────────────
function initializeUi() {
    // Populate script dropdown
    const sel = qs("historyScriptSelect");
    sel.innerHTML = Object.keys(HISTORY_SCRIPTS).map(k =>
        `<option value="${sanitize(k)}">${sanitize(k)}</option>`
    ).join("");
    loadHistoryScript();

    renderMcqs();
    renderActionButtons();
    updateSessionStrip();
    updateConnectionUi();
    setPanelState(null);
    bindEvents();
    startAutoPoll();
    refreshActiveSession();
}

window.addEventListener("beforeunload", () => {
    if (state.autoPollHandle) clearInterval(state.autoPollHandle);
    disconnectSession();
});

document.addEventListener("DOMContentLoaded", initializeUi);
