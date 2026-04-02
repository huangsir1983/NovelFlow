'use client';

import { create } from 'zustand';
import type { ChainTemplate } from '../types/chainWorkflow';
import { fetchAPI } from '../lib/api';

interface ChainTemplateStoreState {
  templates: ChainTemplate[];
  loading: boolean;
  error: string | null;
  selectedTemplateId: string | null;
  editorOpen: boolean;
  editingTemplate: ChainTemplate | null;

  fetchTemplates: (projectId: string) => Promise<void>;
  createTemplate: (projectId: string, template: Omit<ChainTemplate, 'id' | 'isBuiltin' | 'version'>) => Promise<void>;
  updateTemplate: (templateId: string, patch: Partial<ChainTemplate>) => Promise<void>;
  deleteTemplate: (templateId: string) => Promise<void>;
  selectTemplate: (templateId: string | null) => void;
  openEditor: (template: ChainTemplate | null) => void;
  closeEditor: () => void;
}

export const useChainTemplateStore = create<ChainTemplateStoreState>((set, get) => ({
  templates: [],
  loading: false,
  error: null,
  selectedTemplateId: null,
  editorOpen: false,
  editingTemplate: null,

  fetchTemplates: async (projectId) => {
    set({ loading: true, error: null });
    try {
      const data = await fetchAPI<ChainTemplate[]>(
        `/api/projects/${projectId}/chain-templates`,
      );
      set({ templates: data, loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  createTemplate: async (projectId, template) => {
    set({ loading: true, error: null });
    try {
      const created = await fetchAPI<ChainTemplate>(
        `/api/projects/${projectId}/chain-templates`,
        {
          method: 'POST',
          body: JSON.stringify(template),
        },
      );
      set((s) => ({ templates: [...s.templates, created], loading: false, editorOpen: false }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  updateTemplate: async (templateId, patch) => {
    set({ loading: true, error: null });
    try {
      const updated = await fetchAPI<ChainTemplate>(
        `/api/chain-templates/${templateId}`,
        {
          method: 'PUT',
          body: JSON.stringify(patch),
        },
      );
      set((s) => ({
        templates: s.templates.map((t) => (t.id === templateId ? updated : t)),
        loading: false,
        editorOpen: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  deleteTemplate: async (templateId) => {
    set({ loading: true, error: null });
    try {
      await fetchAPI(`/api/chain-templates/${templateId}`, { method: 'DELETE' });
      set((s) => ({
        templates: s.templates.filter((t) => t.id !== templateId),
        loading: false,
        editorOpen: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  selectTemplate: (templateId) => set({ selectedTemplateId: templateId }),

  openEditor: (template) =>
    set({ editorOpen: true, editingTemplate: template ? { ...template } : null }),

  closeEditor: () => set({ editorOpen: false, editingTemplate: null }),
}));
