# Acuity — Frontend

Next.js 16.2 App Router frontend for the Acuity AI-driven PM tool.

> **Read the root [`../README.md`](../README.md) first** — it covers full setup, prerequisites, and the Make targets you'll use daily.

---

## Dev server

```bash
npm run dev      # http://localhost:3000
```

Requires the backend running at `http://localhost:8000` (see root README).

---

## Key commands

```bash
npm run dev          # dev server with hot reload
npm run build        # production build
npm run lint         # ESLint
npx tsc --noEmit     # TypeScript type check
```

---

## Project structure

```
frontend/
├── app/
│   ├── (app)/
│   │   └── projects/[id]/    One directory per phase:
│   │       ├── redaction/    Phase 1 — PII review
│   │       ├── chat/         Phase 2 — RAG chat + proposal
│   │       ├── modules/      Phase 3 — Extract work modules
│   │       ├── techstack/    Phase 4 — Tech stack suggestion
│   │       ├── team/         Phase 5 — Team suggestion
│   │       ├── estimation/   Phase 6 — Effort estimation
│   │       └── epics/        Phase 7 — Epic + task gen + GitHub sync
│   └── layout.tsx
├── components/
│   ├── phase-progress-stepper.tsx
│   ├── redaction-highlight.tsx
│   └── ...
└── lib/
    ├── api.ts              fetch wrapper, all API calls
    ├── api.types.ts        shared TypeScript types
    ├── project-phases.ts   phase ordering + route helpers
    └── utils.ts
```

---

## Tech stack

| | |
|--|--|
| Framework | Next.js 16.2, App Router |
| Styling | Tailwind CSS v4 (`@theme` tokens in `globals.css`) |
| Components | shadcn/ui |
| Charts | Recharts (metrics page only) |
| Toasts | sonner |
| Data fetching | TanStack Query (`@tanstack/react-query`) |
| Type checking | TypeScript strict |

---

## Conventions

- All API calls go through `lib/api.ts` — never `fetch` directly from a page
- Phase pages use `use(params)` for async route params (Next.js 15+)
- Tailwind v4 uses `@theme` — no `tailwind.config.js`; design tokens live in `globals.css`
- Design token reference: `../DESIGN_HANDOFF.md`
