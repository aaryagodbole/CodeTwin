-- CodeTwin Cloud schema (docs/cloud.md, "Database"). Applied once, tracked in schema_migrations; never edit an
-- applied file, add the next number instead.

create table project (
    id               bigint generated always as identity primary key,
    owner            text not null,
    name             text not null,
    public           boolean not null default false,
    uploads_enabled  boolean not null default true,
    created_at       timestamptz not null default now()
);
create unique index project_owner_name on project (lower(owner), lower(name));

-- Upload tokens for self-hosted servers and CI without OIDC. Only the SHA-256 of the token is stored.
create table project_token (
    id          bigint generated always as identity primary key,
    project_id  bigint not null references project (id) on delete cascade,
    token_hash  text not null unique,
    created_at  timestamptz not null default now(),
    last_used   timestamptz
);

create table report (
    id              bigint generated always as identity primary key,
    project_id      bigint not null references project (id) on delete cascade,
    received_at     timestamptz not null default now(),
    head_sha        text not null,
    base_sha        text,
    ref             text,
    pull_request    integer,
    run_source      text not null,
    run_id          text not null,
    run_attempt     integer not null default 1,
    engine_version  text not null,
    decision        text not null check (decision in ('proceed', 'abstain')),
    residual_risk   double precision not null,
    alpha           double precision,
    threshold       double precision,
    mode            text not null,
    selected_count  integer not null,
    payload         jsonb not null,
    unique (project_id, run_id, run_attempt, head_sha)
);
create index report_project_received on report (project_id, received_at desc);

create table outcome (
    report_id    bigint primary key references report (id) on delete cascade,
    missed       boolean not null,
    failing      jsonb not null default '[]',
    received_at  timestamptz not null default now()
);
