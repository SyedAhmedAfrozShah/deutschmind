/**
 * DeutschMind - Isolated Listening Comprehension Engine (js/listeningEngine.js)
 * STRICT SCOPE: Text-to-Speech (TTS) playback and MCQ Rendering ONLY.
 * Uses Event Delegation with .dynamic-tts-btn and data-text attributes.
 */

let listeningScenariosList = [];
let currentListeningScenarioObj = null;
let currentListeningAnswers = {};

/**
 * Global TTS Audio Playback Function attached to window.
 */
window.playGermanTTS = function(textToSpeak) {
    if (!textToSpeak) return;

    if ("speechSynthesis" in window) {
        window.speechSynthesis.cancel();
    }

    const rate = typeof currentListeningSpeed !== "undefined" ? currentListeningSpeed : 0.85;

    const speakNow = () => {
        const uttr = new SpeechSynthesisUtterance(textToSpeak);
        uttr.lang = "de-DE";
        uttr.rate = rate;

        const voices = window.speechSynthesis.getVoices();
        const deVoice = voices.find(v => v.lang.includes("de") || v.lang.includes("DE"));
        if (deVoice) uttr.voice = deVoice;

        window.speechSynthesis.speak(uttr);
        if (typeof showToast === "function") {
            showToast(`🔊 Playing German audio (${rate}x speed)...`);
        }
    };

    if ("speechSynthesis" in window) {
        if (window.speechSynthesis.getVoices().length === 0) {
            window.speechSynthesis.onvoiceschanged = () => {
                speakNow();
                window.speechSynthesis.onvoiceschanged = null;
            };
        } else {
            speakNow();
        }
    } else {
        alert("Speech synthesis is not supported in this browser.");
    }
};

// Global Alias for speakGerman
window.speakGerman = window.playGermanTTS;

/**
 * Loads listening scenarios from static data/listening.json or fallback dataset.
 */
window.loadListeningScenarios = async function() {
    try {
        const res = await fetch("data/listening.json");
        if (res.ok) {
            listeningScenariosList = await res.json();
        }
    } catch (e) {
        console.warn("[ListeningEngine] Failed to load data/listening.json, using memory fallback.", e);
    }

    window.renderListeningScenario();
};

/**
 * Renders a random scenario matching the current global CEFR level.
 */
window.renderListeningScenario = function() {
    const level = (typeof currentLevel !== "undefined" ? currentLevel : "ZERO").toUpperCase();
    
    // Filter scenarios by CEFR level
    const filtered = listeningScenariosList.filter(s => (s.level || "ZERO").toUpperCase() === level);
    
    if (filtered.length === 0) {
        console.warn(`[ListeningEngine] No scenario found for level ${level}`);
        return;
    }

    // Pick random scenario
    const scenario = filtered[Math.floor(Math.random() * filtered.length)];
    currentListeningScenarioObj = scenario;
    currentListeningAnswers = {};

    // 1. DOM Updates for Title & Topic
    const titleEl = document.getElementById("listening-title");
    if (titleEl) titleEl.innerText = scenario.title;

    const topicEl = document.getElementById("listening-topic");
    if (topicEl) topicEl.innerText = `${scenario.topic} (${scenario.level})`;

    // Reset transcripts display
    const transContainer = document.getElementById("listening-transcript-container");
    if (transContainer) {
        transContainer.classList.add("hidden");
        const deEl = document.getElementById("listening-transcript-de");
        const enEl = document.getElementById("listening-transcript-en");
        const urEl = document.getElementById("listening-transcript-ur");
        if (deEl) deEl.innerText = scenario.transcript_de;
        if (enEl) enEl.innerText = scenario.transcript_en;
        if (urEl) urEl.innerText = scenario.transcript_ur;
    }

    // 2. MCQ Generation (Uses class dynamic-tts-btn and data-text for Event Delegation)
    const questionsContainer = document.getElementById("listening-questions-container");
    if (questionsContainer) {
        questionsContainer.innerHTML = ""; // Enforce DOM clear

        scenario.questions.forEach((qObj, qIdx) => {
            const qBox = document.createElement("div");
            qBox.className = "p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3";
            
            qBox.innerHTML = `
                <div class="flex items-center justify-between">
                    <span class="text-xs font-mono text-emerald-400 font-bold">Question ${qIdx + 1}: ${qObj.q}</span>
                    <button type="button" class="dynamic-tts-btn p-1.5 rounded bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30 cursor-pointer" data-text="${qObj.q.replace(/"/g, '&quot;')}" title="Listen Question">
                        <i data-lucide="volume-2" class="w-3.5 h-3.5 pointer-events-none"></i>
                    </button>
                </div>
                <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
                    ${qObj.options.map((opt, oIdx) => `
                        <label id="opt_label_${qIdx}_${oIdx}" class="p-2.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between cursor-pointer hover:border-emerald-500/40 text-xs text-slate-200 transition-all">
                            <div class="flex items-center space-x-2">
                                <input type="radio" name="listening_q_${qIdx}" value="${opt.replace(/"/g, '&quot;')}" onchange="window.selectListeningAnswer(${qIdx}, '${opt.replace(/'/g, "\\'")}')" class="text-emerald-500 bg-slate-950 border-slate-700">
                                <span>${opt}</span>
                            </div>
                            <button type="button" class="dynamic-tts-btn p-1 text-slate-400 hover:text-emerald-300 cursor-pointer" data-text="${opt.replace(/"/g, '&quot;')}" title="Listen Option">
                                <i data-lucide="volume-2" class="w-3 h-3 pointer-events-none"></i>
                            </button>
                        </label>
                    `).join("")}
                </div>
            `;
            questionsContainer.appendChild(qBox);
        });

        // Add Submit Button
        const submitBtnBox = document.createElement("div");
        submitBtnBox.className = "pt-2";
        submitBtnBox.innerHTML = `
            <button onclick="window.submitListeningAnswers()" class="w-full py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs shadow-lg shadow-emerald-600/30 flex items-center justify-center space-x-2">
                <i data-lucide="check-circle" class="w-4 h-4"></i>
                <span>Submit Listening Test Answers</span>
            </button>
            <div id="listening-feedback-result" class="hidden mt-3 p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-center"></div>
        `;
        questionsContainer.appendChild(submitBtnBox);

        if (typeof lucide !== "undefined") lucide.createIcons();
    }
};

