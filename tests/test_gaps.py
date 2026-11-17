"""Tests for the test_gaps report section."""
from __future__ import annotations

import json

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
    assert "0 of 1 changed lines" in gaps["summary"]


def test_edited_comment_or_def_line_is_not_gap(toy_repo, capsys):
    main(["-C", str(toy_repo), "init"])
    main(["-C", str(toy_repo), "record"])
    p = toy_repo / "src/shop/price.py"
    # Edit the def header line
    p.write_text(p.read_text().replace("def total(items):", "def total(items):  # sum prices"))
    capsys.readouterr()
    assert main(["-C", str(toy_repo), "select", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    gaps = out["extras"]["test_gaps"]
    assert gaps["files"] == {}
    assert "0 of 1 changed lines" in gaps["summary"]


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
