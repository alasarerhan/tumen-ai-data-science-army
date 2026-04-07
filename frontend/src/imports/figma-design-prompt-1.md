# Figma Design Prompt — Autonomous Strategic Analytics Platform (M9)

> **Amaç:** Bu prompt, platformun tüm ekranlarını tek seferde tasarlayabilmek için Figma AI / tasarımcıya verilecek tam spesifikasyondur.
> **Kapsam:** Design system + component library + 13 tam ekran + tüm state'ler + dark/light mode + responsive + accessibility annotations.
> **Versiyon:** 1.0 — 2 Mart 2026

---

## PART 1 — PRODUCT CONTEXT

You are designing **Insight Platform** — an autonomous AI-powered strategic analytics platform for enterprise data scientists and business analysts. The platform:

- Orchestrates **multi-agent AI pipelines** (data cleaning → EDA → ML → strategic reporting) via LangGraph + Prefect
- Provides a **drag-and-drop Workflow Designer** for building agent pipelines
- Supports **human-in-the-loop approvals** for critical AI decisions
- Delivers **automated Strategic Reports** (Context → Synthesis → Narrative → Recommendations)
- Manages **cloud deployments** (Terraform / Docker / CI/CD) via CloudOps agents
- Serves enterprise tenants with full RBAC (Admin / Editor / Viewer)

**Tech stack context for designers:** React 18 + TypeScript + TailwindCSS + React Flow (canvas) + Monaco Editor (code). All dimensions should assume a clean, professional SaaS tool in the spirit of Vercel, Linear, or Retool.

---

## PART 2 — DESIGN SYSTEM

### 2.1 Color Tokens (both Light and Dark modes required)

#### Primitive palette

```
Slate:  50=#f8fafc  100=#f1f5f9  200=#e2e8f0  300=#cbd5e1  400=#94a3b8
        500=#64748b  600=#475569  700=#334155  800=#1e293b  900=#0f172a  950=#020617

Indigo: 50=#eef2ff  100=#e0e7ff  200=#c7d2fe  300=#a5b4fc  400=#818cf8
        500=#6366f1  600=#4f46e5  700=#4338ca  800=#3730a3  900=#312e81

Emerald: 500=#10b981  600=#059669
Red:     500=#ef4444  600=#dc2626
Amber:   400=#fbbf24  500=#f59e0b
Sky:     400=#38bdf8  500=#0ea5e9
Violet:  500=#8b5cf6  600=#7c3aed
```

#### Semantic tokens

| Token                    | Light                 | Dark           |
| ------------------------ | --------------------- | -------------- |
| `bg-canvas`            | Slate-50              | Slate-950      |
| `bg-surface`           | White                 | Slate-900      |
| `bg-surface-raised`    | White                 | Slate-800      |
| `bg-surface-sunken`    | Slate-100             | Slate-950      |
| `border-default`       | Slate-200             | Slate-700      |
| `border-strong`        | Slate-300             | Slate-600      |
| `text-primary`         | Slate-900             | Slate-50       |
| `text-secondary`       | Slate-600             | Slate-400      |
| `text-tertiary`        | Slate-400             | Slate-600      |
| `text-disabled`        | Slate-300             | Slate-700      |
| `accent-default`       | Indigo-600            | Indigo-400     |
| `accent-hover`         | Indigo-700            | Indigo-300     |
| `accent-subtle`        | Indigo-50             | Indigo-900/40  |
| `success`              | Emerald-600           | Emerald-500    |
| `success-subtle`       | Emerald-50            | Emerald-900/40 |
| `danger`               | Red-600               | Red-500        |
| `danger-subtle`        | Red-50                | Red-900/40     |
| `warning`              | Amber-500             | Amber-400      |
| `warning-subtle`       | Amber-50              | Amber-900/40   |
| `info`                 | Sky-500               | Sky-400        |
| `info-subtle`          | Sky-50                | Sky-900/40     |
| `run-status-running`   | Indigo-500            | Indigo-400     |
| `run-status-success`   | Emerald-500           | Emerald-400    |
| `run-status-failed`    | Red-500               | Red-400        |
| `run-status-pending`   | Amber-500             | Amber-400      |
| `run-status-cancelled` | Slate-400             | Slate-500      |
| `agent-node-iac`       | #f97316 (Orange-500)  | same           |
| `agent-node-container` | #06b6d4 (Cyan-500)    | same           |
| `agent-node-cicd`      | #8b5cf6 (Violet-500)  | same           |
| `agent-node-eda`       | #10b981 (Emerald-500) | same           |
| `agent-node-ml`        | #6366f1 (Indigo-500)  | same           |
| `agent-node-hitl`      | #f59e0b (Amber-500)   | same           |
| `agent-node-strategic` | #ec4899 (Pink-500)    | same           |

### 2.2 Typography

**Font family:** `Inter` (Google Fonts) — weights 400, 500, 600, 700.
**Code/monospace:** `JetBrains Mono` — weights 400, 500.

| Scale           | Size | Line Height | Weight  | Usage                        |
| --------------- | ---- | ----------- | ------- | ---------------------------- |
| `display-2xl` | 72px | 90px        | 700     | Hero (unused in app)         |
| `display-xl`  | 60px | 72px        | 700     | —                           |
| `display-lg`  | 48px | 60px        | 700     | —                           |
| `display-md`  | 36px | 44px        | 700     | Page title (reports)         |
| `display-sm`  | 30px | 38px        | 600     | Section heading              |
| `text-xl`     | 20px | 30px        | 600     | Card title, panel heading    |
| `text-lg`     | 18px | 28px        | 500/600 | Sub-heading                  |
| `text-md`     | 16px | 24px        | 400/500 | Body default                 |
| `text-sm`     | 14px | 20px        | 400/500 | Secondary body, labels       |
| `text-xs`     | 12px | 18px        | 400/500 | Captions, badges, timestamps |
| `code-sm`     | 13px | 20px        | 400     | Code snippets                |
| `code-xs`     | 11px | 16px        | 400     | Inline code in text          |

**Rules:**

- Use `font-variant-numeric: tabular-nums` on all numbers (run durations, metrics, counts).
- Use `text-wrap: balance` on headings (max 3 lines).
- Ellipsis character `…` (not `...`) for truncation.
- En for ranges: `10–20 ms`, not `10-20 ms`.
- Non-breaking spaces in: `10 MB`, `⌘ K`, brand names.

### 2.3 Spacing Scale

Base: 4px.
`space-0.5`=2px, `space-1`=4px, `space-2`=8px, `space-3`=12px, `space-4`=16px, `space-5`=20px, `space-6`=24px, `space-8`=32px, `space-10`=40px, `space-12`=48px, `space-16`=64px, `space-20`=80px, `space-24`=96px.

### 2.4 Border Radius

