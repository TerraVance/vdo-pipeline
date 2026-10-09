"use client";

import { useState, useEffect, useRef } from "react";
import { apiClient } from "@/lib/api";
import { 
  Send, 
  Loader2, 
  PlusCircle, 
  MessageSquare, 
  Cpu
} from "lucide-react";

export default function StudioPage() {
  const [sessions, setSessions] = useState<any[]>([]);
  const [messages, setMessages] = useState<any[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  
  const [input, setInput] = useState("");
  const [action, setAction] = useState("refine_prompt");
  const [model, setModel] = useState("gemini-3.1-flash");
  const [aspectRatio, setAspectRatio] = useState("16:9");
  
  const [isSending, setIsSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Poll for messages
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (activeSessionId) {
      fetchMessages(activeSessionId);
      interval = setInterval(() => {
        fetchMessages(activeSessionId);
      }, 5000);
    }
    return () => clearInterval(interval);
  }, [activeSessionId]);

  useEffect(() => {
    fetchSessions();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const fetchSessions = async () => {
    try {
      const res = await apiClient.get("/api/v1/chat/sessions");
      setSessions(res.data);
      if (res.data.length > 0 && !activeSessionId) {
        setActiveSessionId(res.data[0].id);
      } else if (res.data.length === 0) {
        createSession();
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : "An error occurred");
    }
  };

  const fetchMessages = async (sessionId: string) => {
    try {
      const res = await apiClient.get(`/api/v1/chat/sessions/${sessionId}/messages`);
      setMessages(res.data);
    } catch (err) {
      alert(err instanceof Error ? err.message : "An error occurred");
    }
  };

  const createSession = async () => {
    try {
      const res = await apiClient.post("/api/v1/chat/sessions", { title: "New Conversation" });
      setSessions([res.data, ...sessions]);
      setActiveSessionId(res.data.id);
      setMessages([]);
    } catch (err) {
      alert(err instanceof Error ? err.message : "An error occurred");
    }
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !activeSessionId) return;

    const userMessage = {
      content: input,
      action,
      model,
      aspect_ratio: action === "create_image" ? aspectRatio : undefined,
    };

    setInput("");
    setIsSending(true);

    try {
      // Optimistically add message
      setMessages(prev => [...prev, { ...userMessage, role: "user", id: "temp", created_at: new Date().toISOString() }]);
      
      await apiClient.post(`/api/v1/chat/sessions/${activeSessionId}/messages`, userMessage);
      await fetchMessages(activeSessionId);
    } catch (err) {
      alert(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="flex h-[calc(100vh-80px)] w-full max-w-[1600px] mx-auto overflow-hidden rounded-2xl border border-white/10 glass-panel shadow-2xl">
      
      {/* ── Sidebar ── */}
      <div className="w-64 bg-black/40 border-r border-white/5 flex flex-col">
        <div className="p-4">
          <button 
            onClick={createSession}
            className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-primary/20 text-primary hover:bg-primary/30 border border-primary/30 transition-all text-sm font-medium"
          >
            <PlusCircle className="w-4 h-4" />
            New Chat
          </button>
        </div>
        
        <div className="flex-1 overflow-y-auto px-3 space-y-1">
          <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider px-2 py-3">
            Recent Chats
          </div>
          {sessions.map(s => (
            <button
              key={s.id}
              onClick={() => setActiveSessionId(s.id)}
              className={`w-full text-left px-3 py-3 rounded-lg text-sm flex items-center gap-3 transition-colors ${
                activeSessionId === s.id ? "bg-white/10 text-white" : "text-white/60 hover:bg-white/5 hover:text-white"
              }`}
            >
              <MessageSquare className="w-4 h-4 opacity-50" />
              <div className="flex-1 truncate">{s.title}</div>
            </button>
          ))}
        </div>
      </div>

      {/* ── Main Chat Area ── */}
      <div className="flex-1 flex flex-col bg-black/20">
        
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 md:p-8 space-y-6">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center opacity-50">
              <Cpu className="w-12 h-12 mb-4" />
              <h2 className="text-xl font-medium text-white mb-2">Welcome to AI Studio</h2>
              <p className="max-w-md text-sm">Describe what you want to create below, and select an action to start building.</p>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div key={msg.id || idx} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[80%] rounded-2xl p-4 ${
                  msg.role === "user" 
                    ? "bg-primary/20 text-white border border-primary/30 rounded-br-none" 
                    : "bg-white/5 text-white/90 border border-white/10 rounded-bl-none"
                }`}>
                  <div className="whitespace-pre-wrap text-sm leading-relaxed">{msg.content}</div>
                  
                  {/* Visuals */}
                  {msg.image_urls && msg.image_urls.length > 0 && (
                    <div className="grid grid-cols-2 gap-2 mt-4">
                      {msg.image_urls.map((url: string, i: number) => (
                        <img key={i} src={url} alt="Generated" className="rounded-lg border border-white/10 w-full aspect-video object-cover" />
                      ))}
                    </div>
                  )}

                  
                  {/* Status indicator for assistant messages */}
                  {msg.role === "assistant" && msg.status === "PENDING" && (
                    <div className="mt-3 flex items-center gap-2 text-xs text-primary animate-pulse">
                      <Loader2 className="w-3 h-3 animate-spin" />
                      Generating content...
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
            <div className="flex items-center gap-3">
              <select 
                value={action} 
                onChange={(e) => setAction(e.target.value)}
                className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:border-primary transition-colors"
              >
                <option value="refine_prompt">Refine Prompt</option>
                <option value="create_image">Create Image</option>
              </select>

              <select 
                value={model} 
                onChange={(e) => setModel(e.target.value)}
                className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:border-primary transition-colors"
              >
                {action === "refine_prompt" && (
                  <>
                    <option value="gemini-3.1-flash">Gemini 3.1 Flash</option>
                    <option value="gemini-3.1-pro-preview">Gemini 3.1 Pro</option>
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
                  className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white outline-none focus:border-primary transition-colors"
                >
                  <option value="16:9">16:9 (Landscape)</option>
                  <option value="9:16">9:16 (Portrait)</option>
                  <option value="1:1">1:1 (Square)</option>
                  <option value="4:3">4:3</option>
                  <option value="3:4">3:4</option>
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
              />
              <button 
                type="submit"
                disabled={isSending || !input.trim() || !activeSessionId}
                className="absolute right-2 top-2 p-2 bg-primary hover:bg-primary/90 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
              >
                {isSending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </button>
            </div>
            
          </form>
        </div>
        
      </div>
    </div>
  );
}
