import React, { useState, useRef } from 'react';
import { TransformWrapper, TransformComponent } from "react-zoom-pan-pinch";
import { ZoomIn, ZoomOut, RotateCcw, Layers, Download, Image as ImageIcon, FileText, Code, ChevronDown } from 'lucide-react';
import { jsPDF } from 'jspdf';

export default function InteractiveCanvas({ 
    blueprintSvg, 
    floorSvgs, 
    floorLabels, 
    activeFloor, 
    onFloorChange,
    isGenerating, 
    generationProgress 
}) {
     const [showFurniture, setShowFurniture] = useState(true);
     const [showStructure, setShowStructure] = useState(true);
     const [showVastu, setShowVastu] = useState(true);
     const [showDims, setShowDims] = useState(true);
     
     const [showDownloadMenu, setShowDownloadMenu] = useState(false);
     const svgContainerRef = useRef(null);

     // Parse viewBox from the generated SVG to get the true aspect ratio
     const getExportDimensions = (svgString, maxDim = 3600) => {
          if (!svgString) return { width: 2400, height: 2400 };
          const vbMatch = svgString.match(/viewBox="([^"]+)"/);
          if (!vbMatch) return { width: 2400, height: 2400 };
          
          const vbValues = vbMatch[1].split(/[ ,]+/).map(Number);
          if (vbValues.length !== 4) return { width: 2400, height: 2400 };
          
          const [, , vbW, vbH] = vbValues;
          if (!vbW || !vbH) return { width: 2400, height: 2400 };
          
          const aspect = vbW / vbH;
          if (aspect >= 1) {
               return { width: maxDim, height: Math.round(maxDim / aspect) };
          } else {
               return { width: Math.round(maxDim * aspect), height: maxDim };
          }
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
                    const blob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
                    const url = URL.createObjectURL(blob);
                    const link = document.createElement('a');
                    link.href = url;
                    link.download = 'plot-ai-blueprint.svg';
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                    return;
               }

               const canvas = document.createElement('canvas');
               canvas.width = width;
               canvas.height = height;
               const ctx = canvas.getContext('2d');
               
               ctx.fillStyle = '#ffffff';
               ctx.fillRect(0, 0, width, height);
               
               const img = new window.Image();
               const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
               const url = URL.createObjectURL(svgBlob);
               
               img.onload = () => {
                   ctx.drawImage(img, 0, 0, width, height);
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
                           format: [width, height] 
                       });
                       pdf.addImage(canvas.toDataURL('image/jpeg', 0.95), 'JPEG', 0, 0, width, height);
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
               <div className="h-full w-full flex flex-col items-center justify-center text-white/50 bg-transparent relative z-10">
                    <div className="w-96 h-64 border-2 border-dashed border-white/10 rounded-xl flex items-center justify-center mb-4 opacity-50 backdrop-blur-sm">
                         <span className="text-4xl text-white/20 font-heading font-bold tracking-widest">CANVAS</span>
                    </div>
                    <p className="font-light tracking-wide">Generate a blueprint to see it here.</p>
               </div>
          );
     }

     if (!blueprintSvg && isGenerating) {
          return (
               <div className="h-full w-full flex flex-col items-center justify-center text-secondary bg-transparent relative z-10">
                    <div className="w-96 h-64 border-2 border-dashed border-accent/30 rounded-xl flex flex-col items-center justify-center mb-4 p-8 relative overflow-hidden bg-accent/5 backdrop-blur-md shadow-neon">
                         <div className="absolute inset-0 bg-gradient-to-r from-transparent via-accent/10 to-transparent -translate-x-[100%] animate-[shimmer_2s_infinite]" />
                         <Layers className="w-12 h-12 text-accent mb-4 animate-pulse" />
                         <span className="text-xl text-accent font-heading font-bold tracking-wide mb-2 drop-shadow-md">Generating Blueprint...</span>
                         <span className="text-sm text-secondary/70 font-light">{generationProgress?.stage ? generationProgress.stage.replace('_', ' ') : 'Processing'}</span>
                    </div>
               </div>
          );
     }

     return (
          <div className="h-full w-full relative overflow-hidden group">
               {/* Layer Controls & Download Toolbar */}
               <div className="absolute top-6 right-20 z-20 mr-2 pointer-events-auto flex gap-2">
                    <div className="flex bg-glass backdrop-blur-md border border-white/10 rounded-lg p-1 gap-1 shadow-lg">
                         <button onClick={() => setShowFurniture(!showFurniture)} className={`px-3 py-1.5 text-sm font-medium transition-colors rounded ${showFurniture ? 'bg-white/10 text-accent' : 'text-secondary/60 hover:text-secondary'}`}>Furniture</button>
                         <button onClick={() => setShowStructure(!showStructure)} className={`px-3 py-1.5 text-sm font-medium transition-colors rounded ${showStructure ? 'bg-white/10 text-purple-400' : 'text-secondary/60 hover:text-secondary'}`}>Structure</button>
                         <button onClick={() => setShowVastu(!showVastu)} className={`px-3 py-1.5 text-sm font-medium transition-colors rounded ${showVastu ? 'bg-white/10 text-orange-400' : 'text-secondary/60 hover:text-secondary'}`}>Vastu</button>
                         <button onClick={() => setShowDims(!showDims)} className={`px-3 py-1.5 text-sm font-medium transition-colors rounded ${showDims ? 'bg-white/10 text-emerald-400' : 'text-secondary/60 hover:text-secondary'}`}>Dimensions</button>
                    </div>

                    <div className="relative">
                         <button 
                              onClick={() => setShowDownloadMenu(!showDownloadMenu)} 
                              className="flex items-center gap-2 bg-glass backdrop-blur-md border border-white/10 rounded-lg px-3 py-2 text-sm font-medium text-secondary hover:text-white hover:bg-white/10 transition-colors shadow-lg"
                         >
                              <Download size={16} />
                              Export
                              <ChevronDown size={14} className={`transition-transform duration-200 ${showDownloadMenu ? 'rotate-180' : ''}`} />
                         </button>

                         {showDownloadMenu && (
                              <div className="absolute top-full right-0 mt-2 w-36 bg-[#0f172a] border border-white/10 rounded-lg shadow-xl overflow-hidden py-1 z-50 animate-in fade-in slide-in-from-top-2">
                                   <button onClick={() => handleDownload('png')} className="w-full text-left px-4 py-2 text-sm text-secondary hover:bg-white/10 hover:text-white flex items-center gap-2">
                                        <ImageIcon size={14} className="text-blue-400" /> PNG Image
                                   </button>
                                   <button onClick={() => handleDownload('pdf')} className="w-full text-left px-4 py-2 text-sm text-secondary hover:bg-white/10 hover:text-white flex items-center gap-2">
                                        <FileText size={14} className="text-red-400" /> PDF Document
                                   </button>
                                   <button onClick={() => handleDownload('svg')} className="w-full text-left px-4 py-2 text-sm text-secondary hover:bg-white/10 hover:text-white flex items-center gap-2">
                                        <Code size={14} className="text-emerald-400" /> SVG Vector
                                   </button>
                              </div>
                         )}
                    </div>
               </div>

               <TransformWrapper
                    initialScale={0.85}
                    minScale={0.05}
                    maxScale={10}
                    centerOnInit={true}
                    limitToBounds={false}
                    wheel={{ step: 0.08 }}
                    onInit={(ref) => {
                        // Auto-fit to viewport on load
                        setTimeout(() => ref.zoomToElement('blueprint-svg-wrapper', undefined, 200), 150);
                    }}
               >
                    {({ zoomIn, zoomOut, resetTransform }) => (
                         <>
                              {/* Zoom Toolbar */}
                              <div className="absolute top-6 right-6 z-20 flex flex-col bg-glass backdrop-blur-md border border-white/10 rounded-lg p-1 gap-1 shadow-lg pointer-events-auto">
                                   <button onClick={() => zoomIn()} className="p-2 hover:bg-white/10 rounded text-secondary/70 hover:text-accent transition-colors duration-200" title="Zoom In">
                                        <ZoomIn size={20} />
                                   </button>
                                   <button onClick={() => zoomOut()} className="p-2 hover:bg-white/10 rounded text-secondary/70 hover:text-accent transition-colors duration-200" title="Zoom Out">
                                        <ZoomOut size={20} />
                                   </button>
                                   <button onClick={() => resetTransform()} className="p-2 hover:bg-white/10 rounded text-secondary/70 hover:text-accent transition-colors duration-200" title="Reset View">
                                        <RotateCcw size={20} />
                                   </button>
                              </div>

                               {/* Floor Selector */}
                               {floorSvgs && typeof floorSvgs === 'object' && Object.keys(floorSvgs).length > 1 && (
                                    <div className="absolute bottom-6 left-6 z-50 flex bg-dominant/80 backdrop-blur-2xl border border-white/10 rounded-2xl p-1.5 shadow-2xl pointer-events-auto items-center gap-1 animate-in slide-in-from-bottom-4 duration-500">
                                         <div className="px-3 py-1 flex items-center gap-2 border-r border-white/10 mr-1">
                                              <Layers size={14} className="text-secondary/40" />
                                              <span className="text-[10px] font-bold text-secondary/40 uppercase tracking-widest hidden sm:inline">Floors</span>
                                         </div>
                                         {Object.keys(floorSvgs).sort((a,b) => Number(a) - Number(b)).map((f) => (
                                              <button
                                                   key={f}
                                                   onClick={() => onFloorChange(f)}
                                                   className={`px-4 py-2 rounded-xl text-xs font-bold transition-all duration-300 ${
                                                        activeFloor === f
                                                        ? 'bg-accent text-primary shadow-neon scale-105'
                                                        : 'text-secondary/60 hover:text-white hover:bg-white/5'
                                                   }`}
                                              >
                                                   {(floorLabels?.[f] || `F${f}`).split(' ')[0]}
                                              </button>
                                         ))}
                                    </div>
                               )}

                              <TransformComponent wrapperClass="!w-full !h-full" contentClass="!w-full !h-full flex items-center justify-center">
    <div
        id="blueprint-svg-wrapper"
        ref={svgContainerRef}
        className="transition-opacity duration-500"
        dangerouslySetInnerHTML={{ __html: blueprintSvg }}
        style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '100%',
            height: '100%',
            padding: '16px',
            overflow: 'visible',
        }}
    />
</TransformComponent>
</>
)}
</TransformWrapper>

{/* CSS Injection to control data-layer visibility and SVG responsiveness */}
<style>{`
#blueprint-svg-wrapper svg {
    display: block;
    width: 100% !important;
    height: 100% !important;
    max-width: 100%;
    max-height: 100%;
    margin: auto;
}

                    ${!showFurniture ? '#blueprint-svg-wrapper [data-layer="furniture"], #blueprint-svg-wrapper g[id*="furniture"], #blueprint-svg-wrapper path[class*="furniture"] { display: none !important; }' : ''}
                    ${!showStructure ? '#blueprint-svg-wrapper [data-layer="structural"] { display: none !important; }' : ''}
                    ${!showVastu ? '#blueprint-svg-wrapper [data-layer="vastu"] { display: none !important; }' : ''}
                    ${!showDims ? '#blueprint-svg-wrapper [data-layer="dimensions"] { display: none !important; }' : ''}
               `}</style>
          </div>
     );
}