| Token           | Value  | Usage                 |
| --------------- | ------ | --------------------- |
| `radius-xs`   | 4px    | Badges, tags          |
| `radius-sm`   | 6px    | Inputs, small buttons |
| `radius-md`   | 8px    | Cards, dropdowns      |
| `radius-lg`   | 12px   | Modals, large cards   |
| `radius-xl`   | 16px   | Sheets, drawers       |
| `radius-2xl`  | 24px   | Feature cards         |
| `radius-full` | 9999px | Pills, avatars        |

### 2.5 Shadows / Elevation

| Token                   | Light value                                                  | Usage                      |
| ----------------------- | ------------------------------------------------------------ | -------------------------- |
| `shadow-xs`           | `0 1px 2px rgba(0,0,0,0.05)`                               | Subtle cards               |
| `shadow-sm`           | `0 1px 3px rgba(0,0,0,0.1), 0 1px 2px rgba(0,0,0,0.06)`    | Cards default              |
| `shadow-md`           | `0 4px 6px rgba(0,0,0,0.07), 0 2px 4px rgba(0,0,0,0.06)`   | Dropdowns                  |
| `shadow-lg`           | `0 10px 15px rgba(0,0,0,0.1), 0 4px 6px rgba(0,0,0,0.05)`  | Modals                     |
| `shadow-xl`           | `0 20px 25px rgba(0,0,0,0.1), 0 8px 10px rgba(0,0,0,0.04)` | Drawers                    |
| `shadow-focus`        | `0 0 0 3px rgba(99,102,241,0.5)`                           | Focus ring (Indigo-500/50) |
| `shadow-focus-danger` | `0 0 0 3px rgba(239,68,68,0.5)`                            | Focus ring on error        |

### 2.6 Icon Set

Use **Lucide Icons** exclusively (stroke width 1.5px, size 16px default, 20px for nav, 24px for empty states). All icon-only buttons/controls MUST include an `aria-label` annotation.

---

## PART 3 — COMPONENT LIBRARY

Design all components in both **Light** and **Dark** variants, and all interactive states: `default`, `hover`, `focus-visible` (ring), `active`, `disabled`.

### 3.1 Atoms

#### Button

Variants: `primary`, `secondary`, `ghost`, `destructive`, `link`.Sizes: `xs` (28px h), `sm` (32px h), `md` (36px h), `lg` (40px h), `xl` (44px h).States: default, hover, focus-visible (3px ring), active (scale 0.98), disabled (opacity-40, cursor-not-allowed), loading (spinner replaces icon, text unchanged, button disabled).

- Leading/trailing icon slots (16px icon).
- Full-width variant.
- `destructive` = Red background; hover darkens.
- Primary button: Indigo-600 bg, white text.
- Secondary: border Slate-300 bg-white.
- Ghost: transparent bg, `text-secondary`.

#### Icon Button

Variants: `ghost`, `soft`, `outline`.
Sizes: 28px, 32px, 36px, 40px (square).
ALWAYS annotate: `aria-label="[action description]"`.

#### Badge / Status Pill

Variants: `neutral`, `indigо`, `success`, `warning`, `danger`, `info`, `violet`.
Sizes: `sm` (20px h), `md` (24px h).
With/without dot indicator, with/without leading icon, with/without remove ×.

**Run Status Badge** (special): animated pulse dot for `running` state. Colors: use `run-status-*` tokens.

#### Avatar

Sizes: 24px, 32px, 40px, 48px, 64px.
Fallback: initials (1–2 chars) on colored bg (deterministic color from user ID hash).
Group avatar (overlap): -8px margin-left.

#### Checkbox

States: unchecked, checked (Indigo fill + white checkmark), indeterminate (dash), disabled-unchecked, disabled-checked.
Always paired with `<label>`. Hit area min 44×44px.

#### Radio Button

Same states. Always grouped with fieldset + legend.

#### Toggle / Switch

On: Indigo-600 bg, white thumb. Off: Slate-300 bg. Sizes: sm (16px h), md (20px h), lg (24px h).
`aria-checked` annotation required.

#### Text Input

Sizes: sm, md, lg.
States: empty, filled, focused (Indigo ring), error (red border + error message below), disabled, readonly.
Always has `<label>` above. Optional helper text below. Optional leading/trailing icon or adornment.
`autocomplete` attribute annotation included in spec.

#### Textarea

Same as Input but resizable vertically. Character counter optional (top-right).

#### Select (Dropdown)

Custom styled. Trigger shows current value + chevron. Dropdown panel `shadow-md`, `radius-md`, scroll at 8 items.

#### Combobox (Searchable Select)

With search input inside dropdown. Multi-select variant with checkbox items.

#### Tag Input

Chips inside input field. Each chip has text + × remove.

#### Slider

Track + thumb. With min/max labels. Optionally with value tooltip on drag.

#### Progress Bar

Sizes: xs (4px), sm (8px), md (12px).
Variants: `determinate` (%) + `indeterminate` (animated shimmer).
Colors: Indigo (default), Emerald (success), Red (error).

#### Spinner / Loader

Sizes: 16px, 20px, 24px, 32px, 48px.
Color: `accent-default`. Animated rotate. Must respect `prefers-reduced-motion` (static version).

#### Skeleton

Block skeleton (rect with shimmer). Circle skeleton. Text line skeleton (varied widths).
Shimmer animation direction: left-to-right gradient.

#### Tooltip

Max width: 280px. Appears after 200ms. Positions: top, right, bottom, left, top-start, top-end.
Dark bg (`Slate-900`/90) + white text even in light mode (inverted).

#### Popover / Dropdown Menu

Width: 200–280px. Shadow-md. Radius-md. Items 36px min-height. Hover bg: Slate-100. Separator line. Section labels (text-xs uppercase text-tertiary). Destructive item in red.

#### Context Menu

Same as popover but triggered by right-click. Keyboard nav with ArrowUp/Down, Enter, Escape.

#### Divider

Horizontal: 1px Slate-200. Optional text center label.

#### Kbd (Keyboard Shortcut)

`⌘ K`, `⌘ S`, `⌃ Z`. Styled as small capsule with border.

### 3.2 Molecules

#### Form Field (Compound)

Label + Input + Helper text + Error message. Vertical stack, 8px gap.
Error state: red border + red error text with ⚠ icon + `aria-describedby` annotation.

#### Search Bar

Leading 🔍 icon (Slate-400). Input. Optional ×-clear button (appears when non-empty).
`Cmd+K` shortcut label on right when empty.

#### Empty State

Icon (48px, Slate-300) + Title (text-md, bold) + Description (text-sm, text-secondary) + optional CTA button.
Centered in container. Min height 240px.

#### Notification Toast

Variants: `info`, `success`, `warning`, `error`.
Left colored border (4px). Icon + title + optional description.
Close × top-right. Auto-dismiss (configurable). Stack from bottom-right.
`aria-live="polite"` annotation.

#### Inline Alert / Banner

Variants: `info`, `success`, `warning`, `error`.
Colored bg-subtle + matching icon. Title + optional description + optional action button.

#### Stat Card

Label (text-xs, text-secondary) + Value (text-2xl, tabular-nums, text-primary) + optional delta (% change, colored).
Shadow-sm, radius-md, padding-6.

#### Data Table

