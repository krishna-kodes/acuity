import createClient from "openapi-fetch"
import type { paths } from "./api.types"

export const apiClient = createClient<paths>({
  baseUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
})

// ── Projects ────────────────────────────────────────────────────────────────

export const createProject = (name: string) =>
  apiClient.POST("/api/v1/projects", { body: { name } })

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

export const syncToGitHub = (projectId: string) =>
  apiClient.POST("/api/v1/projects/{project_id}/sync", {
    params: { path: { project_id: projectId } },
  })

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

// ── Project CRUD (Epic 5) ─────────────────────────────────────────────────────
// NOTE: GET /api/v1/projects and GET /api/v1/projects/{project_id} are not yet
// implemented in the backend (Epic 5 only exposes POST /api/v1/projects).
// These helpers will be added once the backend routes are live and regenerated.

// ── Redaction / PII review (Epic 5) ──────────────────────────────────────────
// NOTE: /api/v1/projects/{project_id}/redaction-decisions is not yet implemented
// in the backend. Helper will be added after the backend route is live.

// ── Phase triggers (Epic 5) ───────────────────────────────────────────────────
// NOTE: /api/v1/projects/{project_id}/phases/{phase_number}/start is not yet
// implemented in the backend. Helper will be added after the backend route is live.

// ── Phase result GETs (Epic 5) ────────────────────────────────────────────────
// NOTE: GET variants for /stack, /team, /estimate, and /epics are not yet
// implemented in the backend. The current backend exposes these as POST-only
// trigger endpoints (suggestStack, estimateEffort above).
// Helpers will be added once the backend GET routes are live and types are regenerated.

// ── DOCX export (binary — use URL directly) ───────────────────────────────────

export const getProposalExportUrl = (projectId: string): string =>
  `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/projects/${projectId}/export/proposal`
