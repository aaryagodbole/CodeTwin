# CodeTwin AI – VS Code extension (skeleton)

Commands: *Select tests for my change*, *Show impact of this file* (also in the editor context menu),
*Record evidence*, *Explain last decision*. The status bar shows the last decision and residual risk.

The extension calls the `codetwin` CLI (`pip install -e .` in the repository root) and never re-implements
analysis. Develop: `npm install && npm run compile`, then press F5 in VS Code to start an Extension
Development Host.
