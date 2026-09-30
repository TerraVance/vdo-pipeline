"use client";

import { useState, useEffect } from "react";
import { useStore } from "@/store/useStore";
import { apiClient, VideoModel } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { LoadingSpinner } from "@/components/ui/loading-spinner";
import { ErrorBanner } from "@/components/ui/error-banner";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowLeft, Play, Download, Film, RefreshCw, CheckCircle2 } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

const VIDEO_MODELS: {
  id: VideoModel;
  label: string;
  description: string;
  api: "Gemini" | "Freepik";
}[] = [
  // ── Gemini API (GEMINI_API_KEY) ───────────────────────────────────────────
  {
    id: "gemini_veo2",
    label: "Veo 2",
    description: "Cinematic quality — 720p, 5s",
    api: "Gemini",
  },
  // ── Freepik API (FREEPIK_API_KEY) ─────────────────────────────────────────
  {
    id: "freepik_video",
    label: "Freepik AI Video",
    description: "Image-to-video — 720p, 5s",
    api: "Freepik",
  },
];

/** Estimated generation time per model (used for progress bar simulation) */
const MODEL_ESTIMATE_MS: Record<VideoModel, number> = {
  gemini_veo2: 75_000,   // ~75 seconds
  freepik_video: 90_000, // ~90 seconds
};

