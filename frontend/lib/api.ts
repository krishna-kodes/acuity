import createClient from "openapi-fetch"
import type { paths } from "./api.types"

export const apiClient = createClient<paths>({
  baseUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
})

// ── Projects ────────────────────────────────────────────────────────────────

export const listProjects = () =>
  apiClient.GET("/api/v1/projects", {})

export const createProject = (name: string, domain?: string) =>
  apiClient.POST("/api/v1/projects", { body: { name, domain } })

export const uploadDocument = (projectId: string, file: File) => {
  const form = new FormData()
  form.append("file", file)
  return apiClient.POST("/api/v1/projects/{project_id}/documents", {
    params: { path: { project_id: projectId } },
    body: form as never, // openapi-fetch doesn't type FormData bodies; cast required for multipart
  })
}

export const getTBDs = (projectId: string) =>
  apiClient.GET("/api/v1/projects/{project_id}/tbds", {
    params: { path: { project_id: projectId } },
  })

export const getRedactionDecisions = (projectId: string) =>
  apiClient.GET("/api/v1/projects/{project_id}/redaction-decisions", {
    params: { path: { project_id: projectId } },
  })

export const patchRedactionDecisions = (
  projectId: string,
  decisions: Array<{ detection_id: number; confirmed: boolean }>,
) =>
  apiClient.PATCH("/api/v1/projects/{project_id}/redaction-decisions", {
    params: { path: { project_id: projectId } },
    body: { decisions },
  })

export const submitClarification = (
  projectId: string,
  tbd_id: string,
  action: string,
  answer?: string,
) =>
  apiClient.POST("/api/v1/projects/{project_id}/clarifications", {
    params: { path: { project_id: projectId } },
    body: { tbd_id, action, answer },
  })

export const generateProposal = (projectId: string) =>
  apiClient.POST("/api/v1/projects/{project_id}/proposal", {
    params: { path: { project_id: projectId } },
  })

export const getProposal = (projectId: string) =>
  apiClient.GET("/api/v1/projects/{project_id}/proposal", {
    params: { path: { project_id: projectId } },
  })

export const suggestStack = (projectId: string) =>
  apiClient.POST("/api/v1/projects/{project_id}/stack", {
    params: { path: { project_id: projectId } },
  })

export const estimateEffort = (projectId: string) =>
  apiClient.POST("/api/v1/projects/{project_id}/estimate", {
    params: { path: { project_id: projectId } },
  })

export const syncToProvider = (projectId: string) =>
  apiClient.POST("/api/v1/projects/{project_id}/sync", {
    params: { path: { project_id: projectId } },
  })

/** @deprecated Use syncToProvider */
export const syncToGitHub = syncToProvider

export const getMetrics = (projectId: string) =>
  apiClient.GET("/api/v1/projects/{project_id}/metrics", {
    params: { path: { project_id: projectId } },
  })

// ── Factory ──────────────────────────────────────────────────────────────────

export const seedEmployees = () =>
  apiClient.POST("/api/v1/factory/seed-employees", {})

export const seedProjects = () =>
  apiClient.POST("/api/v1/factory/seed-projects", {})

export const seedTechnologies = () =>
  apiClient.POST("/api/v1/factory/seed-technologies", {})

export const seedAll = () =>
  apiClient.POST("/api/v1/factory/seed-all", {})

export const resetDb = () =>
  apiClient.DELETE("/api/v1/factory/reset-db", {})

// ── Pending backend routes ────────────────────────────────────────────────────
// NOTE: /api/v1/projects/{project_id}/phases/{phase_number}/start is not yet
// implemented in the backend. Helper will be added after the backend route is live.
// NOTE: GET variants for /stack, /team, /estimate, and /epics are not yet
// implemented in the backend. The current backend exposes these as POST-only
// trigger endpoints (suggestStack, estimateEffort above).
// Helpers will be added once the backend GET routes are live and types are regenerated.

// ── DOCX export (binary — use URL directly) ───────────────────────────────────

export const getProposalExportUrl = (projectId: string): string =>
  `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/projects/${projectId}/export/proposal`

// ── New phase endpoints (not yet in api.types — use raw fetch) ────────────────

const _apiBase = () => process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export type ProjectDetail = {
  id: string
  name: string
  domain: string | null
  status: string
  current_phase: number
  created_at: string
  summary: string | null
}

export async function getProject(projectId: string): Promise<ProjectDetail> {
  const res = await fetch(`${_apiBase()}/api/v1/projects/${projectId}`)
  if (!res.ok) throw new Error(`Fetch project failed: ${res.status}`)
  return res.json()
}

