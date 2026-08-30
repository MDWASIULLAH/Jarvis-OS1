"use client";

import { useState } from "react";
import { X, Clock, Plus, Calendar, Power } from "lucide-react";
import { useUIStore } from "../../store/ui-store";

export function ScheduledModal() {
  const { scheduledOpen, setScheduledOpen, scheduledTasks, toggleScheduledTask, addScheduledTask } =
    useUIStore();

  const [creating, setCreating] = useState(false);
  const [taskName, setTaskName] = useState("");
  const [taskCron, setTaskCron] = useState("Daily at 00:00");
  const [taskAction, setTaskAction] = useState("Run automated codebase lint & test harness");

  if (!scheduledOpen) return null;

  const handleCreate = () => {
    if (!taskName.trim()) return;
    addScheduledTask({
      name: taskName,
      cron: taskCron,
      action: taskAction,
      enabled: true,
      lastRun: "Just created (Ready)",
    });
    setTaskName("");
    setCreating(false);
  };

  return (
    <div className="modal-overlay" onClick={() => setScheduledOpen(false)}>
      <div className="modal-dialog-card" onClick={(e) => e.stopPropagation()}>
        {/* Modal Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            paddingBottom: 8,
            borderBottom: "1px solid var(--border-color)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 600 }}>
            <Clock size={17} color="#3b82f6" />
            <span>Scheduled & Recurring JARVIS Automations</span>
          </div>
          <button
            onClick={() => setScheduledOpen(false)}
            style={{
              border: 0,
              background: "transparent",
              cursor: "pointer",
              color: "var(--text-secondary)",
            }}
          >
            <X size={17} />
          </button>
        </div>

        {/* Task List */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 8,
            maxHeight: 340,
            overflowY: "auto",
          }}
        >
          {scheduledTasks.map((t) => (
            <div
              key={t.id}
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 5,
                padding: "10px 12px",
                borderRadius: 8,
                border: "1px solid var(--border-color)",
                background: "var(--bg-card-subtle)",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Calendar size={14} color="#3b82f6" />
                  <span style={{ fontWeight: 600, fontSize: 13 }}>{t.name}</span>
                </div>

                <button
                  onClick={() => toggleScheduledTask(t.id)}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 4,
                    padding: "3px 8px",
                    borderRadius: 999,
                    border: 0,
                    background: t.enabled ? "#dcfce7" : "var(--bg-pill)",
                    color: t.enabled ? "#15803d" : "var(--text-muted)",
                    fontSize: 11,
                    fontWeight: 500,
                    cursor: "pointer",
                  }}
                >
                  <Power size={11} />
                  <span>{t.enabled ? "Active" : "Paused"}</span>
                </button>
              </div>

              <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
                Frequency: <b>{t.cron}</b>
              </div>
              <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                Action: {t.action}
              </div>
              {t.lastRun && (
                <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
                  Last run: {t.lastRun}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Add New Schedule Form */}
        {creating ? (
          <div
            style={{
              padding: 10,
              borderRadius: 8,
              border: "1px dashed var(--border-color)",
              background: "var(--bg-card)",
              display: "flex",
              flexDirection: "column",
              gap: 8,
            }}
          >
            <input
              type="text"
              placeholder="Task Name (e.g. Memory Fabric Sync)"
              value={taskName}
              onChange={(e) => setTaskName(e.target.value)}
              style={{
                padding: "7px 10px",
                borderRadius: 6,
                border: "1px solid var(--border-color)",
                background: "var(--bg-input)",
                color: "var(--text-main)",
                fontSize: 12,
              }}
            />
            <input
              type="text"
              placeholder="Frequency (e.g. Every 2 hours, Daily at 02:00)"
              value={taskCron}
              onChange={(e) => setTaskCron(e.target.value)}
              style={{
                padding: "7px 10px",
                borderRadius: 6,
                border: "1px solid var(--border-color)",
                background: "var(--bg-input)",
                color: "var(--text-main)",
                fontSize: 12,
              }}
            />
            <input
              type="text"
              placeholder="Action / Target Function"
              value={taskAction}
              onChange={(e) => setTaskAction(e.target.value)}
              style={{
                padding: "7px 10px",
                borderRadius: 6,
                border: "1px solid var(--border-color)",
                background: "var(--bg-input)",
                color: "var(--text-main)",
                fontSize: 12,
              }}
            />
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 6 }}>
              <button
                onClick={() => setCreating(false)}
                style={{
                  padding: "4px 10px",
                  borderRadius: 6,
                  border: "1px solid var(--border-color)",
                  background: "transparent",
                  color: "var(--text-secondary)",
                  cursor: "pointer",
                  fontSize: 12,
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                style={{
                  padding: "4px 12px",
                  borderRadius: 6,
                  border: 0,
                  background: "#111827",
                  color: "#ffffff",
                  cursor: "pointer",
                  fontSize: 12,
                  fontWeight: 500,
                }}
              >
                Save Schedule
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setCreating(true)}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
              padding: 8,
              borderRadius: 8,
              border: "1px dashed var(--border-color)",
              background: "transparent",
              color: "var(--text-secondary)",
              cursor: "pointer",
              fontSize: 12,
            }}
          >
            <Plus size={14} />
            <span>Add New Scheduled Automation</span>
          </button>
        )}

        {/* Footer */}
        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            paddingTop: 8,
            borderTop: "1px solid var(--border-color)",
          }}
        >
          <button
            onClick={() => setScheduledOpen(false)}
            style={{
              padding: "5px 14px",
              borderRadius: 6,
              background: "var(--bg-pill)",
              color: "var(--text-main)",
              border: "1px solid var(--border-color)",
              cursor: "pointer",
              fontSize: 12,
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
