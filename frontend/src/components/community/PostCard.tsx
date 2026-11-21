"use client";

import React, { useState } from "react";
import {
  MessageSquare,
  Share2,
  Trash2,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Image as ImageIcon,
  Paperclip,
} from "lucide-react";
import { MarkdownContent } from "./MarkdownContent";
import { CommentThread } from "./CommentThread";
import { PostResponse, deletePost } from "@/lib/community";

interface PostCardProps {
  post: PostResponse;
  currentPseudonym?: string;
  onPostDeleted?: (postId: number) => void;
}

export function PostCard({ post, currentPseudonym, onPostDeleted }: PostCardProps) {
  const [showComments, setShowComments] = useState(false);
  const [commentsCount, setCommentsCount] = useState(post.comments_count);
  const [deleting, setDeleting] = useState(false);

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

  const handleDelete = async () => {
    if (!confirm("Are you sure you want to delete this post?")) return;
    try {
      setDeleting(true);
      await deletePost(post.post_id);
      onPostDeleted?.(post.post_id);
    } catch (err: any) {
      alert(err?.message || "Failed to delete post");
    } finally {
      setDeleting(false);
    }
  };

  const authorInitial = (post.author_pseudonym || "A").charAt(0).toUpperCase();

  return (
    <div className="bg-white dark:bg-[#151D2B] rounded-2xl border border-slate-200 dark:border-slate-800 p-4 sm:p-5 shadow-xs font-sans transition-all space-y-3">
      {/* Post Header: Author Pseudonym & Timestamp */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 font-bold text-xs flex items-center justify-center border border-slate-200 dark:border-slate-700">
            {authorInitial}
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-bold text-[#0F172A] dark:text-white">
                @{post.author_pseudonym || "anonymous"}
              </span>
              <span className="text-[10px] text-slate-400 font-medium">
                • {formatTimestamp(post.created_at)}
              </span>
            </div>
          </div>
        </div>

        {/* Delete button (if current user matches pseudonym or for moderation) */}
        {currentPseudonym &&
          post.author_pseudonym &&
          currentPseudonym.toLowerCase() === post.author_pseudonym.toLowerCase() && (
            <button
              type="button"
              onClick={handleDelete}
              disabled={deleting}
              className="text-slate-400 hover:text-rose-600 p-1.5 rounded-lg hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-colors cursor-pointer"
              title="Delete this post"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
      </div>

      {/* Post Body (Markdown Content) */}
      <div className="pt-1">
        <MarkdownContent content={post.content} />
      </div>

      {/* Media Attachments Preview */}
      {post.media_attachments && post.media_attachments.length > 0 && (
        <div className="pt-1 space-y-2">
          {post.media_attachments.map((media, idx) => {
            if (media.type === "image") {
              return (
                <div key={idx} className="relative rounded-xl overflow-hidden border border-slate-200 dark:border-slate-800 max-h-80 bg-slate-50 dark:bg-slate-900">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={media.url}
                    alt={media.name || "post attachment"}
                    className="w-full object-contain max-h-80"
                    loading="lazy"
                  />
                  {media.name && (
                    <div className="absolute bottom-2 left-2 bg-slate-900/70 backdrop-blur-xs text-white text-[10px] px-2 py-0.5 rounded-md">
                      {media.name}
                    </div>
                  )}
                </div>
              );
            }
            return (
              <a
                key={idx}
                href={media.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/60 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors text-xs font-semibold text-blue-600 dark:text-blue-400"
              >
                <Paperclip className="w-3.5 h-3.5 shrink-0" />
                <span className="truncate flex-1">{media.name || media.url}</span>
                <ExternalLink className="w-3.5 h-3.5 shrink-0 text-slate-400" />
              </a>
            );
          })}
        </div>
      )}

      {/* Post Footer: Comment Toggle & Share */}
      <div className="flex items-center justify-between pt-2 border-t border-slate-100 dark:border-slate-800/80 text-xs text-slate-500">
        <button
          type="button"
          onClick={() => setShowComments(!showComments)}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg transition-colors cursor-pointer font-bold ${
            showComments
              ? "bg-slate-100 dark:bg-slate-800 text-[#0F172A] dark:text-white"
              : "hover:bg-slate-50 dark:hover:bg-slate-800/60 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          <MessageSquare className="w-3.5 h-3.5" />
          <span>{commentsCount} comments</span>
          {showComments ? (
            <ChevronUp className="w-3 h-3 ml-0.5" />
          ) : (
            <ChevronDown className="w-3 h-3 ml-0.5" />
          )}
        </button>
      </div>

      {/* Expandable Comments Thread */}
      {showComments && (
        <CommentThread
          postId={post.post_id}
          currentPseudonym={currentPseudonym}
          onCommentCountChange={(count) => setCommentsCount(count)}
        />
      )}
    </div>
  );
}
