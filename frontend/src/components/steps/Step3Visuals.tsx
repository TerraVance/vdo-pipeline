"use client";

import { useState, useEffect } from "react";
import { useStore } from "@/store/useStore";
import { apiClient, ImageModel } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { LoadingSpinner } from "@/components/ui/loading-spinner";
import { SkeletonImageGrid } from "@/components/ui/skeleton";
import { ErrorBanner } from "@/components/ui/error-banner";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowLeft, ArrowRight, Wand2, ImageIcon, ChevronDown, ChevronUp } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

// ── Model catalogue — each entry maps 1:1 to a backend ImageModel enum value ─
const IMAGE_MODELS: {
  id: ImageModel;
  label: string;
  description: string;
  api: "Gemini" | "Freepik";
}[] = [
  // ── Gemini API (GEMINI_API_KEY) ──────────────────────────────────────
  {
    id: "gemini_imagen3",
    label: "Imagen 3",
    description: "Highest quality, best prompt adherence",
    api: "Gemini",
  },
  {
    id: "gemini_imagen3_fast",
    label: "Imagen 3 Fast",
    description: "~2× faster, slightly lower fidelity",
    api: "Gemini",
  },
  // ── Freepik API (FREEPIK_API_KEY) ────────────────────────────────────
  {
    id: "freepik_mystic_photo",
    label: "Mystic Photo",
    description: "Photorealistic, stock-quality output",
    api: "Freepik",
  },
  {
    id: "freepik_mystic_art",
    label: "Mystic Art",
    description: "Illustrated / stylised / artistic output",
    api: "Freepik",
  },
];

