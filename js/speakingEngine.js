/**
 * DeutschMind - Isolated Speaking & Pronunciation Engine (js/speakingEngine.js)
 * STRICT SCOPE: Speech-to-Text (STT) Browser Microphone & AI Speech Evaluation.
 * Binds toggleSpeakingMic and engine functions globally on window.
 */

let speakingPromptsList = [];
let currentSpeakingPromptObj = null;
let speakingRecognition = null;
let isSpeakingRecording = false;

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
            <button onclick="window.playGermanTTS('${phrase.replace(/'/g, "\\'").replace(/"/g, '&quot;')}')" class="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 hover:border-violet-500/50 text-violet-300 text-xs font-mono flex items-center space-x-1.5 transition-all">
                <i data-lucide="volume-2" class="w-3 h-3 text-violet-400"></i>
                <span>${phrase}</span>
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

    // Check Browser Compatibility
    initSpeechRecognition();
};

/**
 * Bulletproof STT Initialization supporting standard & webkit SpeechRecognition
 */
function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const warningBanner = document.getElementById("stt-warning-banner");

    if (!SpeechRecognition) {
        console.error("[SpeakingEngine] Web Speech API (SpeechRecognition / webkitSpeechRecognition) is unsupported.");
        if (warningBanner) {
            warningBanner.classList.remove("hidden");
            warningBanner.innerText = "⚠ Speech Recognition API is not supported in this browser. You can type your German response manually below.";
        }
        return;
    }

    if (warningBanner) warningBanner.classList.add("hidden");

    if (!speakingRecognition) {
        speakingRecognition = new SpeechRecognition();
        speakingRecognition.continuous = false;
        speakingRecognition.interimResults = true;
        speakingRecognition.lang = "de-DE";

        speakingRecognition.onstart = () => {
            console.log("[SpeakingEngine] Speech recognition started.");
            isSpeakingRecording = true;
            updateMicUIState(true);
        };

        speakingRecognition.onresult = (event) => {
            let finalTranscript = "";
            for (let i = event.resultIndex; i < event.results.length; ++i) {
                finalTranscript += event.results[i][0].transcript;
            }
            console.log("[SpeakingEngine] Speech captured:", finalTranscript);
            const outputArea = document.getElementById("transcribed-speech-output") || document.getElementById("speaking-transcript-input");
            if (outputArea && finalTranscript) {
                outputArea.value = finalTranscript;
            }
        };

        speakingRecognition.onerror = (event) => {
            console.error("[SpeakingEngine] STT Error:", event.error);
            isSpeakingRecording = false;
            updateMicUIState(false);
            if (typeof showToast === "function") {
                showToast(`Mic Notice (${event.error}): You can speak again or type German text manually.`);
            }
        };

        speakingRecognition.onend = () => {
            console.log("[SpeakingEngine] STT session ended.");
            isSpeakingRecording = false;
            updateMicUIState(false);
        };
    }
}

/**
 * Global Microphone Toggle Function attached to window.
 */
window.toggleSpeakingMic = function() {
    console.log("Mic clicked!");

    if ("speechSynthesis" in window) {
        window.speechSynthesis.cancel();
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        console.error("[SpeakingEngine] STT Unsupported when clicking mic.");
        if (typeof showToast === "function") {
            showToast("Speech Recognition unsupported in this browser. Please type text manually.");
        }
        return;
    }

    if (!speakingRecognition) initSpeechRecognition();

    if (isSpeakingRecording) {
        console.log("[SpeakingEngine] Stopping active recording...");
        try {
            speakingRecognition.stop();
        } catch (e) {
            console.error("[SpeakingEngine] Stop Error:", e);
        }
        isSpeakingRecording = false;
        updateMicUIState(false);
    } else {
        console.log("[SpeakingEngine] Starting new recording session...");
        try {
            speakingRecognition.start();
        } catch (e) {
            console.error("[SpeakingEngine] Start Error:", e);
            isSpeakingRecording = false;
            updateMicUIState(false);
        }
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
            btn.className = "w-16 h-16 rounded-full bg-rose-600 hover:bg-rose-500 text-white flex items-center justify-center shadow-lg shadow-rose-600/50 animate-pulse transition-all mx-auto";
            if (statusText) statusText.innerHTML = `<span class="text-rose-400 font-bold animate-pulse">Listening... Speak German now!</span>`;
        } else {
            btn.className = "w-16 h-16 rounded-full bg-violet-600 hover:bg-violet-500 text-white flex items-center justify-center shadow-lg shadow-violet-600/30 transition-all mx-auto";
            if (statusText) statusText.innerHTML = `<span class="text-slate-400">Click microphone to record your voice</span>`;
        }
    }
}

/**
 * Evaluates speech transcript against 4 criteria: Accuracy, Range, Relevance, Fluency
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

    // 1. Accuracy Score (Target Keywords match ratio)
    const keywords = prompt.target_keywords || [];
    let matchedKeywords = 0;
    keywords.forEach(kw => {
        if (transcript.includes(kw.toLowerCase())) matchedKeywords++;
    });
    const accuracyScore = keywords.length > 0 ? Math.min(100, Math.round((matchedKeywords / keywords.length) * 100)) : 75;

    // 2. Vocabulary Range Score (Unique words & length)
    const uniqueWords = new Set(words).size;
    const rangeScore = Math.min(100, Math.round((uniqueWords / Math.max(1, totalWords)) * 70 + Math.min(30, totalWords * 3)));

    // 3. Relevance Score (Suggested phrases match ratio)
    const phrases = prompt.suggested_phrases || [];
    let matchedPhrases = 0;
    phrases.forEach(ph => {
        const cleanPh = ph.replace(/\./g, "").toLowerCase();
        if (transcript.includes(cleanPh.substring(0, 8))) matchedPhrases++;
    });
    const relevanceScore = phrases.length > 0 ? Math.min(100, Math.round((matchedPhrases / phrases.length) * 100) + 40) : 80;

    // 4. Fluency Score (Word density & length consistency)
    const fluencyScore = Math.min(100, Math.round(Math.min(100, totalWords * 12) * 0.6 + (accuracyScore * 0.4)));

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

        reportBox.innerHTML = `
            <div class="p-6 rounded-2xl bg-slate-950 border border-slate-800 space-y-4 font-mono text-xs">
                <div class="flex items-center justify-between border-b border-slate-800 pb-3">
                    <span class="text-sm font-bold text-white font-sans">AI Speech Evaluation Report</span>
                    <span class="px-3 py-1 rounded-full border text-xs font-bold ${getBadgeClass(overallScore)}">
                        Overall: ${overallScore}% ${passed ? "PASS" : "RETRY"}
                    </span>
                </div>

                <div class="grid grid-cols-2 gap-3">
                    <div class="p-3 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
                        <div class="text-[11px] text-slate-400">Accuracy (Keywords)</div>
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
                    ${passed ? "🎉 Excellent German pronunciation and sentence structure!" : "💡 Keep practicing! Try using more suggested target German phrases."}
                </div>
            </div>
        `;

        if (passed && typeof addXP === "function") {
            addXP(100);
        }
    }
};
