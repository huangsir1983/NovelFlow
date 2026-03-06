'use client';

import React from 'react';

export interface WizardStep {
  id: string;
  label: string;
  description?: string;
}

interface StepNavProps {
  steps: WizardStep[];
  currentStep: number;
  onStepClick?: (index: number) => void;
}

export function StepNav({ steps, currentStep, onStepClick }: StepNavProps) {
  return (
    <nav className="flex items-center justify-center gap-2 py-4" aria-label="Progress">
      {steps.map((step, index) => {
        const isActive = index === currentStep;
        const isCompleted = index < currentStep;
        return (
          <React.Fragment key={step.id}>
            {index > 0 && (
              <div
                className={`h-px w-8 transition-colors ${
                  isCompleted ? 'bg-indigo-500' : 'bg-white/10'
                }`}
              />
            )}
            <button
              type="button"
              onClick={() => onStepClick?.(index)}
              disabled={!onStepClick || index > currentStep}
              className={`
                flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium
                transition-all duration-200
                ${isActive
                  ? 'bg-indigo-500/20 text-indigo-400 ring-1 ring-indigo-500/50'
                  : isCompleted
                    ? 'bg-green-500/10 text-green-400'
                    : 'text-white/40 hover:text-white/60'
                }
                disabled:cursor-default
              `}
              aria-current={isActive ? 'step' : undefined}
            >
              <span
                className={`
                  flex h-6 w-6 items-center justify-center rounded-full text-xs
                  ${isActive
                    ? 'bg-indigo-500 text-white'
                    : isCompleted
                      ? 'bg-green-500 text-white'
                      : 'bg-white/10 text-white/40'
                  }
                `}
              >
                {isCompleted ? '\u2713' : index + 1}
              </span>
              <span className="hidden sm:inline">{step.label}</span>
            </button>
          </React.Fragment>
        );
      })}
    </nav>
  );
}

interface WizardLayoutLabels {
  prev?: string;
  next?: string;
  stepOf?: string;
}

interface WizardLayoutProps {
  steps: WizardStep[];
  currentStep: number;
  onStepClick?: (index: number) => void;
  onNext?: () => void;
  onPrev?: () => void;
  canNext?: boolean;
  canPrev?: boolean;
  children: React.ReactNode;
  labels?: WizardLayoutLabels;
  headerExtra?: React.ReactNode;
}

export function WizardLayout({
  steps,
  currentStep,
  onStepClick,
  onNext,
  onPrev,
  canNext = true,
  canPrev = true,
  children,
  labels,
  headerExtra,
}: WizardLayoutProps) {
  return (
    <div className="flex min-h-screen flex-col bg-bg-0">
      {/* Top navigation bar */}
      <header className="sticky top-0 z-50 border-b border-white/[0.06] bg-bg-1/80 backdrop-blur-xl">
        <div className="flex h-12 items-center justify-between px-6">
          <span className="text-lg font-semibold text-white">虚幻造物</span>
          {headerExtra && <div className="flex items-center">{headerExtra}</div>}
        </div>
      </header>

      {/* Step navigation */}
      <div className="border-b border-white/[0.06] bg-bg-0">
        <div className="px-6">
          <StepNav steps={steps} currentStep={currentStep} onStepClick={onStepClick} />
        </div>
      </div>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="mx-auto max-w-3xl px-6 py-12">
          {children}
        </div>
      </main>

      {/* Bottom navigation */}
      <footer className="sticky bottom-0 border-t border-white/[0.06] bg-bg-1/80 backdrop-blur-xl">
        <div className="flex h-16 items-center justify-between px-6">
          <button
            type="button"
            onClick={onPrev}
            disabled={!canPrev}
            className="rounded-lg px-4 py-2 text-sm text-white/60 transition-colors hover:bg-white/5 hover:text-white disabled:invisible"
          >
            &larr; {labels?.prev ?? '上一步'}
          </button>
          <span className="text-xs text-white/30">
            {currentStep + 1} / {steps.length}
          </span>
          <button
            type="button"
            onClick={onNext}
            disabled={!canNext || currentStep === steps.length - 1}
            className="rounded-lg bg-gradient-to-r from-indigo-500 to-purple-500 px-6 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40"
          >
            {labels?.next ?? '下一步'} &rarr;
          </button>
        </div>
      </footer>
    </div>
  );
}
