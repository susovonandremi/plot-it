import { useConsultationStore } from '@/store/consultationStore';
import { Shield, Layers, Check, Ruler, CheckCircle, Home, ArrowRight } from 'lucide-react';

export default function RecommendationCard({ onGenerate }) {
     const { recommendation } = useConsultationStore();

     if (!recommendation) return null;

     return (
          <div className="space-y-6 animate-in fade-in zoom-in-95 duration-500">
               {/* Header */}
               <div className="text-center space-y-2 pb-2">
                    <div className="inline-flex items-center justify-center w-10 h-10 rounded bg-primary/10 text-primary mb-2 shadow-[0_0_10px_rgba(138,235,255,0.15)] border border-primary/30">
                         <Shield size={20} />
                    </div>
                    <h2 className="text-xl font-bold text-on-surface font-sans">
                         Ideal Floor Plan Configured
                    </h2>
                    <p className="text-xs text-on-surface-variant font-sans">
                         Spatial requirements optimized with Vastu alignment.
                    </p>
               </div>

               {/* Recommended Rooms List */}
               <div className="bg-surface border border-outline-variant/50 rounded-lg p-4 space-y-3 shadow-md">
                    <h3 className="text-[10px] font-data-mono font-bold text-on-surface-variant uppercase tracking-widest mb-1 flex items-center gap-2">
                         <Layers size={12} className="text-on-surface-variant" />
                         Allocated Rooms
                    </h3>
                    <div className="grid gap-3">
                         {recommendation.recommended_rooms.map((room, index) => (
                              <div
                                   key={index}
                                   className="flex items-start gap-3 bg-surface-container p-3 rounded border border-outline-variant/30 animate-in fade-in slide-in-from-right-4 duration-300"
                                   style={{ animationDelay: `${index * 100}ms` }}
                              >
                                   <div className="mt-0.5 w-4 h-4 rounded-sm bg-primary/20 border border-primary/30 flex items-center justify-center flex-shrink-0">
                                        <Check size={10} className="text-primary font-bold" />
                                   </div>
                                   <div>
                                        <div className="flex items-center gap-2 leading-none">
                                             <span className="font-bold text-xs text-primary font-mono">{room.count}x</span>
                                             <span className="font-bold text-xs text-on-surface font-sans">{room.type}</span>
                                        </div>
                                        <p className="text-[11px] text-on-surface-variant mt-1.5 leading-relaxed font-sans">
                                             {room.reasoning}
                                        </p>
                                   </div>
                              </div>
                         ))}
                    </div>
               </div>

               {/* Key Metrics */}
               <div className="grid grid-cols-3 gap-3">
                    <div className="bg-surface border border-outline-variant/50 rounded-lg p-3 text-center hover:border-primary/50 transition-colors">
                         <Ruler size={18} className="text-primary mb-1 block mx-auto" />
                         <p className="text-[9px] font-data-mono text-on-surface-variant uppercase tracking-tighter">Space Use</p>
                         <p className="text-sm font-bold text-on-surface font-mono mt-0.5">{recommendation.estimated_usage}</p>
                    </div>
                    <div className="bg-surface border border-outline-variant/50 rounded-lg p-3 text-center hover:border-primary/50 transition-colors">
                         <CheckCircle size={18} className="text-primary mb-1 block mx-auto" />
                         <p className="text-[9px] font-data-mono text-on-surface-variant uppercase tracking-tighter">Vastu Score</p>
                         <p className="text-sm font-bold text-on-surface font-mono mt-0.5">{recommendation.vastu_preview}</p>
                    </div>
                    <div className="bg-surface border border-outline-variant/50 rounded-lg p-3 text-center hover:border-primary/50 transition-colors">
                         <Home size={18} className="text-primary mb-1 block mx-auto" />
                         <p className="text-[9px] font-data-mono text-on-surface-variant uppercase tracking-tighter">Total Rooms</p>
                         <p className="text-sm font-bold text-on-surface font-mono mt-0.5">{recommendation.total_rooms}</p>
                    </div>
               </div>

               {/* CTA */}
               <div className="pt-2">
                    <button
                         onClick={() => {
                              if (onGenerate) {
                                   onGenerate(recommendation);
                              }
                         }}
                         className="w-full bg-primary hover:bg-primary-fixed text-on-primary font-bold py-3 rounded text-xs shadow-[0_0_15px_rgba(138,235,255,0.25)] transition-all active:scale-[0.98] flex items-center justify-center gap-2 group uppercase tracking-widest font-mono"
                    >
                         <span>Generate Blueprint</span>
                         <ArrowRight size={12} className="group-hover:translate-x-0.5 transition-transform" />
                    </button>
               </div>
          </div>
     );
}
