-- requires: foreign_keys off
-- Decision log (#96, E1 to E4 of #71):
--   * risk_before: estimated residual risk of the first selection; residual_risk is the risk of the selection
--     that runs (they differ when a decision abstains to a broader selection or to every test)
--   * extras: the report sections of the decision (JSON object), so explain, MCP and the dashboard can show them
--   * mode 'no-source-change': a change that edits only tests is stored too
-- SQLite cannot change a CHECK constraint in place, so the table is rebuilt. Store.migrate turns foreign keys off
-- for this file (marker above): dropping the old table must not cascade to the decision_* child rows, which keep
-- their decision ids. It runs `pragma foreign_key_check` before committing.

drop view labelled_decision;

create table decision_new (
    id               integer primary key,
    recorded         real not null,
    base_revision_id integer not null references revision (id),
    head             text,                        -- 'working-tree' today
    mode             text not null check (mode = 'calibrated' or mode glob 'budget *' or mode = 'no-source-change'),
    alpha            real check (alpha is null or (alpha > 0 and alpha < 1)),
    alpha_t          real,                        -- adaptive level when the decision was made
    threshold        real,                        -- calibrated score threshold (null in budget mode)
    residual_risk    real check (residual_risk is null or (residual_risk >= 0 and residual_risk <= 1)),
    verdict          text not null check (verdict in ('proceed', 'abstain')),
    risk_before      real check (risk_before is null or (risk_before >= 0 and risk_before <= 1)),   -- null: before 0005
    extras           text                         -- JSON object of report sections (Store writes it; no JSON functions in SQL)
);

insert into decision_new (id, recorded, base_revision_id, head, mode, alpha, alpha_t, threshold, residual_risk, verdict)
    select id, recorded, base_revision_id, head, mode, alpha, alpha_t, threshold, residual_risk, verdict from decision;

drop table decision;
alter table decision_new rename to decision;
create index decision_by_mode on decision (mode, id);

create view labelled_decision as
    select d.*, o.missed, o.recorded as labelled from decision d join decision_outcome o on o.decision_id = d.id;
