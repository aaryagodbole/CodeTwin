"""One-off edit of paper/sncs/main.tex for the multi-language replication (study v4).
Text only; every new number is a macro filled by pilot/v4/paper_v4.py."""
from pathlib import Path

P = Path(__file__).resolve().parent / "sncs" / "main.tex"
t = P.read_text(encoding="utf-8")


def rep(old: str, new: str) -> None:
    global t
    assert t.count(old) == 1, (t.count(old), old[:80])
    t = t.replace(old, new)


# ---------------------------------------------------------------- preamble: generated macros
rep("\\raggedbottom\n\n\\begin{document}",
    "\\raggedbottom\n\n% Numbers of the multi-language replication, written by pilot/v4/paper_v4.py (do not edit by hand)\n"
    "%% v4-macros: begin\n%% v4-macros: end\n\n\\begin{document}")

# ---------------------------------------------------------------- title
rep("with Abstention---A Survey and an Empirical Study on Python Projects}",
    "with Abstention---A Survey and a Multi-Language Empirical Study}")

# ---------------------------------------------------------------- abstract
rep("We evaluated a Python prototype on 681 changes from 8 open-source projects with three ground truths, including 812 detected seeded faults.",
    "We evaluated the prototype on 681 changes from 8 open-source Python projects with three ground truths, including 812 detected seeded faults, and repeated the main analyses on \\vNchanges{} pull requests from \\vNrepos{} Go, Rust and JavaScript/TypeScript projects.")
rep("The learned ranking did not beat a coverage ranking.}",
    "The learned ranking did not beat a coverage ranking. In the other languages, adaptive calibration again kept the miss rate at or below each target (\\vAciFiveMiss\\%, \\vAciTenMiss\\% and \\vAciTwentyMiss\\%) and the change-level model again beat the product formula, but a once-fitted threshold did not drift and risk-based abstention caught only \\vTrigRiskFlag{} of \\vUnsafe{} unsafe changes.}")

# ---------------------------------------------------------------- introduction
rep("We start with Python. To answer the question we built CodeTwin AI, a Python prototype, and compared it with established baselines on the commit histories of open-source projects.",
    "We start with Python and then ask which findings carry over to other languages. To answer the question we built CodeTwin AI and compared it with established baselines on the commit histories of open-source Python projects, and on pull requests of Go, Rust and JavaScript/TypeScript projects.")
rep("Cross-repository links have been designed but not yet implemented.",
    "Cross-repository links have been designed but not yet implemented. The analysis reads only per-test coverage and static file facts, so other languages need only an adapter that provides them; the tool now has adapters for several languages, and we use them for the replication in Section~\\ref{sec:rq6}.")
rep("    \\item A replication package archived on Zenodo,",
    "    \\item A replication on \\vNtest{} test changes from pull requests of \\vNrepos{} Go, Rust and JavaScript/TypeScript projects, which shows which findings hold beyond Python and which do not (Section~\\ref{sec:rq6}).\n    \\item A replication package archived on Zenodo,")
rep("We make five contributions.", "We make six contributions.")

# ---------------------------------------------------------------- related work
rep("selective risk control and a conformal test-selection prototype) are discussed in the subsections below; they are not part of the survey table.",
    "selective risk control and a conformal test-selection prototype), to multi-language selection and to recent work on tests for coding agents are discussed in the subsections below; they are not part of the survey table.")
rep("How well each technique works depends on its dependency model, the languages it supports",
    "Selection across languages has two lines. Elsner et al.\\ trace system calls to collect file-level dependencies of each test across Java and C/C++ and select by checksums of those files~\\cite{elsner2022multilang}; BinaryRTS extends this to C++ binaries through dynamic binary instrumentation~\\cite{elsner2023binaryrts}. BabelRTS is static: language-specific patterns and actions find file dependencies for many languages and their combinations~\\cite{maurina2025babelrts}. Both lines select tests; neither estimates the risk that a selection leaves. Our language adapters follow BabelRTS's idea of a small per-language description, and the risk layer above them is the same for every language. How well each technique works depends on its dependency model, the languages it supports")
rep("Machine learning helps to prioritise and generate tests, but its confidence is an average,",
    "Elsner et al.\\ found that simple heuristics built from readily available information were competitive with machine-learned models for test optimisation in CI~\\cite{elsner2021readily}. Machine learning helps to prioritise and generate tests, but its confidence is an average,")
