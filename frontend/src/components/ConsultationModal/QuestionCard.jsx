
import { useState, useEffect } from 'react';
import { useConsultationStore } from '@/store/consultationStore';
import OptionButton from './OptionButton';
import { recommendRooms } from '@/api/plotit';
import { toast } from 'sonner';
import { ChevronLeft, ChevronRight, Loader2, BarChart3 } from 'lucide-react';

const getPlaceholder = (question) => {
     if (question.placeholder) return question.placeholder;
     const text = (question.text || '').toLowerCase();
     const id = (question.id || '').toLowerCase();

     const isAreaOrSize = id.includes('area') || id.includes('size') || id.includes('sqft') || id.includes('dimen') ||
                          text.includes('area') || text.includes('size') || text.includes('sqft') || text.includes('dimension');
     if (isAreaOrSize) {
          return "e.g., 1200";
     }

     const isRoomCount = id.includes('room') || id.includes('bed') || id.includes('bath') || id.includes('kitchen') || 
                         id.includes('toilet') || id.includes('floor') || id.includes('count') ||
                         text.includes('how many') || text.includes('number of') || text.includes('kitchen') || text.includes('bathroom');
     if (isRoomCount) {
          return "e.g., 2";
     }

     return question.type === 'number' ? "e.g., 2" : "Type your answer here...";
};

export default function QuestionCard({ question, questionNumber }) {
     const {
          answers,
          answerQuestion,
          nextQuestion,
          previousQuestion,
          currentQuestionIndex,
          questions,
          submitAnswers
     } = useConsultationStore();

     const [isSubmitting, setIsSubmitting] = useState(false);

     // Initialize state based on question type
     const [localAnswer, setLocalAnswer] = useState(() => {
          const stored = answers[question.id];
          if (stored !== undefined && stored !== null) return stored;
          return question.type === 'multi_select' ? [] : '';
     });

     // Sync state if answers change (e.g. from draft restore) or question changes
     useEffect(() => {
          const stored = answers[question.id];
          if (stored !== undefined && stored !== null) {
               setLocalAnswer(stored);
          } else {
               setLocalAnswer(question.type === 'multi_select' ? [] : '');
          }
     }, [answers, question.id, question.type]);

     const handleOptionClick = (optionId) => {
          let updated;
          if (question.type === 'single_select') {
               updated = [optionId];
          } else {
               const current = Array.isArray(localAnswer) ? localAnswer : [];
               const maxSelections = question.max_selections || 999;

               if (current.includes(optionId)) {
                    updated = current.filter(id => id !== optionId);
               } else if (current.length < maxSelections) {
                    updated = [...current, optionId];
               } else {
                    return; // Max selections reached
               }
          }
          setLocalAnswer(updated);
          answerQuestion(question.id, updated);
     };

     const handleTextChange = (e) => {
          const val = e.target.value;
          setLocalAnswer(val);
          answerQuestion(question.id, val);
     };

     const canProceed = !question.required || (
          Array.isArray(localAnswer) ? localAnswer.length > 0 : String(localAnswer).trim().length > 0
     );

     const isLastQuestion = currentQuestionIndex === questions.length - 1;

     return (
          <div className="space-y-4 animate-in fade-in duration-200">
               {/* Question Header */}
               <div className="space-y-2">
                    <div className="flex items-center gap-2">
                         <span className="text-[10px] font-data-mono font-medium text-primary bg-primary/10 px-2 py-0.5 rounded border border-primary/20 uppercase tracking-wider">
                              Step {questionNumber}
                         </span>
                         <span className="text-[10px] font-data-mono font-medium text-on-surface-variant uppercase tracking-wider">
                              of {questions.length}
                         </span>
                    </div>
                    <h2 className="text-sm font-bold text-on-surface font-sans leading-tight">
                         {question.text}
                    </h2>
                    {question.type === 'multi_select' && (
                         <p className="text-[11px] text-on-surface-variant font-sans italic">
                              Select {question.max_selections ? `up to ${question.max_selections}` : 'as many as apply'}
                         </p>
                    )}
               </div>

               {/* Options List OR Text Input */}
               <div className="grid gap-2">
                    {question.options && question.options.length > 0 ? (
                         question.options.map((option, index) => (
                              <OptionButton
                                   key={option.id}
                                   option={option}
                                   isSelected={Array.isArray(localAnswer) && localAnswer.includes(option.id)}
                                   onClick={() => handleOptionClick(option.id)}
                                   type={question.type}
                                   animationDelay={index * 50}
                              />
                         ))
                    ) : question.type === 'number' ? (
                         <input
                              key={question.id}
                              type="number"
                              className="w-full max-w-[200px] p-3 border rounded border-outline-variant bg-surface text-on-surface text-xs font-mono placeholder:text-on-surface-variant/40 focus:border-primary focus:ring-1 focus:ring-primary/20 outline-none transition-all"
                              placeholder={getPlaceholder(question)}
                              value={typeof localAnswer === 'string' || typeof localAnswer === 'number' ? localAnswer : ''}
                              onChange={handleTextChange}
                              autoFocus
                         />
                    ) : (
                         <textarea
                              key={question.id}
                              className="w-full h-24 p-3 border rounded border-outline-variant bg-surface text-on-surface text-xs font-mono placeholder:text-on-surface-variant/40 focus:border-primary focus:ring-1 focus:ring-primary/20 outline-none resize-none transition-all"
                              placeholder={getPlaceholder(question)}
                              value={typeof localAnswer === 'string' ? localAnswer : ''}
                              onChange={handleTextChange}
                              autoFocus
                         />
                    )}
               </div>


               {/* Navigation Footer */}
               <div className="flex items-center justify-between pt-4 border-t border-outline-variant/30">
                    <button
                         onClick={previousQuestion}
                         disabled={currentQuestionIndex === 0}
                         className="flex items-center gap-1 text-[11px] font-data-mono text-on-surface-variant hover:text-on-surface transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                         <ChevronLeft size={14} />
                         <span>Back</span>
                    </button>

                    {isLastQuestion ? (
                         <button
                              onClick={async () => {
                                   setIsSubmitting(true);
                                   try {
                                        await submitAnswers(async ({ answers, plotData }) => {
                                             return await recommendRooms(plotData, answers);
                                        });
                                        toast.success("Recommendations generated!");
                                   } catch (err) {
                                        toast.error("Failed to generate recommendations. Please try again.");
                                        console.error(err);
                                   } finally {
                                        setIsSubmitting(false);
                                   }
                              }}
                              disabled={!canProceed || isSubmitting}
                              className="bg-primary hover:bg-primary-fixed text-on-primary font-bold px-4 py-2 rounded text-xs transition-all active:scale-95 flex items-center gap-1.5 hover:shadow-[0_0_10px_rgba(138,235,255,0.3)] disabled:opacity-50"
                         >
                              {isSubmitting ? (
                                   <>
                                        <Loader2 size={14} className="animate-spin" />
                                        <span>Analyzing...</span>
                                   </>
                              ) : (
                                   <>
                                        <span>Recommendations</span>
                                        <BarChart3 size={12} />
                                   </>
                              )}
                         </button>
                    ) : (
                         <button
                              onClick={nextQuestion}
                              disabled={!canProceed}
                              className="bg-primary hover:bg-primary-fixed text-on-primary font-bold px-5 py-2 rounded text-xs transition-all active:scale-95 flex items-center gap-1 hover:shadow-[0_0_10px_rgba(138,235,255,0.3)] disabled:opacity-50"
                         >
                              <span>Next</span>
                              <ChevronRight size={14} />
                         </button>
                    )}
               </div>
          </div>
     );
}
