"use client";

import { useState, useRef, useEffect, KeyboardEvent } from "react";
import {
  Plus,
  AlertTriangle,
  Hand,
  ShieldCheck,
  Check,
  ChevronRight,
  ChevronDown,
  RotateCcw,
  Mic,
  ArrowUp,
  Folder,
  Terminal,
  Lightbulb,
  BookOpen,
  Clock,
  Sparkles,
  Copy,
  CheckCheck,
  Square,
  ChevronUp,
  Brain,
  Layers,
  Laptop,
  X,
  Download,
  Paperclip,
  Cpu,
  Link2,
} from "lucide-react";
import { useUIStore, ApprovalMode, ModelOption, ReasoningEffort } from "../../store/ui-store";
import { apiUrl } from "../../services/backend";
import { streamChat, type ChatMediaItem, type ChatProvider, type ChatRoute, type ChatSource } from "./chat-service";
import { useConversationStore } from "./stores/conversation-store";
import { MarkdownRenderer } from "./markdown-renderer";
import type { ChatMessage } from "./types";

/** How a model choice in the picker maps onto a real backend route.
 *
 *  "auto" is the point of this: the backend classifies the request first and
 *  then picks the engine for it -- deterministic work (a sum, the clock, an
 *  image render) stays local, writing code or prose goes to the generative
 *  model that is actually configured. The two explicit entries exist for the
 *  cases where the user wants to force it: Local Core never leaves the
 *  machine, Omni always uses the configured cloud model.
 */
function providerFor(model: ModelOption): ChatProvider {
  if (model === "JARVIS J-Local Core") return "local";
  if (model === "JARVIS J-4.0 Omni") return "cloud";
  return "auto";
}

/** Human label for the engine that actually answered. */
function routeLabel(route?: ChatRoute): string {
  if (!route) return "";
  if (route.used === false) return `no model needed · ${route.answered_by || route.task}`;
  const where = route.provider === "cloud" ? "cloud" : "local";
  return `${where} · ${route.model}`;
}

const KB = 1024;

/** "12.4 KB" / "1.2 MB" -- so an attachment chip shows something verifiable. */
function fileSize(bytes: number): string {
  if (bytes < KB) return `${bytes} B`;
  if (bytes < KB * KB) return `${(bytes / KB).toFixed(1)} KB`;
  return `${(bytes / (KB * KB)).toFixed(1)} MB`;
}

/** Files staged for the next turn. They are really uploaded: `handleSend` passes
 *  this list to `streamChat`, which base64-encodes each one into the request. */
function AttachmentTray({ files, onRemove }: { files: File[]; onRemove: (index: number) => void }) {
  if (!files.length) return null;
  return (
    <div className="chat-attach-tray">
      {files.map((file, index) => (
        <span className="chat-attach-chip" key={`${file.name}-${index}`}>
          <Paperclip size={11} />
          <span className="chat-attach-name" title={file.name}>
            {file.name}
          </span>
          <span className="chat-attach-size">{fileSize(file.size)}</span>
          <button
            type="button"
            onClick={() => onRemove(index)}
            aria-label={`Remove ${file.name}`}
            title="Remove"
          >
            <X size={11} />
          </button>
        </span>
      ))}
    </div>
  );
}

/** Images and video the backend actually produced or fetched for a turn. The
 *  bytes live in the local media store; `url` is a path on the backend, which
 *  is why every src goes through `apiUrl`. Without this block the generated
 *  file existed on disk and was never shown -- the "it doesn't generate" bug. */
function MediaGallery({ items }: { items: ChatMediaItem[] }) {
  if (!items.length) return null;
  return (
    <div className="chat-media-grid">
      {items.map((item, index) => {
        const src = apiUrl(item.url);
        const isVideo = (item.media_type || "").startsWith("video");
        return (
          <figure className="chat-media-card" key={item.media_id || `${item.url}-${index}`}>
            {isVideo ? (
              <video src={src} controls preload="metadata" />
            ) : (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={src} alt={item.caption || "generated media"} loading="lazy" />
            )}
            <figcaption>
              <span title={item.caption || ""}>{item.caption || item.kind || "media"}</span>
              <a href={src} download target="_blank" rel="noreferrer" title="Open / download">
                <Download size={12} />
              </a>
            </figcaption>
          </figure>
        );
      })}
    </div>
  );
}

