from ._util import engine, print_json

NAME, HELP, ORDER = "learn", "run the full suite, record whether the last selection missed tests, update calibration", 40


def add_arguments(p) -> None:
    pass


def run(args) -> int:
    with engine(args) as eng:
        z = eng.store.get_state("pending_change_features")
        out = eng.learn()
        if z is not None:   # label the change-level risk features of the decision just learned from
            pts = eng.store.get_state("change_points", [])
            pts.append([z, int(bool(out.get("missed")))])
            eng.store.set_state("change_points", pts[-2000:])
            eng.store.set_state("pending_change_features", None)
            out["change_points"] = len(pts)
        print_json(out)
    return 0
