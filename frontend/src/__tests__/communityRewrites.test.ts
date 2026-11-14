import { describe, it, expect } from 'vitest';
import nextConfig from '../../next.config';

describe('Next.js Community Gateway Rewrites', () => {
  it('defines rewrite for /api/v1/community/:path* pointing to community microservice', async () => {
    if (typeof nextConfig.rewrites === 'function') {
      const rewrites = await nextConfig.rewrites();
      const rules = Array.isArray(rewrites) ? rewrites : rewrites.beforeFiles || [];

      const communityRule = rules.find(
        (rule: any) => rule.source === '/api/v1/community/:path*'
      );

      expect(communityRule).toBeDefined();
      expect(communityRule?.destination).toContain('/api/v1/community/:path*');

      // Verify that community rule comes BEFORE the catch-all /api/v1/:path* rule
      const communityIdx = rules.findIndex(
        (rule: any) => rule.source === '/api/v1/community/:path*'
      );
      const catchAllIdx = rules.findIndex(
        (rule: any) => rule.source === '/api/v1/:path*'
      );

      expect(communityIdx).toBeGreaterThanOrEqual(0);
      expect(catchAllIdx).toBeGreaterThanOrEqual(0);
      expect(communityIdx).toBeLessThan(catchAllIdx);
    }
  });
});
