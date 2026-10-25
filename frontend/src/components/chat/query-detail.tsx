"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronRight, Terminal, CheckCircle2, Clock } from "lucide-react";

export function QueryDetail({
  query,
}: {
  query: { id: string; sql: string; row_count: number; duration_ms: number };
}) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="mt-2 text-xs border border-gray-200 rounded-lg overflow-hidden bg-gray-50">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-3 py-2 flex items-center justify-between text-gray-700 hover:bg-gray-100 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Terminal className="w-3.5 h-3.5 text-indigo-600" />
          <span className="font-mono font-medium">Executed SQL Query</span>
          <span className="flex items-center gap-1 text-[11px] text-emerald-600 font-semibold bg-emerald-50 px-1.5 py-0.5 rounded">
            <CheckCircle2 className="w-3 h-3" /> Read-Only Validated
          </span>
        </div>
        <div className="flex items-center gap-3 text-gray-500 text-[11px]">
          <span>{query.row_count} rows</span>
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" /> {query.duration_ms}ms
          </span>
          {isOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        </div>
      </button>

      {isOpen && (
        <div className="p-3 bg-gray-900 border-t border-gray-200 text-gray-100 font-mono text-[11px] overflow-x-auto">
          <pre>{query.sql}</pre>
        </div>
      )}
    </div>
  );
}
