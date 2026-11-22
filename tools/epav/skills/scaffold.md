# /scaffold

**Day 0 — Production Scaffold** (one-time project setup)

Generates a complete production-grade scaffold from the architecture document and Figma export.
Output: infrastructure + design system + UI shell + AGENTS.md + knowledge/.

**Goal: structure and standards, not live integrations.**
Day 0 prepares developers to follow golden paths and best practices from the very start.
Real auth providers, live databases, and external service integrations are Day 1.

- No business logic. No API wiring. No placeholder pages.
- **Auth = mock only** — login form redirects to dashboard, no real provider calls (no Supabase Auth, no NextAuth, no OAuth). Real auth is wired in Day 1.
- **Data = mock only** — all components use local mock data, no live DB queries.
- **No external service dependency** — the project must build and run without any credentials or services configured.
- The install + dev command must work out of the box — use the stack's row in **Ecosystem reference** below.

---

## Ecosystem reference

Nexus is stack-agnostic: use the row for the stack the arch doc prescribes. If the stack is not listed, apply the same columns using that ecosystem's own official tooling — look the tools up, never guess from memory.

| Ecosystem | `package_manager` | Manifest → lock file | Install + dev | Build (VALIDATE gate) | Lint / format | Pre-commit hooks |
|---|---|---|---|---|---|---|
| Node / TS (Next.js, Vite, Nuxt, SvelteKit, Angular, NestJS, Express…) | npm / pnpm / yarn / bun | `package.json` → `package-lock.json` / `pnpm-lock.yaml` / `yarn.lock` / `bun.lock` | `npm install && npm run dev` | `npm run build` | ESLint + Prettier (or Biome) | husky + lint-staged + commitlint |
| Python (Django, FastAPI, Flask…) | uv / poetry / pipenv / pip | `pyproject.toml` → `uv.lock` / `poetry.lock`; `Pipfile` → `Pipfile.lock` | `uv sync && uv run <server>` | `uv build` or `python -m compileall .` + tests | ruff (lint + format) + mypy/pyright | pre-commit framework |
| Java / Kotlin (Spring Boot, Quarkus, Micronaut, Ktor, Android) | maven / gradle | `pom.xml` / `build.gradle(.kts)` (+ `gradle.lockfile` with locking on) | `./mvnw spring-boot:run` / `./gradlew run` | `./mvnw package -DskipTests` / `./gradlew build -x test` | Checkstyle or Spotless; ktlint/detekt for Kotlin | pre-commit framework or Gradle/Maven git-hook plugin |
| Scala (Play, Akka/Pekko) | sbt | `build.sbt` | `sbt run` | `sbt compile` | scalafmt + scalafix | pre-commit framework |
| .NET (ASP.NET Core, Blazor, MAUI) | dotnet | `*.csproj` → `packages.lock.json` (`RestorePackagesWithLockFile`) | `dotnet restore && dotnet run` | `dotnet build -c Release` | `dotnet format` + analyzers | Husky.Net or pre-commit framework |
| Go (Gin, Echo, Fiber, Chi) | go | `go.mod` → `go.sum` | `go mod download && go run ./cmd/<app>` | `go build ./...` | gofmt + golangci-lint | pre-commit framework or Makefile hook |
| Rust (Axum, Actix, Tauri) | cargo | `Cargo.toml` → `Cargo.lock` | `cargo run` | `cargo build` | rustfmt + clippy | pre-commit framework or cargo-husky |
| PHP (Laravel, Symfony) | composer | `composer.json` → `composer.lock` | `composer install && php artisan serve` / `symfony serve` | `composer validate && php -l` + tests | PHP-CS-Fixer or Pint + PHPStan/Psalm | GrumPHP or pre-commit framework |
| Ruby (Rails, Sinatra) | bundler | `Gemfile` → `Gemfile.lock` | `bundle install && bin/rails server` | `bin/rails zeitwerk:check` + `bin/rails assets:precompile` | RuboCop | lefthook or overcommit |
| Elixir (Phoenix) | mix | `mix.exs` → `mix.lock` | `mix deps.get && mix phx.server` | `mix compile --warnings-as-errors` | `mix format` + Credo | pre-commit framework or git_hooks |
| Swift (SwiftUI, Vapor) | swiftpm / cocoapods | `Package.swift` → `Package.resolved`; `Podfile` → `Podfile.lock` | `swift run` / open in Xcode | `swift build` / `xcodebuild build` | SwiftFormat + SwiftLint | pre-commit framework |
| Dart / Flutter | pub | `pubspec.yaml` → `pubspec.lock` | `flutter pub get && flutter run` | `flutter build apk --debug` (or `web` / `ios --no-codesign`) | `dart format` + `flutter analyze` | lefthook or pre-commit framework |
| React Native / Expo | npm / pnpm / yarn / bun | `package.json` → lock file | `npx expo start` | `npx expo export` (or a debug native build) | ESLint + Prettier | husky + lint-staged |
| C / C++ (Qt, native) | conan (or vcpkg) | `conanfile.txt`/`conanfile.py` → `conan.lock` | `conan install . && cmake --preset default && cmake --build` | `cmake --build --preset default` | clang-format + clang-tidy | pre-commit framework |
| Haskell | cabal | `*.cabal` → `cabal.project.freeze` | `cabal run` | `cabal build` | ormolu/fourmolu + hlint | pre-commit framework |

