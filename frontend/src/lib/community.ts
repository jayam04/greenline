import { apiFetch } from "@/lib/api";
import { generateRandomPseudonym } from "@/lib/pseudonym";

export interface MediaAttachment {
  url: string;
  type: string; // "image" | "link" | "document"
  name?: string;
  size?: number;
}

export interface PostResponse {
  id: number;
  post_id: number;
  author_sub: string;
  author_pseudonym?: string | null;
  content: string;
  media_attachments?: MediaAttachment[] | null;
  comments_count: number;
  created_at: string;
  updated_at: string;
}

export interface PostListResponse {
  items: PostResponse[];
  total_count: number;
  limit: number;
  offset: number;
}

export interface CreatePostPayload {
  content: string;
  media_attachments?: MediaAttachment[] | null;
  author_pseudonym?: string | null;
}

export interface CommentResponse {
  id: number;
  comment_id: number;
  post_id: number;
  parent_comment_id?: number | null;
  author_sub: string;
  author_pseudonym?: string | null;
  content: string;
  created_at: string;
  updated_at: string;
}

export interface CreateCommentPayload {
  content: string;
  parent_comment_id?: number | null;
  author_pseudonym?: string | null;
}

export interface RandomPseudonymResponse {
  pseudonym: string;
}

export const COMMUNITY_PSEUDONYM_STORAGE_KEY = "greenline_community_pseudonym";

/**
 * Retrieves the currently saved community pseudonym from localStorage if available.
 */
export function getSavedCommunityPseudonym(): string {
  if (typeof window === "undefined") return "";
  try {
    return localStorage.getItem(COMMUNITY_PSEUDONYM_STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

/**
 * Persists the chosen community pseudonym to localStorage.
 */
export function saveCommunityPseudonymLocally(pseudonym: string): void {
  if (typeof window === "undefined") return;
  try {
    const trimmed = pseudonym.trim();
    if (trimmed) {
      localStorage.setItem(COMMUNITY_PSEUDONYM_STORAGE_KEY, trimmed);
    } else {
      localStorage.removeItem(COMMUNITY_PSEUDONYM_STORAGE_KEY);
    }
  } catch {
    // ignore
  }
}

/**
 * Fetch paginated community posts feed sorted by latest created_at descending.
 */
export async function fetchPosts(params?: {
  limit?: number;
  offset?: number;
  sort?: "latest" | "oldest";
}): Promise<PostListResponse> {
  const limit = params?.limit ?? 20;
  const offset = params?.offset ?? 0;
  const sort = params?.sort ?? "latest";
  const query = `limit=${limit}&offset=${offset}&sort=${sort}`;
  return apiFetch<PostListResponse>(`/community/posts?${query}`);
}

/**
 * Fetch a single post by ID.
 */
export async function fetchPostById(postId: number): Promise<PostResponse> {
  return apiFetch<PostResponse>(`/community/posts/${postId}`);
}

/**
 * Create a new community post with rich text and optional media attachments.
 */
export async function createPost(payload: CreatePostPayload): Promise<PostResponse> {
  return apiFetch<PostResponse>("/community/posts", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * Delete a community post.
 */
export async function deletePost(postId: number): Promise<void> {
  return apiFetch<void>(`/community/posts/${postId}`, {
    method: "DELETE",
  });
}

/**
 * Fetch chronological comments for a post.
 */
export async function fetchComments(
  postId: number,
  params?: { limit?: number; offset?: number }
): Promise<CommentResponse[]> {
  const limit = params?.limit ?? 50;
  const offset = params?.offset ?? 0;
  const query = `limit=${limit}&offset=${offset}`;
  return apiFetch<CommentResponse[]>(`/community/posts/${postId}/comments?${query}`);
}

/**
 * Submit a comment or threaded reply on a post.
 */
export async function createComment(
  postId: number,
  payload: CreateCommentPayload
): Promise<CommentResponse> {
  return apiFetch<CommentResponse>(`/community/posts/${postId}/comments`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * Fetch a random whimsical pseudonym from the microservice with local fallback.
 */
export async function fetchRandomPseudonym(): Promise<RandomPseudonymResponse> {
  try {
    const res = await apiFetch<RandomPseudonymResponse>("/community/pseudonyms/random");
    if (res && res.pseudonym) {
      return res;
    }
  } catch (err) {
    console.warn("Falling back to local pseudonym generation:", err);
  }
  return { pseudonym: generateRandomPseudonym() };
}

export interface UserProfileResponse {
  user_uuid: string;
  pseudonym: string;
  updated_posts?: number;
  updated_comments?: number;
}

/**
 * Update the user's community pseudonym in the community microservice,
 * dynamically changing the display name across all older posts and comments.
 */
export async function updateCommunityPseudonym(pseudonym: string): Promise<UserProfileResponse> {
  return apiFetch<UserProfileResponse>("/community/pseudonyms/me", {
    method: "PUT",
    body: JSON.stringify({ pseudonym }),
  });
}

/**
 * Fetch the current user's community pseudonym and user UUID from the microservice.
 */
export async function fetchMyCommunityPseudonym(): Promise<UserProfileResponse> {
  return apiFetch<UserProfileResponse>("/community/pseudonyms/me");
}
