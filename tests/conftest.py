import subprocess
import textwrap
from pathlib import Path

import pytest


def sh(cwd, *cmd):
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def toy_repo(tmp_path: Path) -> Path:
    """A small git repository: package `shop` with two modules and two test files."""
    r = tmp_path / "toy"
    (r / "src" / "shop").mkdir(parents=True)
    (r / "tests").mkdir()
    (r / "src" / "shop" / "__init__.py").write_text("")
    (r / "src" / "shop" / "price.py").write_text(textwrap.dedent('''\
        def total(items):
            return sum(i["price"] for i in items)
        '''))
    (r / "src" / "shop" / "names.py").write_text(textwrap.dedent('''\
        def label(name):
            return name.title()
        '''))
    (r / "tests" / "test_price.py").write_text(textwrap.dedent('''\
        from shop.price import total
        def test_total():
            assert total([{"price": 2}, {"price": 3}]) == 5
        '''))
    (r / "tests" / "test_names.py").write_text(textwrap.dedent('''\
        from shop.names import label
        def test_label():
            assert label("ada") == "Ada"
        '''))
    sh(r, "git", "init", "-q")
    sh(r, "git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    sh(r, "git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init")
    return r
