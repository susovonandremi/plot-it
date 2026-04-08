import React, { useState } from 'react';
import { Menu, X } from 'lucide-react';

export default function DashboardLayout({ sidebar, main }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="h-screen w-screen bg-dominant text-secondary overflow-hidden flex flex-col">

      {/* MAIN CONTENT — Full Screen */}
      <div className="flex-1 overflow-hidden relative">
        {main}

        {/* Top Navigation Bar with subtle gradient or just floating */}
        <div className="absolute top-4 left-4 z-30 flex items-center gap-4">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-2 bg-glass hover:bg-glass-hover text-secondary hover:text-accent backdrop-blur-md rounded-lg border border-white/5 transition-all shadow-sm hover:shadow-neon"
            title="Open sidebar"
          >
            <Menu size={20} />
          </button>
          <div className="text-lg font-heading tracking-wide text-secondary font-bold flex items-center gap-2">
            <span className="text-accent text-xl">/</span> Architect.AI
          </div>
        </div>
      </div>

      {/* SIDEBAR OVERLAY */}
      {sidebarOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40"
            onClick={() => setSidebarOpen(false)}
          />
          {/* Drawer */}
          <div className="fixed top-0 left-0 h-full w-72 bg-dominant border-r border-white/5 z-50 shadow-2xl animate-in slide-in-from-left duration-300 ease-in-out">
            <div className="flex items-center justify-between p-6 border-b border-white/5">
              <span className="text-lg font-heading tracking-wide text-secondary font-bold flex items-center gap-2">
                 <span className="text-accent text-xl">/</span> Architect.AI
              </span>
              <button
                onClick={() => setSidebarOpen(false)}
                className="p-2 bg-glass hover:bg-glass-hover hover:text-accent rounded-lg transition-all"
              >
                <X size={18} />
              </button>
            </div>
            <div className="h-full flex flex-col overflow-hidden">
              {sidebar}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
