"use client";

import { useStore } from "@/store/useStore";
import { cn } from "@/lib/utils";
import { Check } from "lucide-react";
import { motion } from "framer-motion";

const steps = [
  { id: 1, title: "Concept", description: "Raw Idea" },
  { id: 2, title: "Script", description: "AI Prompt" },
  { id: 3, title: "Visuals", description: "Image Gen" },
  { id: 4, title: "Motion", description: "Video Gen" },
];

export function Stepper() {
  const currentStep = useStore((state) => state.currentStep);

  return (
    <div className="w-full max-w-4xl mx-auto mb-12">
      <div className="flex items-center justify-between relative">
        {/* Background Line */}
        <div className="absolute left-[10%] right-[10%] top-6 h-0.5 bg-white/10 -z-10" />
        
        {/* Progress Line */}
        <motion.div 
          className="absolute left-[10%] top-6 h-0.5 bg-primary -z-10 origin-left"
          initial={{ scaleX: 0 }}
          animate={{ scaleX: Math.max(0, (currentStep - 1) / (steps.length - 1)) }}
          transition={{ duration: 0.5, ease: "easeInOut" }}
          style={{ width: "80%" }}
        />

        {steps.map((step) => {
          const isActive = step.id === currentStep;
          const isCompleted = step.id < currentStep;

          return (
            <div key={step.id} className="flex flex-col items-center gap-3 relative z-10 w-24">
              <motion.div
                initial={false}
                animate={{
                  backgroundColor: isActive ? "#6366f1" : isCompleted ? "#6366f1" : "#121214",
                  borderColor: isActive || isCompleted ? "#6366f1" : "rgba(255,255,255,0.1)",
                  scale: isActive ? 1.1 : 1,
                }}
                className={cn(
                  "w-12 h-12 rounded-full border-2 flex items-center justify-center text-sm font-semibold transition-colors duration-300",
                  isActive || isCompleted ? "text-white shadow-[0_0_20px_rgba(99,102,241,0.4)]" : "text-muted-foreground"
                )}
              >
                {isCompleted ? <Check className="w-5 h-5 text-white" strokeWidth={3} /> : step.id}
              </motion.div>
              
              <div className="text-center">
                <div className={cn(
                  "text-sm font-semibold font-outfit transition-colors",
                  isActive ? "text-white" : "text-muted-foreground"
                )}>
                  {step.title}
                </div>
                <div className="text-xs text-muted-foreground hidden sm:block mt-1">
                  {step.description}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
