import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as api from '@/lib/api';
import {
  fetchPosts,
  fetchPostById,
  createPost,
  deletePost,
  fetchComments,
  createComment,
  fetchRandomPseudonym,
  updateCommunityPseudonym,
  fetchMyCommunityPseudonym,
} from '@/lib/community';

vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn(),
  getAuthToken: vi.fn(() => 'mock-auth-token'),
}));

describe('Community API Client (src/lib/community.ts)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetchPosts calls /community/posts with default and custom pagination params', async () => {
    const mockFeedResponse = {
      items: [
        {
          id: 1,
          post_id: 1,
          author_sub: 'auth0|123',
          author_pseudonym: 'Giant Elephant',
          content: 'Hello Greenline community! **Welcome**',
          media_attachments: null,
          comments_count: 2,
          created_at: '2026-11-14T10:00:00Z',
          updated_at: '2026-11-14T10:00:00Z',
        },
      ],
      total_count: 1,
      limit: 20,
      offset: 0,
    };

    (api.apiFetch as any).mockResolvedValue(mockFeedResponse);

    const result = await fetchPosts();
    expect(api.apiFetch).toHaveBeenCalledWith('/community/posts?limit=20&offset=0&sort=latest');
    expect(result).toEqual(mockFeedResponse);

    await fetchPosts({ limit: 10, offset: 20, sort: 'oldest' });
    expect(api.apiFetch).toHaveBeenCalledWith('/community/posts?limit=10&offset=20&sort=oldest');
  });

  it('fetchPostById calls /community/posts/{id}', async () => {
    const mockPost = {
      id: 42,
      post_id: 42,
      author_sub: 'auth0|123',
      author_pseudonym: 'Crazy Dog',
      content: 'Single post content',
      media_attachments: [{ url: 'https://example.com/chart.png', type: 'image' }],
      comments_count: 0,
      created_at: '2026-11-14T11:00:00Z',
      updated_at: '2026-11-14T11:00:00Z',
    };

    (api.apiFetch as any).mockResolvedValue(mockPost);

    const result = await fetchPostById(42);
    expect(api.apiFetch).toHaveBeenCalledWith('/community/posts/42');
    expect(result).toEqual(mockPost);
  });

  it('createPost sends POST /community/posts with payload and attaches author pseudonym', async () => {
    const payload = {
      content: 'Sharing my asset allocation breakdown for Q4 2026',
      media_attachments: [
        { url: 'https://example.com/asset-allocation.png', type: 'image', name: 'allocation.png' },
      ],
      author_pseudonym: 'Golden Bull',
    };

    const mockCreated = {
      id: 99,
      post_id: 99,
      author_sub: 'auth0|123',
      author_pseudonym: 'Golden Bull',
      content: payload.content,
      media_attachments: payload.media_attachments,
      comments_count: 0,
      created_at: '2026-11-14T11:30:00Z',
      updated_at: '2026-11-14T11:30:00Z',
    };

    (api.apiFetch as any).mockResolvedValue(mockCreated);

    const result = await createPost(payload);
    expect(api.apiFetch).toHaveBeenCalledWith('/community/posts', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    expect(result).toEqual(mockCreated);
  });

  it('deletePost sends DELETE /community/posts/{post_id}', async () => {
    (api.apiFetch as any).mockResolvedValue(undefined);

    await deletePost(99);
    expect(api.apiFetch).toHaveBeenCalledWith('/community/posts/99', {
      method: 'DELETE',
    });
  });

  it('fetchComments calls GET /community/posts/{post_id}/comments', async () => {
    const mockComments = [
      {
        id: 10,
        comment_id: 10,
        post_id: 99,
        parent_comment_id: null,
        author_sub: 'auth0|456',
        author_pseudonym: 'Wise Owl',
        content: 'Great allocation! What percentage is in ETFs?',
        created_at: '2026-11-14T11:45:00Z',
        updated_at: '2026-11-14T11:45:00Z',
      },
    ];

    (api.apiFetch as any).mockResolvedValue(mockComments);

    const result = await fetchComments(99);
    expect(api.apiFetch).toHaveBeenCalledWith('/community/posts/99/comments?limit=50&offset=0');
    expect(result).toEqual(mockComments);
  });

  it('createComment sends POST /community/posts/{post_id}/comments', async () => {
    const payload = {
      content: 'About 60% in broad market index funds.',
      parent_comment_id: 10,
      author_pseudonym: 'Golden Bull',
    };

    const mockCommentResponse = {
      id: 11,
      comment_id: 11,
      post_id: 99,
      parent_comment_id: 10,
      author_sub: 'auth0|123',
      author_pseudonym: 'Golden Bull',
      content: payload.content,
      created_at: '2026-11-14T11:50:00Z',
      updated_at: '2026-11-14T11:50:00Z',
    };

    (api.apiFetch as any).mockResolvedValue(mockCommentResponse);

    const result = await createComment(99, payload);
    expect(api.apiFetch).toHaveBeenCalledWith('/community/posts/99/comments', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    expect(result).toEqual(mockCommentResponse);
  });

  it('fetchRandomPseudonym calls GET /community/pseudonyms/random with fallback', async () => {
    (api.apiFetch as any).mockResolvedValue({ pseudonym: 'Brave Falcon' });

    const result = await fetchRandomPseudonym();
    expect(api.apiFetch).toHaveBeenCalledWith('/community/pseudonyms/random');
    expect(result.pseudonym).toBe('Brave Falcon');
  });

  it('fetchRandomPseudonym falls back to local generator when server endpoint fails', async () => {
    (api.apiFetch as any).mockRejectedValue(new Error('Network error'));

    const result = await fetchRandomPseudonym();
    expect(result.pseudonym).toBeTruthy();
    expect(typeof result.pseudonym).toBe('string');
    expect(result.pseudonym.split(' ').length).toBeGreaterThanOrEqual(2);
  });

  it('updateCommunityPseudonym calls PUT /community/pseudonyms/me with new pseudonym', async () => {
    const mockProfile = {
      user_uuid: '8f14e45f-b52b-5b32-9b25-a6a38df48210',
      pseudonym: 'Crazy Dog',
      updated_posts: 3,
      updated_comments: 1,
    };
    (api.apiFetch as any).mockResolvedValue(mockProfile);

    const result = await updateCommunityPseudonym('Crazy Dog');
    expect(api.apiFetch).toHaveBeenCalledWith('/community/pseudonyms/me', {
      method: 'PUT',
      body: JSON.stringify({ pseudonym: 'Crazy Dog' }),
    });
    expect(result).toEqual(mockProfile);
  });

  it('fetchMyCommunityPseudonym calls GET /community/pseudonyms/me', async () => {
    const mockProfile = {
      user_uuid: '8f14e45f-b52b-5b32-9b25-a6a38df48210',
      pseudonym: 'Wise Owl',
    };
    (api.apiFetch as any).mockResolvedValue(mockProfile);

    const result = await fetchMyCommunityPseudonym();
    expect(api.apiFetch).toHaveBeenCalledWith('/community/pseudonyms/me');
    expect(result).toEqual(mockProfile);
  });
});
