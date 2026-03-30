import sys, shutil, os, subprocess, shlex, readline, glob, time, io, atexit, re


#GLOBALS
HISTORY_FILE = os.environ.get("HISTFILE", os.path.expanduser("~/.my_shell_history"))
HISTORY_MAX = 1000 #TUTULACAK MAX HISTORY SAYISI
HISTORY_EXIT_MODE = "write"
_LAST_EXIT_CODE = 0
_SESSION_HISTORY_START = 0
_LAST_APPENDED = 0
_SHELL_VARS: dict[str, str] = {}
_ALIASES: dict[str, str] = {}
_JOBS: dict[int, dict] = {}
_JOB_COUNTER = 0


def setup_history():
    global _SESSION_HISTORY_START, _LAST_APPENDED
    _SESSION_HISTORY_START = 0
    _LAST_APPENDED = 0
    readline.set_history_length(HISTORY_MAX)

    if os.path.exists(HISTORY_FILE):
        try:
            readline.read_history_file(HISTORY_FILE)
        except OSError:
            pass

    atexit.register(save_history)


def save_history():
    if HISTORY_EXIT_MODE == "append":
        append_session_to_file(HISTORY_FILE)
    else:
        try:
            total = readline.get_current_history_length()
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                for i in range(_SESSION_HISTORY_START + 1, total + 1):
                    entry = readline.get_history_item(i)
                    if entry:
                        f.write(entry + "\n")
        except OSError:
            pass

def append_session_to_file(filepath):
    global _LAST_APPENDED
    try:
        total = readline.get_current_history_length()
        start = max(_SESSION_HISTORY_START + 1, _LAST_APPENDED + 1)
        with open(filepath, "a", encoding="utf-8") as f:
            for i in range(start, total + 1):
                entry = readline.get_history_item(i)
                if entry:
                    f.write(entry + "\n")
        _LAST_APPENDED = total
    except OSError as e:
        sys.stderr.write(f"history: {e}\n")
#HISTORY



#zaman bazlı invalidasyon 60 saniyede bir #path executable tarama yapıyor. executable cache
_PATH_EXECUTABLES = None
_PATH_EXECUTABLES_TIMESTAMP = 0
_CACHE_TTL = 60


def get_path_executables():
    exes = set()
    pathext = os.environ.get("PATHEXT")
    allowed_extensions = None
    if pathext:
        allowed_extensions = {e.lower() for e in pathext.split(";") if e}

    for folder in os.environ.get("PATH", "").split(os.pathsep):
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
                        exes.add(root)
                elif os.access(full, os.X_OK):
                    exes.add(entry)
        except OSError:
            continue
    return exes


def get_executables_cached():
    global _PATH_EXECUTABLES, _PATH_EXECUTABLES_TIMESTAMP
    if _PATH_EXECUTABLES is None or (time.time() - _PATH_EXECUTABLES_TIMESTAMP) > _CACHE_TTL:
        _PATH_EXECUTABLES = get_path_executables()
        _PATH_EXECUTABLES_TIMESTAMP = time.time()
    return _PATH_EXECUTABLES

def expand_variables(token: str) -> str:
    def lookup(match):
        name = match.group(1) or match.group(2)
        if name in _SHELL_VARS:
            return _SHELL_VARS[name]
        return os.environ.get(name, "")

    token = re.sub(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}', lookup, token)
    token = re.sub(r'\$([A-Za-z_][A-Za-z0-9_]*)', lookup, token)
    return token


def expand_command_substitution(line: str) -> str:
    def run_substitution(match):
        inner = match.group(1).strip()
        if not inner:
            return ""
        try:
            result = subprocess.run(
                inner,
                shell=True,
                capture_output=True,
                text=True,
                errors="replace",
                )
            return result.stdout.rstrip("\n")
        except Exception:
            return ""
    return re.sub(r'\$\((.+?)\)', run_substitution, line)


def register_job(proc, cmd_string: str) -> int:
    global _JOB_COUNTER
    _JOB_COUNTER += 1
    _JOBS[_JOB_COUNTER] = {
        "proc": proc, 
        "cmd": cmd_string,
        "status": "running",
    }
    return _JOB_COUNTER


def reap_jobs():
    for jid, job in list(_JOBS.items()):
        if job["status"] == "running" and job["proc"].poll() is not None:
            job["status"] = "done"
            sys.stdout.write(f"\n[{jid}] Done    {job['cmd']}\n")
