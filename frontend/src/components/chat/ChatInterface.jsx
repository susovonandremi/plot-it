import React, { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import ConsultationModal from '../ConsultationModal';
import { Bot, AlertTriangle, Send, Home, Compass, SlidersHorizontal } from 'lucide-react';
import { useConsultationStore } from '../../store/consultationStore';

const stageMap = {
     parsing: "Reading your prompt",
     building_program: "Building room program",
     vastu: "Applying Vastu rules",
     circulation: "Optimizing corridors",
     layout: "Designing floor plan",
     structural: "Computing structure",
     proportions: "Validating proportions",
     scoring: "Scoring blueprint",
     environment: "Analyzing environment",
     isometric: "Generating 3D view",
     voronoi: "Generating organic layout",
     rendering: "Drawing blueprint",
     complete: "Complete"
};

export default function ChatInterface({ history, onSend, isLoading, isGenerating, generationProgress, pendingDraft, onConsultationGenerate }) {
     const isConsultationActive = useConsultationStore(state => state.isConsultationActive);
     const [input, setInput] = useState('');
     const [isSubmitting, setIsSubmitting] = useState(false);
     const [sessionId] = useState(() => crypto.randomUUID().slice(0, 8).toUpperCase());
     const scrollRef = useRef(null);
     const inputRef = useRef(null);

     const handleChipClick = (text) => {
          setInput(text);
          if (inputRef.current) {
               inputRef.current.focus();
          }
     };

     useEffect(() => {
          if (!isLoading && !isGenerating) {
               setIsSubmitting(false);
          }
     }, [isLoading, isGenerating]);

     useEffect(() => {
          if (scrollRef.current) {
               scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
          }
     }, [history, isLoading, isGenerating, generationProgress]);

     const handleSubmit = useCallback((e) => {
          if (e) e.preventDefault();
          const trimmed = input.trim();
          if (!trimmed || isLoading || isSubmitting) return;
          
          setIsSubmitting(true);
          onSend(trimmed);
          setInput('');
     }, [input, isLoading, isSubmitting, onSend]);

     const handleKeyDown = (e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
               e.preventDefault();
               handleSubmit(e);
          }
     };

     const isSendDisabled = !input.trim() || isLoading || isSubmitting || isConsultationActive;

     return (
          <>
               {/* Chat Header */}
               <div className="px-4 py-3 border-b border-outline-variant/30 bg-surface-container-high/80 backdrop-blur-sm flex justify-between items-center shrink-0">
                    <div className="flex items-center gap-2">
                         <div className="w-2 h-2 rounded-full bg-secondary shadow-[0_0_8px_rgba(69,223,164,0.4)] animate-pulse"></div>
                         <span className="text-label-caps text-on-surface uppercase tracking-widest">Active Session</span>
                    </div>
                    <span className="text-data-mono text-xs text-on-surface-variant/70">ID: PLT-{sessionId}</span>
               </div>
               
               {/* Chat History */}
               <div className="flex-1 overflow-y-auto chat-scroll p-4 space-y-6" ref={scrollRef}>
                    <AnimatePresence initial={false}>
                         {history.length === 0 && !pendingDraft && (
                              <motion.div
                                   initial={{ opacity: 0, y: 10 }}
                                   animate={{ opacity: 1, y: 0 }}
                                   className="flex flex-col items-center justify-center text-center space-y-4 mb-10 pt-10"
                              >
                                   <div className="w-12 h-12 rounded bg-primary/10 flex items-center justify-center border border-primary/30 shadow-[0_0_15px_rgba(138,235,255,0.2)]">
                                        <Bot size={24} className="text-primary" />
                                   </div>
                                   <h2 className="text-headline-md font-bold text-on-surface">Design your vision</h2>
                                   <p className="text-body-sm text-on-surface-variant">Describe your plan in plain words...</p>
                                   <div className="flex flex-col gap-3 mt-6 w-full max-w-sm mx-auto">
                                        <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} onClick={() => handleChipClick("Generate a 3BHK 1200 sqft east-facing house, strictly Vastu compliant.")} className="group relative w-full text-left bg-surface-container border border-outline-variant/50 rounded-xl p-3 hover:border-primary/50 hover:bg-surface-variant/50 transition-all duration-300 overflow-hidden shadow-sm">
                                             <div className="absolute inset-0 bg-gradient-to-r from-primary/0 via-primary/5 to-primary/0 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-700 ease-in-out"></div>
                                             <div className="flex items-center gap-3 relative z-10">
                                                  <div className="w-8 h-8 rounded bg-primary/10 flex items-center justify-center shrink-0 border border-primary/20">
                                                       <Home size={14} className="text-primary" />
                                                  </div>
                                                  <div className="flex flex-col">
                                                       <span className="text-xs font-bold text-on-surface mb-0.5">Standard 3BHK / Vastu</span>
                                                       <span className="text-[10px] text-on-surface-variant/70 font-mono tracking-tight">1200 SQFT • EAST FACING</span>
                                                  </div>
                                             </div>
                                        </motion.button>
                                        
                                        <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} onClick={() => handleChipClick("Create a Kerala-style 2000 sqft house featuring a central courtyard and verandah.")} className="group relative w-full text-left bg-surface-container border border-outline-variant/50 rounded-xl p-3 hover:border-primary/50 hover:bg-surface-variant/50 transition-all duration-300 overflow-hidden shadow-sm">
                                             <div className="absolute inset-0 bg-gradient-to-r from-primary/0 via-primary/5 to-primary/0 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-700 ease-in-out"></div>
                                             <div className="flex items-center gap-3 relative z-10">
                                                  <div className="w-8 h-8 rounded bg-primary/10 flex items-center justify-center shrink-0 border border-primary/20">
                                                       <Compass size={14} className="text-primary" />
                                                  </div>
                                                  <div className="flex flex-col">
                                                       <span className="text-xs font-bold text-on-surface mb-0.5">Courtyard Villa</span>
                                                       <span className="text-[10px] text-on-surface-variant/70 font-mono tracking-tight">2000 SQFT • KERALA STYLE</span>
                                                  </div>
                                             </div>
                                        </motion.button>
                                   </div>
                              </motion.div>
                         )}

                         {history.map((msg, idx) => (
                              <motion.div
                                   key={idx}
                                   initial={{ opacity: 0, scale: 0.95, y: 10 }}
                                   animate={{ opacity: 1, scale: 1, y: 0 }}
                                   transition={{ duration: 0.2 }}
                              >
                                   {msg.role === 'user' ? (
                                        <div className="flex flex-col items-end gap-1 w-full">
                                             <div className="bg-surface-container-highest border border-outline-variant rounded-l-lg rounded-tr-lg p-3 max-w-[85%]">
                                                  <p className="text-body-sm text-on-surface whitespace-pre-wrap">{msg.content}</p>
                                             </div>
                                        </div>
                                   ) : msg.role === 'error' ? (
                                        <div className="flex flex-col items-start gap-2 w-full">
                                             <div className="flex items-center gap-2">
                                                  <AlertTriangle size={14} className="text-error" />
                                                  <span className="text-[10px] text-error font-label-caps uppercase">System Error</span>
                                             </div>
                                              <div className="border border-error/50 bg-error/10 rounded-r-lg rounded-bl-lg p-3 max-w-[85%] shadow-[inset_0_0_10px_rgba(255,180,171,0.05)]">
                                                   <p className="text-body-sm text-error">{msg.content}</p>
                                                   {msg.content.includes("configure") && (
                                                        <button 
                                                             onClick={() => {
                                                                  const defaultQuestions = [
                                                                       { 
                                                                            id: "plot_dimensions", 
                                                                            text: "What are your plot dimensions? (e.g., 30x40, 40x60)", 
                                                                            type: "single_select",
                                                                            required: true,
                                                                            options: [
                                                                                 { id: "30x40", label: "30x40" },
                                                                                 { id: "40x60", label: "40x60" },
                                                                                 { id: "20x30", label: "20x30" },
                                                                                 { id: "Other", label: "Other" }
                                                                            ]
                                                                       },
                                                                       { 
                                                                            id: "bedrooms", 
                                                                            text: "How many bedrooms do you need?", 
                                                                            type: "single_select",
                                                                            required: true,
                                                                            options: [
                                                                                 { id: "1 BHK", label: "1 BHK" },
                                                                                 { id: "2 BHK", label: "2 BHK" },
                                                                                 { id: "3 BHK", label: "3 BHK" },
                                                                                 { id: "4 BHK", label: "4 BHK" }
                                                                            ]
                                                                       },
                                                                       { 
                                                                            id: "floors", 
                                                                            text: "How many floors?", 
                                                                            type: "single_select",
                                                                            required: true,
                                                                            options: [
                                                                                 { id: "1", label: "1 Floor (Ground only)" },
                                                                                 { id: "2", label: "2 Floors (G+1)" },
                                                                                 { id: "3", label: "3 Floors (G+2)" }
                                                                            ]
                                                                       },
                                                                       { 
                                                                            id: "entry", 
                                                                            text: "Which side is the entrance road?", 
                                                                            type: "single_select",
                                                                            required: true,
                                                                            options: [
                                                                                 { id: "E", label: "East" },
                                                                                 { id: "W", label: "West" },
                                                                                 { id: "N", label: "North" },
                                                                                 { id: "S", label: "South" }
                                                                            ]
                                                                       }
                                                                  ];
                                                                  useConsultationStore.getState().startConsultation(defaultQuestions, {
                                                                       plot_size_sqft: 1200,
                                                                       plot_width_ft: 30,
                                                                       plot_depth_ft: 40,
                                                                       entry_direction: "N",
                                                                       rooms: []
                                                                  });
                                                             }}
                                                             className="mt-3 px-3 py-1.5 bg-error hover:bg-red-700 text-white font-bold rounded text-xs transition-colors cursor-pointer block"
                                                        >
                                                             Start Manual Configuration
                                                        </button>
                                                   )}
                                              </div>
                                        </div>
                                   ) : (
                                        <div className="flex flex-col items-start gap-2 w-full">
                                             <div className="flex items-center gap-2">
                                                  <Bot size={14} className="text-primary" />
                                                  <span className="text-[10px] text-primary font-label-caps uppercase">PlotIt Kernel</span>
                                             </div>
                                             <div className="border border-primary/30 bg-primary/5 rounded-r-lg rounded-bl-lg p-4 w-full shadow-[inset_0_0_20px_rgba(138,235,255,0.02)]">
                                                  <p className="text-body-sm text-on-surface whitespace-pre-wrap">{msg.content}</p>
                                             </div>
                                        </div>
                                   )}
                              </motion.div>
                         ))}

                         <ConsultationModal onGenerate={onConsultationGenerate} />
                    </AnimatePresence>
               </div>
               
               {/* Pinned Loading Status Box */}
               <AnimatePresence>
                    {isGenerating && generationProgress && (
                         <motion.div 
                              initial={{ opacity: 0, y: 15 }} 
                              animate={{ opacity: 1, y: 0 }} 
                              exit={{ opacity: 0, y: 15 }}
                              className="px-4 py-3 border-t border-outline-variant/20 glass-surface shrink-0 z-20"
                         >
                              <div className="flex items-center gap-2 mb-2">
                                   <Bot size={14} className="text-primary animate-pulse" />
                                   <span className="text-[10px] text-primary font-label-caps uppercase tracking-wider">Kernel Solver Processing</span>
                              </div>
                              <div className="border border-primary/15 bg-surface/50 rounded-xl p-3.5 shadow-lg backdrop-blur-sm">
                                   <div className="flex items-center justify-between border-b border-outline-variant/20 pb-2 mb-2.5">
                                        <span className="text-xs text-primary font-semibold">Generating Blueprint...</span>
                                        <span className="text-data-mono text-xs text-primary font-bold tabular-nums">{Math.round(generationProgress.progress)}%</span>
                                   </div>
                                   <p className="text-data-mono text-[11px] text-on-surface-variant animate-pulse mb-3">
                                        &gt; {stageMap[generationProgress.stage] || "Finalizing"}...
                                   </p>
                                   <div className="h-1.5 w-full bg-surface-container rounded-full overflow-hidden border border-outline-variant/20 relative">
                                        <div className="absolute top-0 left-0 h-full rounded-full bg-gradient-to-r from-primary-container to-primary shadow-[0_0_12px_rgba(138,235,255,0.5)] transition-all duration-500" style={{ width: `${generationProgress.progress}%` }}></div>
                                   </div>
                              </div>
                         </motion.div>
                    )}

                    {isLoading && !isGenerating && (
                         <motion.div 
                              initial={{ opacity: 0, y: 15 }} 
                              animate={{ opacity: 1, y: 0 }} 
                              exit={{ opacity: 0, y: 15 }}
                              className="px-4 py-3 border-t border-outline-variant/20 glass-surface shrink-0 z-20"
                         >
                              <div className="flex items-center gap-2 mb-2">
                                   <Bot size={14} className="text-primary animate-pulse" />
                                   <span className="text-[10px] text-primary font-label-caps uppercase tracking-wider">PlotIt Kernel</span>
                              </div>
                              <div className="border border-primary/15 bg-surface/50 rounded-xl p-3 flex items-center gap-1.5 shadow-lg backdrop-blur-sm">
                                   <span className="text-xs text-on-surface-variant font-medium mr-1.5">Kernel is thinking</span>
                                   <span className="w-1.5 h-1.5 bg-primary rounded-full shadow-[0_0_6px_rgba(138,235,255,0.4)] animate-bounce [animation-delay:-0.3s]"></span>
                                   <span className="w-1.5 h-1.5 bg-primary rounded-full shadow-[0_0_6px_rgba(138,235,255,0.4)] animate-bounce [animation-delay:-0.15s]"></span>
                                   <span className="w-1.5 h-1.5 bg-primary rounded-full shadow-[0_0_6px_rgba(138,235,255,0.4)] animate-bounce"></span>
                              </div>
                         </motion.div>
                    )}
               </AnimatePresence>
               
               {/* Input Area */}
               <div className="p-4 border-t border-outline-variant/20 bg-surface-container/80 backdrop-blur-sm shrink-0">
                    {isConsultationActive ? (
                         <div className="bg-surface border border-primary/20 rounded-lg p-3.5 flex items-center justify-center gap-2.5 shadow-[inset_0_0_15px_rgba(138,235,255,0.02)] animate-pulse">
                              <SlidersHorizontal size={14} className="text-primary" />
                              <span className="text-xs text-primary font-medium tracking-wide">Answering spatial consultation specs above...</span>
                         </div>
                    ) : (
                         <div className="relative group">
                              <div className="absolute -inset-0.5 bg-gradient-to-r from-primary to-secondary rounded-lg blur opacity-20 group-focus-within:opacity-40 transition duration-500"></div>
                              <div className="relative bg-surface border border-outline-variant rounded-lg flex items-end shadow-inner focus-within:border-primary/50 transition-colors">
                                   <textarea
                                        ref={inputRef}
                                        value={input}
                                        onChange={(e) => setInput(e.target.value)}
                                        onKeyDown={handleKeyDown}
                                        disabled={isLoading || isSubmitting}
                                        placeholder="Command PlotIt..."
                                        className="w-full bg-transparent text-body-sm text-on-surface placeholder-on-surface-variant/50 border-none focus:ring-0 resize-none p-3 max-h-32 outline-none disabled:opacity-50"
                                        rows={2}
                                   />
                                   <div className="p-2">
                                        <button
                                             onClick={handleSubmit}
                                             disabled={isSendDisabled}
                                             className="w-8 h-8 rounded bg-primary/10 text-primary flex items-center justify-center hover:bg-primary hover:text-on-primary transition-colors border border-primary/30 disabled:opacity-50 disabled:cursor-not-allowed"
                                        >
                                             <Send size={14} />
                                        </button>
                                   </div>
                              </div>
                         </div>
                    )}
               </div>
          </>
     );
}
