import sys, shutil, os, subprocess, shlex, readline

def get_path_executables():
    exes = set()
    path_env = os.environ.get("PATH", "")

    pathext = os.environ.get("PATHEXT")
    exts = None
    if pathext:
        exts = {e.lower() for e in pathext.split(";") if e}

    for folder in path_env.split(os.pathsep):
        if not folder:
            continue
        try:
            for entry in os.listdir(folder):
                full = os.path.join(folder, entry)
                if not os.path.isfile(full):
                    continue

                if exts is not None:
                    root, ext = os.path.splitext(entry)
                        if ext.lower() in exts:
                            exes.add(root)
                else:
                    if os.access(full, os.X_OK):
                        exes.add(entry)
        except OSError:
            continue
    return exes

PATH_EXES = get_path_executables()
                    

def cd_function(user_inputs):
    if not user_inputs:
        os.chdir(os.path.expanduser("~"))
        return

    target = user_inputs[0]

    target = os.path.expanduser(target)

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

def command_completion(text, state):
    buffer = readline.get_line_buffer()

    if " " in buffer.lstrip():
        return None

    builtin_matches = [name for name in builtin_functions if name.startswith(text)]
    exe_matches = [name for name in get_path_executables() if name.startswith(text)]

    matches = sorted(set(builtin_matches + exe_matches))

    if len(matches) == 1:
        matches = [matches[0] + " "]

    if state < len(matches):
        return matches[state]
    return None

readline.set_completer(command_completion)
readline.set_completer_delims(" \t\n")
readline.parse_and_bind("tab: complete")

def split_stdout_redirection(tokens):
    if ">"  in tokens:
        op = ">"
        mode = "w"
    elif "1>" in tokens:
        op = "1>"
        mode = "w"
    elif ">>" in tokens:
        op = ">>"
        mode = "a"
    elif "1>>" in tokens:
        op = "1>>"
        mode = "a"
    else:
        return tokens, None, None

    pos = tokens.index(op)
    if pos == len(tokens) - 1:
        sys.stderr.write(f"syntax error: missing filename after {op}\n")
        return None, None, None

    cleaned = tokens[:pos]
    out_file = tokens[pos + 1]
    return cleaned, out_file, mode

def split_stderr_redirection(tokens):
    if "2>" in tokens:
        op = "2>"
        mode = "w"
    elif "2>>" in tokens:
        op = "2>>"
        mode = "a"
    else:
        return tokens, None, None

    pos = tokens.index(op)
    if pos == len(tokens) - 1:
        sys.stderr.write(f"syntax error: missing filename after {op}\n")
        return None, None, None

    cleaned = tokens[:pos]
    err_file= tokens[pos +1]
    return cleaned, err_file, mode

def run_cli():
    while True:
        try:
            user_inputs = input("$ ")
            
            try:
                user_inputs = shlex.split(user_inputs)
            except ValueError as e:
                sys.stderr.write(f"parse error: {e}\n")
                continue

            user_inputs, out_file, out_mode = split_stdout_redirection(user_inputs)
            if user_inputs is None:
                continue

            user_inputs, err_file, err_mode = split_stderr_redirection(user_inputs)
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
                        err_f = open(err_file, err_mode, encoding ="utf-8")
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