rep("The map carries no calibrated confidence, though, and nothing ever tells the agent to stop.",
    "The map carries no calibrated confidence, though, and nothing ever tells the agent to stop. Dipongkor et al.\\ measured the coverage of agent-written pull requests and found that many changed lines were not executed by any test~\\cite{dipongkor2026agentic}. ExecCritic and GTDD give agents tests that must fail on the code before the fix~\\cite{tao2026execcritic,kato2026gtdd}, the same rule that our self-confirming test analysis uses as evidence.")

# ---------------------------------------------------------------- implementation
rep("\\section{Implementation}\\label{sec:impl}\n% =====================================================================\n",
    "\\section{Implementation}\\label{sec:impl}\n% =====================================================================\n")
rep("A fourth script (304 lines) computes the change-level analyses",
    "A fourth script (304 lines) computes the change-level analyses")
IMPL_V4 = (
    "\n\nFor the replication in other languages (Section~\\ref{sec:v4setup}), the CodeTwin AI tool provides each language through an adapter. "
    "An adapter finds source and test files, extracts imports with tree-sitter grammars and resolves them to project files, and runs one test file at a time with the language's own runner and coverage tool: "
    "\\texttt{go test} with Go's cover profiles, \\texttt{cargo llvm-cov}, Jest, Vitest or Mocha with c8, and Maven or Gradle with JaCoCo. "
    "Coverage reports in LCOV, Go, JaCoCo, Cobertura and Clover formats are read into the same per-test record as the Python runs. "
    "The collection ran inside the benchmark's Docker images on GitHub Actions, one job per shard of pull requests, and the same analysis script as in the Python study was applied to the result, "
    "with three changes: source files are recognised by the language of the project, the static graph uses the adapters' file dependencies, and the co-change history is stored per pull request.")
rep("\\section{Experimental Setup}\\label{sec:setup}", IMPL_V4.lstrip("\n") + "\n\n% =====================================================================\n\\section{Experimental Setup}\\label{sec:setup}")

# ---------------------------------------------------------------- research questions
rep("We answer the research question in the Introduction through five research questions.",
    "We answer the research question in the Introduction through six research questions.")
rep("RQ5 and the parts of RQ2 and RQ3 on $q(c)$ are exploratory and were added after the main study.",
    "RQ5, RQ6 and the parts of RQ2 and RQ3 on $q(c)$ are exploratory and were added after the main study.")
rep("\\subsection{Subject Projects}",
    "\\textbf{RQ6 (other languages).} Do the main findings of RQ1 to RQ3 hold for projects in Go, Rust and JavaScript/TypeScript?\n\n\\subsection{Subject Projects}")

# ---------------------------------------------------------------- v4 setup subsection (before Results)
SETUP_V4 = r"""\subsection{Multi-Language Replication}\label{sec:v4setup}
For RQ6 we used Multi-SWE-bench, which provides real pull requests of open-source projects in seven languages, each with a Docker image that builds the project and runs its tests~\cite{zan2025multiswebench}. Each instance holds the base commit, the pull request's code change and its test change. We selected 18 repositories with test runners our adapters support and up to 24 pull requests each. For every pull request we ran the tests on the base commit with per-test coverage, applied the pull request, and ran again. To keep the runs affordable we used a deterministic sample of 30 to 50 test files per project, always including the files the pull request changes, and on the new version we reran only the test files whose base coverage reached a changed file, plus the pull request's tests; the others keep their base record. The coverage ground truth is therefore the same as in Section~\ref{sec:gt}, with one consequence: file coverage is safe on every change by construction and cannot be compared with the other techniques here. The benchmark has no seeded faults, so RQ4 and RQ5 are not repeated. Changes are ordered by the date of their base commit.

Because each repository has at most 24 usable pull requests, we pooled the repositories of one language into one project for calibration, giving three languages: Go (\vReposGo{} repositories, \vChangesGo{} changes), Rust (\vReposRust{}, \vChangesRust{}) and JavaScript/TypeScript (\vReposJSTS{}, \vChangesJSTS{}), \vNchanges{} changes in total, of which \vNtest{} are test changes. The protocol is that of Section~\ref{sec:setup}: the risk model of each language is trained on the other two languages, the first 40\% of its changes calibrate, and the same targets, budgets and ACI step are used. Java gave only \vJavaChanges{} usable changes from \vJavaRepos{} repositories, fewer than the \vMinChanges{} we required: the images of the other Java repositories could not build the project, because parent build files they depend on are no longer published. We report Java separately and leave it out of the pooled results."""
rep("% =====================================================================\n\n\\begin{figure}[htbp]\n\\centering\n\\resizebox{\\linewidth}{!}{%",
    SETUP_V4 + "\n\n% =====================================================================\n\n\\begin{figure}[htbp]\n\\centering\n\\resizebox{\\linewidth}{!}{%")

