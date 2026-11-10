[![progress-banner](https://backend.codecrafters.io/progress/shell/8b55343b-73a7-4140-8ca8-59d3c763587b)](https://app.codecrafters.io/users/codecrafters-bot?r=2qF)

This is a starting point for Python solutions to the
["Build Your Own Shell" Challenge](https://app.codecrafters.io/courses/shell/overview).

In this challenge, you'll build your own POSIX compliant shell that's capable of
interpreting shell commands, running external programs and builtin commands like
cd, pwd, echo and more. Along the way, you'll learn about shell command parsing,
REPLs, builtin commands, and more.

**Note**: If you're viewing this repo on GitHub, head over to
[codecrafters.io](https://codecrafters.io) to try the challenge.

## Myshell

A Unix shell written in Python. Built from scratch as a learning project. I started the project using codecrafters.io's "Build your own Shell" course and added more features after the course.

## Features

- **Pipelines** — `cmd1 | cmd2 | cmd3`
- **Redirections** — `>`, `>>`, `2>`, `2>>`, `<`
- **Logical operators** — `&&`, `||`, `;`
- **Background jobs** — `cmd &`, `jobs`, `fg`, `bg` (thread-based execution, no double-run)
- **Variables** — `name=value`, `$VAR`, `${VAR}`, `export`, `unset`
- **Command substitution** — `echo "today is $(date)"`, nested `$(...)` and quoted `"$(...)"` support
- **Tab completion** — commands and file paths
- **History** — persistent across sessions, `history`, `history -r/-w/-a`
- **Aliases** — `alias ll="ls -la"`, `unalias` (expanded in command substitution)
- **Source** — `source ~/.myshellrc` or `. ~/.myshellrc` (symlink-safe path validation)
- **Dynamic prompt** — configure via `PS1`
- **Exit codes** — `$?` after every command

## Security

- **Command injection prevention** — command substitution uses `parse_line` + `execute` instead of `shell=True`
- **Symlink-safe `source`** — uses `os.path.realpath` + `os.path.commonpath` to prevent directory traversal
- **Hardened `shell_quote`** — excludes dangerous characters (backticks, `$`, `!`, braces, etc.) from safe display
- **Thread-safe exit codes** — background jobs use a lock to prevent race conditions on `$?`

## Builtins

`cd`, `echo`, `pwd`, `type`, `exit`, `history`, `export`, `unset`,
`alias`, `unalias`, `source`, `.`, `jobs`, `fg`, `bg`

## Recent Improvements

- Fixed command substitution to properly handle nested `$(...)` and double-quoted `"$(...)"` contexts
- Background pipelines now execute via threads (no dummy subprocess, no double-execution)
- Alias expansion now works inside command substitution
- Job cleanup fixed — completed background jobs are removed from the job table
- Security hardening across command substitution, `source`, and job display

## History

History is stored in `~/.myshell_history` by default.
Override with the `HISTFILE` environment variable:
```bash
HISTFILE=~/my_history myshell
```

| Command | Effect |
|---|---|
| `history` | Show session history |
| `history 10` | Show last 10 entries |
| `history -w file` | Write history to file |
| `history -r file` | Read history from file |
| `history -a file` | Append new entries to file |
| `history -c` | Clear history |
