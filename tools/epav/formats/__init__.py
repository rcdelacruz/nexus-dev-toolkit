"""
The docs/ formats nexus reads and writes, each defined once.

Every writer and every reader of a format imports it from here, so the two can't drift apart
(v3: /dev-tasks-planner wrote TASK_ID while load_task read task_id). Each format carries
FORMAT_VERSION, which is independent of the package version.

Rule for all of them: lenient when reading (any header case, spacing, Excel BOM, the
project's own ID scheme), strict when writing (one documented layout).
"""

FORMAT_VERSION = 1
