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

const LOCAL_STORAGE_TOPICS_KEY = "deutschmind_completed_topics";

/**
 * Helper function to retrieve completed topic summaries from localStorage.
 */
function getLoggedTopicsArray() {
    try {
        const raw = localStorage.getItem(LOCAL_STORAGE_TOPICS_KEY);
        if (!raw) return [];
        const items = JSON.parse(raw);
        if (!Array.isArray(items)) return [];
        return items.map(item => typeof item === 'string' ? item : item.topic_summary).filter(Boolean);
    } catch (e) {
        return [];
    }
}

/**
 * Constructs AI anti-repetition directive from localStorage.
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
 * Anti-Repetition Auto-Log Functions with Serverless localStorage Fallback
 */
async function logCompletedTopic(category, topicSummary) {
    if (!topicSummary) return;

    // 1. Read existing topics array from localStorage
    let localTopics = [];
    try {
        const stored = localStorage.getItem(LOCAL_STORAGE_TOPICS_KEY);
        localTopics = stored ? JSON.parse(stored) : [];
        if (!Array.isArray(localTopics)) localTopics = [];
    } catch (e) {
        localTopics = [];
    }

    // 2. Append new topic object with category, topic_summary, timestamp
    const summaryStr = typeof topicSummary === 'string' ? topicSummary : (topicSummary.topic_summary || String(topicSummary));
    const alreadyExists = localTopics.some(t => 
        (typeof t === 'string' ? t : t.topic_summary) === summaryStr
    );

    if (!alreadyExists) {
        localTopics.push({
            category: category || "German Learning",
            topic_summary: summaryStr,
            timestamp: new Date().toISOString()
        });
        // Save back to localStorage
        try {
            localStorage.setItem(LOCAL_STORAGE_TOPICS_KEY, JSON.stringify(localTopics));
        } catch (e) {
            console.error("[AntiRepetition] Failed to save to localStorage:", e);
        }
    }

    // 3. Background POST to /api/topics (try/catch so it doesn't crash if backend is offline)
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

    // 4. Immediately call refreshLoggedTopicsUI()
    await refreshLoggedTopicsUI();
}

async function refreshLoggedTopicsUI() {
    let topicsList = [];

    // 1. Retrieve topics from localStorage
    try {
        const stored = localStorage.getItem(LOCAL_STORAGE_TOPICS_KEY);
        if (stored) {
            const parsed = JSON.parse(stored);
            if (Array.isArray(parsed)) {
                topicsList = parsed.map(item => typeof item === 'string' ? item : item.topic_summary).filter(Boolean);
            }
        }
    } catch (e) {
        console.error("[AntiRepetition] Error reading topics from localStorage:", e);
    }

    // 2. Attempt background sync with backend if live server is available
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 1200);
        const res = await fetch('/api/topics/default_user', { signal: controller.signal });
        clearTimeout(timeoutId);

        if (res.ok) {
            const data = await res.json();
            const serverTopics = data.completed_topics || [];
            if (Array.isArray(serverTopics) && serverTopics.length > 0) {
                // Merge server topics into localStorage state
                const mergedMap = new Map();
                topicsList.forEach(t => mergedMap.set(t, { category: "German Learning", topic_summary: t, timestamp: new Date().toISOString() }));
                serverTopics.forEach(t => mergedMap.set(t, { category: "German Learning", topic_summary: t, timestamp: new Date().toISOString() }));
                
                const mergedArray = Array.from(mergedMap.values());
                localStorage.setItem(LOCAL_STORAGE_TOPICS_KEY, JSON.stringify(mergedArray));
                topicsList = Array.from(mergedMap.keys());
            }
        }
    } catch (e) {
        // Backend unavailable (GitHub Pages) - fallback 100% to localStorage state
    }

    // 3. Update DOM elements (#topic-count-badge and container list)
    const badgeEl = document.getElementById('topic-count-badge');
    if (badgeEl) {
        badgeEl.innerText = `${topicsList.length} Topics Logged`;
    }

    const listEl = document.getElementById('topics-badge-list');
    const fullListEl = document.getElementById('full-topics-list');

    if (listEl) {
        if (topicsList.length === 0) {
            listEl.innerHTML = `<span class="text-xs text-slate-500 italic">No topics logged yet. Generate exercises to populate anti-repetition rules.</span>`;
        } else {
            listEl.innerHTML = `
                <div class="flex flex-wrap gap-2 mb-2 w-full">
                    ${topicsList.map(t => `
                        <span class="px-3 py-1 rounded-lg bg-indigo-950/60 border border-indigo-500/30 text-indigo-300 text-xs font-mono flex items-center space-x-1">
                            <i data-lucide="shield" class="w-3 h-3 text-indigo-400"></i>
                            <span>${t}</span>
                        </span>
                    `).join('')}
                </div>
                <div class="w-full p-2.5 rounded-xl bg-slate-900 border border-slate-800 text-xs font-mono text-indigo-300">
                    <span class="text-slate-400 font-bold uppercase tracking-wider text-[10px]">Logged Topics:</span> ${topicsList.join(', ')}
                </div>
            `;
        }
    }

    if (fullListEl) {
        if (topicsList.length === 0) {
            fullListEl.innerHTML = `<div class="text-xs text-slate-500 italic">No topics logged yet.</div>`;
        } else {
            fullListEl.innerHTML = topicsList.map((t, i) => `
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
}

// Expose functions globally
window.getLoggedTopicsArray = getLoggedTopicsArray;
window.getAntiRepetitionPromptDirective = getAntiRepetitionPromptDirective;
window.logCompletedTopic = logCompletedTopic;
window.refreshLoggedTopicsUI = refreshLoggedTopicsUI;


