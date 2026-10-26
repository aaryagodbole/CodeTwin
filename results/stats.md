# Statistics (119 test commits, 101 with affected tests)

## 95% bootstrap CIs (mean [low, high])
- NameMatch: recall 0.492 [0.424, 0.563]; safe 0.378 [0.294, 0.462]; time_red 0.712 [0.656, 0.763]
- StaticImport: recall 1.000 [1.000, 1.000]; safe 1.000 [1.000, 1.000]; time_red 0.174 [0.118, 0.236]
- CoverageFile: recall 1.000 [1.000, 1.000]; safe 1.000 [1.000, 1.000]; time_red 0.369 [0.303, 0.438]
- CoverageLine: recall 0.953 [0.915, 0.984]; safe 0.933 [0.882, 0.975]; time_red 0.491 [0.422, 0.559]
- Hybrid(Static+CovFile): recall 1.000 [1.000, 1.000]; safe 1.000 [1.000, 1.000]; time_red 0.171 [0.114, 0.232]
- CRC@0.1: recall 0.989 [0.974, 1.000]; safe 0.975 [0.941, 1.000]; time_red 0.391 [0.324, 0.460]
- CRC@0.2: recall 0.968 [0.939, 0.992]; safe 0.941 [0.899, 0.983]; time_red 0.462 [0.394, 0.532]
- CRC+abstain@0.1: recall 1.000 [1.000, 1.000]; safe 1.000 [1.000, 1.000]; time_red 0.051 [0.018, 0.090]
- CodeTwin@0.1: recall 0.571 [0.511, 0.631]
- CoverageRanked@0.1: recall 0.568 [0.508, 0.627]
- Random@0.1: recall 0.488 [0.426, 0.551]
- CodeTwin@0.25: recall 0.724 [0.672, 0.775]
- CoverageRanked@0.25: recall 0.721 [0.669, 0.771]
- Random@0.25: recall 0.639 [0.586, 0.692]
- CodeTwin@0.5: recall 0.824 [0.783, 0.864]
- CoverageRanked@0.5: recall 0.821 [0.779, 0.860]
- Random@0.5: recall 0.787 [0.745, 0.827]

## Paired tests
- recall CodeTwin vs CoverageRanked @0.1: {'n': 101, 'nonzero': 1, 'p': 0.31731050786291415, 'mean_diff': 0.0024752475247524753}
- recall CodeTwin vs Random @0.1: {'n': 101, 'nonzero': 69, 'p': 1.1933291037091322e-10, 'mean_diff': 0.08266366977002558}
- recall CodeTwin vs CoverageRanked @0.25: {'n': 101, 'nonzero': 2, 'p': 0.17971249487899976, 'mean_diff': 0.0028052805280528053}
- recall CodeTwin vs Random @0.25: {'n': 101, 'nonzero': 70, 'p': 3.4548056297537734e-10, 'mean_diff': 0.08488863402469281}
- recall CodeTwin vs CoverageRanked @0.5: {'n': 101, 'nonzero': 3, 'p': 0.10880943004054568, 'mean_diff': 0.003187818781878187}
- recall CodeTwin vs Random @0.5: {'n': 101, 'nonzero': 52, 'p': 3.7634120809636093e-06, 'mean_diff': 0.0375738616488377}
- safe CRC@0.1 vs CoverageLine (McNemar): {'a_only_safe': 5, 'b_only_safe': 0, 'p': 0.0625}
- time_red CRC@0.1 vs CoverageLine: {'n': 119, 'nonzero': 40, 'p': 3.569388204466033e-08, 'mean_diff': -0.10039492500990176}
- safe CRC@0.1 vs CoverageFile (McNemar): {'a_only_safe': 0, 'b_only_safe': 3, 'p': 0.25}
- time_red CRC@0.1 vs CoverageFile: {'n': 119, 'nonzero': 15, 'p': 0.0006549583433856954, 'mean_diff': 0.021357534512473474}

