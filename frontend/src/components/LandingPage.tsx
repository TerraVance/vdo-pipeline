"use client";

import { useStore } from "@/store/useStore";
import { motion } from "framer-motion";
import { Wand2, Image as ImageIcon, Video, Layers, ChevronRight } from "lucide-react";

export function LandingPage() {
  const { setAuthModalOpen } = useStore();

  return (
    <div className="w-full max-w-5xl mx-auto flex flex-col items-center pt-10 pb-20">
      
      {/* Hero Section */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center mb-20 space-y-6"
      >
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 text-primary text-sm font-medium mb-4">
          <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
          Next-Gen AI Video Pipeline
        </div>
        <h1 className="text-5xl md:text-7xl font-bold font-outfit text-white tracking-tight max-w-4xl mx-auto leading-tight">
          From Raw Concept to <br />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary via-purple-400 to-primary bg-[length:200%_auto] animate-shimmer">
            Cinematic Reality
          </span>
        </h1>
        <p className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto leading-relaxed">
          TerraVance is a professional-grade, human-in-the-loop AI pipeline. Generate stunning concept art and breathe life into it with state-of-the-art video synthesis models like Google Veo and Freepik Mystic.
        </p>
        <div className="pt-6">
          <button
            onClick={() => setAuthModalOpen(true)}
            className="group relative inline-flex items-center justify-center gap-2 px-8 py-4 text-base font-semibold text-white bg-primary rounded-full overflow-hidden transition-all hover:scale-105 hover:shadow-[0_0_40px_rgba(99,102,241,0.4)]"
          >
            <span className="relative z-10 flex items-center gap-2">
              Start Creating <ChevronRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </span>
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent -translate-x-full group-hover:animate-shimmer" />
          </button>
        </div>
      </motion.div>

      {/* Feature Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 w-full">
        
        {/* Step 1 */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="glass-panel p-6 flex flex-col items-start gap-4 relative overflow-hidden group"
        >
          <div className="w-12 h-12 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center group-hover:scale-110 group-hover:bg-primary/20 transition-all">
            <Wand2 className="w-6 h-6 text-white group-hover:text-primary transition-colors" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white mb-2 font-outfit">1. Concept & Script</h3>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Describe your idea. Our LLMs will instantly expand it into a rich, production-ready cinematic prompt with lighting and camera directions.
            </p>
          </div>
        </motion.div>

        {/* Step 2 */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="glass-panel p-6 flex flex-col items-start gap-4 relative overflow-hidden group"
        >
          <div className="w-12 h-12 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center group-hover:scale-110 group-hover:bg-purple-500/20 transition-all">
            <ImageIcon className="w-6 h-6 text-white group-hover:text-purple-400 transition-colors" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white mb-2 font-outfit">2. Visual Art Gen</h3>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Generate 4 stunning concept frames simultaneously using Google Imagen 3, Nano Banana Pro, or Freepik Mystic.
            </p>
          </div>
        </motion.div>

        {/* Step 3 */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="glass-panel p-6 flex flex-col items-start gap-4 relative overflow-hidden group"
        >
          <div className="w-12 h-12 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center group-hover:scale-110 group-hover:bg-blue-500/20 transition-all">
            <Layers className="w-6 h-6 text-white group-hover:text-blue-400 transition-colors" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white mb-2 font-outfit">3. Human Curation</h3>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Review the generated grid. Select the absolute best composition and aesthetic to use as the visual anchor for your final video.
            </p>
          </div>
        </motion.div>

        {/* Step 4 */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="glass-panel p-6 flex flex-col items-start gap-4 relative overflow-hidden group"
        >
          <div className="w-12 h-12 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center group-hover:scale-110 group-hover:bg-green-500/20 transition-all">
            <Video className="w-6 h-6 text-white group-hover:text-green-400 transition-colors" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white mb-2 font-outfit">4. Video Synthesis</h3>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Breathe life into the frame. We feed your chosen image into Google Veo 3.1 or Kling 2.5 to synthesize a gorgeous, high-fidelity video clip.
            </p>
          </div>
        </motion.div>

      </div>
    </div>
  );
}
