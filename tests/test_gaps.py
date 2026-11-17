"""Tests for the test_gaps report section."""
from __future__ import annotations

import json
import subprocess

from codetwin.cli import main


def test_new_function_appended_is_gap(toy_repo, capsys):
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])
    p = toy_repo / "src/shop/price.py"
    p.write_text(p.read_text() + "\ndef discount(price, percent):\n    return price * (1 - percent)\n")
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "select", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    gaps = out["extras"]["test_gaps"]
    assert "src/shop/price.py" in gaps["files"]
    info = gaps["files"]["src/shop/price.py"]
    assert "discount" in info["symbols"]
    assert len(info["lines"]) >= 2
    assert "ran under no test" in gaps["summary"]


def test_tested_line_edited_is_not_gap(toy_repo, capsys):
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])
    p = toy_repo / "src/shop/price.py"
    p.write_text(p.read_text().replace('sum(i["price"]', 'sum( i["price"]'))
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "select", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    gaps = out["extras"]["test_gaps"]
    assert gaps["files"] == {}
    assert gaps["summary"] == "no test gaps found"


def test_edited_comment_or_def_line_is_not_gap(toy_repo, capsys):
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])
    p = toy_repo / "src/shop/price.py"
    p.write_text(p.read_text().replace("def total(items):", "def total(items):  # sum prices"))
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "select", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    gaps = out["extras"]["test_gaps"]
    assert gaps["files"] == {}
    assert gaps["summary"] == "no test gaps found"


def test_new_file_all_code_lines_are_gaps(toy_repo, capsys):
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])
    new_file = toy_repo / "src/shop/tax.py"
    new_file.write_text("def tax(amount):\n    # 10 percent tax\n    return amount * 0.10\n")
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "select", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    gaps = out["extras"]["test_gaps"]
    assert "src/shop/tax.py" in gaps["files"]
    info = gaps["files"]["src/shop/tax.py"]
    assert info["lines"] == [1, 3]  # line 2 is a comment, skipped
    assert "tax" in info["symbols"]
    assert "2 of 3 changed lines in 1 file ran under no test" in gaps["summary"]


def _commit(repo, msg: str) -> None:
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-am", msg], cwd=repo, check=True, capture_output=True)


def test_docstring_edit_is_not_gap(toy_repo, capsys):
    p = toy_repo / "src/shop/price.py"
    p.write_text('def total(items):\n    """Calculate total price."""\n    return sum(i["price"] for i in items)\n')
    _commit(toy_repo, "add docstring")
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])
    p.write_text('def total(items):\n    """Calculate total price of all items."""\n    return sum(i["price"] for i in items)\n')
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "select", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    gaps = out["extras"]["test_gaps"]
    assert gaps["files"] == {}
    assert gaps["summary"] == "no test gaps found"


def test_untested_branch_edit_and_addition_are_gaps(toy_repo, capsys):
    p = toy_repo / "src/shop/price.py"
    p.write_text(
        'def total(items):\n'
        '    t = sum(i["price"] for i in items)\n'
        '    if t > 1000:\n'
        '        return t - 10\n'
        '    return t\n'
    )
    _commit(toy_repo, "add untested branch")
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])
    # Edit the untested branch and add a print below it
    p.write_text(
        'def total(items):\n'
        '    t = sum(i["price"] for i in items)\n'
        '    if t > 1000:\n'
        '        print(t)\n'
        '        return t - 20\n'
        '    return t\n'
    )
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "select", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    gaps = out["extras"]["test_gaps"]
    assert "src/shop/price.py" in gaps["files"]
    info = gaps["files"]["src/shop/price.py"]
    # Both lines 4 and 5 in the new file should be gaps
    assert 4 in info["lines"] and 5 in info["lines"]
    assert "total" in info["symbols"]


def test_mixed_coverage_hunk_reports_gap(toy_repo, capsys):
    p = toy_repo / "src/shop/price.py"
    p.write_text(
        'def total(items):\n'
        '    t = sum(i["price"] for i in items)\n'
        '    if t > 1000:\n'
        '        return t - 10\n'
        '    return t\n'
    )
    _commit(toy_repo, "add untested branch")
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])
    # Modify condition (covered line 3) and add a statement to untested return (line 4)
    # Hunk has (3, 2, 3, 3): line 3 is covered, line 4 was untested
    p.write_text(
        'def total(items):\n'
        '    t = sum(i["price"] for i in items)\n'
        '    if t >= 1000:\n'
        '        print(t)\n'
        '        return t - 20\n'
        '    return t\n'
    )
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "select", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    gaps = out["extras"]["test_gaps"]
    assert "src/shop/price.py" in gaps["files"]
    info = gaps["files"]["src/shop/price.py"]
    # Line 3 is edit of covered line -> not gap
    # Lines 4 and 5 in untested branch -> both are gaps
    assert 3 not in info["lines"]
    assert 4 in info["lines"] and 5 in info["lines"]


