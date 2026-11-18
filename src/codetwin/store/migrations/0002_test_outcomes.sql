-- Every observed outcome of a test file, appended (never replaced), so failures can be traced over time and
-- flaky tests recognised: one row per test file per run (record, CI import, rerun).
create table if not exists test_outcomes (
  id integer primary key autoincrement, sha text, recorded real, test text, passed integer,
  failing_cases text, source text);
create index if not exists test_outcomes_test on test_outcomes (test, recorded);