export function Step4Motion() {
  const { project, updateProject, setStep } = useStore();

  const [selectedModel, setSelectedModel] = useState<VideoModel>("freepik_video");
  const [isGenerating, setIsGenerating] = useState(project?.status === "GENERATING_VIDEO");
  const [error, setError] = useState<string | null>(null);

  // ── Indeterminate progress simulation ─────────────────────────────
  const [progress, setProgress] = useState(0);
  const [elapsedMs, setElapsedMs] = useState(0);

  useEffect(() => {
    if (!isGenerating) {
      setProgress(0);
      setElapsedMs(0);
      return;
    }

    const TICK = 500;
    const estimateMs = MODEL_ESTIMATE_MS[selectedModel];
    const timer = setInterval(() => {
      setElapsedMs((prev) => {
        const next = prev + TICK;
        // Ease toward 90% — never reaches 100% until server confirms
        const ratio = Math.min(next / estimateMs, 0.9);
        setProgress(Math.round(ratio * 100));
        return next;
      });
    }, TICK);

    return () => clearInterval(timer);
  }, [isGenerating, selectedModel]);

  // ── Status polling ────────────────────────────────────────────────
  const { data: statusData } = useQuery({
    queryKey: ["projectStatusVideo", project?.id],
    queryFn: async () => {
      if (!project?.id) throw new Error("No project ID");
      const res = await apiClient.get(`/api/v1/projects/${project.id}/status`);
      return res.data;
    },
    enabled: isGenerating && !!project?.id,
    refetchInterval: 5000,
  });

  useEffect(() => {
    if (!statusData) return;
    if (statusData.status === "VIDEO_READY") {
      setProgress(100);
      setIsGenerating(false);
      updateProject({ final_video_url: statusData.final_video_url, status: "VIDEO_READY" });
    } else if (statusData.status === "FAILED") {
      setIsGenerating(false);
      setError("Video synthesis failed. The model may have timed out or rejected the image.");
    }
  }, [statusData, updateProject]);

  const handleGenerate = async () => {
    if (!project?.id || !project?.selected_image_url) return;
    setIsGenerating(true);
    setError(null);
    updateProject({ final_video_url: undefined });

    try {
      await apiClient.post(`/api/v1/projects/${project.id}/synthesize-video`, {
        model: selectedModel,
        image_url: project.selected_image_url,
        prompt: project.refined_prompt,
      });
      updateProject({ status: "GENERATING_VIDEO" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start video generation.");
      setIsGenerating(false);
    }
  };

  const handleDownload = () => {
    if (!project?.final_video_url) return;
    const link = document.createElement("a");
    link.href = project.final_video_url;
    link.download = `terravance_${project.id.slice(0, 8)}.mp4`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const hasVideo = !!project?.final_video_url;
  const estimateSec = Math.round(MODEL_ESTIMATE_MS[selectedModel] / 1000);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="w-full max-w-4xl mx-auto space-y-6"
    >
      {/* ── Page Header ───────────────────────────────────────────── */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setStep(3)}
          aria-label="Back to image selection"
        >
          <ArrowLeft className="w-5 h-5" />
        </Button>
        <div>
          <h2 className="text-2xl font-bold font-outfit text-white">Final Synthesis</h2>
          <p className="text-muted-foreground text-sm">Bring your selected image to life.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

        {/* ── Left: Config ────────────────────────────────────────── */}
        <div className="md:col-span-1 space-y-4">
          <div className="glass-panel p-5 space-y-5">
            {/* Seed image thumbnail */}
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-3">
                Seed Image
              </h3>
              <div className="aspect-video rounded-lg overflow-hidden border border-white/10 bg-black/30">
                {project?.selected_image_url && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={project.selected_image_url}
                    alt="Seed image for video"
                    className="w-full h-full object-cover"
                  />
                )}
              </div>
            </div>

            {/* Model selector */}
            <div className="border-t border-white/5 pt-4 space-y-2">
              <label
                htmlFor="video-model-select"
                className="text-sm font-semibold text-foreground/80"
              >
                Video Model
              </label>
              <select
                id="video-model-select"
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value as VideoModel)}
                disabled={isGenerating || hasVideo}
                className="w-full bg-black/50 border border-white/10 rounded-lg px-3 py-3 text-sm text-white outline-none focus:border-primary transition-colors"
              >
                {(["Gemini", "Freepik"] as const).map((api) => (
                  <optgroup key={api} label={`── ${api} API ──`}>
                    {VIDEO_MODELS.filter((m) => m.api === api).map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.label} — {m.description}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
              <p className="text-xs text-muted-foreground">
                Estimated time: ~{estimateSec}s
              </p>
            </div>

            {/* Animate button */}
            <Button
              id="animate-video-btn"
              className="w-full"
              onClick={handleGenerate}
              disabled={isGenerating || hasVideo}
            >
              {isGenerating ? (
                <LoadingSpinner size="sm" label="Processing…" />
              ) : (
                <>
                  <Play className="w-4 h-4 mr-2" />
                  {hasVideo ? "Done" : "Animate"}
                </>
              )}
            </Button>
          </div>

          {/* Error with retry */}
          {error && (
            <ErrorBanner
              message={error}
              onRetry={handleGenerate}
              retryLabel="Retry Synthesis"
            />
          )}
        </div>

        {/* ── Right: Player ───────────────────────────────────────── */}
        <div className="md:col-span-2 space-y-4">
          <div className="w-full aspect-video rounded-2xl border border-white/5 bg-black/40 flex items-center justify-center relative overflow-hidden shadow-2xl">
            <AnimatePresence mode="wait">
              {isGenerating ? (
                <motion.div
                  key="generating"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="w-full flex flex-col items-center justify-center gap-6 p-8 text-center"
                >
                  <div className="relative w-20 h-20">
                    <div className="w-20 h-20 border-[3px] border-white/10 rounded-full absolute inset-0" />
                    <div className="w-20 h-20 border-[3px] border-primary rounded-full border-t-transparent animate-spin absolute inset-0" />
                    <Film className="w-8 h-8 text-primary absolute inset-0 m-auto" />
                  </div>

                  <div>
                    <h4 className="text-lg font-semibold text-white">Synthesizing Video…</h4>
                    <p className="text-muted-foreground mt-1 text-sm max-w-xs mx-auto">
                      This takes approximately {estimateSec}s depending on the engine.
                    </p>
                  </div>

                  {/* ── Progress bar (gap fix 12.3) ──────────────── */}
                  <div className="w-full max-w-sm space-y-1.5">
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>Progress</span>
                      <span>{progress}%</span>
                    </div>
                    <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
                      <motion.div
                        className="h-full bg-gradient-to-r from-primary to-purple-500 rounded-full"
                        animate={{ width: `${progress}%` }}
                        transition={{ duration: 0.5, ease: "easeOut" }}
                      />
                    </div>
                  </div>
                </motion.div>
              ) : hasVideo ? (
                <motion.div
                  key="video"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="w-full h-full"
                >
                  <video
                    src={project!.final_video_url!}
                    controls
                    autoPlay
                    loop
                    className="w-full h-full object-contain"
                    aria-label="Generated video"
                  />
                </motion.div>
              ) : (
                <motion.div key="empty" className="text-center">
                  <Film className="w-12 h-12 text-muted-foreground/25 mx-auto mb-3" />
                  <p className="text-muted-foreground text-sm font-medium">Video Player</p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* ── Success bar ──────────────────────────────────────── */}
          {hasVideo && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 glass-panel p-4"
            >
              <div className="flex items-center gap-3 text-emerald-400">
                <CheckCircle2 className="w-5 h-5 shrink-0" />
                <span className="font-semibold font-outfit text-sm">Render Complete</span>
              </div>
              <div className="flex gap-3 w-full sm:w-auto">
                <Button
                  variant="outline"
                  onClick={() => {
                    updateProject({ final_video_url: undefined, status: "IMAGES_READY" });
                  }}
                  className="flex-1 sm:flex-none"
                >
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Re-roll
                </Button>
                <Button
                  id="download-video-btn"
                  onClick={handleDownload}
                  className="flex-1 sm:flex-none bg-gradient-to-r from-primary to-purple-600 hover:opacity-90 text-white shadow-lg shadow-primary/25 border-0 transition-opacity"
                >
                  <Download className="w-4 h-4 mr-2" />
                  Download MP4
                </Button>
              </div>
            </motion.div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
