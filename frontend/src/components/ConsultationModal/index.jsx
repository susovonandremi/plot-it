import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { useConsultationStore } from '@/store/consultationStore';
import QuestionCard from './QuestionCard';
import RecommendationCard from './RecommendationCard';
import ProgressBar from './ProgressBar';
import { Sparkles } from 'lucide-react';

export default function ConsultationModal({ onGenerate }) {
     const {
          isConsultationActive,
          questions,
          currentQuestionIndex,
          recommendation,
          resetConsultation,
     } = useConsultationStore();

     const currentQuestion = questions ? questions[currentQuestionIndex] : null;

     return (
          <Dialog open={isConsultationActive} onOpenChange={(open) => {
               if (!open) {
                    // User closed the dialog (clicked outside or pressed Escape)
                    // Always reset to ensure clean state for next use
                    resetConsultation();
               }
          }}>
               <DialogContent className="max-w-[640px] w-[95vw] bg-dominant bg-opacity-95 backdrop-blur-xl rounded-3xl shadow-2xl p-0 border border-white/10 overflow-hidden animate-in zoom-in-95 duration-300">
                    <DialogHeader className="sr-only">
                         <DialogTitle>Consultation</DialogTitle>
                         <DialogDescription>
                              Answer a few questions to help us design your perfect floor plan.
                         </DialogDescription>
                    </DialogHeader>

                    <div className="relative max-h-[85vh] overflow-y-auto overflow-x-hidden custom-scrollbar">
                         {/* Header Accent */}
                         <div className="h-2 w-full bg-accent shadow-neon sticky top-0 z-10" />

                         <div className="p-8 md:p-12">
                              {recommendation ? (
                                   <RecommendationCard onGenerate={onGenerate} />
                              ) : (
                                   <>
                                        <div className="flex items-center gap-3 mb-6">
                                             <div className="p-2 rounded-lg bg-glass text-accent shadow-neon border border-accent/20">
                                                  <Sparkles className="w-5 h-5" />
                                             </div>
                                             <div>
                                                  <h1 className="text-xl font-bold text-secondary font-heading">Consultation</h1>
                                                  <p className="text-xs text-secondary/60 font-mono uppercase tracking-widest">Requirement Definition</p>
                                             </div>
                                        </div>

                                        <ProgressBar
                                             current={currentQuestionIndex + 1}
                                             total={questions.length}
                                        />

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
               </DialogContent>
          </Dialog>
     );
}
