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

/**
 * Anti-Repetition Auto-Log API Communication Functions
 */
async function logCompletedTopic(category, topicSummary) {
    if (!topicSummary) return;
    try {
        console.log(`[AntiRepetition] Auto-logging topic (${category}):`, topicSummary);
        const res = await fetch('/api/topics', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: "default_user",
                category: category || "German Learning",
                topic_summary: topicSummary
            })
        });
        if (res.ok) {
            console.log("[AntiRepetition] Successfully logged topic:", topicSummary);
            await refreshLoggedTopicsUI();
        }
    } catch (e) {
        console.error("[AntiRepetition] Failed to log topic:", e);
    }
}

async function refreshLoggedTopicsUI() {
    try {
        const res = await fetch('/api/topics/default_user');
        if (!res.ok) return;
        const data = await res.json();
        const topics = data.completed_topics || [];

        // 1. Update counter text
        const badgeEl = document.getElementById('topic-count-badge');
        if (badgeEl) {
            badgeEl.innerText = `${topics.length} Topics Logged`;
        }

        // 2. Update empty text field container to display a comma-separated list of retrieved completed_topics
        const listEl = document.getElementById('topics-badge-list');
        const fullListEl = document.getElementById('full-topics-list');

        if (listEl) {
            if (topics.length === 0) {
                listEl.innerHTML = `<span class="text-xs text-slate-500 italic">No topics logged yet. Generate exercises to populate anti-repetition rules.</span>`;
            } else {
                listEl.innerHTML = `
                    <div class="flex flex-wrap gap-2 mb-2 w-full">
                        ${topics.map(t => `
                            <span class="px-3 py-1 rounded-lg bg-indigo-950/60 border border-indigo-500/30 text-indigo-300 text-xs font-mono flex items-center space-x-1">
                                <i data-lucide="shield" class="w-3 h-3 text-indigo-400"></i>
                                <span>${t}</span>
                            </span>
                        `).join('')}
                    </div>
                    <div class="w-full p-2.5 rounded-xl bg-slate-900 border border-slate-800 text-xs font-mono text-indigo-300">
                        <span class="text-slate-400 font-bold uppercase tracking-wider text-[10px]">Logged Topics:</span> ${topics.join(', ')}
                    </div>
                `;
            }
        }

        if (fullListEl) {
            if (topics.length === 0) {
                fullListEl.innerHTML = `<div class="text-xs text-slate-500 italic">No topics logged yet.</div>`;
            } else {
                fullListEl.innerHTML = topics.map((t, i) => `
                    <div class="p-3 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-between text-xs font-mono">
                        <span class="text-white">#${i+1} ${t}</span>
                        <span class="text-emerald-400">Excluded</span>
                    </div>
                `).join('');
            }
        }

        if (window.lucide) {
            window.lucide.createIcons();
        }
    } catch (e) {
        console.error("[AntiRepetition] Error refreshing logged topics UI:", e);
    }
}

// Expose globally
window.logCompletedTopic = logCompletedTopic;
window.refreshLoggedTopicsUI = refreshLoggedTopicsUI;