Column headers (text-xs uppercase text-secondary, sort arrow icon).
Row hover: bg-surface-sunken. Row selected: Indigo-50 bg (dark: Indigo-900/20).
Checkbox column (bulk select).
Virtualization annotation: >50 rows must use virtual scrolling.
Pagination footer: page size selector + prev/next + current range `1–25 of 142`.
Empty state built in.

#### Code Block

JetBrains Mono. Dark bg (Slate-900 even in light mode). Syntax highlighting tokens defined. Copy-to-clipboard button (top-right). Language badge top-left. Line numbers (optional). Horizontal scroll on overflow.

#### Accordion / Collapsible

Header (click toggles) + animated content reveal. Chevron rotates 180°. Respect `prefers-reduced-motion`.

#### Tabs

Variants: `line` (underline indicator), `pill` (rounded active bg), `boxed`.
Keyboard nav: ArrowLeft/Right switches tabs. `role="tablist"`, `role="tab"`, `role="tabpanel"` annotated.

#### Breadcrumb

`/`-separated. Last item: `text-primary`, not a link. Others: `text-secondary` links. Overflow: collapse to `…` at narrow widths with popover showing full path.

#### Pagination

First, Prev, numbered (max 7 visible with `…`), Next, Last. Current page: Indigo-600 bg white text.

#### Stepper / Progress Steps

Horizontal stepper: completed (checkmark circle), current (Indigo filled circle + pulsing ring), upcoming (Slate circle).
Vertical stepper variant for pipeline stages.

#### Date Picker (single + range)

Calendar grid. Today highlight. Selected: Indigo bg. Hover: Indigo-50. Clear button. Formatted using `Intl.DateTimeFormat`.

#### Modal / Dialog

Overlay (bg-black/50, backdrop-blur-sm). Max widths: sm=448px, md=560px, lg=672px, xl=800px, full=95vw.
Header (title + × close), body (scrollable), footer (action buttons right-aligned).
`overscroll-behavior: contain`. `role="dialog"`, `aria-modal="true"`, focus trap annotation.
Confirm/destructive variant: red footer CTA.

#### Drawer / Sheet

Right-side slide-in. Widths: sm=360px, md=480px, lg=640px, full=100vw.
Same overlay as modal. `overscroll-behavior: contain`.

#### Command Palette (⌘K)

Full-screen overlay with centered input box. Instant fuzzy search results. Sections: "Recent", "Pages", "Actions". Keyboard nav. `role="combobox"`.

#### Resizable Panels (Split View)

Draggable divider (4px grab area, 1px visual). Min/max constraints. Cursor: `col-resize` / `row-resize`.

### 3.3 Organisms

#### App Shell

- **Top Navigation Bar** (56px height): Logo left + Workspace switcher (dropdown) + main nav items center + Search (⌘K) + Notifications bell + User avatar dropdown right.
- **Left Sidebar** (240px width, collapsible to 56px): Nav sections with icons + labels. Collapse to icon-only with tooltips. `aria-current="page"` annotation.
- **Main Content Area**: fluid, 16px padding, max-width 1280px centered on wide screens.

#### Workspace Switcher

Dropdown with workspace list. Active workspace: checkmark. "Create Workspace" option bottom. Avatar + name + role badge per item.

#### Left Sidebar Navigation Sections:

1. **Home** — Dashboard icon
2. **Runs** — Play circle icon
3. **Workflows** — Git branch icon
4. **Data Sources** — Database icon
5. **Agents** — Bot icon
6. **Reports** — Bar chart icon
7. **Deployments** — Cloud icon
8. **Settings** — Gear icon (bottom)

#### Agent Pipeline Node (Workflow Designer)

Rectangle card (200×80px). Left colored border (agent-type color). Icon (24px) + Agent name (text-sm bold) + Status badge. 3 input ports (left) + 3 output ports (right). Selected: Indigo ring 2px. Error: red border. Running: animated left border shimmer.

---

## PART 4 — SCREENS (13 total)

Design all screens at **1440×900** (desktop primary). Also provide **375×812** (mobile) and **768×1024** (tablet) artboards for screens S0, S1, S2, S3, S11.

---

### S0 — Login / Authentication

**URL:** `/login`

**Layout:** Full-screen split (50/50 on desktop).

**Left panel (marketing):**

- Dark bg: `bg-canvas` dark mode regardless of OS theme.
- Logo top-left: "Insight Platform" wordmark + icon.
- Hero headline (display-md, white): "AI-Powered Analytics. Delivered at Scale."
- Sub-text (text-md, Slate-400): "Orchestrate multi-agent pipelines, synthesize strategic insights, and deploy at enterprise speed."
- 3 feature pills (icon + text): "Autonomous Agents", "Strategic Reports", "Human-in-the-Loop".
- Bottom: small print version number + copyright.

**Right panel (auth form):**

- White bg (light), Slate-950 (dark).
- "Sign In" heading (text-xl, bold).
- Sub: "Use your corporate Google Workspace account."
- **Google Sign In button** (full-width, lg size): Google G icon + "Continue with Google" (Title Case). White bg, Slate-300 border, hover shadow-sm.
- Divider with "or" label.
- **Dev Bearer token form** (collapsible, default closed):
  - Label: "Developer Token (local only)"
  - Token input: `type="password"`, `autocomplete="current-password"`, placeholder "Bearer eyJ…", `spellCheck={false}`.
  - "Sign In" submit button (primary, full-width).
  - Warning banner (amber): "Dev mode only — not for production."
- Footer links: "Privacy Policy · Terms of Service".
- Error alert (red inline banner) when auth fails: "Sign-in failed — check your credentials and try again."

**States to design:** default, loading (spinner on button), error.

**Accessibility:** `<form>` with `aria-label="Sign in"`. Inputs have `<label>`. Button `type="submit"`.

---

### S1 — Workspace Dashboard

**URL:** `/workspaces/{workspace_id}`

**Layout:** App Shell (sidebar + top-nav) + main content.

**Top section — Welcome bar:**

- "Good morning, {First Name}" (text-xl, 600) — time-aware greeting.
- Workspace name badge (top-right of greeting).

**Metrics row (4 stat cards):**

1. **Active Runs** — count (tabular-nums) + "↑ 3 since yesterday" delta.
2. **Workflows** — published count.
3. **Agents** — healthy count / total count.
4. **Reports Generated** — last 30 days count.

**Main grid (2 columns, 60/40 split):**

*Left — Recent Runs (table, 5 rows max):*

- Columns: Status (badge), Run Name, Workflow, Started (relative: "2 hours ago"), Duration (tabular-nums "3m 24s"), Triggered By.
- "View All Runs →" link bottom-right.
- Row hover: subtle bg, cursor pointer → navigates to run detail.

*Right — Quick Actions (card):*

- Title: "Quick Actions"
- 4 action buttons (secondary, full-width):
  1. "New Workflow" (+ icon)
  2. "Trigger Run" (play icon)
  3. "Browse Data Sources" (database icon)
  4. "View Reports" (bar-chart icon)