#executable cache


 
#builtins
def builtin_history(args):
    if args and args[0] in ("-r", "-w", "-a"):
        flag = args[0]
        if len(args) < 2:
            sys.stderr.write(f"history: {flag} requires a filepath\n")
            return
        filepath = args[1]

        if flag == "-r":
            try:
                readline.read_history_file(filepath)
            except OSError as e:
                sys.stderr.write(f"history: cannot read {filepath}: {e}\n")

        elif flag == "-w":
            try:
                total = readline.get_current_history_length()
                with open(filepath, "w", encoding="utf-8") as f:
                    for i in range(_SESSION_HISTORY_START + 1, total + 1):
                        entry = readline.get_history_item(i)
                        if entry:
                            f.write(entry + "\n")
            except OSError as e:
                sys.stderr.write(f"history: cannot write to {filepath}: {e}\n")

        elif flag == "-a":
            append_session_to_file(filepath)
        return

    if args and args[0] == "-c":
        readline.clear_history()
        return

    limit = None
    if args:
        try:
            limit = int(args[0])
            if limit <= 0:
                sys.stderr.write("history: limit must be a positive integer\n")
                return
        except ValueError:
            sys.stderr.write(f"history: {args[0]}: invalid option\n")
            return

    total = readline.get_current_history_length()
    
    session_entries = []
    for i in range(_SESSION_HISTORY_START + 1, total + 1):
        entry = readline.get_history_item(i)
        if entry:
            session_number = i - _SESSION_HISTORY_START
            session_entries.append((session_number, entry))

    if limit is not None:
        session_entries = session_entries[-limit:]

    for n, entry in session_entries:
        sys.stdout.write(f"  {n:4}  {entry}\n")


def cd_function(user_inputs):
    target = os.path.expanduser(user_inputs[0]) if user_inputs else os.path.expanduser("~")
    if not os.path.isdir(target):
        sys.stderr.write(f"cd: {target}: No such file or directory\n")
    else:
        os.chdir(target)


def builtin_export(args):
    if not args:
        for key, val in sorted(os.environ.items()):
            sys.stdout.write(f"declare -x {key}={val!r}\n")
        return

    for arg in args:
        if "=" in arg:
            name, _, value = arg.partition("=")
            _SHELL_VARS[name] = value
            os.environ[name] = value
        else:
            if arg in _SHELL_VARS:
                os.environ[arg] = _SHELL_VARS[arg]
            elif arg not in os.environ:
                sys.stderr.write(f"export: {arg}: not found\n")


def builtin_unset(args):
    for name in args:
        _SHELL_VARS.pop(name, None)
        os.environ.pop(name, None)


def builtin_alias(args):
    if not args:
        for name, cmd in sorted(_ALIASES.items()):
            sys.stdout.write(f"alias {name}='{cmd}'\n")
        return
    for arg in args:
        if "=" in arg:
            name, _, cmd = arg.partition("=")
            _ALIASES[name.strip()] = cmd.strip("'\"")
        else:
            if arg in _ALIASES:
                sys.stdout.write(f"alias {arg}='{_ALIASES[arg]}'\n")
            else:
                sys.stderr.write(f"alias: {arg}: not found\n")


def builtin_unalias(args):
    if not args:
        sys.stderr.write("unalias: usage: unalias name [name ...]\n")
        return
    for name in args:
        if name not in _ALIASES:
            sys.stderr.write(f"unalias: {name}: not found\n")
        else:
            _ALIASES.pop(name)


