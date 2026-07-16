import React, { useState, useRef, useId } from 'react';
import { TransformWrapper, TransformComponent } from "react-zoom-pan-pinch";
import {
     ZoomIn, ZoomOut, RotateCcw, Layers, Download, Image as ImageIcon,
     FileText, Code, ChevronDown, Hammer, Ruler, Flame, CheckCircle, AlertTriangle,
     Bot
} from 'lucide-react';
import DOMPurify from 'dompurify';
import { jsPDF } from 'jspdf';
import 'svg2pdf.js';
import BlueprintRenderer from './BlueprintRenderer';

// Strict SVG sanitization via DOMPurify — strips <script>, event handlers,
// javascript: URIs, foreignObject, and any non-SVG payloads.
const sanitizeSvg = (rawSvg) => {
     if (typeof rawSvg !== 'string') return '';
     return DOMPurify.sanitize(rawSvg, {
          USE_PROFILES: { svg: true, svgFilters: true },
          FORBID_TAGS: ['foreignObject'],
          FORBID_ATTR: ['href', 'xlink:href'],
     });
};

export default function InteractiveCanvas({
     blueprintSvg,
     floorSvgs,
     floorLabels,
     activeFloor,
     onFloorChange,
     isGenerating,
     generationProgress,
     blueprintScore
}) {
     const [showRooms, setShowRooms] = useState(true);
     const [showFurniture, setShowFurniture] = useState(true);
     const [showStructure, setShowStructure] = useState(true);
     const [showVastu, setShowVastu] = useState(true);
     const [showDims, setShowDims] = useState(true);

     const [showDownloadMenu, setShowDownloadMenu] = useState(false);
     const svgContainerRef = useRef(null);
     // Unique ID per instance — enables side-by-side Compare View without
     // DOM ID collisions or global CSS selector interference.
     const instanceId = useId();
     const wrapperId = `bp-wrap-${instanceId.replace(/:/g, '')}`;

     const axisLabels = {
          vastu: "Vastu Compliance",
          space_efficiency: "Space Efficiency",
          accessibility: "Accessibility",
          proportions: "Proportions",
          ventilation: "Ventilation Potential"
     };

     const isJsonSchema = typeof blueprintSvg === 'object' || (typeof blueprintSvg === 'string' && blueprintSvg.trim() && !blueprintSvg.trim().startsWith('<svg'));
     let parsedSchema = null;
     if (isJsonSchema) {
          try {
               parsedSchema = typeof blueprintSvg === 'object' ? blueprintSvg : JSON.parse(blueprintSvg);
          } catch (e) {
               console.error("Failed to parse floor plan JSON schema:", e);
          }
     }

     // Derive export dimensions from the live SVG element's viewBox attribute.
     // This ensures export dimensions always match the rendered canvas exactly,
     // regardless of coordinate system changes (SCALE, PADDING, etc.).
     const getExportDimensions = (_svgString, maxDim = 3600) => {
          // Strategy 1: Read viewBox from the live SVG DOM element
          const svgElement = svgContainerRef.current?.querySelector('svg');
          if (svgElement) {
               const vb = svgElement.getAttribute('viewBox');
               if (vb) {
                    const parts = vb.split(/[\s,]+/).map(Number);
                    if (parts.length === 4 && parts[2] > 0 && parts[3] > 0) {
                         const aspect = parts[2] / parts[3];
                         return aspect >= 1
                              ? { width: maxDim, height: Math.round(maxDim / aspect) }
                              : { width: Math.round(maxDim * aspect), height: maxDim };
                    }
               }
          }

          // Strategy 2: Derive from schema metadata (uses coordinateTransform constants)
          if (isJsonSchema && parsedSchema?.metadata) {
               const { plot_width_ft, plot_height_ft } = parsedSchema.metadata;
               // Mirror the computeViewBox formula from coordinateTransform.js
               // SCALE=30, PADDING=80, title block=120
               const w = plot_width_ft * 30.0 + 2 * 80.0;
               const h = plot_height_ft * 30.0 + 2 * 80.0 + 120.0;
               const aspect = w / h;
               return aspect >= 1
                    ? { width: maxDim, height: Math.round(maxDim / aspect) }
                    : { width: Math.round(maxDim * aspect), height: maxDim };
          }

          return { width: 2400, height: 2400 };
     };

     const handleDownload = async (format) => {
          setShowDownloadMenu(false);
          const svgElement = svgContainerRef.current?.querySelector('svg');
          if (!svgElement) return;

          try {
               const clonedSvg = svgElement.cloneNode(true);
               const { width, height } = getExportDimensions(blueprintSvg);
               clonedSvg.setAttribute('width', width);
               clonedSvg.setAttribute('height', height);

               const svgData = new XMLSerializer().serializeToString(clonedSvg);

               if (format === 'svg') {
                    // Embed font references directly in the SVG for portability
                    const fontStyle = document.createElementNS('http://www.w3.org/2000/svg', 'style');
                    fontStyle.textContent = `@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&family=Archivo:wght@700&display=swap');`;
                    const defsEl = clonedSvg.querySelector('defs') || clonedSvg.insertBefore(
                         document.createElementNS('http://www.w3.org/2000/svg', 'defs'), clonedSvg.firstChild
                    );
                    defsEl.appendChild(fontStyle);
                    const finalSvgData = new XMLSerializer().serializeToString(clonedSvg);
                    const blob = new Blob([finalSvgData], { type: 'image/svg+xml;charset=utf-8' });
                    const url = URL.createObjectURL(blob);
                    const link = document.createElement('a');
                    link.href = url;
                    link.download = 'plot-ai-blueprint.svg';
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                    URL.revokeObjectURL(url);
                    return;
               }

               if (format === 'pdf') {
                    // Vector PDF export via svg2pdf.js — retains infinite zoom clarity,
                    // selectable text, and proper vector paths. No rasterization.
                    try {
                         const pdf = new jsPDF({
                              orientation: width > height ? 'landscape' : 'portrait',
                              unit: 'px',
                              format: [width, height],
                         });
                         // svg2pdf.js augments jsPDF with a .svg() method
                         await pdf.svg(clonedSvg, { x: 0, y: 0, width, height });
                         pdf.save('plot-ai-blueprint.pdf');
                         return;
                    } catch (vectorErr) {
                         console.warn('svg2pdf.js vector export failed, falling back to high-DPI raster:', vectorErr);
                         // Fall through to raster fallback below
                    }
               }

               // Raster export path (PNG, or PDF fallback at 2x resolution)
               const scale = format === 'pdf' ? 2 : 1;
               const canvas = document.createElement('canvas');
               canvas.width = width * scale;
               canvas.height = height * scale;
               const ctx = canvas.getContext('2d');

               ctx.fillStyle = '#ffffff';
               ctx.fillRect(0, 0, canvas.width, canvas.height);

               const img = new window.Image();
               const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
               const url = URL.createObjectURL(svgBlob);

               img.onload = () => {
                    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                    URL.revokeObjectURL(url);

                    if (format === 'png') {
                         const link = document.createElement('a');
                         link.download = 'plot-ai-blueprint.png';
                         link.href = canvas.toDataURL('image/png');
                         document.body.appendChild(link);
                         link.click();
                         document.body.removeChild(link);
                    } else if (format === 'pdf') {
                         // Fallback: high-DPI PNG embedded in PDF
                         const pdf = new jsPDF({
                              orientation: width > height ? 'landscape' : 'portrait',
                              unit: 'px',
                              format: [width, height],
                         });
                         pdf.addImage(canvas.toDataURL('image/png'), 'PNG', 0, 0, width, height);
                         pdf.save('plot-ai-blueprint.pdf');
                    }
               };
               img.src = url;

          } catch (error) {
               console.error("Export failed:", error);
          }
     };

     if (!blueprintSvg && !isGenerating) {
          return (
               <div className="h-full w-full flex flex-col items-center justify-center text-on-surface-variant bg-transparent relative z-10">
                    {/* Architectural Grid Background for empty state */}
                    <div className="absolute inset-0 bg-[linear-gradient(rgba(138,235,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(138,235,255,0.03)_1px,transparent_1px)] bg-[size:40px_40px] [mask-image:radial-gradient(ellipse_60%_60%_at_50%_50%,#000_10%,transparent_100%)] pointer-events-none"></div>

                    <div className="relative flex flex-col items-center z-10">
                         {/* Premium Icon / Graphic */}
                         <div className="w-24 h-24 mb-6 relative flex items-center justify-center">
                              <div className="absolute inset-0 border border-primary/20 rotate-45 rounded-xl shadow-[0_0_30px_rgba(138,235,255,0.1)]"></div>
                              <div className="absolute inset-2 border border-primary/40 -rotate-12 rounded-lg opacity-50"></div>
                              <span className="material-symbols-outlined text-5xl text-primary/80 drop-shadow-[0_0_10px_rgba(138,235,255,0.3)]" style={{ fontVariationSettings: "'FILL' 1" }}>
                                   Architecture
                              </span>
                         </div>

                         <h3 className="text-headline-md font-bold text-on-surface mb-2 font-mono tracking-wide">NO BLUEPRINT LOADED</h3>
                         <p className="text-body-sm text-on-surface-variant max-w-sm text-center opacity-80 leading-relaxed">
                              Use the CAD Copilot to generate a property layout, or upload an existing project to begin visualization.
                         </p>

                         {/* Decorative technical lines */}
                         <div className="mt-12 flex items-center gap-4 opacity-30">
                              <div className="h-px w-16 bg-gradient-to-r from-transparent to-primary"></div>
                              <div className="w-1.5 h-1.5 rounded-full bg-primary"></div>
                              <span className="text-label-caps tracking-[0.2em] text-primary">AWAITING INPUT</span>
                              <div className="w-1.5 h-1.5 rounded-full bg-primary"></div>
                              <div className="h-px w-16 bg-gradient-to-l from-transparent to-primary"></div>
                         </div>
                    </div>
               </div>
          );
     }

     if (!blueprintSvg && isGenerating) {
          const progressPercent = generationProgress?.progress || 0;
          const currentStage = generationProgress?.stage || 'parsing';
          const stageLabelMap = {
               'parsing': 'Parsing requirements & LLM design inference',
               'building_program': 'Building room layout configurations',
               'setbacks': 'Calculating property municipal setbacks',
               'solving': 'Optimizing rooms layout via CP-SAT solver',
               'validating': 'Checking vastu zone alignment rules',
               'rendering': 'Generating detailed architectural blueprint'
          };
          return (
               <div className="h-full w-full flex flex-col items-center justify-center text-primary bg-transparent relative z-10 p-6 animate-in fade-in duration-300">
                    <div className="w-96 h-64 border border-primary/30 rounded-xl flex flex-col items-center justify-center p-8 relative overflow-hidden bg-surface-container-high/80 backdrop-blur-md shadow-[0_0_30px_rgba(138,235,255,0.15)]">
                         <div className="absolute inset-0 bg-gradient-to-r from-transparent via-primary/5 to-transparent -translate-x-[100%] animate-[shimmer_2s_infinite]" />
                         <Bot size={48} className="text-primary mb-4 animate-bounce" />
                         <span className="text-sm font-bold text-on-surface tracking-wide mb-1">Architectural Solver Active</span>
                         <span className="text-[11px] text-on-surface-variant/80 font-light text-center mb-6 h-4">
                              {stageLabelMap[currentStage] || 'Processing layout request...'}
                         </span>
                         
                         {/* Dynamic Progress Bar */}
                         <div className="w-full h-1.5 bg-surface-variant/50 rounded-full overflow-hidden border border-outline-variant/30 relative mb-2">
                              <div 
                                   className="absolute top-0 left-0 h-full bg-primary shadow-[0_0_10px_rgba(138,235,255,0.5)] transition-all duration-300" 
                                   style={{ width: `${progressPercent}%` }}
                              />
                         </div>
                         <span className="text-[10px] font-data-mono text-primary font-bold">
                              {Math.round(progressPercent)}% Completed
                         </span>
                    </div>
               </div>
          );
     }

     return (
          <div className="h-full w-full relative overflow-hidden group">
               {/* Floating Toolbar (Top Center) */}
               <div className="absolute top-20 left-1/2 -translate-x-1/2 glass-panel rounded-lg px-2 py-1.5 flex items-center gap-1.5 z-20 pointer-events-auto shadow-lg">
                    <button onClick={() => setShowStructure(!showStructure)} className={`px-2.5 py-1 rounded text-label-caps transition-colors flex items-center gap-1.5 ${showStructure ? 'bg-primary/20 text-primary border border-primary/30' : 'text-on-surface-variant hover:bg-white/5 border border-transparent'}`}>
                         <Hammer size={14} />
                         Walls
                    </button>
                    <div className="w-px h-4 bg-outline-variant mx-1"></div>
                    <button onClick={() => setShowRooms(!showRooms)} className={`px-2.5 py-1 rounded text-label-caps transition-colors flex items-center gap-1.5 ${showRooms ? 'bg-primary/20 text-primary border border-primary/30' : 'text-on-surface-variant hover:bg-white/5 border border-transparent'}`}>
                         Rooms
                    </button>
                    <button onClick={() => setShowFurniture(!showFurniture)} className={`px-2.5 py-1 rounded text-label-caps transition-colors flex items-center gap-1.5 ${showFurniture ? 'bg-primary/20 text-primary border border-primary/30' : 'text-on-surface-variant hover:bg-white/5 border border-transparent'}`}>
                         Furniture
                    </button>
                    <button onClick={() => setShowDims(!showDims)} className={`px-2.5 py-1 rounded text-label-caps transition-colors flex items-center gap-1.5 ${showDims ? 'bg-primary/20 text-primary border border-primary/30' : 'text-on-surface-variant hover:bg-white/5 border border-transparent'}`}>
                         <Ruler size={14} />
                         Dims
                    </button>
                    <div className="w-px h-4 bg-outline-variant mx-1"></div>
                    <button onClick={() => setShowVastu(!showVastu)} className={`px-2.5 py-1 rounded text-label-caps transition-colors flex items-center gap-1.5 ${showVastu ? 'bg-secondary/20 text-secondary border border-secondary/30' : 'text-on-surface-variant hover:bg-white/5 border border-transparent'}`}>
                         <Flame size={14} />
                         Vastu Heat
                    </button>
               </div>

               {/* Download Menu (Top Right) */}
               <div className="absolute top-20 right-6 z-20 pointer-events-auto">
                    <div className="relative">
                         <button
                              onClick={() => setShowDownloadMenu(!showDownloadMenu)}
                              className="flex items-center gap-2 bg-glass backdrop-blur-md border border-white/10 rounded px-3 py-2 text-sm font-medium text-on-surface hover:bg-white/10 transition-colors shadow-lg"
                         >
                              <Download size={16} />
                              Export
                              <ChevronDown size={14} className={`transition-transform duration-200 ${showDownloadMenu ? 'rotate-180' : ''}`} />
                         </button>

                         {showDownloadMenu && (
                              <div className="absolute top-full right-0 mt-2 w-36 bg-surface-container border border-outline-variant rounded shadow-xl overflow-hidden py-1 z-50 animate-in fade-in slide-in-from-top-2">
                                   <button onClick={() => handleDownload('png')} className="w-full text-left px-4 py-2 text-sm text-on-surface hover:bg-surface-variant hover:text-primary flex items-center gap-2">
                                        <ImageIcon size={14} className="text-primary" /> PNG Image
                                   </button>
                                   <button onClick={() => handleDownload('pdf')} className="w-full text-left px-4 py-2 text-sm text-on-surface hover:bg-surface-variant hover:text-primary flex items-center gap-2">
                                        <FileText size={14} className="text-error" /> PDF Document
                                   </button>
                                   <button onClick={() => handleDownload('svg')} className="w-full text-left px-4 py-2 text-sm text-on-surface hover:bg-surface-variant hover:text-primary flex items-center gap-2">
                                        <Code size={14} className="text-secondary" /> SVG Vector
                                   </button>
                              </div>
                         )}
                    </div>
               </div>

               {/* Overall Grade Card (Top Right, floating below Export) */}
               {blueprintScore && (
                    <div className="absolute top-36 right-6 z-20 pointer-events-auto bg-surface-container/95 border border-outline-variant rounded-lg p-4 shadow-2xl w-64 backdrop-blur-md animate-in fade-in slide-in-from-top-4 duration-300">
                         <div className="flex justify-between items-start mb-4">
                              <div>
                                   <span className="text-[10px] font-data-mono text-on-surface-variant uppercase tracking-widest block mb-1">Overall Grade</span>
                                   <div className="flex items-baseline">
                                        <span className="text-3xl font-bold text-primary font-mono">{blueprintScore.grade}</span>
                                        <span className="text-xs text-secondary font-bold uppercase tracking-wider ml-2">{blueprintScore.label}</span>
                                   </div>
                              </div>
                              <span className="text-secondary">
                                   {blueprintScore.overall >= 70 ? (
                                        <CheckCircle size={24} className="text-secondary" />
                                   ) : (
                                        <AlertTriangle size={24} className="text-error" />
                                   )}
                              </span>
                         </div>
                         <div className="space-y-3">
                              {Object.entries(blueprintScore.axes || {}).map(([key, val]) => (
                                   <div key={key} className="space-y-1.5">
                                        <div className="flex justify-between text-[10px] font-data-mono text-on-surface-variant">
                                             <span>{axisLabels[key] || key.replace('_', ' ')}</span>
                                             <span className="text-primary font-bold">{Math.round(val)}</span>
                                        </div>
                                        <div className="h-1 bg-surface-container-low rounded-full overflow-hidden border border-outline-variant/10">
                                             <div
                                                  className="h-full bg-primary transition-all duration-500"
                                                  style={{ width: `${Math.round(val)}%` }}
                                             />
                                        </div>
                                   </div>
                              ))}
                         </div>
                    </div>
               )}

               <TransformWrapper
                    initialScale={0.85}
                    minScale={0.05}
                    maxScale={10}
                    centerOnInit={true}
                    limitToBounds={false}
                    wheel={{ step: 0.08 }}
                    onInit={(ref) => {
                         // Auto-fit to viewport on load using the unique wrapper ID
                         setTimeout(() => ref.zoomToElement(wrapperId, undefined, 200), 150);
                    }}
               >
                    {({ zoomIn, zoomOut, resetTransform }) => (
                         <>
                              {/* Zoom Toolbar */}
                              <div className="absolute top-20 left-6 z-20 flex flex-col bg-glass backdrop-blur-md border border-white/10 rounded p-1 gap-1 shadow-lg pointer-events-auto">
                                   <button onClick={() => zoomIn()} className="p-2 hover:bg-white/10 rounded text-on-surface-variant hover:text-primary transition-colors duration-200" title="Zoom In">
                                        <ZoomIn size={20} />
                                   </button>
                                   <button onClick={() => zoomOut()} className="p-2 hover:bg-white/10 rounded text-on-surface-variant hover:text-primary transition-colors duration-200" title="Zoom Out">
                                        <ZoomOut size={20} />
                                   </button>
                                   <button onClick={() => resetTransform()} className="p-2 hover:bg-white/10 rounded text-on-surface-variant hover:text-primary transition-colors duration-200" title="Reset View">
                                        <RotateCcw size={20} />
                                   </button>
                              </div>

                              {/* Floor Selector */}
                              {floorSvgs && typeof floorSvgs === 'object' && Object.keys(floorSvgs).length > 1 && (
                                   <div className="absolute bottom-6 left-6 z-50 flex bg-surface-container/90 backdrop-blur-2xl border border-outline-variant rounded-lg p-1.5 shadow-2xl pointer-events-auto items-center gap-1 animate-in slide-in-from-bottom-4 duration-500">
                                        <div className="px-3 py-1 flex items-center gap-2 border-r border-outline-variant mr-1">
                                             <Layers size={14} className="text-on-surface-variant" />
                                             <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest hidden sm:inline">Floors</span>
                                        </div>
                                        {Object.keys(floorSvgs).sort((a, b) => Number(a) - Number(b)).map((f) => (
                                             <button
                                                  key={f}
                                                  onClick={() => onFloorChange(f)}
                                                  className={`px-3 py-1.5 rounded text-xs font-bold transition-all duration-300 ${activeFloor === f
                                                            ? 'bg-primary text-on-primary shadow-[0_0_10px_rgba(138,235,255,0.3)] scale-105'
                                                            : 'text-on-surface-variant hover:text-on-surface hover:bg-white/5'
                                                       }`}
                                             >
                                                  {(floorLabels?.[f] || `F${f}`).split(' ')[0]}
                                             </button>
                                        ))}
                                   </div>
                              )}

                              <TransformComponent wrapperClass="!w-full !h-full" contentClass="!w-full !h-full flex items-center justify-center">
                                   <div
                                        id={wrapperId}
                                        ref={svgContainerRef}
                                        className="transition-opacity duration-500"
                                        style={{
                                             display: 'flex',
                                             alignItems: 'center',
                                             justifyContent: 'center',
                                             width: '100%',
                                             height: '100%',
                                             padding: '16px',
                                             overflow: 'visible',
                                        }}
                                   >
                                        {isJsonSchema && parsedSchema ? (
                                             <BlueprintRenderer
                                                  schema={parsedSchema}
                                                  layersVisibility={{
                                                       rooms: showRooms,
                                                       furniture: showFurniture,
                                                       structural: showStructure,
                                                       annotations: showVastu,
                                                       dimensions: showDims
                                                  }}
                                             />
                                        ) : (
                                             <div
                                                  className="w-full h-full flex items-center justify-center"
                                                  dangerouslySetInnerHTML={{ __html: sanitizeSvg(blueprintSvg) }}
                                             />
                                        )}
                                   </div>
                              </TransformComponent>
                         </>
                    )}
               </TransformWrapper>

               {/* Scoped CSS to ensure child SVG resizes responsively inside wrapper */}
               <style>{`
                    #${wrapperId} svg {
                         display: block;
                         width: 100% !important;
                         height: 100% !important;
                         max-width: 100%;
                         max-height: 100%;
                         margin: auto;
                    }
               `}</style>
          </div>
     );
}
