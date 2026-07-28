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

// Auto-initialize header UI on window load
document.addEventListener("DOMContentLoaded", () => {
    const state = getUserState();
    updateHeaderUI(state);
});
