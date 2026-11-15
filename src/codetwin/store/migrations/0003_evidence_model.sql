-- Normalized evidence store (docs/database.md has the ER diagram and the reasoning behind each table).
--
-- Replaces the JSON-blob tables of 0001/0002 (runs, static, decisions, outcomes, state, test_outcomes). The Python
-- step registered for this file (store/legacy.py) copies their rows into these tables in the same transaction, then
-- drops them. Never edit this file once released; add 0004_*.sql instead.
--
-- Conventions
--   * every table has a surrogate integer key or a composite natural key; text identities (paths, shas, test ids)
--     live once, in `revision` and `code_entity`, and are referenced by id;
--   * `recorded` / `observed` columns are Unix time in seconds (REAL);
--   * `ordinal` columns keep the order the analyser produced, so facts read back exactly as they were written;
--   * foreign keys are enforced (Store turns on `pragma foreign_keys`); children of a run, snapshot or decision are
--     deleted with it.

-- ===================================================================== code model
-- Every revision and code entity belongs to a repository. Row 1 is the repository this database lives in; other
-- rows are connected repositories ([[repos]]), whose files and commits are referenced by cross-repository and
-- contract analyses (0004). Their own runs stay in their own databases.
create table repository (
    id        integer primary key,
    name      text not null unique,               -- '.' for this repository, else the [[repos]] name
    location  text,                               -- path relative to this repository, or a URL
    is_self   integer not null default 0 check (is_self in (0, 1))
);
create unique index repository_one_self on repository (is_self) where is_self = 1;
insert into repository (id, name, location, is_self) values (1, '.', '.', 1);

create table revision (
    id             integer primary key,
    repository_id  integer not null default 1 references repository (id),
    sha            text not null,                 -- a git commit, or the pseudo-revision 'working-tree'
    recorded       real not null,
    unique (repository_id, sha)
);

create table code_entity (
    id             integer primary key,
    repository_id  integer not null default 1 references repository (id),
    kind           text not null check (kind in ('file', 'class', 'function', 'method')),
    path           text not null,                 -- repository-relative path of the file
    name           text not null default '',      -- qualified name inside the file; '' for a file
    unique (repository_id, kind, path, name),
    check ((kind = 'file') = (name = ''))
);

-- ===================================================================== static evidence (one snapshot per file per revision)
create table file_snapshot (
    id           integer primary key,
    revision_id  integer not null references revision (id) on delete cascade,
    file_id      integer not null references code_entity (id),
    unique (revision_id, file_id)
);

create table snapshot_import (                    -- FileFacts.imports: imported module names
    snapshot_id  integer not null references file_snapshot (id) on delete cascade,
    ordinal      integer not null,
    module       text not null,
    primary key (snapshot_id, ordinal)
) without rowid;

create table snapshot_line (                      -- FileFacts.dyn_lines and FileFacts.mod_lines
    snapshot_id  integer not null references file_snapshot (id) on delete cascade,
    role         text not null check (role in ('dynamic', 'module')),
    ordinal      integer not null,
    line         integer not null check (line >= 0),
    primary key (snapshot_id, role, ordinal)
) without rowid;

create table definition (                         -- FileFacts.defs: [start incl. decorators, end, first body line]
    snapshot_id  integer not null references file_snapshot (id) on delete cascade,
    ordinal      integer not null,
    start_line   integer not null,
    end_line     integer not null,
    body_line    integer not null,
    primary key (snapshot_id, ordinal),
    check (start_line <= end_line)
) without rowid;

create table symbol_occurrence (                  -- FileFacts.symbols: where a class/function/method sits in a snapshot
    snapshot_id  integer not null references file_snapshot (id) on delete cascade,
    ordinal      integer not null,
    entity_id    integer not null references code_entity (id),
    first_line   integer not null,
    last_line    integer not null,
    primary key (snapshot_id, ordinal),
    check (first_line <= last_line)
) without rowid;

create table unresolved_reference (               -- FileFacts.dynamic: links that exist but cannot be resolved
    snapshot_id  integer not null references file_snapshot (id) on delete cascade,
    ordinal      integer not null,
    kind         text not null,                   -- e.g. 'getattr', 'importlib', 'unparsed'
    primary key (snapshot_id, ordinal)
) without rowid;

