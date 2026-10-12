"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { apiClient } from "@/lib/api";
import { 
  Send, 
  Loader2, 
  PlusCircle, 
  MessageSquare, 
  Cpu, 
  Trash2, 
  X, 
  Copy, 
  Check, 
  Download, 
  AlertCircle 
} from "lucide-react";

export interface ChatSession {
  id: string;
  title: string;
  user_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  action?: string | null;
  model?: string | null;
  aspect_ratio?: string | null;
  image_urls?: string[];
  status?: "PENDING" | "COMPLETED" | "FAILED" | string;
  task_id?: string | null;
  created_at?: string;
  updated_at?: string;
}

// Formatted markdown parser for chat bubbles
const renderFormattedText = (text: string) => {
  if (!text) return null;
  const parts = text.split(/(\*\*.*?\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={i} className="font-semibold text-white">
          {part.slice(2, -2)}
        </strong>
      );
    }
    return <span key={i}>{part}</span>;
  });
};

export default function StudioPage() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  
  const [input, setInput] = useState("");
  const [action, setAction] = useState<"refine_prompt" | "create_image">("refine_prompt");
  const [model, setModel] = useState("gemini-3.8-flash");
  const [aspectRatio, setAspectRatio] = useState("16:9");
  
  const [isSending, setIsSending] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const prevMessagesLengthRef = useRef(0);

  const fetchSessions = useCallback(async () => {
    try {
      const res = await apiClient.get<ChatSession[]>("/api/v1/chat/sessions");
      setSessions(res.data);
      if (res.data.length > 0 && !activeSessionId) {
        setActiveSessionId(res.data[0].id);
      } else if (res.data.length === 0) {
        createSession();
      }
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to load chats");
    }
  }, [activeSessionId]);

  const fetchMessages = useCallback(async (sessionId: string) => {
    try {
      const res = await apiClient.get<ChatMessage[]>(`/api/v1/chat/sessions/${sessionId}/messages`);
      setMessages(res.data);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to load messages");
    }
  }, []);

  const createSession = async () => {
    try {
      const res = await apiClient.post<ChatSession>("/api/v1/chat/sessions", { title: "New Conversation" });
      setSessions((prev) => [res.data, ...prev]);
      setActiveSessionId(res.data.id);
      setMessages([]);
      setErrorMessage(null);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to create new chat");
    }
  };

  // Initial load
  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  // Load messages on active session switch
  useEffect(() => {
    if (activeSessionId) {
      fetchMessages(activeSessionId);
    }
  }, [activeSessionId, fetchMessages]);

  // Smart polling: only poll while there are pending tasks in the active session
  useEffect(() => {
    if (!activeSessionId) return;

    const hasPendingTasks = messages.some((m) => m.status === "PENDING");
    if (!hasPendingTasks) return;

    const interval = setInterval(() => {
      fetchMessages(activeSessionId);
    }, 3000);

    return () => clearInterval(interval);
  }, [activeSessionId, messages, fetchMessages]);

  // Auto-scroll logic
  useEffect(() => {
    const container = chatContainerRef.current;
    if (!container) return;

    const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 160;
    if (messages.length > prevMessagesLengthRef.current || isNearBottom) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
    prevMessagesLengthRef.current = messages.length;
  }, [messages]);

  // Sync default model when switching action
  useEffect(() => {
    if (action === "refine_prompt") {
      setModel("gemini-3.8-flash");
    } else if (action === "create_image") {
      setModel("gemini_imagen3");
    }
  }, [action]);

  const deleteSession = async (e: React.MouseEvent, sessionId: string) => {
    e.preventDefault();
    e.stopPropagation();

    try {
      await apiClient.delete(`/api/v1/chat/sessions/${sessionId}`);
      const remaining = sessions.filter((s) => s.id !== sessionId);
      setSessions(remaining);

      if (activeSessionId === sessionId) {
        setMessages([]);
        if (remaining.length > 0) {
          setActiveSessionId(remaining[0].id);
        } else {
          setActiveSessionId(null);
          createSession();
        }
      }
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to delete chat");
    }
  };

  const handleCopyPrompt = async (id: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      // Fallback
      setErrorMessage("Could not copy to clipboard");
    }
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !activeSessionId || isSending) return;

    const userMessageContent = input.trim();
    const tempMessage: ChatMessage = {
      id: `temp-${Date.now()}`,
      session_id: activeSessionId,
      role: "user",
      content: userMessageContent,
      action,
      model,
      aspect_ratio: action === "create_image" ? aspectRatio : undefined,
      created_at: new Date().toISOString(),
    };

    setInput("");
    setIsSending(true);
    setErrorMessage(null);

    try {
      // Optimistic append
      setMessages((prev) => [...prev, tempMessage]);

      await apiClient.post(`/api/v1/chat/sessions/${activeSessionId}/messages`, {
        content: userMessageContent,
        action,
        model,
        aspect_ratio: action === "create_image" ? aspectRatio : undefined,
      });

      await fetchMessages(activeSessionId);

      // Refresh titles if this was the initial prompt
      if (messages.length === 0) {
        await fetchSessions();
      }
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="flex h-[calc(100vh-176px)] w-full max-w-[1600px] mx-auto overflow-hidden rounded-2xl border border-white/10 glass-panel shadow-2xl relative">
      
      {/* Toast Error Notification */}
      {errorMessage && (
        <div className="absolute top-4 right-4 z-50 flex items-center gap-2 px-4 py-2.5 rounded-xl bg-red-500/90 text-white text-xs font-medium backdrop-blur-md shadow-lg border border-red-400/30 animate-in fade-in slide-in-from-top-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorMessage}</span>
          <button 
            onClick={() => setErrorMessage(null)} 
            className="ml-2 hover:opacity-75 transition-opacity"
            aria-label="Dismiss error"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* ── Sidebar ── */}
      <div className="w-64 bg-black/40 border-r border-white/5 flex flex-col">
        <div className="p-4">
          <button 
            onClick={createSession}
            className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-primary/20 text-primary hover:bg-primary/30 border border-primary/30 transition-all text-sm font-medium cursor-pointer"
            aria-label="Create new chat"
          >
            <PlusCircle className="w-4 h-4" />
            New Chat
          </button>
        </div>
        
        <div className="flex-1 overflow-y-auto px-3 space-y-1">
          <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider px-2 py-3">
            Recent Chats
          </div>
          {sessions.map((s) => (
            <div key={s.id} className="relative group">
              <button
                onClick={() => setActiveSessionId(s.id)}
                className={`w-full text-left px-3 py-3 rounded-lg text-sm flex items-center gap-3 transition-colors ${
                  activeSessionId === s.id ? "bg-white/10 text-white" : "text-white/60 hover:bg-white/5 hover:text-white"
                }`}
              >
                <MessageSquare className="w-4 h-4 opacity-50 shrink-0" />
                <div className="truncate pr-8">{s.title}</div>
              </button>
              
              <button 
                onClick={(e) => deleteSession(e, s.id)}
                className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 hover:bg-red-500/20 text-white/60 hover:text-red-400 p-1.5 rounded-md transition-all z-10 cursor-pointer"
                title="Delete Chat"
                aria-label={`Delete chat ${s.title}`}
                type="button"
              >
                <Trash2 className="w-4 h-4 pointer-events-none" />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* ── Main Chat Area ── */}
      <div className="flex-1 flex flex-col bg-black/20">
        
        {/* Messages */}
        <div ref={chatContainerRef} className="flex-1 overflow-y-auto p-4 md:p-8 space-y-6">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center opacity-50">
              <Cpu className="w-12 h-12 mb-4 text-primary animate-pulse" />
              <h2 className="text-xl font-medium text-white mb-2 font-outfit">Welcome to AI Studio</h2>
              <p className="max-w-md text-sm text-muted-foreground">
                Craft cinematic prompts or generate multi-aspect ratio images directly from your concepts.
              </p>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div key={msg.id || idx} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[80%] rounded-2xl p-4 relative group ${
                  msg.role === "user" 
                    ? "bg-primary/20 text-white border border-primary/30 rounded-br-none" 
                    : "bg-white/5 text-white/90 border border-white/10 rounded-bl-none"
                }`}>
                  <div className="whitespace-pre-wrap text-sm leading-relaxed">
                    {renderFormattedText(msg.content)}
                  </div>

                  {/* Copy Prompt button for Assistant messages */}
                  {msg.role === "assistant" && msg.content && (
                    <div className="mt-2 pt-2 border-t border-white/5 flex items-center justify-end">
                      <button
                        onClick={() => handleCopyPrompt(msg.id || String(idx), msg.content)}
                        className="flex items-center gap-1.5 text-xs text-white/40 hover:text-white transition-colors py-1 px-2 rounded hover:bg-white/5"
                        title="Copy to clipboard"
                      >
                        {copiedId === (msg.id || String(idx)) ? (
                          <>
                            <Check className="w-3.5 h-3.5 text-green-400" />
                            <span className="text-green-400">Copied</span>
                          </>
                        ) : (
                          <>
                            <Copy className="w-3.5 h-3.5" />
                            <span>Copy Prompt</span>
                          </>
                        )}
                      </button>
                    </div>
                  )}
                  
                  {/* Generated Visuals Grid */}
                  {msg.image_urls && msg.image_urls.length > 0 && (
                    <div className="grid grid-cols-2 gap-2 mt-4">
                      {msg.image_urls.map((url: string, i: number) => (
                        <div key={i} className="relative group/img overflow-hidden rounded-lg border border-white/10">
                          <img 
                            src={url} 
                            alt={`Generated frame ${i + 1}`} 
                            className="w-full h-auto cursor-pointer object-cover hover:scale-[1.02] transition-transform duration-200" 
                            onClick={() => setSelectedImage(url)}
                            loading="lazy"
                          />
                          <a
                            href={url}
                            target="_blank"
                            rel="noopener noreferrer"
                            download={`generated_image_${i + 1}.png`}
                            className="absolute bottom-2 right-2 p-1.5 rounded-md bg-black/70 hover:bg-black text-white/80 hover:text-white opacity-0 group-hover/img:opacity-100 transition-opacity backdrop-blur-sm"
                            title="Download full image"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <Download className="w-3.5 h-3.5" />
                          </a>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Status indicator for pending/failed jobs */}
                  {msg.role === "assistant" && msg.status === "PENDING" && (
                    <div className="mt-3 flex items-center gap-2 text-xs text-primary animate-pulse">
                      <Loader2 className="w-3 h-3 animate-spin" />
                      Generating content...
                    </div>
                  )}
                  {msg.role === "assistant" && msg.status === "FAILED" && (
                    <div className="mt-3 flex items-center gap-2 text-xs text-red-400">
                      <span className="w-2 h-2 rounded-full bg-red-400" />
                      Generation encountered an error. Please try again.
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 bg-black/40 border-t border-white/5 backdrop-blur-xl">
          <form onSubmit={handleSend} className="max-w-4xl mx-auto space-y-3">
            
            {/* Options Row */}
            <div className="flex items-center gap-3 flex-wrap">
              <select 
                value={action} 
                onChange={(e) => setAction(e.target.value as "refine_prompt" | "create_image")}
                className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:border-primary transition-colors cursor-pointer"
                aria-label="Select generation action"
              >
                <option value="refine_prompt">Refine Prompt</option>
                <option value="create_image">Create Image</option>
              </select>

              <select 
                value={model} 
                onChange={(e) => setModel(e.target.value)}
                className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:border-primary transition-colors cursor-pointer"
                aria-label="Select model"
              >
                {action === "refine_prompt" && (
                  <>
                    <option value="gemini-3.8-flash">Gemini 3.8 Flash</option>
                    <option value="gemini-3-flash-preview">Gemini 3 Flash</option>
                  </>
                )}
                {action === "create_image" && (
                  <>
                    <option value="gemini_imagen3">Gemini Imagen 3</option>
                    <option value="freepik_mystic_photo">Freepik Mystic (Photo)</option>
                  </>
                )}
              </select>

              {action === "create_image" && (
                <select 
                  value={aspectRatio} 
                  onChange={(e) => setAspectRatio(e.target.value)}
                  className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:border-primary transition-colors cursor-pointer"
                  aria-label="Select aspect ratio"
                >
                  <option value="16:9">16:9 (Landscape)</option>
                  <option value="9:16">9:16 (Portrait)</option>
                  <option value="1:1">1:1 (Square)</option>
                  <option value="4:3">4:3 (Classic)</option>
                  <option value="3:4">3:4 (Traditional)</option>
                </select>
              )}
            </div>

            {/* Chat Input */}
            <div className="relative">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSend(e);
                  }
                }}
                placeholder="Message AI Studio..."
                className="w-full bg-white/5 border border-white/10 rounded-xl pl-4 pr-12 py-4 text-sm text-white outline-none focus:border-primary/50 transition-colors resize-none h-14"
                rows={1}
                disabled={isSending || !activeSessionId}
                aria-label="Chat input message"
              />
              <button 
                type="submit"
                disabled={isSending || !input.trim() || !activeSessionId}
                className="absolute right-2 top-2 p-2 bg-primary hover:bg-primary/90 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center cursor-pointer"
                aria-label="Send message"
              >
                {isSending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </button>
            </div>
            
          </form>
        </div>
        
      </div>

      {/* ── Image Lightbox Modal ── */}
      {selectedImage && (
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/90 backdrop-blur-sm p-4 animate-in fade-in duration-200"
          onClick={() => setSelectedImage(null)}
          role="dialog"
          aria-modal="true"
        >
          <div className="relative max-w-[90vw] max-h-[90vh] flex items-center justify-center">
            <button 
              className="absolute -top-12 right-0 text-white/70 hover:text-white p-2 rounded-full hover:bg-white/10 transition-colors cursor-pointer"
              onClick={(e) => {
                e.stopPropagation();
                setSelectedImage(null);
              }}
              aria-label="Close image lightbox"
            >
              <X className="w-6 h-6" />
            </button>
            <img 
              src={selectedImage} 
              alt="Generated full size" 
              className="max-w-[90vw] max-h-[90vh] object-contain rounded-lg shadow-2xl border border-white/10"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
        </div>
      )}
    </div>
  );
}

