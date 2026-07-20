import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useConsultationStore } from '../store/consultationStore';
import { parsePrompt, generateBlueprint, generateBlueprintStream, setAuthTokenGetter } from '../api/plotit';
import { UserButton, useAuth } from '@clerk/clerk-react';

// Components
import DashboardLayout from '../components/layout/DashboardLayout';
import SplitScreenView from '../components/layout/SplitScreenView';
import ChatInterface from '../components/chat/ChatInterface';
import InteractiveCanvas from '../components/blueprint/InteractiveCanvas';
import GenerationProgress from '../components/GenerationProgress';

// Modals
import ConsultationModal from '../components/ConsultationModal';
import ResumeConsultationPrompt from '../components/ConsultationModal/ResumeConsultationPrompt';
import ErrorBoundary from '../components/ErrorBoundary';
import { Layers, History, Bot, FolderOpen, Plus, Settings, Bell, Send, Home as HomeIcon, Compass } from 'lucide-react';

/**
 * ──────────────────────────────────────────────────────────────
 * UI STATE MACHINE
 * ──────────────────────────────────────────────────────────────
 *
 *  idle ──→ parsing ──→ consulting ──→ generating ──→ active
 *    │          │                            │           │
 *    │          └──→ generating ─────────────┘           │
 *    │          └──→ error ──────────────────────────→ idle
 *    └──────────────────────────────────────── reset ──┘
 *
 *  • idle:        Hero prompt, minimalist, Midjourney-style
 *  • parsing:     Prompt submitted, parsing with backend
 *  • consulting:  Consultation modal active
 *  • generating:  Blueprint being generated (shows GenerationProgress)
 *  • active:      Blueprint loaded, full workspace
 *  • error:       Recoverable error, shown inline
 * ──────────────────────────────────────────────────────────────
 */

