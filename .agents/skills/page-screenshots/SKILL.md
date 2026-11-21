---
name: page-screenshots
description: Capture high-fidelity screenshots of Next.js pages across light, dark, and auto themes using a self-contained Playwright script, automatic Next.js route discovery, and historical photo preservation.
---

# Page Screenshots Skill

A self-contained Playwright-based skill that discovers pages via Next.js folder conventions (App Router and Pages Router), renders them across theme modes (`light`, `dark`, `auto`, or custom sets), captures retina-quality screenshots, and safely archives previous captures so historical images are never lost.

All scripts, outputs, and archived screenshots live directly inside this skill folder (`.agents/skills/page-screenshots`).

---

## 1. Capabilities & Features

- **Next.js Router Discovery**: Automatically crawls the Next.js directory (`frontend/src/app`, `src/app`, or `app`) to discover all `page.{tsx,jsx,js}` files and translate them into clean HTTP routes, cleanly stripping route groups (e.g., `(auth)`) and ignoring internal components and API routes.
- **Multi-Theme Support**: Captures pages in `light`, `dark`, `auto` (system preference), or any comma-separated combination (e.g. `--theme light,dark` or `--theme all`). Injects both Playwright color schemes and DOM/localStorage properties (`greenline_theme`, `.dark` classes) for complete CSS hydration.
- **Historical Photo Preservation**: Before saving a new screenshot to `screenshots/current/`, any pre-existing snapshot for that page and theme is automatically archived to `screenshots/archive/<timestamp>/`, ensuring old photos are preserved across runs.
- **Automated Login / Session**: Optional `--auth` flag automatically signs in at `/login` so protected dashboards (e.g. `/investments`, `/accounts`, `/cashflow`) render real UI components rather than login redirects.
- **Zero-Config Browser Fallback**: Automatically leverages Playwright Chromium, system Google Chrome (`/usr/bin/google-chrome`), or cached binaries.
- **Pure Script Execution**: Built as a fast, deterministic Node.js script without depending on conversational LLM iterations to take screenshots.

---

## 2. Directory Layout

```
.agents/skills/page-screenshots/
├── SKILL.md                          # Skill specification and runbook
├── scripts/
│   ├── capture.mjs                   # Main Playwright capture & discovery engine
│   └── capture.test.mjs              # Unit tests for route discovery, themes, & archival
└── screenshots/
    ├── current/                      # Latest active screenshots
    │   ├── overview-light.png
    │   ├── overview-dark.png
    │   └── login-light.png
    └── archive/                      # Historical snapshots by timestamp
        └── 2026-11-18T15-46-18-952Z/
            ├── login-light.png
            └── login-dark.png
```

---

## 3. Usage & CLI Flags

Run the script from anywhere in the repository:

```bash
node .agents/skills/page-screenshots/scripts/capture.mjs [options]
```

### CLI Options

| Flag | Argument | Default | Description |
|---|---|---|---|
| `--page` | `<route>` | `/` | Target a specific route (e.g. `/`, `/accounts`, `/investments/holdings`). |
| `--all` | None | `false` | Discover and capture all Next.js pages found in the app directory. |
| `--theme` | `<modes>` | `light` | Target theme: `light`, `dark`, `auto`, `all`, or comma-separated `light,dark`. |
| `--cookie` | `<string\|file>` | None | Inject cookies: HTTP string (`"sid=123; auth=abc"`), JSON array, or cookie file path. (Also reads `SCREENSHOT_COOKIE` or `COOKIE` env). |
| `--storage-state` | `<path>` | None | Path to Playwright storage state JSON file (`storageState.json`) containing cookies and localStorage. |
| `--list` | None | `false` | Scan and display all discovered Next.js routes without capturing screenshots. |
| `--auth` | None | `false` | Log in at `/login` before capturing protected application pages. |
| `--base-url` | `<url>` | `http://localhost:3000` | Target web server URL (reads `BASE_URL` env var if set). |
| `--viewport` | `<WxH>` | `1440x900` | Viewport dimensions (captured at 2x Device Pixel Ratio). |
| `--app-dir` | `<path>` | auto-detected | Path to Next.js `app` or `pages` directory. |
| `--output-dir` | `<path>` | `.../screenshots` | Base directory for `current/` and `archive/` images. |

---

## 4. Common Recipes

### Discover all Next.js routes
```bash
node .agents/skills/page-screenshots/scripts/capture.mjs --list
```

### Capture a single page in both Light and Dark modes
```bash
node .agents/skills/page-screenshots/scripts/capture.mjs --page /login --theme light,dark
```

### Capture using an authenticated session Cookie
```bash
# Via CLI argument
node .agents/skills/page-screenshots/scripts/capture.mjs --page /accounts --theme dark --cookie "session_id=your_cookie_here"

# Or via environment variable
SCREENSHOT_COOKIE="session_id=your_cookie_here" node .agents/skills/page-screenshots/scripts/capture.mjs --page /accounts --theme light
```

### Capture using Playwright Storage State file
```bash
node .agents/skills/page-screenshots/scripts/capture.mjs --page /investments --theme dark --storage-state ./playwright/.auth/user.json
```

### Capture an authenticated dashboard with automated form login
```bash
node .agents/skills/page-screenshots/scripts/capture.mjs --page /accounts --theme dark --auth
```

### Capture all discovered pages across all themes
```bash
node .agents/skills/page-screenshots/scripts/capture.mjs --all --theme all --cookie "session=..."
```

---

## 5. Automated Testing

Run the included regression suite using Node's native test runner:

```bash
node --test .agents/skills/page-screenshots/scripts/capture.test.mjs
```
