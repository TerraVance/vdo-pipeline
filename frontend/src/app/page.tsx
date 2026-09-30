"use client";

import { useStore } from "@/store/useStore";
import { Stepper } from "@/components/Stepper";
import { Step1Idea } from "@/components/steps/Step1Idea";
import { Step2Prompt } from "@/components/steps/Step2Prompt";
import { Step3Visuals } from "@/components/steps/Step3Visuals";
import { Step4Motion } from "@/components/steps/Step4Motion";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AnimatePresence } from "framer-motion";
import { useState } from "react";

export default function Home() {
  const currentStep = useStore((state) => state.currentStep);
  const [queryClient] = useState(() => new QueryClient());

  return (
    <QueryClientProvider client={queryClient}>
      <div className="w-full flex flex-col items-center">
        <div className="text-center mb-10">
          <h2 className="text-4xl font-bold font-outfit text-white mb-4">
            Create Stunning AI Videos
          </h2>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            Our pipeline guides you from a raw concept to a polished production script, generates stunning concept art, and brings it all to life with state-of-the-art video AI.
          </p>
        </div>

        <Stepper />

        <div className="w-full mt-4 flex justify-center">
          <AnimatePresence mode="wait">
            {currentStep === 1 && <Step1Idea key="step1" />}
            {currentStep === 2 && <Step2Prompt key="step2" />}
            {currentStep === 3 && <Step3Visuals key="step3" />}
            {currentStep === 4 && <Step4Motion key="step4" />}
          </AnimatePresence>
        </div>
      </div>
    </QueryClientProvider>
  );
}
