from ._util import engine, print_json

NAME, HELP, ORDER = "learn", "run the full suite, record whether the last selection missed tests, update calibration", 40


def add_arguments(p) -> None:
    pass


def run(args) -> int:
    with engine(args) as eng:
        pending = eng.store.get_state("pending_change_features")
        last = eng.store.get_state("last_decision") or {}
        out = eng.learn()
        # label the change-level features only if they were computed for the decision just learned from
        if isinstance(pending, dict) and "features" in pending and \
                [pending.get(k) for k in ("base", "mode", "selected")] == [last.get(k) for k in ("base", "mode", "selected")]:
            pts = eng.store.get_state("change_points", [])
            pts.append([pending["features"], int(bool(out.get("missed")))])
            eng.store.set_state("change_points", pts[-2000:])
            eng.store.set_state("pending_change_features", None)
            out["change_points"] = len(pts)
        print_json(out)
    return 0
