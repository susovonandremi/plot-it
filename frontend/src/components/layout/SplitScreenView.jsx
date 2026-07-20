import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { PanelRightClose, PanelRightOpen, MessageSquare } from 'lucide-react';

/**
 * SplitScreenView — Canvas + collapsible chat side panel.
 *
 * Design rationale: The chat panel slides out to a slim 48px icon bar
 * when collapsed, letting the InteractiveCanvas breathe at full width.
 * Both the aside and the main section use `layout` so Framer Motion
 * smoothly interpolates the flex reflow — no janky jumps.
 */
export default function SplitScreenView({ chat, canvas, hasBlueprint = false, isGenerating = false }) {
     const [activeTab, setActiveTab] = useState('chat'); // mobile: 'chat' | 'canvas'
     const [isPanelCollapsed, setIsPanelCollapsed] = useState(false);

     return (
          <div className="flex-1 flex flex-col md:flex-row min-h-0 w-full pt-16 relative">
               {/* Mobile Tab bar (Only visible on mobile if blueprint is loaded) */}
               {hasBlueprint && (
                    <div className="md:hidden flex justify-around border-b border-outline-variant bg-surface-container shrink-0 z-30">
                         <button
                              onClick={() => setActiveTab('chat')}
                              className={`flex-1 py-3 text-xs font-bold uppercase tracking-widest text-center border-b-2 transition-colors ${activeTab === 'chat' ? 'border-primary text-primary' : 'border-transparent text-on-surface-variant'}`}
                         >
                              Copilot Chat
                         </button>
                         <button
                              onClick={() => setActiveTab('canvas')}
                              className={`flex-1 py-3 text-xs font-bold uppercase tracking-widest text-center border-b-2 transition-colors ${activeTab === 'canvas' ? 'border-primary text-primary' : 'border-transparent text-on-surface-variant'}`}
                         >
                              Blueprint Canvas
                         </button>
                    </div>
               )}

               {/* AI Copilot Panel — Collapsible on desktop */}
               <motion.aside
                    layout
                    transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
                    className={`relative h-full bg-surface border-r border-outline-variant flex flex-col z-30 shadow-[4px_0_24px_rgba(0,0,0,0.5)] shrink-0 ${
                         hasBlueprint && activeTab !== 'chat' ? 'hidden md:flex' : 'flex'
                    }`}
                    style={{
                         width: isPanelCollapsed ? '48px' : '320px',
                         minWidth: isPanelCollapsed ? '48px' : '320px',
                    }}
               >
                    {/* Collapse toggle (desktop only) */}
                    <button
                         onClick={() => setIsPanelCollapsed(!isPanelCollapsed)}
                         className="hidden md:flex absolute -right-3 top-4 z-50 w-6 h-6 rounded-full bg-surface-container-high border border-outline-variant items-center justify-center text-on-surface-variant hover:text-primary hover:border-primary/50 hover:bg-surface-container-highest transition-all duration-200 shadow-lg hover:shadow-primary/20 cursor-pointer"
                         title={isPanelCollapsed ? 'Expand panel' : 'Collapse panel'}
                    >
                         {isPanelCollapsed ? <PanelRightOpen size={12} /> : <PanelRightClose size={12} />}
                    </button>

                    {/* Panel content — hidden when collapsed */}
                    <AnimatePresence mode="wait">
                         {isPanelCollapsed ? (
                              <motion.div
                                   key="collapsed"
                                   initial={{ opacity: 0 }}
                                   animate={{ opacity: 1 }}
                                   exit={{ opacity: 0 }}
                                   transition={{ duration: 0.15 }}
                                   className="flex flex-col items-center pt-14 gap-4"
                              >
                                   <button
                                        onClick={() => setIsPanelCollapsed(false)}
                                        className="w-8 h-8 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center text-primary hover:bg-primary/20 transition-colors cursor-pointer"
                                        title="Open Copilot"
                                   >
                                        <MessageSquare size={16} />
                                   </button>
                              </motion.div>
                         ) : (
                              <motion.div
                                   key="expanded"
                                   initial={{ opacity: 0 }}
                                   animate={{ opacity: 1 }}
                                   exit={{ opacity: 0 }}
                                   transition={{ duration: 0.2, delay: 0.1 }}
                                   className="flex flex-col h-full min-w-0 overflow-hidden"
                              >
                                   {chat}
                              </motion.div>
                         )}
                    </AnimatePresence>
               </motion.aside>

               {/* CAD Canvas Area */}
               <motion.section
                    layout
                    transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
                    className={`flex-1 relative overflow-hidden flex items-center justify-center ${hasBlueprint && activeTab !== 'canvas' ? 'hidden md:flex' : 'flex'}`}
               >
                    <div className="w-full h-full relative z-10">
                         {canvas}
                    </div>
               </motion.section>
          </div>
     );
}
