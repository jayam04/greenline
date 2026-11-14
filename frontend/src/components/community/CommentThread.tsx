"use client";

import React, { useState, useEffect, useRef } from "react";
import { Send, CornerDownRight, Reply, X, MessageSquare, AlertCircle } from "lucide-react";
import { MarkdownContent } from "./MarkdownContent";
import {
  fetchComments,
  createComment,
  getSavedCommunityPseudonym,
  CommentResponse,
} from "@/lib/community";

interface CommentThreadProps {
  postId: number;
  currentPseudonym?: string;
  onCommentCountChange?: (newCount: number) => void;
}

export function CommentThread({
  postId,
  currentPseudonym: propPseudonym,
  onCommentCountChange,
}: CommentThreadProps) {
  const [comments, setComments] = useState<CommentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [content, setContent] = useState("");
  const [replyingTo, setReplyingTo] = useState<CommentResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const countCallbackRef = useRef(onCommentCountChange);
  useEffect(() => {
    countCallbackRef.current = onCommentCountChange;
  });

  const activePseudonym = propPseudonym || getSavedCommunityPseudonym() || "anonymous";

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        setLoading(true);
        const data = await fetchComments(postId);
        if (mounted) {
          setComments(data || []);
          countCallbackRef.current?.(data?.length || 0);
        }
      } catch (err: any) {
        if (mounted) {
          console.error("Failed to load comments:", err);
          setError("Failed to load comments");
        }
      } finally {
        if (mounted) setLoading(false);
      }
    };
    load();
    return () => {
      mounted = false;
    };
  }, [postId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = content.trim();
    if (!trimmed || submitting) return;

    try {
      setSubmitting(true);
      setError(null);

      const created = await createComment(postId, {
        content: trimmed,
        parent_comment_id: replyingTo ? replyingTo.comment_id : null,
        author_pseudonym: activePseudonym,
      });

      setComments((prev) => [...prev, created]);
      setContent("");
      setReplyingTo(null);
      onCommentCountChange?.(comments.length + 1);
    } catch (err: any) {
      setError(err?.message || "Failed to submit comment");
    } finally {
      setSubmitting(false);
    }
  };

  const formatTimestamp = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateStr;
    }
  };

  // Group comments: top-level vs child comments
  const topLevel = comments.filter((c) => !c.parent_comment_id);
  const repliesMap = new Map<number, CommentResponse[]>();
  comments.forEach((c) => {
    if (c.parent_comment_id) {
      const existing = repliesMap.get(c.parent_comment_id) || [];
      existing.push(c);
      repliesMap.set(c.parent_comment_id, existing);
    }
  });

  return (
    <div className="pt-3 border-t border-slate-100 dark:border-slate-800 space-y-3 font-sans">
      {/* Inline Comments List */}
      {loading ? (
        <div className="text-center py-4 text-xs text-slate-400">Loading replies...</div>
      ) : comments.length === 0 ? (
        <div className="text-center py-3 text-xs text-slate-400">
          No replies yet. Be the first to join the conversation!
        </div>
      ) : (
        <div className="space-y-2.5">
          {topLevel.map((comment) => (
            <div key={comment.comment_id} className="space-y-2">
              {/* Comment Card */}
              <div className="bg-slate-50 dark:bg-[#0E1522] rounded-xl p-3 border border-slate-100 dark:border-slate-800/80">
                <div className="flex items-center justify-between pb-1.5">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-bold text-[#0F172A] dark:text-white">
                      @{comment.author_pseudonym || "anonymous"}
                    </span>
                    <span className="text-[10px] text-slate-400">
                      • {formatTimestamp(comment.created_at)}
                    </span>
                  </div>

                  <button
                    type="button"
                    onClick={() => setReplyingTo(comment)}
                    className="text-[11px] font-semibold text-slate-500 hover:text-slate-900 dark:hover:text-white flex items-center gap-1 cursor-pointer"
                  >
                    <Reply className="w-3 h-3" />
                    <span>Reply</span>
                  </button>
                </div>

                <MarkdownContent content={comment.content} />
              </div>

              {/* Nested replies if any */}
              {repliesMap.get(comment.comment_id)?.map((reply) => (
                <div
                  key={reply.comment_id}
                  className="ml-6 pl-3 border-l-2 border-slate-200 dark:border-slate-700 bg-slate-50/70 dark:bg-[#0E1522]/60 rounded-xl p-2.5"
                >
                  <div className="flex items-center justify-between pb-1">
                    <div className="flex items-center gap-1.5">
                      <CornerDownRight className="w-3 h-3 text-slate-400" />
                      <span className="text-xs font-bold text-[#0F172A] dark:text-white">
                        @{reply.author_pseudonym || "anonymous"}
                      </span>
                      <span className="text-[10px] text-slate-400">
                        • {formatTimestamp(reply.created_at)}
                      </span>
                    </div>
                  </div>
                  <MarkdownContent content={reply.content} />
                </div>
              ))}
            </div>
          ))}
        </div>
      )}

      {/* Reply Submission Form */}
      <form onSubmit={handleSubmit} className="space-y-2 pt-1">
        {replyingTo && (
          <div className="flex items-center justify-between px-2.5 py-1 bg-blue-50 dark:bg-blue-950/40 rounded-lg text-xs font-semibold text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-900">
            <span className="flex items-center gap-1 truncate">
              <CornerDownRight className="w-3.5 h-3.5 shrink-0" />
              Replying to @{replyingTo.author_pseudonym || "anonymous"}
            </span>
            <button
              type="button"
              onClick={() => setReplyingTo(null)}
              className="p-0.5 hover:text-rose-600 cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        <div className="flex items-center gap-2">
          <input
            type="text"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder={
              replyingTo
                ? `Reply to @${replyingTo.author_pseudonym}...`
                : "Write a reply to this post..."
            }
            className="flex-1 bg-white dark:bg-[#151D2B] text-xs font-medium text-slate-900 dark:text-white placeholder-slate-400 px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 focus:outline-none focus:border-slate-400"
          />
          <button
            type="submit"
            disabled={!content.trim() || submitting}
            className="btn-pill-black text-xs px-3 py-2 cursor-pointer flex items-center gap-1 disabled:opacity-50"
            aria-label="Submit Reply"
          >
            <Send className="w-3 h-3" />
            <span>Post Reply</span>
          </button>
        </div>

        {error && (
          <div className="text-[11px] font-semibold text-rose-600 flex items-center gap-1">
            <AlertCircle className="w-3 h-3" />
            <span>{error}</span>
          </div>
        )}
      </form>
    </div>
  );
}
