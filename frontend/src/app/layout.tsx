import type { Metadata } from "next";
import { Inter, Outfit } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const outfit = Outfit({ subsets: ["latin"], variable: "--font-outfit" });

export const metadata: Metadata = {
  title: "VDO Pipeline | Interactive AI Video Generation",
  description: "Transform simple text concepts into high-quality videos with a human-in-the-loop AI pipeline.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} ${outfit.variable} font-sans antialiased`}>
        <div className="min-h-screen flex flex-col relative overflow-hidden">
          
          {/* Animated Background Orbs */}
          <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-primary/20 rounded-full blur-[120px] pointer-events-none -z-10" />
          <div className="absolute bottom-[-10%] right-[-10%] w-[30%] h-[30%] bg-purple-600/20 rounded-full blur-[100px] pointer-events-none -z-10" />

          {/* Header */}
          <header className="w-full border-b border-white/5 bg-black/20 backdrop-blur-md z-50">
            <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-purple-600 flex items-center justify-center">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-white">
                    <path d="m22 8-6 4 6 4V8Z"/><rect x="2" y="6" width="14" height="12" rx="2" ry="2"/>
                  </svg>
                </div>
                <h1 className="text-xl font-outfit font-bold tracking-tight text-white">
                  Terra<span className="text-primary">Vance</span>
                </h1>
              </div>
              <div className="text-sm font-medium text-muted-foreground bg-white/5 px-3 py-1.5 rounded-full border border-white/5">
                AI Video Pipeline
              </div>
            </div>
          </header>

          {/* Main Content Area */}
          <main className="flex-1 w-full max-w-7xl mx-auto px-6 py-12 flex flex-col items-center">
            {children}
          </main>
          
        </div>
      </body>
    </html>
  );
}
