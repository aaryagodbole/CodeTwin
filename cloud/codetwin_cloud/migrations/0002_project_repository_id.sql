-- GitHub's numeric repository id, from the repository_id claim of the first OIDC upload. Names can be renamed,
-- transferred or reused by a new repository; the id cannot, so later OIDC uploads must carry the same id.
alter table project add column github_repository_id bigint;
