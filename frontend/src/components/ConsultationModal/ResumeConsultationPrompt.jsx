import { Trash2, Play } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function ResumeConsultationPrompt({ draft, onResume, onStartOver }) {
     const questionsAnswered = Object.keys(draft.answers).length;
     const totalQuestions = draft.questions.length;

     return (
          <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-md z-50 flex items-center justify-center p-4 animate-in fade-in duration-300">
               <div className="bg-white rounded-3xl shadow-2xl max-w-md w-full overflow-hidden animate-in zoom-in-95 duration-300">
                    <div className="h-2 w-full bg-sky-500" />

                    <div className="p-8">
                         <h2 className="text-2xl font-bold text-slate-900 mb-2 font-heading">
                              Continue Your Consultation?
                         </h2>

                         <p className="text-slate-600 mb-8 font-body leading-relaxed">
                              We found a saved draft. You answered <span className="font-bold text-slate-900">{questionsAnswered} of {totalQuestions}</span> questions for your <span className="font-bold text-slate-900">{draft.plotData?.size || draft.plotData?.plot_size_sqft} sqft</span> plot.
                         </p>

                         <div className="flex gap-4">
                              <Button
                                   variant="outline"
                                   onClick={onStartOver}
                                   className="flex-1 border-2 border-slate-100 text-slate-500 font-semibold py-6 rounded-xl hover:bg-slate-50 hover:text-slate-900 transition-all flex items-center gap-2 group"
                              >
                                   <Trash2 className="w-4 h-4 group-hover:text-red-500 transition-colors" />
                                   <span>Start over</span>
                              </Button>

                              <Button
                                   onClick={onResume}
                                   className="flex-1 bg-sky-500 hover:bg-sky-600 text-white font-semibold py-6 rounded-xl transition-all active:scale-95 flex items-center gap-2"
                              >
                                   <Play className="w-4 h-4 fill-current" />
                                   <span>Resume</span>
                              </Button>
                         </div>
                    </div>
               </div>
          </div>
     );
}
