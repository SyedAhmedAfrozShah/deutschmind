/**
 * DeutschMind - Persistent State Manager (progress.js)
 * Manages client-side storage for CEFR level progression, XP points, streaks, and unlocked modules.
 */

const STORAGE_KEY = "deutschmind_user_progress";

const DEFAULT_STATE = {
    currentLevel: "A1",
    xp: 0,
    streak: 1,
    lastLogin: new Date().toISOString().split("T")[0],
    unlockedLevels: ["ZERO", "A1"],
    masteredVocabCount: 0
};

/**
 * Safely fetches user state from localStorage or initializes default state.
 */
function getUserState() {
    try {
        const data = localStorage.getItem(STORAGE_KEY);
        if (!data) {
            saveUserState(DEFAULT_STATE);
            return { ...DEFAULT_STATE };
        }
        const state = JSON.parse(data);
        
        // Auto-check streak on login
        checkStreak(state);
        return state;
    } catch (e) {
        console.warn("[StateManager] localStorage unavailable or corrupted. Using fallback in-memory state:", e);
        return { ...DEFAULT_STATE };
    }
}

/**
 * Saves user state object back to localStorage.
 */
function saveUserState(state) {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
        updateHeaderUI(state);
    } catch (e) {
        console.error("[StateManager] Failed to save state to localStorage:", e);
    }
}

/**
 * Adds XP points to the user's total and saves state.
 */
function addXP(amount) {
    const state = getUserState();
    state.xp = (state.xp || 0) + amount;
    saveUserState(state);
    showToast(`+${amount} XP Earned! Total: ${state.xp} XP`);
    return state.xp;
}

/**
 * Unlocks a new CEFR level (e.g. 'A2', 'B1') and promotes current level.
 */
function unlockLevel(level) {
    const state = getUserState();
    if (!state.unlockedLevels.includes(level)) {
        state.unlockedLevels.push(level);
    }
    state.currentLevel = level;
    saveUserState(state);
    return state;
}

/**
 * Updates streak based on daily logins.
 */
function checkStreak(state) {
    const today = new Date().toISOString().split("T")[0];
    if (state.lastLogin === today) return;

    const last = new Date(state.lastLogin);
    const now = new Date(today);
    const diffDays = Math.round((now - last) / (1000 * 60 * 60 * 24));

    if (diffDays === 1) {
        state.streak = (state.streak || 1) + 1;
    } else if (diffDays > 1) {
        state.streak = 1;
    }
    state.lastLogin = today;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

/**
 * Updates header badges (XP, Streak, Level, Unlocked icons).
 */
function updateHeaderUI(state) {
    const xpEl = document.getElementById("header-xp-val");
    if (xpEl) xpEl.innerText = `${state.xp || 0} XP`;

    const streakEl = document.getElementById("header-streak-val");
    if (streakEl) streakEl.innerText = `${state.streak || 1} Days`;

    const levelEl = document.getElementById("header-level-badge");
    if (levelEl) levelEl.innerText = state.currentLevel || "A1";

    if (typeof updateLevelSelectorLocks === "function") {
        updateLevelSelectorLocks(state);
    }
}

// Auto-initialize header UI & refresh Anti-Repetition topics on window load
document.addEventListener("DOMContentLoaded", () => {
    const state = getUserState();
    updateHeaderUI(state);
    refreshLoggedTopicsUI();
});

const STAGED_TOPICS_KEY = "deutschmind_staged_topics";
const VERIFIED_TOPICS_KEY = "deutschmind_verified_topics";

/**
 * Retrieves staged (short-term) topics from localStorage.
 */
function getStagedTopics() {
    try {
        const raw = localStorage.getItem(STAGED_TOPICS_KEY);
        if (!raw) return [];
        const items = JSON.parse(raw);
        return Array.isArray(items) ? items : [];
    } catch (e) {
        return [];
    }
}

/**
 * Retrieves verified (long-term certified) topics from localStorage.
 */
function getVerifiedTopics() {
    try {
        const raw = localStorage.getItem(VERIFIED_TOPICS_KEY);
        if (!raw) return [];
        const items = JSON.parse(raw);
        return Array.isArray(items) ? items : [];
    } catch (e) {
        return [];
    }
}

/**
 * Helper function to retrieve concatenated staged + verified topic summaries for AI blacklist.
 */
function getLoggedTopicsArray() {
    const staged = getStagedTopics();
    const verified = getVerifiedTopics();
    const all = [...staged, ...verified];
    return all.map(item => typeof item === 'string' ? item : item.topic_summary).filter(Boolean);
}

/**
 * Constructs AI anti-repetition directive concatenating BOTH staged and verified topics.
 */
function getAntiRepetitionPromptDirective() {
    const topics = getLoggedTopicsArray();
    if (topics.length === 0) {
        return "System Directive: Ensure 100% novel, engaging German scenarios suitable for the student.";
    }
    const topicsStr = topics.map(t => `"${t}"`).join(', ');
    return `System Directive: Do not generate scenarios involving the following topics as the user has already completed them: [${topicsStr}]. Ensure 100% novel scenarios.`;
}

/**
 * Anti-Repetition Auto-Log Functions — Appends EXCLUSIVELY to Staged Memory Queue
 */
async function logCompletedTopic(category, topicSummary) {
    if (!topicSummary) return;

    let staged = getStagedTopics();
    const verified = getVerifiedTopics();
    const summaryStr = typeof topicSummary === 'string' ? topicSummary : (topicSummary.topic_summary || String(topicSummary));

    const alreadyStaged = staged.some(t => (typeof t === 'string' ? t : t.topic_summary) === summaryStr);
    const alreadyVerified = verified.some(t => (typeof t === 'string' ? t : t.topic_summary) === summaryStr);

    if (!alreadyStaged && !alreadyVerified) {
        staged.push({
            category: category || "German Learning",
            topic_summary: summaryStr,
            timestamp: new Date().toISOString()
        });
        try {
            localStorage.setItem(STAGED_TOPICS_KEY, JSON.stringify(staged));
        } catch (e) {
            console.error("[AntiRepetition] Failed to save staged topic to localStorage:", e);
        }
    }

    // Silent background POST attempt to /api/topics for backend sync
    try {
        fetch('/api/topics', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: "default_user",
                category: category || "German Learning",
                topic_summary: summaryStr
            })
        }).catch(() => {});
    } catch (e) {}

    await refreshLoggedTopicsUI();
}

