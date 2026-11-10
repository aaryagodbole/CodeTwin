"""`codetwin serve`: read-only API (and optionally the built dashboard) on localhost."""
from __future__ import annotations

NAME, HELP, ORDER = "serve", "start the dashboard API on localhost (needs codetwin[server])", 70


def add_arguments(p) -> None:
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--static", help="directory of a built dashboard to serve at / (default: the one bundled in "
                                    "release packages, if any)")


def run(args) -> int:
    try:
        import uvicorn

        from ..server.app import create_app
    except ImportError:
        print('codetwin serve needs the server extra: pip install "codetwin[server]"')
        return 2
    from pathlib import Path

    static = args.static or (Path(__file__).resolve().parent.parent / "server" / "static")
    has_ui = Path(static).is_dir()
    where = f"dashboard on http://{args.host}:{args.port}/ and " if has_ui else ""
    print(f"CodeTwin: {where}API on http://{args.host}:{args.port}/api/docs", flush=True)
    uvicorn.run(create_app(args.root, static if has_ui else None), host=args.host, port=args.port, log_level="warning")
    return 0
