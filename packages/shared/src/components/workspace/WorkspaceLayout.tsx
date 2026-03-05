'use client';

import React, { useState } from 'react';
import { Group, Panel, Separator } from 'react-resizable-panels';

interface WorkspaceLayoutLabels {
  toggleSidebar?: string;
  toggleRightPanel?: string;
  onlineText?: string;
}

interface WorkspaceLayoutProps {
  sidebar?: React.ReactNode;
  main: React.ReactNode;
  rightPanel?: React.ReactNode;
  toolbar?: React.ReactNode;
  statusBar?: React.ReactNode;
  projectName?: string;
  stageTabs?: React.ReactNode;
  onlineCount?: number;
  labels?: WorkspaceLayoutLabels;
  headerExtra?: React.ReactNode;
}

export function WorkspaceLayout({
  sidebar,
  main,
  rightPanel,
  toolbar,
  statusBar,
  projectName = 'Untitled',
  stageTabs,
  onlineCount = 0,
  labels,
  headerExtra,
}: WorkspaceLayoutProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [rightPanelCollapsed, setRightPanelCollapsed] = useState(false);

  return (
    <div className="flex h-screen flex-col bg-bg-0 text-white">
      {/* Top navigation bar - Glass effect */}
      <header className="flex h-12 shrink-0 items-center gap-4 border-b border-white/[0.06] bg-bg-1/80 px-4 backdrop-blur-xl">
        <span className="text-lg font-semibold">NovelFlow</span>
        <span className="text-sm text-white/40">|</span>
        <span className="text-sm text-white/70">{projectName}</span>

        {stageTabs && (
          <div className="flex flex-1 items-center justify-center">
            {stageTabs}
          </div>
        )}

        <div className="ml-auto flex items-center gap-3">
          {onlineCount > 0 && (
            <span className="flex items-center gap-1 text-xs text-white/40">
              <span className="h-1.5 w-1.5 rounded-full bg-green-400" />
              {onlineCount} {labels?.onlineText ?? 'online'}
            </span>
          )}
          {headerExtra}
          <button
            type="button"
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="rounded p-1.5 text-white/40 transition-colors hover:bg-white/5 hover:text-white/70"
            aria-label={labels?.toggleSidebar ?? 'Toggle sidebar'}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <rect x="1" y="2" width="4" height="12" rx="1" stroke="currentColor" strokeWidth="1.5"/>
              <rect x="7" y="2" width="8" height="12" rx="1" stroke="currentColor" strokeWidth="1.5"/>
            </svg>
          </button>
          <button
            type="button"
            onClick={() => setRightPanelCollapsed(!rightPanelCollapsed)}
            className="rounded p-1.5 text-white/40 transition-colors hover:bg-white/5 hover:text-white/70"
            aria-label={labels?.toggleRightPanel ?? 'Toggle right panel'}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <rect x="1" y="2" width="8" height="12" rx="1" stroke="currentColor" strokeWidth="1.5"/>
              <rect x="11" y="2" width="4" height="12" rx="1" stroke="currentColor" strokeWidth="1.5"/>
            </svg>
          </button>
        </div>
      </header>

      {/* Main content area with resizable panels */}
      <div className="flex-1 overflow-hidden">
        <Group orientation="horizontal" id="workspace-layout">
          {/* Left sidebar */}
          {sidebar && !sidebarCollapsed && (
            <>
              <Panel
                id="sidebar"
                defaultSize={18}
                minSize={12}
                maxSize={25}
              >
                <div className="h-full overflow-y-auto border-r border-white/[0.06] bg-bg-1/50 backdrop-blur-xl">
                  {sidebar}
                </div>
              </Panel>
              <Separator className="w-px bg-white/[0.06] transition-colors hover:bg-indigo-500/50 active:bg-indigo-500" />
            </>
          )}

          {/* Main editor area */}
          <Panel id="main-editor" defaultSize={60} minSize={40}>
            <div className="flex h-full flex-col">
              {/* Toolbar */}
              {toolbar && (
                <div className="shrink-0 border-b border-white/[0.06] bg-bg-1/60 px-4 py-2 backdrop-blur-xl">
                  {toolbar}
                </div>
              )}
              {/* Editor content */}
              <div className="flex-1 overflow-auto">
                {main}
              </div>
            </div>
          </Panel>

          {/* Right panel */}
          {rightPanel && !rightPanelCollapsed && (
            <>
              <Separator className="w-px bg-white/[0.06] transition-colors hover:bg-indigo-500/50 active:bg-indigo-500" />
              <Panel
                id="right-panel"
                defaultSize={22}
                minSize={15}
                maxSize={35}
              >
                <div className="h-full overflow-y-auto border-l border-white/[0.06] bg-bg-1/50 backdrop-blur-xl">
                  {rightPanel}
                </div>
              </Panel>
            </>
          )}
        </Group>
      </div>

      {/* Status bar */}
      {statusBar && (
        <footer className="flex h-7 shrink-0 items-center border-t border-white/[0.06] bg-bg-1/60 px-4 text-xs text-white/30 backdrop-blur-xl">
          {statusBar}
        </footer>
      )}
    </div>
  );
}
