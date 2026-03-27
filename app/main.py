import sys, shutil, os, subprocess, shlex, readline, glob

def get_path_executables():
    exes = set()
    path_env = os.environ.get("PATH", "")

    pathext = os.environ.get("PATHEXT")
    allowed_extensions = None
    if pathext:
        allowed_extensions = {e.lower() for e in pathext.split(";") if e}

    for folder in path_env.split(os.pathsep):
        if not folder:
            continue
        try:
            for entry in os.listdir(folder):
                full = os.path.join(folder, entry)
                if not os.path.isfile(full):
                    continue

                if allowed_extensions is not None:
                    root, ext = os.path.splitext(entry)
                    if ext.lower() in allowed_extensions:
                        # store both root and full entry; helps "extension complete"
                        exes.add(root)
                        exes.add(entry)
                else:
                    if os.access(full, os.X_OK):
                        exes.add(entry)
        except OSError:
            continue
    return exes

def cd_function(user_inputs):
    if not user_inputs:
        os.chdir(os.path.expanduser("~"))
        return

    target = os.path.expanduser(user_inputs[0])

    if not os.path.isdir(target):
        sys.stderr.write(f"cd: {target}: No such file or directory\n")
        return

    os.chdir(target)

def custom_user_inputs(user_inputs):
    for user_input in user_inputs:
        if user_input in builtin_functions:
            sys.stdout.write(f"{user_input} is a shell builtin\n")
        elif path := shutil.which(user_input):
            sys.stdout.write(f"{user_input} is {path}\n")
        else:
            sys.stdout.write(f"{user_input}: not found\n")

builtin_functions = {
    "type": lambda user_inputs: custom_user_inputs(user_inputs),
    "exit": lambda user_inputs: sys.exit(0),
    "echo": lambda args: sys.stdout.write(" ".join(args) + "\n"),
    "pwd": lambda user_inputs: sys.stdout.write(f"{os.getcwd()}\n"),
    "cd": cd_function,
}

def split_redirection(tokens, ops):
    for op, mode in ops:
        if op in tokens:
            pos = tokens.index(op)
            if pos == len(tokens) - 1:
                sys.stderr.write(f"syntax error: expected file after {op}\n")
                return None, None, None
            cleaned = tokens[:pos]
            file = tokens[pos+1]
            return cleaned, file, mode
    return tokens, None, None

# ----------------------------
# Completion implementation
# ----------------------------

_EXEC_CACHE = None

def _executables():
    global _EXEC_CACHE
    if _EXEC_CACHE is None:
        _EXEC_CACHE = get_path_executables()
    return _EXEC_CACHE

def _listdir_safe(folder):
    try:
        return os.listdir(folder)
    except OSError:
        return []

def _complete_path(prefix, only_dirs=False):
    """
    File + directory completion, supports:
    - nested paths: src/uti<Tab>
    - ~ expansion: ~/Do<Tab>
    - returns dirs with trailing slash
    """
    if prefix == "":
        prefix = ""

    # Expand ~ for matching, but keep user-facing prefix style when possible
    expanded = os.path.expanduser(prefix)
    # Decide directory to scan
    scan_dir, base = os.path.split(expanded)

    if scan_dir == "":
        scan_dir = "."
    entries = _listdir_safe(scan_dir)

    out = []
    for e in entries:
        if not e.startswith(base):
            continue
        full = os.path.join(scan_dir, e)
        is_dir = os.path.isdir(full)

        if only_dirs and not is_dir:
            continue

        # Build suggestion using the *original* prefix's directory component if user typed one
        typed_dir, _ = os.path.split(prefix)
        if typed_dir == "":
            candidate = e
        else:
            # keep original separator usage
            candidate = typed_dir.rstrip("/\\") + os.sep + e

        if is_dir:
            candidate += os.sep
        out.append(candidate)

    # Optional: sort for stable cycling
    out.sort()
    return out

def _parse_line_for_completion(line, begidx):
    """
    Return (tokens, current_token_index).
    We use shlex to respect quotes as much as we can.
    If shlex fails (unfinished quotes), fall back to simple split.
    """
    before_cursor = line[:begidx]
    try:
        tokens = shlex.split(before_cursor)
    except ValueError:
        # incomplete quotes; best-effort split
        tokens = before_cursor.split()

    # If cursor is at a space, we're starting a new token
    if before_cursor.endswith((" ", "\t")):
        tokens.append("")
    cur_index = len(tokens) - 1 if tokens else 0
    return tokens, cur_index

