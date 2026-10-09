"use client";

import { AuthHeader } from "@/components/auth/AuthHeader";
import { LoginModal } from "@/components/auth/LoginModal";
import { Providers } from "@/components/Providers";
import { useStore } from "@/store/useStore";
import { Plus } from "lucide-react";

/**
 * ClientLayout — wraps all interactive, client-side UI:
 *   - The animated background orbs
 *   - The header with Auth controls and New Project button
 *   - The React Query provider
 */
export function ClientLayout({ children }: { children: React.ReactNode }) {
  const { isAuthModalOpen, setAuthModalOpen, currentStep, user, reset } = useStore();

  return (
    <div className="min-h-screen flex flex-col relative overflow-hidden">
      {/* Animated Background Orbs */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-primary/20 rounded-full blur-[120px] pointer-events-none -z-10" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[30%] h-[30%] bg-purple-600/20 rounded-full blur-[100px] pointer-events-none -z-10" />

      {/* Header */}
      <header className="w-full border-b border-white/5 bg-black/20 backdrop-blur-md z-50">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          {/* Logo — clicking it resets to step 1 when logged in */}
          <button
            onClick={() => user && reset()}
            className="flex items-center gap-2 hover:opacity-80 transition-opacity"
            aria-label="TerraVance — back to start"
          >
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-purple-600 flex items-center justify-center">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-white">
                <path d="m22 8-6 4 6 4V8Z"/><rect x="2" y="6" width="14" height="12" rx="2" ry="2"/>
              </svg>
            </div>
            <h1 className="text-xl font-outfit font-bold tracking-tight text-white">
              Terra<span className="text-primary">Vance</span>
            </h1>
          </button>

          <div className="flex items-center gap-3">
            {/* "New Project" button — only visible when logged in and past Step 1 */}
            {user && currentStep > 1 && (
              <button
                onClick={reset}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-white/10 bg-white/5 hover:bg-white/10 hover:border-white/20 text-sm text-muted-foreground hover:text-white transition-all"
                aria-label="Start a new project"
              >
                <Plus className="w-3.5 h-3.5" />
                New Project
              </button>
            )}
            <AuthHeader />
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 w-full max-w-7xl mx-auto px-6 py-12 flex flex-col items-center">
        <Providers>
          {children}
        </Providers>
      </main>

      <LoginModal isOpen={isAuthModalOpen} onClose={() => setAuthModalOpen(false)} />
    </div>
  );
}
