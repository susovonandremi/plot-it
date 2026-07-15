import React, { useState } from 'react';

export default function SplitScreenView({ chat, canvas, hasBlueprint = false, isGenerating = false }) {
     const [activeTab, setActiveTab] = useState('chat'); // 'chat' | 'canvas'

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

               {/* AI Copilot Panel */}
               <aside className={`w-full md:w-[320px] h-full bg-surface border-r border-outline-variant flex flex-col z-30 shadow-[4px_0_24px_rgba(0,0,0,0.5)] shrink-0 ${hasBlueprint && activeTab !== 'chat' ? 'hidden md:flex' : 'flex'}`}>
                    {chat}
               </aside>

               {/* CAD Canvas Area */}
               <section className={`flex-1 relative overflow-hidden flex items-center justify-center ${hasBlueprint && activeTab !== 'canvas' ? 'hidden md:flex' : 'flex'}`}>
                    <div className="w-full h-full relative z-10">
                         {canvas}
                    </div>
               </section>
          </div>
     );
}
