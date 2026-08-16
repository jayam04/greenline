import React from "react";

interface BauhausCardProps {
  children: React.ReactNode;
  className?: string;
  variant?: "white" | "red" | "blue" | "yellow" | "black";
  shape?: "circle" | "square" | "triangle" | "none";
  shadowSize?: "sm" | "md" | "lg";
}

export function BauhausCard({
  children,
  className = "",
  variant = "white",
  shape = "square",
  shadowSize = "lg",
}: BauhausCardProps) {
  const variantStyles = {
    white: "bg-white text-[#121212] border-4 border-[#121212]",
    red: "bg-[#D02020] text-white border-4 border-[#121212]",
    blue: "bg-[#1040C0] text-white border-4 border-[#121212]",
    yellow: "bg-[#F0C020] text-[#121212] border-4 border-[#121212]",
    black: "bg-[#121212] text-white border-4 border-[#121212]",
  };

  const shadowStyles = {
    sm: "shadow-bauhaus-sm",
    md: "shadow-bauhaus",
    lg: "shadow-bauhaus-lg",
  };

  return (
    <div
      className={`relative p-6 ${variantStyles[variant]} ${shadowStyles[shadowSize]} ${className}`}
    >
      {/* Decorative corner geometric shape */}
      {shape === "circle" && (
        <div className="absolute top-4 right-4 w-4 h-4 rounded-full bg-[#D02020] border-2 border-[#121212]" />
      )}
      {shape === "square" && (
        <div className="absolute top-4 right-4 w-4 h-4 rounded-none bg-[#1040C0] border-2 border-[#121212]" />
      )}
      {shape === "triangle" && (
        <div className="absolute top-4 right-4 w-4 h-4 clip-triangle bg-[#F0C020]" />
      )}
      {children}
    </div>
  );
}
