from ._util import engine, print_json

NAME, HELP, ORDER = "learn", "run the full suite, record whether the last selection missed tests, update calibration", 40


def add_arguments(p) -> None:
    pass


def run(args) -> int:
    with engine(args) as eng:
        pending = eng.store.get_state("pending_change_features")
        last = eng.store.last_decision() or {}
        out = eng.learn()
        # label the change-level features only if they were computed for the decision just learned from
        if isinstance(pending, dict) and "features" in pending and \
                [pending.get(k) for k in ("base", "mode", "selected")] == [last.get(k) for k in ("base", "mode", "selected")]:
            eng.store.add_change_point(pending["features"], int(bool(out.get("missed"))), last.get("id"))
            eng.store.set_state("pending_change_features", None)
            out["change_points"] = len(eng.store.change_points())
        print_json(out)
    return 0