-- Typed links between code entities that are *not* observed by running tests (runtime links are derived from
-- coverage, see the `evidence` view). Only 'static' is written today (FileFacts.deps); 'declared', 'co-change' and
-- 'suggested' are reserved for the planned evidence sources, and 'suggested' rows must never be used for selection.
create table evidence_edge (
    id            integer primary key,
    revision_id   integer not null references revision (id) on delete cascade,
    src_id        integer not null references code_entity (id),
    dst_id        integer not null references code_entity (id),
    type          text not null check (type in ('static', 'declared', 'co-change', 'suggested')),
    ordinal       integer,                        -- position in FileFacts.deps (static edges)
    source        text not null,                  -- what produced it, e.g. 'import-resolution'
    tool_version  text,                           -- codetwin version that produced it
    observed      real not null,
    status        text not null default 'current' check (status in ('current', 'stale', 'rejected')),
    unique (revision_id, src_id, dst_id, type),
    check (src_id <> dst_id)
);
create index evidence_edge_dst on evidence_edge (dst_id, revision_id);

-- ===================================================================== runtime evidence (one full run per revision)
create table test_run (
    id           integer primary key,
    revision_id  integer not null unique references revision (id) on delete cascade,
    recorded     real not null,
    returncode   text not null,                   -- runner exit code as text (several runners may be merged)
    wall         real not null check (wall >= 0)
);

create table test_result (                        -- one row per test file seen by the run
    run_id    integer not null references test_run (id) on delete cascade,
    test_id   integer not null references code_entity (id),
    ordinal   integer not null,                   -- order of TestRun.durations, then covered-only tests
    duration  real check (duration is null or duration >= 0),   -- null: traced but not timed
    traced    integer not null check (traced in (0, 1)),        -- 1: the run recorded coverage for this test
    primary key (run_id, test_id)
) without rowid;

create table test_failure (                       -- TestRun.failing, in runner order
    run_id   integer not null references test_run (id) on delete cascade,
    ordinal  integer not null,
    case_id  text not null,                       -- 'file::case', or a file for a file-level error
    primary key (run_id, ordinal)
) without rowid;

create table coverage_line (                      -- TestRun.covered: test file -> source file -> line
    run_id   integer not null,
    test_id  integer not null,
    file_id  integer not null references code_entity (id),
    line     integer not null check (line >= 0),
    primary key (run_id, test_id, file_id, line),
    foreign key (run_id, test_id) references test_result (run_id, test_id) on delete cascade
) without rowid;
create index coverage_by_line on coverage_line (run_id, file_id, line);    -- "which tests run this line?"

create table import_line (                        -- TestRun.import_lines: lines a file runs at import time
    run_id   integer not null references test_run (id) on delete cascade,
    file_id  integer not null references code_entity (id),
    line     integer not null check (line >= 0),
    primary key (run_id, file_id, line)
) without rowid;

-- Pass/fail observations of single test files outside full runs (CI uploads, `codetwin why` reruns) and of
-- recorded runs; the history failure triage reads.
create table test_outcome (
    id           integer primary key,
    revision_id  integer not null references revision (id),
    test_id      integer not null references code_entity (id),
    recorded     real not null,
    passed       integer not null check (passed in (0, 1)),
    source       text not null check (source in ('record', 'ci', 'rerun'))
);
create index test_outcome_by_test on test_outcome (test_id, recorded);

create table test_outcome_case (
    outcome_id  integer not null references test_outcome (id) on delete cascade,
    ordinal     integer not null,
    case_id     text not null,
    primary key (outcome_id, ordinal)
) without rowid;

