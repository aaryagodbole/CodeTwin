"""Java: JUnit through Maven (Surefire) or Gradle, coverage from JaCoCo XML, one test class per run.

Imports resolve to the files of the named class or package; classes of the same package need no import, so
a file also depends on same-package files whose class names it mentions. Reflection (`Class.forName`,
`getMethod`, `invoke`, ...), `ServiceLoader` and dynamic proxies are reported as dynamic. Static
initialiser blocks and static field initialisers count as load-time code.
"""
from __future__ import annotations

import posixpath
import re
from pathlib import Path

from ..spec import Runner, Spec
from ._util import leading_insert, txt

JACOCO = "org.jacoco:jacoco-maven-plugin:0.8.13"
PACKAGE = re.compile(r"^\s*package\s+([\w.]+)\s*;?", re.M)
REFLECT = {"forName", "getMethod", "getDeclaredMethod", "getMethods", "getDeclaredMethods", "invoke", "newInstance",
           "getField", "getDeclaredField", "loadClass", "getConstructor", "getDeclaredConstructor"}
DEFAULTS = {"boolean": "false", "char": "'\\0'", "byte": "0", "short": "0", "int": "0", "long": "0L", "float": "0f",
            "double": "0d"}


def imports(n, src: bytes) -> list[str] | None:
    if n.type == "import_declaration":
        named = [c for c in n.named_children if c.type in ("scoped_identifier", "identifier")]
        if not named:
            return None
        name = txt(named[0], src)
        return [name + ".*" if any(c.type == "asterisk" for c in n.named_children) else name]
    return None


def dynamic(n, src: bytes) -> str | None:
    if n.type == "method_invocation":
        name = n.child_by_field_name("name")
        nm = txt(name, src) if name is not None else ""
        if nm in REFLECT:
            return "reflection"
        obj = n.child_by_field_name("object")
        o = txt(obj, src) if obj is not None else ""
        if o == "ServiceLoader" and nm == "load":
            return "service-loader"
        if o == "Proxy" and nm == "newProxyInstance":
            return "proxy"
    return None


def names(n, src: bytes) -> str | None:
    if n.type in ("type_identifier", "identifier"):
        t = txt(n, src)
        return t if t[:1].isupper() else None
    return None


def prepare(idx) -> None:
    pkg_of: dict[str, str] = {}
    by_pkg: dict[str, list[str]] = {}
    by_type: dict[tuple[str, str], str] = {}
    for f in sorted(idx.files):
        try:
            head = (idx.root / f).read_text(encoding="utf-8", errors="replace")[:4000]
        except OSError:
            continue
        m = PACKAGE.search(head)
        pkg = m.group(1) if m else ""
        pkg_of[f] = pkg
        by_pkg.setdefault(pkg, []).append(f)
        by_type[(pkg, posixpath.splitext(posixpath.basename(f))[0])] = f
    idx.data.update(pkg_of=pkg_of, by_pkg=by_pkg, by_type=by_type)


def resolve(spec: str, from_file: str, idx) -> list[str]:
    if spec.endswith(".*"):
        pkg = spec[:-2]
        hit = idx.data["by_pkg"].get(pkg)
        if hit:
            return sorted(hit)
        spec = pkg                     # `import static a.b.C.*` names a class, not a package
    parts = spec.split(".")
    for k in range(len(parts) - 1, 0, -1):        # a.b.C, a.b.C.Inner, a.b.C.staticMember
        f = idx.data["by_type"].get((".".join(parts[:k]), parts[k]))
        if f:
            return [f]
    return []


def extra_deps(f: str, idx) -> list[str]:
    pkg = idx.data["pkg_of"].get(f)
    if pkg is None:
        return []
    by_type = idx.data["by_type"]
    return sorted({by_type[(pkg, n)] for n in idx.names.get(f, ()) if (pkg, n) in by_type})


def mutant(fn, src: bytes, path: str) -> tuple[int, int, str] | None:
    if fn.type != "method_declaration":
        return None                    # constructors and lambdas have no neutral early return
    body = fn.child_by_field_name("body")
    typ = fn.child_by_field_name("type")
    if body is None or typ is None:
        return None
    t = txt(typ, src)
    value = "" if t == "void" else " " + DEFAULTS.get(t, "null")
    # `if (true)` keeps the rest of the body reachable for javac
    return leading_insert(body, src, f"if (true) return{value};")


