import { normalizeStorageUrl } from './api';

describe('normalizeStorageUrl', () => {
  it('returns empty string for null/undefined/empty', () => {
    expect(normalizeStorageUrl(null)).toBe('');
    expect(normalizeStorageUrl(undefined)).toBe('');
    expect(normalizeStorageUrl('')).toBe('');
  });

  it('passes through HTTP URLs unchanged', () => {
    const url = 'http://localhost:8000/uploads/assets/images/abc.jpeg';
    expect(normalizeStorageUrl(url)).toBe(url);
  });

  it('passes through HTTPS URLs unchanged', () => {
    const url = 'https://cdn.example.com/images/abc.jpeg';
    expect(normalizeStorageUrl(url)).toBe(url);
  });

  it('passes through data URIs unchanged', () => {
    const url = 'data:image/jpeg;base64,/9j/4AAQSkZJRg==';
    expect(normalizeStorageUrl(url)).toBe(url);
  });

  it('converts Windows absolute path with /uploads/ to HTTP URL', () => {
    const filePath = 'G:\\涛项目\\claude版\\模块二\\backend\\uploads\\assets\\images\\abc.jpeg';
    expect(normalizeStorageUrl(filePath)).toBe(
      'http://localhost:8000/uploads/assets/images/abc.jpeg',
    );
  });

  it('converts Unix absolute path with /uploads/ to HTTP URL', () => {
    const filePath = '/home/user/project/backend/uploads/assets/images/abc.jpeg';
    expect(normalizeStorageUrl(filePath)).toBe(
      'http://localhost:8000/uploads/assets/images/abc.jpeg',
    );
  });

  it('converts relative path starting with / to HTTP URL', () => {
    expect(normalizeStorageUrl('/api/some/resource')).toBe(
      'http://localhost:8000/api/some/resource',
    );
  });

  it('returns original string for unrecognized format', () => {
    expect(normalizeStorageUrl('some-random-string')).toBe('some-random-string');
  });

  it('handles Windows path with forward slashes', () => {
    const filePath = 'G:/涛项目/claude版/模块二/backend/uploads/assets/images/abc.jpeg';
    expect(normalizeStorageUrl(filePath)).toBe(
      'http://localhost:8000/uploads/assets/images/abc.jpeg',
    );
  });
});
