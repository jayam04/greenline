"use client";

import * as React from "react";
import { Maximize2, Minimize2, MessageCircle, Trash2, Send, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Segmented } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { CommentThread } from "@/components/community/CommentThread";
import {
  fetchPosts,
  createPost,
  deletePost,
  getSavedCommunityPseudonym,
  PostResponse,
} from "@/lib/community";

function formatAgo(dateStr: string) {
  try {
    const diffMs = Date.now() - new Date(dateStr).getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins} min ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours} h ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays === 1) return "Yesterday";
    return `${diffDays} days ago`;
  } catch {
    return dateStr;
  }
}

interface CommunityPanelProps {
  expanded: boolean;
  onToggle: () => void;
  alias?: string;
  onPostCreated?: () => void;
}

export function CommunityPanel({
  expanded,
  onToggle,
  alias: propAlias,
  onPostCreated,
}: CommunityPanelProps) {
  const [alias, setAlias] = React.useState(propAlias || getSavedCommunityPseudonym() || "Solar Beaver");
  const [posts, setPosts] = React.useState<PostResponse[]>([]);
  const [draft, setDraft] = React.useState("");
  const [sort, setSort] = React.useState<"latest" | "oldest">("latest");
  const [loading, setLoading] = React.useState(true);
  const [submitting, setSubmitting] = React.useState(false);
  const [expandedPostIds, setExpandedPostIds] = React.useState<number[]>([]);

  React.useEffect(() => {
    if (propAlias) {
      setAlias(propAlias);
    } else {
      const saved = getSavedCommunityPseudonym();
      if (saved) setAlias(saved);
    }
  }, [propAlias]);

  const loadFeed = React.useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetchPosts({ limit: 50, offset: 0, sort });
      setPosts(res?.items || []);
    } catch (e) {
      console.error("Failed to load community feed:", e);
    } finally {
      setLoading(false);
    }
  }, [sort]);

  React.useEffect(() => {
    loadFeed();
  }, [loadFeed]);

  const submit = async () => {
    if (!draft.trim() || submitting) return;
    try {
      setSubmitting(true);
      const newPost = await createPost({
        content: draft.trim(),
        author_pseudonym: alias,
      });
      if (newPost) {
        setPosts((prev) => [newPost, ...prev]);
        setDraft("");
        onPostCreated?.();
      }
    } catch (e) {
      console.error("Failed to submit post:", e);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (postId: number) => {
    try {
      await deletePost(postId);
      setPosts((prev) => prev.filter((p) => p.post_id !== postId && p.id !== postId));
    } catch (e) {
      console.error("Failed to delete post:", e);
    }
  };

  return (
    <section
      aria-label="Community"
      className={cn(
        "flex flex-col rounded-card border border-border bg-surface shadow-card",
        expanded ? "min-h-[640px]" : "lg:h-[calc(100vh-8.5rem)] lg:min-h-[600px]"
      )}
    >
      <header className="flex items-center justify-between gap-3 border-b border-border px-5 py-3.5">
        <h2 className="text-title font-semibold">Community</h2>
        <div className="flex items-center gap-2">
          <Segmented
            size="sm"
            value={sort}
            onChange={(v) => setSort(v as "latest" | "oldest")}
            options={[
              { value: "latest", label: "Latest" },
              { value: "oldest", label: "Oldest" },
            ]}
          />
          <button
            type="button"
            onClick={onToggle}
            aria-label={expanded ? "Collapse community" : "Expand community"}
            title={expanded ? "Collapse" : "Expand"}
            className="hidden lg:inline-flex size-8 items-center justify-center rounded-control text-muted hover:bg-surface-2 hover:text-foreground transition-colors"
          >
            {expanded ? <Minimize2 className="size-4" /> : <Maximize2 className="size-4" />}
          </button>
        </div>
      </header>

      <div className="border-b border-border p-4">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Share an idea or ask a question"
          className="min-h-16 w-full rounded-control border border-border-strong bg-surface p-3 text-body placeholder:text-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-info/40 focus-visible:border-info resize-none"
          aria-label="New post"
        />
        <div className="mt-2 flex items-center justify-between">
          <span className="text-label text-muted">
            Posting as <Badge tone="warn">{alias}</Badge>
          </span>
          <button
            type="button"
            onClick={submit}
            disabled={!draft.trim() || submitting}
            className="inline-flex items-center gap-1.5 rounded-control bg-primary px-3 py-1.5 text-label font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            {submitting ? <Loader2 className="size-3.5 animate-spin" /> : <Send className="size-3.5" />}
            <span>Post</span>
          </button>
        </div>
      </div>

      <ul
        className={cn(
          "min-h-0 flex-1 divide-y divide-border overflow-auto",
          expanded && "grid divide-y-0 gap-0 md:grid-cols-2 [&>li]:border-b [&>li]:border-border md:[&>li:nth-child(odd)]:border-r"
        )}
      >
        {loading && posts.length === 0 ? (
          <li className="flex items-center justify-center p-8 text-muted text-label">
            <Loader2 className="size-5 animate-spin mr-2" /> Loading posts...
          </li>
        ) : posts.length === 0 ? (
          <li className="p-8 text-center text-label text-muted">
            No community posts yet. Be the first to share!
          </li>
        ) : (
          posts.map((p) => {
            const authorName = p.author_pseudonym || "Anonymous";
            const initials = authorName.split(" ").map((w) => w[0]).join("").slice(0, 2);
            const isMine = p.author_pseudonym === alias;
            const postId = p.post_id || p.id;

            return (
              <li key={postId} className="group px-5 py-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="grid size-7 place-items-center rounded-full bg-surface-2 text-micro font-semibold uppercase">
                      {initials}
                    </span>
                    <span className="text-label font-medium">{authorName}</span>
                    <span className="text-micro text-muted">{formatAgo(p.created_at)}</span>
                  </div>
                  {isMine && (
                    <button
                      type="button"
                      aria-label="Delete post"
                      onClick={() => handleDelete(postId)}
                      className="rounded-control p-1 text-subtle opacity-0 transition-opacity hover:text-loss group-hover:opacity-100 focus-visible:opacity-100"
                    >
                      <Trash2 className="size-4" />
                    </button>
                  )}
                </div>
                <p className="mt-2 text-body whitespace-pre-wrap">{p.content}</p>
                <button
                  type="button"
                  onClick={() =>
                    setExpandedPostIds((prev) =>
                      prev.includes(postId) ? prev.filter((id) => id !== postId) : [...prev, postId]
                    )
                  }
                  className="mt-2 inline-flex items-center gap-1.5 text-label text-muted hover:text-foreground transition-colors cursor-pointer"
                >
                  <MessageCircle className="size-4" /> {p.comments_count || 0}{" "}
                  {p.comments_count === 1 ? "comment" : "comments"}
                </button>
                {expandedPostIds.includes(postId) && (
                  <div className="mt-3">
                    <CommentThread
                      postId={postId}
                      currentPseudonym={alias}
                      onCommentCountChange={(newCount) => {
                        setPosts((prev) =>
                          prev.map((item) =>
                            (item.post_id || item.id) === postId
                              ? { ...item, comments_count: newCount }
                              : item
                          )
                        );
                      }}
                    />
                  </div>
                )}
              </li>
            );
          })
        )}
      </ul>
    </section>
  );
}
