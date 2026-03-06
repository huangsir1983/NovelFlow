'use client';

import { create } from 'zustand';
import type {
  AIProvider,
  AIProviderCreateInput,
  AIProviderUpdateInput,
  AvailableModelsByTier,
  TestResult,
} from '../types/aiProvider';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface AIProviderStoreState {
  providers: AIProvider[];
  availableModels: AvailableModelsByTier | null;
  loading: boolean;
  error: string | null;

  fetchProviders: () => Promise<void>;
  createProvider: (input: AIProviderCreateInput) => Promise<AIProvider>;
  updateProvider: (id: string, input: AIProviderUpdateInput) => Promise<AIProvider>;
  deleteProvider: (id: string) => Promise<void>;
  testProvider: (id: string) => Promise<TestResult>;
  fetchAvailableModels: () => Promise<void>;
}

export const useAIProviderStore = create<AIProviderStoreState>((set, get) => ({
  providers: [],
  availableModels: null,
  loading: false,
  error: null,

  fetchProviders: async () => {
    set({ loading: true, error: null });
    try {
      const res = await fetch(`${API_BASE}/api/settings/ai-providers`);
      if (!res.ok) throw new Error('Failed to fetch providers');
      const data = await res.json();
      set({ providers: data.providers, loading: false });
    } catch (e: unknown) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  createProvider: async (input) => {
    const res = await fetch(`${API_BASE}/api/settings/ai-providers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    });
    if (!res.ok) throw new Error('Failed to create provider');
    const provider = await res.json();
    await get().fetchProviders();
    return provider;
  },

  updateProvider: async (id, input) => {
    const res = await fetch(`${API_BASE}/api/settings/ai-providers/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    });
    if (!res.ok) throw new Error('Failed to update provider');
    const provider = await res.json();
    await get().fetchProviders();
    return provider;
  },

  deleteProvider: async (id) => {
    const res = await fetch(`${API_BASE}/api/settings/ai-providers/${id}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error('Failed to delete provider');
    await get().fetchProviders();
  },

  testProvider: async (id) => {
    const res = await fetch(`${API_BASE}/api/settings/ai-providers/${id}/test`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Failed to test provider');
    return await res.json();
  },

  fetchAvailableModels: async () => {
    try {
      const res = await fetch(`${API_BASE}/api/settings/ai-providers/available-models`);
      if (!res.ok) throw new Error('Failed to fetch models');
      const data = await res.json();
      set({ availableModels: data.tiers });
    } catch (e: unknown) {
      console.error('Failed to fetch available models:', e);
    }
  },
}));
