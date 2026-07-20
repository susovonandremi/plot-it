import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Menu, X } from 'lucide-react';

/**
 * DashboardLayout — The chrome shell wrapping the entire app.
 *
 * Accepts a `visible` prop so Home.jsx can hide the entire dashboard
 * during the idle/hero state and reveal it with a smooth entrance
 * during workspace states. The sidebar uses Framer Motion layout
 * for seamless width transitions.
 */
export default function DashboardLayout({ sidebar, main, visible = true }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <AnimatePresence mode="wait">
      {visible && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          className="h-screen w-screen bg-surface text-on-surface font-body-sm overflow-hidden flex antialiased relative"
        >
          {/* Mobile Menu Toggle Button */}
          <button 
            onClick={() => setIsOpen(!isOpen)}
            className="md:hidden absolute top-4 left-4 z-50 p-2 rounded bg-surface-container-high border border-outline-variant text-on-surface transition-colors cursor-pointer"
            aria-label="Toggle navigation menu"
          >
            {isOpen ? <X size={20} /> : <Menu size={20} />}
          </button>

          {/* Global Navigation Shell - Sidebar */}
          <motion.aside
            layout
            className={`fixed md:relative inset-y-0 left-0 w-[280px] h-full flex flex-col bg-surface-container border-r border-outline-variant z-40 shrink-0 transition-transform duration-300 transform ${isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}
          >
            <div className="md:hidden h-14 shrink-0" />
            {sidebar}
          </motion.aside>

          {/* Overlay for mobile sidebar */}
          <AnimatePresence>
            {isOpen && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onClick={() => setIsOpen(false)}
                className="fixed inset-0 bg-black/50 z-30 md:hidden"
              />
            )}
          </AnimatePresence>

          {/* Main Content Area (Fluid Right) */}
          <motion.main
            layout
            className="flex-1 flex flex-col relative h-full overflow-hidden bg-surface-container-lowest grid-bg grid-bg-dense"
          >
            {main}
          </motion.main>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
