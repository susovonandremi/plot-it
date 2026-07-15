import { Trash2, Play } from 'lucide-react';

export default function ResumeConsultationPrompt({ draft, onResume, onStartOver }) {
     const questionsAnswered = Object.keys(draft.answers).length;
     const totalQuestions = draft.questions.length;

     return (
          <div className="fixed inset-0 bg-surface/80 backdrop-blur-md z-50 flex items-center justify-center p-4 animate-in fade-in duration-300">
               <div className="bg-surface-container-high border border-outline-variant rounded-lg shadow-2xl max-w-md w-full overflow-hidden animate-in zoom-in-95 duration-200">
                    <div className="h-1.5 w-full bg-primary" />

                    <div className="p-6">
                         <h2 className="text-lg font-bold text-on-surface mb-2 font-sans">
                              Resume Spatial Consultation?
                         </h2>

                         <p className="text-xs text-on-surface-variant mb-6 font-sans leading-relaxed">
                              We found an active layout draft. You have configured <span className="font-semibold text-primary">{questionsAnswered} of {totalQuestions}</span> specs for your <span className="font-semibold text-primary font-mono">{draft.plotData?.size || draft.plotData?.plot_size_sqft} sqft</span> plot.
                         </p>

                         <div className="flex gap-3">
                              <button
                                   onClick={onStartOver}
                                   className="flex-1 border border-outline-variant/60 hover:border-error/50 hover:bg-error/10 text-on-surface-variant hover:text-error text-xs font-mono py-2.5 rounded transition-all flex items-center justify-center gap-1.5 group"
                              >
                                   <Trash2 size={14} className="text-on-surface-variant group-hover:text-error" />
                                   <span>Start Over</span>
                              </button>

                              <button
                                   onClick={onResume}
                                   className="flex-1 bg-primary hover:bg-primary-fixed text-on-primary font-bold py-2.5 rounded text-xs transition-all active:scale-[0.98] flex items-center justify-center gap-1.5 shadow-[0_0_12px_rgba(138,235,255,0.2)]"
                              >
                                   <Play size={14} className="text-on-primary" />
                                   <span>Resume Config</span>
                              </button>
                         </div>
                    </div>
               </div>
          </div>
     );
}
