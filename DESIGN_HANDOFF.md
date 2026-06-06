# Design Handoff

## Claude Design link
- [Share the Claude Design file or export link here.](https://claude.ai/design/p/01159eb0-0c4b-4129-9342-c1bfa04efae0?file=AI+PM+Tool.html&via=share)

## Overview
- Purpose of the UI design
- Target users and main use cases

## Screens and routes
- `/` — landing / dashboard overview
- `/projects/new` — upload new project / requirements
- `/projects/[id]/redaction` — redaction review
- `/projects/[id]/chat` — chat & refinement
- `/projects/[id]/techstack` — tech stack review
- `/projects/[id]/team` — team suggestion
- `/projects/[id]/estimation` — effort estimation
- `/projects/[id]/epics` — epic & task review
- `/projects/[id]/metrics` — metrics dashboard

## Key components
- Navigation / sidebar
- Project card / summary widgets
- Chat UI and message thread
- Metrics charts and status panels
- Epic/task list with sync controls

## Frontend implementation notes
- Use `Next.js App Router` and `Tailwind CSS`.
- Use `shadcn/ui` for reusable form controls, buttons, cards, and dialogs.
- Keep backend API integration separate from UI scaffolding until endpoints exist.

## Priority work for frontend
1. Scaffold the app and establish main routes.
2. Build the landing/dashboard shell.
3. Implement the project details and chat flow screens.
4. Add metrics and review screens.

## Assets and specs
- List exported images, icons, fonts, colors, spacing.
- Note any interactive behavior or animations.

## Questions / clarifications
- Where should the API route integration begin?
- Are there any responsive/mobile breakpoints to prioritize?