**Design token format by UI stack** (never copy oklch/hex from a design export raw):
- Web with Tailwind v4: `hsl()` — never oklch, hex, or rgb
- Web without Tailwind: CSS custom properties in `hsl()`
- Flutter: `Color(0xFF...)` in a generated `color_theme.dart` / `ThemeData`
- React Native: hex strings in a `colors.ts` theme file
- SwiftUI: an Asset Catalog color set or a `Color` extension
- Jetpack Compose / KMP: a `Color(0xFF...)` palette in `ui/theme/Color.kt` + `MaterialTheme`
- .NET MAUI / WPF: a `ResourceDictionary` of `Color` resources

---

## Prerequisites

Before running /scaffold:
1. Architecture document must be in `docs/arch-docs/`
2. Figma export ZIP must be available
3. Run: `ingest_architecture_doc` MCP tool on `docs/arch-docs/`
4. Run: `ingest_figma_zip` MCP tool on the Figma ZIP

---

## EVALUATE — Understand the Architecture and Design

Load `docs/arch-docs/` (ARCH doc + ADRs) and the Figma export. Then walk through:

**Architecture:**
1. The stack decisions and why they were made
2. The data model — tables, relationships, indexes
3. What infrastructure is needed from the start
4. The middleware stack and auth flow
5. Error response format and error handling strategy
6. Security rules and constraints

**Design:**
7. Design tokens (colors, typography, spacing, radii, shadows)
8. Component inventory (every component, variants, states)
9. Layout patterns (grid, breakpoints, responsive behavior)
10. Iconography (style, sizes, library)

**Read the design-system reference file itself, in full — not a summary of
it.** If a `knowledge/*.md` design-system doc already exists from a prior
pass, treat it as a lead, not a substitute: it can go stale or compress away
detail. Read the actual `Design System.dc.html` (or equivalent) export
directly before relying on any derived summary.

**These generated design-system pages often restate the same fact in
multiple places, and the restatements can disagree** — an early illustrative
example may show one value while the file's own underlying data (the
JS/script section actually driving the page's swatches, e.g. a `TYPE_SCALE`
or `COLORS` array) declares another. Don't stop at the first section that
seems to answer the question — read the whole file. When two statements in
the same file conflict, prefer whichever one is more specific or names an
actual file path in the codebase (e.g. "`lib/icons.jsx` now imports from
lucide-react") over a generic illustrative swatch — the specific one is
usually the more recently updated, authoritative one.

**Also check for sibling token files in the same export folder** (e.g.
`tokens.css`, `design-tokens.css`, `tailwind.config.js` alongside the `.dc.html`
files) — these can be more authoritative than the HTML page, or in rare cases
be misplaced/leftover from a different sibling app's export (verify the
palette and page names inside actually match this app before trusting one).

