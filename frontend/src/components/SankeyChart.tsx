"use client";

import React, { useState, useMemo } from "react";
import { formatCurrency } from "@/lib/format";
import { useTheme } from "@/components/ThemeProvider";

export interface SankeyNode {
  id: string;
  name: string;
  category_type?: string | null;
  level: number;
  color?: string | null;
}

export interface SankeyLink {
  source: string;
  target: string;
  value: number;
  color?: string | null;
}

export interface SankeyData {
  nodes: SankeyNode[];
  links: SankeyLink[];
  total_income: number;
  total_expenses: number;
  total_investments: number;
  depth: number;
}

export type SankeyDataResponse = SankeyData;

interface SankeyChartProps {
  data: SankeyData | null;
  loading?: boolean;
  currency?: string;
}

export function SankeyChart({ data, loading = false, currency = "EUR" }: SankeyChartProps) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [hoveredLink, setHoveredLink] = useState<{ source: string; target: string; value: number } | null>(null);

  // Layout Dimensions
  const width = 1000;
  const height = 480;
  const paddingX = 60;
  const paddingY = 40;
  const nodeWidth = 20;

  // Compute Layout Positions
  const layout = useMemo(() => {
    if (!data || !data.nodes.length || !data.links.length) {
      return null;
    }

    const { nodes, links } = data;

    // 1. Group nodes by level (columns)
    const levelMap: { [level: number]: SankeyNode[] } = {};
    nodes.forEach((n) => {
      const lvl = n.level || 1;
      if (!levelMap[lvl]) levelMap[lvl] = [];
      levelMap[lvl].push(n);
    });

    const levels = Object.keys(levelMap)
      .map(Number)
      .sort((a, b) => a - b);
    const numLevels = levels.length;

    // 2. Compute total throughput value per node
    const nodeValues: { [id: string]: number } = {};
    nodes.forEach((n) => (nodeValues[n.id] = 0));

    links.forEach((l) => {
      nodeValues[l.source] = (nodeValues[l.source] || 0) + l.value;
      nodeValues[l.target] = (nodeValues[l.target] || 0) + l.value;
    });

    // Effective node value for sizing
    const getNodeVal = (id: string) => {
      const outVal = links.filter((l) => l.source === id).reduce((sum, l) => sum + l.value, 0);
      const inVal = links.filter((l) => l.target === id).reduce((sum, l) => sum + l.value, 0);
      return Math.max(outVal, inVal, 0.1);
    };

    // 3. Compute Column Heights & Scales
    const maxColumnSum = Math.max(
      ...levels.map((lvl) =>
        levelMap[lvl].reduce((acc, node) => acc + getNodeVal(node.id), 0)
      ),
      1
    );

    const availableHeight = height - paddingY * 2;
    const colSpacing = (width - paddingX * 2 - nodeWidth) / Math.max(numLevels - 1, 1);

    // Compute (x, y, h) for each node
    const computedNodes: { [id: string]: { x: number; y: number; width: number; height: number; value: number; node: SankeyNode } } = {};

    levels.forEach((lvl, colIndex) => {
      const colNodes = levelMap[lvl];
      const colTotalVal = colNodes.reduce((acc, node) => acc + getNodeVal(node.id), 0);
      const totalGaps = (colNodes.length - 1) * 14;
      const heightForNodes = Math.min(availableHeight - totalGaps, (colTotalVal / maxColumnSum) * availableHeight);
      const scale = colTotalVal > 0 ? heightForNodes / colTotalVal : 1;

      // Center column vertically
      const totalColHeight = colNodes.reduce((acc, node) => acc + Math.max(getNodeVal(node.id) * scale, 12), 0) + totalGaps;
      let startY = paddingY + (availableHeight - totalColHeight) / 2;

      colNodes.forEach((n) => {
        const val = getNodeVal(n.id);
        const nodeHeight = Math.max(val * scale, 14);
        const x = paddingX + colIndex * colSpacing;
        const y = startY;

        computedNodes[n.id] = {
          x,
          y,
          width: nodeWidth,
          height: nodeHeight,
          value: val,
          node: n,
        };

        startY += nodeHeight + 14;
      });
    });

    // 4. Compute Links with Source and Target Ribbon Y-Offsets
    const sourceOffsets: { [id: string]: number } = {};
    const targetOffsets: { [id: string]: number } = {};
    nodes.forEach((n) => {
      sourceOffsets[n.id] = 0;
      targetOffsets[n.id] = 0;
    });

    const computedLinks = links.map((l) => {
      const srcNode = computedNodes[l.source];
      const tgtNode = computedNodes[l.target];

      if (!srcNode || !tgtNode) return null;

      const srcScale = srcNode.height / Math.max(srcNode.value, 0.001);
      const tgtScale = tgtNode.height / Math.max(tgtNode.value, 0.001);

      const linkHeightSrc = Math.max(l.value * srcScale, 1.5);
      const linkHeightTgt = Math.max(l.value * tgtScale, 1.5);

      const y0 = srcNode.y + sourceOffsets[l.source];
      const y1 = tgtNode.y + targetOffsets[l.target];

      sourceOffsets[l.source] += linkHeightSrc;
      targetOffsets[l.target] += linkHeightTgt;

      const x0 = srcNode.x + srcNode.width;
      const x1 = tgtNode.x;
      const xi = (x0 + x1) / 2;

      // SVG smooth cubic bezier path
      const path = `
        M ${x0} ${y0}
        C ${xi} ${y0}, ${xi} ${y1}, ${x1} ${y1}
        L ${x1} ${y1 + linkHeightTgt}
        C ${xi} ${y1 + linkHeightTgt}, ${xi} ${y0 + linkHeightSrc}, ${x0} ${y0 + linkHeightSrc}
        Z
      `;

      return {
        ...l,
        path,
        srcNode,
        tgtNode,
        linkHeightSrc,
        linkHeightTgt,
      };
    }).filter(Boolean);

    return {
      nodes: Object.values(computedNodes),
      links: computedLinks,
    };
  }, [data]);

  if (loading) {
    return (
      <div className="w-full h-80 flex items-center justify-center bg-slate-50 rounded-2xl border border-slate-100">
        <div className="text-center space-y-2">
          <div className="w-6 h-6 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-xs font-bold text-slate-400">Computing Cashflow Sankey Ribbons...</p>
        </div>
      </div>
    );
  }

  if (!layout || !layout.links.length) {
    return (
      <div className="w-full h-80 flex flex-col items-center justify-center bg-slate-50/50 rounded-2xl border border-dashed border-slate-200 p-6 text-center">
        <div className="w-10 h-10 bg-slate-100 text-slate-400 rounded-full flex items-center justify-center mb-2">
          🌿
        </div>
        <h4 className="text-xs font-bold text-slate-700">No Cashflow Data Recorded</h4>
        <p className="text-[11px] text-slate-400 max-w-sm mt-1">
          Add your first salary, freelance invoice, or Amazon purchase to visualize your money flow.
        </p>
      </div>
    );
  }

  return (
    <div className="relative w-full overflow-hidden select-none">
      {/* Tooltip Overlay */}
      {hoveredLink && (
        <div className="absolute top-3 right-4 z-20 bg-[#0F172A] text-white text-[11px] font-bold px-3 py-1.5 rounded-lg shadow-lg flex items-center gap-2 border border-slate-700 pointer-events-none">
          <span className="text-emerald-400">{hoveredLink.source}</span>
          <span className="text-slate-400">➔</span>
          <span className="text-rose-300">{hoveredLink.target}</span>
          <span className="text-white bg-slate-800 px-1.5 py-0.5 rounded ml-1 font-bold">
            {formatCurrency(hoveredLink.value, currency)}
          </span>
        </div>
      )}

      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full h-auto max-h-[500px]"
        preserveAspectRatio="xMidYMid meet"
      >
        {/* Gradients */}
        <defs>
          {layout.links.map((link: any, idx) => {
            const gradId = `sankey-grad-${idx}`;
            const srcColor = link.srcNode.node.color || "#10B981";
            const tgtColor = link.tgtNode.node.color || link.color || "#EF4444";
            return (
              <linearGradient key={gradId} id={gradId} x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor={srcColor} stopOpacity="0.45" />
                <stop offset="100%" stopColor={tgtColor} stopOpacity="0.45" />
              </linearGradient>
            );
          })}
        </defs>

        {/* 1. Links (Flow Ribbons) */}
        <g className="links">
          {layout.links.map((link: any, idx) => {
            const isHovered =
              hoveredLink?.source === link.srcNode.node.name &&
              hoveredLink?.target === link.tgtNode.node.name;
            const isNodeRelated =
              hoveredNode === link.source || hoveredNode === link.target;
            const opacity = hoveredNode
              ? isNodeRelated
                ? 0.8
                : 0.1
              : isHovered
              ? 0.85
              : 0.45;

            return (
              <path
                key={`link-${idx}`}
                d={link.path}
                fill={`url(#sankey-grad-${idx})`}
                opacity={opacity}
                className="transition-all duration-200 cursor-pointer"
                onMouseEnter={() =>
                  setHoveredLink({
                    source: link.srcNode.node.name,
                    target: link.tgtNode.node.name,
                    value: link.value,
                  })
                }
                onMouseLeave={() => setHoveredLink(null)}
              />
            );
          })}
        </g>

        {/* 2. Nodes (Vertical Bars & Labels) */}
        <g className="nodes">
          {layout.nodes.map(({ x, y, width: nw, height: nh, value, node }) => {
            const isHovered = hoveredNode === node.id;
            const isLeft = x < width / 3;
            const isRight = x > (width * 2) / 3;
            const nodeColor = node.color || (node.category_type === "INCOME" ? "#10B981" : "#EF4444");

            return (
              <g
                key={node.id}
                className="cursor-pointer group"
                onMouseEnter={() => setHoveredNode(node.id)}
                onMouseLeave={() => setHoveredNode(null)}
              >
                {/* Rect Block */}
                <rect
                  x={x}
                  y={y}
                  width={nw}
                  height={nh}
                  rx={4}
                  fill={nodeColor}
                  stroke={isHovered ? "#0F172A" : "transparent"}
                  strokeWidth={2}
                  className="transition-all duration-150"
                />

                {/* Node Label Text */}
                <text
                  x={isLeft ? x - 8 : isRight ? x + nw + 8 : x + nw / 2}
                  y={y + nh / 2 - 3}
                  textAnchor={isLeft ? "end" : isRight ? "start" : "middle"}
                  dominantBaseline="central"
                  fill={isDark ? "#F8FAFC" : "#0F172A"}
                  className={`text-[11px] font-bold pointer-events-none transition-all ${
                    isHovered ? "font-extrabold" : ""
                  }`}
                >
                  {node.name}
                </text>

                {/* Amount Under Label */}
                <text
                  x={isLeft ? x - 8 : isRight ? x + nw + 8 : x + nw / 2}
                  y={y + nh / 2 + 10}
                  textAnchor={isLeft ? "end" : isRight ? "start" : "middle"}
                  dominantBaseline="central"
                  fill={isDark ? "#94A3B8" : "#64748B"}
                  className="text-[10px] font-semibold tabular-nums pointer-events-none"
                >
                  {formatCurrency(value, currency)}
                </text>
              </g>
            );
          })}
        </g>
      </svg>
    </div>
  );
}
