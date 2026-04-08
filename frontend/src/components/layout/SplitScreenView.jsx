import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export default function SplitScreenView({ chat, canvas, hasBlueprint = false, isGenerating = false }) {
     const isSplit = hasBlueprint || isGenerating;

     return (
          <div className="h-full w-full relative bg-dominant overflow-hidden flex">
               
               {/* Background Canvas Area (takes full screen behind) */}
               {!isSplit && (
                    <div className="absolute inset-0 z-0 flex items-center justify-center">
                         {/* Empty canvas state or subtle background for Architect.AI */}
                         <div className="absolute inset-0 bg-[linear-gradient(to_right,#ffffff05_1px,transparent_1px),linear-gradient(to_bottom,#ffffff05_1px,transparent_1px)] bg-[size:48px_48px]"></div>
                         <div className="absolute inset-0 bg-[radial-gradient(circle_800px_at_50%_50%,#00E5FF10,transparent)]"></div>
                    </div>
               )}

               {/* CHAT PANEL */}
               <motion.div 
                    layout
                    initial={false}
                    animate={{ 
                         width: isSplit ? '35%' : '100%',
                         borderRightWidth: isSplit ? 1 : 0
                    }}
                    transition={{ type: "spring", bounce: 0, duration: 0.6 }}
                    className="h-full z-20 flex flex-col border-white/5 bg-transparent lg:max-w-none max-w-full"
               >
                    <div className="w-full h-full p-4 md:p-8 flex items-end justify-center pointer-events-none">
                         {/* We pass pointer-events-none here and pointer-events-auto in ChatInterface */}
                         <div className="w-full h-full pointer-events-auto flex justify-center">
                              {chat}
                         </div>
                    </div>
               </motion.div>

               {/* CANVAS PANEL */}
               <AnimatePresence>
                    {isSplit && (
                         <motion.div 
                              layout
                              initial={{ opacity: 0, width: '0%' }}
                              animate={{ opacity: 1, width: '65%' }}
                              exit={{ opacity: 0, width: '0%' }}
                              transition={{ type: "spring", bounce: 0, duration: 0.6 }}
                              className="h-full z-10 relative overflow-hidden bg-dominant flex-shrink-0"
                         >
                              <div className="absolute inset-0 z-0 bg-[linear-gradient(to_right,#ffffff05_1px,transparent_1px),linear-gradient(to_bottom,#ffffff05_1px,transparent_1px)] bg-[size:24px_24px]"></div>
                              <div className="w-full h-full relative z-10">
                                   {canvas}
                              </div>
                         </motion.div>
                    )}
               </AnimatePresence>

          </div>
     );
}
