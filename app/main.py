from multiprocessing import process
import sys, shutil, os, subprocess, shlex, readline, glob, time



#zaman bazlı invalidasyon 60 saniyede bir #path executable tarama yapıyor. 5-41 executable cache
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
#5-41 executable cache


 
#builtins 45-68
def cd_function(user_inputs):
    target = os.path.expanduser(user_inputs[0]) if user_inputs else os.path.expanduser("~")
    if not os.path.isdir(target):
        sys.stderr.write(f"cd: {target}: No such file or directory\n")
    else:
        os.chdir(target)


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
}
#builtins 45-68



#completion 78-124
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
#completion 78-124



#parsing
class ParseError(Exception):
    pass

def parse_line(line):
    try:
        raw_tokens = shlex.split(line)
    except ValueError as e:
        raise ParseError(str(e))

    segments_raw = []
    current = []
    for tok in raw_tokens:
        if tok == "|":
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
        
    redirect_ops = {
        ">": (1, "w"),
        "1>": (1, "w"),
        ">>": (1, "a"),
        "1>>": (1, "a"),
        "2>": (2, "w"),
        "2>>": (2, "a"),
    }

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
#parsing



#execution
class RedirectContext:
    def __init__(self, redirects):
        self.redirects = redirects
        self._open_files = []
        self.saved = {}


    def __enter__(self):
        stream_map = {1: "stdout", 2: "stderr"}
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


def execute_external(cmd, args, redirects):
    path = shutil.which(cmd)
    if not path:
        sys.stderr.write(f"{cmd}: command not found\n")
        return

    stdout_target = subprocess.PIPE
    stderr_target = subprocess.PIPE
    open_files = []

    try:
        for fd, mode, filepath in redirects:
            f = open(filepath, mode, encoding="utf-8")
            open_files.append(f)
            if fd == 1:
                stdout_target = f
            elif fd == 2:
                stderr_target = f

        result = subprocess.run(
            [cmd] + args,
            stdout=stdout_target,
            stderr=stderr_target,
            text=True,
            errors="replace"
        )
    finally:
        for f in open_files:
            f.close()

    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)


def execute_pipeline(segments):
    processes = []
    prev_read_fd = None

    for i, (tokens, redirects) in enumerate(segments):
        cmd, args = tokens[0], tokens[1:]
        is_last = (i == len(segments) - 1)
        is_first = (i == 0)

        path = shutil.which(cmd)
        if not path:
            sys.stderr.write(f"{cmd}: command not found\n")
            if prev_read_fd:
                prev_read_fd.close()
            for proc in processes:
                proc.kill()
                proc.wait()
            return

        stdin_source = prev_read_fd if not is_first else None

        stdout_target = None if is_last else subprocess.PIPE

        open_files = []
        for fd, mode, filepath in redirects:
            f = open(filepath, mode, encoding = "utf-8")
            open_files.append((fd, f))
            if fd == 1 and is_last:
                stdout_target = f
            elif fd == 2:
                sys.stderr_target = f

        try:
            proc = subprocess.Popen(
                [cmd] + args,
                stdin=stdin_source,
                stdout=stdout_target,
                stderr=None,
                text=True,
                errors="replace",
            )
        
        except Exception as e:
            sys.stderr.write(f"{cmd}: {e}\n")
            if prev_read_fd:
                prev_read_fd.close()
            for proc in process:
                proc.kill()
                proc.wait()
            return

        if prev_read_fd:
            prev_read_fd.close()

        process.append((proc, open_files))
        prev_read_fd = proc.stdout

    for proc, open_files in processes:
        proc.wait()
        for fd, f in open_files:
            f.close()



def execute(segments):
    if len(segments) == 1:
        tokens, redirects = segments[0]
        execute_single(tokens, redirects)
    else:
        execute_pipeline(segments)


def execute_single(tokens, redirects):
    if not tokens:
        return
    cmd, args = tokens[0], tokens[1:]
    if cmd in builtin_functions:
        execute_builtin(cmd, args, redirects)
    else:
        execute_external(cmd, args, redirects)
#execution 



#main loop 248-269
def run_cli():
    while True:
        try:
            user_inputs = input("$ ") 
        except EOFError:
            sys.stdout.write("\n")
            break
        except KeyboardInterrupt:
            sys.stdout.write("\n")
            continue

        if not user_inputs.strip():
            continue

        try:
            segments = parse_line(user_inputs)
        except ParseError as e:
            sys.stderr.write(f"parse error: {e}\n")
            continue

        execute(segments)
#main loop 248-269



if __name__ == "__main__":
    run_cli()