export default function Home() {
     // ─── State Machine ──────────────────────────────────────────────
     const [uiState, setUiState] = useState('idle'); // 'idle' | 'parsing' | 'consulting' | 'generating' | 'active' | 'error'
     const [chatHistory, setChatHistory] = useState([]);
     const [generationProgress, setGenerationProgress] = useState({ progress: 0, stage: '' });
     const [blueprintData, setBlueprintData] = useState(null);
     const [activeFloor, setActiveFloor] = useState("1");
     const [pendingDraft, setPendingDraft] = useState(null);
     const [heroInput, setHeroInput] = useState('');
     const [errorMessage, setErrorMessage] = useState('');

     // Store
     const {
          startConsultation,
          restoreDraft,
          resetConsultation,
          answerQuestion,
          plotData,
          isConsultationActive,
          setConsultationActive
     } = useConsultationStore();

     const parsedPlotDataRef = React.useRef(null);
     const activeStreamRef = React.useRef(null);

     const { getToken } = useAuth();

     // Derived state flags for convenience
     const isWorkspaceVisible = useMemo(() =>
          ['parsing', 'consulting', 'generating', 'active', 'error'].includes(uiState),
     [uiState]);

     // Register token getter
     useEffect(() => {
          setAuthTokenGetter(getToken);
     }, [getToken]);

     // Check for saved drafts on mount
     useEffect(() => {
          const draft = restoreDraft();
          if (draft) setPendingDraft(draft);
          return () => {
               if (activeStreamRef.current) {
                    activeStreamRef.current();
               }
          };
     }, []); // eslint-disable-line react-hooks/exhaustive-deps

     // Sync consultation store → uiState
     useEffect(() => {
          if (isConsultationActive && uiState !== 'consulting') {
               setUiState('consulting');
          }
     }, [isConsultationActive]); // eslint-disable-line react-hooks/exhaustive-deps

     // ─── Core generation handler ────────────────────────────────────
     const handleGenerationResponse = useCallback(async (rooms, plotInfo, recommendationPlotSize) => {
          setChatHistory(prev => [...prev, { role: 'system', content: "Generating blueprint..." }]);

          setUiState('generating');
          setGenerationProgress({ progress: 0, stage: 'parsing' });

          const plot_size = (recommendationPlotSize && recommendationPlotSize > 0)
               ? recommendationPlotSize
               : (plotInfo.plot_size_sqft || 1200);

          let progressInterval = null;

          try {
               const stream = generateBlueprintStream({
                    plot_size_sqft: plot_size,
                    floors: plotInfo.floors || 1,
                    rooms: rooms,
                    user_tier: "free",
                    original_unit_system: plotInfo.original_unit_system,
                    prompt: plotInfo.prompt || chatHistory.filter(m => m.role === 'user').slice(-1)[0]?.content || "Generated via options"
               }, (eventName, data) => {
                    if (eventName === 'stage') {
                         setGenerationProgress({ progress: data.progress, stage: data.stage });
                    }
               });

               activeStreamRef.current = stream.abort;

               const data = await stream.promise;
               setBlueprintData(data);
               setGenerationProgress({ progress: 100, stage: 'complete' });
               const defaultFloor = (data.floor_plans && data.floor_plans["1"]) || (data.floor_svgs && data.floor_svgs["1"]) ? "1" : "0";
               setActiveFloor(defaultFloor);
               setChatHistory(prev => [...prev, { role: 'assistant', content: `Done! Here is your ${plot_size} sqft plan.` }]);
               setUiState('active');
          } catch (err) {
               console.warn("WebSocket streaming failed, attempting REST fallback...", err);
               setChatHistory(prev => [...prev, { role: 'system', content: "Streaming timed out — falling back to standard generation..." }]);

               setGenerationProgress({ progress: 5, stage: 'building_program' });
               let currentProgress = 5;
               progressInterval = setInterval(() => {
                    currentProgress += Math.floor(Math.random() * 6) + 3;
                    if (currentProgress > 95) currentProgress = 95;

                    let stage = 'solving';
                    if (currentProgress > 30 && currentProgress <= 65) {
                         stage = 'validating';
                    } else if (currentProgress > 65) {
                         stage = 'rendering';
                    }
                    setGenerationProgress({ progress: currentProgress, stage });
               }, 400);

               try {
                    const fallbackData = await generateBlueprint({
                         plot_size_sqft: plot_size,
                         floors: plotInfo.floors || 1,
                         rooms: rooms,
                         user_tier: "free",
                         original_unit_system: plotInfo.original_unit_system,
                         prompt: plotInfo.prompt || "Generated via REST Fallback"
                    });
                    setBlueprintData(fallbackData);
                    const defaultFloor = (fallbackData.floor_plans && fallbackData.floor_plans["1"]) || (fallbackData.floor_svgs && fallbackData.floor_svgs["1"]) ? "1" : "0";
                    setActiveFloor(defaultFloor);
                    setGenerationProgress({ progress: 100, stage: 'complete' });
                    setChatHistory(prev => [...prev, { role: 'assistant', content: `Done! (via REST) Here is your ${plot_size} sqft plan.` }]);
                    setUiState('active');
               } catch (fallbackErr) {
                    console.error("REST fallback failed:", fallbackErr);
                    const errorReason = fallbackErr?.message || fallbackErr?.detail || err?.message || 'Server error';
                    const cleanReason = (errorReason.includes("status code 500") || errorReason.includes("status code 400"))
                         ? (fallbackErr?.response?.data?.detail || "Plot too small for requested rooms.")
                         : errorReason;
                    setChatHistory(prev => [...prev, { role: 'error', content: cleanReason }]);
                    setErrorMessage(cleanReason);
                    setUiState('error');
               }
          } finally {
               if (progressInterval) {
                    clearInterval(progressInterval);
               }
               activeStreamRef.current = null;
          }
     }, [chatHistory]);

     // ─── Chat send handler ─────────────────────────────────────────
     const handleSend = async (message) => {
          setChatHistory(prev => [...prev, { role: 'user', content: message }]);
          setUiState('parsing');

          try {
               const result = await parsePrompt(message);

               const hasPromptDims = result.plot_width_ft && result.plot_depth_ft;
               const promptEntry = result.entry_direction || 'N';

               if (result.consultation?.needed) {
                    setChatHistory(prev => [...prev, { role: 'system', content: "I need a few more details to get this right. Opening consultation..." }]);

                    startConsultation(result.consultation.questions || [], {
                         ...result,
                         plot_width_ft: result.plot_width_ft,
                         plot_depth_ft: result.plot_depth_ft,
                         entry_direction: promptEntry
                    });
                    // uiState will be set to 'consulting' by the useEffect sync
               } else {
                    const directRequest = {
                         ...result,
                         rooms: result.rooms || [],
                         plot_size_sqft: result.plot_size_sqft,
                         prompt: message
                    };
                    await handleGenerationResponse(directRequest.rooms, directRequest, directRequest.plot_size_sqft);
               }
          } catch (err) {
               console.error(err);
               setChatHistory(prev => [
                    ...prev,
                    { role: 'error', content: "Sorry, I couldn't parse your requirements. If this continues, you can manually configure your plot and room details." }
               ]);
               setErrorMessage(err.message || 'Parse error');
               setUiState('error');
          }
     };

     // ─── Hero submit (idle-state prompt) ────────────────────────────
     const handleHeroSubmit = (e) => {
          if (e) e.preventDefault();
          const trimmed = heroInput.trim();
          if (!trimmed) return;
          setHeroInput('');
          handleSend(trimmed);
     };

     const handleHeroChipClick = (text) => {
          setHeroInput(text);
     };

     // ─── Consultation → Generate ────────────────────────────────────
     const handleConsultationGenerate = useCallback((recommendation) => {
          const finishConsultation = async (reco) => {
               setConsultationActive(false);
               setUiState('generating');

               const finalRequest = {
                    ...reco,
                    rooms: reco.recommended_rooms || [],
                    plot_size_sqft: reco.plot_size_sqft || plotData?.plot_size_sqft,
                    plot_width_ft: reco.plot_width_ft || plotData?.plot_width_ft,
                    plot_depth_ft: reco.plot_depth_ft || plotData?.plot_depth_ft,
                    entry_direction: reco.entry_direction || plotData?.entry_direction || 'N',
                    prompt: reco.summary || plotData?.prompt || "Consultation Recommendation"
               };

               await handleGenerationResponse(finalRequest.rooms, finalRequest, finalRequest.plot_size_sqft);
               resetConsultation();
          };

          finishConsultation(recommendation);
     }, [handleGenerationResponse, resetConsultation, plotData, setConsultationActive]);

     // ─── Reset ──────────────────────────────────────────────────────
     const handleReset = () => {
          if (activeStreamRef.current) {
               activeStreamRef.current();
          }
          setBlueprintData(null);
          setChatHistory([]);
          setActiveFloor("0");
          setHeroInput('');
          setErrorMessage('');
          resetConsultation();
          parsedPlotDataRef.current = null;
          setUiState('idle');
     };

     // ───────────────────────────────────────────────────────────────
     // RENDER
     // ───────────────────────────────────────────────────────────────
     return (
          <>
               {/* ═══════════════════════════════════════════════════
                    HERO STATE (idle) — Full-screen centered prompt
                  ═══════════════════════════════════════════════════ */}
               <AnimatePresence mode="wait">
                    {uiState === 'idle' && (
                         <motion.div
                              key="hero"
                              initial={{ opacity: 0 }}
                              animate={{ opacity: 1 }}
                              exit={{ opacity: 0, y: -40, scale: 0.97 }}
                              transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
                              className="h-screen w-screen bg-surface flex flex-col items-center justify-center relative overflow-hidden"
                         >
                              {/* Subtle grid background */}
                              <div className="absolute inset-0 grid-bg grid-bg-dense opacity-50" />

                              {/* Radial glow behind logo */}
                              <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-primary/[0.03] blur-3xl pointer-events-none" />

                              {/* Content */}
                              <div className="relative z-10 flex flex-col items-center w-full max-w-2xl px-6">
                                   {/* Logo */}
                                   <motion.div
                                        initial={{ opacity: 0, y: 20 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ duration: 0.6, delay: 0.1 }}
                                        className="flex items-center gap-4 mb-4"
                                   >
                                        <svg className="w-12 h-12 text-primary" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                                             <path d="M10 20H90M10 40H90M10 60H90M10 80H90M20 10V90M40 10V90M60 10V90M80 10V90" stroke="currentColor" strokeWidth="0.5" strokeOpacity="0.15" strokeDasharray="2 2" />
                                             <rect x="15" y="15" width="70" height="70" rx="2" stroke="currentColor" strokeWidth="1.5" strokeOpacity="0.4" />
                                             <path d="M15 10H85M15 8V12M85 8V12" stroke="#45dfa4" strokeWidth="1" />
                                             <path d="M90 15V85M88 15H92M88 85H92" stroke="#45dfa4" strokeWidth="1" />
                                             <path d="M15 50H50V85M50 50H85M65 15V50" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                                             <circle cx="50" cy="50" r="3" fill="#45dfa4" />
                                        </svg>
                                        <div className="flex flex-col">
                                             <span className="text-3xl font-black tracking-tight text-on-surface leading-none">
                                                  Plot<span className="text-primary font-mono font-medium">It</span>
                                             </span>
                                             <span className="text-[10px] font-data-mono text-on-surface-variant/60 uppercase tracking-[0.2em] mt-1">
                                                  AI Architecture Studio
                                             </span>
                                        </div>
                                   </motion.div>

                                   {/* Tagline */}
                                   <motion.p
                                        initial={{ opacity: 0, y: 12 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ duration: 0.5, delay: 0.25 }}
                                        className="text-on-surface-variant text-center text-sm mb-8 max-w-md"
                                   >
                                        Describe your dream home in plain English. Our AI architect will design it in seconds.
                                   </motion.p>

                                   {/* Prompt Input */}
                                   <motion.form
                                        initial={{ opacity: 0, y: 16 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ duration: 0.5, delay: 0.35 }}
                                        onSubmit={handleHeroSubmit}
                                        className="w-full relative group"
                                   >
                                        {/* Glow ring */}
                                        <div className="absolute -inset-1 bg-gradient-to-r from-primary/30 via-secondary/20 to-primary/30 rounded-2xl blur-md opacity-40 group-focus-within:opacity-70 transition-opacity duration-500 animate-pulse-glow" />

                                        <div className="relative glass-surface rounded-2xl flex items-end overflow-hidden">
                                             <textarea
                                                  value={heroInput}
                                                  onChange={(e) => setHeroInput(e.target.value)}
                                                  onKeyDown={(e) => {
                                                       if (e.key === 'Enter' && !e.shiftKey) {
                                                            e.preventDefault();
                                                            handleHeroSubmit(e);
                                                       }
                                                  }}
                                                  placeholder="Describe your floor plan... e.g., &quot;3BHK 1200 sqft east-facing Vastu compliant house&quot;"
                                                  className="w-full bg-transparent text-on-surface text-sm placeholder-on-surface-variant/40 border-none focus:ring-0 resize-none p-5 pr-16 max-h-36 outline-none font-body-sm"
                                                  rows={2}
                                             />
                                             <div className="absolute right-3 bottom-3">
                                                  <button
                                                       type="submit"
                                                       disabled={!heroInput.trim()}
                                                       className="w-10 h-10 rounded-xl bg-primary text-on-primary flex items-center justify-center hover:bg-primary-fixed transition-all duration-200 shadow-[0_0_20px_rgba(138,235,255,0.3)] hover:-translate-y-0.5 active:scale-95 disabled:opacity-30 disabled:cursor-not-allowed disabled:shadow-none disabled:translate-y-0 cursor-pointer"
                                                  >
                                                       <Send size={18} />
                                                  </button>
                                             </div>
                                        </div>
                                   </motion.form>

                                   {/* Suggestion chips */}
                                   <motion.div
                                        initial={{ opacity: 0, y: 12 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ duration: 0.5, delay: 0.5 }}
                                        className="flex flex-col items-center gap-3 mt-6 w-full"
                                   >
                                        <span className="text-[10px] text-on-surface-variant/40 uppercase tracking-[0.15em] font-data-mono">Quick start</span>
                                        <div className="flex flex-wrap justify-center gap-2">
                                             <button
                                                  onClick={() => handleHeroChipClick("Generate a 3BHK 1200 sqft east-facing house, strictly Vastu compliant.")}
                                                  className="group relative text-left bg-surface-container border border-outline-variant/30 rounded-xl px-4 py-2.5 hover:border-primary/40 transition-all duration-300 overflow-hidden cursor-pointer"
                                             >
                                                  <div className="absolute inset-0 bg-gradient-to-r from-primary/0 via-primary/5 to-primary/0 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-700" />
                                                  <div className="flex items-center gap-2.5 relative z-10">
                                                       <HomeIcon size={14} className="text-primary/60" />
                                                       <div className="flex flex-col">
                                                            <span className="text-xs font-semibold text-on-surface">3BHK Vastu Home</span>
                                                            <span className="text-[10px] text-on-surface-variant/50 font-mono">1200 SQFT · EAST</span>
                                                       </div>
                                                  </div>
                                             </button>
                                             <button
                                                  onClick={() => handleHeroChipClick("Create a Kerala-style 2000 sqft house featuring a central courtyard and verandah.")}
                                                  className="group relative text-left bg-surface-container border border-outline-variant/30 rounded-xl px-4 py-2.5 hover:border-primary/40 transition-all duration-300 overflow-hidden cursor-pointer"
                                             >
                                                  <div className="absolute inset-0 bg-gradient-to-r from-primary/0 via-primary/5 to-primary/0 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-700" />
                                                  <div className="flex items-center gap-2.5 relative z-10">
                                                       <Compass size={14} className="text-primary/60" />
                                                       <div className="flex flex-col">
                                                            <span className="text-xs font-semibold text-on-surface">Courtyard Villa</span>
                                                            <span className="text-[10px] text-on-surface-variant/50 font-mono">2000 SQFT · KERALA</span>
                                                       </div>
                                                  </div>
                                             </button>
                                        </div>
                                   </motion.div>

                                   {/* User button (top-right corner) */}
                                   <div className="fixed top-6 right-6 z-50">
                                        <UserButton afterSignOutUrl="/" />
                                   </div>
                              </div>
                         </motion.div>
                    )}
               </AnimatePresence>

               {/* ═══════════════════════════════════════════════════
                    WORKSPACE STATE — Dashboard with split view
                  ═══════════════════════════════════════════════════ */}
               <DashboardLayout
                    visible={isWorkspaceVisible}
                    sidebar={
                         <div className="flex flex-col h-full py-6">
                              {/* Brand Header */}
                              <div className="px-6 pb-6 flex items-center justify-between border-b border-outline-variant/30">
                                   <button onClick={handleReset} className="flex items-center gap-3 hover:opacity-80 transition-opacity text-left bg-transparent border-none p-0 outline-none cursor-pointer">
                                        <svg className="w-9 h-9 text-primary shrink-0" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                                             <path d="M10 20H90M10 40H90M10 60H90M10 80H90M20 10V90M40 10V90M60 10V90M80 10V90" stroke="currentColor" strokeWidth="0.5" strokeOpacity="0.15" strokeDasharray="2 2" />
                                             <rect x="15" y="15" width="70" height="70" rx="2" stroke="currentColor" strokeWidth="1.5" strokeOpacity="0.4" />
                                             <path d="M15 10H85M15 8V12M85 8V12" stroke="#45dfa4" strokeWidth="1" />
                                             <path d="M90 15V85M88 15H92M88 85H92" stroke="#45dfa4" strokeWidth="1" />
                                             <path d="M15 50H50V85M50 50H85M65 15V50" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                                             <circle cx="50" cy="50" r="3" fill="#45dfa4" />
                                        </svg>
                                        <div className="flex flex-col">
                                             <span className="text-headline-md font-black tracking-tight text-on-surface font-sans leading-none">Plot<span className="text-primary font-mono font-medium">It</span></span>
                                             <span className="text-[9px] font-data-mono text-on-surface-variant/60 uppercase tracking-widest mt-1">Property Intel</span>
                                        </div>
                                   </button>
                              </div>
                              {/* Navigation Links */}
                              <ul className="flex-1 overflow-y-auto px-4 py-6 space-y-1">
                                   <li>
                                        <button className="w-full flex items-center gap-3 px-3 py-2.5 rounded bg-surface-variant text-primary font-bold transition-transform duration-150 border-l-2 border-primary">
                                             <Bot size={18} className="text-primary" />
                                             <span className="text-body-sm">CAD Copilot</span>
                                        </button>
                                   </li>
                                   <li>
                                        <button onClick={handleReset} className="w-full flex items-center gap-3 px-3 py-2.5 rounded text-on-surface-variant hover:bg-surface-variant hover:text-on-surface transition-colors">
                                             <FolderOpen size={18} className="text-on-surface-variant group-hover:text-on-surface" />
                                             <span className="text-body-sm">New Project</span>
                                        </button>
                                   </li>
                              </ul>
                              {/* Bottom Actions */}
                              <div className="px-4 pt-4 border-t border-outline-variant/30 space-y-2">
                                   <button onClick={handleReset} className="w-full flex items-center justify-center gap-2 bg-primary text-on-primary font-data-mono py-2 rounded hover:bg-primary-fixed transition-colors shadow-[0_0_15px_rgba(138,235,255,0.2)]">
                                        <Plus size={16} />
                                        New Analysis
                                   </button>
                              </div>
                         </div>
                    }
                    main={
                         <>
                              {/* Top App Bar */}
                              <header className="absolute top-0 right-0 left-0 h-16 z-40 flex justify-between items-center px-8 glass-surface border-b border-outline-variant/20 pointer-events-none">
                                   {/* Left Side */}
                                   <div className="flex items-center gap-6 pointer-events-auto">
                                        <h2 className="text-body-lg font-bold text-primary border-r border-outline-variant/30 pr-6 uppercase tracking-wider font-mono drop-shadow-[0_0_8px_rgba(138,235,255,0.4)] ml-10 md:ml-0">PlotIt CAD Studio</h2>
                                        <nav className="flex gap-6">
                                             <button className="flex flex-col items-center cursor-pointer group pt-1 bg-transparent border-none outline-none">
                                                  <span className="text-primary text-body-sm font-semibold tracking-wide transition-colors">Viewer</span>
                                                  <div className="w-full h-0.5 bg-primary mt-1 shadow-[0_0_5px_rgba(138,235,255,0.6)]"></div>
                                             </button>
                                             <button className="flex flex-col items-center cursor-pointer group pt-1 bg-transparent border-none outline-none">
                                                  <span className="text-on-surface-variant text-body-sm font-medium tracking-wide group-hover:text-on-surface transition-colors">Compare</span>
                                                  <div className="w-0 h-0.5 bg-on-surface-variant mt-1 group-hover:w-full transition-all duration-300"></div>
                                             </button>
                                             <button className="flex flex-col items-center cursor-pointer group pt-1 bg-transparent border-none outline-none">
                                                  <span className="text-on-surface-variant text-body-sm font-medium tracking-wide group-hover:text-on-surface transition-colors">Vastu</span>
                                                  <div className="w-0 h-0.5 bg-on-surface-variant mt-1 group-hover:w-full transition-all duration-300"></div>
                                             </button>
                                        </nav>
                                   </div>
                                   {/* Right Side */}
                                   <div className="flex items-center gap-4 pointer-events-auto">
                                        <button className="text-label-caps text-on-surface-variant uppercase px-3 py-1.5 border border-outline-variant rounded hover:bg-surface-variant transition-colors">Share</button>
                                        <button className="text-label-caps bg-primary text-on-primary uppercase px-4 py-1.5 rounded font-bold shadow-[0_0_10px_rgba(138,235,255,0.3)] hover:bg-primary-fixed transition-colors">Export DWG</button>
                                        <div className="flex gap-4 border-l border-outline-variant/30 pl-4 ml-2 items-center">
                                             <button className="text-on-surface-variant hover:text-primary transition-colors flex items-center">
                                                  <Bell size={18} />
                                             </button>
                                             <UserButton afterSignOutUrl="/" />
                                        </div>
                                   </div>
                              </header>

                              <SplitScreenView
                                   hasBlueprint={!!blueprintData}
                                   isGenerating={uiState === 'generating'}
                                   chat={
                                        <ChatInterface
                                             history={chatHistory}
                                             onSend={handleSend}
                                             isLoading={uiState === 'parsing'}
                                             isGenerating={uiState === 'generating'}
                                             generationProgress={generationProgress}
                                             pendingDraft={pendingDraft}
                                             onConsultationGenerate={handleConsultationGenerate}
                                        />
                                   }
                                   canvas={
                                        <ErrorBoundary>
                                             {uiState === 'generating' && !blueprintData ? (
                                                  <div className="h-full w-full flex items-center justify-center bg-transparent relative z-10">
                                                       {/* Architectural grid behind loader */}
                                                       <div className="absolute inset-0 bg-[linear-gradient(rgba(138,235,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(138,235,255,0.03)_1px,transparent_1px)] bg-[size:40px_40px] [mask-image:radial-gradient(ellipse_60%_60%_at_50%_50%,#000_10%,transparent_100%)] pointer-events-none" />
                                                       <GenerationProgress
                                                            progress={generationProgress.progress}
                                                            stage={generationProgress.stage}
                                                       />
                                                  </div>
                                             ) : (
                                                  <InteractiveCanvas
                                                       blueprintSvg={
                                                            blueprintData?.floor_plans?.[activeFloor] ||
                                                            blueprintData?.floor_svgs?.[activeFloor] ||
                                                            blueprintData?.floor_plan ||
                                                            blueprintData?.svg
                                                       }
                                                       floorSvgs={blueprintData?.floor_plans || blueprintData?.floor_svgs}
                                                       floorLabels={blueprintData?.floor_labels}
                                                       activeFloor={activeFloor}
                                                       onFloorChange={setActiveFloor}
                                                       isIsoMode={false}
                                                       isGenerating={uiState === 'generating'}
                                                       generationProgress={generationProgress}
                                                       blueprintScore={blueprintData?.blueprint_score}
                                                  />
                                             )}
                                        </ErrorBoundary>
                                   }
                              />
                         </>
                    }
               />

               {/* Modals */}
               {pendingDraft && !isConsultationActive && (
                    <ResumeConsultationPrompt
                         draft={pendingDraft}
                         onResume={() => {
                              startConsultation(pendingDraft.questions, pendingDraft.plotData);
                              Object.entries(pendingDraft.answers || {}).forEach(([qId, val]) => {
                                   answerQuestion(qId, val);
                              });
                              setPendingDraft(null);
                         }}
                         onStartOver={() => { resetConsultation(); setPendingDraft(null); }}
                    />
               )}
          </>
     );
}
