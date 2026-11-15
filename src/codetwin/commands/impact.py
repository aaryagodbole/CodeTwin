from ._util import engine, print_json

NAME, HELP, ORDER = "impact", "tests and unknowns reached by files or symbols (path:Name, path:Class.method, path:42)", 50


def add_arguments(p) -> None:
    p.add_argument("files", nargs="+", help="source files, or symbols as path:Name / path:Class.method / path:line")
    p.add_argument("--json", action="store_true")


def _symbols(eng, targets: list[tuple[str, str]]) -> list[dict]:
    from ..graph.symbols import find, symbol_impact
    facts = eng.facts_now()
    base = eng.store.latest_run_sha()
    run = eng.store.get_run(base) if base else None
    tests = eng.tests_now()
    out = []
    for path, query in targets:
        hits = find(facts, path, query)
        if not hits:
            out.append({"symbol": {"name": query, "file": path}, "tests": {}, "callers": [],
                        "unknowns": [f"no function or class '{query}' found in {path}"], "summary": "not found"})
            continue
        for sym in hits:
            out.append(symbol_impact(eng.root, facts, run, tests, sym, eng.lang.is_test).to_dict())
    return out


def run(args) -> int:
    from ..graph.symbols import parse_target
    parsed = [parse_target(f) for f in args.files]
    syms = [(p, q) for p, q in parsed if q is not None]
    files = [p for p, q in parsed if not q]
    with engine(args) as eng:
        imp = eng.impact(files) if files else None
        sym_out = _symbols(eng, syms) if syms else []
    if args.json:
        if imp is not None and not sym_out:
            print_json({"tests": {t: sorted(v) for t, v in imp.tests.items()}, "unknowns": imp.unknowns})
        elif imp is None and len(sym_out) == 1:
            print_json(sym_out[0])
        else:
            print_json({"files": None if imp is None else {"tests": {t: sorted(v) for t, v in imp.tests.items()},
                                                            "unknowns": imp.unknowns},
                        "symbols": sym_out})
        return 0
    if imp is not None:
        for t, types in sorted(imp.tests.items()):
            print(f"{t}  [{', '.join(sorted(types))}]")
        for u in imp.unknowns:
            print(f"UNKNOWN: {u}")
    for s in sym_out:
        sy = s["symbol"]
        print(f"== {sy.get('name')} ({sy.get('file')}:{sy.get('start', '?')}-{sy.get('end', '?')}): {s['summary']}")
        for c in s["callers"]:
            print(f"  caller  {c['file']}:{c['line']}" + (f"  in {c['symbol']}" if c.get("symbol") else ""))
        for t, ev in s["tests"].items():
            print(f"  test    {t}  [{', '.join(ev)}]")
        for u in s["unknowns"]:
            print(f"  UNKNOWN: {u}")
    return 0
