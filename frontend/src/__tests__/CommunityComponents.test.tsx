import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MarkdownContent } from '@/components/community/MarkdownContent';
import { PostComposer } from '@/components/community/PostComposer';
import { PostCard } from '@/components/community/PostCard';
import { CommentThread } from '@/components/community/CommentThread';
import { CommunityFeed } from '@/components/community/CommunityFeed';
import * as communityApi from '@/lib/community';

vi.mock('@/lib/community', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/community')>();
  return {
    ...actual,
    fetchPosts: vi.fn(),
    createPost: vi.fn(),
    fetchComments: vi.fn(),
    createComment: vi.fn(),
    fetchRandomPseudonym: vi.fn(),
  };
});

describe('Community UI Components', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    (communityApi.fetchRandomPseudonym as any).mockResolvedValue({
      pseudonym: 'Golden Falcon',
    });
  });

  describe('MarkdownContent Component', () => {
    it('renders plain text and formatted bold, italic, and code', () => {
      const markdown = 'Hello **world** and *investors* with `code block`';
      const { container } = render(<MarkdownContent content={markdown} />);

      expect(screen.getByText(/Hello/i)).toBeInTheDocument();
      const boldEl = container.querySelector('strong');
      expect(boldEl).toBeInTheDocument();
      expect(boldEl?.textContent).toBe('world');

      const emEl = container.querySelector('em');
      expect(emEl).toBeInTheDocument();
      expect(emEl?.textContent).toBe('investors');

      const codeEl = container.querySelector('code');
      expect(codeEl).toBeInTheDocument();
      expect(codeEl?.textContent).toBe('code block');
    });

    it('renders headings and blockquotes', () => {
      const markdown = '# Main Heading\n> This is a quote';
      const { container } = render(<MarkdownContent content={markdown} />);

      const heading = screen.getByRole('heading', { level: 1 });
      expect(heading).toHaveTextContent('Main Heading');

      const blockquote = container.querySelector('blockquote');
      expect(blockquote).toBeInTheDocument();
      expect(blockquote?.textContent).toContain('This is a quote');
    });

    it('renders links safely with target blank and rel noopener', () => {
      const markdown = 'Check this [Greenline](https://greenline.example.com)';
      render(<MarkdownContent content={markdown} />);

      const link = screen.getByRole('link', { name: 'Greenline' });
      expect(link).toHaveAttribute('href', 'https://greenline.example.com');
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'));
    });

    it('sanitizes unsafe javascript: links', () => {
      const markdown = 'Bad [Attack](javascript:alert(1))';
      render(<MarkdownContent content={markdown} />);

      const badLink = screen.queryByRole('link', { name: 'Attack' });
      expect(badLink).not.toBeInTheDocument();
    });
  });

  describe('PostComposer Component', () => {
    it('renders author pseudonym badge and allows inserting markdown formatting', async () => {
      localStorage.setItem('greenline_community_pseudonym', 'Golden Falcon');
      const onCreated = vi.fn();

      render(<PostComposer onPostCreated={onCreated} currentPseudonym="Golden Falcon" />);

      expect(screen.getByText(/@Golden Falcon/i)).toBeInTheDocument();

      const textarea = screen.getByPlaceholderText(/What's on your mind|Share an insight/i);
      expect(textarea).toBeInTheDocument();

      // Click Bold button
      const boldBtn = screen.getByTitle(/Bold/i);
      fireEvent.click(boldBtn);
      expect((textarea as HTMLTextAreaElement).value).toContain('**bold text**');
    });

    it('adds media attachments and displays preview chips', async () => {
      render(<PostComposer onPostCreated={vi.fn()} currentPseudonym="Crazy Dog" />);

      // Open media attachment input
      const attachBtn = screen.getByRole('button', { name: /Attach Media|Media/i });
      fireEvent.click(attachBtn);

      const urlInput = screen.getByPlaceholderText(/Enter image or media URL/i);
      fireEvent.change(urlInput, { target: { value: 'https://example.com/screenshot.png' } });

      const addBtn = screen.getByRole('button', { name: /Add Attachment|Add/i });
      fireEvent.click(addBtn);

      // Verify attachment chip is rendered
      expect(screen.getByText(/screenshot\.png|example\.com/i)).toBeInTheDocument();
    });

    it('submits post with content and media attachments', async () => {
      const mockPost = {
        id: 101,
        post_id: 101,
        author_sub: 'auth0|1',
        author_pseudonym: 'Giant Elephant',
        content: 'Portfolio allocation update',
        media_attachments: [{ url: 'https://example.com/chart.png', type: 'image' }],
        comments_count: 0,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      (communityApi.createPost as any).mockResolvedValue(mockPost);

      const onCreated = vi.fn();
      render(<PostComposer onPostCreated={onCreated} currentPseudonym="Giant Elephant" />);

      const textarea = screen.getByPlaceholderText(/What's on your mind|Share an insight/i);
      fireEvent.change(textarea, { target: { value: 'Portfolio allocation update' } });

      const submitBtn = screen.getByRole('button', { name: /Post|Publish|Share/i });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(communityApi.createPost).toHaveBeenCalledWith(
          expect.objectContaining({
            content: 'Portfolio allocation update',
            author_pseudonym: 'Giant Elephant',
          })
        );
        expect(onCreated).toHaveBeenCalledWith(mockPost);
      });
    });
  });

  describe('PostCard Component', () => {
    const samplePost = {
      id: 201,
      post_id: 201,
      author_sub: 'auth0|201',
      author_pseudonym: 'Wise Owl',
      content: 'Here is my **weekly net worth** update!',
      media_attachments: [
        { url: 'https://example.com/asset-growth.png', type: 'image', name: 'asset-growth.png' },
      ],
      comments_count: 3,
      created_at: '2026-11-14T09:00:00Z',
      updated_at: '2026-11-14T09:00:00Z',
    };

    it('renders author pseudonym, formatted content, and media preview', () => {
      render(<PostCard post={samplePost} currentPseudonym="Crazy Dog" />);

      expect(screen.getByText(/@Wise Owl/i)).toBeInTheDocument();
      expect(screen.getByText(/weekly net worth/i)).toBeInTheDocument();

      const img = screen.getByAltText(/attachment|asset-growth/i);
      expect(img).toHaveAttribute('src', 'https://example.com/asset-growth.png');

      expect(screen.getByText(/3/)).toBeInTheDocument();
    });

    it('toggles comment thread expansion on comments button click', async () => {
      (communityApi.fetchComments as any).mockResolvedValue([
        {
          id: 501,
          comment_id: 501,
          post_id: 201,
          parent_comment_id: null,
          author_sub: 'auth0|3',
          author_pseudonym: 'Brave Lion',
          content: 'Impressive progress!',
          created_at: '2026-11-14T09:30:00Z',
          updated_at: '2026-11-14T09:30:00Z',
        },
      ]);

      render(<PostCard post={samplePost} currentPseudonym="Crazy Dog" />);

      // Initially comments thread is collapsed
      expect(screen.queryByText('Impressive progress!')).not.toBeInTheDocument();

      // Click comment toggle button
      const commentBtn = screen.getByRole('button', { name: /comments|reply/i });
      fireEvent.click(commentBtn);

      await waitFor(() => {
        expect(screen.getByText('Impressive progress!')).toBeInTheDocument();
        expect(screen.getByText(/@Brave Lion/i)).toBeInTheDocument();
      });
    });
  });

  describe('CommentThread Component', () => {
    it('submits a new comment and appends it to the thread', async () => {
      const mockComments = [
        {
          id: 601,
          comment_id: 601,
          post_id: 301,
          parent_comment_id: null,
          author_sub: 'auth0|5',
          author_pseudonym: 'Solar Bear',
          content: 'Initial comment',
          created_at: '2026-11-14T08:00:00Z',
          updated_at: '2026-11-14T08:00:00Z',
        },
      ];
      (communityApi.fetchComments as any).mockResolvedValue(mockComments);

      const newCommentResponse = {
        id: 602,
        comment_id: 602,
        post_id: 301,
        parent_comment_id: null,
        author_sub: 'auth0|me',
        author_pseudonym: 'Crazy Dog',
        content: 'Replying to solar bear',
        created_at: '2026-11-14T08:10:00Z',
        updated_at: '2026-11-14T08:10:00Z',
      };
      (communityApi.createComment as any).mockResolvedValue(newCommentResponse);

      render(<CommentThread postId={301} currentPseudonym="Crazy Dog" />);

      await waitFor(() => {
        expect(screen.getByText('Initial comment')).toBeInTheDocument();
      });

      const input = screen.getByPlaceholderText(/Write a reply|Leave a comment/i);
      fireEvent.change(input, { target: { value: 'Replying to solar bear' } });

      const replySubmit = screen.getByRole('button', { name: /Submit Reply|Post Reply/i });
      fireEvent.click(replySubmit);

      await waitFor(() => {
        expect(communityApi.createComment).toHaveBeenCalledWith(
          301,
          expect.objectContaining({
            content: 'Replying to solar bear',
            author_pseudonym: 'Crazy Dog',
          })
        );
        expect(screen.getByText('Replying to solar bear')).toBeInTheDocument();
      });
    });
  });

  describe('CommunityFeed Component', () => {
    it('renders post composer, feed header, and posts list', async () => {
      const mockPosts = [
        {
          id: 1,
          post_id: 1,
          author_sub: 'auth0|1',
          author_pseudonym: 'Giant Elephant',
          content: 'First post in feed',
          media_attachments: null,
          comments_count: 0,
          created_at: '2026-11-14T07:00:00Z',
          updated_at: '2026-11-14T07:00:00Z',
        },
      ];
      (communityApi.fetchPosts as any).mockResolvedValue({
        items: mockPosts,
        total_count: 1,
        limit: 20,
        offset: 0,
      });

      render(<CommunityFeed currentPseudonym="Crazy Dog" />);

      await waitFor(() => {
        expect(screen.getByText('First post in feed')).toBeInTheDocument();
        expect(screen.getByText(/@Giant Elephant/i)).toBeInTheDocument();
      });
    });

    it('shows empty state when feed has no posts', async () => {
      (communityApi.fetchPosts as any).mockResolvedValue({
        items: [],
        total_count: 0,
        limit: 20,
        offset: 0,
      });

      render(<CommunityFeed currentPseudonym="Crazy Dog" />);

      await waitFor(() => {
        expect(screen.getByText('No posts yet')).toBeInTheDocument();
      });
    });
  });
});
