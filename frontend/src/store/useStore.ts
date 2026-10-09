import { create } from "zustand";
import { persist } from "zustand/middleware";
import { ProjectState, ImageModel, VideoModel } from "../lib/api";
import type { User } from "@supabase/supabase-js";

interface AppState {
  currentStep: number;
  project: ProjectState | null;
  user: User | null;
  isAuthModalOpen: boolean;
  isAuthLoading: boolean;
  preferredImageModel: ImageModel;
  preferredVideoModel: VideoModel;
  preferredDurationSeconds: number;
  // Actions
  setStep: (step: number) => void;
  setAuthModalOpen: (isOpen: boolean) => void;
  setAuthLoading: (isLoading: boolean) => void;
  setPreferredImageModel: (model: ImageModel) => void;
  setPreferredVideoModel: (model: VideoModel) => void;
  setPreferredDurationSeconds: (seconds: number) => void;
  setProject: (project: ProjectState) => void;
  updateProject: (data: Partial<ProjectState>) => void;
  setUser: (user: User | null) => void;
  reset: () => void;
}

export const useStore = create<AppState>()(
  persist(
    (set) => ({
      currentStep: 1,
      project: null,
      user: null,
      isAuthModalOpen: false,
      isAuthLoading: true,
      preferredImageModel: "freepik_mystic_photo" as ImageModel,
      preferredVideoModel: "gemini_veo2" as VideoModel,
      preferredDurationSeconds: 8,

      setStep: (step) => set({ currentStep: step }),
      setAuthModalOpen: (isOpen) => set({ isAuthModalOpen: isOpen }),
      setAuthLoading: (isLoading) => set({ isAuthLoading: isLoading }),
      setPreferredImageModel: (model) => set({ preferredImageModel: model }),
      setPreferredVideoModel: (model) => set({ preferredVideoModel: model }),
      setPreferredDurationSeconds: (seconds) => set({ preferredDurationSeconds: seconds }),

      // setProject is called after POST /projects — automatically moves to Step 2
      setProject: (project) => set({ project, currentStep: 2 }),

      // Partial merge — used for polling updates, prompt edits, image/video saves
      updateProject: (data) =>
        set((state) => ({
          project: state.project ? { ...state.project, ...data } : null,
        })),

      setUser: (user) => set({ user }),

      // Full reset — clears everything back to Step 1
      reset: () => set({ currentStep: 1, project: null }),
    }),
    {
      name: "vdo-pipeline-storage",
      // Only persist the minimum needed to resume a session
      partialize: (state) => ({
        currentStep: state.currentStep,
        project: state.project,
      }),
    }
  )
);
