import React from "react";
import { TrendingDown, TrendingUp, Minus } from "lucide-react";
import { cn } from "../../lib/utils";

export interface KPICardProps {
  title: string;
  value: string | number;
  change?: string;
  changeDirection?: "up" | "down" | "neutral";
  subtitle?: string;
  icon?: React.ReactNode;
  className?: string;
}

export function KPICard({
  title,
  value,
  change,
  changeDirection = "neutral",
  subtitle,
  icon,
  className,
}: KPICardProps) {
  return (
    <div
      className={cn(
        "p-5 bg-white rounded-xl border border-gray-200 shadow-sm flex flex-col justify-between",
        className
      )}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
          {title}
        </span>
        {icon && <div className="text-gray-400 p-2 bg-gray-50 rounded-lg">{icon}</div>}
      </div>

      <div className="mt-3">
        <div className="text-2xl font-bold text-gray-900 tracking-tight">{value}</div>
        {(change || subtitle) && (
          <div className="mt-1 flex items-center gap-1.5 text-xs">
            {change && (
              <span
                className={cn(
                  "inline-flex items-center font-medium",
                  changeDirection === "up" && "text-emerald-600",
                  changeDirection === "down" && "text-red-600",
                  changeDirection === "neutral" && "text-gray-500"
                )}
              >
                {changeDirection === "up" && <TrendingUp className="w-3.5 h-3.5 mr-0.5" />}
                {changeDirection === "down" && <TrendingDown className="w-3.5 h-3.5 mr-0.5" />}
                {changeDirection === "neutral" && <Minus className="w-3.5 h-3.5 mr-0.5" />}
                {change}
              </span>
            )}
            {subtitle && <span className="text-gray-400">{subtitle}</span>}
          </div>
        )}
      </div>
    </div>
  );
}
