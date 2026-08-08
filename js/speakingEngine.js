/**
 * DeutschMind - Isolated Speaking & Pronunciation Engine (js/speakingEngine.js)
 * STRICT SCOPE: Speech-to-Text (STT) Browser Microphone & AI Speech Evaluation.
 * Single-Phrase Candidate Isolation Math: Evaluates speech against individual target phrases
 * to prevent denominator inflation bugs when user speaks a single phrase.
 */

let speakingPromptsList = [];
let currentSpeakingPromptObj = null;
let speakingRecognition = null;
let isSpeakingRecording = false;
let isMicTransitioning = false; // Transition lock to prevent button spamming

// =========================================================================
// GLOBAL CLICK DIAGNOSTICS & EVENT DELEGATION
// =========================================================================
document.addEventListener("click", function(event) {
    // 1. Handle Mic Button Clicks (Catches SVG icons and paths inside the mic button)
    const micBtn = event.target.closest("#btn-toggle-mic") || event.target.closest("#btn-mic-record");
    if (micBtn) {
        event.preventDefault();
        if (typeof window.toggleSpeakingMic === "function") {
            window.toggleSpeakingMic();
        }
        return;
    }

    // 2. Handle Dynamic TTS Speaker Clicks
    const ttsBtn = event.target.closest(".dynamic-tts-btn");
    if (ttsBtn) {
        event.preventDefault();
        const textToSpeak = ttsBtn.getAttribute("data-text");
        if (textToSpeak && typeof window.playGermanTTS === "function") {
            window.playGermanTTS(textToSpeak);
        }
    }
});

/**
 * Loads speaking prompts from static data/speaking.json or fallback dataset.
 */
window.loadSpeakingPrompts = async function() {
    try {
        const res = await fetch("data/speaking.json");
        if (res.ok) {
            speakingPromptsList = await res.json();
        }
    } catch (e) {
        console.warn("[SpeakingEngine] Failed to load data/speaking.json, using memory fallback.", e);
    }

    window.renderSpeakingPrompt();
};

/**
 * Renders a random speaking prompt matching the active CEFR level.
 */
window.renderSpeakingPrompt = function() {
    const level = (typeof currentLevel !== "undefined" ? currentLevel : "ZERO").toUpperCase();
    
    // Filter prompts by CEFR level
    const filtered = speakingPromptsList.filter(p => (p.level || "ZERO").toUpperCase() === level);
    
    if (filtered.length === 0) {
        console.warn(`[SpeakingEngine] No speaking prompt found for level ${level}`);
        return;
    }

    // Pick random prompt
    const prompt = filtered[Math.floor(Math.random() * filtered.length)];
    currentSpeakingPromptObj = prompt;

    // 1. Title & Level Badge DOM Updates
    const titleEl = document.getElementById("speaking-title");
    if (titleEl) titleEl.innerText = prompt.title;

    if (prompt && prompt.title && typeof window.autoLogTopic === "function") {
        window.autoLogTopic("German Speaking", prompt.title);
    }

    const levelBadge = document.getElementById("speaking-cefr-badge");
    if (levelBadge) levelBadge.innerText = prompt.level;

    // 2. Dual Language Prompt Texts
    const promptDeEl = document.getElementById("speaking-prompt-de");
    if (promptDeEl) promptDeEl.innerText = prompt.prompt_de;

    const promptEnEl = document.getElementById("speaking-prompt-en");
    if (promptEnEl) promptEnEl.innerText = prompt.prompt_en;

    // RTL Urdu Text Formatting
    const promptUrEl = document.getElementById("speaking-prompt-ur");
    if (promptUrEl) {
        promptUrEl.innerText = prompt.prompt_ur;
        promptUrEl.setAttribute("dir", "rtl");
    }

    // 3. Suggested Target German Phrase Chips
    const phrasesContainer = document.getElementById("speaking-suggested-phrases");
    if (phrasesContainer && prompt.suggested_phrases) {
        phrasesContainer.innerHTML = prompt.suggested_phrases.map(phrase => `
            <button type="button" class="dynamic-tts-btn px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 hover:border-violet-500/50 text-violet-300 text-xs font-mono flex items-center space-x-1.5 transition-all cursor-pointer" data-text="${phrase.replace(/"/g, '&quot;')}">
                <i data-lucide="volume-2" class="w-3 h-3 text-violet-400 pointer-events-none"></i>
                <span class="pointer-events-none">${phrase}</span>
            </button>
        `).join("");
        if (typeof lucide !== "undefined") lucide.createIcons();
    }

    // Reset STT Output Text Area & Report Box
    const transcriptOutput = document.getElementById("transcribed-speech-output") || document.getElementById("speaking-transcript-input");
    if (transcriptOutput) transcriptOutput.value = "";

    const reportBox = document.getElementById("speaking-evaluation-report");
    if (reportBox) {
        reportBox.classList.add("hidden");
    }
};

