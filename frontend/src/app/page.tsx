"use client";

import { useStore } from "@/store/useStore";
import { LandingPage } from "@/components/LandingPage";
import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function Home() {
  const { user, isAuthLoading } = useStore();
  const router = useRouter();

  useEffect(() => {
    if (user && !isAuthLoading) {
      router.push("/studio");
    }
  }, [user, isAuthLoading, router]);

  if (isAuthLoading) {
    return (
      <div className="w-full flex-1 flex flex-col items-center justify-center mt-32">
        <Loader2 className="w-8 h-8 animate-spin text-primary opacity-50" />
      </div>
    );
  }

  return <LandingPage />;
}
