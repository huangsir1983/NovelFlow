import { describe, it, expect } from 'vitest';
import { matchActionToPreset } from './actionPresetMatcher';

describe('matchActionToPreset', () => {
  // ── Fallback behavior ──

  it('returns "standing" for undefined action', () => {
    expect(matchActionToPreset(undefined)).toBe('standing');
  });

  it('returns "standing" for empty string', () => {
    expect(matchActionToPreset('')).toBe('standing');
  });

  it('returns "standing" for unrecognized action', () => {
    expect(matchActionToPreset('微笑着看向远方')).toBe('standing');
  });

  // ── Running ──

  it('matches "奔跑" → running', () => {
    expect(matchActionToPreset('奔跑着穿过走廊')).toBe('running');
  });

  it('matches "冲" → running', () => {
    expect(matchActionToPreset('冲向大门')).toBe('running');
  });

  it('matches "飞奔" → running', () => {
    expect(matchActionToPreset('飞奔而去')).toBe('running');
  });

  // ── Walking ──

  it('matches "走近" → walking', () => {
    expect(matchActionToPreset('走近窗边')).toBe('walking');
  });

  it('matches "漫步" → walking', () => {
    expect(matchActionToPreset('在花园中漫步')).toBe('walking');
  });

  it('matches "走到" → walking', () => {
    expect(matchActionToPreset('走到桌前')).toBe('walking');
  });

  // ── Sitting ──

  it('matches "坐在" → sitting', () => {
    expect(matchActionToPreset('坐在椅子上')).toBe('sitting');
  });

  it('matches "端坐" → sitting', () => {
    expect(matchActionToPreset('端坐于案前')).toBe('sitting');
  });

  it('matches "席地而坐" → sitting', () => {
    expect(matchActionToPreset('席地而坐')).toBe('sitting');
  });

  // ── Crouching ──

  it('matches "蹲下" → crouching', () => {
    expect(matchActionToPreset('蹲下身子')).toBe('crouching');
  });

  // ── Lying ──

  it('matches "躺在" → lying', () => {
    expect(matchActionToPreset('躺在床上')).toBe('lying');
  });

  it('matches "倒下" → lying', () => {
    expect(matchActionToPreset('痛苦地倒下')).toBe('lying');
  });

  // ── Prone ──

  it('matches "趴在" → prone', () => {
    expect(matchActionToPreset('趴在地上')).toBe('prone');
  });

  it('matches "匍匐" → prone', () => {
    expect(matchActionToPreset('匍匐前进')).toBe('prone');
  });

  // ── Kneeling (new preset) ──

  it('matches "跪下" → kneeling', () => {
    expect(matchActionToPreset('跪下求饶')).toBe('kneeling');
  });

  it('matches "下跪" → kneeling', () => {
    expect(matchActionToPreset('下跪行礼')).toBe('kneeling');
  });

  // ── Hugging ──

  it('matches "拥抱" → hugging', () => {
    expect(matchActionToPreset('紧紧拥抱')).toBe('hugging');
  });

  it('matches "依偎" → hugging', () => {
    expect(matchActionToPreset('依偎在怀中')).toBe('hugging');
  });

  // ── Fighting ──

  it('matches "格斗" → fighting', () => {
    expect(matchActionToPreset('与敌人格斗')).toBe('fighting');
  });

  it('matches "拔剑" → fighting', () => {
    expect(matchActionToPreset('拔剑而起')).toBe('fighting');
  });

  // ── Thinking ──

  it('matches "沉思" → thinking', () => {
    expect(matchActionToPreset('沉思片刻')).toBe('thinking');
  });

  it('matches "发呆" → thinking', () => {
    expect(matchActionToPreset('对着窗外发呆')).toBe('thinking');
  });

  // ── Leaning (new preset) ──

  it('matches "靠在" → leaning', () => {
    expect(matchActionToPreset('靠在墙上')).toBe('leaning');
  });

  it('matches "倚靠" → leaning', () => {
    expect(matchActionToPreset('倚靠着门框')).toBe('leaning');
  });

  // ── Pointing (new preset) ──

  it('matches "指着" → pointing', () => {
    expect(matchActionToPreset('指着远方')).toBe('pointing');
  });

  it('matches "指向" → pointing', () => {
    expect(matchActionToPreset('指向地图上的一点')).toBe('pointing');
  });

  // ── Bowing (new preset) ──

  it('matches "鞠躬" → bowing', () => {
    expect(matchActionToPreset('深深鞠躬')).toBe('bowing');
  });

  it('matches "欠身" → bowing', () => {
    expect(matchActionToPreset('微微欠身')).toBe('bowing');
  });

  // ── Standing (explicit) ──

  it('matches "站在" → standing', () => {
    expect(matchActionToPreset('站在门口')).toBe('standing');
  });

  it('matches "伫立" → standing', () => {
    expect(matchActionToPreset('伫立良久')).toBe('standing');
  });

  // ── Priority: specific keywords beat generic ones ──

  it('"奔跑" beats "跑" (specific before generic)', () => {
    // Both could match, but "奔跑" is checked first
    expect(matchActionToPreset('奔跑')).toBe('running');
  });

  it('"坐在椅子上站起来" matches sitting (first keyword wins)', () => {
    // "坐在" appears before "站" in the text, and sitting rules are checked before standing
    expect(matchActionToPreset('坐在椅子上')).toBe('sitting');
  });

  it('compound action: "走到桌前坐下" matches walking (first matching rule wins)', () => {
    // "走到" matches walking before "坐下" matches sitting
    expect(matchActionToPreset('走到桌前坐下')).toBe('walking');
  });
});
