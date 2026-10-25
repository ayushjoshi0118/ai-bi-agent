"use client";

import React from "react";
import { Bell, Shield } from "lucide-react";
import { useAuthStore } from "../../stores/auth-store";

export function Header({ title }: { title?: string }) {
  const { activeOrg } = useAuthStore();

  return (
    <header className="h-16 bg-white border-b border-gray-200 px-8 flex items-center justify-between flex-shrink-0">
      <div>
        <h1 className="text-lg font-bold text-gray-900 tracking-tight">
          {title || "Dashboard Overview"}
        </h1>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5 px-2.5 py-1 bg-emerald-50 text-emerald-700 rounded-full text-xs font-medium border border-emerald-200">
          <Shield className="w-3.5 h-3.5" />
          <span>Tenant Isolated: {activeOrg?.slug || "workspace"}</span>
        </div>

        <button className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 transition-colors">
          <Bell className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}