async function refreshLoggedTopicsUI() {
    const staged = getStagedTopics();
    const verified = getVerifiedTopics();
    const totalCount = staged.length + verified.length;

    // 1. Update counter elements
    const countEl = document.getElementById("anti-repetition-count") || document.getElementById("topic-count-badge");
    if (countEl) {
        countEl.innerText = `${totalCount} Topics (${staged.length} Staged / ${verified.length} Verified)`;
    }
    const topicCountBadge = document.getElementById("topic-count-badge");
    if (topicCountBadge && topicCountBadge !== countEl) {
        topicCountBadge.innerText = `${totalCount} Topics (${staged.length} Staged / ${verified.length} Verified)`;
    }

    // 2. Update list container elements
    const listEl = document.getElementById("anti-repetition-list") || document.getElementById("topics-badge-list");
    const topicsBadgeList = document.getElementById("topics-badge-list");
    const fullListEl = document.getElementById("full-topics-list");

    const renderListHTML = () => {
        if (totalCount === 0) {
            return '<p class="text-slate-500 text-xs italic">No topics in queue. Complete daily lessons to stage memory topics for certification.</p>';
        }

        let html = '';
        if (staged.length > 0) {
            html += `<div class="w-full text-[10px] font-mono text-indigo-400 font-bold uppercase tracking-wider mb-1">⏳ Short-Term Staged Memory (${staged.length}):</div>`;
            html += staged.map(t => {
                const label = typeof t === 'string' ? t : (`${t.category || 'General'}: ${t.topic_summary}`);
                return `<span class="inline-block bg-indigo-950/80 text-indigo-300 border border-indigo-500/40 text-xs px-2.5 py-1 rounded-md mr-2 mb-2 font-mono">⏳ ${label}</span>`;
            }).join('');
        }

        if (verified.length > 0) {
            html += `<div class="w-full text-[10px] font-mono text-emerald-400 font-bold uppercase tracking-wider mt-2 mb-1">🛡️ Verified Long-Term Mastery (${verified.length}):</div>`;
            html += verified.map(t => {
                const label = typeof t === 'string' ? t : (`${t.category || 'General'}: ${t.topic_summary}`);
                return `<span class="inline-block bg-emerald-950/80 text-emerald-300 border border-emerald-500/40 text-xs px-2.5 py-1 rounded-md mr-2 mb-2 font-mono">🛡️ ${label} ✓</span>`;
            }).join('');
        }

        return html;
    };

    const listHTML = renderListHTML();
    if (listEl) listEl.innerHTML = listHTML;
    if (topicsBadgeList && topicsBadgeList !== listEl) topicsBadgeList.innerHTML = listHTML;

    if (fullListEl) {
        if (totalCount === 0) {
            fullListEl.innerHTML = `<div class="text-xs text-slate-500 italic">No topics logged yet.</div>`;
        } else {
            let fullHTML = '';
            staged.forEach((t, i) => {
                const label = typeof t === 'string' ? t : (`${t.category || 'General'}: ${t.topic_summary}`);
                fullHTML += `
                    <div class="p-3 rounded-lg bg-indigo-950/30 border border-indigo-500/30 flex items-center justify-between text-xs font-mono">
                        <span class="text-indigo-200">#${i+1} ${label}</span>
                        <span class="text-indigo-400">⏳ Staged</span>
                    </div>
                `;
            });
            verified.forEach((t, i) => {
                const label = typeof t === 'string' ? t : (`${t.category || 'General'}: ${t.topic_summary}`);
                fullHTML += `
                    <div class="p-3 rounded-lg bg-emerald-950/30 border border-emerald-500/30 flex items-center justify-between text-xs font-mono">
                        <span class="text-emerald-200">#${staged.length + i + 1} ${label}</span>
                        <span class="text-emerald-400">🛡️ Verified</span>
                    </div>
                `;
            });
            fullListEl.innerHTML = fullHTML;
        }
    }

    if (window.lucide) {
        window.lucide.createIcons();
    }
}

/**
 * Manually resets staged short-term memory and returns topics to daily learning pool.
 */
window.clearStagedTopics = function() {
    if (confirm("Are you sure you want to restore all staged topics? This will return them to your daily learning pool. (Verified topics will not be affected).")) {
        localStorage.setItem("deutschmind_staged_topics", JSON.stringify([]));
        if (typeof refreshLoggedTopicsUI === "function") {
            refreshLoggedTopicsUI();
        }
        if (typeof showToast === "function") {
            showToast("Staged memory restored to the active pool!");
        }
    }
};

// Expose functions globally
window.getStagedTopics = getStagedTopics;
window.getVerifiedTopics = getVerifiedTopics;
window.getLoggedTopicsArray = getLoggedTopicsArray;
window.getAntiRepetitionPromptDirective = getAntiRepetitionPromptDirective;
window.logCompletedTopic = logCompletedTopic;
window.refreshLoggedTopicsUI = refreshLoggedTopicsUI;




