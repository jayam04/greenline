"use client";

import React, { ReactNode } from "react";

interface MarkdownContentProps {
  content: string;
  className?: string;
}

/**
 * Checks if a URL is safe to render as an anchor href (only http, https, or relative paths).
 */
function isSafeUrl(url: string): boolean {
  if (!url) return false;
  const trimmed = url.trim().toLowerCase();
  return trimmed.startsWith("http://") || trimmed.startsWith("https://") || trimmed.startsWith("/");
}

/**
 * Parses inline formatting: bold, italic, strikethrough, inline code, and links.
 */
function parseInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  // Regex to match code, links, bold, italic, strikethrough
  // Tokenizer pattern:
  // 1: Inline code: `([^`]+)`
  // 2: Link: \[([^\]]+)\]\(([^)]+)\)
  // 3: Bold: \*\*([^*]+)\*\* or __([^_]+)__
  // 4: Italic: \*([^*]+)\* or _([^_]+)_
  // 5: Strikethrough: ~~([^~]+)~~
  const regex = /(`([^`]+)`)|(\[([^\]]+)\]\(([^)]+)\))|(\*\*([^*]+)\*\*|__([^_]+)__)|(\*([^*]+)\*|_([^_]+)_)|(~~([^~]+)~~)/g;

  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let index = 0;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }

    const key = `${keyPrefix}-${index++}`;

    if (match[1]) {
      // Inline code
      nodes.push(
        <code
          key={key}
          className="bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 px-1.5 py-0.5 rounded text-xs font-mono font-semibold"
        >
          {match[2]}
        </code>
      );
    } else if (match[3]) {
      // Link: [text](url)
      const linkText = match[4];
      const linkUrl = match[5];
      if (isSafeUrl(linkUrl)) {
        nodes.push(
          <a
            key={key}
            href={linkUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 dark:text-blue-400 font-semibold hover:underline"
          >
            {linkText}
          </a>
        );
      } else {
        nodes.push(linkText);
      }
    } else if (match[6]) {
      // Bold: **text** or __text__
      const boldText = match[7] || match[8];
      nodes.push(
        <strong key={key} className="font-bold text-[#0F172A] dark:text-white">
          {boldText}
        </strong>
      );
    } else if (match[9]) {
      // Italic: *text* or _text_
      const italicText = match[10] || match[11];
      nodes.push(<em key={key}>{italicText}</em>);
    } else if (match[12]) {
      // Strikethrough: ~~text~~
      nodes.push(<del key={key}>{match[13]}</del>);
    }

    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes;
}

/**
 * Safe renderer for formatted Markdown text content.
 * Avoids dangerouslySetInnerHTML by compiling markdown AST nodes directly into React JSX.
 */
export function MarkdownContent({ content, className = "" }: MarkdownContentProps) {
  if (!content) return null;

  const lines = content.split("\n");
  const elements: ReactNode[] = [];
  let inCodeBlock = false;
  let codeBlockLines: string[] = [];
  let codeBlockLang = "";

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Handle code blocks ```
    if (line.trim().startsWith("```")) {
      if (inCodeBlock) {
        // End code block
        elements.push(
          <pre
            key={`code-${i}`}
            className="p-3 my-2 bg-slate-900 text-slate-100 rounded-xl text-xs font-mono overflow-x-auto"
          >
            <code>{codeBlockLines.join("\n")}</code>
          </pre>
        );
        inCodeBlock = false;
        codeBlockLines = [];
        codeBlockLang = "";
      } else {
        inCodeBlock = true;
        codeBlockLang = line.trim().slice(3).trim();
      }
      continue;
    }

    if (inCodeBlock) {
      codeBlockLines.push(line);
      continue;
    }

    // Handle empty lines as spacing
    if (!line.trim()) {
      elements.push(<div key={`empty-${i}`} className="h-2" />);
      continue;
    }

    // Headings
    if (line.startsWith("# ")) {
      elements.push(
        <h1
          key={`h1-${i}`}
          className="text-base font-extrabold text-[#0F172A] dark:text-white mt-2 mb-1"
        >
          {parseInline(line.slice(2), `h1-${i}`)}
        </h1>
      );
      continue;
    }
    if (line.startsWith("## ")) {
      elements.push(
        <h2
          key={`h2-${i}`}
          className="text-sm font-bold text-[#0F172A] dark:text-white mt-2 mb-1"
        >
          {parseInline(line.slice(3), `h2-${i}`)}
        </h2>
      );
      continue;
    }
    if (line.startsWith("### ")) {
      elements.push(
        <h3
          key={`h3-${i}`}
          className="text-xs font-bold text-[#0F172A] dark:text-white mt-1.5 mb-0.5"
        >
          {parseInline(line.slice(4), `h3-${i}`)}
        </h3>
      );
      continue;
    }

    // Blockquote
    if (line.startsWith("> ")) {
      elements.push(
        <blockquote
          key={`quote-${i}`}
          className="border-l-4 border-slate-300 dark:border-slate-700 pl-3 py-1 my-1 italic text-slate-600 dark:text-slate-400 text-xs bg-slate-50/50 dark:bg-slate-900/30 rounded-r"
        >
          {parseInline(line.slice(2), `quote-${i}`)}
        </blockquote>
      );
      continue;
    }

    // Unordered list
    if (line.trim().startsWith("- ") || line.trim().startsWith("* ")) {
      const listContent = line.trim().slice(2);
      elements.push(
        <li
          key={`li-${i}`}
          className="ml-4 list-disc text-xs text-slate-700 dark:text-slate-300"
        >
          {parseInline(listContent, `li-${i}`)}
        </li>
      );
      continue;
    }

    // Ordered list
    const orderedMatch = line.trim().match(/^(\d+)\.\s+(.*)$/);
    if (orderedMatch) {
      elements.push(
        <li
          key={`oli-${i}`}
          className="ml-4 list-decimal text-xs text-slate-700 dark:text-slate-300"
        >
          {parseInline(orderedMatch[2], `oli-${i}`)}
        </li>
      );
      continue;
    }

    // Normal paragraph
    elements.push(
      <p
        key={`p-${i}`}
        className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed"
      >
        {parseInline(line, `p-${i}`)}
      </p>
    );
  }

  return <div className={`space-y-1 ${className}`}>{elements}</div>;
}
