import React, { useState, useEffect, useCallback } from 'react';
import { useConsultationStore } from '../store/consultationStore';
import { parsePrompt, generateBlueprint, generateBlueprintStream } from '../api/plotit';

// New Components
import DashboardLayout from '../components/layout/DashboardLayout';
import SplitScreenView from '../components/layout/SplitScreenView';
import ChatInterface from '../components/chat/ChatInterface';
import InteractiveCanvas from '../components/blueprint/InteractiveCanvas';

// Legacy/Modal Components
import ConsultationModal from '../components/ConsultationModal';
import ResumeConsultationPrompt from '../components/ConsultationModal/ResumeConsultationPrompt';
import ErrorBoundary from '../components/ErrorBoundary';
import { Layers, History, Bot, FolderOpen, Plus, Settings, Bell, User } from 'lucide-react';

export default function Home() {
     // State
     const [chatHistory, setChatHistory] = useState([]);
     const [isLoading, setIsLoading] = useState(false);
     const [isGenerating, setIsGenerating] = useState(false);
     const [generationProgress, setGenerationProgress] = useState({ progress: 0, stage: '' });
     const [blueprintData, setBlueprintData] = useState(null);
     const [activeFloor, setActiveFloor] = useState("1"); // Default to Floor 1 (string key)
     const [pendingDraft, setPendingDraft] = useState(null);
     const [consultationData, setConsultationData] = useState(null);

     // Store — only pull what we actually need; avoid reading `recommendation` in render scope
     const {
          startConsultation,
          restoreDraft,
          resetConsultation,
          answerQuestion,
          plotData,
          isConsultationActive,
          setConsultationActive
     } = useConsultationStore();

     // Ref to hold the parsed plotData from the initial prompt (before consultation)
     const parsedPlotDataRef = React.useRef(null);
     const activeStreamRef = React.useRef(null);

     // Effects: Check for saved drafts on mount
     useEffect(() => {
          const draft = restoreDraft();
          if (draft) setPendingDraft(draft);
          return () => {
               if (activeStreamRef.current) {
                    activeStreamRef.current();
               }
          };
     }, []); // eslint-disable-line react-hooks/exhaustive-deps

     // ─── Core generation handler ────────────────────────────────────────
     // Accepts rooms and plotInfo explicitly — no store closures
     const handleGenerationResponse = useCallback(async (rooms, plotInfo, recommendationPlotSize) => {
          setChatHistory(prev => [...prev, { role: 'system', content: "Generating blueprint..." }]);

          setIsGenerating(true);
          setGenerationProgress({ progress: 0, stage: 'parsing' });

           const plot_size = (recommendationPlotSize && recommendationPlotSize > 0)
                ? recommendationPlotSize
                : (plotInfo.plot_size_sqft || 1200);

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
           } catch (err) {
                console.warn("WebSocket streaming failed, attempting REST fallback...", err);
                // Reset progress so the user doesn't see a stale percentage
                setGenerationProgress({ progress: 0, stage: 'fallback' });
                setChatHistory(prev => [...prev, { role: 'system', content: "Streaming timed out — falling back to standard generation..." }]);
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
                } catch (fallbackErr) {
                     console.error("Critical: REST fallback failed too:", fallbackErr);
                     setChatHistory(prev => [...prev, { role: 'error', content: `Critical: ${fallbackErr.message || 'Server error'}` }]);
                }
           } finally {
                activeStreamRef.current = null;
                setIsGenerating(false);
           }
     }, [chatHistory]);

     // ─── Chat send handler ─────────────────────────────────────────────
     const handleSend = async (message) => {
          setChatHistory(prev => [...prev, { role: 'user', content: message }]);
          setIsLoading(true);

          try {
               const result = await parsePrompt(message);

               // Track if dimensions were explicitly parsed from prompt
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
               } else {
                    // Direct generation — no consultation needed
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
          } finally {
               setIsLoading(false);
          }
     };

     // ─── Called by ConsultationModal when user clicks "Generate Blueprint" ──
     const handleConsultationGenerate = useCallback((recommendation) => {
          const finishConsultation = async (reco) => {
               setConsultationActive(false);
               setIsGenerating(true);
               
               // HYDRATION: Ensure we have all necessary metadata for the blueprint generator
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

     const handleReset = () => {
          if (activeStreamRef.current) {
               activeStreamRef.current();
          }
          setBlueprintData(null);
          setChatHistory([]);
          setActiveFloor("0");
          resetConsultation();
          parsedPlotDataRef.current = null;
     };

     // Render
     return (
          <>
               <DashboardLayout
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
                              {/* Top App Bar (Overlapping Canvas) */}
                              <header className="absolute top-0 right-0 left-0 h-16 z-40 flex justify-between items-center px-8 bg-surface-container/85 backdrop-blur-md border-b border-outline-variant/30 shadow-sm pointer-events-none">
                                   {/* Left Side: Nav Links */}
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
                                   {/* Right Side: Actions */}
                                   <div className="flex items-center gap-4 pointer-events-auto">
                                        <button className="text-label-caps text-on-surface-variant uppercase px-3 py-1.5 border border-outline-variant rounded hover:bg-surface-variant transition-colors">Share</button>
                                        <button className="text-label-caps bg-primary text-on-primary uppercase px-4 py-1.5 rounded font-bold shadow-[0_0_10px_rgba(138,235,255,0.3)] hover:bg-primary-fixed transition-colors">Export DWG</button>
                                        <div className="flex gap-4 border-l border-outline-variant/30 pl-4 ml-2">
                                             <button className="text-on-surface-variant hover:text-primary transition-colors flex items-center">
                                                  <Bell size={18} />
                                             </button>
                                             <button className="text-on-surface-variant hover:text-primary transition-colors flex items-center">
                                                  <User size={18} />
                                             </button>
                                        </div>
                                   </div>
                              </header>
                              <SplitScreenView
                                   hasBlueprint={!!blueprintData}
                                   isGenerating={isGenerating}
                                   chat={
                                        <ChatInterface
                                             history={chatHistory}
                                             onSend={handleSend}
                                             isLoading={isLoading}
                                             isGenerating={isGenerating}
                                             generationProgress={generationProgress}
                                             pendingDraft={pendingDraft}
                                             onConsultationGenerate={handleConsultationGenerate}
                                        />
                                   }
                                   canvas={
                                        <ErrorBoundary>
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
                                                  isGenerating={isGenerating}
                                                  generationProgress={generationProgress}
                                                  blueprintScore={blueprintData?.blueprint_score}
                                             />
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
