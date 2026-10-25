"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthStore } from "../../../stores/auth-store";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";

export default function SignupPage() {
  const router = useRouter();
  const { signup, isLoading, error } = useAuthStore();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await signup(email, password, fullName);
      router.push("/dashboard");
    } catch {
      // Handled in store
    }
  };

  return (
    <div>
      <div className="text-center mb-8">
        <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center font-bold text-white mx-auto mb-3 shadow-md">
          BI
        </div>
        <h2 className="text-2xl font-bold text-gray-900 tracking-tight">
          Create your account
        </h2>
        <p className="text-xs text-gray-500 mt-1">
          Set up an isolated workspace for your business data
        </p>
      </div>

      {error && (
        <div className="p-3 mb-4 text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Full Name"
          type="text"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          placeholder="Jane Analyst"
          required
        />

        <Input
          label="Work Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="analyst@company.com"
          required
        />

        <Input
          label="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="At least 8 characters"
          required
          minLength={8}
        />

        <Button type="submit" isLoading={isLoading} className="w-full mt-2">
          Create Workspace
        </Button>
      </form>

      <div className="mt-6 text-center text-xs text-gray-500">
        Already have an account?{" "}
        <Link href="/login" className="text-indigo-600 font-medium hover:underline">
          Sign In
        </Link>
      </div>
    </div>
  );
}
