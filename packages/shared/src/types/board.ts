export type BoardViewMode = 'creative' | 'pipeline';

export interface SpatialRelation {
  source_shot_id: string;
  target_shot_id: string;
  relation: 'before' | 'after' | 'parallel' | 'portal' | 'reference';
  note?: string;
}

export interface AssetLock {
  asset_id: string;
  asset_type: 'character' | 'location' | 'prop' | 'style';
  locked: boolean;
  propagated_shot_ids: string[];
}

export interface ShotCard {
  id: string;
  scene_id?: string;
  title: string;
  intent: string;
  x: number;
  y: number;
  group_id?: string;
  referenced_asset_ids: string[];
  lock_state: AssetLock[];
}

export interface CinemaLabConfig {
  director_method_enabled: boolean;
  sound_narrative_enabled: boolean;
  motif_tracking_enabled: boolean;
  cross_culture_preset: 'auto' | 'cn' | 'intl';
}