-- ===================================================================== decisions
create table decision (
    id               integer primary key,
    recorded         real not null,
    base_revision_id integer not null references revision (id),
    head             text,                        -- 'working-tree' today
    mode             text not null check (mode = 'calibrated' or mode glob 'budget *'),
    alpha            real check (alpha is null or (alpha > 0 and alpha < 1)),
    alpha_t          real,                        -- adaptive level when the decision was made
    threshold        real,                        -- calibrated score threshold (null in budget mode)
    residual_risk    real check (residual_risk is null or (residual_risk >= 0 and residual_risk <= 1)),
    verdict          text not null check (verdict in ('proceed', 'abstain'))
);
create index decision_by_mode on decision (mode, id);

create table decision_score (                     -- the model's score of every candidate test
    decision_id  integer not null references decision (id) on delete cascade,
    test_id      integer not null references code_entity (id),
    score        real,                            -- null: score was not a number
    primary key (decision_id, test_id)
) without rowid;

create table decision_selection (                 -- tests the decision runs
    decision_id  integer not null references decision (id) on delete cascade,
    test_id      integer not null references code_entity (id),
    primary key (decision_id, test_id)
) without rowid;

create table decision_reason (                    -- reasons and unknowns, in the order shown to the user
    decision_id  integer not null references decision (id) on delete cascade,
    ordinal      integer not null,
    text         text not null,
    primary key (decision_id, ordinal)
) without rowid;

create table decision_outcome (                   -- label from `codetwin learn`: did the selection miss a test?
    decision_id  integer primary key references decision (id) on delete cascade,
    missed       integer not null check (missed in (0, 1)),
    recorded     real not null
);

-- ===================================================================== learning state (append-only histories)
-- decision_id is null only for rows imported from the 0001 `state` blobs, whose decision was not kept.
create table calibration_point (                  -- min non-forced score of an affected test, per labelled change
    id           integer primary key,
    decision_id  integer unique references decision (id) on delete set null,
    value        real,                            -- null: +inf (no affected test was scored)
    recorded     real not null
);

create table recalibration_point (                -- (score, affected?) pairs for the isotonic recalibrator
    id           integer primary key,
    decision_id  integer references decision (id) on delete set null,
    test_id      integer references code_entity (id),
    score        real not null,
    label        integer not null check (label in (0, 1))
);

create table change_point (                       -- change-level features z(c) and whether the change missed tests
    id           integer primary key,
    decision_id  integer references decision (id) on delete set null,
    label        integer not null check (label in (0, 1)),
    recorded     real not null
);

create table change_feature (
    point_id  integer not null references change_point (id) on delete cascade,
    name      text not null,
    value     real,
    primary key (point_id, name)
) without rowid;

create table adaptive_level (                     -- alpha_t after each update; the current level is the last row
    id           integer primary key,
    decision_id  integer references decision (id) on delete set null,
    alpha_t      real not null,
    recorded     real not null
);

-- Scratch values that are not evidence (e.g. features computed for a decision not yet labelled).
create table setting (
    key    text primary key,
    value  text not null                          -- JSON
);

-- ===================================================================== views
create view latest_run as
    select t.*, r.sha from test_run t join revision r on r.id = t.revision_id where r.repository_id = 1
    order by t.recorded desc, t.id desc limit 1;

-- Every typed link of every revision in one shape: static/declared/co-change/suggested edges, runtime links
-- derived from coverage (test -> source file), and unresolved references (file -> nothing).
create view evidence as
    select e.revision_id, e.src_id, e.dst_id, e.type, e.source, e.status from evidence_edge e
    union all
    select t.revision_id, c.test_id, c.file_id, 'runtime', 'coverage', 'current'
    from (select distinct run_id, test_id, file_id from coverage_line) c join test_run t on t.id = c.run_id
    union all
    select s.revision_id, s.file_id, null, 'unresolved', u.kind, 'current'
    from unresolved_reference u join file_snapshot s on s.id = u.snapshot_id;

create view labelled_decision as
    select d.*, o.missed, o.recorded as labelled from decision d join decision_outcome o on o.decision_id = d.id;

-- Tests that both passed and failed on the same revision: the outcome did not depend on the code.
create view flaky_test as
    select o.revision_id, e.path as test, sum(o.passed) as passes, sum(1 - o.passed) as failures
    from test_outcome o join code_entity e on e.id = o.test_id
    group by o.revision_id, o.test_id having passes > 0 and failures > 0;
