import { create } from 'zustand';

const DRAFT_KEY = 'plotai_consultation_draft';
const DRAFT_EXPIRY_HOURS = 24;

const saveToLocalStorage = (state) => {
     try {
          const expiresAt = Date.now() + DRAFT_EXPIRY_HOURS * 60 * 60 * 1000;
          const draft = {
               state: {
                    questions: state.questions,
                    answers: state.answers,
                    currentQuestionIndex: state.currentQuestionIndex,
                    plotData: state.plotData,
               },
               expiresAt,
          };
          localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
     } catch (error) {
          console.error('Failed to save draft to localStorage:', error);
     }
};

const clearLocalStorage = () => {
     try {
          localStorage.removeItem(DRAFT_KEY);
     } catch (error) {
          console.error('Failed to clear draft from localStorage:', error);
     }
};

export const useConsultationStore = create((set, get) => ({
     // State
     isConsultationActive: false,
     questions: [],
     answers: {},
     currentQuestionIndex: 0,
     recommendation: null,
     plotData: null,

     // Actions
     startConsultation: (questions, plotData) => {
          set({
               isConsultationActive: true,
               questions,
               plotData,
               answers: {},
               currentQuestionIndex: 0,
               recommendation: null,
          });
     },

     restoreDraft: (providedDraft) => {
          try {
               const draft = providedDraft || JSON.parse(localStorage.getItem(DRAFT_KEY));
               if (!draft) return null;

               if (Date.now() > draft.expiresAt) {
                    if (!providedDraft) clearLocalStorage();
                    return null;
               }

               set({
                    isConsultationActive: true,
                    ...(draft.state || draft),
               });
               return draft.state || draft;
          } catch (error) {
               console.error('Failed to restore draft:', error);
               if (!providedDraft) clearLocalStorage();
               return null;
          }
     },

     answerQuestion: (questionId, value) => {
          set((state) => {
               const updatedAnswers = { ...state.answers, [questionId]: value };
               const newState = { answers: updatedAnswers };

               // Immediate save to localStorage
               saveToLocalStorage({ ...state, ...newState });

               return newState;
          });
     },

     nextQuestion: () => {
          set((state) => {
               const nextIndex = Math.min(state.currentQuestionIndex + 1, state.questions.length - 1);
               const newState = { currentQuestionIndex: nextIndex };
               saveToLocalStorage({ ...state, ...newState });
               return newState;
          });
     },

     previousQuestion: () => {
          set((state) => {
               const prevIndex = Math.max(state.currentQuestionIndex - 1, 0);
               const newState = { currentQuestionIndex: prevIndex };
               saveToLocalStorage({ ...state, ...newState });
               return newState;
          });
     },

     submitAnswers: async (submitFn) => {
          const { answers, plotData } = get();
          try {
               const result = await submitFn({ answers, plotData });
               set({ recommendation: result });
               clearLocalStorage();
               return result;
          } catch (error) {
               console.error('Failed to submit answers:', error);
               throw error;
          }
     },

     setConsultationActive: (active) => set({ isConsultationActive: active }),

     resetConsultation: () => {
          set({
               isConsultationActive: false,
               questions: [],
               answers: {},
               currentQuestionIndex: 0,
               recommendation: null,
               plotData: null,
          });
          clearLocalStorage();
     },
}));
