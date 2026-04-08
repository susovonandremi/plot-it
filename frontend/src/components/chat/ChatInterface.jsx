import React, { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Bot, User, Sparkles, AlertCircle, Send, CheckCircle2, Loader2 } from 'lucide-react';
import * as Progress from '@radix-ui/react-progress';

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

export default function ChatInterface({ history, onSend, isLoading, isGenerating, generationProgress, pendingDraft }) {
     const [input, setInput] = useState('');
     const [isSubmitting, setIsSubmitting] = useState(false);
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

     const isSendDisabled = !input.trim() || isLoading || isSubmitting;

     return (
          <div className="w-full h-full flex flex-col items-center justify-end pb-8 px-4 sm:px-8">
               
               {/* Messages Area (Floating directly over canvas) */}
               <div className="w-full max-w-3xl flex-1 overflow-y-auto mb-6 custom-scrollbar pointer-events-auto flex flex-col justify-end" ref={scrollRef}>
                    <div className="space-y-4 pt-20">
                         <AnimatePresence initial={false}>
                              {history.length === 0 && !pendingDraft && (
                                   <motion.div
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        className="flex flex-col items-center justify-center text-center text-secondary space-y-4 mb-10"
                                   >
                                        <div className="p-4 bg-glass border border-white/5 rounded-full mb-2 shadow-sm">
                                             <Sparkles size={32} className="text-accent" />
                                        </div>
                                        <h2 className="text-2xl font-heading font-medium tracking-wide">Design your vision</h2>
                                        <p className="text-sm opacity-60">Describe your plan in plain words...</p>
                                        <div className="flex flex-wrap justify-center gap-2 mt-6 max-w-2xl">
                                             <button onClick={() => handleChipClick("3BHK 1200sqft east-facing, Vastu compliant")} className="text-xs py-2 px-4 bg-glass hover:bg-glass-hover border border-white/10 rounded-full transition-all text-secondary hover:shadow-neon hover:border-accent">
                                                  "3BHK 1200sqft east-facing..."
                                             </button>
                                             <button onClick={() => handleChipClick("Kerala-style 2000sqft house with courtyard and verandah")} className="text-xs py-2 px-4 bg-glass hover:bg-glass-hover border border-white/10 rounded-full transition-all text-secondary hover:shadow-neon hover:border-accent">
                                                  "Kerala-style 2000sqft house..."
                                             </button>
                                             <button onClick={() => handleChipClick("2BHK apartment 800sqft, modern minimalist style")} className="text-xs py-2 px-4 bg-glass hover:bg-glass-hover border border-white/10 rounded-full transition-all text-secondary hover:shadow-neon hover:border-accent">
                                                  "2BHK apartment 800sqft..."
                                             </button>
                                        </div>
                                   </motion.div>
                              )}

                              {history.map((msg, idx) => (
                                   <motion.div
                                        key={idx}
                                        initial={{ opacity: 0, scale: 0.95, y: 10 }}
                                        animate={{ opacity: 1, scale: 1, y: 0 }}
                                        transition={{ duration: 0.2 }}
                                        className={`flex w-full ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                                   >
                                        <div className={`flex gap-3 max-w-[85%] ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                                             <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${msg.role === 'user' ? 'bg-dominant-light border border-white/10' : msg.role === 'error' ? 'bg-red-900/50 text-red-400' : 'bg-glass text-accent border border-accent/30 shadow-neon'}`}>
                                                  {msg.role === 'user' ? <User size={16} /> : msg.role === 'error' ? <AlertCircle size={16} /> : <Bot size={16} />}
                                             </div>

                                             <div className={`p-4 rounded-2xl text-sm leading-relaxed backdrop-blur-md shadow-lg ${msg.role === 'user'
                                                  ? 'bg-glass border border-white/10 rounded-tr-sm text-secondary'
                                                  : msg.role === 'error'
                                                  ? 'bg-red-900/20 text-red-300 border border-red-500/30 rounded-tl-sm'
                                                  : 'bg-glass border border-accent/20 rounded-tl-sm text-secondary'
                                                  }`}>
                                                  {msg.content}
                                             </div>
                                        </div>
                                   </motion.div>
                              ))}

                              {isGenerating && generationProgress ? (
                                   <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex justify-start w-full">
                                        <div className="flex gap-3 w-full max-w-[85%]">
                                             <div className="w-8 h-8 rounded-full bg-glass text-accent border border-accent/30 shadow-neon flex items-center justify-center shrink-0">
                                                  <Bot size={16} />
                                             </div>
                                              <div className="p-4 bg-glass backdrop-blur-md rounded-2xl rounded-tl-sm border border-white/10 flex flex-col gap-4 flex-1 shadow-lg max-w-[85%]">
                                                   <div className="flex items-center justify-between border-b border-white/5 pb-2">
                                                        <div className="flex items-center gap-2 text-accent font-heading font-bold text-sm">
                                                             <Sparkles size={16} className="animate-pulse" />
                                                             <span>AI Architect Processing</span>
                                                        </div>
                                                        <span className="text-xs font-mono text-secondary/50">{Math.round(generationProgress.progress)}%</span>
                                                   </div>

                                                   {/* CoT steps */}
                                                   <div className="flex flex-col gap-3 font-mono text-xs pl-1">
                                                        <div className="flex items-start gap-3">
                                                             {generationProgress.progress > 20 ? <CheckCircle2 size={14} className="text-white/30 shrink-0 mt-0.5" /> : <Loader2 size={14} className="text-accent animate-spin shrink-0 mt-0.5" />}
                                                             <span className={generationProgress.progress > 20 ? "text-white/30" : "text-accent"}>Parsing spatial constraints</span>
                                                        </div>
                                                        {generationProgress.progress > 20 && (
                                                             <div className="flex items-start gap-3 animate-in fade-in zoom-in slide-in-from-top-2 duration-300">
                                                                  {generationProgress.progress > 50 ? <CheckCircle2 size={14} className="text-white/30 shrink-0 mt-0.5" /> : <Loader2 size={14} className="text-accent animate-spin shrink-0 mt-0.5" />}
                                                                  <span className={generationProgress.progress > 50 ? "text-white/30" : "text-accent"}>Applying Vastu & dimensions</span>
                                                             </div>
                                                        )}
                                                        {generationProgress.progress > 50 && (
                                                             <div className="flex items-start gap-3 animate-in fade-in zoom-in slide-in-from-top-2 duration-300">
                                                                  {generationProgress.progress > 80 ? <CheckCircle2 size={14} className="text-white/30 shrink-0 mt-0.5" /> : <Loader2 size={14} className="text-accent animate-spin shrink-0 mt-0.5" />}
                                                                  <span className={generationProgress.progress > 80 ? "text-white/30" : "text-accent"}>Computing generative layouts</span>
                                                             </div>
                                                        )}
                                                        {generationProgress.progress > 80 && (
                                                             <div className="flex items-start gap-3 animate-in fade-in zoom-in slide-in-from-top-2 duration-300">
                                                                  {generationProgress.progress >= 99 ? <CheckCircle2 size={14} className="text-white/30 shrink-0 mt-0.5" /> : <Loader2 size={14} className="text-accent animate-spin shrink-0 mt-0.5" />}
                                                                  <div className="flex flex-col gap-1 w-full overflow-hidden">
                                                                       <span className={generationProgress.progress >= 99 ? "text-white/30" : "text-accent"}>Rendering structural blueprint</span>
                                                                       {generationProgress.progress < 99 && (
                                                                            <span className="text-[10px] text-accent/60 italic overflow-hidden text-ellipsis whitespace-nowrap w-full animate-pulse">
                                                                                 &gt; {stageMap[generationProgress.stage] || "Finalizing"}...
                                                                            </span>
                                                                       )}
                                                                  </div>
                                                             </div>
                                                        )}
                                                   </div>

                                                   {/* Progress line */}
                                                   <div className="mt-2 h-1.5 w-full bg-dominant-light rounded-full overflow-hidden border border-white/5 relative">
                                                        <div className="absolute top-0 left-0 h-full bg-accent shadow-neon transition-all duration-300" style={{ width: `${generationProgress.progress}%` }}></div>
                                                   </div>
                                              </div>
                                        </div>
                                   </motion.div>
                              ) : isLoading && !isGenerating && (
                                   <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex justify-start w-full">
                                        <div className="flex gap-3 max-w-[85%]">
                                             <div className="w-8 h-8 rounded-full bg-glass text-accent border border-accent/30 shadow-neon flex items-center justify-center shrink-0 animate-pulse">
                                                  <Bot size={16} />
                                             </div>
                                             <div className="p-4 bg-glass backdrop-blur-md rounded-2xl rounded-tl-sm border border-white/10 flex items-center gap-1.5 shadow-lg">
                                                  <span className="w-1.5 h-1.5 bg-accent rounded-full animate-bounce [animation-delay:-0.3s]"></span>
                                                  <span className="w-1.5 h-1.5 bg-accent rounded-full animate-bounce [animation-delay:-0.15s]"></span>
                                                  <span className="w-1.5 h-1.5 bg-accent rounded-full animate-bounce"></span>
                                             </div>
                                        </div>
                                   </motion.div>
                              )}
                         </AnimatePresence>
                    </div>
               </div>

               {/* Input Area (Floating Pill) */}
               <div className="w-full max-w-3xl pointer-events-auto relative">
                    {/* The glowing active border illusion */}
                    <div className="absolute -inset-0.5 bg-gradient-to-r from-transparent via-accent/30 to-transparent rounded-full opacity-0 focus-within:opacity-100 transition-opacity duration-500 blur-sm pointer-events-none"></div>
                    
                    <div className="relative flex items-center gap-2 bg-glass backdrop-blur-xl p-2 rounded-full border border-white/10 shadow-2xl transition-all duration-300 hover:border-white/20 focus-within:border-accent/50 focus-within:shadow-neon focus-within:bg-[#ffffff0a]">
                         <textarea
                              ref={inputRef}
                              value={input}
                              onChange={(e) => setInput(e.target.value)}
                              onKeyDown={handleKeyDown}
                              placeholder="Describe your plan in plain words..."
                              className="flex-1 bg-transparent border-none outline-none text-base text-secondary resize-none h-[48px] py-3.5 px-6 custom-scrollbar placeholder:text-secondary/40 font-body placeholder:font-light"
                              rows={1}
                         />
                         <button
                              onClick={handleSubmit}
                              disabled={isSendDisabled}
                              className="w-12 h-12 rounded-full flex items-center justify-center bg-accent text-dominant shrink-0 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-300 hover:shadow-neon hover:scale-105 active:scale-95"
                         >
                              <Send size={20} strokeWidth={2.5} className="-ml-1" />
                         </button>
                    </div>
                    <div className="text-[10px] text-white/30 text-center mt-4 tracking-wide font-light">
                         AI CAN MAKE MISTAKES. REVIEW CAREFULLY.
                    </div>
               </div>
          </div>
     );
}
