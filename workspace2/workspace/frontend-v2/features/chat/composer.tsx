"use client";

import { ChangeEvent, ClipboardEvent, useRef } from "react";
import { Camera, ImagePlus, Paperclip, Send, Square, X } from "lucide-react";
import type { ChatAttachment } from "./types";

type ComposerProps = {
  value: string;
  onChange: (value: string) => void;
  queue: ChatAttachment[];
  onFiles: (files: FileList | File[]) => void;
  onRemove: (id: string) => void;
  onSend: () => void;
  onCancel: () => void;
  sending: boolean;
  provider: "local" | "cloud";
  onProviderChange: (provider: "local" | "cloud") => void;
};

export function Composer({
  value,
  onChange,
  queue,
  onFiles,
  onRemove,
  onSend,
  onCancel,
  sending,
  provider,
  onProviderChange,
}: ComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const filesRef = useRef<HTMLInputElement>(null);
  const imagesRef = useRef<HTMLInputElement>(null);
  const cameraRef = useRef<HTMLInputElement>(null);

  const pick = (event: ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files ?? [];
    onFiles(files);
    event.currentTarget.value = "";
  };

  const paste = (event: ClipboardEvent<HTMLTextAreaElement>) => {
    const files = Array.from(event.clipboardData.files);
    if (files.length) {
      event.preventDefault();
      onFiles(files);
    }
  };

  return (
    <>
      <div className="upload-queue" aria-label="Upload queue">
        {queue.map((item) => (
          <span key={item.id}>
            <span>{item.file.name}</span>
            <progress value={item.progress} max="100" />
            <button aria-label={`Remove ${item.file.name}`} onClick={() => onRemove(item.id)}>
              <X size={12} />
            </button>
          </span>
        ))}
      </div>
      <div className="chat-composer">
        <div className="composer-tools" aria-label="Attachment controls">
          <button
            type="button"
            className="composer-tool-btn"
            title="Add files"
            aria-label="Add files"
            onClick={() => filesRef.current?.click()}
          >
            <Paperclip size={16} />
          </button>
          <button
            type="button"
            className="composer-tool-btn"
            title="Add image"
            aria-label="Add image"
            onClick={() => imagesRef.current?.click()}
          >
            <ImagePlus size={16} />
          </button>
          <button
            type="button"
            className="composer-tool-btn"
            title="Open camera"
            aria-label="Open camera"
            onClick={() => cameraRef.current?.click()}
          >
            <Camera size={16} />
          </button>
          <input ref={filesRef} type="file" multiple hidden onChange={pick} />
          <input ref={imagesRef} type="file" multiple accept="image/*" hidden onChange={pick} />
          <input ref={cameraRef} type="file" accept="image/*" capture="environment" hidden onChange={pick} />
        </div>
        <textarea
          ref={textareaRef}
          value={value}
          onPaste={paste}
          onChange={(event) => {
            onChange(event.target.value);
            event.currentTarget.style.height = "auto";
            event.currentTarget.style.height = `${event.currentTarget.scrollHeight}px`;
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
              event.preventDefault();
              onSend();
            }
          }}
          placeholder="Message JARVIS · Ctrl+Enter to send"
        />
        <select
          aria-label="Connect options"
          value={provider}
          onChange={(event) => onProviderChange(event.target.value as "local" | "cloud")}
          title="Connect options"
        >
          <option value="local">Local</option>
          <option value="cloud">OpenRouter / cloud</option>
        </select>
        {sending ? (
          <button aria-label="Stop generation" onClick={onCancel}>
            <Square />
          </button>
        ) : (
          <button aria-label="Send message" onClick={onSend}>
            <Send />
          </button>
        )}
      </div>
    </>
  );
}
