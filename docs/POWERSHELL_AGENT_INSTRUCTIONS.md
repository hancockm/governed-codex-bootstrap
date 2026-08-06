# PowerShell Agent Instructions

PowerShell is not Bash. Use this guide for nontrivial repository inspection,
verification, cleanup, and local orchestration on Windows.

## Core Rule

Use pipelines for cmdlet streams. Assign control-flow output to a variable
before piping it. Do not pipe directly from `foreach`, `if`, `try/catch`,
`switch`, or function-declaration blocks.

Unsafe:

```powershell
foreach ($item in $items) {
  [pscustomobject]@{ Name = $item.Name }
} | Format-Table -AutoSize
```

Safe:

```powershell
$rows = foreach ($item in $items) {
  [pscustomobject]@{ Name = $item.Name }
}

$rows | Format-Table -AutoSize
```

The unsafe form may produce `An empty pipe element is not allowed` because the
control-flow block is a statement rather than a pipeline expression.

## Statement Blocks And Output

PowerShell statements may emit objects without being safe pipeline heads.
Use an explicit collection:

```powershell
$results = @()
foreach ($path in $paths) {
  $results += [pscustomobject]@{
    Path = $path
    Exists = Test-Path -LiteralPath $path
  }
}
$results | Sort-Object Path | Format-Table -AutoSize
```

When input is already pipeline-shaped, use `ForEach-Object`:

```powershell
$results = Get-ChildItem -LiteralPath $root -Directory |
  ForEach-Object {
    [pscustomobject]@{ Name = $_.Name; Path = $_.FullName }
  }
```

## Upstream Syntax

Do not rely on shorthand such as `@{u}` when inspecting Git upstreams. The
token can be parsed as a hashtable or malformed expression depending on
quoting/context. Use explicit revision syntax:

```powershell
git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}'
git rev-list --left-right --count 'HEAD...origin/master'
```

Pass Git revision expressions as quoted literal arguments. Split branch,
upstream, and divergence checks into separate commands when a combined command
becomes difficult to review.

## Separate Inspection, Mutation, And Verification

Do not combine discovery, deletion, and verification into one clever pipeline.

```powershell
# Inspect.
$targets = Get-ChildItem -LiteralPath $root -Directory |
  Where-Object { $_.Name -like '.pytest-*' } |
  Select-Object -ExpandProperty FullName
$targets
```

```powershell
# Mutate one exact approved path.
Remove-Item -LiteralPath 'C:\path\to\exact\target' -Recurse -Force
```

```powershell
# Verify.
Test-Path -LiteralPath 'C:\path\to\exact\target'
```

Resolve recursive deletion or move targets first and verify containment inside
the intended repository/worktree root. Do not use unresolved variables, globs,
or command substitution as destructive targets.

## Quoting And Paths

- Use `-LiteralPath` for filesystem paths.
- Prefer single quotes for literal Windows paths.
- Use `Join-Path` for constructed paths.
- Print resolved targets before destructive operations.
- Avoid backtick line continuation; use variables or argument arrays.
- Do not interpolate untrusted `$`, backticks, or parentheses into commands.
- Do not repurpose `$HOME`, `$home`, or other system variables.

```powershell
$repositoryRoot = 'C:\path\to\repository'
$target = Join-Path $repositoryRoot 'tmp\task-id'
$resolved = [System.IO.Path]::GetFullPath($target)
$resolved
```

## Formatting Is Display-Only

`Format-Table`, `Format-List`, and other `Format-*` cmdlets create formatting
objects. Use them only at the end of a display pipeline.

```powershell
$rows = Get-ChildItem -LiteralPath $root -Directory |
  Select-Object Name, FullName
$rows | Format-Table -AutoSize
```

Do not pass formatted output into filtering or business logic.

## Exit Codes And Inspection Failures

Capture native-command exit codes before interpreting output:

```powershell
git status --porcelain=v1 --untracked-files=all --ignore-submodules=all
$statusExit = $LASTEXITCODE
if ($statusExit -ne 0) {
  throw "Git status inspection failed with exit code $statusExit"
}
```

An empty output stream with a nonzero exit is failure, not clean state.

## Background Processes

When launching a noninteractive helper, hide its window unless the user needs
to interact with it:

```powershell
Start-Process -FilePath $program -ArgumentList $arguments -WindowStyle Hidden
```

Record the process identity and provide bounded stop/cleanup behavior.

## When To Use A Project Tool

Prefer a repository Python tool when logic needs nested data, deterministic
JSON, complex grouping, cross-platform behavior, or substantial recovery.
Do not replace a mature checked-in tool with an ad hoc PowerShell parser.

## Checklist

1. Are control-flow blocks assigned before piping?
2. Are Git revisions and upstream syntax explicit and quoted?
3. Are inspection, mutation, and verification separate?
4. Are exact paths passed with `-LiteralPath`?
5. Are destructive targets resolved inside the intended root?
6. Are `Format-*` cmdlets display-only?
7. Is every native-command exit code checked before interpretation?
8. Would an existing repository tool be safer?
