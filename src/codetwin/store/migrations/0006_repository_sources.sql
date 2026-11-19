-- requires: foreign_keys off
-- Connected repositories given by URL (`[[repos]] url = ...`, synced into .codetwin/repos): an analysis target can
-- now also be 'not-synced' (a URL entry whose local copy does not exist yet) or 'invalid' (an entry that cannot
-- be used, e.g. both path and url, a duplicate name, a refused URL).
-- SQLite cannot change a CHECK constraint in place, so analysis_target is rebuilt with the same ids. Foreign keys
-- are off for this file (marker above), so dropping the old table does not cascade to the consumer_file,
-- impacted_test, contract_site and analysis_unknown rows that point at it; Store.migrate checks them before
-- committing. The two views that read the table are dropped and created again unchanged.

drop view repository_relation;
drop view breaking_matrix;

create table analysis_target_new (
    id                integer primary key,
    analysis_id       integer not null references impact_analysis (id) on delete cascade,
    repository_id     integer not null references repository (id),
    revision_id       integer references revision (id),   -- null: not a git checkout, not found or not synced
    language          text,
    status            text not null check (status in ('analysed', 'not-found', 'not-synced', 'invalid', 'no-package',
                                                       'unsupported')),
    runtime_evidence  integer not null check (runtime_evidence in (0, 1)),   -- it had a recorded run
    unique (analysis_id, repository_id)
);
insert into analysis_target_new (id, analysis_id, repository_id, revision_id, language, status, runtime_evidence)
    select id, analysis_id, repository_id, revision_id, language, status, runtime_evidence from analysis_target;
drop table analysis_target;
alter table analysis_target_new rename to analysis_target;

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
