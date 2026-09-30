"use client";

import { useState } from "react";
import { useStore } from "@/store/useStore";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingSpinner } from "@/components/ui/loading-spinner";
import { ErrorBanner } from "@/components/ui/error-banner";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";

const STYLE_TAGS = [
  "Cinematic",
  "Cyberpunk",
  "Photorealistic",
  "Anime",
  "3D Render",
  "Vintage Film",
  "Neon Noir",
  "Surrealism",
  "Macro Photography",
];

const MAX_CHARS = 5000;
const MIN_CHARS = 10;

export function Step1Idea() {
  const [prompt, setPrompt] = useState("");
  const [selectedStyles, setSelectedStyles] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const setProject = useStore((state) => state.setProject);

  const toggleStyle = (style: string) => {
    setSelectedStyles((prev) =>
      prev.includes(style) ? prev.filter((s) => s !== style) : [...prev, style]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (prompt.trim().length < MIN_CHARS) {
      setError(`Please enter a more detailed idea (minimum ${MIN_CHARS} characters).`);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await apiClient.post("/api/v1/projects", {
        raw_prompt: prompt.trim(),
        style_tags: selectedStyles,
      });
      setProject(response.data);
      // Zustand's setProject automatically advances currentStep to 2
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to initialize pipeline.");
      setIsLoading(false);
    }
  };

  const charsLeft = MAX_CHARS - prompt.length;
  const isOverLimit = charsLeft < 0;
  const canSubmit = !isLoading && prompt.trim().length >= MIN_CHARS && !isOverLimit;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="w-full max-w-3xl"
    >
      <Card>
        <CardHeader className="text-center">
          <CardTitle>What do you want to create?</CardTitle>
          <p className="text-muted-foreground mt-2 text-sm">
            Describe your core idea in a few words. We handle the complex prompt engineering.
          </p>
        </CardHeader>

        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-8" noValidate>
            {/* Prompt Textarea */}
            <div className="space-y-2">
              <textarea
                id="raw-prompt"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                maxLength={MAX_CHARS}
                placeholder="e.g. A cyberpunk street market in Tokyo during a heavy rainstorm…"
                className="w-full h-36 glass-input p-4 resize-none text-base leading-relaxed"
                disabled={isLoading}
                aria-label="Your video concept"
                aria-describedby="char-count"
              />
              <div className="flex items-center justify-between text-xs">
                <span
                  id="char-count"
                  className={
                    isOverLimit
                      ? "text-red-400 font-semibold"
                      : charsLeft < 50
                      ? "text-amber-400"
                      : "text-muted-foreground"
                  }
                >
                  {isOverLimit ? `${Math.abs(charsLeft)} over limit` : `${charsLeft} characters remaining`}
                </span>
                <span className="text-muted-foreground">
                  {prompt.length} / {MAX_CHARS}
                </span>
              </div>
            </div>

            {/* Style Tag Selector */}
            <div className="space-y-3">
              <label className="text-sm font-semibold text-foreground/80">
                Style Preferences{" "}
                <span className="text-muted-foreground font-normal">(Optional)</span>
              </label>
              <div className="flex flex-wrap gap-2" role="group" aria-label="Style tags">
                {STYLE_TAGS.map((style) => {
                  const isSelected = selectedStyles.includes(style);
                  return (
                    <button
                      key={style}
                      type="button"
                      onClick={() => toggleStyle(style)}
                      disabled={isLoading}
                      aria-pressed={isSelected}
                      className={`px-4 py-2 rounded-full text-sm font-medium transition-all duration-200 border
                        ${
                          isSelected
                            ? "bg-primary/20 border-primary text-white shadow-[0_0_10px_rgba(99,102,241,0.3)]"
                            : "bg-black/20 border-white/10 text-muted-foreground hover:bg-white/5 hover:text-foreground"
                        }
                        disabled:cursor-not-allowed disabled:opacity-50`}
                    >
                      {style}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Error */}
            {error && (
              <ErrorBanner message={error} onRetry={() => setError(null)} retryLabel="Dismiss" />
            )}

            {/* Submit */}
            <Button
              type="submit"
              size="lg"
              id="initialize-pipeline-btn"
              className="w-full group"
              disabled={!canSubmit}
            >
              {isLoading ? (
                <LoadingSpinner size="sm" label="Initializing..." />
              ) : (
                <>
                  Next: Refine Prompt
                  <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
                </>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>
    </motion.div>
  );
}
