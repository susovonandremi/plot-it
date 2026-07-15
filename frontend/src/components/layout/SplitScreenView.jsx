import React from 'react';

export default function SplitScreenView({ chat, canvas, hasBlueprint = false, isGenerating = false }) {
     return (
          <div className="flex-1 flex min-h-0 w-full pt-16">
               {/* AI Copilot Panel (Left/Middle, Fixed Width: 320px) */}
               <aside className="w-[320px] h-full bg-surface border-r border-outline-variant flex flex-col z-30 shadow-[4px_0_24px_rgba(0,0,0,0.5)] shrink-0">
                    {chat}
               </aside>

               {/* CAD Canvas Area (Fluid Remaining) */}
               <section className="flex-1 relative overflow-hidden flex items-center justify-center">
                    <div className="w-full h-full relative z-10">
                         {canvas}
                    </div>
               </section>
          </div>
     );
}