**Design token conversion (before writing any design file):**
Figma exports colors in oklch or hex — never copy them raw. Convert to the target stack's native format — see **Design token format by UI stack** in the Ecosystem reference.

Do NOT generate code yet. Produce an EVALUATE SUMMARY covering all 10 points.
Stop and wait for confirmation before proceeding to PLAN.

---

## PLAN — Boilerplate + UI Shell + Project Rules

Based on the architecture document and Figma design, plan four things:

**1. INFRASTRUCTURE BOILERPLATE**
- Project structure — every directory, annotated
- Database schema — from the architecture doc's data model
- Environment variables — complete list, documented
- Auth flow — as specified in the architecture
- Error handling — using the format from the architecture

**2. UI SHELL (from Figma)**
- Design system config in the stack's native format (e.g. Tailwind config + CSS custom properties for web, `ThemeData` for Flutter, `MaterialTheme` for Compose) plus font loading
- Component architecture (name, path, props interface, variants, composition, accessibility)
- Page layouts (every page from the Figma, structured with placeholder data)
- Build order (component dependency chain)

**3. AGENTS.md (cross-tool project rules)**
- Project description and stack summary
- Backend and frontend coding standards
- Security rules, git conventions, quality gates

**4. KNOWLEDGE DIRECTORY STRUCTURE**
- `knowledge/rules/coding-standards.md`
- `knowledge/prompts/dev/` (initial prompt templates)
- `knowledge/patterns/` (implement-and-test chain)
- Design system spec saved to `knowledge/`

Output as a blueprint. No code yet.
Stop and wait for `/apply` approval before proceeding.

---

## APPLY — Generate the Complete Boilerplate

Plan approved. Generate everything in one scaffold.

**MANDATORY FIRST STEP — call `resolve_package_versions` before writing any file.**

`resolve_package_versions` runs the real package manager in a temp directory and returns exact pinned versions from the lock file. Use those exact versions in the manifest — no guessing, no ranges, no AI memory.

```
Step 1 — call resolve_package_versions with all deps + stack hint from arch doc
  packages: in the ecosystem's own naming, e.g.
    npm      ["next@16", "@supabase/supabase-js@2"]
    Python   ["django@5", "psycopg[binary]@3"]
    JVM      ["org.springframework.boot:spring-boot-starter-web@3"]
    Go       ["github.com/gin-gonic/gin@1"]
    Composer ["laravel/framework@11"]
    SwiftPM  ["https://github.com/vapor/vapor@4"]
  package_manager: the stack's value from the Ecosystem reference (or omit and pass stack_hint)
  → returns: { "status": "resolved", "versions": { "next": "16.2.9", ... } }

  status is not "resolved"?
    "partial" / "failed"  → read `errors`, fix the package names/constraints, call again
    "tool_missing"        → the package manager binary is not installed — install it, call again
    "unsupported"         → follow `instructions`: pin from the official registry / CLI, never memory

Step 2 — write the package manifest (Ecosystem reference → Manifest column)
  with the EXACT versions from Step 1 — no ^, ~, *, or open ranges

Step 3 — run the package manager to produce the lock file
  (Ecosystem reference → lock file; e.g. npm install → package-lock.json,
   uv lock → uv.lock, bundle lock → Gemfile.lock, dotnet restore → packages.lock.json)
```

NEVER write "latest" in any manifest.
NEVER write semver ranges (^ or ~) in the final manifest.
NEVER write patch versions from AI memory — training data is always stale.

