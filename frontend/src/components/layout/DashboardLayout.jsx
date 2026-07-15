import React from 'react';

export default function DashboardLayout({ sidebar, main }) {
  return (
    <div className="h-screen w-screen bg-surface text-on-surface font-body-sm overflow-hidden flex antialiased">
      {/* Global Navigation Shell - Sidebar (Left 280px) */}
      <aside className="w-[280px] h-full flex flex-col bg-surface-container border-r border-outline-variant z-50 shrink-0">
        {sidebar}
      </aside>

      {/* Main Content Area (Fluid Right) */}
      <main className="flex-1 flex flex-col relative h-full overflow-hidden bg-surface-container-lowest grid-bg grid-bg-dense">
        {main}
      </main>
    </div>
  );
}
