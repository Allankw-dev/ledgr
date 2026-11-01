import { describe, expect, it } from 'vitest';
import { safeUrl } from '../lib/safeUrl';

describe('safeUrl', () => {
  it.each([
    'https://api.example.com/api/attachments/download?token=abc',
    'http://localhost:4000/file.png',
    'blob:https://app.example.com/1234-5678',
    '/api/attachments/download?token=abc',
  ])('lets %s through unchanged', (url) => {
    expect(safeUrl(url)).toBe(url);
  });

  it.each([
    'javascript:alert(1)',
    'JaVaScRiPt:alert(1)',
    ' javascript:alert(1)',
    'java\tscript:alert(1)',
    'data:text/html,<script>alert(1)</script>',
    'vbscript:msgbox(1)',
    'file:///etc/passwd',
  ])('refuses %j', (url) => {
    expect(safeUrl(url)).toBeUndefined();
  });

  it('treats empty and missing values as no link', () => {
    expect(safeUrl(undefined)).toBeUndefined();
    expect(safeUrl(null)).toBeUndefined();
    expect(safeUrl('')).toBeUndefined();
  });
});