**1. Infrastructure:**
- `.gitignore` — node_modules, .env*, build outputs, OS files
- `.env.example` — all variables documented, no real secrets
- Initial migration — exact schema from arch doc
- Auth middleware — as specified
- Error handler — consistent format from arch doc
- Health-check endpoint
- Seed script — idempotent test data
- Linter + formatter config — the stack's **Lint / format** column in the Ecosystem reference
- Pre-commit hooks — the stack's **Pre-commit hooks** column. Details for the common ones:
  - **npm:** husky + lint-staged + commitlint
    - `package.json` must have `"prepare": "husky"` in scripts
    - Write `.husky/pre-commit` with `npx lint-staged`, then `chmod +x .husky/pre-commit`
    - Write `.lintstagedrc.json` (lint + format on staged files)
    - Write `.commitlintrc.json` with `@commitlint/config-conventional`
    - CI pipeline must set `HUSKY=0` env var — husky fails in CI without a git repo
  - **pre-commit framework** (Python, Go, Rust, JVM, Elixir, C/C++, Haskell, Swift): `.pre-commit-config.yaml` running the stack's formatter + linter, plus a conventional-commit `commit-msg` hook
  - **Ruby:** lefthook (`lefthook.yml`) or overcommit · **PHP:** GrumPHP · **.NET:** Husky.Net
- README with local setup instructions
- CI pipeline config (GitHub Actions or equivalent: lint, typecheck, test, db push)

**2. UI shell (matching Figma exactly):**
- Design system config — tokens from Figma, in the stack's native format (web: tailwind.config.ts + globals.css)
- **(Web + Tailwind)** **Any hand-written base selector in globals.css (`a`, `body`, `input:focus`,
  `thead th`, etc.) MUST be wrapped in `@layer base { ... }`.** Tailwind v4
  emits its own utilities into a cascade layer; an unlayered rule beats a
  layered one regardless of specificity — so a plain `a { color: ... }` will
  silently override every `text-*` utility ever applied to a link, app-wide,
  not just on hover. This is invisible when diffing declared values against
  the Figma export (which sets colors via inline `style`, immune to this),
  and only shows up once rendered — verify by checking the generated
  `globals.css` has no selector outside `@layer base`/`@theme`/`@import`.
- Icons ported from a Figma export's raw `<svg>` relying on a parent's
  `text-align: center` for centering will NOT center once run through
  Tailwind: preflight sets `svg { display: block }`, and block elements
  ignore `text-align`. Give such icons `mx-auto` (or center via flex)
  instead — don't assume `text-align: center` survives the port.
