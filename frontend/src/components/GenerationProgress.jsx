import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Cpu, Layers, Ruler, Pen, CheckCircle2 } from 'lucide-react';

/**
 * GenerationProgress — Cinematic multi-step progress overlay.
 *
 * Design rationale: Each generation stage maps to an icon + label that
 * staggers in sequentially, giving the user a sense of forward momentum.
 * The progress bar uses a dual-layer glow (solid fill + shimmer sweep)
 * so it feels alive even when the WebSocket hasn't sent a new event yet.
 */

const STAGES = [
     { key: 'parsing',          icon: Cpu,          label: 'Parsing prompt & design inference' },
     { key: 'building_program', icon: Layers,       label: 'Building spatial room program' },
     { key: 'solving',          icon: Ruler,        label: 'Solving constraints via CP-SAT' },
     { key: 'validating',       icon: CheckCircle2, label: 'Validating Vastu & proportions' },
     { key: 'rendering',        icon: Pen,          label: 'Rendering architectural blueprint' },
];

// Map any backend stage to a sequential index
const STAGE_ORDER = {
     parsing: 0,
     building_program: 1,
     setbacks: 1,
     vastu: 2,
     circulation: 2,
     layout: 2,
     structural: 2,
     proportions: 3,
     scoring: 3,
     environment: 3,
     solving: 2,
     validating: 3,
     isometric: 4,
     voronoi: 4,
     rendering: 4,
     complete: 5,
};

export default function GenerationProgress({ progress = 0, stage = 'parsing' }) {
     const currentIdx = STAGE_ORDER[stage] ?? 0;

     return (
          <div className="flex flex-col items-center justify-center w-full max-w-lg mx-auto px-6">
               {/* Glassmorphism card */}
               <motion.div
                    initial={{ opacity: 0, scale: 0.92, y: 30 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
                    className="w-full glass-surface rounded-2xl p-8 relative overflow-hidden"
               >
                    {/* Background shimmer sweep */}
                    <div className="absolute inset-0 overflow-hidden pointer-events-none">
                         <div className="absolute inset-0 bg-gradient-to-r from-transparent via-primary/[0.04] to-transparent animate-shimmer" />
                    </div>

                    {/* Header */}
                    <div className="flex items-center gap-3 mb-6 relative z-10">
                         <div className="w-10 h-10 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center shadow-[0_0_20px_rgba(138,235,255,0.15)]">
                              <Cpu size={20} className="text-primary animate-pulse" />
                         </div>
                         <div>
                              <h3 className="text-sm font-bold text-on-surface tracking-wide">Architectural Solver</h3>
                              <p className="text-[10px] text-on-surface-variant font-data-mono uppercase tracking-widest">Processing layout</p>
                         </div>
                         <div className="ml-auto">
                              <span className="text-lg font-bold text-primary font-data-mono tabular-nums">
                                   {Math.round(progress)}%
                              </span>
                         </div>
                    </div>

                    {/* Progress bar */}
                    <div className="relative h-2 w-full bg-surface-container rounded-full overflow-hidden border border-outline-variant/20 mb-8">
                         {/* Filled portion */}
                         <motion.div
                              className="absolute inset-y-0 left-0 rounded-full"
                              style={{
                                   background: 'linear-gradient(90deg, #22d3ee, #8aebff, #45dfa4)',
                                   backgroundSize: '200% 100%',
                              }}
                              initial={{ width: '0%' }}
                              animate={{ width: `${Math.min(progress, 100)}%` }}
                              transition={{ duration: 0.6, ease: 'easeOut' }}
                         />
                         {/* Glow overlay on the filled bar */}
                         <motion.div
                              className="absolute inset-y-0 left-0 rounded-full opacity-60"
                              style={{ filter: 'blur(4px)' }}
                              initial={{ width: '0%' }}
                              animate={{ width: `${Math.min(progress, 100)}%` }}
                              transition={{ duration: 0.6, ease: 'easeOut' }}
                         >
                              <div
                                   className="w-full h-full animate-progress-glow"
                                   style={{
                                        background: 'linear-gradient(90deg, transparent, rgba(138,235,255,0.6), transparent)',
                                        backgroundSize: '200% 100%',
                                   }}
                              />
                         </motion.div>
                    </div>

                    {/* Stage steps */}
                    <div className="space-y-3 relative z-10">
                         <AnimatePresence mode="popLayout">
                              {STAGES.map((s, idx) => {
                                   const Icon = s.icon;
                                   const isComplete = idx < currentIdx;
                                   const isCurrent = idx === currentIdx;
                                   const isPending = idx > currentIdx;

                                   return (
                                        <motion.div
                                             key={s.key}
                                             initial={{ opacity: 0, x: -12 }}
                                             animate={{
                                                  opacity: isPending ? 0.3 : 1,
                                                  x: 0,
                                             }}
                                             transition={{
                                                  duration: 0.35,
                                                  delay: idx * 0.08,
                                                  ease: 'easeOut',
                                             }}
                                             className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors duration-300 ${
                                                  isCurrent
                                                       ? 'bg-primary/[0.08] border border-primary/20'
                                                       : isComplete
                                                       ? 'border border-transparent'
                                                       : 'border border-transparent'
                                             }`}
                                        >
                                             {/* Step icon */}
                                             <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 transition-all duration-300 ${
                                                  isComplete
                                                       ? 'bg-secondary/20 text-secondary'
                                                       : isCurrent
                                                       ? 'bg-primary/20 text-primary shadow-[0_0_12px_rgba(138,235,255,0.2)]'
                                                       : 'bg-surface-container text-on-surface-variant/40'
                                             }`}>
                                                  {isComplete ? (
                                                       <CheckCircle2 size={14} />
                                                  ) : (
                                                       <Icon size={14} className={isCurrent ? 'animate-pulse' : ''} />
                                                  )}
                                             </div>

                                             {/* Step label */}
                                             <span className={`text-xs font-medium transition-colors duration-300 ${
                                                  isComplete
                                                       ? 'text-secondary/80 line-through decoration-secondary/30'
                                                       : isCurrent
                                                       ? 'text-on-surface font-semibold'
                                                       : 'text-on-surface-variant/40'
                                             }`}>
                                                  {s.label}
                                             </span>

                                             {/* Current step spinner */}
                                             {isCurrent && (
                                                  <motion.div
                                                       initial={{ opacity: 0, scale: 0 }}
                                                       animate={{ opacity: 1, scale: 1 }}
                                                       className="ml-auto"
                                                  >
                                                       <div className="w-4 h-4 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
                                                  </motion.div>
                                             )}
                                        </motion.div>
                                   );
                              })}
                         </AnimatePresence>
                    </div>
               </motion.div>
          </div>
     );
}
