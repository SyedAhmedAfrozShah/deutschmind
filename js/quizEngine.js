/**
 * DeutschMind - Dynamic Assessment & Promotion Engine (quizEngine.js)
 * Generates 10-question dynamic MCQs from grammar.json and vocab.json with distractor options.
 */

let activeQuizSession = {
    cefrLevel: "A1",
    questions: [],
    currentIndex: 0,
    userAnswers: [],
    scorePercent: 0
};

/**
 * Utility to shuffle an array in-place.
 */
function shuffleArray(array) {
    const arr = [...array];
    for (let i = arr.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
}

/**
 * Generates a 10-question dynamic MCQ quiz for a given CEFR level.
 */
async function generateQuiz(cefrLevel) {
    const level = (cefrLevel || "A1").toUpperCase();
    
    // Fetch dataset items
    let grammarData = [];
    let vocabData = [];

    try {
        const gRes = await fetch("data/grammar.json");
        if (gRes.ok) grammarData = await gRes.json();
    } catch(e) {}

    try {
        const vRes = await fetch("data/vocab.json");
        if (vRes.ok) vocabData = await vRes.json();
    } catch(e) {}

    // Fallback pools if JSON fetch unavailable
    if (grammarData.length === 0 && typeof GOETHE_GRAMMAR_BANK !== "undefined") {
        grammarData = GOETHE_GRAMMAR_BANK[level] || [];
    }
    if (vocabData.length === 0 && typeof GOETHE_VOCAB_BANK !== "undefined") {
        vocabData = GOETHE_VOCAB_BANK[level] || [];
    }

    // Filter items matching CEFR level
    const levelGrammar = grammarData.filter(i => (i.cefr || i.cefr_level || level).toUpperCase() === level);
    const levelVocab = vocabData.filter(i => (i.cefr || i.cefr_level || level).toUpperCase() === level);

    const combinedPool = [...levelGrammar, ...levelVocab];
    if (combinedPool.length === 0) {
        console.warn(`[QuizEngine] No items found for level ${level}. Using default fallback pool.`);
    }

    // Select 10 random items from combined pool
    const shuffledPool = shuffleArray(combinedPool);
    const selectedItems = shuffledPool.slice(0, Math.min(10, shuffledPool.length));

    // Distractor pool source
    const distractorPool = combinedPool.length >= 4 ? combinedPool : (grammarData.length > 0 ? grammarData : vocabData);

    // Build 10 MCQ Questions
    const questions = selectedItems.map((item, idx) => {
        const germanText = item.german || item.german_word || item.word || item.incorrect_sentence;
        const correctAnswer = item.english || item.english_translation || item.definition_en || item.instructions_en || "Correct German expression";
        const urduTranslation = item.urdu || item.urdu_translation || item.definition_ur || "";

        // Extract 3 distractors from distinct pool items
        const otherItems = distractorPool.filter(other => {
            const otherAns = other.english || other.english_translation || other.definition_en;
            return otherAns && otherAns !== correctAnswer;
        });

        const shuffledOthers = shuffleArray(otherItems);
        const distractors = shuffledOthers.slice(0, 3).map(o => o.english || o.english_translation || o.definition_en);

        // Fill remaining distractors if pool small
        while (distractors.length < 3) {
            distractors.push(`Alternative German phrase ${distractors.length + 1}`);
        }

        // Combine correct answer + 3 distractors & shuffle options
        const allOptions = shuffleArray([correctAnswer, ...distractors]);

        return {
            id: item.id || `q_${idx + 1}`,
            questionNumber: idx + 1,
            germanPrompt: germanText,
            urduSubtext: urduTranslation,
            correctAnswer: correctAnswer,
            options: allOptions,
            topic: item.topic || item.target_concept || "German Grammar & Vocabulary",
            ruleHint: item.rule_hint || item.hint_en || ""
        };
    });

    activeQuizSession = {
        cefrLevel: level,
        questions: questions,
        currentIndex: 0,
        userAnswers: [],
        scorePercent: 0
    };

    return activeQuizSession;
}

/**
 * Grades user answers and calculates percentage score.
 * Promotes user level if score >= 80%.
 */
function gradeQuiz(userAnswers) {
    const session = activeQuizSession;
    let correctCount = 0;

    session.questions.forEach((q, idx) => {
        const userChoice = userAnswers[idx];
        if (userChoice === q.correctAnswer) {
            correctCount++;
        }
    });

    const total = session.questions.length || 1;
    const scorePercent = Math.round((correctCount / total) * 100);
    const passed = scorePercent >= 80;

    session.scorePercent = scorePercent;

    let nextLevel = session.cefrLevel;
    if (passed) {
        if (session.cefrLevel === "ZERO") nextLevel = "A1";
        else if (session.cefrLevel === "A1") nextLevel = "A2";
        else if (session.cefrLevel === "A2") nextLevel = "B1";
        else if (session.cefrLevel === "B1") nextLevel = "B2";

        // Unlock next tier & award 500 XP
        unlockLevel(nextLevel);
        addXP(500);
    }

    return {
        scorePercent: scorePercent,
        correctCount: correctCount,
        totalQuestions: total,
        passed: passed,
        currentLevel: session.cefrLevel,
        nextLevel: nextLevel,
        earnedXP: passed ? 500 : 50
    };
}