**Bottom section — Activity Feed:**

- Timeline list (vertical stepper style).
- Each item: avatar + user name + action text + timestamp (Intl.DateTimeFormat, relative).
- Max 10 items. "Load More…" button bottom.

**Empty state variant:** When no runs exist — empty state illustration + "Create Your First Workflow" CTA.

---

### S2 — Runs List

**URL:** `/workspaces/{workspace_id}/runs`

**Layout:** App Shell + full-width data table.

**Page header:**

- "Pipeline Runs" (display-sm, 700).
- Sub: "All workflow executions across your workspace." (text-sm, text-secondary).
- Right: "Trigger Run" primary button.

**Filter bar (horizontal, sticky on scroll):**

- Search input (placeholder "Search runs…").
- Status filter: multi-select combobox (All / Running / Success / Failed / Pending / Cancelled).
- Workflow filter: searchable combobox.
- Date range picker.
- "Clear Filters" ghost button (visible only when filters active).
- Result count: "Showing 25 of 142 runs" (text-xs, text-secondary, right side).

**Data Table columns:**

| Column       | Width | Notes                                                         |
| ------------ | ----- | ------------------------------------------------------------- |
| Status       | 100px | Animated badge with pulsing dot if running                    |
| Run ID       | 120px | Monospace, truncated, copy icon on hover                      |
| Workflow     | 200px | Name + version badge                                          |
| Triggered By | 140px | Avatar + name                                                 |
| Started      | 160px | `Intl.DateTimeFormat` full date + relative on hover tooltip |
| Duration     | 100px | `tabular-nums`, "3m 24s" or "—" if running                 |
| Artifacts    | 80px  | Count badge, clickable                                        |
| Actions      | 80px  | `…` menu (View Detail, Re-run, Cancel, Delete)             |

**Row states:** default, hover (bg-surface-sunken), running (left border animated Indigo), selected (Indigo-50 bg, checkbox checked).

**Bulk action bar:** Appears when ≥1 selected. Shows "3 selected" + "Retry" + "Cancel" + "Delete" destructive buttons.

**Empty state:** (no runs) illustration + "No runs found." + "Adjust your filters or trigger a new run."

**Pagination:** bottom-right, page-size selector (10/25/50), prev/next + page numbers.

---

### S3 — Run Detail

**URL:** `/workspaces/{workspace_id}/runs/{run_id}`

**Layout:** App Shell + vertical split (main left, side panel right 360px).

**Header:**

- Back breadcrumb: "Runs / {Run ID truncated}".
- Run name (text-xl, bold) + Status badge + Duration (tabular-nums).
- Action buttons: "Re-run" (secondary), "Cancel" (destructive, only if running), "Download Artifacts" (ghost with download icon).

**Main area — Tab navigation:**

**Tab 1 — Overview:**

- Run metadata grid (2-col):
  - Run ID (monospace + copy button)
  - Workflow (name + version link)
  - Triggered By (avatar + name)
  - Started / Ended (full ISO format via Intl.DateTimeFormat)
  - Duration (mm:ss, tabular-nums)
  - Prefect Flow Run ID (monospace + external link)
- Agent Pipeline Step Stepper (vertical, shows each agent stage):
  - Each stage: agent name + status badge + duration + expand chevron.
  - Expanded: shows tool calls list + output summary.

**Tab 2 — Logs:**

- Live log stream (code block style, dark bg).
- Auto-scroll to bottom toggle (sticky bottom-right button: "Follow Logs").
- Log level filter: ALL / INFO / WARN / ERROR.
- "Copy All" button top-right.

**Tab 3 — Artifacts:**

- Grid of artifact cards (3-col): thumbnail (for images/charts), name, type badge (CSV/JSON/PNG/HTML), size (tabular-nums), download button.
- Empty state if no artifacts.

**Tab 4 — Strategy Report** (visible only when run has strategic output):

- Renders the full strategic report (see S7 layout as embedded view).

**Right side panel — Related Runs:**

- Same workflow, 5 most recent runs.
- Mini timeline with status indicator.
- "View All →" link.

**HITL Panel (conditional — only when run is paused awaiting approval):**

- Top of main area: amber banner "⏸ Awaiting Human Approval".
- "Review & Decide" button → opens HITL Approval Modal (see S9 as modal).

---

### S4 — Workflow Designer

**URL:** `/workspaces/{workspace_id}/workflows/{workflow_id}/designer`

**Layout:** Full-bleed canvas (no sidebar). Custom top toolbar.

**Top Toolbar (56px, bg-surface, shadow-sm):**

- Left: Back arrow + Workflow name (editable inline text, click to rename) + version badge ("v3 · Draft").
- Center: Undo (`⌘Z`), Redo (`⌘⇧Z`), separator, Fit to screen, Zoom %, separator, "Validate" (checks HCL/YAML syntax).
- Right: "Save Draft" (ghost), "Publish" (primary, disabled if validation errors), user avatar.

**Left Panel — Node Palette (280px, collapsible):**

- Search nodes input.
- Sections (collapsible accordions):
  - **Data** — DataLoader, DataCleaner, DataWrangler, EDA
  - **ML** — FeatureEngineering, H2O AutoML, ModelEvaluator, MLflowLogger
  - **Strategic** — ContextualKnowledge, ResultsSynthesizer, Narrative, Recommendation
  - **CloudOps** — IaC (Terraform), Containerization, CICD
  - **Control** — Human-in-the-Loop Gate, Conditional Branch, Merge, Start, End
- Each node: draggable card (48px h) with color-coded left border + icon + name.

**Canvas (React Flow style):**

- Grid background (dot grid, Slate-200 dots, 24px spacing).
- Pan with Space+drag or middle-click. Zoom scroll.
- Mini-map (bottom-right, 160×100px, bg-surface with border).
- Zoom controls (bottom-right above mini-map): +, −, fit, reset.
- Selection box (Indigo-500 dashed border, 1px, Indigo-100/20 fill).
- Connection lines: bezier curves, Slate-400 stroke (1.5px), animated when running (Indigo dashed flow animation).
- Selected connection: Indigo-500, 2px.

**Agent Node (detailed spec):**

- Size: 200×80px, radius-md.
- Header: colored top border (4px, agent-type color) + icon (20px) + agent name (text-sm, 600).
- Body: status badge + "0 tool calls" counter.
- Input port (left, center) — circle 10px, white fill, type-color border.
- Output port (right, center) — same.
- Hover: shadow-md, scale(1.01).
- Selected: 2px Indigo-500 ring.
- Running: left border animated gradient shimmer (Indigo → Violet → Indigo, 1.5s loop). Respect `prefers-reduced-motion`: static border for reduced-motion users.
- Error: red border, error icon top-right corner, tooltip on hover with error message.

**HITL Gate Node (special):**

- Hexagon shape (or diamond). Amber color scheme. "Approval Required" label. Lock icon.

**Right Panel — Node Config (360px, slides in when node selected):**

