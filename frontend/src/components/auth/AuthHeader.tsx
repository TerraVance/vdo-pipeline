"use client";

import { useState, useEffect } from "react";
import { supabase } from "@/lib/supabase";
import { useStore } from "@/store/useStore";
import { LogOut, Image as ImageIcon } from "lucide-react";
import Link from "next/link";

export function AuthHeader() {
  const { user, setUser, setAuthModalOpen, setAuthLoading } = useStore();

  useEffect(() => {
    // Check active session on mount
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null);
      setAuthLoading(false);
    });

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
      setAuthLoading(false);
    });

    return () => subscription.unsubscribe();
  }, [setUser]);

  const handleLogout = async () => {
    await supabase.auth.signOut();
  };

  return (
    <>
      <div className="flex items-center gap-3">
        {user ? (
          <>
            <Link href="/gallery" className="text-sm font-medium text-muted-foreground hover:text-white transition-colors flex items-center gap-1.5 px-3 py-1.5 rounded-full hover:bg-white/5">
              <ImageIcon className="w-4 h-4" /> My Gallery
            </Link>
            <button
              onClick={handleLogout}
              className="text-sm font-medium text-muted-foreground hover:text-white transition-colors flex items-center gap-1.5 px-3 py-1.5 rounded-full hover:bg-white/5"
            >
              <LogOut className="w-4 h-4" /> Logout
            </button>
          </>
        ) : (
          <button
            onClick={() => setAuthModalOpen(true)}
            className="text-sm font-medium bg-primary/10 text-primary hover:bg-primary hover:text-white transition-colors px-4 py-1.5 rounded-full"
          >
            Sign In
          </button>
        )}
      </div>
    </>
  );
}