/** Links the turn was grounded on, when a tool really consulted them. */
function SourceList({ items }: { items: ChatSource[] }) {
  if (!items.length) return null;
  return (
    <div className="chat-source-list">
      {items.slice(0, 8).map((source, index) => (
        <a
          key={`${source.url}-${index}`}
          href={source.url}
          target="_blank"
          rel="noreferrer"
          title={source.url}
        >
          <Link2 size={11} />
          <span>{source.title || source.url}</span>
        </a>
      ))}
    </div>
  );
}

export function CodexHarness() {
  const {
    approvalMode,
    setApprovalMode,
    selectedModel,
    setSelectedModel,
    reasoningEffort,
    setReasoningEffort,
    activeProject,
    activeDirectory,
    togglePanel,
    setPluginsOpen,
    activePlugins,
  } = useUIStore();

  const { conversations, activeId, hydrate, update } = useConversationStore();
  const conversation = conversations.find((c) => c.id === activeId) || conversations[0];

  const [prompt, setPrompt] = useState("");
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [isListening, setIsListening] = useState(false);
  const [approvalPopoverOpen, setApprovalPopoverOpen] = useState(false);
  const [modelPopoverOpen, setModelPopoverOpen] = useState(false);
  const [modelSubmenu, setModelSubmenu] = useState<"none" | "model" | "effort">("none");
  const [isStreaming, setIsStreaming] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [expandedReasoning, setExpandedReasoning] = useState<Record<string, boolean>>({});
  const [voiceNotice, setVoiceNotice] = useState("");

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [conversation?.messages, isStreaming]);

  const approvalOptions: {
    mode: ApprovalMode;
    title: string;
    description: string;
    icon: React.ElementType;
  }[] = [
    {
      mode: "ask_approval",
      title: "Ask for approval",
      description: "Always ask to edit external files and use the internet",
      icon: Hand,
    },
    {
      mode: "approve_for_me",
      title: "Approve for me",
      description: "Only ask for actions detected as potentially unsafe",
      icon: ShieldCheck,
    },
    {
      mode: "full_access",
      title: "Full access",
      description: "Unrestricted access to the internet and any file on your computer",
      icon: AlertTriangle,
    },
  ];

  const jarvisModelsList: ModelOption[] = [
    "JARVIS J-3.1 Ultra",
    "JARVIS J-4.0 Omni",
    "JARVIS J-2.5 Pro",
    "JARVIS J-1.1 Turbo",
    "JARVIS J-1.0 Mini",
    "JARVIS J-Local Core",
  ];
  const effortList: ReasoningEffort[] = ["High", "Medium", "Low"];

  const currentApproval =
    approvalOptions.find((o) => o.mode === approvalMode) || approvalOptions[2];

  const toggleReasoning = (msgId: string) => {
    setExpandedReasoning((prev) => ({ ...prev, [msgId]: !prev[msgId] }));
  };

  /** Patch one message in the live store. Every stream callback needs this, and
   *  each one has to re-read the store first: the closure's `conversation` is a
   *  snapshot from render, so building on it drops earlier frames. */
  const patchMessage = (conversationId: string, messageId: string, change: Partial<ChatMessage>) => {
    const latest = useConversationStore
      .getState()
      .conversations.find((c) => c.id === conversationId);
    if (!latest) return;
    update(conversationId, {
      messages: latest.messages.map((m) => (m.id === messageId ? { ...m, ...change } : m)),
    });
  };

  const appendTrace = (conversationId: string, messageId: string, type: string, detail: string) => {
    const latest = useConversationStore
      .getState()
      .conversations.find((c) => c.id === conversationId);
    const target = latest?.messages.find((m) => m.id === messageId);
    if (!latest || !target) return;
    patchMessage(conversationId, messageId, {
      execution: [...(target.execution || []), { type, detail, createdAt: Date.now() }],
    });
  };

  const handleSend = async (customPrompt?: string) => {
    if (isStreaming || !conversation) return;
    const files = pendingFiles;
    // The backend requires non-empty text, so an attachment-only send gets an
    // explicit instruction -- shown in the bubble, not smuggled in.
    const text =
      (customPrompt || prompt).trim() ||
      (files.length ? "Read the attached file(s) and tell me what is in them." : "");
    if (!text) return;

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      createdAt: Date.now(),
      attachments: [],
      attachmentNames: files.map((file) => file.name),
    };

    const assistantId = crypto.randomUUID();
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      createdAt: Date.now(),
      attachments: [],
      execution: [
        {
          type: "reasoning",
          detail:
            providerFor(selectedModel) === "auto"
              ? `Classifying the request and picking the engine for it (${reasoningEffort} effort)...`
              : `Routing to ${selectedModel} (${reasoningEffort} effort)...`,
          createdAt: Date.now(),
        },
      ],
    };

    const newMessages = [...conversation.messages, userMessage, assistantMessage];
    update(conversation.id, {
      title: conversation.messages.length === 0 ? text.slice(0, 48) : conversation.title,
      messages: newMessages,
    });

    setPrompt("");
    setPendingFiles([]);
    setIsStreaming(true);
    abortControllerRef.current = new AbortController();

    try {
      let accumulated = "";
      await streamChat(
        text,
        files,
        providerFor(selectedModel),
        abortControllerRef.current.signal,
        (token) => {
          accumulated += token;
          patchMessage(conversation.id, assistantId, { content: accumulated });
        },
        (event) => {
          // "route" and "media" carry structured payloads handled below; the
          // trace only needs the human-readable line for each other frame.
          if (event.type === "route" || event.type === "media" || event.type === "sources") return;
          const detail =
            event.type === "intent"
              ? `Intent: ${event.payload.intent} (${Math.round(Number(event.payload.confidence ?? 0) * 100)}%)`
              : event.type === "tool"
                ? `${event.payload.tool}${event.payload.detail ? `: ${event.payload.detail}` : ""}${event.payload.ok === false ? " (failed)" : ""}`
                : String(
                    event.payload.message || event.payload.status || event.payload.name || event.type
                  );
          appendTrace(conversation.id, assistantId, event.type, detail);
        },
        {
          onRoute: (route) => {
            patchMessage(conversation.id, assistantId, { route });
            appendTrace(
              conversation.id,
              assistantId,
              "route",
              `Engine: ${route.provider} · ${route.model} — ${route.reason}`
            );
          },
          onMedia: (items) => patchMessage(conversation.id, assistantId, { media: items }),
          onSources: (items) => patchMessage(conversation.id, assistantId, { sources: items }),
        }
      );
      setIsStreaming(false);
    } catch (err: any) {
      if (err?.name === "AbortError") {
        setIsStreaming(false);
        return;
      }
      // Report the failure. The previous version wrote a canned "all tools are
      // online and ready" message here, so a dead backend or a failed tool
      // looked exactly like a successful turn -- with nothing generated.
      const reason = String(err?.message || err || "unknown error");
      const offline = /failed to fetch|networkerror|load failed/i.test(reason);
      const message = offline
        ? `I could not reach the JARVIS backend, so nothing ran.\n\n\`\`\`\n${reason}\n\`\`\`\n\nStart it with \`uvicorn app.main:app --port 8000\` from the \`backend\` folder, then send this again.`
        : `That turn failed, so I am not going to pretend it worked.\n\n\`\`\`\n${reason}\n\`\`\``;

      const latest = useConversationStore
        .getState()
        .conversations.find((c) => c.id === conversation.id);
      const target = latest?.messages.find((m) => m.id === assistantId);
      patchMessage(conversation.id, assistantId, {
        content: target?.content ? `${target.content}\n\n---\n\n${message}` : message,
        failed: true,
      });
      setIsStreaming(false);
    }
  };

  const handleStop = () => {
    abortControllerRef.current?.abort();
    setIsStreaming(false);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const toggleVoice = () => {
    // Real dictation. This used to set `isListening` and then paste a canned
    // sentence after two seconds, so the mic never captured anything the user
    // actually said.
    const Recognition: any =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!Recognition) {
      setVoiceNotice("This browser has no speech recognition. Chrome or Edge support it; typing works everywhere.");
      return;
    }
    if (isListening) {
      recognitionRef.current?.stop();
      return;
    }

    const recognition = new Recognition();
    recognition.lang = navigator.language || "en-US";
    recognition.interimResults = true;
    recognition.continuous = false;
    const base = prompt ? `${prompt} ` : "";

    recognition.onresult = (event: any) => {
      let transcript = "";
      for (let index = 0; index < event.results.length; index += 1) {
        transcript += event.results[index][0].transcript;
      }
      setPrompt(base + transcript);
    };
    recognition.onerror = (event: any) => {
      setVoiceNotice(
        event?.error === "not-allowed"
          ? "Microphone access was blocked, so I can't hear you. Allow it in the browser's site settings."
          : `Dictation stopped: ${event?.error || "unknown error"}`
      );
      setIsListening(false);
    };
    recognition.onend = () => {
      setIsListening(false);
      recognitionRef.current = null;
    };

    setVoiceNotice("");
    recognitionRef.current = recognition;
    setIsListening(true);
    recognition.start();
  };

  const addFiles = (incoming: FileList | null) => {
    if (!incoming?.length) return;
    setPendingFiles((current) => [...current, ...Array.from(incoming)].slice(0, 5));
  };

  const removeFile = (index: number) => {
    setPendingFiles((current) => current.filter((_, position) => position !== index));
  };

  const copyMessage = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const hasMessages = conversation && conversation.messages.length > 0;
  const canSend = Boolean(prompt.trim()) || pendingFiles.length > 0;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        width: "100%",
        overflow: "hidden",
        position: "relative",
      }}
    >
      {/* If No Messages: Hero Welcome View */}
      {!hasMessages ? (
        <div className="codex-viewport">
          <div className="codex-hero-container">
            {/* Hero Title */}
            <h1 className="codex-hero-title">What should we work on?</h1>

            {/* Central Floating Codex Prompt Card */}
            <div className="codex-prompt-card">
              <textarea
                ref={textareaRef}
                className="codex-textarea"
                placeholder="Work with JARVIS"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={onKeyDown}
                rows={1}
                autoFocus
              />

              <AttachmentTray files={pendingFiles} onRemove={removeFile} />
              {voiceNotice && (
                <div className="chat-voice-notice">
                  <AlertTriangle size={12} />
                  <span>{voiceNotice}</span>
                  <button type="button" onClick={() => setVoiceNotice("")} aria-label="Dismiss">
                    <X size={11} />
                  </button>
                </div>
              )}

              {/* Action Row Inside Card */}
              <div className="codex-card-actions-row">
                <div className="card-actions-left">
                  <button
                    className="add-attach-btn"
                    title="Attach files or context"
                    onClick={() => fileInputRef.current?.click()}
                    aria-label="Add files"
                  >
                    <Plus size={18} />
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    hidden
                    onChange={(e) => {
                      addFiles(e.target.files);
                      // Clearing the value lets the same file be re-picked after
                      // it was removed from the tray.
                      e.target.value = "";
                    }}
                  />

                  {/* Approval Mode Selector Pill */}
                  <div style={{ position: "relative" }}>
                    <button
                      className={`approval-pill-btn ${
                        approvalMode === "full_access" ? "warning" : ""
                      }`}
                      onClick={() => {
                        setApprovalPopoverOpen(!approvalPopoverOpen);
                        setModelPopoverOpen(false);
                      }}
                      aria-label="Approval Mode"
                    >
                      <currentApproval.icon size={14} />
                      <span>{currentApproval.title}</span>
                    </button>

                    {/* Approval Mode Popover Modal */}
                    {approvalPopoverOpen && (
                      <>
                        <div
                          className="popover-backdrop"
                          onClick={() => setApprovalPopoverOpen(false)}
                        />
                        <div className="approval-popover">
                          <div className="popover-header">
                            <span>How should JARVIS actions be approved?</span>
                            <a href="#learn-more" onClick={(e) => e.preventDefault()}>
                              Learn more
                            </a>
                          </div>

                          {approvalOptions.map((opt) => {
                            const Icon = opt.icon;
                            const isSelected = approvalMode === opt.mode;
                            return (
                              <button
                                key={opt.mode}
                                className={`approval-option-btn ${isSelected ? "selected" : ""}`}
                                onClick={() => {
                                  setApprovalMode(opt.mode);
                                  setApprovalPopoverOpen(false);
                                }}
                              >
                                <Icon size={16} className="option-icon" />
                                <div className="option-content">
                                  <div className="option-title">{opt.title}</div>
                                  <div className="option-desc">{opt.description}</div>
                                </div>
                                {isSelected && <Check size={16} className="option-check" />}
                              </button>
                            );
                          })}
                        </div>
                      </>
                    )}
                  </div>
                </div>

                <div className="card-actions-right">
                  {/* Model & Effort Selector Pill */}
                  <div style={{ position: "relative" }}>
                    <button
                      className="model-pill-btn"
                      onClick={() => {
                        setModelPopoverOpen(!modelPopoverOpen);
                        setApprovalPopoverOpen(false);
                        setModelSubmenu("none");
                      }}
                      aria-label="Select Model & Reasoning Effort"
                    >
                      <span>
                        {selectedModel} {reasoningEffort}
                      </span>
                      <ChevronDown size={14} />
                    </button>

                    {/* Model & Effort Popover Modal */}
                    {modelPopoverOpen && (
                      <>
                        <div
                          className="popover-backdrop"
                          onClick={() => {
                            setModelPopoverOpen(false);
                            setModelSubmenu("none");
                          }}
                        />
                        <div className="model-popover">
                          <button
                            className="reset-default-btn"
                            onClick={() => {
                              setSelectedModel("JARVIS J-3.1 Ultra");
                              setReasoningEffort("High");
                              setModelPopoverOpen(false);
                            }}
                          >
                            <span>Reset to default</span>
                            <RotateCcw size={12} />
                          </button>

                          <div style={{ position: "relative" }}>
                            <button
                              className="model-menu-row"
                              onClick={() =>
                                setModelSubmenu(modelSubmenu === "model" ? "none" : "model")
                              }
                            >
                              <span>Model</span>
                              <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                                <span style={{ color: "var(--text-muted)", fontSize: 12 }}>
                                  {selectedModel.split(" ")[1] || selectedModel}
                                </span>
                                <ChevronRight size={13} />
                              </div>
                            </button>

                            {modelSubmenu === "model" && (
                              <div className="model-sublevel-menu">
                                {jarvisModelsList.map((m) => (
                                  <button
                                    key={m}
                                    className="model-menu-row"
                                    onClick={() => {
                                      setSelectedModel(m);
                                      setModelPopoverOpen(false);
                                      setModelSubmenu("none");
                                    }}
                                  >
                                    <span>{m}</span>
                                    {selectedModel === m && (
                                      <Check size={14} color="#10a37f" />
                                    )}
                                  </button>
                                ))}
                              </div>
                            )}
                          </div>

                          <div style={{ position: "relative" }}>
                            <button
                              className="model-menu-row"
                              onClick={() =>
                                setModelSubmenu(modelSubmenu === "effort" ? "none" : "effort")
                              }
                            >
                              <span>Effort</span>
                              <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                                <span style={{ color: "var(--text-muted)", fontSize: 12 }}>
                                  {reasoningEffort}
                                </span>
                                <ChevronRight size={13} />
                              </div>
                            </button>

                            {modelSubmenu === "effort" && (
                              <div className="model-sublevel-menu">
                                {effortList.map((eff) => (
                                  <button
                                    key={eff}
                                    className="model-menu-row"
                                    onClick={() => {
                                      setReasoningEffort(eff);
                                      setModelPopoverOpen(false);
                                      setModelSubmenu("none");
                                    }}
                                  >
                                    <span>{eff}</span>
                                    {reasoningEffort === eff && (
                                      <Check size={14} color="#10a37f" />
                                    )}
                                  </button>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      </>
                    )}
                  </div>

                  {/* Voice Input Button */}
                  <button
                    className={`mic-btn ${isListening ? "listening" : ""}`}
                    title="Voice Dictation"
                    onClick={toggleVoice}
                    aria-label="Voice input"
                  >
                    <Mic size={17} />
                  </button>

                  {/* Send / Run Button */}
                  <button
                    className="send-btn"
                    title="Execute (Enter)"
                    onClick={() => handleSend()}
                    disabled={!canSend && !isStreaming}
                    aria-label="Run Prompt"
                  >
                    <ArrowUp size={17} />
                  </button>
                </div>
              </div>

              {/* Bottom Card Footer Strip (Matching Image 1) */}
              <div className="codex-card-footer">
                <div className="card-footer-left">
                  <button
                    className="footer-dir-pill"
                    title="Active Workspace Project"
                    onClick={() => togglePanel("rightOpen")}
                  >
                    <Folder size={14} />
                    <span>{activeProject}</span>
                  </button>

                  <button
                    className="footer-plugins-pill"
                    title="Configure Plugins"
                    onClick={() => setPluginsOpen(true)}
                  >
                    <span className="plugin-micro-icons">
                      <span style={{ display: "inline-block", width: 7, height: 7, borderRadius: 2, background: "#3b82f6" }} />
                      <span style={{ display: "inline-block", width: 7, height: 7, borderRadius: 2, background: "#ef4444" }} />
                      <span style={{ display: "inline-block", width: 7, height: 7, borderRadius: 2, background: "#10a37f" }} />
                    </span>
                    <span>Plugins</span>
                  </button>
                </div>

                <button
                  className="footer-terminal-btn"
                  title="Toggle Host PowerShell Drawer (Ctrl+`)"
                  onClick={() => togglePanel("terminalOpen")}
                  aria-label="Open Terminal"
                >
                  <Laptop size={14} />
                </button>
              </div>
            </div>

            {/* Suggestion Quick Action Buttons */}
            <div className="codex-suggestions">
              <button
                className="suggestion-item-btn"
                onClick={() =>
                  handleSend("Create a new component file or build an interactive web interface")
                }
              >
                <Lightbulb size={16} />
                <span>Create a file or build a site</span>
              </button>

              <button
                className="suggestion-item-btn"
                onClick={() =>
                  handleSend("Research repository dependencies and plan the architecture next steps")
                }
              >
                <BookOpen size={16} />
                <span>Research and plan next steps</span>
              </button>

              <button
                className="suggestion-item-btn"
                onClick={() =>
                  handleSend("Automate routine maintenance, test runs, and recurring jobs")
                }
              >
                <Clock size={16} />
                <span>Automate routine and recurring work</span>
              </button>
            </div>
          </div>
        </div>
      ) : (
        /* If Messages Exist: Live Conversation & Work Session View */
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            minHeight: 0,
            overflow: "hidden",
          }}
        >
          {/* Scrollable Message History */}
          <div
            ref={scrollRef}
            style={{
              flex: 1,
              overflowY: "auto",
              padding: "24px 20px 140px",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 20,
            }}
          >
            <div style={{ width: "100%", maxWidth: 760, display: "flex", flexDirection: "column", gap: 18 }}>
              {conversation.messages.map((msg) => {
                const isUser = msg.role === "user";
                const isReasoningOpen = expandedReasoning[msg.id] ?? false;

                return (
                  <div
                    key={msg.id}
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      alignSelf: isUser ? "flex-end" : "flex-start",
                      width: "100%",
                      maxWidth: isUser ? "85%" : "100%",
                    }}
                  >
                    {/* User Message Bubble */}
                    {isUser ? (
                      <div
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          alignItems: "flex-end",
                          gap: 4,
                        }}
                      >
                        <div
                          style={{
                            alignSelf: "flex-end",
                            background: "var(--bg-pill)",
                            color: "var(--text-main)",
                            padding: "10px 16px",
                            borderRadius: "18px 18px 4px 18px",
                            fontSize: 14,
                            lineHeight: 1.5,
                            boxShadow: "var(--shadow-sm)",
                            whiteSpace: "pre-wrap",
                          }}
                        >
                          {msg.content}
                        </div>
                        {msg.attachmentNames && msg.attachmentNames.length > 0 && (
                          <div className="chat-attach-tray sent">
                            {msg.attachmentNames.map((name) => (
                              <span className="chat-attach-chip" key={name}>
                                <Paperclip size={11} />
                                <span className="chat-attach-name">{name}</span>
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ) : (
                      /* Assistant Message & Harness Output */
                      <div
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          gap: 8,
                          width: "100%",
                        }}
                      >
                        {/* Reasoning / Thinking Collapsible Block */}
                        {msg.execution && msg.execution.length > 0 && (
                          <div
                            style={{
                              border: "1px solid var(--border-subtle)",
                              borderRadius: 8,
                              background: "var(--bg-card-subtle)",
                              overflow: "hidden",
                              marginBottom: 4,
                            }}
                          >
                            <button
                              onClick={() => toggleReasoning(msg.id)}
                              style={{
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "space-between",
                                width: "100%",
                                padding: "6px 10px",
                                border: 0,
                                background: "transparent",
                                fontSize: 12,
                                color: "var(--text-secondary)",
                                cursor: "pointer",
                              }}
                            >
                              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                                <Brain size={14} color="#8b5cf6" />
                                <span style={{ fontWeight: 500 }}>
                                  {/* The engine that actually ran this turn, not
                                      the label in the picker. */}
                                  Reasoning ({routeLabel(msg.route) || `${selectedModel} · ${reasoningEffort}`})
                                </span>
                              </div>
                              {isReasoningOpen ? (
                                <ChevronUp size={14} />
                              ) : (
                                <ChevronDown size={14} />
                              )}
                            </button>

                            {isReasoningOpen && (
                              <div
                                style={{
                                  padding: "8px 12px",
                                  borderTop: "1px solid var(--border-subtle)",
                                  fontSize: 11,
                                  color: "var(--text-secondary)",
                                  display: "flex",
                                  flexDirection: "column",
                                  gap: 4,
                                }}
                              >
                                {msg.execution.map((step, sIdx) => (
                                  <div
                                    key={sIdx}
                                    style={{
                                      display: "flex",
                                      alignItems: "center",
                                      gap: 6,
                                    }}
                                  >
                                    <Sparkles size={12} color="#10a37f" />
                                    <span>{step.detail}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )}

                        {/* Markdown Rendered Content */}
                        <div
                          style={{
                            fontSize: 14,
                            lineHeight: 1.6,
                            color: msg.failed ? "#fca5a5" : "var(--text-main)",
                            borderLeft: msg.failed ? "2px solid #ef4444" : undefined,
                            paddingLeft: msg.failed ? 10 : undefined,
                          }}
                        >
                          <MarkdownRenderer content={msg.content} />
                        </div>

                        {/* Anything the turn actually produced or cited. */}
                        {msg.media && msg.media.length > 0 && <MediaGallery items={msg.media} />}
                        {msg.sources && msg.sources.length > 0 && <SourceList items={msg.sources} />}

                        {/* Copy / Actions Bar */}
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 6,
                            marginTop: 4,
                          }}
                        >
                          <button
                            onClick={() => copyMessage(msg.content, msg.id)}
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 4,
                              padding: "3px 8px",
                              border: 0,
                              background: "transparent",
                              color: "var(--text-muted)",
                              borderRadius: 4,
                              fontSize: 11,
                              cursor: "pointer",
                            }}
                          >
                            {copiedId === msg.id ? (
                              <CheckCheck size={12} color="#10a37f" />
                            ) : (
                              <Copy size={12} />
                            )}
                            <span>{copiedId === msg.id ? "Copied" : "Copy"}</span>
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}

              {isStreaming && (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    color: "var(--text-secondary)",
                    fontSize: 13,
                  }}
                >
                  <Sparkles size={14} className="animate-spin" color="#10a37f" />
                  <span>JARVIS is generating response...</span>
                </div>
              )}
            </div>
          </div>

          {/* Docked Composer at the Bottom */}
          <div
            style={{
              position: "absolute",
              bottom: 0,
              left: 0,
              right: 0,
              padding: "12px 20px 16px",
              background: "linear-gradient(to top, var(--bg-app) 70%, transparent)",
              display: "flex",
              justifyContent: "center",
              zIndex: 30,
            }}
          >
            <div
              className="codex-prompt-card"
              style={{
                maxWidth: 760,
                width: "100%",
                boxShadow: "var(--shadow-lg)",
              }}
            >
              <textarea
                ref={textareaRef}
                className="codex-textarea"
                placeholder="Ask follow up or run code in JARVIS"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={onKeyDown}
                rows={1}
              />

              <AttachmentTray files={pendingFiles} onRemove={removeFile} />
              {voiceNotice && (
                <div className="chat-voice-notice">
                  <AlertTriangle size={12} />
                  <span>{voiceNotice}</span>
                  <button type="button" onClick={() => setVoiceNotice("")} aria-label="Dismiss">
                    <X size={11} />
                  </button>
                </div>
              )}

              <div className="codex-card-actions-row">
                <div className="card-actions-left">
                  <button
                    className="add-attach-btn"
                    title="Attach files or context"
                    onClick={() => fileInputRef.current?.click()}
                    aria-label="Add files"
                  >
                    <Plus size={18} />
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    hidden
                    onChange={(e) => {
                      addFiles(e.target.files);
                      e.target.value = "";
                    }}
                  />

                  {/* Approval Mode Pill */}
                  <button
                    className={`approval-pill-btn ${
                      approvalMode === "full_access" ? "warning" : ""
                    }`}
                    onClick={() => setApprovalPopoverOpen(!approvalPopoverOpen)}
                  >
                    <currentApproval.icon size={14} />
                    <span>{currentApproval.title}</span>
                  </button>
                </div>

                <div className="card-actions-right">
                  <button
                    className="model-pill-btn"
                    onClick={() => setModelPopoverOpen(!modelPopoverOpen)}
                  >
                    <span>
                      {selectedModel} {reasoningEffort}
                    </span>
                    <ChevronDown size={14} />
                  </button>

                  <button
                    className={`mic-btn ${isListening ? "listening" : ""}`}
                    title="Voice Dictation"
                    onClick={toggleVoice}
                  >
                    <Mic size={17} />
                  </button>

                  {isStreaming ? (
                    <button
                      className="send-btn"
                      title="Stop Generation"
                      onClick={handleStop}
                      style={{ background: "#ef4444" }}
                    >
                      <Square size={14} />
                    </button>
                  ) : (
                    <button
                      className="send-btn"
                      title="Send Message (Enter)"
                      onClick={() => handleSend()}
                      disabled={!canSend}
                    >
                      <ArrowUp size={17} />
                    </button>
                  )}
                </div>
              </div>

              {/* Bottom Card Footer Strip */}
              <div className="codex-card-footer">
                <div className="card-footer-left">
                  <button
                    className="footer-dir-pill"
                    onClick={() => togglePanel("rightOpen")}
                  >
                    <Folder size={14} />
                    <span>{activeProject}</span>
                  </button>

                  <button
                    className="footer-plugins-pill"
                    onClick={() => setPluginsOpen(true)}
                  >
                    <span className="plugin-micro-icons">
                      <span style={{ display: "inline-block", width: 7, height: 7, borderRadius: 2, background: "#3b82f6" }} />
                      <span style={{ display: "inline-block", width: 7, height: 7, borderRadius: 2, background: "#ef4444" }} />
                      <span style={{ display: "inline-block", width: 7, height: 7, borderRadius: 2, background: "#10a37f" }} />
                    </span>
                    <span>Plugins</span>
                  </button>
                </div>

                <button
                  className="footer-terminal-btn"
                  title="Toggle PowerShell Drawer (Ctrl+`)"
                  onClick={() => togglePanel("terminalOpen")}
                >
                  <Laptop size={14} />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
