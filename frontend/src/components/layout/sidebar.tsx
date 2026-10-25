"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  MessageSquare,
  Database,
  Table2,
  FileBarChart,
  AlertTriangle,
  Clock,
  Settings,
  ShieldCheck,
  LogOut,
  Building2,
} from "lucide-react";
import { cn } from "../../lib/utils";
import { useAuthStore } from "../../stores/auth-store";

const NAV_ITEMS = [
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { name: "AI Analyst", href: "/chat", icon: MessageSquare },
  { name: "Data Sources", href: "/data-sources", icon: Database },
  { name: "Datasets", href: "/datasets", icon: Table2 },
  { name: "Saved Reports", href: "/reports", icon: FileBarChart },
  { name: "Anomalies", href: "/anomalies", icon: AlertTriangle },
  { name: "Scheduled Jobs", href: "/scheduled-jobs", icon: Clock },
  { name: "Organization", href: "/settings", icon: Settings },
  { name: "Audit Logs", href: "/audit", icon: ShieldCheck },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, activeOrg, organizations, setActiveOrg, logout } = useAuthStore();

  return (
    <aside className="w-64 flex-shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col justify-between text-white">
      <div>
        {/* Logo */}
        <div className="h-16 px-6 flex items-center gap-3 border-b border-gray-800">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-white shadow-md">
            BI
          </div>
          <span className="font-semibold text-base tracking-tight text-white">
            BI Agent SaaS
          </span>
        </div>

        {/* Workspace Selector */}
        <div className="px-4 py-3 border-b border-gray-800">
          <div className="flex items-center justify-between text-xs text-gray-400 mb-1.5 px-2">
            <span>ACTIVE WORKSPACE</span>
            <Building2 className="w-3.5 h-3.5" />
          </div>
          <select
            value={activeOrg?.id || ""}
            onChange={(e) => {
              const target = organizations.find((o) => o.id === e.target.value);
              if (target) setActiveOrg(target);
            }}
            className="w-full bg-gray-800 border border-gray-700 text-xs text-gray-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            {organizations.map((org) => (
              <option key={org.id} value={org.id}>
                {org.name}
              </option>
            ))}
          </select>
        </div>

        {/* Navigation items */}
        <nav className="p-3 space-y-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive =
              pathname === item.href ||
              (item.href !== "/dashboard" && pathname?.startsWith(item.href));

            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                  isActive
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-gray-400 hover:text-white hover:bg-gray-800"
                )}
              >
                <Icon className="w-4 h-4 flex-shrink-0" />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>
      </div>

      {/* User profile & logout */}
      <div className="p-4 border-t border-gray-800 flex items-center justify-between">
        <div className="flex items-center gap-3 overflow-hidden">
          <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center text-xs font-semibold text-gray-200">
            {user?.full_name?.charAt(0) || "U"}
          </div>
          <div className="truncate">
            <p className="text-xs font-medium text-white truncate">{user?.full_name}</p>
            <p className="text-[10px] text-gray-400 truncate">{user?.email}</p>
          </div>
        </div>
        <button
          onClick={logout}
          title="Sign Out"
          className="text-gray-400 hover:text-red-400 p-1.5 rounded-lg hover:bg-gray-800 transition-colors"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </aside>
  );
}
