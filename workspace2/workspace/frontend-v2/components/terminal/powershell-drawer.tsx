"use client";

import { useState, useRef, useEffect, KeyboardEvent } from "react";
import { Folder, Plus, X, Trash2, Terminal as TerminalIcon } from "lucide-react";
import { useUIStore } from "../../store/ui-store";

interface TerminalHistoryItem {
  id: string;
  command: string;
  output: string;
  type: "command" | "output" | "error";
  timestamp: string;
}

export function PowerShellDrawer() {
  const { terminalOpen, togglePanel, activeDirectory, setActiveDirectory } = useUIStore();
  const [inputVal, setInputVal] = useState("");
  const [hostInfo, setHostInfo] = useState<{
    user: string;
    cwd: string;
    platform: string;
  }>({
    user: "user",
    cwd: activeDirectory || "workspace",
    platform: "win32",
  });

  const [history, setHistory] = useState<TerminalHistoryItem[]>([]);
  const [commandHistory, setCommandHistory] = useState<string[]>([]);
  const [historyIdx, setHistoryIdx] = useState(-1);
  const [running, setRunning] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);

  // Fetch real host info on mount
  useEffect(() => {
    fetch("/api/terminal")
      .then((res) => res.json())
      .then((data) => {
        if (data && data.cwd) {
          setHostInfo({
            user: data.user || "user",
            cwd: data.cwd,
            platform: data.platform || "win32",
          });
          if (!activeDirectory) {
            setActiveDirectory(data.cwd);
          }
          const isWin = (data.platform || "").startsWith("win");
          setHistory([
            {
              id: "banner-1",
              command: "",
              output: isWin
                ? "Windows PowerShell\nCopyright (C) Microsoft Corporation. All rights reserved.\n"
                : `JARVIS Terminal (${data.platform || "host"})\nConnected to local shell session.\n`,
              type: "output",
              timestamp: "",
            },
          ]);
        }
      })
      .catch(() => {
        setHistory([
          {
            id: "banner-1",
            command: "",
            output: "JARVIS Interactive Terminal\nShell host session ready.\n",
            type: "output",
            timestamp: "",
          },
        ]);
      });
  }, [activeDirectory, setActiveDirectory]);

  useEffect(() => {
    if (terminalOpen) {
      inputRef.current?.focus();
    }
  }, [terminalOpen]);

  useEffect(() => {
    if (viewportRef.current) {
      viewportRef.current.scrollTop = viewportRef.current.scrollHeight;
    }
  }, [history]);

  const handleCommand = async (cmd: string) => {
    const trimmed = cmd.trim();
    if (!trimmed) return;

    setCommandHistory((prev) => [...prev, trimmed]);
    setHistoryIdx(-1);

    const isWin = hostInfo.platform.startsWith("win");
    const promptPrefix = isWin ? `PS ${hostInfo.cwd}> ` : `${hostInfo.user}@host:${hostInfo.cwd}$ `;

    const newCmdItem: TerminalHistoryItem = {
      id: crypto.randomUUID(),
      command: trimmed,
      output: "",
      type: "command",
      timestamp: new Date().toLocaleTimeString(),
    };

    if (trimmed.toLowerCase() === "cls" || trimmed.toLowerCase() === "clear") {
      setHistory([]);
      setInputVal("");
      return;
    }

    setHistory((prev) => [...prev, newCmdItem]);
    setInputVal("");
    setRunning(true);

    try {
      const res = await fetch("/api/terminal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: trimmed, cwd: hostInfo.cwd }),
      });
      const result = await res.json();

      let outputText = "";
      let isError = false;

      if (result.stdout) {
        outputText += result.stdout;
      }
      if (result.stderr) {
        outputText += (outputText ? "\n" : "") + result.stderr;
        if (result.exitCode !== 0) isError = true;
      }
      if (!result.stdout && !result.stderr) {
        outputText = result.exitCode === 0 ? "(Process exited with code 0)" : `(Exit code ${result.exitCode})`;
      }

      if (result.cwd && result.cwd !== hostInfo.cwd) {
        setHostInfo((prev) => ({ ...prev, cwd: result.cwd }));
        setActiveDirectory(result.cwd);
      }

      const newOutputItem: TerminalHistoryItem = {
        id: crypto.randomUUID(),
        command: "",
        output: outputText,
        type: isError ? "error" : "output",
        timestamp: new Date().toLocaleTimeString(),
      };

      setHistory((prev) => [...prev, newOutputItem]);
    } catch (err: any) {
      setHistory((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          command: "",
          output: `Command failed to execute: ${err.message || err}`,
          type: "error",
          timestamp: new Date().toLocaleTimeString(),
        },
      ]);
    } finally {
      setRunning(false);
    }
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      handleCommand(inputVal);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (commandHistory.length > 0) {
        const nextIdx =
          historyIdx === -1 ? commandHistory.length - 1 : Math.max(0, historyIdx - 1);
        setHistoryIdx(nextIdx);
        setInputVal(commandHistory[nextIdx]);
      }
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      if (historyIdx !== -1) {
        const nextIdx = historyIdx + 1;
        if (nextIdx < commandHistory.length) {
          setHistoryIdx(nextIdx);
          setInputVal(commandHistory[nextIdx]);
        } else {
          setHistoryIdx(-1);
          setInputVal("");
        }
      }
    }
  };

  if (!terminalOpen) return null;

  const isWin = hostInfo.platform.startsWith("win");
  const tabLabel = isWin
    ? `${hostInfo.cwd.split("\\").pop() || "terminal"} - powershell.exe`
    : `${hostInfo.cwd.split("/").pop() || "terminal"} - bash`;

  const promptPrefix = isWin ? `PS ${hostInfo.cwd}> ` : `${hostInfo.user}@host:${hostInfo.cwd}$ `;

  return (
    <aside className="powershell-drawer" aria-label="Host Integrated Terminal">
      {/* Header with Tabs */}
      <div className="terminal-header-bar">
        <div className="terminal-tabs">
          <div className="terminal-tab">
            <TerminalIcon size={12} />
            <span style={{ maxWidth: 360, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {tabLabel}
            </span>
            <button
              className="terminal-tab-close"
              onClick={() => togglePanel("terminalOpen")}
              aria-label="Close Tab"
            >
              ✕
            </button>
          </div>
          <button className="terminal-add-tab" title="New Terminal Tab">
            <Plus size={13} />
          </button>
        </div>

        <div className="terminal-controls">
          <button
            className="terminal-ctrl-btn"
            title="Clear Console"
            onClick={() => setHistory([])}
          >
            <Trash2 size={13} />
          </button>
          <button
            className="terminal-ctrl-btn"
            title="Close Terminal Drawer"
            onClick={() => togglePanel("terminalOpen")}
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Terminal Content */}
      <div
        className="terminal-output-viewport"
        ref={viewportRef}
        onClick={() => inputRef.current?.focus()}
      >
        {history.map((item) => (
          <div key={item.id} className={`terminal-line ${item.type}`}>
            {item.type === "command" ? (
              <div>
                <span className="terminal-prompt-prefix">{promptPrefix}</span>
                <span>{item.command}</span>
              </div>
            ) : (
              <div>{item.output}</div>
            )}
          </div>
        ))}

        <div className="terminal-input-row">
          <span className="terminal-prompt-prefix">{promptPrefix}</span>
          <input
            ref={inputRef}
            type="text"
            className="terminal-prompt-input"
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            onKeyDown={onKeyDown}
            disabled={running}
            autoFocus
            spellCheck={false}
          />
        </div>
      </div>
    </aside>
  );
}