export function Step3Visuals() {
  const { project, updateProject, setStep } = useStore();

  const [selectedModel, setSelectedModel] = useState<ImageModel>("freepik_mystic_photo");
  const [selectedImage, setSelectedImage] = useState<string | null>(
    project?.selected_image_url ?? null
  );
  const [isGenerating, setIsGenerating] = useState(
    project?.status === "GENERATING_IMAGES"
  );
  const [error, setError] = useState<string | null>(null);

  // ── Iterate prompt override ────────────────────────────────────────
  const [showPromptEditor, setShowPromptEditor] = useState(false);
  const [promptOverride, setPromptOverride] = useState(project?.refined_prompt ?? "");

  // ── Status polling — only active when a generation is in flight ───
  const { data: statusData } = useQuery({
    queryKey: ["projectStatus", project?.id],
    queryFn: async () => {
      if (!project?.id) throw new Error("No project ID");
      const res = await apiClient.get(`/api/v1/projects/${project.id}/status`);
      return res.data;
    },
    enabled: isGenerating && !!project?.id,
    refetchInterval: 3000,
  });

  useEffect(() => {
    if (!statusData) return;
    if (statusData.status === "IMAGES_READY") {
      setIsGenerating(false);
      updateProject({ image_urls: statusData.image_urls, status: "IMAGES_READY" });
    } else if (statusData.status === "FAILED") {
      setIsGenerating(false);
      setError("Image generation failed on the server. Please try again.");
    }
  }, [statusData, updateProject]);

  const handleGenerate = async () => {
    if (!project?.id) return;
    setIsGenerating(true);
    setError(null);
    setSelectedImage(null);

    try {
      await apiClient.post(`/api/v1/projects/${project.id}/generate-images`, {
        model: selectedModel,
        prompt: promptOverride || project?.refined_prompt,
      });
      updateProject({ status: "GENERATING_IMAGES" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start image generation.");
      setIsGenerating(false);
    }
  };

  const handleSelectImage = async (url: string) => {
    if (!project?.id) return;
    setSelectedImage(url);
    updateProject({ selected_image_url: url });
    try {
      await apiClient.patch(`/api/v1/projects/${project.id}/select-image`, {
        image_url: url,
      });
    } catch (err) {
      // Non-critical — selection is already saved in local state
      console.error("Failed to persist image selection:", err);
    }
  };

  const hasImages = (project?.image_urls?.length ?? 0) > 0;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 1.03 }}
      className="w-full max-w-5xl space-y-6"
    >
      {/* ── Toolbar ────────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 glass-panel p-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setStep(2)}
          aria-label="Back to prompt"
        >
          <ArrowLeft className="w-5 h-5" />
        </Button>

        <div className="flex-1 space-y-1">
          <label
            htmlFor="image-model-select"
            className="text-xs text-muted-foreground font-semibold uppercase tracking-wider block"
          >
            Image Engine
          </label>
          <select
            id="image-model-select"
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value as ImageModel)}
            disabled={isGenerating}
            className="bg-black/50 border border-white/10 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-primary transition-colors"
          >
            {/* Grouped by API so users see which key powers each model */}
            {(["Gemini", "Freepik"] as const).map((api) => (
              <optgroup key={api} label={`── ${api} API ──`}>
                {IMAGE_MODELS.filter((m) => m.api === api).map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label} — {m.description}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>

        <Button
          id="generate-images-btn"
          onClick={handleGenerate}
          disabled={isGenerating}
          className="w-full sm:w-auto"
        >
          {isGenerating ? (
            <LoadingSpinner size="sm" label="Generating…" />
          ) : (
            <>
              <Wand2 className="w-4 h-4 mr-2" />
              {hasImages ? "Regenerate" : "Generate Images"}
            </>
          )}
        </Button>
      </div>

      {/* ── Iterate Prompt Editor (gap fix 11.7) ───────────────────── */}
      <div className="glass-panel overflow-hidden">
        <button
          type="button"
          onClick={() => setShowPromptEditor((v) => !v)}
          className="w-full flex items-center justify-between px-5 py-3 text-sm font-medium text-muted-foreground hover:text-white transition-colors"
        >
          <span>✏️ Iterate Prompt <span className="text-xs font-normal ml-1">(edit before regenerating)</span></span>
          {showPromptEditor ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>

        <AnimatePresence>
          {showPromptEditor && (
            <motion.div
              key="prompt-editor"
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.25, ease: "easeInOut" }}
              className="overflow-hidden border-t border-white/5"
            >
              <textarea
                value={promptOverride}
                onChange={(e) => setPromptOverride(e.target.value)}
                className="w-full h-28 bg-transparent p-4 resize-none outline-none text-white/85 text-sm leading-relaxed focus:bg-white/[0.02] transition-colors"
                placeholder="Modify the AI prompt before regenerating images…"
                disabled={isGenerating}
                aria-label="Prompt override for image generation"
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ── Error ──────────────────────────────────────────────────── */}
      {error && (
        <ErrorBanner message={error} onRetry={handleGenerate} retryLabel="Try Again" />
      )}

      {/* ── Image Canvas ──────────────────────────────────────────── */}
      <div className="min-h-[400px] w-full rounded-2xl border border-white/5 bg-black/20 flex flex-col items-center justify-center relative overflow-hidden">
        {isGenerating ? (
          <div className="w-full h-full p-4">
            <SkeletonImageGrid />
            <div className="mt-6 flex justify-center">
              <LoadingSpinner size="md" label="Synthesizing visuals from your prompt…" />
            </div>
          </div>
        ) : hasImages ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 p-4 w-full">
            <AnimatePresence>
              {project!.image_urls!.map((url, i) => (
                <motion.div
                  key={url}
                  initial={{ opacity: 0, scale: 0.85 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: i * 0.08, duration: 0.35 }}
                  onClick={() => handleSelectImage(url)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => e.key === "Enter" && handleSelectImage(url)}
                  aria-pressed={selectedImage === url}
                  aria-label={`Select image ${i + 1}`}
                  className={`relative aspect-video rounded-xl overflow-hidden cursor-pointer group transition-all duration-300 focus:outline-none
                    ${
                      selectedImage === url
                        ? "ring-4 ring-primary ring-offset-2 ring-offset-background shadow-[0_0_25px_rgba(99,102,241,0.4)]"
                        : "hover:ring-2 hover:ring-white/40 hover:shadow-lg"
                    }`}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={url}
                    alt={`Generated image candidate ${i + 1}`}
                    className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
                  />

                  {selectedImage === url && (
                    <div className="absolute inset-0 bg-primary/20 flex items-center justify-center">
                      <div className="bg-primary/90 text-white px-4 py-1.5 rounded-full text-sm font-semibold backdrop-blur-md">
                        ✓ Selected for Video
                      </div>
                    </div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        ) : (
          <div className="text-center space-y-3 py-16">
            <ImageIcon className="w-12 h-12 text-muted-foreground/25 mx-auto" />
            <p className="text-muted-foreground text-sm">
              Choose an engine above and click <strong>Generate Images</strong>.
            </p>
          </div>
        )}
      </div>

      {/* ── Navigation ────────────────────────────────────────────── */}
      <div className="flex justify-end pt-2">
        <Button
          id="proceed-to-video-btn"
          size="lg"
          onClick={() => setStep(4)}
          disabled={!selectedImage || isGenerating}
          className="group"
        >
          Animate this Image
          <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-0.5 transition-transform" />
        </Button>
      </div>
    </motion.div>
  );
}