def test_docstring_sharing_line_with_code_is_not_excluded(toy_repo, capsys):
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])
    new_file = toy_repo / "src/shop/tax.py"
    new_file.write_text('def tax(a): """Tax."""; return a * 0.1\n')
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "select", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    gaps = out["extras"]["test_gaps"]
    assert "src/shop/tax.py" in gaps["files"]
    info = gaps["files"]["src/shop/tax.py"]
    assert 1 in info["lines"]


def test_deletion_of_untested_branch(toy_repo, capsys):
    p = toy_repo / "src/shop/price.py"
    p.write_text(
        'def total(items):\n'
        '    t = sum(i["price"] for i in items)\n'
        '    if t > 1000:\n'
        '        return t - 10\n'
        '    return t\n'
    )
    _commit(toy_repo, "add untested branch")
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])
    # Delete the untested branch
    p.write_text(
        'def total(items):\n'
        '    t = sum(i["price"] for i in items)\n'
        '    return t\n'
    )
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "select", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    gaps = out["extras"]["test_gaps"]
    assert gaps["files"] == {}
    # A source file did change (lines were only deleted), so it must not say "no source files changed"
    assert gaps["summary"] == "no test gaps found"


UNTESTED_BRANCH = (
    'def total(items):\n'
    '    t = sum(i["price"] for i in items)\n'
    '    if t > 1000:\n'
    '        t = t - 10\n'
    '    return t\n'
)


def _select_gaps(repo, capsys) -> dict:
    capsys.readouterr()
    assert main(["-C", str(repo), "select", "--json"]) == 0
    return json.loads(capsys.readouterr().out)["extras"]["test_gaps"]


def test_line_inserted_after_untested_block_is_not_gap(toy_repo, capsys):
    p = toy_repo / "src/shop/price.py"
    p.write_text(UNTESTED_BRANCH)
    _commit(toy_repo, "add untested branch")
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])
    # Inserted at function level after the if block: it runs on every call, and the test calls total()
    p.write_text(UNTESTED_BRANCH.replace("    return t\n", "    t = round(t, 2)\n    return t\n"))
    gaps = _select_gaps(toy_repo, capsys)
    assert gaps["files"] == {}
    assert gaps["summary"] == "no test gaps found"


def test_line_inserted_at_end_of_untested_branch_is_gap(toy_repo, capsys):
    p = toy_repo / "src/shop/price.py"
    p.write_text(UNTESTED_BRANCH)
    _commit(toy_repo, "add untested branch")
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])
    # Inserted inside the branch that no test enters (t > 1000)
    p.write_text(UNTESTED_BRANCH.replace("        t = t - 10\n", "        t = t - 10\n        t = t * 2\n"))
    gaps = _select_gaps(toy_repo, capsys)
    assert gaps["files"]["src/shop/price.py"]["lines"] == [5]


def test_line_appended_after_untested_body_at_end_of_file_is_not_gap(toy_repo, capsys):
    # The tested function ends with an untested if body, and nothing follows it in the file
    p = toy_repo / "src/shop/price.py"
    p.write_text(p.read_text() + "\n\ndef mark(seen):\n    seen.append(1)\n    if len(seen) > 1000:\n        seen.clear()\n")
    (toy_repo / "tests/test_mark.py").write_text(
        "from shop.price import mark\n\n\ndef test_mark():\n    seen = []\n    mark(seen)\n    assert seen == [1]\n")
    subprocess.run(["git", "add", "-A"], cwd=toy_repo, check=True, capture_output=True)
    _commit(toy_repo, "add mark")
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])
    # Appended at function level after the untested body: it runs whenever mark() runs
    p.write_text(p.read_text() + "    seen.append(2)\n")
    gaps = _select_gaps(toy_repo, capsys)
    assert gaps["files"] == {}


def test_inserted_branch_body_is_gap(toy_repo, capsys):
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])
    p = toy_repo / "src/shop/price.py"
    old = p.read_text()
    ret = next(line for line in old.splitlines() if line.strip().startswith("return"))
    # A new branch before the tested return: the condition runs, its body has never run
    p.write_text(old.replace(ret + "\n", "    if not items:\n        return 0\n" + ret + "\n", 1))
    new_lines = p.read_text().splitlines()
    body = new_lines.index("        return 0") + 1
    gaps = _select_gaps(toy_repo, capsys)
    assert gaps["files"]["src/shop/price.py"]["lines"] == [body]
