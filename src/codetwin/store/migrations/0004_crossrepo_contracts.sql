-- Cross-repository dependencies and API contracts (docs/database.md, "Repositories and contracts").
--
-- Design sources, adapted to a single local database:
--   * repositories provide and reference packages, and an analysis is tied to the commit of every repository it
--     read (Sourcegraph's cross-repository index: packages from export/import monikers, uploads per repo+commit);
--   * an API is an entity that a repository provides and others consume (Backstage: providesApi / consumesApi);
--   * contract content is stored once per content hash and published at revisions, so the diff of two contents is
--     computed and stored once (Pact Broker: pact versions by content sha, publications per consumer version);
--   * a contract change has a stable check id and a severity level (oasdiff: check ids, ERR / WARN / INFO).
-- Results of analyses are kept so that "which repositories used this endpoint" has a history, and every result
-- names the revision of each repository it was computed from (stale results are detectable).

-- ===================================================================== repository graph
create table package (                            -- a unit others import: a PyPI/npm/Go module name
    id       integer primary key,
    manager  text not null default '.',           -- 'pypi', 'npm', ...; '.' when unknown (SCIP placeholder)
    name     text not null,
    unique (manager, name)
);

create table package_provider (                   -- repository provides package (export side)
    repository_id  integer not null references repository (id),
    package_id     integer not null references package (id),
    source         text not null check (source in ('config', 'detected')),
    primary key (repository_id, package_id)
) without rowid;

create table repository_link (                    -- consumer depends on provider; declared in [[repos]]
    id           integer primary key,
    consumer_id  integer not null references repository (id),
    provider_id  integer not null references repository (id),
    source       text not null default 'config' check (source in ('config', 'detected')),
    first_seen   real not null,
    last_seen    real not null,                   -- last analysis that found it declared
    ended        real,                            -- when it stopped being declared; null while it is
    unique (consumer_id, provider_id),
    check (consumer_id <> provider_id)
);

-- ===================================================================== API contracts
create table api (                                -- an API description file a repository provides
    id             integer primary key,
    repository_id  integer not null references repository (id),
    file_id        integer not null unique references code_entity (id),
    format         text not null check (format in ('openapi', 'json-schema')),
    title          text
);

create table contract_version (                   -- one row per distinct content of an API file
    id            integer primary key,
    api_id        integer not null references api (id) on delete cascade,
    content_sha   text not null check (length(content_sha) = 64),   -- sha256 of the text
    spec_version  text,                           -- e.g. '3.0.3' or '2.0'; null for JSON schema
    content       text not null,
    recorded      real not null,
    unique (api_id, content_sha)
);

create table contract_publication (               -- which content an API had at a revision
    revision_id  integer not null references revision (id) on delete cascade,
    api_id       integer not null references api (id) on delete cascade,
    version_id   integer not null references contract_version (id) on delete cascade,
    recorded     real not null,
    primary key (revision_id, api_id)
) without rowid;

create table api_element (                        -- a stable part of an API across its versions
    id        integer primary key,
    api_id    integer not null references api (id) on delete cascade,
    kind      text not null check (kind in ('path', 'operation', 'parameter', 'response', 'schema', 'property')),
    location  text not null,                      -- 'GET /users/{id}', 'GET /users/{id} query id', 'User.email'
    unique (api_id, location)
);

create table contract_diff (                      -- computed once per pair of contents and differ version
    id              integer primary key,
    old_version_id  integer not null references contract_version (id) on delete cascade,
    new_version_id  integer not null references contract_version (id) on delete cascade,
    tool_version    text not null,
    recorded        real not null,
    unique (old_version_id, new_version_id, tool_version),
    check (old_version_id <> new_version_id)
);

create table contract_change (
    id          integer primary key,
    diff_id     integer not null references contract_diff (id) on delete cascade,
    ordinal     integer not null,
    element_id  integer not null references api_element (id),
    check_id    text not null,                    -- 'parameter-removed', 'type-changed', ... (contracts/diff.py)
    level       text not null check (level in ('error', 'warning', 'info')),   -- error = breaking
    detail      text not null,
    api_path    text,                             -- the API path, used to find path literals in code
    field       text,                             -- the field or parameter name, used to find uses
    unique (diff_id, ordinal)
);
create index contract_change_by_element on contract_change (element_id);

-- ===================================================================== impact analyses (results, with history)
create table impact_analysis (
    id                integer primary key,
    kind              text not null check (kind in ('cross-repo', 'contracts')),
    recorded          real not null,
    base_revision_id  integer not null references revision (id),
    head              text not null default 'working-tree',
    tool_version      text not null,
    summary           text not null
);
create index impact_analysis_by_kind on impact_analysis (kind, id);

create table analysis_target (                    -- one repository an analysis looked at, at one revision
    id                integer primary key,
    analysis_id       integer not null references impact_analysis (id) on delete cascade,
    repository_id     integer not null references repository (id),
    revision_id       integer references revision (id),   -- null: not a git checkout, or not found
    language          text,
    status            text not null check (status in ('analysed', 'not-found', 'no-package', 'unsupported')),
    runtime_evidence  integer not null check (runtime_evidence in (0, 1)),   -- it had a recorded run
    unique (analysis_id, repository_id)
);

create table analysis_changed_symbol (            -- changed symbols of this repository that were searched for
    analysis_id  integer not null references impact_analysis (id) on delete cascade,
    entity_id    integer not null references code_entity (id),
    primary key (analysis_id, entity_id)
) without rowid;

create table analysis_diff (                      -- contract diffs a contracts analysis looked at
    analysis_id  integer not null references impact_analysis (id) on delete cascade,
    diff_id      integer not null references contract_diff (id) on delete cascade,
    primary key (analysis_id, diff_id)
) without rowid;

create table consumer_file (                      -- cross-repo: a dependent's file that imports this repository
    id         integer primary key,
    target_id  integer not null references analysis_target (id) on delete cascade,
    file_id    integer not null references code_entity (id),
    link       text not null check (link in ('uses-changed-symbol', 'imports-package')),
    is_test    integer not null check (is_test in (0, 1)),
    unique (target_id, file_id)
);

create table consumer_import (
    consumer_id  integer not null references consumer_file (id) on delete cascade,
    ordinal      integer not null,
    import       text not null,
    primary key (consumer_id, ordinal)
) without rowid;

create table consumer_symbol_use (                -- name-matched use of a changed symbol (names are not unique,
    consumer_id  integer not null references consumer_file (id) on delete cascade,   -- so not a foreign key)
    symbol       text not null,
    line         integer not null check (line > 0),
    primary key (consumer_id, symbol, line)
) without rowid;

create table contract_site (                      -- contracts: code that may rely on a changed API element
    id         integer primary key,
    target_id  integer not null references analysis_target (id) on delete cascade,
    change_id  integer not null references contract_change (id) on delete cascade,
    file_id    integer not null references code_entity (id),
    line       integer not null check (line > 0),
    how        text not null check (how in ('path-literal', 'name-match')),
    unique (target_id, change_id, file_id, line)
);

create table impacted_test (                      -- a test of a target that reaches an affected file
    id         integer primary key,
    target_id  integer not null references analysis_target (id) on delete cascade,
    test_id    integer not null references code_entity (id),
    change_id  integer references contract_change (id) on delete cascade,   -- contracts only
    evidence   text not null                      -- 'runtime', 'static', 'direct:uses-changed-symbol', ...
);
create unique index impacted_test_once on impacted_test (target_id, test_id, coalesce(change_id, 0), evidence);

create table analysis_unknown (                   -- what the analysis could not see; never dropped
    analysis_id  integer not null references impact_analysis (id) on delete cascade,
    ordinal      integer not null,
    target_id    integer references analysis_target (id) on delete cascade,
    text         text not null,
    primary key (analysis_id, ordinal)
) without rowid;

-- ===================================================================== views
-- Typed relations between repositories, packages and APIs in one shape (Backstage-style relation triples).
create view repository_relation as
    select r1.name as source, 'dependsOn' as type, r2.name as target from repository_link l
        join repository r1 on r1.id = l.consumer_id join repository r2 on r2.id = l.provider_id
        where l.ended is null
    union all
    select r.name, 'providesPackage', p.name from package_provider pp
        join repository r on r.id = pp.repository_id join package p on p.id = pp.package_id
    union all
    select r.name, 'providesApi', f.path from api a
        join repository r on r.id = a.repository_id join code_entity f on f.id = a.file_id
    union all
    select distinct r.name, 'consumesApi', f.path from contract_site s
        join analysis_target t on t.id = s.target_id join repository r on r.id = t.repository_id
        join contract_change c on c.id = s.change_id join api_element e on e.id = c.element_id
        join api a on a.id = e.api_id join code_entity f on f.id = a.file_id;

-- Content of every API at every revision it was seen at.
create view api_history as
    select a.id as api_id, f.path as file, rv.sha, v.content_sha, v.spec_version, p.recorded
    from contract_publication p join api a on a.id = p.api_id join code_entity f on f.id = a.file_id
    join revision rv on rv.id = p.revision_id join contract_version v on v.id = p.version_id;

-- Pact-style matrix: for each breaking change in an analysis, each repository looked at, and whether it is
-- affected (code may rely on it), clear (analysed, nothing found) or unknown (could not be analysed).
create view breaking_matrix as
    select ad.analysis_id, c.id as change_id, e.location, c.check_id, r.name as repository,
           case when t.status <> 'analysed' then 'unknown'
                when exists (select 1 from contract_site s where s.target_id = t.id and s.change_id = c.id) then 'affected'
                else 'clear' end as state,
           (select count(*) from contract_site s where s.target_id = t.id and s.change_id = c.id) as sites,
           (select count(*) from impacted_test it where it.target_id = t.id and it.change_id = c.id) as tests
    from analysis_diff ad join contract_change c on c.diff_id = ad.diff_id and c.level = 'error'
    join api_element e on e.id = c.element_id
    join analysis_target t on t.analysis_id = ad.analysis_id join repository r on r.id = t.repository_id;
