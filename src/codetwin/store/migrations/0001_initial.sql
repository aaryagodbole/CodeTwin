create table if not exists runs (
  sha text primary key, recorded real, returncode text, wall real,
  durations text, failing text, covered text, import_lines text);
create table if not exists static (
  sha text, file text, facts text, primary key (sha, file));
create table if not exists decisions (
  id integer primary key autoincrement, recorded real, base text, head text, mode text,
  alpha real, alpha_t real, threshold real, residual_risk real, decision text, selected text, reasons text);
create table if not exists outcomes (
  decision_id integer primary key, missed integer, recorded real);
create table if not exists state (key text primary key, value text);