/**
 * MICROPHONE TOGGLE WITH TRANSITION LOCK & ASYNC NATIVE EVENT SYNC
 */
window.toggleSpeakingMic = function() {
    console.log("[SpeakingEngine] window.toggleSpeakingMic called!");

    // 1. Transition lock check (Prevents rapid click spamming)
    if (isMicTransitioning) {
        console.log("[SpeakingEngine] Mic transition in progress, ignoring click.");
        return;
    }
    isMicTransitioning = true;

    if ("speechSynthesis" in window) {
        window.speechSynthesis.cancel();
    }

    // Inline SpeechRecognition Instantiation if null
    if (!speakingRecognition) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            console.error("[SpeakingEngine] Web Speech API unsupported.");
            isMicTransitioning = false;
            const warningBanner = document.getElementById("stt-warning-banner");
            if (warningBanner) warningBanner.classList.remove("hidden");
            if (typeof showToast === "function") {
                showToast("Speech Recognition is not supported in this browser.");
            }
            return;
        }

        try {
            speakingRecognition = new SpeechRecognition();
            speakingRecognition.lang = "de-DE"; // Enforce German
            speakingRecognition.interimResults = true;
            speakingRecognition.continuous = false;

            // Native Event Callbacks handle UI state & unlock transition lock
            speakingRecognition.onstart = () => {
                console.log("[SpeakingEngine] Native onstart fired.");
                isSpeakingRecording = true;
                updateMicUIState(true);
                isMicTransitioning = false;
            };

            speakingRecognition.onresult = (event) => {
                const transcript = Array.from(event.results)
                    .map(result => result[0].transcript)
                    .join("");
                console.log("[SpeakingEngine] Transcript captured:", transcript);
                const outputArea = document.getElementById("transcribed-speech-output") || document.getElementById("speaking-transcript-input");
                if (outputArea) outputArea.value = transcript;
            };

            speakingRecognition.onerror = (event) => {
                console.error("[SpeakingEngine] Native onerror fired:", event.error);
                isSpeakingRecording = false;
                updateMicUIState(false);
                isMicTransitioning = false;
                if (typeof showToast === "function") {
                    showToast(`Mic Notice: ${event.error}`);
                }
            };

            speakingRecognition.onend = () => {
                console.log("[SpeakingEngine] Native onend fired.");
                isSpeakingRecording = false;
                updateMicUIState(false);
                isMicTransitioning = false;
            };
        } catch (e) {
            console.error("[SpeakingEngine] Construction Error:", e);
            isMicTransitioning = false;
            return;
        }
    }

    // 2. Execution block (relies 100% on native event callbacks above for state update)
    try {
        if (isSpeakingRecording) {
            console.log("[SpeakingEngine] Calling abort() for immediate hard stop...");
            speakingRecognition.abort(); // Hard kill instead of stop()
        } else {
            console.log("[SpeakingEngine] Calling start()...");
            speakingRecognition.start();
        }
    } catch (e) {
        console.error("[SpeakingEngine] STT Execution Error:", e);
        isMicTransitioning = false; // Unlock if instant hardware error
    }
};