def builtin_source(args):
    if not args:
        sys.stderr.write("source: usage: source <file>\n")
        return

    path = os.path.expanduser(args[0])
    if not os.path.isfile(path):
        sys.stderr.write(f"source: {path}: No such file\n")
        return

    try:
        with open(path, encoding = "utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                line = line.replace("$?", str(_LAST_EXIT_CODE))
                line = expand_variables(line)
                line = expand_command_substitution(line)
                try:
                    chains, background = parse_line(line)
                    execute(chains, background)
                except ParseError as e:
                    sys.stderr.write(f"source: parse error in {path}: {e}\n")
    except OSError as e:
        sys.stderr.write(f"source: {e}\n")


def builtin_jobs(args):
    if not _JOBS:
        return
    for jid, job in sorted(_JOBS.items()):
        status = "Running" if job["proc"].poll() is None else "Done"
        job["status"] = status.lower()
        sys.stdout.write(f"[{jid}] {status}    {job['cmd']}\n")


def builtin_fg(args):
    jid = _resolve_job_id(args)
    if jid is None:
        return
    job = _JOBS[jid]
    if job["proc"].poll() is not None:
        sys.stderr.write(f"fg: job {jid} has already finished\n")
        return
    sys.stdout.write(f"{job['cmd']}\n")
    job["proc"].wait()
    job["status"] = "done"
    del _JOBS[jid]


def builtin_bg(args):
    import signal
    jid = _resolve_job_id(args)
    if jid is None:
        return
    job = _JOBS[jid]
    if job["proc"].poll() is not None:
        sys.stderr.write(f"bg: job {jid} has already finished\n")
        return
    try:
        os.kill(job["proc"].pid, signal.SIGCONT)
        job["status"] = "running"
        sys.stdout.write(f"[{jid}] {job['cmd']} &\n")
    except (ProcessLookupError, AttributeError):
        sys.stderr.write(f"bg: could not resume job {jid}\n")


def _resolve_job_id(args) -> int | None:
    if not _JOBS:
        sys.stderr.write("no current jobs\n")
        return None
    if args:
        jid_str = args[0].lstrip("%")
        try:
            jid = int(jid_str)
        except ValueError:
            sys.stderr.write(f"invalid job id: {args[0]}\n")
            return None

        if jid not in _JOBS:
            sys.stderr.write(f"no such job: {args[0]}\n")
            return None
        return jid
    return max(_JOBS.keys())



def builtin_type(user_inputs):
    for user_input in user_inputs:
        if user_input in builtin_functions:
            sys.stdout.write(f"{user_input} is a shell builtin\n")
        elif path := shutil.which(user_input):
            sys.stdout.write(f"{user_input} is {path}\n")
        else:
            sys.stdout.write(f"{user_input}: not found\n")


builtin_functions = {
    "type": builtin_type,
    "exit": lambda user_inputs: sys.exit(0),
    "echo": lambda args: sys.stdout.write(" ".join(args) + "\n"),
    "pwd": lambda user_inputs: sys.stdout.write(f"{os.getcwd()}\n"),
    "cd": cd_function,
    "history": builtin_history,
    "export": builtin_export,
    "unset": builtin_unset,
    "alias": builtin_alias,
    "unalias": builtin_unalias,
    "source": builtin_source,
    ".": builtin_source,
    "jobs": builtin_jobs,
    "fg": builtin_fg,
    "bg": builtin_bg,
}
#builtins 



#completion 
def complete_path(text, dirs_only=False):
    expanded = os.path.expanduser(os.path.expandvars(text)) if text else ""
    pattern = (expanded + "*") if expanded else "*"
    candidates = []
    for match in sorted(glob.glob(pattern)):
        is_dir = os.path.isdir(match)
        if dirs_only and not is_dir:
            continue
        display = match
        if text.startswith("~"):
            display = "~" + match[len(os.path.expanduser("~")):]
        display += "/" if is_dir else " "
        candidates.append(display)
    return candidates


def command_completion(text, state):
    try:
        buffer = readline.get_line_buffer()
        try:
            tokens = shlex.split(buffer, posix=True)
        except ValueError:
            tokens = buffer.split()

        if buffer.endswith(" "):
            tokens.append("")

        if len(tokens) <= 1:
            candidates = sorted(
                name for name in (set(builtin_functions) | get_executables_cached())
                if name.startswith(text)
            )
            if len(candidates) == 1:
                candidates = [candidates[0] + " "]
        else:
            dirs_only = tokens[0] == "cd"
            candidates = complete_path(text, dirs_only=dirs_only)

        return candidates[state] if state < len(candidates) else None

    except Exception:
        return None


readline.set_completer(command_completion)
readline.set_completer_delims(" \t\n")
readline.parse_and_bind("tab: complete")
#completion 



#parsing
class ParseError(Exception):
    pass

def parse_line(line):
    try:
        raw_tokens = shlex.split(line)
    except ValueError as e:
        raise ParseError(str(e))

    redirect_ops = {
        ">": (1, "w"),
        "1>": (1, "w"),
        ">>": (1, "a"),
        "1>>": (1, "a"),
        "2>": (2, "w"),
        "2>>": (2, "a"),
        "<": (0, "r"),
    }

    chain_splits = []
    current = []
    current_op = None
    list_ops = {"&&", "||", ";"}

    for tok in raw_tokens:
        if tok in list_ops:
            if not current:
                raise ParseError(f"syntax error: empty command before {tok}")
            chain_splits.append((current_op, current))
            current_op = tok
            current = []
        else:
            current.append(tok)

    if not current:
        if chain_splits:
            raise ParseError(f"syntax error: empty command after {chain_splits[-1][0]}")
    else:
        chain_splits.append((current_op, current))


    def parse_pipeline(chain_tokens):
        segments_raw = []
        current = []
        for tok in chain_tokens:
            if tok  == "|":
                if not current:
                    raise ParseError("syntax error: empty command before |")
                segments_raw.append(current)
                current = []
            else:
                current.append(tok)
        if not current:
            if segments_raw:
                raise ParseError("syntax error: empty command after |")
        else:
            segments_raw.append(current)

        segments = []
        for raw in segments_raw:
            tokens = []
            redirects = []
            i = 0
            while i < len(raw):
                tok = raw[i]
                if tok in redirect_ops:
                    if i + 1 >= len(raw):
                        raise ParseError(f"syntax error: expected file after {tok}")
                    fd, mode = redirect_ops[tok]
                    redirects.append((fd, mode, raw[i + 1]))
                    i += 2
                else:
                    tokens.append(tok)
                    i += 1
            if not tokens:
                raise ParseError("syntax error: empty command in pipeline")
            segments.append((tokens, redirects))

        return segments

    background = False
    if chain_splits:
        last_op, last_chain = chain_splits[-1]
        if last_chain and last_chain[-1] == "&":
            background = True
            last_chain = last_chain[:-1]
            if not last_chain:
                raise ParseError("syntax error: empty command before &")
            chain_splits[-1] = (last_op, last_chain)

    chains = [(op, parse_pipeline(chain)) for op, chain in chain_splits]
    return chains, background
#parsing



#execution
class RedirectContext:
    def __init__(self, redirects):
        self.redirects = redirects
        self._open_files = []
        self.saved = {}


    def __enter__(self):
        stream_map = {0: "stdin", 1: "stdout",  2: "stderr"}
        for fd, mode, path in self.redirects:
            f = open(path, mode, encoding="utf-8")
            self._open_files.append(f)
            attr = stream_map[fd]
            self.saved[attr] = getattr(sys, attr)
            setattr(sys, attr, f)
        return self


    def __exit__(self, *_):
        for attr, original in self.saved.items():
            setattr(sys, attr, original)
        for f in self._open_files:
            f.close()


def execute_builtin(cmd, args, redirects):
    with RedirectContext(redirects):
        builtin_functions[cmd](args)


def capture_builtin(cmd, args):
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        builtin_functions[cmd](args)
    finally:
        sys.stdout = old_stdout
    return buf.getvalue()


def run_builtin_with_stdin(cmd, args, stdin_text, redirects):
    with RedirectContext(redirects):
        old_stdin = sys.stdin
        sys.stdin = io.StringIO(stdin_text) if stdin_text else sys.stdin
        try:
            builtin_functions[cmd](args)
        finally:
            sys.stdin = old_stdin


def execute_external(cmd, args, redirects):
    path = shutil.which(cmd)
    if not path:
        sys.stderr.write(f"{cmd}: command not found\n")
        return 127

    stdout_target = None
    stderr_target = None
    stdin_target = None
    open_files = []

    try:
        for fd, mode, filepath in redirects:
            f = open(filepath, mode, encoding="utf-8")
            open_files.append(f)
            if fd == 0:
                stdin_target = f
            elif fd == 1:
                stdout_target = f
            elif fd == 2:
                stderr_target = f

        result = subprocess.run(
            [cmd] + args,
            stdin=stdin_target,
            stdout=stdout_target,
            stderr=stderr_target,
            text=True,
            errors="replace"
        )
        return result.returncode

    finally:
        for f in open_files:
            f.close()



def execute_pipeline(segments):
    processes = []
    prev_read_fd = None
    prev_builtin_out = None

    for i, (tokens, redirects) in enumerate(segments):
        cmd, args = tokens[0], tokens[1:]
        is_last = (i == len(segments) - 1)
        is_builtin = cmd in builtin_functions

        if is_builtin:
            if not is_last:
                if prev_read_fd:
                    prev_read_fd.close()
                    prev_read_fd = None
                prev_builtin_out = capture_builtin(cmd, args)
            else:
                if prev_read_fd:
                    stdin_text = prev_read_fd.read()
                    prev_read_fd.close()
                    prev_read_fd = None
                elif prev_builtin_out is not None:
                    stdin_text = prev_builtin_out
                    prev_builtin_out = None
                else:
                    stdin_text = None

                run_builtin_with_stdin(cmd, args, stdin_text, redirects)

                for proc, open_files in processes:
                    proc.wait()
                    for fd, f in open_files:
                        f.close()
            continue

        if not shutil.which(cmd):
            sys.stderr.write(f"{cmd}: command not found\n")
            if prev_read_fd:
                prev_read_fd.close()
            for proc, open_files in processes:
                proc.kill()
                proc.wait()
                for fd, f in open_files:
                    f.close()
            return

        if prev_builtin_out is not None:
            stdin_source = subprocess.PIPE
        elif prev_read_fd is not None:
            stdin_source = prev_read_fd
        else:
            stdin_source = None

        stdout_target = None if is_last else subprocess.PIPE
        stderr_target = None

        open_files = []
        for fd, mode, filepath in redirects:
            f = open(filepath, mode, encoding = "utf-8")
            open_files.append((fd, f))
            if fd == 1 and is_last:
                stdout_target = f
            elif fd == 2:
                stderr_target = f

        try:
            proc = subprocess.Popen(
                [cmd] + args,
                stdin=stdin_source,
                stdout=stdout_target,
                stderr=stderr_target,
                text=True,
                errors="replace",
            )
        
        except Exception as e:
            sys.stderr.write(f"{cmd}: {e}\n")
            if prev_read_fd:
                prev_read_fd.close()
            for proc, open_files in processes:
                proc.kill()
                proc.wait()
                for fd, f in open_files:
                    f.close()
            return
        
        if prev_builtin_out is not None:
            proc.stdin.write(prev_builtin_out)
            proc.stdin.close()
            prev_builtin_out = None

        if prev_read_fd:
            prev_read_fd.close()

        processes.append((proc, open_files))
        prev_read_fd = proc.stdout

    for proc, open_files in processes:
        proc.wait()
        last_code = proc.returncode
        for fd, f in open_files:
            f.close()
    return last_code


def execute(chains, background: bool = False):
    global _LAST_EXIT_CODE

    if background:
        cmd_string = " ".join(
            " | ".join(" ".join(tokens) for tokens, _ in segments)
            for _, segments in chains
        ) + " &"

        _, segments = chains[0]
        tokens, redirects = segments[0] if len(segments) == 1 else segments[-1]
        cmd = tokens[0]
        args = tokens[1:]
        path = shutil.which(cmd)
        if not path:
            sys.stderr.write(f"{cmd}: command not found\n")
            return
        try:
            proc = subprocess.Popen(
                [cmd] + args,
                stdin=subprocess.DEVNULL,
                text=True,
                errors="replace",
            )
            jid = register_job(proc, cmd_string)
            sys.stdout.write(f"[{jid}] {proc.pid}\n")
            _LAST_EXIT_CODE = 0
        except Exception as e:
            sys.stderr.write(f"{cmd}: {e}\n")
        return

    for op, segments in chains:
        if op == "&&" and _LAST_EXIT_CODE != 0:
            continue
        if op == "||" and _LAST_EXIT_CODE == 0:
            continue
        if len(segments) == 1:
            tokens, redirects = segments[0]
            _LAST_EXIT_CODE = execute_single(tokens, redirects)
        else:
            _LAST_EXIT_CODE = execute_pipeline(segments)


def execute_single(tokens, redirects):
    if not tokens:
        return 0
    if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*=.*', tokens[0]) and len(tokens) == 1:
        name, _, value = tokens[0].partition("=")
        _SHELL_VARS[name] = value
        return 0

    cmd, args = tokens[0], tokens[1:]

    if cmd in _ALIASES and cmd not in _ALIASES.get(_ALIASES[cmd].split()[0], {}):
        expanded = shlex.split(_ALIASES[cmd]) + args
        cmd = expanded[0]
        args = expanded[1:]

    if cmd in builtin_functions:
        execute_builtin(cmd, args, redirects)
        return 0
    else:
        return execute_external(cmd, args, redirects)
#execution 


def build_prompt() -> str:
    ps1 = os.environ.get("PS1") or _SHELL_VARS.get("PS1")
    if ps1:
        cwd = os.getcwd()
        home = os.path.expanduser("~")
        if cwd.startswith(home):
            cwd = "~" + cwd[len(home):]
        return ps1.replace(r"\w", cwd).replace(r"\W", os.path.basename(cwd))
    return "$ "

#main loop
def run_cli():
    setup_history()

    while True:
        reap_jobs()
        try:
            user_inputs = input(build_prompt()) 
        except EOFError:
            sys.stdout.write("\n")
            break
        except KeyboardInterrupt:
            sys.stdout.write("\n")
            continue

        if not user_inputs.strip():
            continue

        user_inputs = user_inputs.replace("$?", str(_LAST_EXIT_CODE))
        user_inputs = expand_variables(user_inputs)
        user_inputs = expand_command_substitution(user_inputs)

        last = readline.get_history_item(readline.get_current_history_length())
        if user_inputs != last:
            readline.add_history(user_inputs)

        try:
            chains, background = parse_line(user_inputs)
        except ParseError as e:
            sys.stderr.write(f"parse error: {e}\n")
            continue

        execute(chains, background)
#main loop 



if __name__ == "__main__":
    run_cli()