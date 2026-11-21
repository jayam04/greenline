"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  Bold,
  Italic,
  Code,
  Link as LinkIcon,
  Quote,
  List,
  Image as ImageIcon,
  Send,
  Sparkles,
  X,
  Paperclip,
  Check,
  AlertCircle,
} from "lucide-react";
import {
  createPost,
  fetchRandomPseudonym,
  getSavedCommunityPseudonym,
  saveCommunityPseudonymLocally,
  MediaAttachment,
  PostResponse,
} from "@/lib/community";

interface PostComposerProps {
  onPostCreated?: (post: PostResponse) => void;
  currentPseudonym?: string;
  onPseudonymChange?: (newPseudonym: string) => void;
}

export function PostComposer({
  onPostCreated,
  currentPseudonym: initialPseudonym,
  onPseudonymChange,
}: PostComposerProps) {
  const [content, setContent] = useState("");
  const [authorPseudonym, setAuthorPseudonym] = useState(initialPseudonym || "");
  const [mediaAttachments, setMediaAttachments] = useState<MediaAttachment[]>([]);
  const [showMediaInput, setShowMediaInput] = useState(false);
  const [mediaUrlInput, setMediaUrlInput] = useState("");
  const [mediaNameInput, setMediaNameInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [randomizing, setRandomizing] = useState(false);

  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Sync initial pseudonym from props or localStorage
  useEffect(() => {
    if (initialPseudonym) {
      setAuthorPseudonym(initialPseudonym);
    } else {
      const saved = getSavedCommunityPseudonym();
      if (saved) {
        setAuthorPseudonym(saved);
      } else {
        // Fetch or generate random pseudonym
        Promise.resolve(fetchRandomPseudonym())
          .then((res) => {
            if (res && res.pseudonym) {
              setAuthorPseudonym(res.pseudonym);
              saveCommunityPseudonymLocally(res.pseudonym);
              onPseudonymChange?.(res.pseudonym);
            }
          })
          .catch(() => {});
      }
    }
  }, [initialPseudonym, onPseudonymChange]);

  const handleRandomizePseudonym = async () => {
    try {
      setRandomizing(true);
      const res = await fetchRandomPseudonym();
      if (res && res.pseudonym) {
        setAuthorPseudonym(res.pseudonym);
        saveCommunityPseudonymLocally(res.pseudonym);
        onPseudonymChange?.(res.pseudonym);
      }
    } catch {
      // ignore
    } finally {
      setRandomizing(false);
    }
  };

  const insertFormatting = (prefix: string, suffix: string, defaultText: string) => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selectedText = content.substring(start, end) || defaultText;
    const replacement = `${prefix}${selectedText}${suffix}`;

    const newContent = content.substring(0, start) + replacement + content.substring(end);
    setContent(newContent);

    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(start + prefix.length, start + prefix.length + selectedText.length);
    }, 10);
  };

  const handleAddMedia = (e: React.FormEvent) => {
    e.preventDefault();
    const url = mediaUrlInput.trim();
    if (!url) return;

    const isImage = /\.(jpeg|jpg|gif|png|webp|svg)($|\?)/i.test(url) || url.includes("image");
    const name = mediaNameInput.trim() || url.split("/").pop()?.split("?")[0] || "Attachment";

    const newAttachment: MediaAttachment = {
      url,
      type: isImage ? "image" : "link",
      name,
    };

    setMediaAttachments((prev) => [...prev, newAttachment]);
    setMediaUrlInput("");
    setMediaNameInput("");
    setShowMediaInput(false);
  };

  const handleRemoveMedia = (index: number) => {
    setMediaAttachments((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = content.trim();
    if (!trimmed || submitting) return;

    try {
      setSubmitting(true);
      setError(null);

      const post = await createPost({
        content: trimmed,
        author_pseudonym: authorPseudonym || undefined,
        media_attachments: mediaAttachments.length > 0 ? mediaAttachments : undefined,
      });

      setContent("");
      setMediaAttachments([]);
      setShowMediaInput(false);
      onPostCreated?.(post);
    } catch (err: any) {
      setError(err?.message || "Failed to create post. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="bg-white dark:bg-[#151D2B] rounded-2xl border border-slate-200 dark:border-slate-800 p-4 shadow-xs font-sans transition-all">
      {/* Header with Author Pseudonym & Randomize */}
      <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-100 dark:border-slate-800/80">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 font-bold text-xs flex items-center justify-center border border-emerald-200 dark:border-emerald-800">
            {authorPseudonym ? authorPseudonym.charAt(0).toUpperCase() : "U"}
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-bold text-[#0F172A] dark:text-white">
                @{authorPseudonym || "anonymous"}
              </span>
              <span className="text-[10px] uppercase font-extrabold bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 px-1.5 py-0.2 rounded">
                Author
              </span>
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={handleRandomizePseudonym}
          disabled={randomizing}
          className="text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white text-[11px] font-semibold flex items-center gap-1 px-2 py-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
          title="Pick a different random pseudonym"
        >
          <Sparkles className={`w-3.5 h-3.5 text-amber-500 ${randomizing ? "animate-spin" : ""}`} />
          <span className="hidden sm:inline">Randomize</span>
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3">
        {/* Rich Text Area */}
        <textarea
          ref={textareaRef}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Share an insight, trade review, or financial update with the community..."
          rows={3}
          className="w-full bg-slate-50 dark:bg-[#0E1522] text-xs font-medium text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 p-3 rounded-xl border border-slate-200 dark:border-slate-800 focus:border-slate-400 dark:focus:border-slate-600 focus:outline-none resize-y min-h-[75px]"
        />

        {/* Media Attachments Preview List */}
        {mediaAttachments.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-1">
            {mediaAttachments.map((att, idx) => (
              <div
                key={idx}
                className="flex items-center gap-2 pl-2.5 pr-1.5 py-1 bg-slate-100 dark:bg-slate-800 rounded-lg text-xs font-semibold text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700"
              >
                {att.type === "image" ? (
                  <ImageIcon className="w-3.5 h-3.5 text-blue-500" />
                ) : (
                  <Paperclip className="w-3.5 h-3.5 text-slate-500" />
                )}
                <span className="max-w-[150px] truncate text-[11px]">{att.name || att.url}</span>
                <button
                  type="button"
                  onClick={() => handleRemoveMedia(idx)}
                  className="p-0.5 hover:text-rose-600 rounded cursor-pointer"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Inline Media Input Drawer */}
        {showMediaInput && (
          <div className="p-3 bg-slate-50 dark:bg-[#0E1522] rounded-xl border border-slate-200 dark:border-slate-800 space-y-2">
            <div className="text-[11px] font-bold text-slate-700 dark:text-slate-300">
              Attach Image or Media Link
            </div>
            <div className="flex flex-col sm:flex-row gap-2">
              <input
                type="url"
                value={mediaUrlInput}
                onChange={(e) => setMediaUrlInput(e.target.value)}
                placeholder="Enter image or media URL (https://...)"
                className="flex-1 px-3 py-1.5 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-[#151D2B] text-slate-900 dark:text-white focus:outline-none"
              />
              <input
                type="text"
                value={mediaNameInput}
                onChange={(e) => setMediaNameInput(e.target.value)}
                placeholder="Optional label / name"
                className="w-full sm:w-36 px-3 py-1.5 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-[#151D2B] text-slate-900 dark:text-white focus:outline-none"
              />
              <div className="flex gap-1.5">
                <button
                  type="button"
                  onClick={handleAddMedia}
                  className="btn-pill-black text-xs px-3 py-1.5 cursor-pointer whitespace-nowrap"
                >
                  Add Attachment
                </button>
                <button
                  type="button"
                  onClick={() => setShowMediaInput(false)}
                  className="px-2.5 py-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 cursor-pointer"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Error notification */}
        {error && (
          <div className="flex items-center gap-1.5 text-xs font-semibold text-rose-600 bg-rose-50 dark:bg-rose-950/40 px-3 py-1.5 rounded-lg border border-rose-200 dark:border-rose-900">
            <AlertCircle className="w-3.5 h-3.5" />
            <span>{error}</span>
          </div>
        )}

        {/* Toolbar & Action Footer */}
        <div className="flex items-center justify-between pt-1 flex-wrap gap-2">
          {/* Formatting Shortcuts */}
          <div className="flex items-center gap-0.5 text-slate-500 dark:text-slate-400">
            <button
              type="button"
              title="Bold"
              onClick={() => insertFormatting("**", "**", "bold text")}
              className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg hover:text-slate-900 dark:hover:text-white transition-colors cursor-pointer"
            >
              <Bold className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              title="Italic"
              onClick={() => insertFormatting("*", "*", "italic text")}
              className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg hover:text-slate-900 dark:hover:text-white transition-colors cursor-pointer"
            >
              <Italic className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              title="Code"
              onClick={() => insertFormatting("`", "`", "code")}
              className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg hover:text-slate-900 dark:hover:text-white transition-colors cursor-pointer"
            >
              <Code className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              title="Quote"
              onClick={() => insertFormatting("> ", "", "quote")}
              className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg hover:text-slate-900 dark:hover:text-white transition-colors cursor-pointer"
            >
              <Quote className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              title="List"
              onClick={() => insertFormatting("- ", "", "item")}
              className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg hover:text-slate-900 dark:hover:text-white transition-colors cursor-pointer"
            >
              <List className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              title="Attach Media"
              onClick={() => setShowMediaInput(!showMediaInput)}
              className={`p-1.5 rounded-lg transition-colors cursor-pointer flex items-center gap-1 text-[11px] font-semibold ${
                showMediaInput
                  ? "bg-slate-200 dark:bg-slate-700 text-slate-900 dark:text-white"
                  : "hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-white"
              }`}
            >
              <ImageIcon className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Media</span>
            </button>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={!content.trim() || submitting}
            className="btn-pill-black text-xs px-4 py-1.5 cursor-pointer flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send className="w-3.5 h-3.5" />
            <span>{submitting ? "Posting..." : "Share"}</span>
          </button>
        </div>
      </form>
    </div>
  );
}
