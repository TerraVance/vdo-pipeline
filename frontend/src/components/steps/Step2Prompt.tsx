"use client";

import { useEffect, useState, useRef } from "react";
import { useStore } from "@/store/useStore";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { LoadingSpinner } from "@/components/ui/loading-spinner";
import { SkeletonText } from "@/components/ui/skeleton";
import { ErrorBanner } from "@/components/ui/error-banner";
import { motion, AnimatePresence } from "framer-motion";
import { RefreshCw, ArrowLeft, ArrowRight, Sparkles } from "lucide-react";

// ── Available Gemini text models ─────────────────────────────────────────────
// These match GEMINI_TEXT_MODELS in backend/app/models/schemas.py
const GEMINI_TEXT_MODELS: { id: string; label: string; description: string }[] = [
  { id: "gemini-3.8-flash",      label: "Gemini 3.8 Flash",      description: "Latest & fastest — recommended" },
  { id: "gemini-3.5-flash",      label: "Gemini 3.5 Flash",      description: "Stable, proven for creative tasks" },
  { id: "gemini-3.5-flash-lite", label: "Gemini 3.5 Flash Lite", description: "Most cost-efficient, high volume" },
  { id: "gemini-3.1-pro",        label: "Gemini 3.1 Pro",        description: "Highest quality, slower (paid tier)" },
];

export function Step2Prompt() {
  const { project, updateProject, setStep } = useStore();
  const [refinedText, setRefinedText] = useState(project?.refined_prompt ?? "");
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState("gemini-3.8-flash");

  // Ref prevents double-fire in React Strict Mode
  const hasFetched = useRef(!!project?.refined_prompt);

  const generatePrompt = async (regenerate = false) => {
    if (!project?.id) return;
    setIsGenerating(true);
    setError(null);

    try {
      const response = await apiClient.post(
        `/api/v1/projects/${project.id}/refine-prompt`,
        { regenerate, gemini_model: selectedModel }
      );
      const { refined_prompt, status } = response.data;
      setRefinedText(refined_prompt);
      updateProject({ refined_prompt, status });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate prompt from Gemini.");
    } finally {
      setIsGenerating(false);
    }
  };

  useEffect(() => {
    if (!hasFetched.current && project?.id) {
      hasFetched.current = true;
      generatePrompt();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project?.id]);

  const handleProceed = () => {
    // Sync any manual edits back to the store before advancing
    if (refinedText !== project?.refined_prompt) {
      updateProject({ refined_prompt: refinedText });
    }
    setStep(3);
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="w-full max-w-5xl grid grid-cols-1 md:grid-cols-2 gap-6"
    >
      {/* ── Left: Original Concept ──────────────────────────────────── */}
      <div className="space-y-4">
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-widest">
          Original Concept
        </h3>
        <Card className="bg-black/30 border-white/5 shadow-none h-full">
          <CardContent className="p-6">
            <p className="text-base text-white/85 leading-relaxed">{project?.raw_prompt}</p>

            {project?.style_tags && project.style_tags.length > 0 && (
              <div className="mt-6 flex flex-wrap gap-2">
                {project.style_tags.map((tag) => (
                  <span
                    key={tag}
                    className="px-3 py-1 bg-white/5 border border-white/10 rounded-full text-xs text-muted-foreground"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Button
          variant="ghost"
          onClick={() => setStep(1)}
          className="text-muted-foreground hover:text-white"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Edit Idea
        </Button>
      </div>

      {/* ── Right: AI Refined Script ────────────────────────────────── */}
      <div className="space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h3 className="text-xs font-semibold text-primary uppercase tracking-widest flex items-center gap-2">
            <Sparkles className="w-3.5 h-3.5" />
            AI Refined Script
          </h3>

          {/* ── Gemini Model Selector ───────────────────────────────── */}
          <div className="flex items-center gap-2">
            <label
              htmlFor="gemini-model-select"
              className="text-xs text-muted-foreground font-semibold uppercase tracking-wider whitespace-nowrap"
            >
              Model
            </label>
            <select
              id="gemini-model-select"
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              disabled={isGenerating}
              className="bg-black/50 border border-white/10 rounded-lg px-2 py-1 text-xs text-white outline-none focus:border-primary transition-colors"
            >
              {GEMINI_TEXT_MODELS.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label} — {m.description}
                </option>
              ))}
            </select>
          </div>

          <Button
            variant="outline"
            size="sm"
            id="regenerate-prompt-btn"
            onClick={() => generatePrompt(true)}
            disabled={isGenerating}
            className="text-xs h-8"
          >
            <RefreshCw className={`w-3 h-3 mr-1.5 ${isGenerating ? "animate-spin" : ""}`} />
            Regenerate
          </Button>
        </div>

        <Card className="relative overflow-hidden border-primary/20 min-h-[300px]">
          <AnimatePresence>
            {isGenerating && (
              <motion.div
                key="loading-overlay"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="absolute inset-0 bg-background/80 backdrop-blur-sm z-10 flex flex-col items-center justify-center gap-6 p-6"
              >
                <LoadingSpinner size="md" />
                {/* Shimmer skeleton lines show the shape of the incoming content */}
                <div className="w-full max-w-xs space-y-2">
                  <SkeletonText lines={5} />
                </div>
                <p className="text-xs text-primary/80 font-medium">
                  {selectedModel} is crafting the perfect prompt…
                </p>
              </motion.div>
            )}
          </AnimatePresence>

          <CardContent className="p-0">
            <textarea
              id="refined-prompt-editor"
              value={refinedText}
              onChange={(e) => setRefinedText(e.target.value)}
              className="w-full h-[300px] bg-transparent p-6 resize-none outline-none text-white/90 leading-relaxed focus:bg-white/[0.02] transition-colors text-sm"
              placeholder="Your AI-refined production script will appear here…"
              disabled={isGenerating}
              aria-label="Refined prompt — editable"
            />
          </CardContent>
        </Card>

        {error && (
          <ErrorBanner
            message={error}
            onRetry={() => generatePrompt()}
            retryLabel="Try Again"
          />
        )}

        <div className="flex justify-end pt-2">
          <Button
            id="proceed-to-visuals-btn"
            size="lg"
            onClick={handleProceed}
            disabled={isGenerating || !refinedText.trim()}
            className="w-full sm:w-auto group"
          >
            Approve & Generate Visuals
            <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-0.5 transition-transform" />
          </Button>
        </div>
      </div>
    </motion.div>
  );
}