/**
 * Stores user choice for a listening question.
 */
window.selectListeningAnswer = function(qIdx, optionText) {
    currentListeningAnswers[qIdx] = optionText;
};

/**
 * Toggles visibility of DE, EN, UR transcript box.
 */
window.toggleListeningTranscript = function() {
    const transContainer = document.getElementById("listening-transcript-container");
    if (transContainer) {
        transContainer.classList.toggle("hidden");
    }
};

/**
 * Validates listening test answers and highlights choices.
 */
window.submitListeningAnswers = function() {
    const scenario = currentListeningScenarioObj;
    if (!scenario || !scenario.questions) return;

    let correctCount = 0;
    const total = scenario.questions.length;

    scenario.questions.forEach((qObj, qIdx) => {
        const userChoice = currentListeningAnswers[qIdx];
        const isCorrect = userChoice === qObj.answer;

        if (isCorrect) correctCount++;

        const radios = document.getElementsByName(`listening_q_${qIdx}`);
        radios.forEach(radio => {
            radio.disabled = true;
            const parentLabel = radio.closest("label");
            if (parentLabel) {
                if (radio.value === qObj.answer) {
                    parentLabel.className = "p-2.5 rounded-lg bg-emerald-950/60 border border-emerald-500 text-xs text-emerald-300 font-bold flex items-center justify-between";
                } else if (radio.checked && !isCorrect) {
                    parentLabel.className = "p-2.5 rounded-lg bg-rose-950/60 border border-rose-500 text-xs text-rose-300 font-bold flex items-center justify-between";
                } else {
                    parentLabel.className = "p-2.5 rounded-lg bg-slate-950 border border-slate-900 opacity-50 text-xs text-slate-500 flex items-center justify-between";
                }
            }
        });
    });

    const scorePercent = Math.round((correctCount / total) * 100);
    const feedbackBox = document.getElementById("listening-feedback-result");
    if (feedbackBox) {
        feedbackBox.classList.remove("hidden");
        const passed = scorePercent >= 66;
        feedbackBox.innerHTML = `
            <div class="${passed ? 'text-emerald-400' : 'text-rose-400'} font-bold text-sm">
                ${passed ? '🎉 Listening Exercise Passed!' : '⚠ Listening Exercise Attempt Complete'}
            </div>
            <div class="text-slate-300 text-xs mt-1">
                Score: <strong class="text-amber-400">${scorePercent}%</strong> (${correctCount} of ${total} correct)
            </div>
        `;

        if (passed && typeof addXP === "function") {
            addXP(100);
        }
    }
};
