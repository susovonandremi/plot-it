import { useConsultationStore } from '@/store/consultationStore';
import QuestionCard from './QuestionCard';
import RecommendationCard from './RecommendationCard';
import { SlidersHorizontal } from 'lucide-react';

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
          <div className="flex flex-col items-start gap-2 animate-pulse-once w-full mt-4">
               <div className="flex items-center gap-2">
                    <SlidersHorizontal size={14} className="text-primary" />
                    <span className="text-[10px] text-primary font-label-caps uppercase">Consultation Mode</span>
               </div>
               <div className="border border-primary/30 bg-surface-container-highest rounded-r-lg rounded-bl-lg p-4 w-full shadow-[0_0_15px_rgba(138,235,255,0.1)]">
                    {recommendation ? (
                         <RecommendationCard onGenerate={onGenerate} />
                    ) : (
                         <>
                              <h3 className="text-body-sm font-bold text-on-surface mb-4">
                                   Refine Plot Parameters ({currentQuestionIndex + 1}/{questions.length})
                              </h3>
                              {currentQuestion && (
                                   <QuestionCard
                                        question={currentQuestion}
                                        questionNumber={currentQuestionIndex + 1}
                                   />
                              )}
                         </>
                    )}
               </div>
          </div>
     );
}
