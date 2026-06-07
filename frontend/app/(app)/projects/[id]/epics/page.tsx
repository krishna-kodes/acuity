"use client";

import { useState, useEffect, use } from "react";
import { PhaseProgressStepper } from "@/components/phase-progress-stepper";
import { EpicTaskListItem } from "@/components/epic-task-list-item";
import { SyncStatusBadge } from "@/components/sync-status-badge";
import { ErrorBanner, ReviewPageSkeleton } from "@/components/page-states";
import { getPhasesForRoute } from "@/lib/project-phases";
import type { EpicItem } from "@/components/epic-task-list-item";
import type { SyncStatus } from "@/components/sync-status-badge";
import { cn } from "@/lib/utils";
import {
  getEpics,
  triggerEpics,
  getSyncConfig,
  updateSyncConfig,
} from "@/lib/api";
import type { SyncProvider, SyncConfig, SyncConfigResponse } from "@/lib/api";

type ApiEpic = {
  id: number;
  title: string;
  description: string | null;
  sync_status: string;
  github_milestone_number: number | null;
  github_milestone_url: string | null;
  tracker_ref: string | null;
  tracker_url: string | null;
  tracker_type: string | null;
  tasks: Array<{
    id: number;
    title: string;
    description: string | null;
    story_points: number;
    labels: string[];
    sync_status: string;
    github_issue_number: number | null;
    github_issue_url: string | null;
    tracker_ref: string | null;
    tracker_url: string | null;
    tracker_type: string | null;
  }>;
};

function mapApiEpics(apiEpics: ApiEpic[]): EpicItem[] {
  return apiEpics.map((e) => ({
    id: String(e.id),
    title: e.title,
    points: e.tasks.reduce((sum, t) => sum + (t.story_points ?? 0), 0),
    syncStatus: (e.sync_status as SyncStatus) ?? "pending",
    selected: e.sync_status !== "skipped",
    tasks: e.tasks.map((t) => ({
      id: String(t.id),
      title: t.title,
      points: t.story_points ?? 3,
      syncStatus: (t.sync_status as SyncStatus) ?? "pending",
    })),
  }));
}

type SyncState = "idle" | "syncing" | "done" | "error";

function SyncSummary({ epics }: { epics: EpicItem[] }) {
  const counts: Record<SyncStatus, number> = { pending: 0, synced: 0, skipped: 0, failed: 0 };
  epics.forEach((e) => counts[e.syncStatus]++);
  return (
    <div className="flex items-center gap-3 flex-wrap">
      {(["synced", "pending", "skipped", "failed"] as SyncStatus[]).map((s) =>
        counts[s] > 0 ? (
          <span key={s} className="flex items-center gap-1.5 text-xs text-text-secondary">
            <SyncStatusBadge status={s} size="sm" />
            <span className="tabular-nums">{counts[s]}</span>
          </span>
        ) : null
      )}
    </div>
  );
}

function providerLabel(provider: SyncProvider): string {
  return provider === "jira" ? "Jira" : "GitHub";
}

// ── Configure Sync Dialog ────────────────────────────────────────────────────

type ConfigureDialogProps = {
  projectId: string;
  current: SyncConfigResponse;
  onSaved: (cfg: SyncConfigResponse) => void;
  onClose: () => void;
};

