
import { useState, useEffect } from 'react';
import { useConsultationStore } from '@/store/consultationStore';
import OptionButton from './OptionButton';
import { ChevronLeft, ChevronRight, Sparkles, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { recommendRooms } from '@/api/plotai';
import { toast } from 'sonner';

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
          if (stored !== undefined) return stored;
          return question.type === 'multi_select' ? [] : '';
     });

     // Sync state if answers change (e.g. from draft restore) or question changes
     useEffect(() => {
          const stored = answers[question.id];
          if (stored !== undefined) {
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
          <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-300">
               {/* Question Header */}
               <div>
                    <div className="flex items-center gap-2 mb-2">
                         <span className="text-xs font-mono font-medium text-accent bg-accent/10 px-2 py-0.5 rounded uppercase tracking-wider">
                              Step {questionNumber}
                         </span>
                         <span className="text-xs font-mono font-medium text-secondary/60 uppercase tracking-wider">
                              of {questions.length}
                         </span>
                    </div>
                    <h2 className="text-2xl font-bold text-secondary font-heading leading-tight">
                         {question.text}
                    </h2>
                    {question.type === 'multi_select' && (
                         <p className="text-sm text-secondary/60 mt-2 font-body italic">
                              Select {question.max_selections ? `up to ${question.max_selections}` : 'as many as apply'}
                         </p>
                    )}
               </div>

               {/* Options List OR Text Input */}
               <div className="grid gap-3">
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
                    ) : (
                         <textarea
                              className="w-full h-32 p-4 border rounded-xl border-white/10 focus:border-accent focus:ring-4 focus:ring-accent/20 outline-none resize-none bg-glass text-secondary font-body transition-all"
                              placeholder="Type your answer here..."
                              value={typeof localAnswer === 'string' ? localAnswer : ''}
                              onChange={handleTextChange}
                              autoFocus
                         />
                    )}
               </div>

               {/* Navigation Footer */}
               <div className="flex items-center justify-between pt-6 border-t border-white/5">
                    <Button
                         variant="ghost"
                         onClick={previousQuestion}
                         disabled={currentQuestionIndex === 0}
                         className="flex items-center gap-2 text-secondary/60 hover:text-secondary hover:bg-glass transition-colors"
                    >
                         <ChevronLeft className="w-4 h-4" />
                         <span>Back</span>
                    </Button>

                    {isLastQuestion ? (
                         <Button
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
                              className="bg-accent hover:bg-accent-hover text-dominant font-semibold px-8 py-6 rounded-xl h-auto transition-all active:scale-95 flex items-center gap-2 hover:shadow-neon"
                         >
                              {isSubmitting ? (
                                   <>
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                        <span>Analyzing...</span>
                                   </>
                              ) : (
                                   <>
                                        <span>See Recommendations</span>
                                        <Sparkles className="w-4 h-4" />
                                   </>
                              )}
                         </Button>
                    ) : (
                         <Button
                              onClick={nextQuestion}
                              disabled={!canProceed}
                              className="bg-accent hover:bg-accent-hover text-dominant font-semibold px-8 py-6 rounded-xl h-auto transition-all active:scale-95 flex items-center gap-2 hover:shadow-neon"
                         >
                              <span>Next</span>
                              <ChevronRight className="w-4 h-4" />
                         </Button>
                    )}
               </div>
          </div>
     );
}
