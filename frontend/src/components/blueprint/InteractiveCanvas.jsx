import React, { useState, useRef, useId } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { TransformWrapper, TransformComponent } from "react-zoom-pan-pinch";
import {
     ZoomIn, ZoomOut, RotateCcw, Layers, Download, Image as ImageIcon,
     FileText, Code, ChevronDown, Hammer, Ruler, Flame, CheckCircle, AlertTriangle,
     Bot, Loader2, Sparkles
} from 'lucide-react';
import DOMPurify from 'dompurify';
import { jsPDF } from 'jspdf';
import 'svg2pdf.js';
import BlueprintRenderer from './BlueprintRenderer';
import GenerationProgress from '../GenerationProgress';

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

/**
 * Shared button classes for glassmorphism micro-interactions.
 * All canvas controls use this for a cohesive premium feel.
 */
const glassButtonBase = "transition-all duration-200 hover:-translate-y-0.5 active:scale-95 focus-visible:ring-2 focus-visible:ring-primary/50 focus-visible:ring-offset-2 focus-visible:ring-offset-surface outline-none cursor-pointer";

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
     const [isExporting, setIsExporting] = useState(false);
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
          setIsExporting(true);
          const svgElement = svgContainerRef.current?.querySelector('svg');
          if (!svgElement) { setIsExporting(false); return; }

          try {
               const clonedSvg = svgElement.cloneNode(true);
               const { width, height } = getExportDimensions(blueprintSvg);
               clonedSvg.setAttribute('width', width);
               clonedSvg.setAttribute('height', height);

               const svgData = new XMLSerializer().serializeToString(clonedSvg);

               if (format === 'svg') {
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
                    try {
                         const pdf = new jsPDF({
                              orientation: width > height ? 'landscape' : 'portrait',
                              unit: 'px',
                              format: [width, height],
                         });
                         await pdf.svg(clonedSvg, { x: 0, y: 0, width, height });
                         pdf.save('plot-ai-blueprint.pdf');
                         return;
                    } catch (vectorErr) {
                         console.warn('svg2pdf.js vector export failed, falling back to high-DPI raster:', vectorErr);
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
          } finally {
               setIsExporting(false);
          }
     };

     // ─── EMPTY STATE ─────────────────────────────────────────────────
     if (!blueprintSvg && !isGenerating) {
          return (
               <div className="h-full w-full flex flex-col items-center justify-center text-on-surface-variant bg-transparent relative z-10">
                    {/* Architectural grid background */}
                    <div className="absolute inset-0 bg-[linear-gradient(rgba(138,235,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(138,235,255,0.03)_1px,transparent_1px)] bg-[size:40px_40px] [mask-image:radial-gradient(ellipse_60%_60%_at_50%_50%,#000_10%,transparent_100%)] pointer-events-none" />

                    <motion.div
                         initial={{ opacity: 0, y: 16 }}
                         animate={{ opacity: 1, y: 0 }}
                         transition={{ duration: 0.5, ease: 'easeOut' }}
                         className="relative flex flex-col items-center z-10"
                    >
                         {/* Premium geometric icon */}
                         <div className="w-20 h-20 mb-6 relative flex items-center justify-center">
                              <div className="absolute inset-0 border border-primary/15 rotate-45 rounded-xl" />
                              <div className="absolute inset-3 border border-primary/25 -rotate-12 rounded-lg opacity-60" />
                              <Layers size={32} className="text-primary/70 animate-float" />
                         </div>

                         <h3 className="text-xl font-bold text-on-surface mb-2 tracking-wide">No Blueprint Loaded</h3>
                         <p className="text-body-sm text-on-surface-variant max-w-sm text-center opacity-70 leading-relaxed">
                              Use the Copilot to generate a property layout, or start a new analysis from the sidebar.
                         </p>

                         {/* Hint chips */}
                         <div className="mt-8 flex flex-col items-center gap-2 max-w-md">
                              <span className="text-[10px] text-on-surface-variant/40 uppercase tracking-[0.15em] font-data-mono mb-1">Try asking the copilot</span>
                              <div className="flex flex-wrap justify-center gap-2">
                                   <span className="text-[11px] px-3 py-1.5 rounded-full border border-primary/15 text-primary/50 bg-primary/5">"3BHK 1200 sqft east-facing"</span>
                                   <span className="text-[11px] px-3 py-1.5 rounded-full border border-primary/15 text-primary/50 bg-primary/5">"Kerala courtyard villa"</span>
                              </div>
                         </div>
                    </motion.div>
               </div>
          );
     }

     // ─── GENERATING STATE ────────────────────────────────────────────
     if (!blueprintSvg && isGenerating) {
          return (
               <div className="h-full w-full flex items-center justify-center bg-transparent relative z-10">
                    <div className="absolute inset-0 bg-[linear-gradient(rgba(138,235,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(138,235,255,0.03)_1px,transparent_1px)] bg-[size:40px_40px] [mask-image:radial-gradient(ellipse_60%_60%_at_50%_50%,#000_10%,transparent_100%)] pointer-events-none" />
                    <GenerationProgress
                         progress={generationProgress?.progress || 0}
                         stage={generationProgress?.stage || 'parsing'}
                    />
               </div>
          );
     }

     // ─── ACTIVE STATE (Blueprint loaded) ─────────────────────────────
     return (
          <div className="h-full w-full relative overflow-hidden group">
               {/* ── Floating Layer Toolbar (Top Center) ──────────── */}
               <motion.div
                    initial={{ opacity: 0, y: -12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.4, delay: 0.2 }}
                    className="absolute top-20 left-1/2 -translate-x-1/2 glass-surface rounded-xl px-2 py-1.5 flex items-center gap-1 z-20 pointer-events-auto"
               >
                    <button
                         onClick={() => setShowStructure(!showStructure)}
                         className={`${glassButtonBase} px-2.5 py-1.5 rounded-lg text-label-caps flex items-center gap-1.5 ${
                              showStructure
                                   ? 'bg-primary/15 text-primary border border-primary/25 shadow-[0_0_8px_rgba(138,235,255,0.1)]'
                                   : 'text-on-surface-variant hover:bg-white/5 border border-transparent'
                         }`}
                    >
                         <Hammer size={14} />
                         Walls
                    </button>
                    <div className="w-px h-4 bg-outline-variant/30 mx-0.5" />
                    <button
                         onClick={() => setShowRooms(!showRooms)}
                         className={`${glassButtonBase} px-2.5 py-1.5 rounded-lg text-label-caps flex items-center gap-1.5 ${
                              showRooms
                                   ? 'bg-primary/15 text-primary border border-primary/25 shadow-[0_0_8px_rgba(138,235,255,0.1)]'
                                   : 'text-on-surface-variant hover:bg-white/5 border border-transparent'
                         }`}
                    >
                         Rooms
                    </button>
                    <button
                         onClick={() => setShowFurniture(!showFurniture)}
                         className={`${glassButtonBase} px-2.5 py-1.5 rounded-lg text-label-caps flex items-center gap-1.5 ${
                              showFurniture
                                   ? 'bg-primary/15 text-primary border border-primary/25 shadow-[0_0_8px_rgba(138,235,255,0.1)]'
                                   : 'text-on-surface-variant hover:bg-white/5 border border-transparent'
                         }`}
                    >
                         Furniture
                    </button>
                    <button
                         onClick={() => setShowDims(!showDims)}
                         className={`${glassButtonBase} px-2.5 py-1.5 rounded-lg text-label-caps flex items-center gap-1.5 ${
                              showDims
                                   ? 'bg-primary/15 text-primary border border-primary/25 shadow-[0_0_8px_rgba(138,235,255,0.1)]'
                                   : 'text-on-surface-variant hover:bg-white/5 border border-transparent'
                         }`}
                    >
                         <Ruler size={14} />
                         Dims
                    </button>
                    <div className="w-px h-4 bg-outline-variant/30 mx-0.5" />
                    <button
                         onClick={() => setShowVastu(!showVastu)}
                         className={`${glassButtonBase} px-2.5 py-1.5 rounded-lg text-label-caps flex items-center gap-1.5 ${
                              showVastu
                                   ? 'bg-secondary/15 text-secondary border border-secondary/25 shadow-[0_0_8px_rgba(69,223,164,0.1)]'
                                   : 'text-on-surface-variant hover:bg-white/5 border border-transparent'
                         }`}
                    >
                         <Flame size={14} />
                         Vastu Heat
                    </button>
               </motion.div>

               {/* ── Export Menu (Top Right) ───────────────────────── */}
               <motion.div
                    initial={{ opacity: 0, y: -12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.4, delay: 0.3 }}
                    className="absolute top-20 right-6 z-50 pointer-events-auto"
               >
                    <div className="relative">
                         <button
                              onClick={() => setShowDownloadMenu(!showDownloadMenu)}
                              disabled={isExporting}
                              className={`${glassButtonBase} flex items-center gap-2 glass-surface rounded-xl px-4 py-2.5 text-sm font-medium text-on-surface disabled:opacity-50 disabled:cursor-not-allowed`}
                         >
                              {isExporting ? (
                                   <><Loader2 size={16} className="animate-spin" /> Exporting...</>
                              ) : (
                                   <><Download size={16} /> Export</>
                              )}
                              <ChevronDown size={14} className={`transition-transform duration-200 ${showDownloadMenu ? 'rotate-180' : ''}`} />
                         </button>

                         <AnimatePresence>
                              {showDownloadMenu && (
                                   <motion.div
                                        initial={{ opacity: 0, y: -8, scale: 0.95 }}
                                        animate={{ opacity: 1, y: 0, scale: 1 }}
                                        exit={{ opacity: 0, y: -8, scale: 0.95 }}
                                        transition={{ duration: 0.15 }}
                                        className="absolute top-full right-0 mt-2 w-40 glass-surface rounded-xl overflow-hidden py-1.5 z-50 shadow-2xl bg-surface-container-high/95 backdrop-blur-xl"
                                   >
                                        <button onClick={() => handleDownload('png')} className={`${glassButtonBase} w-full text-left px-4 py-2.5 text-sm text-on-surface hover:bg-white/5 flex items-center gap-2.5`}>
                                             <ImageIcon size={14} className="text-primary" /> PNG Image
                                        </button>
                                        <button onClick={() => handleDownload('pdf')} className={`${glassButtonBase} w-full text-left px-4 py-2.5 text-sm text-on-surface hover:bg-white/5 flex items-center gap-2.5`}>
                                             <FileText size={14} className="text-error" /> PDF Document
                                        </button>
                                        <button onClick={() => handleDownload('svg')} className={`${glassButtonBase} w-full text-left px-4 py-2.5 text-sm text-on-surface hover:bg-white/5 flex items-center gap-2.5`}>
                                             <Code size={14} className="text-secondary" /> SVG Vector
                                        </button>
                                   </motion.div>
                              )}
                         </AnimatePresence>
                    </div>
               </motion.div>

               {/* ── Score Card (Top Right, below Export) ──────────── */}
               <AnimatePresence>
                    {blueprintScore && (
                         <motion.div
                              initial={{ opacity: 0, y: -16, scale: 0.95 }}
                              animate={{ opacity: 1, y: 0, scale: 1 }}
                              exit={{ opacity: 0, y: -16, scale: 0.95 }}
                              transition={{ duration: 0.4, delay: 0.4, ease: [0.22, 1, 0.36, 1] }}
                              className="absolute top-36 right-6 z-10 pointer-events-auto glass-surface rounded-xl p-4 w-64"
                         >
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
                                                  <motion.div
                                                       className="h-full bg-primary"
                                                       initial={{ width: 0 }}
                                                       animate={{ width: `${Math.round(val)}%` }}
                                                       transition={{ duration: 0.8, delay: 0.5, ease: 'easeOut' }}
                                                  />
                                             </div>
                                        </div>
                                   ))}
                              </div>
                         </motion.div>
                    )}
               </AnimatePresence>

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
                              {/* ── Zoom Toolbar (Left) ────────────────── */}
                              <motion.div
                                   initial={{ opacity: 0, x: -12 }}
                                   animate={{ opacity: 1, x: 0 }}
                                   transition={{ duration: 0.4, delay: 0.25 }}
                                   className="absolute top-20 left-6 z-20 flex flex-col glass-surface rounded-xl p-1.5 gap-1 pointer-events-auto"
                              >
                                   <button onClick={() => zoomIn()} className={`${glassButtonBase} p-2.5 hover:bg-white/8 rounded-lg text-on-surface-variant hover:text-primary`} title="Zoom In">
                                        <ZoomIn size={18} />
                                   </button>
                                   <button onClick={() => zoomOut()} className={`${glassButtonBase} p-2.5 hover:bg-white/8 rounded-lg text-on-surface-variant hover:text-primary`} title="Zoom Out">
                                        <ZoomOut size={18} />
                                   </button>
                                   <div className="w-full h-px bg-outline-variant/20 my-0.5" />
                                   <button onClick={() => resetTransform()} className={`${glassButtonBase} p-2.5 hover:bg-white/8 rounded-lg text-on-surface-variant hover:text-primary`} title="Reset View">
                                        <RotateCcw size={18} />
                                   </button>
                              </motion.div>

                              {/* ── Floor Selector (Bottom Left) ────────── */}
                              {floorSvgs && typeof floorSvgs === 'object' && Object.keys(floorSvgs).length > 1 && (
                                   <motion.div
                                        initial={{ opacity: 0, y: 16 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ duration: 0.4, delay: 0.35 }}
                                        className="absolute bottom-6 left-6 z-50 flex glass-surface rounded-xl p-1.5 pointer-events-auto items-center gap-1"
                                   >
                                        <div className="px-3 py-1 flex items-center gap-2 border-r border-outline-variant/20 mr-1">
                                             <Layers size={14} className="text-on-surface-variant" />
                                             <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest hidden sm:inline">Floors</span>
                                        </div>
                                        {Object.keys(floorSvgs).sort((a, b) => Number(a) - Number(b)).map((f) => (
                                             <button
                                                  key={f}
                                                  onClick={() => onFloorChange(f)}
                                                  className={`${glassButtonBase} px-3 py-1.5 rounded-lg text-xs font-bold ${activeFloor === f
                                                            ? 'bg-primary text-on-primary shadow-[0_0_12px_rgba(138,235,255,0.3)] scale-105'
                                                            : 'text-on-surface-variant hover:text-on-surface hover:bg-white/5'
                                                       }`}
                                             >
                                                  {(floorLabels?.[f] || `F${f}`).split(' ')[0]}
                                             </button>
                                        ))}
                                   </motion.div>
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
