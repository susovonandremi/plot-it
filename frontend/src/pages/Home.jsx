import React, { useState, useEffect, useCallback } from 'react';
import { useConsultationStore } from '../store/consultationStore';
import { parsePrompt, generateBlueprint, generateBlueprintStream } from '../api/plotai';

// New Components
import DashboardLayout from '../components/layout/DashboardLayout';
import SplitScreenView from '../components/layout/SplitScreenView';
import ChatInterface from '../components/chat/ChatInterface';
import InteractiveCanvas from '../components/blueprint/InteractiveCanvas';

// Legacy/Modal Components
import ConsultationModal from '../components/ConsultationModal';
import ResumeConsultationPrompt from '../components/ConsultationModal/ResumeConsultationPrompt';
import ErrorBoundary from '../components/ErrorBoundary';
import { Layers, History } from 'lucide-react';

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

     // Effects: Check for saved drafts on mount
     useEffect(() => {
          const draft = restoreDraft();
          if (draft) setPendingDraft(draft);
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
                const data = await generateBlueprintStream({
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
                
                setBlueprintData(data);
                const defaultFloor = (data.floor_svgs && data.floor_svgs["1"]) ? "1" : "0";
                setActiveFloor(defaultFloor);
                setChatHistory(prev => [...prev, { role: 'assistant', content: `Done! Here is your ${plot_size} sqft plan.` }]);
           } catch (err) {
                console.warn("WebSocket streaming failed, attempting REST fallback...", err);
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
                     setGenerationProgress({ progress: 100, stage: 'complete' });
                     setChatHistory(prev => [...prev, { role: 'assistant', content: `Done! (via REST) Here is your ${plot_size} sqft plan.` }]);
                } catch (fallbackErr) {
                     console.error("Critical: REST fallback failed too:", fallbackErr);
                     setChatHistory(prev => [...prev, { role: 'error', content: `Generation failed: ${fallbackErr.message || 'Server error'}` }]);
                }
           } finally {
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
               setChatHistory(prev => [...prev, { role: 'error', content: "Sorry, I couldn't process that. Please try again." }]);
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
          setBlueprintData(null);
          setChatHistory([]);
          resetConsultation();
          parsedPlotDataRef.current = null;
     };

     // Render
     return (
          <>
               <DashboardLayout
                    sidebar={
                         <div className="flex flex-col h-full">
                              <div className="p-4 border-b border-neutral-800">
                                   <h2 className="text-neutral-400 text-xs font-bold uppercase tracking-wider mb-2">Projects</h2>
                                   <button onClick={handleReset} className="w-full text-left text-sm text-neutral-300 hover:bg-neutral-800 p-2 rounded flex items-center gap-2">
                                        <Layers size={14} /> New Project
                                   </button>
                                   <button onClick={() => alert("Project history feature coming soon!")} className="w-full text-left text-sm text-neutral-300 hover:bg-neutral-800 p-2 rounded flex items-center gap-2 mt-1">
                                        <History size={14} /> My Dream Home (Yesterday)
                                   </button>
                              </div>
                               <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
                                   {/* History list would go here */}
                              </div>
                              <div className="p-4 border-t border-neutral-800">
                                   <div className="text-xs text-neutral-600">PlotAI v3.0</div>
                              </div>
                         </div>
                    }
                    main={
                         <ErrorBoundary>
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
                                        />
                                   }
                                   canvas={
                                        <InteractiveCanvas
                                             blueprintSvg={blueprintData?.floor_svgs?.[activeFloor] || blueprintData?.svg}
                                             floorSvgs={blueprintData?.floor_svgs}
                                             floorLabels={blueprintData?.floor_labels}
                                             activeFloor={activeFloor}
                                             onFloorChange={setActiveFloor}
                                             isIsoMode={false}
                                             isGenerating={isGenerating}
                                             generationProgress={generationProgress}
                                        />
                                   }
                              />
                         </ErrorBoundary>
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
               <ConsultationModal onGenerate={handleConsultationGenerate} />
          </>
     );
}