- Node title + type badge.
- Parameters form (dynamic per agent type):
  - **Common for all:** "Display Name" text input, "Description" textarea, "Human-in-the-Loop" toggle.
  - **Data agents:** data source selector, column selectors.
  - **ML agents:** target variable input, metric selector.
  - **HITL Gate:** approver role selector, timeout input (hours), notification message textarea.
- "Delete Node" destructive button (bottom).
- Panel close × top-right.

**Bottom Status Bar:**

- Node count + Connection count. "Auto-saved 2m ago". Validation status (green ✓ or red ✕ with error count).

**Keyboard shortcuts:**

- `Del`/`Backspace` — delete selected.
- `⌘A` — select all.
- `⌘C`/`⌘V` — copy/paste nodes.
- `⌘Z`/`⌘⇧Z` — undo/redo.
- `Space` + drag — pan.

---

### S5 — Workflow Spec Editor

**URL:** `/workspaces/{workspace_id}/workflows/{workflow_id}`

**Layout:** App Shell + split view (60/40): Monaco editor left, version history right.

**Page header:**

- "Workflows / {Workflow Name}" breadcrumb.
- Workflow name (text-xl, editable inline) + status badge (Draft / Published / Deprecated).
- Right: "Open in Designer" (secondary), "Publish" (primary), `…` menu (Duplicate, Deprecate, Delete).

**Editor panel (left, Monaco-style):**

- Toolbar: language badge "YAML", format button (⌥⇧F), collapse-all, expand-all.
- Monaco editor embedded with syntax highlighting (custom theme matching dark/light mode).
- Gutter: line numbers + diff indicators (added/modified lines).
- Bottom: cursor position "Ln 24, Col 8" + "UTF-8" + "YAML" — tabular-nums.

**Version History panel (right, 40%):**

- Header: "Version History" (text-md, 600) + "Compare" toggle.
- List: each version = card (48px min-height):
  - Version badge ("v4") + status pill + author avatar + date (Intl.DateTimeFormat relative).
  - "Published" versions have green dot.
  - Active/viewing version: Indigo-50 bg.
  - Hover actions: "View", "Restore", "Publish" (if draft).
- Version detail drawer (opens right): shows full spec diff, additions green, deletions red.
- "Create New Version" button (top of list).

**Publish confirmation modal:** "Publish workflow v4?" + warning "This will make v4 the active version." + "Publish" (primary) + "Cancel".

---

### S6 — Artifacts Browser

**URL:** `/workspaces/{workspace_id}/runs/{run_id}/artifacts`
Also accessible as standalone: `/workspaces/{workspace_id}/artifacts`

**Layout:** App Shell + page with filter sidebar (240px) + main grid.

**Filter sidebar:**

- "Filter" heading.
- Artifact type: checkboxes (CSV, JSON, PNG, HTML, Parquet, Model, Other).
- Date range.
- Run filter (searchable combobox).
- Agent filter.

**Main area header:**

- "Artifacts" (display-sm) + count ("142 artifacts").
- Right: view toggle (grid / list icon buttons), sort dropdown ("Newest First").

**Grid view (3-col):**
Each artifact card (aspect-ratio 4:3 + info below):

- Preview area:
  - PNG/chart → actual image preview (lazy loaded, `loading="lazy"` annotation).
  - CSV/Parquet → table icon + row count.
  - HTML → browser icon.
  - Model → model icon.
- Below: artifact name (text-sm, truncate, 1 line), type badge + size (tabular-nums), date.
- Hover: overlay with "Download" and "Preview" icon buttons.

**List view (table):**

- Columns: Name, Type, Size, Run, Agent, Created, Actions (Download).

**Artifact Preview drawer (right, 480px):**

- Opens on click. Shows full preview.
- PNG: full-size image with zoom in/out.
- CSV: data-table (first 100 rows).
- HTML: sandboxed iframe.
- Download button + "Open in New Tab" link.
- Close × top-right.

---

### S7 — Strategic Report Panel

**URL:** `/workspaces/{workspace_id}/reports/{report_id}`

**Layout:** App Shell + single-column report body (max-width 840px, centered) + floating table-of-contents right (240px, sticky, desktop only).

**Report Header (full-width bg, Indigo gradient subtle):**

- Report title (display-md, bold) — from `NarrativeAgent` output.
- Meta row: generated date (Intl.DateTimeFormat) + run ID chip + "AI-Generated" badge.
- Action bar: "Download PDF", "Copy Link", "Share" buttons.
- Tags: context profile tags (from `ContextualKnowledgeAgent`).

**Report body sections (4-stage pipeline output):**

**Stage 1 — Context Profile** (card, left border `agent-node-strategic` color):

- "Business Context" heading.
- Business entities list (chips).
- Clarifying questions answered (accordion, collapsed by default).
- Context confidence score (progress bar, 0–100%).

**Stage 2 — Synthesized Findings** (card):

- "Key Findings" heading.
- Ranked findings list (numbered, with rank badge "🥇 #1").
- Merged metrics table (data-table, max 10 rows, tabular-nums).
- "Compare Results" toggle (shows before/after comparison for each metric).

**Stage 3 — Executive Narrative** (card, editorial typography):

- "Executive Summary" heading (display-sm).
- Long-form text content (text-md, 1.75 line-height, `text-pretty` on paragraphs).
- Section headers (text-lg, 600).
- Pull quote callout (left border Indigo, italic, larger text).
- Charts/visualizations embedded inline (if generated).

**Stage 4 — Recommendations** (card):

- "Strategic Recommendations" heading.
- ICE-scored recommendation cards (grid 2-col):
  - Rec number + title (text-md, 600).
  - Impact / Confidence / Ease badges (numeric, tabular-nums, color-coded).
  - ICE Total score (large, Indigo, tabular-nums).
  - Description (text-sm, 4 lines max, expand toggle).
- A/B Test Design section (collapsible):
  - Hypothesis, control variant, test variant, success metric, sample size, duration.
  - Each as labeled row.

**Floating Table of Contents (desktop, sticky right):**

- Jump links to: Context, Findings, Summary, Recommendations.
- Active section highlighted (Indigo-600, left indicator bar).
- Smooth scroll + `scroll-margin-top` annotations.

**Export / Share Modal:**

- "Download as PDF" (full report).
- "Copy Report URL" (deep link, copies to clipboard + success toast).
- "Share with Team" (email input + role selector + "Send Invite" button).

---

### S8 — CloudOps Agent Monitor

**URL:** `/workspaces/{workspace_id}/deployments`

**Layout:** App Shell + 3-column dashboard.

**Page header:**

- "CloudOps Deployments" (display-sm).
- "Infrastructure managed by AI agents." (text-sm, text-secondary).
- "New Deployment" primary button.

**Status Overview row (3 stat cards):**

1. IaC Resources — count (tabular-nums) + "Terraform" badge.
2. Container Images — count + "Docker" badge.
3. CI/CD Pipelines — count + "GitHub Actions / GitLab CI" badge.

**Deployment Pipeline Stepper (full-width card):**