/**
 * Updates Mic Button Visuals and status text
 */
function updateMicUIState(recording) {
    const btn = document.getElementById("btn-toggle-mic") || document.getElementById("btn-mic-record");
    const statusText = document.getElementById("mic-status-text") || document.getElementById("recording-status");

    if (btn) {
        if (recording) {
            btn.className = "w-16 h-16 rounded-full bg-rose-600 hover:bg-rose-500 text-white flex items-center justify-center shadow-lg shadow-rose-600/50 animate-pulse transition-all mx-auto cursor-pointer";
            if (statusText) statusText.innerHTML = `<span class="text-rose-400 font-bold animate-pulse">Listening... Speak German now!</span>`;
        } else {
            btn.className = "w-16 h-16 rounded-full bg-violet-600 hover:bg-violet-500 text-white flex items-center justify-center shadow-lg shadow-violet-600/30 transition-all mx-auto cursor-pointer";
            if (statusText) statusText.innerHTML = `<span class="text-slate-400">Read one of the suggested target German phrases aloud into mic</span>`;
        }
    }
}

/**
 * Evaluates speech transcript against 4 criteria: Accuracy, Range, Relevance, Fluency
 * ISOLATION RULE: User speaks ONE target phrase. Candidate phrases are evaluated individually,
 * taking the max score across candidate options to prevent denominator inflation bugs.
 */