function ConfigureDialog({ projectId, current, onSaved, onClose }: ConfigureDialogProps) {
  const [provider, setProvider] = useState<SyncProvider>(current.provider);
  const [githubRepo, setGithubRepo] = useState(current.config.github_repo ?? "");
  const [jiraKey, setJiraKey] = useState(current.config.jira_project_key ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    setSaving(true);
    setError(null);
    const payload: SyncConfig = { provider };
    if (provider === "github" && githubRepo) payload.github_repo = githubRepo;
    if (provider === "jira" && jiraKey) payload.jira_project_key = jiraKey;
    try {
      const result = await updateSyncConfig(projectId, payload);
      onSaved(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save sync config");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-background border border-border rounded-lg shadow-xl w-full max-w-sm p-6 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-foreground">Configure Sync</h3>
          <button onClick={onClose} className="text-text-muted hover:text-foreground transition-colors text-lg leading-none">×</button>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-text-secondary">Provider</label>
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value as SyncProvider)}
            className="border border-border rounded-md px-3 py-2 text-sm bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="github">GitHub Issues + Milestones</option>
            <option value="jira">Jira</option>
          </select>
        </div>

        {provider === "github" && (
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-text-secondary">Repository name</label>
            <input
              type="text"
              placeholder="e.g. my-project-repo"
              value={githubRepo}
              onChange={(e) => setGithubRepo(e.target.value)}
              className="border border-border rounded-md px-3 py-2 text-sm bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            />
            <span className="text-xs text-text-muted">Leave blank to use global GITHUB_REPO</span>
          </div>
        )}

        {provider === "jira" && (
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-text-secondary">Project key</label>
            <input
              type="text"
              placeholder="e.g. PROJ"
              value={jiraKey}
              onChange={(e) => setJiraKey(e.target.value.toUpperCase())}
              className="border border-border rounded-md px-3 py-2 text-sm bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            />
            <span className="text-xs text-text-muted">Leave blank to use global JIRA_PROJECT_KEY</span>
          </div>
        )}

        {error && <p className="text-xs text-destructive">{error}</p>}

        <div className="flex items-center justify-end gap-2 pt-1">
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-sm text-text-secondary hover:text-foreground transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-1.5 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function EpicsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [epics, setEpics]               = useState<EpicItem[]>([]);
  const [syncState, setSyncState]       = useState<SyncState>("idle");
  const [syncError, setSyncError]       = useState<string | null>(null);
  const [loading, setLoading]           = useState(true);
  const [syncCfg, setSyncCfg]           = useState<SyncConfigResponse | null>(null);
  const [showConfig, setShowConfig]     = useState(false);

  useEffect(() => {
    Promise.all([
      getEpics(id),
      getSyncConfig(id),
    ]).then(([epicsData, cfgData]) => {
      setSyncCfg(cfgData);
      if (epicsData.epics.length > 0) {
        setEpics(mapApiEpics(epicsData.epics));
      } else {
        return triggerEpics(id).then((genData) => {
          setEpics(mapApiEpics(genData.epics.map((e, i) => ({
            id: i + 1,
            title: e.title,
            description: e.description,
            sync_status: "pending",
            github_milestone_number: null,
            github_milestone_url: null,
            tracker_ref: null,
            tracker_url: null,
            tracker_type: null,
            tasks: e.tasks.map((t, j) => ({
              id: (i + 1) * 100 + j,
              title: t.title,
              description: t.description,
              story_points: t.story_points,
              labels: t.labels,
              sync_status: "pending",
              github_issue_number: null,
              github_issue_url: null,
              tracker_ref: null,
              tracker_url: null,
              tracker_type: null,
            })),
          }))));
        });
      }
    })
    .catch(() => { /* stay with empty list */ })
    .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <ReviewPageSkeleton />;

  const selectedCount  = epics.filter((e) => e.selected).length;
  const selectedPoints = epics.filter((e) => e.selected).reduce((s, e) => s + e.points, 0);
  const provider       = syncCfg?.provider ?? "github";

  function toggleEpic(epicId: string) {
    setEpics((prev) =>
      prev.map((e) =>
        e.id === epicId
          ? {
              ...e,
              selected: !e.selected,
              syncStatus: !e.selected ? "pending" : "skipped",
              tasks: e.tasks.map((t) => ({
                ...t,
                syncStatus: (!e.selected ? "pending" : "skipped") as SyncStatus,
              })),
            }
          : e
      )
    );
  }

  async function handleSync() {
    setSyncState("syncing");
    setSyncError(null);

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const res = await fetch(`${apiBase}/api/v1/projects/${id}/sync`, { method: "POST" });
      if (!res.ok) throw new Error(`Sync failed: ${res.status}`);

      const data = await getEpics(id);
      setEpics(mapApiEpics(data.epics));
      setSyncState("done");
    } catch (err) {
      setSyncState("error");
      setSyncError(
        err instanceof Error
          ? err.message
          : `${providerLabel(provider)} sync failed. Check your credentials and try again.`
      );
    }
  }

  return (
    <>
      {showConfig && syncCfg && (
        <ConfigureDialog
          projectId={id}
          current={syncCfg}
          onSaved={(cfg) => { setSyncCfg(cfg); setShowConfig(false); }}
          onClose={() => setShowConfig(false)}
        />
      )}

      <div className="px-6 py-8 max-w-4xl mx-auto flex flex-col gap-6">
        <PhaseProgressStepper phases={getPhasesForRoute("epics")} />

        <div className="flex flex-col gap-4">
          {/* Header */}
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <h2 className="text-base font-semibold text-foreground">Epics &amp; Tasks</h2>
              <p className="text-xs text-text-muted mt-0.5">
                Review generated epics. Deselect any to skip. Then sync to{" "}
                <span className="font-medium text-text-secondary">{providerLabel(provider)}</span>.
              </p>
            </div>
            <div className="flex items-center gap-3 flex-wrap">
              <SyncSummary epics={epics} />
              <button
                onClick={() => setShowConfig(true)}
                className="text-xs text-text-secondary hover:text-foreground border border-border rounded px-2.5 py-1 transition-colors"
              >
                Configure sync
              </button>
            </div>
          </div>

          {/* Selection summary */}
          <div className="flex items-center gap-4 text-xs text-text-secondary px-1">
            <span><strong className="text-foreground tabular-nums">{selectedCount}</strong> of {epics.length} epics selected</span>
            <span><strong className="text-foreground tabular-nums">{selectedPoints}</strong> story points</span>
          </div>

          {/* Epic list */}
          <div className="flex flex-col gap-2">
            {epics.map((epic) => (
              <EpicTaskListItem key={epic.id} epic={epic} onToggleSelect={toggleEpic} />
            ))}
          </div>

          {/* Error */}
          {syncError && (
            <ErrorBanner message={syncError} onRetry={() => { setSyncError(null); setSyncState("idle"); }} />
          )}

          {/* Sync action */}
          <div className="flex items-center justify-between pt-2 border-t border-border flex-wrap gap-3">
            <div className="text-xs text-text-muted">
              {syncState === "done"
                ? `Sync complete — epics and tasks created in ${providerLabel(provider)}.`
                : `${selectedCount} epic${selectedCount !== 1 ? "s" : ""} will be synced to ${providerLabel(provider)}.`}
            </div>
            <button
              onClick={handleSync}
              disabled={syncState === "syncing" || syncState === "done" || selectedCount === 0}
              className={cn(
                "inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors",
                syncState === "done"
                  ? "bg-success-subtle text-success border border-success/20 cursor-default"
                  : syncState === "syncing" || selectedCount === 0
                  ? "bg-muted text-text-muted cursor-not-allowed"
                  : "bg-primary text-primary-foreground hover:bg-accent-hover"
              )}
            >
              {syncState === "syncing" && (
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2}>
                  <path d="M8 2a6 6 0 1 0 6 6" strokeLinecap="round" />
                </svg>
              )}
              {syncState === "done" && (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 16 16" stroke="currentColor" strokeWidth={2.5}>
                  <polyline points="2.5,8 6,11.5 13.5,4" />
                </svg>
              )}
              {syncState === "syncing"
                ? `Syncing to ${providerLabel(provider)}…`
                : syncState === "done"
                ? "Synced"
                : `Sync to ${providerLabel(provider)}`}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
