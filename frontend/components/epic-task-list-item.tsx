"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { SyncStatusBadge, SyncStatus } from "./sync-status-badge";

export interface TaskItem {
  id: string;
  title: string;
  points: number;
  assignee?: string;
  syncStatus: SyncStatus;
}

export interface EpicItem {
  id: string;
  title: string;
  points: number;
  syncStatus: SyncStatus;
  selected: boolean;
  tasks: TaskItem[];
}

interface EpicTaskListItemProps {
  epic: EpicItem;
  onToggleSelect?: (id: string) => void;
  className?: string;
}

function PointsBadge({ points }: { points: number }) {
  return (
    <span className="text-[10px] font-medium text-text-muted bg-surface-subtle border border-border px-1.5 py-0.5 rounded tabular-nums">
      {points} pts
    </span>
  );
}

function TaskRow({ task }: { task: TaskItem }) {
  return (
    <div className="flex items-center gap-3 px-4 py-2 border-t border-border/60 bg-surface-subtle/40">
      <div className="w-4 h-4 shrink-0 flex items-center justify-center">
        <span className="w-1 h-1 rounded-full bg-border-strong" />
      </div>
      <span className="flex-1 text-xs text-foreground truncate">{task.title}</span>
      <div className="flex items-center gap-2 shrink-0">
        {task.assignee && (
          <span className="text-[10px] text-text-muted hidden sm:block">{task.assignee}</span>
        )}
        <PointsBadge points={task.points} />
        <SyncStatusBadge status={task.syncStatus} size="sm" />
      </div>
    </div>
  );
}

export function EpicTaskListItem({
  epic,
  onToggleSelect,
  className,
}: EpicTaskListItemProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className={cn(
        "border border-border rounded-md overflow-hidden transition-opacity",
        !epic.selected && "opacity-60",
        className
      )}
    >
      {/* Epic header row */}
      <div className="flex items-center gap-3 px-3.5 py-3 bg-card">
        {/* Select toggle */}
        {onToggleSelect && (
          <button
            onClick={() => onToggleSelect(epic.id)}
            title={epic.selected ? "Deselect (skip)" : "Select"}
            className={cn(
              "w-4 h-4 rounded border-2 shrink-0 flex items-center justify-center transition-colors",
              epic.selected
                ? "bg-primary border-primary"
                : "bg-background border-border hover:border-primary"
            )}
          >
            {epic.selected && (
              <svg className="w-2.5 h-2.5 text-primary-foreground" fill="none" viewBox="0 0 10 10" stroke="currentColor" strokeWidth={2.5}>
                <polyline points="1.5,5 4,7.5 8.5,2.5" />
              </svg>
            )}
          </button>
        )}

        {/* Title + meta */}
        <div className="flex-1 min-w-0">
          <span className="text-sm font-semibold text-foreground">{epic.title}</span>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <PointsBadge points={epic.points} />
          <SyncStatusBadge status={epic.syncStatus} />

          {/* Expand toggle */}
          <button
            onClick={() => setExpanded((v) => !v)}
            className="w-6 h-6 rounded flex items-center justify-center text-text-muted hover:bg-surface-subtle transition-colors"
          >
            <svg
              className={cn("w-4 h-4 transition-transform", expanded && "rotate-180")}
              fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}
            >
              <path d="M4 6l4 4 4-4" />
            </svg>
          </button>
        </div>
      </div>

      {/* Task rows */}
      {expanded && epic.tasks.length > 0 && (
        <div>
          {epic.tasks.map((task) => (
            <TaskRow key={task.id} task={task} />
          ))}
        </div>
      )}

      {expanded && epic.tasks.length === 0 && (
        <div className="px-4 py-3 border-t border-border/60 bg-surface-subtle/40">
          <span className="text-xs text-text-muted">No tasks defined yet.</span>
        </div>
      )}
    </div>
  );
}