def load_time(root, src: bytes) -> set[int]:
    """Lines that run when a class is loaded: static initialiser blocks and initialisers of static fields."""
    out: set[int] = set()
    stack = [root]
    while stack:
        n = stack.pop()
        static_field = n.type == "field_declaration" and any(
            c.type == "modifiers" and "static" in txt(c, src).split() for c in n.children) and "=" in txt(n, src)
        if n.type == "static_initializer" or static_field:
            out.update(range(n.start_point[0] + 1, n.end_point[0] + 2))
            continue
        if n.type not in ("method_declaration", "constructor_declaration", "lambda_expression"):
            stack.extend(n.children)
    return out


def _vars(test: str, text: str, cwd: Path | None = None) -> dict:
    m = PACKAGE.search(text)
    cls = posixpath.splitext(posixpath.basename(test))[0]
    gradle = "./gradlew" if cwd is not None and (cwd / "gradlew").exists() else "gradle"
    return {"test_class": f"{m.group(1)}.{cls}" if m else cls, "gradle": gradle}


GRADLE_INIT = str(Path(__file__).with_name("_jacoco.gradle"))
MAVEN_FLAGS = ("-B -q -Dmaven.test.failure.ignore=true -DfailIfNoTests=false -Dsurefire.failIfNoSpecifiedTests=false "
               "-Djacoco.skip=false -Dtest={test_class}")
RUNNERS = [
    Runner("maven",
           f"mvn {MAVEN_FLAGS} -Djacoco.destFile={{cov_dir}}/jacoco.exec -Djacoco.dataFile={{cov_dir}}/jacoco.exec "
           f"{JACOCO}:prepare-agent surefire:test {JACOCO}:report",
           "jacoco", "./**/target/site/jacoco/jacoco.xml",       # the report goal has no output-directory property
           run_command=f"mvn {MAVEN_FLAGS} test",
           setup_command=f"mvn -B -q -DskipTests {JACOCO}:prepare-agent test-compile",
           build_command="mvn -B -q -DskipTests test-compile",
           result_glob="**/target/surefire-reports/TEST-{test_class}*.xml",
           detect=lambda root: (root / "pom.xml").exists(), vars=_vars, shares_build_dir=True),
    Runner("gradle",
           f"{{gradle}} -q --init-script {GRADLE_INIT} -Dcodetwin.covdir={{cov_dir}} test --tests {{test_class}}",
           "jacoco", "**/*.xml",
           run_command=f"{{gradle}} -q --init-script {GRADLE_INIT} test --tests {{test_class}}",
           setup_command="sh -c \"[ -x ./gradlew ] && ./gradlew -q testClasses || gradle -q testClasses\"",
           build_command="sh -c \"[ -x ./gradlew ] && ./gradlew -q testClasses || gradle -q testClasses\"",
           result_glob="**/build/test-results/test/TEST-{test_class}*.xml",
           detect=lambda root: (root / "build.gradle").exists() or (root / "build.gradle.kts").exists(), vars=_vars,
           shares_build_dir=True),
]

SPEC = Spec(
    name="java",
    grammars={".java": "java"},
    test_globs=["**/src/test/**/Test*.java", "**/src/test/**/*Test.java", "**/src/test/**/*Tests.java",
                "**/src/test/**/*TestCase.java"],
    markers=["pom.xml", "build.gradle", "build.gradle.kts"],
    source_dirs=["src/main/java", "src"],
    tests_dirs=["src/test/java", "src/test"],
    function_types={"method_declaration", "constructor_declaration", "lambda_expression"},
    decl_types={"package_declaration", "import_declaration", "field_declaration", "interface_declaration",
                "annotation_type_declaration", "module_declaration", "record_declaration", "constant_declaration",
                "enum_constant", "class_declaration", "enum_declaration"},
    load_time=load_time,
    imports=imports, dynamic=dynamic, names=names, prepare=prepare, resolve=resolve, extra_deps=extra_deps,
    mutant=mutant, runners=RUNNERS,
)