export type LiveStatus = {
  agent: string | null
  model: string | null
  total_tokens: number
  session_cost_usd: number
  last_node: string | null
  last_latency_ms: number | null
  llm_call_count: number
  active_phase: string | null
  token_budget: number
  is_recent: boolean
}

export async function getLiveStatus(projectId: string): Promise<LiveStatus> {
  const res = await fetch(`${_apiBase()}/api/v1/projects/${projectId}/live-status`)
  if (!res.ok) throw new Error(`Live status failed: ${res.status}`)
  return res.json()
}

export async function triggerTeam(projectId: string): Promise<{ members: Array<{ id: number; name: string; seniority: string; availability_pct: number; skills: string[] }>; total: number }> {
  const res = await fetch(`${_apiBase()}/api/v1/projects/${projectId}/team`, { method: "POST" })
  if (!res.ok) throw new Error(`Team suggestion failed: ${res.status}`)
  return res.json()
}

export async function triggerEpics(projectId: string): Promise<{ epics: Array<{ title: string; description: string; due_date: string; tasks: Array<{ title: string; description: string; story_points: number; labels: string[] }> }>; count: number }> {
  const res = await fetch(`${_apiBase()}/api/v1/projects/${projectId}/epics`, { method: "POST" })
  if (!res.ok) throw new Error(`Epic generation failed: ${res.status}`)
  return res.json()
}

export async function getEpics(projectId: string): Promise<{ epics: Array<{ id: number; title: string; description: string; sync_status: string; github_milestone_number: number | null; github_milestone_url: string | null; tracker_ref: string | null; tracker_url: string | null; tracker_type: string | null; tasks: Array<{ id: number; title: string; description: string; story_points: number; labels: string[]; sync_status: string; github_issue_number: number | null; github_issue_url: string | null; tracker_ref: string | null; tracker_url: string | null; tracker_type: string | null }> }> }> {
  const res = await fetch(`${_apiBase()}/api/v1/projects/${projectId}/epics`)
  if (!res.ok) throw new Error(`Fetch epics failed: ${res.status}`)
  return res.json()
}

export type SyncProvider = "github" | "jira"

export type SyncConfig = {
  provider?: SyncProvider
  github_repo?: string
  jira_project_key?: string
}

export type SyncConfigResponse = {
  provider: SyncProvider
  config: SyncConfig
}

export async function getSyncConfig(projectId: string): Promise<SyncConfigResponse> {
  const res = await fetch(`${_apiBase()}/api/v1/projects/${projectId}/sync-config`)
  if (!res.ok) throw new Error(`Fetch sync config failed: ${res.status}`)
  return res.json()
}

export async function updateSyncConfig(projectId: string, config: SyncConfig): Promise<SyncConfigResponse> {
  const res = await fetch(`${_apiBase()}/api/v1/projects/${projectId}/sync-config`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  })
  if (!res.ok) throw new Error(`Update sync config failed: ${res.status}`)
  return res.json()
}

// ── Documents tab ─────────────────────────────────────────────────────────────

export const listProjectDocuments = (projectId: string) =>
  apiClient.GET("/api/v1/projects/{project_id}/documents-list" as never, {
    params: { path: { project_id: projectId } },
  } as never) as Promise<{ data?: Array<{
    id: string;
    doc_type: "uploaded" | "generated";
    filename: string;
    status: string;
    size_bytes: number | null;
    created_at: string;
    download_url: string;
  }>; error?: unknown }>

export const deleteDocument = (projectId: string, docId: string) =>
  fetch(
    `${_apiBase()}/api/v1/projects/${projectId}/documents/${docId}`,
    { method: "DELETE" }
  )

export const deleteProposal = (projectId: string, proposalId: string) =>
  fetch(
    `${_apiBase()}/api/v1/projects/${projectId}/proposals/${proposalId}`,
    { method: "DELETE" }
  )

// ── Project archive ───────────────────────────────────────────────────────────

export type ProjectListItem = {
  id: string
  name: string
  domain: string | null
  status: string
  current_phase: number
  created_at: string
  updated_at: string
}

export async function listAllProjects(): Promise<ProjectListItem[]> {
  const res = await fetch(`${_apiBase()}/api/v1/projects?include_archived=true`)
  if (!res.ok) throw new Error(`List projects failed: ${res.status}`)
  return res.json()
}

export async function archiveProject(projectId: string): Promise<void> {
  const res = await fetch(`${_apiBase()}/api/v1/projects/${projectId}/archive`, { method: "PATCH" })
  if (!res.ok) throw new Error(`Archive failed: ${res.status}`)
}

