import React from "react";

interface LimeCardProps {
  children: React.ReactNode;
  className?: string;
  variant?: "hero-lime" | "white" | "dark" | "lime-light";
}

export function LimeCard({
  children,
  className = "",
  variant = "white",
}: LimeCardProps) {
  const variantStyles = {
    "hero-lime": "bg-[#9FE837] text-[#0F172A] rounded-3xl border border-[#8BD428]/40 shadow-[0_10px_25px_-5px_rgba(159,232,55,0.3)]",
    white: "bg-white text-[#0F172A] rounded-3xl border border-slate-200/80 shadow-[0_8px_30px_rgb(0,0,0,0.03)]",
    dark: "bg-[#0F172A] text-white rounded-3xl border border-slate-800 shadow-[0_10px_30px_rgb(0,0,0,0.15)]",
    "lime-light": "bg-[#F7FEE7] text-[#0F172A] rounded-3xl border border-[#A3E635]/40 shadow-sm",
  };

  return (
    <div className={`p-6 transition-all ${variantStyles[variant]} ${className}`}>
      {children}
    </div>
  );
}
