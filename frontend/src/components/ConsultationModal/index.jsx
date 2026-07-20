import { useConsultationStore } from '@/store/consultationStore';
import QuestionCard from './QuestionCard';
import RecommendationCard from './RecommendationCard';
import { SlidersHorizontal } from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';

export default function ConsultationModal({ onGenerate }) {
     const {
          isConsultationActive,
          questions,
          currentQuestionIndex,
          recommendation,
     } = useConsultationStore();

     if (!isConsultationActive) return null;

     const currentQuestion = questions ? questions[currentQuestionIndex] : null;

     return (
          <div className="flex flex-col items-start gap-2 w-full mt-4">
               <div className="flex items-center gap-2">
                    <SlidersHorizontal size={14} className="text-primary" />
                    <span className="text-[10px] text-primary font-label-caps uppercase">Consultation Mode</span>
               </div>
               <div className="border border-primary/30 bg-surface-container-highest rounded-r-lg rounded-bl-lg p-4 w-fit max-w-[85%] shadow-[0_0_15px_rgba(138,235,255,0.1)] overflow-hidden">
                    {recommendation ? (
                         <RecommendationCard onGenerate={onGenerate} />
                    ) : (
                         <>
                              <h3 className="text-body-sm font-bold text-on-surface mb-4">
                                   Refine Plot Parameters ({currentQuestionIndex + 1}/{questions.length})
                              </h3>
                              <AnimatePresence mode="wait">
                                   {currentQuestion && (
                                        <motion.div
                                             key={currentQuestion.id}
                                             initial={{ opacity: 0, x: 20 }}
                                             animate={{ opacity: 1, x: 0 }}
                                             exit={{ opacity: 0, x: -20 }}
                                             transition={{ duration: 0.2 }}
                                        >
                                             <QuestionCard
                                                  question={currentQuestion}
                                                  questionNumber={currentQuestionIndex + 1}
                                             />
                                        </motion.div>
                                   )}
                              </AnimatePresence>
                         </>
                    )}
               </div>
          </div>
     );
}
