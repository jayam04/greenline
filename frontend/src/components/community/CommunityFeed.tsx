"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Users,
  RefreshCw,
  Sparkles,
  ArrowUpDown,
  MessageSquareDashed,
  AlertCircle,
} from "lucide-react";
import { PostComposer } from "./PostComposer";
import { PostCard } from "./PostCard";
import {
  fetchPosts,
  getSavedCommunityPseudonym,
  saveCommunityPseudonymLocally,
  PostResponse,
} from "@/lib/community";

interface CommunityFeedProps {
  currentPseudonym?: string;
  onPseudonymChange?: (newPseudonym: string) => void;
  className?: string;
}

export function CommunityFeed({
  currentPseudonym: propPseudonym,
  onPseudonymChange,
  className = "",
}: CommunityFeedProps) {
  const [posts, setPosts] = useState<PostResponse[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [sortOrder, setSortOrder] = useState<"latest" | "oldest">("latest");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [activePseudonym, setActivePseudonym] = useState(
    propPseudonym || getSavedCommunityPseudonym() || ""
  );

  const loadFeed = useCallback(
    async (isManualRefresh = false) => {
      try {
        if (isManualRefresh) setRefreshing(true);
        else setLoading(true);
        setError(null);

        const data = await fetchPosts({ limit: 50, offset: 0, sort: sortOrder });
        setPosts(data?.items || []);
        setTotalCount(data?.total_count ?? (data?.items ? data.items.length : 0));
      } catch (err: any) {
        console.error("Failed to fetch community posts:", err);
        setError(err?.message || "Failed to load community feed");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [sortOrder]
  );

  useEffect(() => {
    loadFeed();
  }, [loadFeed]);

  const handlePseudonymChange = (newPseudo: string) => {
    setActivePseudonym(newPseudo);
    saveCommunityPseudonymLocally(newPseudo);
    onPseudonymChange?.(newPseudo);
  };

  const handlePostCreated = (newPost: PostResponse) => {
    setPosts((prev) => [newPost, ...prev]);
    setTotalCount((prev) => prev + 1);
  };

  const handlePostDeleted = (deletedPostId: number) => {
    setPosts((prev) => prev.filter((p) => p.post_id !== deletedPostId));
    setTotalCount((prev) => Math.max(0, prev - 1));
  };

  return (
    <div className={`space-y-4 font-sans ${className}`}>
      {/* Feed Section Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-2.5">
          <div className="p-2 bg-purple-50 dark:bg-purple-950/40 text-purple-600 rounded-xl">
            <Users className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-[#0F172A] dark:text-white">
                Community Insights & Feed
              </h2>
              <span className="px-2 py-0.5 text-[10px] font-extrabold uppercase bg-purple-50 dark:bg-purple-950/50 text-purple-700 dark:text-purple-300 rounded-full border border-purple-200 dark:border-purple-800">
                Live
              </span>
            </div>
            <p className="text-[11px] font-medium text-slate-400">
              Share portfolio ideas, discuss trade thesis, and learn with peers anonymously
            </p>
          </div>
        </div>

        {/* Action Controls: Sort & Refresh */}
        <div className="flex items-center gap-2 self-start sm:self-auto">
          {/* Sort Switcher */}
          <div className="flex items-center bg-slate-100 dark:bg-[#1A2333] p-0.5 rounded-lg border border-slate-200/70 dark:border-slate-800 text-xs">
            <button
              type="button"
              onClick={() => setSortOrder("latest")}
              className={`px-2.5 py-1 text-[11px] font-bold rounded-md transition-all cursor-pointer ${
                sortOrder === "latest"
                  ? "bg-white dark:bg-[#0E1522] text-[#0F172A] dark:text-white shadow-xs"
                  : "text-slate-500 hover:text-slate-900 dark:hover:text-white"
              }`}
            >
              Latest
            </button>
            <button
              type="button"
              onClick={() => setSortOrder("oldest")}
              className={`px-2.5 py-1 text-[11px] font-bold rounded-md transition-all cursor-pointer ${
                sortOrder === "oldest"
                  ? "bg-white dark:bg-[#0E1522] text-[#0F172A] dark:text-white shadow-xs"
                  : "text-slate-500 hover:text-slate-900 dark:hover:text-white"
              }`}
            >
              Oldest
            </button>
          </div>

          {/* Refresh Button */}
          <button
            type="button"
            onClick={() => loadFeed(true)}
            disabled={refreshing || loading}
            className="p-1.5 text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors cursor-pointer"
            title="Refresh Community Feed"
          >
            <RefreshCw
              className={`w-4 h-4 ${refreshing ? "animate-spin text-purple-600" : ""}`}
            />
          </button>
        </div>
      </div>

      {/* Post Composer Card */}
      <PostComposer
        currentPseudonym={activePseudonym}
        onPseudonymChange={handlePseudonymChange}
        onPostCreated={handlePostCreated}
      />

      {/* Feed Content */}
      {error && (
        <div className="flex items-center justify-between p-3.5 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 rounded-xl text-xs text-rose-700 dark:text-rose-300">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4" />
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={() => loadFeed(true)}
            className="font-bold underline hover:no-underline cursor-pointer"
          >
            Retry
          </button>
        </div>
      )}

      {loading ? (
        <div className="space-y-3 py-4">
          {[1, 2].map((i) => (
            <div
              key={i}
              className="bg-white dark:bg-[#151D2B] rounded-2xl border border-slate-200 dark:border-slate-800 p-5 space-y-3 animate-pulse"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-full bg-slate-200 dark:bg-slate-700" />
                <div className="space-y-1">
                  <div className="w-24 h-3 bg-slate-200 dark:bg-slate-700 rounded" />
                  <div className="w-16 h-2 bg-slate-100 dark:bg-slate-800 rounded" />
                </div>
              </div>
              <div className="w-full h-12 bg-slate-100 dark:bg-slate-800 rounded-lg" />
            </div>
          ))}
        </div>
      ) : posts.length === 0 ? (
        <div className="bg-white dark:bg-[#151D2B] rounded-2xl border border-dashed border-slate-200 dark:border-slate-800 p-8 text-center space-y-2">
          <div className="w-10 h-10 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-400 mx-auto flex items-center justify-center">
            <MessageSquareDashed className="w-5 h-5" />
          </div>
          <h3 className="text-sm font-bold text-[#0F172A] dark:text-white">No posts yet</h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto">
            Be the first to share your market insights, strategy reflections, or ask a question!
          </p>
        </div>
      ) : (
        <div className="space-y-3.5">
          {posts.map((post) => (
            <PostCard
              key={post.post_id}
              post={post}
              currentPseudonym={activePseudonym}
              onPostDeleted={handlePostDeleted}
            />
          ))}
        </div>
      )}
    </div>
  );
}
