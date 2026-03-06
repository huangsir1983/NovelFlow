import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { Edition, FeatureConfig, FEATURE_FLAGS, EDITION_ORDER } from '../types/edition';

interface EditionState {
  edition: Edition;
  setEdition: (edition: Edition) => void;
  getFeatureConfig: () => FeatureConfig;
  hasFeature: (key: keyof FeatureConfig) => boolean;
  isEditionAtLeast: (minEdition: Edition) => boolean;
  isAgentAvailable: (agentName: string) => boolean;
}

export const useEdition = create<EditionState>()(
  persist(
    (set, get) => ({
      edition: Edition.NORMAL,

      setEdition: (edition: Edition) => set({ edition }),

      getFeatureConfig: () => {
        return FEATURE_FLAGS[get().edition];
      },

      hasFeature: (key: keyof FeatureConfig) => {
        const config = FEATURE_FLAGS[get().edition];
        const value = config[key];
        if (typeof value === 'boolean') return value;
        if (value === 'all') return true;
        if (Array.isArray(value)) return value.length > 0;
        if (typeof value === 'string') return value !== '';
        if (typeof value === 'number') return value !== 0;
        return !!value;
      },

      isEditionAtLeast: (minEdition: Edition) => {
        const currentIndex = EDITION_ORDER.indexOf(get().edition);
        const minIndex = EDITION_ORDER.indexOf(minEdition);
        return currentIndex >= minIndex;
      },

      isAgentAvailable: (agentName: string) => {
        const config = FEATURE_FLAGS[get().edition];
        return config.agents.includes(agentName);
      },
    }),
    {
      name: 'unrealmake-edition',
    },
  ),
);
