# /scaffold

**Day 0 — Production Scaffold** (one-time project setup)

Generates a complete production-grade scaffold from the architecture document
(plus a Figma export, for project shapes that have a UI). What gets generated
depends on two independent fields from `ingest_architecture_doc`: `project_shape`
(the primary output — a single choice, it can't be more than one of these) and
`has_infrastructure_component` (a separate yes/no — true whenever the doc ALSO
defines its own infrastructure-as-code, regardless of `project_shape`):

| `project_shape` | Output |
|---|---|
| `web_app` / `mobile_app` | infrastructure boilerplate + design system + UI shell + AGENTS.md + knowledge/ |
| `backend_api` / `data_pipeline` / `cli_or_library` | infrastructure boilerplate + AGENTS.md + knowledge/ — no UI shell, no Figma |
| `infrastructure` | IaC modules/playbooks/charts + AGENTS.md + knowledge/ — no application boilerplate, no UI shell, no Figma |

**If `has_infrastructure_component` is also `true`** for any non-`infrastructure`
shape above (e.g. a 3-tier app whose doc also defines the Terraform/OpenTofu
modules that provision what it runs on): generate the IaC deliverables
*in addition to* that shape's normal output, not instead of it. Every "PLAN"/
"APPLY"/"VALIDATE" item below marked `infrastructure` also applies whenever
`has_infrastructure_component` is true, on top of — not replacing — the
app-shaped items, unless `project_shape` itself is `infrastructure` (nothing
else to add on top of).

**Goal: structure and standards, not live integrations.**
Day 0 prepares developers to follow golden paths and best practices from the very start.
Real auth providers, live databases, and external service integrations are Day 1.
For `infrastructure`, the equivalent boundary is: real modules/resources, wired
correctly and passing `plan`/`lint`, but never `apply`d against real cloud
accounts in Day 0.

- No business logic. No API wiring. No placeholder pages.
- **`web_app` / `mobile_app` only — Auth = mock only** — login form redirects to dashboard, no real provider calls (no Supabase Auth, no NextAuth, no OAuth). Real auth is wired in Day 1.
- **Data = mock only** — all components use local mock data, no live DB queries. (Not applicable to `infrastructure`: there's no application data layer to mock — a database showing up in the arch doc there is a provisioned resource, e.g. an RDS instance, not something to fake.)
- **No external service dependency** — the project must build and run (for `infrastructure`: `terraform plan` / `helm template` / `ansible-playbook --check` must succeed) without any credentials or live cloud resources.
- The install + dev command must work out of the box (e.g. `npm install && npm run dev` for Next.js, `flutter pub get && flutter run` for Flutter, `terraform init && terraform plan` for Terraform).

---

## Prerequisites

Before running /scaffold:
1. Architecture document must be in `docs/arch-docs/`
2. Run: `ingest_architecture_doc` MCP tool on `docs/arch-docs/` — read its
   `project_shape` field first, it determines the rest of this checklist.
3. **If `project_shape` is `web_app` or `mobile_app`:** a Figma export ZIP
   must also be available. Run: `ingest_figma_zip` MCP tool on it.
4. **Any other `project_shape`:** no Figma/UI step — there's no design to
   ingest. Skip straight to EVALUATE.

---

## EVALUATE — Understand the Architecture (and Design, if there is a UI)

Load `docs/arch-docs/` (ARCH doc + ADRs). If `project_shape` is `web_app` or
`mobile_app`, also load the Figma export. Then walk through:

**Architecture (always):**
1. The stack decisions and why they were made
2. The data model — tables, relationships, indexes. For `infrastructure`,
   this means data stores as provisioned resources (e.g. an RDS instance's
   engine/size/backup policy), not an application ORM schema.
3. What infrastructure is needed from the start. For `infrastructure`, this
   *is* the whole project — every resource, module, and environment.
4. The middleware stack and auth flow (skip for `infrastructure`)
5. Error response format and error handling strategy (skip for `infrastructure`)
6. Security rules and constraints. For `infrastructure`, this means IAM
   policies, network ACLs/security groups, secrets management (no plaintext
   secrets in `.tf`/`.yml` files), and remote state encryption/locking.

**Design — `web_app` / `mobile_app` only, skip entirely otherwise:**
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
Figma exports colors in oklch or hex — never copy them raw. Convert to the target stack's native format:
- Web (Tailwind v4): `hsl()` — never oklch, hex, or rgb
- Flutter: `Color(0xFF...)` or generated `color_theme.dart`
- React Native: hex strings in a `colors.ts` theme file

Do NOT generate code yet. Produce an EVALUATE SUMMARY covering points 1-6
always, plus 7-10 for `web_app`/`mobile_app`. Stop and wait for confirmation
before proceeding to PLAN.

---

## PLAN — Boilerplate (+ UI Shell, if there is one) + Project Rules

Based on the architecture document (and Figma design, if applicable), plan:

**1. INFRASTRUCTURE BOILERPLATE** — `web_app` / `mobile_app` / `backend_api` / `data_pipeline`
- Project structure — every directory, annotated
- Database schema — from the architecture doc's data model
- Environment variables — complete list, documented
- Auth flow — as specified in the architecture
- Error handling — using the format from the architecture

**1′. INFRASTRUCTURE-AS-CODE PLAN** — whenever `has_infrastructure_component`
is true; replaces item 1 above if `project_shape` is `infrastructure`, runs
alongside item 1 otherwise (e.g. the 3-tier-app-with-its-own-Terraform case)
- Module/playbook/chart layout — every directory, annotated (e.g.
  `modules/vpc`, `modules/eks`, `environments/staging`, `environments/prod`)
- Every resource the arch doc calls for, grouped by module, with its exact
  provider/chart source (this is what `resolve_package_versions` pins)
- Remote state backend (S3+DynamoDB, Terraform Cloud, etc.) and how each
  environment isolates its state
- Variable/tfvars structure per environment — no hardcoded account IDs,
  regions, or secrets
- What runs `plan`/`lint` on PR vs. `apply` on merge — plan the CI shape,
  don't wire real CI credentials in Day 0

**2. UI SHELL (from Figma)** — `web_app` / `mobile_app` only, skip entirely otherwise
- Design system config (tailwind.config.ts, globals.css, CSS custom properties, font loading)
- Component architecture (name, path, props interface, variants, composition, accessibility)
- Page layouts (every page from the Figma, structured with placeholder data)
- Build order (component dependency chain)

**3. AGENTS.md (cross-tool project rules)**
- Project description and stack summary
- Backend and frontend coding standards (or IaC conventions, for `infrastructure`)
- Security rules, git conventions, quality gates

**4. KNOWLEDGE DIRECTORY STRUCTURE**
- `knowledge/rules/coding-standards.md`
- `knowledge/prompts/dev/` (initial prompt templates)
- `knowledge/patterns/` (implement-and-test chain)
- Design system spec saved to `knowledge/` — `web_app` / `mobile_app` only

Output as a blueprint. No code yet.
Stop and wait for `/apply` approval before proceeding.

---

## APPLY — Generate the Complete Boilerplate

Plan approved. Generate everything in one scaffold.

**MANDATORY FIRST STEP — call `resolve_package_versions` before writing any file.**

`resolve_package_versions` runs the real package manager (or, for the three
IaC tools below, the real CLI — terraform or tofu, whichever is installed;
same lock file either way) in a temp directory and returns exact pinned
versions. Use those exact versions in the manifest — no guessing, no ranges,
no AI memory.

**If `has_infrastructure_component` is true alongside an app-shaped
`project_shape`:** call `resolve_package_versions` twice, once per component
— once with the app's stack_hint/packages, once with the IaC stack_hint/
packages. One call resolves one tool; a mixed project has two.

```
Step 1 — call resolve_package_versions with all deps + stack hint from arch doc

  Application stacks:
    packages: ["next@^16", "react@^19", "@supabase/supabase-js@^2", ...]
    stack_hint: "Next.js 16 TypeScript" / "Flutter 3" / "Go" / etc.
    → returns: { "versions": { "next": "16.2.9", "react": "19.2.7", ... } }

  Terraform (providers only — format "source@constraint"):
    packages: ["hashicorp/aws@~>5.0", "hashicorp/random"]
    stack_hint: "Terraform modules for an AWS VPC and EKS cluster"
    → returns: { "versions": { "hashicorp/aws": "5.31.0", ... } }

  Helm (repository URL required — format "name@version@repo_url"):
    packages: ["nginx@~15.0.0@https://charts.bitnami.com/bitnami"]
    stack_hint: "Helm chart for our microservices on Kubernetes"
    → returns: { "versions": { "nginx": "15.0.2" } }

  Ansible (collections only — format "namespace.name:constraint"):
    packages: ["community.general:>=8.0.0"]
    stack_hint: "Ansible playbooks provisioning an EC2 fleet"
    → returns: { "versions": { "community.general": "13.4.0" } }

Step 2 — write the REAL manifest in the project with EXACT versions from Step 1
  npm:       package.json        — "next": "16.2.9"  (no ^ or ~)
  Flutter:   pubspec.yaml        — exact version constraints
  Go:        go.mod              — exact module versions
  Rust:      Cargo.toml          — exact versions
  Terraform: versions.tf         — required_providers with exact "version ="
  Helm:      Chart.yaml          — dependencies with exact version + repository
  Ansible:   requirements.yml    — collections with exact version

Step 3 — run the real tool again in the actual project to produce its lockfile
  npm install                          → package-lock.json
  flutter pub get                      → pubspec.lock
  go mod tidy                          → go.sum
  cargo build                          → Cargo.lock
  terraform/tofu init -backend=false   → .terraform.lock.hcl (then configure the real backend)
  helm dependency update               → Chart.lock
  ansible-galaxy collection install -r requirements.yml   → collections/ (no lockfile — the pinned version in requirements.yml *is* the pin)
```

NEVER write "latest" in any manifest.
NEVER write semver ranges (^ or ~) in the final manifest (Terraform provider
`~>` constraints are the one exception — that's Terraform's own pinning
syntax, paired with the exact resolved version from `.terraform.lock.hcl`).
NEVER write patch versions from AI memory — training data is always stale.

**1. Infrastructure** — `web_app` / `mobile_app` / `backend_api` / `data_pipeline`:
- `.gitignore` — node_modules, .env*, build outputs, OS files
- `.env.example` — all variables documented, no real secrets
- Initial migration — exact schema from arch doc
- Auth middleware — as specified
- Error handler — consistent format from arch doc
- Health-check endpoint
- Seed script — idempotent test data
- Linter + formatter config (stack-appropriate: ESLint + Prettier for JS/TS; gofmt + golangci-lint for Go; clippy for Rust; dart format for Flutter)
- Pre-commit hooks (stack-appropriate):
  - **npm:** husky + lint-staged + commitlint
    - `package.json` must have `"prepare": "husky"` in scripts
    - Write `.husky/pre-commit` with `npx lint-staged`, then `chmod +x .husky/pre-commit`
    - Write `.lintstagedrc.json` (lint + format on staged files)
    - Write `.commitlintrc.json` with `@commitlint/config-conventional`
    - CI pipeline must set `HUSKY=0` env var — husky fails in CI without a git repo
  - **Python:** pre-commit framework with `.pre-commit-config.yaml`
  - **Go / Rust / Java:** git hooks via Makefile or pre-commit framework
- README with local setup instructions
- CI pipeline config (GitHub Actions or equivalent: lint, typecheck, test, db push)

**1′. Infrastructure-as-code deliverables** — whenever `has_infrastructure_component`
is true; replaces item 1 above if `project_shape` is `infrastructure`, generated
alongside item 1 otherwise:
- `.gitignore` — `.terraform/`, `*.tfstate*`, `.terraform.lock.hcl` only if
  intentionally not committed (most teams DO commit the lock file — don't
  ignore it by default), `crash.log`, chart `charts/*.tgz`, ansible
  `collections/`
- Every module/playbook/chart from the PLAN, with real resource
  definitions from the arch doc — no placeholder resources
- Remote state backend configured (e.g. S3 backend block with a DynamoDB
  `dynamodb_table` for locking) — never local state for anything beyond a
  throwaway example
- Per-environment `.tfvars` / `group_vars` / `values-<env>.yaml` — no
  hardcoded account IDs, regions, or secrets; secrets referenced via a
  secrets manager (e.g. `aws_secretsmanager_secret` data source), never
  inline
- Linter config: `.tflint.hcl` (if `tflint` available) or note in README to
  install it; `.ansible-lint` config; Helm chart passes `helm lint`
- Pre-commit hooks: `terraform fmt -check`, `tflint`, `ansible-lint`, or
  `helm lint` as applicable, via `.pre-commit-config.yaml`
- README with real init/plan instructions (`terraform init && terraform
  plan`, `helm template . --debug`, `ansible-playbook --check`) and an
  explicit note that `apply`/`install`/real playbook runs are NOT part of
  Day 0
- CI pipeline config: lint + plan/dry-run on PR (never apply)

**2. UI shell (matching Figma exactly)** — `web_app` / `mobile_app` only, skip entirely otherwise:
- Design system config (tailwind.config.ts, globals.css — tokens from Figma)
- **Any hand-written base selector in globals.css (`a`, `body`, `input:focus`,
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
- All components with TypeScript props and ALL visual states:
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
- Run the package manager (or terraform/helm/ansible-galaxy) after writing
  the manifest to produce the lock file
- No beta, canary, or RC packages
- No deprecated packages or APIs

**Production-grade standards:**
- No placeholder pages or unused dependencies
- Auth protecting all routes that need it (`web_app`/`mobile_app`/`backend_api`)
- Consistent error response format throughout (not `infrastructure`)
- Proper logging setup (not console.log)
- Environment-based configuration (dev/staging/prod)
- Security headers configured (next.config.ts for Next.js, equivalent for other stacks) — not `infrastructure`
- Database connection pooling (use pooler URL, not direct) — not `infrastructure`
- **Whenever `has_infrastructure_component` is true:** every resource tagged
  (environment, owner, cost-center as applicable), no `0.0.0.0/0` ingress
  without an explicit justification comment, state backend encrypted at rest

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
- **Whenever `has_infrastructure_component` is true:** `terraform`/`tofu apply`,
  `helm install`/`helm upgrade`, or `ansible-playbook` run for real against
  any cloud account — planning/linting/templating only

**Mock auth pattern** — `web_app` / `mobile_app` only:
The login page accepts any input and sets a session cookie (preferred over localStorage — cookies are readable server-side for route guarding). No credentials checked.
- Cookie holds the user's mock role (e.g. `mock-role=admin`), 8h expiry
- Route guard (middleware/proxy) reads the cookie and redirects unauthenticated requests to login
- Server components read the cookie to get the current session (no Context provider needed)
- All role-gating uses the mock role value — no JWT, no OAuth token
Real auth provider replaces the cookie on Day 1.

Output as complete files. The install + dev command must work (e.g. `npm
install && npm run dev` for Next.js, `flutter pub get && flutter run` for
Flutter, `terraform init && terraform plan` for Terraform).

---

## VALIDATE — Validate Infrastructure + Design Fidelity

**MANDATORY FIRST STEP — run the build/plan/lint. VALIDATE is not started until this passes.**

Use the command for the stack prescribed in the arch doc. If `has_infrastructure_component`
is true alongside an app-shaped `project_shape`, run BOTH the app's command
and the IaC command(s) — both must pass:

| Stack | Build / validate command |
|---|---|
| Next.js | `npm run build` |
| Vite / React | `npm run build` |
| Flutter | `flutter build apk --debug` |
| Go | `go build ./...` |
| Rust | `cargo build` |
| Java / Spring | `mvn package -DskipTests` |
| Terraform / OpenTofu | `terraform validate && terraform plan` (or `tofu validate && tofu plan`) |
| Helm | `helm lint . && helm template .` |
| Ansible | `ansible-lint` (or `ansible-playbook --syntax-check` if ansible-lint isn't available) |

If it fails, fix ALL errors before running any other checks. Do not proceed
to the checklist until it exits 0. A failed build/plan/lint is an automatic
[BLOCKER] that overrides everything else.

---

Review everything against the architecture doc (and Figma, for `web_app`/`mobile_app`).

**Packages:**
1. Are all dependencies on stable versions (no beta/canary/RC)?
2. Any deprecated packages or APIs in use?
3. Are versions pinned exactly in the lock file (package-lock.json / pubspec.lock / go.sum / Cargo.lock / .terraform.lock.hcl / Chart.lock)?
4. Any known security vulnerabilities? (npm audit / flutter pub audit / cargo audit / `tflint` or `checkov` for Terraform / etc.)

**Infrastructure:**
5. Does the project structure match the architecture?
6. Does the schema match the data model? (`infrastructure`: does every resource match what the arch doc specified?)
7. Are all env vars from the architecture doc present? (`infrastructure`: are all tfvars/group_vars/values documented and environment-scoped?)
8. Is logging production-grade (not console.log)? (not `infrastructure`)
9. Are security headers and CORS configured? (`infrastructure`: are IAM policies/security groups least-privilege, no `0.0.0.0/0` without justification?)
10. Is database connection pooling set up? (not `infrastructure`)
10′. **Whenever `has_infrastructure_component` is true:** Is the state backend remote and locked (not local state)? Is it encrypted at rest? Are there zero plaintext secrets/credentials committed anywhere in `.tf`/`.yml` files?

**UI fidelity — `web_app` / `mobile_app` only, skip entirely otherwise:**
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
19. Coding standards match the architecture?
20. Design system spec saved to knowledge/? (`web_app` / `mobile_app` only)

**Git hygiene:**
21. Pre-commit hooks configured and working? (husky executable + lint-staged for npm; `terraform fmt`/`tflint`/`ansible-lint`/`helm lint` for `infrastructure`; equivalent for other stacks)

Classify every issue: [BLOCKER] / [FIX NOW] / [BACKLOG]
Fix every [BLOCKER] and [FIX NOW] before calling Day 0 complete.
