import { Edition, FEATURE_FLAGS, FeatureConfig, EDITION_ORDER } from '../types/edition';

let currentEdition: Edition = Edition.NORMAL;

/** Set the active edition */
export function setEdition(edition: Edition): void {
  currentEdition = edition;
}

/** Get the active edition */
export function getEdition(): Edition {
  return currentEdition;
}

/** Get the full feature config for the active edition */
export function getFeatureConfig(): FeatureConfig {
  return FEATURE_FLAGS[currentEdition];
}

/** Check if a specific feature is enabled */
export function hasFeature(key: keyof FeatureConfig): boolean {
  const config = getFeatureConfig();
  const value = config[key];
  if (typeof value === 'boolean') return value;
  if (value === 'all') return true;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === 'string') return value !== '';
  if (typeof value === 'number') return value !== 0;
  return !!value;
}

/** Check if current edition is at least the given level */
export function isEditionAtLeast(minEdition: Edition): boolean {
  const currentIndex = EDITION_ORDER.indexOf(currentEdition);
  const minIndex = EDITION_ORDER.indexOf(minEdition);
  return currentIndex >= minIndex;
}

/** Get feature config for a specific edition */
export function getEditionFeatures(edition: Edition): FeatureConfig {
  return FEATURE_FLAGS[edition];
}

/** Check if a specific agent is available in the current edition */
export function isAgentAvailable(agentName: string): boolean {
  const config = getFeatureConfig();
  return config.agents.includes(agentName);
}

/** Get the UI mode for the current edition */
export function getUIMode(): 'wizard' | 'workspace' {
  return getFeatureConfig().ui_mode;
}

/** Get available import sources for current edition */
export function getImportSources(): string[] {
  return getFeatureConfig().import_sources;
}

/** Get available export formats for current edition */
export function getExportFormats(): string[] {
  const formats = getFeatureConfig().export_formats;
  if (formats === 'all') {
    return ['pdf', 'json', 'fountain', 'fdx', 'csv', 'docx'];
  }
  return formats;
}