def _command_candidates(text):
    # builtin + PATH executables
    cands = set(builtin_functions.keys()) | set(_executables())
    return sorted([c for c in cands if c.startswith(text)])

def _arg_candidates(cmd, text):
    """
    Command-specific argument completion:
    - cd: directories only
    - type: builtins + executables as arguments
    - default: file completion (files + dirs)
    """
    if cmd == "cd":
        return _complete_path(text, only_dirs=True)

    if cmd == "type":
        cands = set(builtin_functions.keys()) | set(_executables())
        return sorted([c for c in cands if c.startswith(text)])

    # Default: file completion for args
    # If you want "extension complete" for files, you could filter here by ext.
    return _complete_path(text, only_dirs=False)

def _completer(text, state):
    """
    readline completer signature:
      - text: the current token fragment
      - state: 0..n, return nth match or None
    """
    line = readline.get_line_buffer()
    begidx = readline.get_begidx()

    tokens, cur_i = _parse_line_for_completion(line, begidx)

    # Decide whether we are completing the command name or an argument
    if not tokens or cur_i == 0:
        matches = _command_candidates(text)
    else:
        cmd = tokens[0]
        matches = _arg_candidates(cmd, text)

    try:
        return matches[state]
    except IndexError:
        return None

def setup_completion():
    # Basic readline configuration
    readline.set_completer(_completer)
    readline.parse_and_bind("tab: complete")

    # Helps with nicer completion behavior on many systems
    # (If unsupported, it's fine.)
    try:
        readline.set_completer_delims(" \t\n")
    except Exception:
        pass

# ----------------------------
# CLI loop
# ----------------------------

def run_cli():
    setup_completion()

    while True:
        try:
            user_inputs = input("$ ")

            try:
                user_inputs = shlex.split(user_inputs)
            except ValueError as e:
                sys.stderr.write(f"parse error: {e}\n")
                continue

            user_inputs, out_file, out_mode = split_redirection(
                user_inputs, [(">", "w"), ("1>", "w"), (">>", "a"), ("1>>", "a")]
            )
            if user_inputs is None:
                continue

            user_inputs, err_file, err_mode = split_redirection(
                user_inputs, [("2>", "w"), ("2>>", "a")]
            )
            if user_inputs is None:
                continue

            if len(user_inputs) == 0:
                continue

            cmd = user_inputs[0]
            args = user_inputs[1:]

            if cmd in builtin_functions:
                old_stdout = sys.stdout
                old_stderr = sys.stderr

                out_f = None
                err_f = None

                try:
                    if out_file:
                        out_f = open(out_file, out_mode, encoding="utf-8")
                        sys.stdout = out_f

                    if err_file:
                        err_f = open(err_file, err_mode, encoding="utf-8")
                        sys.stderr = err_f

                    builtin_functions[cmd](args)

                finally:
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr
                    if out_f:
                        out_f.close()
                    if err_f:
                        err_f.close()

                continue

            path = shutil.which(cmd)
            if not path:
                sys.stderr.write(f"{cmd}: command not found\n")
                continue

            out_handle = None
            err_handle = None

            try:
                stdout_target = subprocess.PIPE
                stderr_target = subprocess.PIPE

                if out_file:
                    out_handle = open(out_file, out_mode, encoding="utf-8")
                    stdout_target = out_handle

                if err_file:
                    err_handle = open(err_file, err_mode, encoding="utf-8")
                    stderr_target = err_handle

                result = subprocess.run(
                    [cmd] + args,
                    stdout=stdout_target,
                    stderr=stderr_target,
                    text=True,
                    errors="replace"
                )

            finally:
                if out_handle:
                    out_handle.close()
                if err_handle:
                    err_handle.close()

            if result.stdout:
                sys.stdout.write(result.stdout)
            if result.stderr:
                sys.stderr.write(result.stderr)

        except EOFError:
            sys.stdout.write("\n")
            break
        except KeyboardInterrupt:
            sys.stdout.write("\n")
            continue

if __name__ == "__main__":
    run_cli()