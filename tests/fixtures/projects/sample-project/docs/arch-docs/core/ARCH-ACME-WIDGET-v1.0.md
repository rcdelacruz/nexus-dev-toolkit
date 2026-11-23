# Architecture Document — ACME Widget

## 1\. Document Metadata
Version 1.0.

## 2\. System Overview
Two clients share one backend. A reverse proxy sits in front (existing — e.g. Traefik / Nginx).

## 3\. Component Breakdown
widget-web and widget-api.

## 4\. Technology Choices

### Frontend Framework
- **Choice**: Next.js v16 (TypeScript)
- **Rationale**: specified in the PRD (NFR-009).

### Backend Framework
- **Choice**: NestJS v11, Node.js Active LTS

### Caching
- **Prior choice (superseded)**: Redis, as a general cache.
- **Client-confirmed correction**: Redis is no longer used anywhere.

### Shared platform choices
| Category | Choice | Rationale |
| -------- | ------ | --------- |
| Database | MS SQL Server, on-premise | Platform-wide |
| Secrets | No vault. Client's words: "we inject variables, appsettings.json for .NET framework" | Confirmed |

## 5\. Data Model
Tables: widget, owner.

## 6\. Integration and API Design
REST.

## 7\. Deployment Topology
Docker secrets / Kubernetes Secrets were discussed for later.

## 8\. NFR Fulfillment
NFR-009 met by SSR.

## 9\. Open Questions and Deferred Decisions
None.