- Horizontal pipeline: `IaC Agent → Containerization Agent → CI/CD Agent`.
- Each stage:
  - Agent icon + name.
  - Status badge.
  - Last run timestamp.
  - "View Logs" link.
  - Click → expands accordion showing last output (tool calls + generated code).
- Connecting arrows show flow direction.

**Agent Activity Feed (left, 60%):**

- Real-time tool call log. Each entry:
  - Agent tag (colored chip) + tool name (monospace) + result status icon.
  - Timestamp (relative).
  - Expand → shows input args (collapsed JSON) + output (syntax-highlighted code block).

**Generated Artifacts Panel (right, 40%):**

- Tabs: "Terraform", "Dockerfiles", "CI/CD Pipelines".
- Each file: filename (monospace) + agent tag + generated date + "View" + "Download".
- Click "View" → opens code preview in bottom sheet with syntax highlighting.

**New Deployment Modal:**

- Title: "Configure New Deployment".
- Steps (wizard, 3 steps):
  1. **IaC Config**: Provider selector (AWS/GCP/Azure), resource type selector, region input.
  2. **Container Config**: Base image input, build args textarea, registry URL.
  3. **CI/CD Config**: Platform selector (GitHub/GitLab), branch trigger input, environment variables (tag-input, masked values).
- Footer: "Back" + "Next" / "Deploy" (final step, primary).

---

### S9 — Human-in-the-Loop Approval

**URL:** Triggered as modal overlay from S3 Run Detail (also standalone: `/workspaces/{workspace_id}/approvals/{approval_id}`)

**Layout:** Full modal (lg size, 672px wide) OR standalone page with App Shell.

**Modal Header:**

- "⏸ Approval Required" (text-xl, 600, Amber-700).
- Run context: "Run: {run-name} · {workflow} v{version}".
- Time-sensitive notice: "Requested 12 minutes ago. Auto-expires in 47m 23s." (countdown, tabular-nums, animated, Amber).

**Body — 3 sections:**

**Section 1 — Context Summary (from `ApprovalGateAgent.summarize_for_approval`):**

- Card with: "What is being approved" plain text summary.
- Business entities referenced (chips).
- Risk level badge: Low / Medium / High (colored).

**Section 2 — Recommended Steps (from agent output):**

- Code block (Python/YAML, syntax highlighted, dark bg).
- Collapsible (default collapsed for brevity, "Show Details" toggle).
- Copy button.

**Section 3 — Approval History (if prior back-and-forth):**

- Timeline: "Requested by AI", "Reviewed: Modification requested (you)", "Revised by AI"…
- Each item: avatar + action + timestamp.

**Modification Request Input:**

- Textarea: placeholder "Request changes or additional context… (optional)".
- character counter (500 max).

**Footer actions:**

- Left: "Request Changes" (secondary) — submits modification, resumes agent with instructions.
- Right: "Reject" (destructive) + "Approve" (primary, Emerald for approval).
- Approve confirmation: inline confirmation replaces button row: "Confirm approval?" + "Yes, Approve" (Emerald) + "Cancel".

**Standalone page variant:**

- Shows same content but with breadcrumb "Approvals / {approval_id}".
- Side panel: related run details (mini version of S3 right panel).

**Accessibility:**

- Modal: `role="dialog"`, `aria-modal="true"`, `aria-labelledby="approval-title"`, focus trap.
- Countdown: `aria-live="polite"` on time display.
- "Approve" button: `aria-label="Approve this AI action"`.

---

### S10 — Data Connector Manager

**URL:** `/workspaces/{workspace_id}/data-sources`

**Layout:** App Shell + connector management page.

**Page header:**

- "Data Sources" (display-sm).
- "Connect your data to enable AI-powered analysis." (text-sm, text-secondary).
- "Add Data Source" primary button.

**Connector List:**
Each connector = card (horizontal, 72px height):

- Left: connector type icon (24px, colored circle bg) + name (text-md, 600) + type badge (Local File / SQL / MCP Plugin).
- Middle: connection string preview (truncated, monospace, text-xs) + health indicator dot (green=healthy, red=error, yellow=degraded).
- Right: "Last tested: 5m ago" (text-xs, text-secondary) + "Test Connection" (ghost, sm) + `…` menu (Edit, Duplicate, Delete).

**Health status indicator with tooltip:** `aria-label="Connection healthy"` annotation.

**Add Data Source Modal — Wizard:**

**Step 1 — Choose Type:**

- 3 large option cards:
  1. **Local File** — file icon — "CSV, Excel, Parquet, JSON files from local storage."
  2. **SQL Database** — database icon — "PostgreSQL, MySQL, SQLite via SQLAlchemy."
  3. **MCP Plugin** — plug icon — "Custom connector via Model Context Protocol."
- Selection: card gets Indigo border + checkmark top-right.

**Step 2 — Configure:**

*Local File:*

- "Display Name" text input.
- "Base Directory" path input (with folder-picker button).
- "Allowed Extensions" multi-select combobox (CSV / Excel / Parquet / JSON).
- "Test Connection" → shows file count found.

*SQL Database:*

- "Display Name" text input.
- "Connection URI" input (`type="password"`, `autocomplete="off"` annotation, `spellCheck={false}`). Tooltip: "Format: postgresql+psycopg2://user:pass@host/db".
- "Test Connection" → shows table count or error.
- Advanced (collapsible): pool size, max overflow, connect timeout.

*MCP Plugin:*

- "Plugin Name" text input.
- "Module Path" text input (e.g. `mypackage.connectors.custom`).
- "Config (JSON)" textarea (Monaco mini editor).
- "Load Plugin" → validates and shows status.

**Step 3 — Review & Save:**

- Summary card of all settings.
- "Save & Connect" primary button.
- Connection test result inline (spinner → success/error banner).

---

### S11 — Settings

**URL:** `/workspaces/{workspace_id}/settings`

**Layout:** App Shell + settings page with left sub-nav (200px) + content right.

**Left sub-nav sections:**

1. Profile
2. Workspace
3. Members & RBAC
4. API Keys
5. Notifications
6. Integrations
7. Danger Zone

---

**Sub-page: Profile**

- Avatar (64px) + "Change Photo" button.
- Fields: Full Name (text), Email (disabled, read-only, `text-tertiary`), Job Title, Timezone (searchable combobox with Intl.Timezone listing), Language.
- "Save Changes" primary button.
- "Unsaved changes" amber banner appears on changes (+ `beforeunload` guard annotation).

---

**Sub-page: Workspace**

- Workspace Name (text input).
- Workspace Slug (monospace input, auto-generates from name, editable).
- Region (select, locked after creation, `disabled`).
- "Save" button.

---

**Sub-page: Members & RBAC**

- Current members table:
  - Avatar + Name + Email.
  - Role selector per row (Admin / Editor / Viewer) — `<select>` with label.
  - "Remove Member" destructive icon button with `aria-label`.
- "Invite Member" section:
  - Email input (`type="email"`, `autocomplete="off"`, `spellCheck={false}`).
  - Role selector.
  - "Send Invite" button.
- Pending invites table (separate section): email + role + "Resend" + "Revoke".

