import { create } from "zustand";
import { persist } from "zustand/middleware";
import { ProjectState } from "../lib/api";

interface AppState {
  currentStep: number;
  project: ProjectState | null;
  // Actions
  setStep: (step: number) => void;
  setProject: (project: ProjectState) => void;
  updateProject: (data: Partial<ProjectState>) => void;
  reset: () => void;
}

export const useStore = create<AppState>()(
  persist(
    (set) => ({
      currentStep: 1,
      project: null,

      setStep: (step) => set({ currentStep: step }),

      // setProject is called after POST /projects — automatically moves to Step 2
      setProject: (project) => set({ project, currentStep: 2 }),

      // Partial merge — used for polling updates, prompt edits, image/video saves
      updateProject: (data) =>
        set((state) => ({
          project: state.project ? { ...state.project, ...data } : null,
        })),

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