# ---------------------------------------------------------------- RQ6 results (before Ablation)
RQ6 = r"""\subsection{RQ6: Other Languages}\label{sec:rq6}
Table~\ref{tab:v4} repeats the main comparisons on the \vNtest{} test changes of the Go, Rust and JavaScript/TypeScript projects.

%% v4-table: begin
%% v4-table: end

\emph{Calibration.} Adaptive calibration again held the pooled miss rate at or below each target: \vAciFiveMiss\%, \vAciTenMiss\% and \vAciTwentyMiss\% for targets of 5\%, 10\% and 20\%. At $\alpha=0.10$ this held in every language (\vAciTenMissGo\%, \vAciTenMissRust\% and \vAciTenMissJSTS\%); at $\alpha=0.05$ Go missed on \vAciFiveMissGo\% of its \vTestGo{} test changes. Unlike on the Python history projects, the threshold fitted once on the calibration changes did not drift: at $\alpha=0.10$ it missed on \vCrcStaticMiss\% of later changes, against 17.5\% in Python. The drift we saw in Python is therefore not a general property of commit histories; whether it occurs depends on the project, and adaptive calibration is a safe default in both cases.

\emph{Baselines.} As in Python, line coverage of the old version was unsafe on some changes (\vLineMiss\%, \vUnsafe{} of \vNtest{}). Static import selection was unsafe on \vStaticMiss\% of changes, mostly in Rust (\vStaticMissRust\%) and JavaScript/TypeScript (\vStaticMissJSTS\%), where our adapters resolve only part of the module system (for example Rust \texttt{mod} paths and re-exports through index files). This measures our adapters, not static selection in general. Name matching missed on \vNameMiss\% of changes.

\emph{Abstention.} This finding did not replicate. Of the \vUnsafe{} changes on which line coverage was unsafe, the risk rule $r(c)>\alpha$ flagged only \vTrigRiskFlag{} (Go \vTrigRiskFlagGo{} of \vUnsafeGo{}, Rust \vTrigRiskFlagRust{} of \vUnsafeRust{}, JavaScript/TypeScript \vTrigRiskFlagJSTS{} of \vUnsafeJSTS{}), while it fired on \vTrigRiskSafePct\% of the safe changes. The line-level triggers, which flagged 7 of 31 unsafe changes in Python, flagged \vTrigLineFlag{} of \vUnsafe{} here, but they fired on \vTrigLineSafePct\% of the safe changes; the file-level triggers flagged \vTrigFileFlag{} and fired on \vTrigFileSafePct\%. The per-test product formula behind $r(c)$ was poorly calibrated in both directions: it predicted a mean miss probability of \vProdPredictedRust\% on Rust, where \vQObservedRust\% of selections missed, and \vProdPredictedJSTS\% on JavaScript/TypeScript, where \vQObservedJSTS\% did. With file coverage as the broader run, risk-based abstention on top of ACI at $\alpha=0.10$ missed on \vRiskAbMiss\% of changes and saved \vRiskAbSaved\% of test time; abstaining on line-level triggers missed on \vLineAbMiss\% and saved \vLineAbSaved\%. With only \vUnsafe{} unsafe changes, these counts are imprecise, but they do not support H3 for risk-based abstention outside Python.

\emph{Change-level risk.} The change-level model $q(c)$, trained on the other languages, predicted a mean miss probability of \vQPredicted\% for the ACI selections at $\alpha=0.10$, where \vQObserved\% missed; the product formula predicted \vProdPredicted\%. Its Brier score (\vQBrier) was below that of a constant forecast (\vConstBrier), and that of the product formula (\vProdBrier) was above it, as in Python. With a 5\% target on top of ACI at $\alpha_{\mathit{sel}}=0.10$, the $q$-rule abstained on \vQRuleAbst\% of changes and missed on \vQRuleMissProc\% of those that proceeded (the rule on $r(c)$: \vRRuleAbst\% and \vRRuleMissProc\%). Pooled, both stayed below 5\%, but not in \vQRuleWorstLang{} (\vQRuleWorst\%). The online selective rule missed on \vSelRuleMissProc\% of the changes that proceeded.

\emph{Ranking.} At the 25\% budget the learned ranking found \vBudgetLearned{} of the affected tests and the coverage ranking \vBudgetCoverage{} ($p=\vBudgetP$), against \vBudgetRandom{} for random order, so the learned ranking again did not beat a coverage ranking.

\emph{Java.} The \vJavaTest{} Java test changes are too few to calibrate on: with \vJavaCalib{} calibration changes no threshold is feasible, and CodeTwin AI then runs every test, as designed. Line coverage was safe on all of them and saved \vJavaLineSaved\% of test time.

\textbf{Answer to RQ6:} on Go, Rust and JavaScript/TypeScript, adaptive calibration again kept the miss rate at or below the target, a change-level risk model was again better calibrated than the product formula, line coverage of the old version again missed tests, and the learned ranking again did not beat a coverage ranking. Two Python findings did not carry over: a once-fitted threshold did not drift, and risk-based abstention on $r(c)$ caught few of the unsafe changes. The second weakens H3, which holds for Python only.

"""
rep("\\subsection{Ablation}\\label{sec:ablation}", RQ6 + "\\subsection{Ablation}\\label{sec:ablation}")