---

**Sub-page: API Keys**

- "Generate New Key" primary button.
- Keys table:
  - Name (editable inline on click) + created date + last used (relative, `Intl.DateTimeFormat`) + "Revoke" destructive button with confirm popover.
- Key creation modal:
  - Name input.
  - Expiry selector (Never / 30d / 90d / 1yr).
  - On success: "Copy Your New Key" — shows key once in monospace with copy button + amber warning "This key will not be shown again."

---

**Sub-page: Notifications**

- Toggles per event type:
  - "Run completed" (on/off toggle)
  - "Run failed" (on/off toggle)
  - "Approval required" (on/off toggle)
  - "Deployment succeeded" (on/off toggle)
  - "New member joined" (on/off toggle)
- Channels: Email / Slack Webhook (input for webhook URL if Slack enabled).

---

**Sub-page: Danger Zone**

- Red-bordered card.
- "Delete Workspace" — "This permanently deletes all runs, workflows, artifacts, and reports. This action cannot be undone."
- "Delete Workspace" destructive button → confirmation modal requiring user to type workspace name.

---

### S12 — Onboarding / Workspace Provisioning

**URL:** `/onboarding` (first-time only flow after login)

**Layout:** Full-screen wizard (no sidebar). Steps indicator top-center (stepper, 4 steps).

**Step 1 — Create Workspace:**

- Workspace Name input.
- Slug preview (auto-generated, monospace).
- Region selector.
- "Continue →" primary.

**Step 2 — Connect Data Source:**

- Mirrors S10 Add Data Source step 1+2 compressed.
- "Skip for Now" ghost link bottom.

**Step 3 — Invite Teammates:**

- Tag-input for email addresses.
- Role selector (applies to all invited).
- "Send Invites" or "Skip for Now".

**Step 4 — You're all set!:**

- Confetti animation (SVG/CSS, `prefers-reduced-motion`: skip confetti).
- "Welcome to Insight Platform, {Name}!" (display-md).
- 3 next-step cards: "Create Your First Workflow", "Browse Documentation", "Watch a 3-min Demo".
- "Go to Dashboard" primary button.

---

## PART 5 — STATES MATRIX

For EACH screen, design the following variants:

| State             | Description                                              |
| ----------------- | -------------------------------------------------------- |
| **Default** | Normal loaded state with real-looking data               |
| **Loading** | Skeleton screens (no spinner-only, use skeleton loaders) |
| **Empty**   | No data, with helpful empty state (illus + CTA)          |
| **Error**   | API error, with inline error banner + retry button       |
| **Success** | Action confirmation (inline or toast)                    |

**Skeleton loader rules:**

- Match exact size/shape of final content.
- Shimmer animation (LTR, 1.5s loop).
- `prefers-reduced-motion`: static gray blocks, no animation.

---

## PART 6 — RESPONSIVE BREAKPOINTS

| Breakpoint | Width  | Notes                                       |
| ---------- | ------ | ------------------------------------------- |
| `xs`     | 375px  | Mobile — stacked layout, sidebar as drawer |
| `sm`     | 640px  | Large mobile — same as xs mostly           |
| `md`     | 768px  | Tablet — sidebar collapses to icon-only    |
| `lg`     | 1024px | Laptop — full sidebar                      |
| `xl`     | 1280px | Desktop standard                            |
| `2xl`    | 1440px | Wide desktop (primary design target)        |

**Mobile-specific rules:**

- Sidebar becomes bottom sheet drawer (slide up from bottom).
- Tables become card-list on < 640px.
- Multi-column grids collapse to single column.
- Modals: full-screen on mobile (`width: 100vw`, `height: 100dvh`).
- Touch targets: minimum 44×44px for all interactive elements.
- `touch-action: manipulation` annotation on all buttons (prevents double-tap zoom).
- `overscroll-behavior: contain` on modals and drawers.

---

## PART 7 — INTERACTIONS & ANIMATION

All animations must have a `prefers-reduced-motion: reduce` companion (instant/static fallback).

| Interaction             | Animation                 | Duration | Easing                     |
| ----------------------- | ------------------------- | -------- | -------------------------- |
| Page transition         | Fade in (opacity 0→1)    | 150ms    | ease-out                   |
| Modal open              | Scale 0.97→1 + fade in   | 200ms    | ease-out                   |
| Modal close             | Scale 1→0.97 + fade out  | 150ms    | ease-in                    |
| Drawer open             | translate-x -100%→0      | 300ms    | cubic-bezier(0.16,1,0.3,1) |
| Toast appear            | slide-up + fade in        | 200ms    | ease-out                   |
| Toast dismiss           | fade out                  | 150ms    | ease-in                    |
| Accordion open          | height 0→auto + opacity  | 200ms    | ease-out                   |
| Node selected (canvas)  | ring scale-in             | 100ms    | ease-out                   |
| Pipeline running (node) | border shimmer loop       | 1500ms   | linear                     |
| Button active           | scale(0.98)               | 80ms     | ease-in                    |
| Skeleton shimmer        | gradient translate        | 1500ms   | linear                     |
| Spinner                 | rotate 360°              | 700ms    | linear                     |
| Tab switch              | indicator translate       | 200ms    | ease-out                   |
| Tooltip appear          | fade + translate-y 2px→0 | 100ms    | ease-out                   |
| Number change           | count-up animation        | 600ms    | ease-out                   |

**Animate `transform` and `opacity` only** — never width/height/top/left directly.
Explicit `transition-property` — never `transition: all`.
Set `transform-origin: center` on scale transforms.

---

## PART 8 — ACCESSIBILITY ANNOTATIONS

Include these annotations on relevant frames:

1. **Focus order numbers** — tab order overlaid on each screen.
2. **Landmark regions** — `<header>`, `<nav>`, `<main>`, `<aside>`, `<footer>` labeled on layout.
3. **ARIA roles** — `role="dialog"`, `role="tablist"`, `role="log"` (live log), `role="timer"` (countdown), `role="alert"` (error banners), `role="status"` (toasts).
4. **ARIA labels** — all icon buttons get `aria-label` annotation callout.
5. **ARIA live regions** — `aria-live="polite"` on: toasts, async validation, log stream updates, countdown timer.
6. **Heading hierarchy** — h1 per page, h2 for sections, h3 for sub-sections. Always hierarchical.
7. **Skip Link** — "Skip to main content" visually hidden but focusable, appears on first Tab.
8. **Focus visible** — all interactive elements: `focus-visible:ring-2 ring-offset-2 ring-indigo-500`.
9. **Color contrast** — all text pairs must meet WCAG AA (4.5:1 for text, 3:1 for large text/UI). Annotate color contrast ratio for text-secondary on bg-surface.
10. **Form autocomplete** — annotate `autocomplete` values: `name`, `email`, `current-password`, `new-password`, `organization`, `off`.
11. **Error association** — `aria-describedby` linking input to error message element.
12. **Destructive confirmation** — all destructive actions (delete, revoke) require explicit confirmation step.

---

