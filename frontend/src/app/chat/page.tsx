"use client";

import React, { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { Plus, MessageSquare, Clock } from "lucide-react";
import { DashboardLayout } from "../../components/layout/dashboard-layout";
import { ChatContainer } from "../../components/chat/chat-container";
import { Button } from "../../components/ui/button";
import { ApiClient } from "../../lib/api";
import { Conversation } from "../../lib/types";

export default function ChatPage() {
  const searchParams = useSearchParams();
  const initialId = searchParams?.get("id") || undefined;

  const [activeConvId, setActiveConvId] = useState<string | undefined>(initialId);
  const [conversations, setConversations] = useState<Conversation[]>([]);

  const fetchConversations = () => {
    ApiClient.getConversations()
      .then(setConversations)
      .catch(() => []);
  };

  useEffect(() => {
    fetchConversations();
  }, []);

  const handleNewChat = () => {
    setActiveConvId(undefined);
  };

  return (
    <DashboardLayout title="AI Business Analyst Workspace">
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 h-full">
        {/* Conversation History Sidebar */}
        <div className="lg:col-span-1 bg-white rounded-xl border border-gray-200 shadow-sm p-4 flex flex-col justify-between h-[calc(100vh-10rem)]">
          <div className="space-y-4">
            <Button onClick={handleNewChat} className="w-full gap-2 text-xs" size="sm">
              <Plus className="w-4 h-4" />
              <span>New Analysis</span>
            </Button>

            <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider px-2">
              Recent Queries
            </div>

            <div className="space-y-1 overflow-y-auto max-h-[calc(100vh-20rem)] pr-1">
              {conversations.length === 0 ? (
                <p className="text-xs text-gray-400 px-2 py-4 text-center">No history yet</p>
              ) : (
                conversations.map((c) => {
                  const isSelected = c.id === activeConvId;
                  return (
                    <button
                      key={c.id}
                      onClick={() => setActiveConvId(c.id)}
                      className={`w-full text-left p-2.5 rounded-lg text-xs transition-colors flex items-center gap-2 ${
                        isSelected
                          ? "bg-indigo-50 text-indigo-700 font-medium border border-indigo-200"
                          : "text-gray-600 hover:bg-gray-50"
                      }`}
                    >
                      <MessageSquare className="w-3.5 h-3.5 flex-shrink-0" />
                      <span className="truncate">{c.title}</span>
                    </button>
                  );
                })
              )}
            </div>
          </div>

          <div className="pt-4 border-t border-gray-100 text-[11px] text-gray-400 flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5" />
            <span>Encrypted conversation history</span>
          </div>
        </div>

        {/* Main Chat Interface */}
        <div className="lg:col-span-3">
          <ChatContainer
            conversationId={activeConvId}
            onConversationCreated={(id) => {
              setActiveConvId(id);
              fetchConversations();
            }}
          />
        </div>
      </div>
    </DashboardLayout>
  );
}