- All components with typed props (TypeScript props, Dart/Swift/Kotlin constructor params, C# properties…) and ALL visual states:
  (default, hover, focus, disabled, loading, empty, error)
- All page layouts responsive to Figma breakpoints
- Semantic HTML + ARIA attributes throughout
- Placeholder/mock data — NOT real API calls
- Prop interfaces defined so Day 1 can wire real data without changing the component

**3. AGENTS.md at project root**

**4. knowledge/ directory with initial content**

**Package requirements:**
- Exact versions from `resolve_package_versions` — not from memory, not ranges
- NEVER write "latest" — it is not a version
- NEVER write patch versions from AI memory
- Run the package manager after writing the manifest to produce the lock file
- No beta, canary, or RC packages
- No deprecated packages or APIs

**Production-grade standards:**
- No placeholder pages or unused dependencies
- Auth protecting all routes that need it
- Consistent error response format throughout
- Proper logging setup (not console.log)
- Environment-based configuration (dev/staging/prod)
- Security headers configured (next.config.ts for Next.js; framework middleware for others — e.g. Spring Security, Django `SecurityMiddleware`, Rails `config.action_dispatch.default_headers`, ASP.NET Core middleware, helmet for Express)
- Database connection pooling (use pooler URL, not direct)

**Next.js 16 specifics:**
- Route proxy file is `proxy.ts` not `middleware.ts` — export function `proxy`, not `middleware`
- `tsconfig.json` must use `"jsx": "react-jsx"` not `"jsx": "preserve"`

**Do NOT implement:**
- Real auth provider integration (Supabase Auth, NextAuth, OAuth, etc.)
- Live database queries or mutations
- External service calls (email, storage, payment, etc.)
- API endpoints or business logic beyond health check
- Data fetching, form submissions, or backend interactions
- Dev tasks from the CSV — that is Day 1

**Mock auth pattern:**
The login page accepts any input and sets a session cookie (preferred over localStorage — cookies are readable server-side for route guarding). No credentials checked.
- Cookie holds the user's mock role (e.g. `mock-role=admin`), 8h expiry
- Route guard (middleware/proxy) reads the cookie and redirects unauthenticated requests to login
- Server components read the cookie to get the current session (no Context provider needed)
- All role-gating uses the mock role value — no JWT, no OAuth token
Real auth provider replaces the cookie on Day 1.

Output as complete files. The install + dev command must work — the stack's **Install + dev** column in the Ecosystem reference.

---

## VALIDATE — Validate Infrastructure + Design Fidelity

**MANDATORY FIRST STEP — run the build. VALIDATE is not started until this passes.**

Use the **Build (VALIDATE gate)** command for the stack prescribed in the arch doc — see the Ecosystem reference at the top of this skill. Stack not listed: use that ecosystem's standard release/compile command.

If the build fails, fix ALL errors before running any other checks. Do not proceed to the checklist until the build exits with code 0. A failed build is an automatic [BLOCKER] that overrides everything else.

---

Review everything against the architecture doc AND Figma.

**Packages:**
1. Are all dependencies on stable versions (no beta/canary/RC)?
2. Any deprecated packages or APIs in use?
3. Are versions pinned exactly in the lock file (the stack's lock file from the Ecosystem reference)?
4. Any known security vulnerabilities? (npm audit / pip-audit / bundle audit / composer audit / `dotnet list package --vulnerable` / govulncheck / cargo audit / OWASP dependency-check / etc.)

**Infrastructure:**
5. Does the project structure match the architecture?
6. Does the schema match the data model?
7. Are all env vars from the architecture doc present?
8. Is logging production-grade (a structured logger, not console.log / print / println)?
9. Are security headers and CORS configured?
10. Is database connection pooling set up?

**UI fidelity:**
11. Do components match the Figma design?
12. Responsive at 320px, 768px, 1024px, 1440px?
13. All visual states render with placeholder data?
14. Accessibility — keyboard nav, WCAG AA contrast?
15. Prop interfaces typed for Day 1 wiring?
16. No business logic or API calls in components?
17. `grep` `globals.css` for any selector outside `@layer base { }` /
    `@theme { }` / `@import` — an unlayered rule there silently overrides
    every matching Tailwind utility app-wide (not just on hover; see
    "UI shell" above). Matching declared hex/px values against the Figma
    export is NOT sufficient proof of correctness — that only confirms the
    *value* is present somewhere, not that the cascade actually resolves to
    it once rendered.
18. Any icon centered via a parent's `text-align: center` — confirm it
    carries `mx-auto` (or sits in a flex-centered parent), since Tailwind's
    preflight makes `<svg>` block-level and text-align won't center it.

**AGENTS.md + knowledge directory:**
17. Coding standards match the architecture?
18. Design system spec saved to knowledge/?

**Git hygiene:**
19. Pre-commit hooks configured and working? (the stack's Pre-commit hooks column — e.g. husky executable + lint-staged for npm, `pre-commit install` done for the pre-commit framework)

Classify every issue: [BLOCKER] / [FIX NOW] / [BACKLOG]
Fix every [BLOCKER] and [FIX NOW] before calling Day 0 complete.