## PART 9 — DARK MODE SPECIFICATIONS

All screens must have Dark Mode variants.

**Rules:**

- `color-scheme: dark` on `<html>` when dark mode active (fixes scrollbars, native inputs).
- `<meta name="theme-color">` = `#020617` (Slate-950) in dark mode.
- Shadows become more subtle in dark mode (reduce opacity 50%).
- Code blocks: always dark (Slate-900 bg) in both modes.
- Images: no filter adjustments in dark mode (content images stay natural).
- Illustrations/icons: use `currentColor` fill so they adapt automatically.
- Toggle: System / Light / Dark — tri-state in Settings > Profile.

---

## PART 10 — COPY & CONTENT GUIDELINES

All visible text in mockups must follow:

1. **Title Case** for all headings, button labels, nav items, column headers.
2. **Active voice:** "Deploy Infrastructure" not "Infrastructure Deployment".
3. **Specific CTAs:** "Save Workflow" not "Save". "Approve This Action" not "Yes". "Delete Workspace" not "Delete".
4. **Numerals for counts:** "8 runs" not "eight runs".
5. **Ellipsis:** `…` not `...` in truncated text and loading states ("Loading…", "Saving…").
6. **`&` over "and"** in space-constrained contexts (breadcrumbs, badges).
7. **Error messages** always include next step: "Failed to save — check your connection and try again."
8. **Empty states** are helpful: "No runs yet — create your first workflow to get started."
9. **Placeholders** end with `…`: "Search agents…", "Enter workflow name…".
10. **Tooltips** are descriptive, not repeating the label: button labeled "Download" → tooltip "Download all artifacts as ZIP".
11. **Timestamps:** always use `Intl.DateTimeFormat` output format. Relative for <24h ("2 hours ago"), absolute for older (annotate locale format).
12. **File sizes:** `Intl.NumberFormat` with unit: "2.4 MB", "128 KB".

---

## PART 11 — FIGMA FILE ORGANIZATION

Structure the Figma file exactly as follows:

```
📁 Insight Platform — Design System + Screens

  📄 Cover Page
  
  📁 0 — Design System
    📄 0.1 Colors (all primitives + semantic tokens, light + dark)
    📄 0.2 Typography (all type scales with live text examples)
    📄 0.3 Spacing & Grid (8px base grid illustration)
    📄 0.4 Shadows & Elevation
    📄 0.5 Icons (Lucide usage guide + size examples)
  
  📁 1 — Components
    📄 1.1 Atoms (Button, Badge, Input, Checkbox, Toggle, Avatar, etc.)
    📄 1.2 Molecules (Form Field, Search Bar, Empty State, Toast, Modal, etc.)
    📄 1.3 Organisms (App Shell, Data Table, Workflow Node, Report Card)
  
  📁 2 — Screens Light Mode
    📄 S0 — Login
    📄 S1 — Dashboard
    📄 S2 — Runs List
    📄 S3 — Run Detail
    📄 S4 — Workflow Designer
    📄 S5 — Workflow Spec Editor
    📄 S6 — Artifacts Browser
    📄 S7 — Strategic Report
    📄 S8 — CloudOps Monitor
    📄 S9 — HITL Approval
    📄 S10 — Data Sources
    📄 S11 — Settings
    📄 S12 — Onboarding

  📁 3 — Screens Dark Mode
    (same structure as section 2)

  📁 4 — Responsive (Mobile 375px + Tablet 768px)
    📄 S0–S3, S11 mobile + tablet variants
  
  📁 5 — States
    📄 Loading (all skeleton variants)
    📄 Empty States (all screens)
    📄 Error States
  
  📁 6 — Prototype Flow
    (interactive connections between screens)
```

---

## PART 12 — PROTOTYPE FLOW CONNECTIONS

Connect these screen flows for prototype playback:

1. S0 Login → S12 Onboarding (first time) OR S1 Dashboard.
2. S12 Step 1 → Step 2 → Step 3 → Step 4 → S1 Dashboard.
3. S1 Dashboard → S2 Runs List (via "View All Runs").
4. S2 Row click → S3 Run Detail.
5. S3 "Open in Designer" (workflow link) → S4 Workflow Designer.
6. S3 "Review & Decide" (HITL banner) → S9 HITL Approval.
7. S3 "View Report" tab → S7 Strategic Report.
8. S4 "Save Draft" → same screen (updated state). "Publish" → publish modal → S5 Workflow Spec Editor.
9. S1 "New Workflow" → S4 Workflow Designer (blank canvas).
10. S1 "Browse Data Sources" → S10 Data Connector Manager.
11. Sidebar "Deployments" → S8 CloudOps Monitor.
12. Sidebar "Reports" → S7 Strategic Report (list view).
13. Avatar dropdown "Settings" → S11 Settings.
14. S11 Sidebar → sub-pages.

---

## PART 13 — SAMPLE DATA FOR MOCKUPS

Use this realistic data throughout all screens (do not use Lorem ipsum):

**Workspace:** "Acme Analytics" · slug `acme-analytics` · region `us-central1`

**Users:**

- Sarah Chen (Admin) — sarah@acme.com
- Marcus Williams (Editor) — marcus@acme.com
- Priya Sharma (Viewer) — priya@acme.com

**Workflows:**

- "Customer Churn Prediction Pipeline" — v4 (Published)
- "Q1 Revenue Forecast" — v2 (Published)
- "Market Segmentation Analysis" — v1 (Draft)

**Runs (recent):**

| ID             | Workflow                              | Status               | Duration | Triggered By     |
| -------------- | ------------------------------------- | -------------------- | -------- | ---------------- |
| `run-a1b2c3` | Customer Churn Prediction Pipeline v4 | ✅ success           | 4m 12s   | Sarah Chen       |
| `run-d4e5f6` | Q1 Revenue Forecast v2                | 🔄 running           | 1m 47s… | Marcus Williams  |
| `run-g7h8i9` | Customer Churn Prediction Pipeline v4 | ❌ failed            | 52s      | Auto (Scheduled) |
| `run-j1k2l3` | Market Segmentation Analysis v1       | ⏸ awaiting approval | 3m 01s   | Priya Sharma     |
| `run-m4n5o6` | Q1 Revenue Forecast v2                | ✅ success           | 6m 33s   | Sarah Chen       |

**Strategic Report example:**

- Title: "Q1 2026 Revenue Intelligence Report"
- Context: customer churn risk, revenue forecasting for Q1 2026
- Key Finding #1: "18.4% churn probability in enterprise tier — highest since Q3 2024"
- Recommendation #1: "Launch proactive retention campaign for enterprise accounts with ICE score 8.4"

**Agents used (in pipeline):**

- DataCleaningAgent → EDAToolsAgent → FeatureEngineeringAgent → H2O AutoML → ResultsSynthesizerAgent → NarrativeAgent → RecommendationAgent

---

*End of Figma Prompt — M9 Autonomous Strategic Analytics Platform*
*Generated: 2 March 2026 · Version 1.0 · Covers M9+M10+M12+M17+M18+M19 frontend scope*