"use client";

import React, { useEffect, useState } from "react";
import { Building2, UserPlus, ShieldCheck, Mail, User } from "lucide-react";
import { DashboardLayout } from "../../components/layout/dashboard-layout";
import { Card, CardHeader, CardTitle, CardContent } from "../../components/ui/card";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Badge } from "../../components/ui/badge";
import { Modal } from "../../components/ui/modal";
import { ApiClient } from "../../lib/api";
import { Member, Organization } from "../../lib/types";
import { useAuthStore } from "../../stores/auth-store";

export default function SettingsPage() {
  const { activeOrg, user } = useAuthStore();
  const [members, setMembers] = useState<Member[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isInviteOpen, setIsInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("analyst");
  const [isInviting, setIsInviting] = useState(false);

  const fetchMembers = () => {
    setIsLoading(true);
    ApiClient.getOrgMembers()
      .then(setMembers)
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    fetchMembers();
  }, []);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim()) return;

    setIsInviting(true);
    try {
      await ApiClient.inviteMember(inviteEmail.trim(), inviteRole);
      setIsInviteOpen(false);
      setInviteEmail("");
      fetchMembers();
      alert("Member invited successfully!");
    } catch (err: any) {
      alert(`Invitation error: ${err.message}`);
    } finally {
      setIsInviting(false);
    }
  };

  return (
    <DashboardLayout title="Workspace & Access Settings">
      <div className="space-y-8 max-w-4xl">
        {/* Workspace Info Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Organization Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  Workspace Name
                </label>
                <div className="text-sm font-semibold text-gray-900">
                  {activeOrg?.name || "My Workspace"}
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  Tenant Slug (Isolated DB Schema)
                </label>
                <div className="text-sm font-mono text-indigo-600 font-medium">
                  {activeOrg?.slug || "workspace"}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Member Management Card */}
        <Card>
          <CardHeader className="flex items-center justify-between">
            <div>
              <CardTitle className="text-sm">Workspace Members & RBAC</CardTitle>
              <p className="text-xs text-gray-400 mt-0.5">
                Role-based access control (Owner, Admin, Analyst, Viewer)
              </p>
            </div>
            <Button onClick={() => setIsInviteOpen(true)} size="sm" className="gap-1.5 text-xs">
              <UserPlus className="w-3.5 h-3.5" />
              <span>Invite Member</span>
            </Button>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="p-8 text-center text-xs text-gray-400">Loading members...</div>
            ) : (
              <div className="divide-y divide-gray-100">
                {members.map((m) => (
                  <div key={m.id} className="py-3 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-gray-100 text-gray-700 flex items-center justify-center text-xs font-semibold">
                        {m.full_name?.charAt(0) || "U"}
                      </div>
                      <div>
                        <p className="text-xs font-semibold text-gray-900">{m.full_name}</p>
                        <p className="text-[11px] text-gray-400">{m.email}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <Badge variant={m.role === "owner" ? "info" : "default"} className="capitalize">
                        {m.role}
                      </Badge>
                      <span className="text-[11px] text-gray-400">
                        Joined {new Date(m.joined_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Invite Member Modal */}
        <Modal
          isOpen={isInviteOpen}
          onClose={() => setIsInviteOpen(false)}
          title="Invite Member to Workspace"
          description="Grant team members role-based access to query permitted datasets."
        >
          <form onSubmit={handleInvite} className="space-y-4">
            <Input
              label="User Email Address"
              type="email"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="colleague@company.com"
              required
            />

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Workspace Role
              </label>
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-1 focus:ring-indigo-500"
              >
                <option value="admin">Admin (Manage data sources & members)</option>
                <option value="analyst">Analyst (Ask questions & run queries)</option>
                <option value="viewer">Viewer (Read-only reports)</option>
              </select>
            </div>

            <div className="flex justify-end gap-3 pt-3">
              <Button variant="outline" type="button" onClick={() => setIsInviteOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" isLoading={isInviting}>
                Send Invitation
              </Button>
            </div>
          </form>
        </Modal>
      </div>
    </DashboardLayout>
  );
}