## CRC alpha=0.10 misses (3)
- {"project": "dateutil", "sha": "21b6862a1e", "date": "2026-10-21", "subject": "Allow pickling and deepcopy of cached recurrence rules (#1600)", "changed": ["src/dateutil/rrule.py"], "affected": 4, "selected": 3, "missed": [{"test": "tests/test_tz.py", "p": 0.184, "cov_line": 0, "cov_file": 1, "static_inv_dist": 0.3333333333333333, "name_match": 0}], "lambda": 0.195, "triggers_fired": ["dynamic_call", "untested_change", "module_level_change"]}
- {"project": "itsdangerous", "sha": "0e13d6613a", "date": "2021-10-06", "subject": "Merge branch '2.0.x'", "changed": ["src/itsdangerous/encoding.py", "src/itsdangerous/jws.py", "src/itsdangerous/serializer.py", "src/itsdangerous/url_safe.py"], "affected": 4, "selected": 2, "missed": [{"test": "tests/test_itsdangerous/test_serializer.py", "p": 0.382, "cov_line": 0, "cov_file": 1, "static_inv_dist": 1.0, "name_match": 1}, {"test": "tests/test_itsdangerous/test_timed.py", "p": 0.247, "cov_line": 0, "cov_file": 1, "static_inv_dist": 0.5, "name_match": 0}], "lambda": 0.924, "triggers_fired": ["untested_change"]}
- {"project": "toolz", "sha": "a1e25cbd2c", "date": "2026-09-17", "subject": "Expose combined `__annotations__` on composed functions (#496) (#634)", "changed": ["toolz/functoolz.py"], "affected": 9, "selected": 6, "missed": [{"test": "toolz/tests/test_curried.py", "p": 0.244, "cov_line": 0, "cov_file": 1, "static_inv_dist": 0.5, "name_match": 0}, {"test": "toolz/tests/test_serialization.py", "p": 0.238, "cov_line": 0, "cov_file": 1, "static_inv_dist": 0.5, "name_match": 0}, {"test": "toolz/tests/test_signatures.py", "p": 0.245, "cov_line": 0, "cov_file": 1, "static_inv_dist": 0.5, "name_match": 0}], "lambda": 0.247, "triggers_fired": ["dynamic_call", "untested_change", "module_level_change"]}

## Unnecessary abstentions at alpha=0.10: 107 (first 10)
- {"project": "click", "sha": "94c191ca6c", "subject": "Add `@custom_version_option`, freeze `@version_option` (#3581)", "changed": ["src/click/__init__.py", "src/click/decorators.py"], "triggers_fired": ["untested_change", "module_level_change"], "time_saved_lost": 0.031}
- {"project": "click", "sha": "a44e9f05ed", "subject": "Update documentation following Colorama removal (#3671)", "changed": ["src/click/termui.py", "src/click/utils.py"], "triggers_fired": ["dynamic_call", "untested_change"], "time_saved_lost": 0.038}
- {"project": "click", "sha": "8a4ce84256", "subject": "Validate `style()` color arguments (#3677)", "changed": ["src/click/termui.py"], "triggers_fired": ["module_level_change"], "time_saved_lost": 0.219}
- {"project": "click", "sha": "8c1a0a7abb", "subject": "Strip all ANSI sequences (#3681)", "changed": ["src/click/_compat.py"], "triggers_fired": ["dynamic_call", "module_level_change"], "time_saved_lost": 0.034}
- {"project": "click", "sha": "b67832c216", "subject": "Fix parsing when a parameter is named `help` (#3678)", "changed": ["src/click/core.py"], "triggers_fired": ["module_level_change"], "time_saved_lost": 0.14}
- {"project": "click", "sha": "b551fe8571", "subject": "Streamline option flag management (#3641)", "changed": ["src/click/core.py"], "triggers_fired": ["module_level_change"], "time_saved_lost": 0.138}
- {"project": "click", "sha": "7df2f82305", "subject": "Add built-in PowerShell shell completion support (#3637)", "changed": ["src/click/shell_completion.py"], "triggers_fired": ["module_level_change"], "time_saved_lost": 0.972}
- {"project": "click", "sha": "333c28d79c", "subject": "Mark clearly functions private status. Deprecated Python 2 utilities. (#3695)", "changed": ["src/click/__init__.py", "src/click/_termui_impl.py", "src/click/core.py", "src/click/termui.py", "src/click/types.py", "src/click/utils.py"], "triggers_fired": ["dynamic_call", "module_level_change"], "time_saved_lost": 0.054}
- {"project": "click", "sha": "cfa01eeb78", "subject": "Deprecate `isolated_filesystem` and document its limits (#3704)", "changed": ["src/click/testing.py"], "triggers_fired": ["dynamic_call", "untested_change", "static_runtime_conflict"], "time_saved_lost": 0.433}
- {"project": "click", "sha": "5e906a8afb", "subject": "`click.prompt` typing clarifications / improvements (#3407)", "changed": ["src/click/termui.py", "src/click/types.py"], "triggers_fired": ["module_level_change"], "time_saved_lost": 0.062}
