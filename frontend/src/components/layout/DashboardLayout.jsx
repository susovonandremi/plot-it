import React, { useState } from 'react';
import { Menu, X } from 'lucide-react';

export default function DashboardLayout({ sidebar, main }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="h-screen w-screen bg-surface text-on-surface font-body-sm overflow-hidden flex antialiased relative">
      {/* Mobile Menu Toggle Button */}
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="md:hidden absolute top-4 left-4 z-50 p-2 rounded bg-surface-container-high border border-outline-variant text-on-surface transition-colors cursor-pointer"
        aria-label="Toggle navigation menu"
      >
        {isOpen ? <X size={20} /> : <Menu size={20} />}
      </button>

      {/* Global Navigation Shell - Sidebar */}
      <aside className={`fixed md:relative inset-y-0 left-0 w-[280px] h-full flex flex-col bg-surface-container border-r border-outline-variant z-40 shrink-0 transition-transform duration-300 transform ${isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}>
        <div className="md:hidden h-14 shrink-0" />
        {sidebar}
      </aside>

      {/* Overlay for mobile sidebar */}
      {isOpen && (
        <div 
          onClick={() => setIsOpen(false)}
          className="fixed inset-0 bg-black/50 z-30 md:hidden"
        />
      )}

      {/* Main Content Area (Fluid Right) */}
      <main className="flex-1 flex flex-col relative h-full overflow-hidden bg-surface-container-lowest grid-bg grid-bg-dense">
        {main}
      </main>
    </div>
  );
}
