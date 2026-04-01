'use client';

import { StageNavigation } from '@unrealmake/shared/components';
import type { StageRoute } from '@unrealmake/shared/hooks';
import { useRouter } from '@/i18n/navigation';
import { useParams } from 'next/navigation';

interface StageScaffoldProps {
  stage: StageRoute;
  title: string;
  description: string;
  checklist: string[];
}

function readProjectId(raw: unknown): string {
  if (typeof raw === 'string') {
    return raw;
  }
  if (Array.isArray(raw) && raw.length > 0 && typeof raw[0] === 'string') {
    return raw[0];
  }
  return '';
}

export function StageScaffold({ stage, title, description, checklist }: StageScaffoldProps) {
  const router = useRouter();
  const params = useParams();
  const projectId = readProjectId(params?.id);

  return (
    <div className="min-h-screen bg-bg-0 text-white">
      <header className="border-b border-white/10 px-6 py-4">
        <p className="text-xs uppercase tracking-wider text-white/40">Project {projectId || 'N/A'}</p>
        <h1 className="mt-1 text-2xl font-semibold">{title}</h1>
        <p className="mt-2 max-w-4xl text-sm text-white/60">{description}</p>
      </header>

      <div className="px-6 py-5">
        <StageNavigation
          projectId={projectId}
          activeStage={stage}
          onNavigate={(_, path) => router.push(path)}
        />
      </div>

      <main className="px-6 pb-10">
        <section className="rounded-xl border border-white/10 bg-bg-1/70 p-5">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-white/60">Current Delivery Scope</h2>
          <ol className="mt-4 space-y-2 text-sm text-white/70">
            {checklist.map((item, index) => (
              <li key={item} className="flex gap-2">
                <span className="text-white/40">{index + 1}.</span>
                <span>{item}</span>
              </li>
            ))}
          </ol>
        </section>
      </main>
    </div>
  );
}
