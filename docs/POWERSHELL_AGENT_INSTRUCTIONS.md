# PowerShell Agent Instructions

Use explicit literal paths and native cmdlets for file operations. Resolve targets before a recursive move or delete, keep temporary work beneath `tmp/`, and prefer non-destructive inspection. Do not compose path discovery in one shell with destructive operations in another. Avoid repurposing common environment variables.

For control flow, collect `foreach`, `if`, and `try/catch` output into a variable before piping or formatting it. Check `$LASTEXITCODE` immediately after external commands. Use `rg` for text/file discovery, pass structured arguments instead of interpolated shell fragments, and keep output compact enough to audit. Do not use `git reset --hard`, force updates, or branch-changing recovery commands unless explicitly authorized.
