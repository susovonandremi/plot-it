import { useConsultationStore } from '@/store/consultationStore';
import { Check, ArrowRight, Home, Layout, Ruler, ShieldCheck } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function RecommendationCard({ onGenerate }) {
     const { recommendation } = useConsultationStore();

     if (!recommendation) return null;

     return (
          <div className="space-y-8 animate-in fade-in zoom-in-95 duration-500">
               {/* Header */}
               <div className="text-center space-y-2">
                    <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-accent/10 text-accent mb-2 shadow-neon">
                         <ShieldCheck className="w-6 h-6" />
                    </div>
                    <h2 className="text-3xl font-bold text-secondary font-heading">
                         Your Ideal Floor Plan
                    </h2>
                    <p className="text-secondary/60 font-body">
                         Based on your preferences, we've optimized your layout.
                    </p>
               </div>

               {/* Recommended Rooms List */}
               <div className="bg-glass rounded-2xl p-6 space-y-4 border border-white/10 shadow-lg">
                    <h3 className="text-sm font-mono font-bold text-secondary/60 uppercase tracking-widest mb-2 flex items-center gap-2">
                         <Layout className="w-4 h-4" />
                         Recommended Rooms
                    </h3>
                    <div className="grid gap-4">
                         {recommendation.recommended_rooms.map((room, index) => (
                              <div
                                   key={index}
                                   className="flex items-start gap-4 bg-dominant p-4 rounded-xl shadow-sm border border-white/5 animate-in fade-in slide-in-from-right-4 duration-300"
                                   style={{ animationDelay: `${index * 100}ms` }}
                              >
                                   <div className="mt-1 w-5 h-5 rounded-full bg-accent flex items-center justify-center flex-shrink-0 shadow-neon">
                                        <Check className="w-3 h-3 text-dominant" />
                                   </div>
                                   <div>
                                        <div className="flex items-center gap-2">
                                             <span className="font-bold text-secondary">{room.count}x</span>
                                             <span className="font-semibold text-secondary">{room.type}</span>
                                        </div>
                                        <p className="text-sm text-secondary/60 mt-1 leading-relaxed">
                                             {room.reasoning}
                                        </p>
                                   </div>
                              </div>
                         ))}
                    </div>
               </div>

               {/* Key Metrics */}
               <div className="grid grid-cols-3 gap-4">
                    <div className="bg-glass border border-white/10 rounded-xl p-4 text-center hover:border-accent transition-colors">
                         <Ruler className="w-5 h-5 text-accent mx-auto mb-2" />
                         <p className="text-xs font-mono text-secondary/60 uppercase tracking-tighter">Space Use</p>
                         <p className="text-lg font-bold text-secondary font-heading">{recommendation.estimated_usage}</p>
                    </div>
                    <div className="bg-glass border border-white/10 rounded-xl p-4 text-center hover:border-accent transition-colors">
                         <ShieldCheck className="w-5 h-5 text-accent mx-auto mb-2" />
                         <p className="text-xs font-mono text-secondary/60 uppercase tracking-tighter">Vastu Score</p>
                         <p className="text-lg font-bold text-secondary font-heading">{recommendation.vastu_preview}</p>
                    </div>
                    <div className="bg-glass border border-white/10 rounded-xl p-4 text-center hover:border-accent transition-colors">
                         <Home className="w-5 h-5 text-accent mx-auto mb-2" />
                         <p className="text-xs font-mono text-secondary/60 uppercase tracking-tighter">Total Rooms</p>
                         <p className="text-lg font-bold text-secondary font-heading">{recommendation.total_rooms}</p>
                    </div>
               </div>

               {/* CTA */}
               <div className="pt-4">
                    <Button
                         onClick={() => {
                              // Pass the recommendation data up explicitly. 
                              // Home.jsx will reset the consultation and start generation.
                              if (onGenerate) {
                                   onGenerate(recommendation);
                              }
                         }}
                         className="w-full bg-accent hover:bg-accent-hover text-dominant font-bold py-8 rounded-2xl text-lg shadow-neon transition-all active:scale-95 flex items-center justify-center gap-3 group"
                    >
                         <span>Generate Blueprint</span>
                         <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                    </Button>
               </div>
          </div>
     );
}
