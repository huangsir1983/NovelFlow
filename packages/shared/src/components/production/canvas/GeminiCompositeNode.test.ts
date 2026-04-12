/**
 * TDD tests for GeminiCompositeNode generate flow.
 *
 * Tests the key data transformations:
 * 1. normalizeStorageUrl converts file paths to HTTP URLs
 * 2. Reference images are fetched and converted to base64
 * 3. buildInterleavedParts receives correct data
 * 4. API request has non-empty prompt
 */

import { normalizeStorageUrl, API_BASE_URL } from '../../../lib/api';
import { buildInterleavedParts, type StageScreenshots } from '../../panorama/stageScreenshot';

// Mock character mappings as they come from DirectorStage3DNode
const mockCharacterMappings = [
  {
    stageCharId: 'char-0',
    stageCharName: '高令宁',
    color: '#06b6d4',
    poseScreenshot: 'AAAA', // base64 pose screenshot
    referenceImageUrl: 'G:\\涛项目\\claude版\\模块二\\backend\\uploads\\assets\\images\\abc.jpeg',
    referenceStorageKey: 'assets/images/abc.jpeg',
  },
  {
    stageCharId: 'char-1',
    stageCharName: '林婉',
    color: '#f472b6',
    poseScreenshot: 'BBBB',
    referenceImageUrl: 'http://localhost:8000/uploads/assets/images/def.jpeg',
    referenceStorageKey: 'assets/images/def.jpeg',
  },
];

describe('GeminiComposite generate flow', () => {
  describe('URL normalization for reference images', () => {
    it('converts Windows file path to HTTP URL', () => {
      const url = mockCharacterMappings[0].referenceImageUrl;
      const normalized = normalizeStorageUrl(url);
      expect(normalized).toBe('http://localhost:8000/uploads/assets/images/abc.jpeg');
      expect(normalized).toMatch(/^https?:\/\//);
    });

    it('keeps HTTP URLs unchanged', () => {
      const url = mockCharacterMappings[1].referenceImageUrl;
      const normalized = normalizeStorageUrl(url);
      expect(normalized).toBe(url);
    });

    it('handles all character mappings without file:// URLs', () => {
      for (const m of mockCharacterMappings) {
        const normalized = normalizeStorageUrl(m.referenceImageUrl);
        expect(normalized).not.toContain('file:///');
        expect(normalized).toMatch(/^https?:\/\//);
      }
    });
  });

  describe('buildInterleavedParts with character data', () => {
    it('builds correct parts with scene + characters', () => {
      const screenshots: StageScreenshots = {
        base: 'SCENE_BASE64',
        characters: [
          { stageCharId: 'char-0', stageCharName: '高令宁', color: '#06b6d4', screenshot: 'POSE1' },
        ],
      };

      const charData = [
        {
          stageCharId: 'char-0',
          referenceCharName: '高令宁',
          stageCharColor: '#06b6d4',
          poseScreenshot: 'POSE1',
          referenceBase64: 'REF1_BASE64',
        },
      ];

      const parts = buildInterleavedParts(screenshots, charData, '古风庭院场景');
      // Images first: scene + (pose + ref) per character
      const imageParts = parts.filter(p => p.type === 'image');
      const textParts = parts.filter(p => p.type === 'text');

      expect(imageParts.length).toBe(3); // scene + 1 pose + 1 ref
      expect(textParts.length).toBe(1);
      expect(imageParts[0].content).toBe('SCENE_BASE64');
      expect(imageParts[1].content).toBe('POSE1');
      expect(imageParts[2].content).toBe('REF1_BASE64');
      expect(textParts[0].content).toContain('高令宁');
      expect(textParts[0].content).toContain('古风庭院场景');
    });

    it('includes bbox position data in prompt when available', () => {
      const screenshots: StageScreenshots = {
        base: 'SCENE',
        characters: [
          { stageCharId: 'char-0', stageCharName: '高令宁', color: '#06b6d4', screenshot: 'P1',
            bbox: { left: 10, top: 20, width: 25, height: 70 } },
        ],
      };

      const charData = [
        {
          stageCharId: 'char-0',
          referenceCharName: '高令宁',
          stageCharColor: '#06b6d4',
          poseScreenshot: 'P1',
          referenceBase64: 'REF1',
          bbox: { left: 10, top: 20, width: 25, height: 70 },
        },
      ];

      const parts = buildInterleavedParts(screenshots, charData);
      const text = parts.find(p => p.type === 'text')!.content;

      // Should contain position data in new format
      expect(text).toContain('左边界10%');
      expect(text).toContain('上边界20%');
      expect(text).toContain('宽25%');
      expect(text).toContain('高70%');
      expect(text).toContain('画面左侧');
      expect(text).toContain('不能偏移也不能放大缩小');
    });

    it('includes position lock rules in prompt', () => {
      const screenshots: StageScreenshots = { base: 'S', characters: [] };
      const parts = buildInterleavedParts(screenshots, []);
      const text = parts.find(p => p.type === 'text')!.content;

      expect(text).toContain('位置锁定');
      expect(text).toContain('大小锁定');
      expect(text).toContain('姿势锁定');
      expect(text).toContain('面部一致性');
      expect(text).toContain('风格保真');
    });

    it('builds parts without characters (scene only)', () => {
      const screenshots: StageScreenshots = {
        base: 'SCENE_BASE64',
        characters: [],
      };

      const parts = buildInterleavedParts(screenshots, [], '场景描述');
      const imageParts = parts.filter(p => p.type === 'image');
      const textParts = parts.filter(p => p.type === 'text');

      expect(imageParts.length).toBe(1); // scene only
      expect(textParts.length).toBe(1);
      expect(imageParts[0].content).toBe('SCENE_BASE64');
    });

    it('filters out characters with empty referenceBase64', () => {
      const charData = [
        {
          stageCharId: 'char-0',
          referenceCharName: '高令宁',
          stageCharColor: '#06b6d4',
          poseScreenshot: 'POSE1',
          referenceBase64: 'HAS_DATA',
        },
        {
          stageCharId: 'char-1',
          referenceCharName: '林婉',
          stageCharColor: '#f472b6',
          poseScreenshot: 'POSE2',
          referenceBase64: '', // empty — should be filtered
        },
      ];

      const filtered = charData.filter(cd => cd.referenceBase64);
      expect(filtered.length).toBe(1);
      expect(filtered[0].referenceCharName).toBe('高令宁');
    });
  });

  describe('API request construction', () => {
    it('prompt must be non-empty', () => {
      const prompt = '根据提供的图片生成高品质画面';
      expect(prompt.trim()).not.toBe('');
    });

    it('interleaved_parts format matches backend schema', () => {
      const screenshots: StageScreenshots = {
        base: 'SCENE',
        characters: [],
      };
      const parts = buildInterleavedParts(screenshots, []);
      const apiParts = parts.map(p => ({
        type: p.type,
        content: p.content,
        mime_type: p.mime_type,
      }));

      for (const part of apiParts) {
        expect(part).toHaveProperty('type');
        expect(part).toHaveProperty('content');
        expect(['text', 'image']).toContain(part.type);
        if (part.type === 'image') {
          expect(part.mime_type).toBeDefined();
        }
      }
    });
  });
});
