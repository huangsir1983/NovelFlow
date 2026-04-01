import {
  buildAnimaticClips,
  buildSequenceBundle,
  buildShotProductionProjection,
} from '@unrealmake/shared/lib';
import type { Character, Location, Project, Prop, Scene, Shot } from '@unrealmake/shared/types';

describe('shot production flow helpers', () => {
  const project: Project = {
    id: 'project-1',
    name: 'TapNow Demo',
    description: '',
    import_source: 'script',
    edition: 'canvas',
    stage: 'storyboard',
    style_preset: 'realistic',
    created_at: '2026-03-29T00:00:00.000Z',
    updated_at: '2026-03-29T00:00:00.000Z',
  };

  const scene: Scene = {
    id: 'scene-1',
    project_id: project.id,
    heading: 'Rooftop confrontation',
    location: 'Rooftop',
    time_of_day: 'night',
    description: 'Two characters argue under neon rain.',
    action: 'The camera follows them across the rooftop.',
    dialogue: [{ character: 'Lin', line: 'You came back.', parenthetical: '' }],
    order: 1,
    characters_present: ['Lin'],
    key_props: ['Umbrella'],
    core_event: 'Lin confronts the rival on the rooftop.',
    estimated_duration_s: 4,
    narrative_mode: 'dialogue',
  };

  const character: Character = {
    id: 'char-1',
    project_id: project.id,
    name: 'Lin',
    aliases: [],
    role: 'protagonist',
    description: 'Main character',
    personality: '',
    arc: '',
    relationships: [],
    visual_reference: 'Rain-soaked close-up portrait',
  };

  const location: Location = {
    id: 'loc-1',
    project_id: project.id,
    name: 'Rooftop',
    description: 'Wet rooftop at night',
    visual_description: 'Neon reflections on concrete',
    mood: 'tense',
    visual_reference: 'Night rooftop visual anchor',
  };

  const prop: Prop = {
    id: 'prop-1',
    project_id: project.id,
    name: 'Umbrella',
    category: 'prop',
    description: 'Black umbrella with rain drops',
    visual_reference: 'Hero umbrella prop anchor',
  };

  const shot: Shot = {
    id: 'shot-1',
    scene_id: scene.id,
    project_id: project.id,
    shot_number: 1,
    goal: 'Lin faces the rival under neon rain.',
    composition: 'medium close-up',
    camera_angle: 'eye level',
    camera_movement: 'slow push',
    framing: 'MCU',
    duration_estimate: '3.2s',
    characters_in_frame: ['Lin'],
    emotion_target: 'tension',
    dramatic_intensity: 0.8,
    transition_in: 'cut',
    transition_out: 'cut',
    description: 'Lin grips the umbrella and confronts the rival.',
    visual_prompt: 'Rain-soaked neon rooftop confrontation, Lin in medium close-up.',
    order: 1,
  };

  it('builds ready shot specs when anchors and style are present', () => {
    const projection = buildShotProductionProjection({
      project,
      scenes: [scene],
      shots: [shot],
      characters: [character],
      locations: [location],
      props: [prop],
      assetImages: {
        'char-1': { front_full: 'ref-a', front_half: 'ref-b' },
        'loc-1': { east: 'ref-c', north: 'ref-d' },
        'prop-1': { front: 'ref-e' },
      },
      assetImageKeys: {},
      stylePreset: 'realistic',
    });

    expect(projection.specs).toHaveLength(1);
    expect(projection.specs[0].readiness).toBe('ready');
    expect(projection.specs[0].storyboardStatus).toBe('ready');
    expect(projection.specs[0].videoModeDecision.recommendedMode).toBe('image_to_video');
    expect(projection.specs[0].recommendedModuleIds).toContain('dialogue-module');
    expect(projection.sceneReports[0]?.status).toBe('ready');
    expect(projection.readiness.readyShots).toBe(1);
  });

  it('keeps text-to-video fallback available when anchors are missing', () => {
    const projection = buildShotProductionProjection({
      project: { ...project, style_preset: undefined },
      scenes: [scene],
      shots: [shot],
      characters: [],
      locations: [],
      props: [],
      assetImages: {},
      assetImageKeys: {},
      stylePreset: null,
    });

    expect(projection.specs[0].readiness).toBe('ready');
    expect(projection.specs[0].videoModeDecision.availableModes).toContain('text_to_video');
    expect(projection.specs[0].videoModeDecision.recommendedMode).toBe('text_to_video');
    expect(projection.requirements.length).toBeGreaterThan(0);
  });

  it('builds storyboard/video animatic clips and approved sequence bundles from approved artifacts', () => {
    const projection = buildShotProductionProjection({
      project,
      scenes: [scene],
      shots: [shot],
      characters: [character],
      locations: [location],
      props: [prop],
      assetImages: {
        'char-1': { front_full: 'ref-a', front_half: 'ref-b' },
        'loc-1': { east: 'ref-c', north: 'ref-d' },
        'prop-1': { front: 'ref-e' },
      },
      assetImageKeys: {},
      stylePreset: 'realistic',
    });
    const spec = projection.specs[0];
    const imageArtifact = {
      id: 'artifact-image-1',
      shotId: spec.shotId,
      nodeId: `${spec.moduleId}:image-candidate`,
      type: 'image' as const,
      label: 'Image Candidate 1',
      status: 'approved' as const,
      prompt: 'image prompt',
      thumbnailText: 'img',
      version: 1,
      costCredits: 1.2,
      createdAt: '2026-03-29T00:00:00.000Z',
      sourceAnchorKeys: ['char-1', 'loc-1'],
    };
    const videoArtifact = {
      id: 'artifact-video-1',
      shotId: spec.shotId,
      nodeId: `${spec.moduleId}:video-generation`,
      type: 'video' as const,
      label: 'Video Candidate 1',
      status: 'approved' as const,
      prompt: 'video prompt',
      thumbnailText: 'vid',
      version: 1,
      durationMs: 3600,
      costCredits: 7.5,
      createdAt: '2026-03-29T00:00:00.000Z',
      sourceAnchorKeys: ['char-1', 'loc-1'],
    };
    const artifactsByShotId = {
      [spec.shotId]: [imageArtifact, videoArtifact],
    };
    const writebacksByShotId = {
      [spec.shotId]: {
        shotId: spec.shotId,
        recommendedImageArtifactId: imageArtifact.id,
        approvedVideoArtifactId: videoArtifact.id,
        reusableAnchorAssetIds: ['char-1', 'loc-1'],
        transitionHint: 'cut',
        audioPlaceholder: 'audio',
        subtitlePlaceholder: 'subtitle',
      },
    };

    const clips = buildAnimaticClips(
      projection.specs,
      artifactsByShotId,
      writebacksByShotId,
      { [spec.shotId]: 3200 },
    );
    const bundle = buildSequenceBundle(
      project.id,
      projection.specs,
      artifactsByShotId,
      writebacksByShotId,
      clips,
    );

    expect(clips).toHaveLength(2);
    expect(clips.map((clip) => clip.phase)).toEqual(['storyboard', 'video']);
    expect(clips[0].sourceType).toBe('image');
    expect(clips[0].durationMs).toBe(3200);
    expect(clips[1].sourceType).toBe('video');
    expect(bundle?.status).toBe('approved');
    expect(bundle?.exportTarget).toBe('jianying');
  });
});