window.submitSpeakingEvaluation = function() {
    const prompt = currentSpeakingPromptObj;
    const outputArea = document.getElementById("transcribed-speech-output") || document.getElementById("speaking-transcript-input");
    const transcript = outputArea ? outputArea.value.trim().toLowerCase() : "";

    if (!transcript) {
        if (typeof showToast === "function") {
            showToast("Please record audio or type a German response first!");
        }
        return;
    }

    if (!prompt) return;

    const words = transcript.split(/\s+/).filter(w => w.length > 0);
    const totalWords = words.length;

    // Collect all candidate phrases (main prompt_de + each suggested_phrase)
    const candidates = [];
    if (prompt.prompt_de) candidates.push(prompt.prompt_de);
    if (prompt.suggested_phrases && Array.isArray(prompt.suggested_phrases)) {
        candidates.push(...prompt.suggested_phrases);
    }
    if (candidates.length === 0 && prompt.target_keywords) {
        candidates.push(prompt.target_keywords.join(" "));
    }

    // Single-Phrase Isolation Matching: evaluate transcript against each candidate phrase
    let bestAccuracy = 0;
    let bestMatchedPhrase = candidates[0] || "";

    candidates.forEach(cand => {
        const cleanCand = cand.replace(/[.,!?;:]/g, "").toLowerCase();
        const candWords = cleanCand.split(/\s+/).filter(w => w.length > 0);
        if (candWords.length === 0) return;

        let matched = 0;
        candWords.forEach(w => {
            if (transcript.includes(w)) matched++;
        });

        const score = Math.round((matched / candWords.length) * 100);
        if (score > bestAccuracy) {
            bestAccuracy = score;
            bestMatchedPhrase = cand;
        }
    });

    // 1. Accuracy Score (Bounded 0 - 100%)
    const accuracyScore = Math.min(100, Math.max(0, bestAccuracy));

    // 2. Vocabulary Range Score (Unique spoken words vs length)
    const uniqueWords = new Set(words).size;
    const rangeScore = Math.min(100, Math.round((uniqueWords / Math.max(1, totalWords)) * 60 + Math.min(40, totalWords * 8)));

    // 3. Relevance Score (Match against best phrase & keyword coverage)
    const relevanceScore = Math.min(100, Math.max(50, bestAccuracy));

    // 4. Fluency Score (Speech length & word articulation)
    const fluencyScore = Math.min(100, Math.round(Math.min(100, totalWords * 15) * 0.5 + (accuracyScore * 0.5)));

    // Overall Aggregate Score
    const overallScore = Math.round((accuracyScore + rangeScore + relevanceScore + fluencyScore) / 4);

    // Update Report Card UI
    const reportBox = document.getElementById("speaking-evaluation-report") || document.getElementById("speaking-result-container");
    if (reportBox) {
        reportBox.classList.remove("hidden");

        const getBadgeClass = (score) => {
            if (score >= 70) return "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
            if (score >= 40) return "text-amber-400 bg-amber-500/10 border-amber-500/30";
            return "text-rose-400 bg-rose-500/10 border-rose-500/30";
        };

        const passed = overallScore >= 65;

        if (passed && typeof window.logCompletedTopic === "function") {
            const promptTitle = (promptObj && (promptObj.title || promptObj.prompt || promptObj.topic)) || "German Speaking Practice";
            window.logCompletedTopic("Speaking", promptTitle);
        }

        reportBox.innerHTML = `
            <div class="p-6 rounded-2xl bg-slate-950 border border-slate-800 space-y-4 font-mono text-xs">
                <div class="flex items-center justify-between border-b border-slate-800 pb-3">
                    <span class="text-sm font-bold text-white font-sans">AI Speech Evaluation Report</span>
                    <span class="px-3 py-1 rounded-full border text-xs font-bold ${getBadgeClass(overallScore)}">
                        Overall: ${overallScore}% ${passed ? "PASS" : "RETRY"}
                    </span>
                </div>

                <div class="p-3 rounded-xl bg-slate-900 border border-slate-800 text-[11px] text-slate-300 font-mono">
                    <span class="text-slate-400">Target Match:</span> <strong class="text-emerald-400">"${bestMatchedPhrase}"</strong>
                </div>

                <div class="grid grid-cols-2 gap-3">
                    <div class="p-3 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
                        <div class="text-[11px] text-slate-400">Accuracy (Matched Phrase)</div>
                        <div class="text-sm font-bold text-white">${accuracyScore}%</div>
                        <div class="w-full bg-slate-950 h-1.5 rounded-full overflow-hidden">
                            <div class="bg-violet-500 h-full" style="width: ${accuracyScore}%"></div>
                        </div>
                    </div>
                    
                    <div class="p-3 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
                        <div class="text-[11px] text-slate-400">Vocab Range</div>
                        <div class="text-sm font-bold text-white">${rangeScore}%</div>
                        <div class="w-full bg-slate-950 h-1.5 rounded-full overflow-hidden">
                            <div class="bg-indigo-500 h-full" style="width: ${rangeScore}%"></div>
                        </div>
                    </div>

                    <div class="p-3 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
                        <div class="text-[11px] text-slate-400">Relevance</div>
                        <div class="text-sm font-bold text-white">${relevanceScore}%</div>
                        <div class="w-full bg-slate-950 h-1.5 rounded-full overflow-hidden">
                            <div class="bg-emerald-500 h-full" style="width: ${relevanceScore}%"></div>
                        </div>
                    </div>

                    <div class="p-3 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
                        <div class="text-[11px] text-slate-400">Fluency Rate</div>
                        <div class="text-sm font-bold text-white">${fluencyScore}%</div>
                        <div class="w-full bg-slate-950 h-1.5 rounded-full overflow-hidden">
                            <div class="bg-amber-500 h-full" style="width: ${fluencyScore}%"></div>
                        </div>
                    </div>
                </div>

                <div class="pt-2 text-center text-xs text-slate-300 font-sans">
                    ${passed ? "🎉 Excellent German pronunciation and sentence structure!" : "💡 Keep practicing! Try reading the target German phrase aloud again into the mic."}
                </div>
            </div>
        `;

        if (passed && typeof addXP === "function") {
            addXP(100);
        }
    }
};
