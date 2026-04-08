/**
 * Mocking the store logic for testing persistence without a browser environment.
 */
const { execSync } = require('child_process');

class MockLocalStorage {
     constructor() {
          this.store = {};
     }
     getItem(key) { return this.store[key] || null; }
     setItem(key, value) { this.store[key] = value.toString(); }
     removeItem(key) { delete this.store[key]; }
     clear() { this.store = {}; }
}

const localStorage = new MockLocalStorage();
const DRAFT_KEY = 'plotai_consultation_draft';
const DRAFT_EXPIRY_HOURS = 24;

const saveDraft = (state) => {
     const draft = {
          timestamp: Date.now(),
          plotData: state.plotData,
          questions: state.questions,
          answers: state.answers,
          currentQuestionIndex: state.currentQuestionIndex,
          expiresAt: Date.now() + DRAFT_EXPIRY_HOURS * 60 * 60 * 1000,
     };
     localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
};

const restoreDraft = () => {
     const draftString = localStorage.getItem(DRAFT_KEY);
     if (!draftString) return null;
     const draft = JSON.parse(draftString);
     if (Date.now() > draft.expiresAt) {
          localStorage.removeItem(DRAFT_KEY);
          return null;
     }
     return draft;
};

// Start Test
console.log("--- Starting Consultation Store Persistence Test ---");

// 1. Initial State
let state = {
     isConsultationActive: true,
     questions: [{ id: 'q1', text: 'Q1' }, { id: 'q2', text: 'Q2' }],
     answers: {},
     currentQuestionIndex: 0,
     plotData: { plot_size_sqft: 1500, orientation: 'north' }
};

// 2. Answer Q1
state.answers['q1'] = ['home'];
saveDraft(state);
console.log("Answered Q1. localStorage:", localStorage.getItem(DRAFT_KEY));

// 3. Answer Q2
state.answers['q2'] = ['3-4'];
state.currentQuestionIndex = 1;
saveDraft(state);
console.log("\nAnswered Q2. localStorage (updated):", localStorage.getItem(DRAFT_KEY));

// 4. Test Restore
const restored = restoreDraft();
if (restored && restored.answers['q1'][0] === 'home' && restored.answers['q2'][0] === '3-4') {
     console.log("\n✅ Draft restored successfully!");
} else {
     console.log("\n❌ Draft restoration failed!");
}

// 5. Test Expiry (Mocking time)
console.log("\nTesting Expiry (Mocking future time)...");
const expiredDraft = JSON.parse(localStorage.getItem(DRAFT_KEY));
expiredDraft.expiresAt = Date.now() - 1000; // Set to 1 second ago
localStorage.setItem(DRAFT_KEY, JSON.stringify(expiredDraft));

const restoredExpired = restoreDraft();
if (restoredExpired === null) {
     console.log("✅ Expired draft cleared correctly!");
} else {
     console.log("❌ Expired draft was not cleared!");
}

console.log("\n--- Test Complete ---");