export async function unarchiveProject(projectId: string): Promise<void> {
  const res = await fetch(`${_apiBase()}/api/v1/projects/${projectId}/unarchive`, { method: "PATCH" })
  if (!res.ok) throw new Error(`Unarchive failed: ${res.status}`)
}

// ── Admin ──────────────────────────────────────────────────────────────────

export interface AdminSkill {
  id: number
  name: string
  category: string
}

export interface AdminEmployee {
  id: number
  name: string
  email: string | null
  seniority: string
  availability_pct: number
  joined_at: string | null
  status: string
  skills: AdminSkill[]
}

export async function listAdminEmployees(): Promise<AdminEmployee[]> {
  const res = await fetch(`${_apiBase()}/api/v1/admin/employees`)
  if (!res.ok) throw new Error(`Failed to fetch employees: ${res.status}`)
  return res.json()
}

export async function listAdminSkills(): Promise<AdminSkill[]> {
  const res = await fetch(`${_apiBase()}/api/v1/admin/skills`)
  if (!res.ok) throw new Error(`Failed to fetch skills: ${res.status}`)
  return res.json()
}

export async function updateTeam(
  projectId: string,
  members: Array<{
    id: number
    name: string
    seniority: string
    availability_pct: number
    skills: string[]
    manual?: boolean
  }>
): Promise<void> {
  const res = await fetch(`${_apiBase()}/api/v1/projects/${projectId}/team`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ members }),
  })
  if (!res.ok) throw new Error(`Failed to save team: ${res.status}`)
}

// ── Proposal preview/retry/approve ────────────────────────────────────────────

export type ProposalSection = { heading: string; body: string }

export type ProposalData = {
  id: string
  project_id: string
  content_path: string
  created_at: string
  sections: ProposalSection[]
}

export async function generateProposalRaw(projectId: string): Promise<ProposalData> {
  const res = await fetch(`${_apiBase()}/api/v1/projects/${projectId}/proposal`, { method: "POST" })
  if (!res.ok) throw new Error(`Generate failed: ${res.status}`)
  return res.json()
}

export async function retryProposal(projectId: string, comment: string): Promise<ProposalData> {
  const res = await fetch(`${_apiBase()}/api/v1/projects/${projectId}/proposal/retry`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ comment }),
  })
  if (!res.ok) throw new Error(`Retry failed: ${res.status}`)
  return res.json()
}

export async function approveProposal(projectId: string): Promise<ProposalData> {
  const res = await fetch(`${_apiBase()}/api/v1/projects/${projectId}/proposal/approve`, { method: "POST" })
  if (!res.ok) throw new Error(`Approve failed: ${res.status}`)
  return res.json()
}

// ── Redaction helpers ─────────────────────────────────────────────────────────

export async function piiLlmFilter(projectId: string): Promise<{ candidates_sent: number; kept: number; pruned: number }> {
  const res = await fetch(`${_apiBase()}/api/v1/projects/${projectId}/pii-llm-filter`, { method: "POST" })
  if (!res.ok) throw new Error(`LLM filter failed: ${res.status}`)
  return res.json()
}

export async function getDocumentStatus(projectId: string): Promise<{ status: string; project_phase: string }> {
  const res = await fetch(`${_apiBase()}/api/v1/projects/${projectId}/document-status`)
  if (!res.ok) throw new Error(`Status check failed: ${res.status}`)
  return res.json()
}

// ── Modules ───────────────────────────────────────────────────────────────────

export type Module = { id: string; title: string; label: string; description: string }
export type ModulesData = { modules: Module[] }

export async function extractModules(projectId: string): Promise<ModulesData> {
  const res = await fetch(`${_apiBase()}/api/v1/projects/${projectId}/modules`, { method: "POST" })
  if (!res.ok) throw new Error(`Extract modules failed: ${res.status}`)
  return res.json()
}

export async function getModules(projectId: string): Promise<ModulesData> {
  const res = await fetch(`${_apiBase()}/api/v1/projects/${projectId}/modules`)
  if (!res.ok) throw new Error(`Get modules failed: ${res.status}`)
  return res.json()
}

export async function saveModules(projectId: string, modules: Module[]): Promise<ModulesData> {
  const res = await fetch(`${_apiBase()}/api/v1/projects/${projectId}/modules`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ modules }),
  })
  if (!res.ok) throw new Error(`Save modules failed: ${res.status}`)
  return res.json()
}

export async function approveModules(projectId: string): Promise<ModulesData> {
  const res = await fetch(`${_apiBase()}/api/v1/projects/${projectId}/modules/approve`, { method: "POST" })
  if (!res.ok) throw new Error(`Approve modules failed: ${res.status}`)
  return res.json()
}
