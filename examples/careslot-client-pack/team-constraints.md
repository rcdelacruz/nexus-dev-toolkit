# Team and constraints — for the architect (made up)

- **People:** 2 developers (both strong in Python and Django; one has used htmx; neither has run a React SPA
  in production), 1 designer. A tech lead is one of the two developers.
- **Deadline:** live before 1 October (flu season). About 10 weeks of development.
- **Hosting:** the clinic group has an AWS account; everything must run in the clinic's region (data protection).
  Managed PostgreSQL and Redis are available there.
- **SMS:** the clinic already has an account with a regional SMS provider (HTTPS API, no SDK needed).
- **Operations:** nobody on call at night; the system must recover on its own from a crashed process, and
  reminders must not be lost if the SMS provider is briefly down.
- **Users:** about 200 patients online at the busiest time; receptionists and doctors on desktops.
- **The designer** may also export a React version of the screens from the design tool. Decide whether the team
  builds on it or not — and write down why.