# ---------------------------------------------------------------- discussion
rep("the weakness of line-level selection agrees with the Python study of Kauhanen et al.~\\cite{kauhanen2021python}.",
    "the weakness of line-level selection agrees with the Python study of Kauhanen et al.~\\cite{kauhanen2021python}. Multi-language selection itself is established~\\cite{elsner2022multilang,maurina2025babelrts}; our replication adds that calibration and its adaptive variant carry over to other languages, while the per-test product formula and the abstention rule built on it do not.")
rep("co-changed tests have served as relevance labels~\\cite{jungwirth2026pto},",
    "co-changed tests have served as relevance labels~\\cite{jungwirth2026pto}, selection across languages exists in dynamic and static form~\\cite{elsner2022multilang,maurina2025babelrts},")
rep("Fourth, a guarantee that holds in the long run did not help on short histories: the online selective rule missed more often than a fixed rule on every group of projects.",
    "Fourth, a guarantee that holds in the long run did not help on short histories: the online selective rule missed more often than a fixed rule on every group of projects. Fifth, a result on one language is a hypothesis for the next: in Go, Rust and JavaScript/TypeScript, static calibration did not drift and risk-based abstention lost most of its value, so a deployment should check its abstention rule on the project's own history before relying on it.")

# ---------------------------------------------------------------- threats
rep("Larger systems, other languages and industrial code may behave differently.",
    "Larger systems and industrial code may behave differently. The replication in other languages has its own limits. Multi-SWE-bench selects pull requests that fix an issue and come with tests that fail before the fix, so its changes are not a random sample of commits. We used a sample of 30 to 50 test files per project and reran on the new version only the tests whose old coverage reached a changed file, so file coverage is safe there by construction. Each language pools several repositories into one calibration sequence, which mixes projects in time order; the pull requests are few per repository, and Java is represented by \\vJavaChanges{} changes only. The adapters' static imports are incomplete for some module systems, which affects the static baselines and features in those languages.")
rep("The history projects contribute different numbers of changes (from 30 to 150 test changes), so pooled results lean towards click.",
    "The history projects contribute different numbers of changes (from 30 to 150 test changes), so pooled results lean towards click. In the replication, only \\vUnsafe{} test changes were unsafe for line coverage, so the trigger counts of RQ6 have wide uncertainty.")

# ---------------------------------------------------------------- conclusion
rep("Nearly all tests that detect seeded faults lie inside the coverage ground truth, and on NameRTS's own commits, whether NameRTS or coverage-based selection came out ahead depended on the ground truth used.\n",
    "Nearly all tests that detect seeded faults lie inside the coverage ground truth, and on NameRTS's own commits, whether NameRTS or coverage-based selection came out ahead depended on the ground truth used. On \\vNtest{} test changes from Go, Rust and JavaScript/TypeScript pull requests, adaptive calibration again kept the miss rate at or below each target and the change-level model was again better calibrated than the product formula, but a once-fitted threshold did not drift there and risk-based abstention caught only \\vTrigRiskFlag{} of \\vUnsafe{} unsafe changes.\n")
rep("extending the language adapters beyond Python;",
    "repeating the study on more pull requests per language, including Java, with complete suites;")

# ---------------------------------------------------------------- data availability
rep("and the script that writes every number of this paper.\n",
    "and the script that writes every number of this paper. The scripts and data of the multi-language replication are on the branches \\texttt{study-v3} and \\texttt{study-v4-results} of \\url{https://github.com/aaryagodbole/CodeTwin} and will be added to the next version of the archive.\n")

P.write_text(t, encoding="utf-8")
print("ok")
