/** AI Provider types for multi-vendor configuration. */

export interface AIModelConfig {
  model_id: string;
  display_name: string;
  capability_tier: 'fast' | 'standard' | 'advanced';
  max_tokens: number;
  supports_streaming: boolean;
  supports_image: boolean;
}

export type ProviderType = 'anthropic' | 'gemini' | 'openai_compat';

export interface AIProvider {
  id: string;
  name: string;
  provider_type: ProviderType;
  base_url: string;
  api_key_masked: string;
  models: AIModelConfig[];
  is_default: boolean;
  enabled: boolean;
  priority: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface AIProviderCreateInput {
  name: string;
  provider_type: ProviderType;
  base_url: string;
  api_key: string;
  models: AIModelConfig[];
  is_default: boolean;
  enabled: boolean;
  priority: number;
}

export interface AIProviderUpdateInput {
  name?: string;
  provider_type?: ProviderType;
  base_url?: string;
  api_key?: string;
  models?: AIModelConfig[];
  is_default?: boolean;
  enabled?: boolean;
  priority?: number;
}

export interface TestResult {
  success: boolean;
  message: string;
}

export interface AvailableModelInfo {
  provider_id: string;
  provider_name: string;
  provider_type: ProviderType;
  model_id: string;
  display_name: string;
  max_tokens: number;
  supports_streaming: boolean;
  supports_image: boolean;
}

export interface AvailableModelsByTier {
  fast: AvailableModelInfo[];
  standard: AvailableModelInfo[];
  advanced: AvailableModelInfo[];
}

export const PROVIDER_TYPE_LABELS: Record<ProviderType, string> = {
  anthropic: 'Anthropic',
  gemini: 'Gemini',
  openai_compat: 'OpenAI Compatible',
};

export const CAPABILITY_TIER_LABELS: Record<string, string> = {
  fast: 'Fast',
  standard: 'Standard',
  advanced: 'Advanced',
};

export const DEFAULT_BASE_URLS: Record<ProviderType, string> = {
  anthropic: 'https://api.anthropic.com',
  gemini: 'https://generativelanguage.googleapis.com',
  openai_compat: '',
};
