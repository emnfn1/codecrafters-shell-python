#!/usr/bin/env python3
# First line is called Shebang, tells Unix-like systems to execute this file with python3
import sys, shutil, os, subprocess, shlex, readline, glob, time, io, atexit, re, signal

try:
    # attempts to import readline. 
    # If it cant, it tries to import pyreadline3(Windows alternative for readline) as readline.
    # if neither is available, sets readline = None. 
    # Allowing shell to not crash and run without history/completion features.
    import readline
except ModuleNotFoundError:
    try:
        import pyreadline3 as readline
    except ModuleNotFoundError:
        readline = None

#GLOBALS
# Decides where we will save a text file containing the command history.
# ~/my_shell_history by default.
HISTORY_FILE = os.environ.get("HISTFILE", 
    os.path.expanduser("~/.my_shell_history"))  

HISTORY_MAX = 1000 # max history entries kept in memory
HISTORY_EXIT_MODE = "write" # controls how history is saved on exit 
_LAST_EXIT_CODE = 0 # when program finishes, 
    # its exit code is stored here for use in $?. 
    # 0 means success, nonzero means error.

# load all your past commands from history file
_SESSION_HISTORY_START = 0
_LAST_APPENDED = 0 # remembers how many commands were in history
    # at the last time we appended to the history file
 
_SHELL_VARS: dict[str, str] = {} # stores user's custom variables
_ALIASES: dict[str, str] = {} # stores user alternative names for codes
_JOBS: dict[int, dict] = {} # uses job ID as the folder name, 
    # stores information about the job

_JOB_COUNTER = 0 # assigns unique job IDs for background jobs. 
    # Incremented each time a new job is registered.



#History
# we run this function at the start of the shell 
# to set up the command history.
def setup_history():
    # we declare it as "global" so we can modify the variables 
    # that are created outside the function. 
    global _SESSION_HISTORY_START, _LAST_APPENDED
    # we reset both bookmarks to 0, 
    # meaning we start with an empty history session
    _SESSION_HISTORY_START = 0
    _LAST_APPENDED = 0

    # safety switch: if readline is not available, 
    # we just skip all the history setup and features.
    if readline is None:
        return

    # we make sure we don't keep 
    # more than HISTORY_MAX commands in memory
    readline.set_history_length(HISTORY_MAX)

    # we check if the HISTORY_FILE exists
    if os.path.exists(HISTORY_FILE):
        try:
            # if it does, we load the past commands into memory.
            readline.read_history_file(HISTORY_FILE)
            _SESSION_HISTORY_START = readline.get_current_history_length()
            _LAST_APPENDED = _SESSION_HISTORY_START
        # if the file is locked or unreadable, 
        # we ignore the error, start with an empty history instead.
        except OSError:
            pass
    # right before the shell exits, 
    # we register the save_history function to be called
    atexit.register(save_history)


# when the shell exits, this function is called to 
# save the command history to the HISTORY_FILE.
def save_history():
    # if HISTORY_EXIT_MODE is "append", 
    # we call the append_session_to_file function,
    if HISTORY_EXIT_MODE == "append":
        append_session_to_file(HISTORY_FILE)
    else:
        try:
            # asks "how many total commands in memory right now?"
            total = readline.get_current_history_length()
            # opens the history in w(write) mode, 
            # which clears the file first to start fresh.
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                # writes every command from this session to the file, 
                # starting from the _SESSION_HISTORY_START index
                for i in range(_SESSION_HISTORY_START + 1, total + 1):
                    entry = readline.get_history_item(i)
                    if entry:
                        f.write(entry + "\n")
        # if the hard drive is full or file is locked, 
        # we catch the OSError and ignore it
        except OSError:
            pass

# we use this when HISTORY_EXIT_MODE = "append" or user runs history -a
# to add new commands to the end of an existing history file
def append_session_to_file(filepath):
    global _LAST_APPENDED
    try:
        total = readline.get_current_history_length()
        start = max(_SESSION_HISTORY_START + 1, _LAST_APPENDED + 1)
        # opens the history file in a(append) mode, 
        # that allows us to add new commands to the end of the file
        with open(filepath, "a", encoding="utf-8") as f:
            for i in range(start, total + 1):
                entry = readline.get_history_item(i)
                if entry:
                    f.write(entry + "\n")
        # we update the _LAST_APPENDED index 
        # to remember how many commands we have already saved
        _LAST_APPENDED = total
    except OSError as e:
        # if something goes wrong we print an error message so
        # the the user knows their history might not be saved
        sys.stderr.write(f"history: {e}\n")


#Executable cache
#scans path at most once every minute
_PATH_EXECUTABLES = None
_PATH_EXECUTABLES_TIMESTAMP = 0
_CACHE_TTL = 60


def get_path_executables():
    exes = set() # auto removes duplicate words. 
    pathext = os.environ.get("PATHEXT")
    allowed_extensions = None
    if pathext: # grabs the list of windows programs end in .exe, .bat, .cmd.
        allowed_extensions = {e.lower() for e in pathext.split(";") if e}

    # lists the folders computer allowed to look for programs
    # then chops the long list into individual folder names,
    # so we can look inside them one by one
    for folder in os.environ.get("PATH", "").split(os.pathsep):  
        if not folder:
            continue
        try:
            # open the found folder and look at every file inside
            for entry in os.listdir(folder):
                full = os.path.join(folder, entry)
                # if it's a sub-folder and not a file, ignore
                if not os.path.isfile(full):
                    continue
                # if we are on windows we check if the file ends in
                # .exe or .bat etc
                if allowed_extensions is not None:
                    root, ext = os.path.splitext(entry)
                    if ext.lower() in allowed_extensions:
                        exes.add(root)
                # if we are on Mac/Linux, 
                # we ask if the file marked as runnable/executable
                # if yes, we add it to our exes set 
                elif os.access(full, os.X_OK):
                    exes.add(entry)
        except OSError:
            continue
    return exes


# decides if we actually need to run the get_path_executables or 
# if we can just use the _PATH_EXECUTABLES
def get_executables_cached():
    global _PATH_EXECUTABLES, _PATH_EXECUTABLES_TIMESTAMP
    # asks if the _PATH_EXECUTABLES is empty or 
    # has it been more than 60 seconds since last checked
    if _PATH_EXECUTABLES is None or (time.time() - _PATH_EXECUTABLES_TIMESTAMP) > _CACHE_TTL:
        # if either is true, it runs the get_path_executables,
        # updates the stopwatch and gives a fresh list
        _PATH_EXECUTABLES = get_path_executables()
        _PATH_EXECUTABLES_TIMESTAMP = time.time()
    # if the list is still fresh, gives the saved list 
    return _PATH_EXECUTABLES



#expansion
# we handle $NAME and ${NAME} variable expansions with this function.
def expand_variables(token: str) -> str:
    # this function acts as the "Dictionary worker"
    def lookup(match):
        # when we find a $VAR or ${VAR} pattern
        name = match.group(1) or match.group(2)
        # we check our _SHELL_VARS first
        if name in _SHELL_VARS:
            return _SHELL_VARS[name]
        # if not found, we check the environment variables
        return os.environ.get(name, "")

    # we use regular expressions to find patterns in text
    # first line looks for ${VAR} and second line looks for $VAR
    token = re.sub(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}', lookup, token)
    token = re.sub(r'\$([A-Za-z_][A-Za-z0-9_]*)', lookup, token)
    return token


# we handle $(command) substitution with this function
def expand_command_substitution(line: str) -> str:
    def run_substitution(match):
        # this grabs whatever text is inside the $(...)
        inner = match.group(1).strip()
        if not inner:
            return ""
        try:
            result = subprocess.run(
                inner,
                shell=True, # we tell computer to run the command in a shell,
                capture_output=True, # we capture the output of the command
                text=True, # and save it as pure text in result.stdout
                errors="replace",
                )
            return result.stdout.rstrip("\n")
        except Exception:
            return ""
    # we use regex to find all $(...) pattens, 
    # and send them to the run_substitution function
    return re.sub(r'\$\((.+?)\)', run_substitution, line)


# this function is called right after we send a job to the background
# proc: special python object representing the actual running program
# cmd_string: the text of the command the user ran
def register_job(proc, cmd_string: str) -> int:
    # we take the current _JOB_COUNTER value as the new job's ID
    global _JOB_COUNTER
    # then increment the counter for the next job
    _JOB_COUNTER += 1
    # we save the job information in the _JOBS dictionary
    _JOBS[_JOB_COUNTER] = {
        "proc": proc, 
        "cmd": cmd_string,
        "status": "running",
    }
    return _JOB_COUNTER


# we run this function right before shell draws a new $ prompt,
# to check if any background jobs have finished and update the user.
def reap_jobs():
    # we loop through all the jobs in _JOBS
    for jid, job in list(_JOBS.items()):
        # we filter the "running" jobs and 
        # check if their process has finished by calling poll()
        if job["status"] == "running" and job["proc"].poll() is not None:
            job["status"] = "done" #we update the job status to "done"
            # we print a message to the user that the job has finished
            sys.stdout.write(f"\n[{jid}] Done    {job['cmd']}\n")



 
#Builtins
# this function called when user runs the "history" command.
def builtin_history(args):
    # First we check if the user typed a special flag
    # "-r" for read, "-w" for write, or "-a" for append. 
    if args and args[0] in ("-r", "-w", "-a"):
        flag = args[0]
        # we check if the user provided a filepath after the flag
        if len(args) < 2:
            # if not, we print an error message and stop
            sys.stderr.write(f"history: {flag} requires a filepath\n")
            return
        filepath = args[1]

        if flag == "-r":
            try:
                # we try to read the history from the given file,
                # load it into memory, replacing the current history.
                readline.read_history_file(filepath)
            except OSError as e:
                sys.stderr.write(f"history: cannot read {filepath}: {e}\n")

        elif flag == "-w":
            try:
                total = readline.get_current_history_length()
                # we open the file in write mode, which clears it first
                # and overwrite it with the current session's memory
                with open(filepath, "w", encoding="utf-8") as f:
                    for i in range(_SESSION_HISTORY_START + 1, total + 1):
                        entry = readline.get_history_item(i)
                        if entry:
                            f.write(entry + "\n")
            except OSError as e:
                sys.stderr.write(f"history: cannot write to {filepath}: {e}\n")

        elif flag == "-a":
            # we call append_session_to_file funciton to safely add
            # new commands to the bottom
            append_session_to_file(filepath)
        return

    # this simply clears the history in memory
    if args and args[0] == "-c":
        readline.clear_history()
        return

    # if the user just types "history" or with a number,
    # the code moves to this part
    limit = None
    if args:
        try:
            # if they typed a number,
            # we convert it to an integer and save as "limit"
            limit = int(args[0])
            if limit <= 0:
                sys.stderr.write("history: limit must be a positive integer\n")
                return
        except ValueError:
            sys.stderr.write(f"history: {args[0]}: invalid option\n")
            return
    
    total = readline.get_current_history_length()
    session_entries = []
    # we loop through the history entries, 
    # starting from _SESSION_HISTORY_START
    for i in range(_SESSION_HISTORY_START + 1, total + 1):
        entry = readline.get_history_item(i)
        if entry:
            session_number = i - _SESSION_HISTORY_START
            session_entries.append((session_number, entry))

    if limit is not None:
        session_entries = session_entries[-limit:]

    for n, entry in session_entries:
        sys.stdout.write(f"  {n:4}  {entry}\n")


# this handles the change directory command "cd".
def cd_function(user_inputs):
    # if user provided a directory, we use that as the target,
    # otherwise we default to the user's home directory.
    target = os.path.expanduser(user_inputs[0]) if user_inputs else os.path.expanduser("~")
    # we check if the target is a valid directory. 
    # if not, we print an error message.
    # if it is, we change the current working directory to the target. 
    if not os.path.isdir(target):
        sys.stderr.write(f"cd: {target}: No such file or directory\n")
    else:
        os.chdir(target)


# this function is called when user runs the "export" command.
# export takes a variable and makes it enivronment variable
def builtin_export(var):
    # if user just types "export" without arguments,
    # we print all the environment variables
    if not var:
        for key, val in sorted(os.environ.items()):
            # we use !r to get the string representation of the value,
            # which adds quotes around it
            sys.stdout.write(f"declare -x {key}={val!r}\n")
        return

    for v in var:
        if "=" in v:
            # partiiton the string into name and value, 
            # based on the first "="
            name, _, value = v.partition("=")
            # save it internally to _SHELL_VARS, publicly to os.environ
            # so both shell and other programs can access it
            _SHELL_VARS[name] = value
            os.environ[name] = value
        else:
            # if user just types "export VAR", 
            # we check if we have it in _SHELL_VARS, 
            # if yes, we add it to os.environ
            if v in _SHELL_VARS:
                os.environ[v] = _SHELL_VARS[v]
            elif v not in os.environ:
                sys.stderr.write(f"export: {v}: not found\n")


# this function is called when user runs the "unset" command.
def builtin_unset(var):
    # deletes the variable from _SHELL_VARS and os.environ if it exists
    # if not, it just ignores it without error.
    for name in var:
        _SHELL_VARS.pop(name, None)
        os.environ.pop(name, None)


# this function is called when user runs the "alias" command.
def builtin_alias(args):
    if not args:
        for name, cmd in sorted(_ALIASES.items()):
            sys.stdout.write(f"alias {name}='{cmd}'\n")
        return 
    for arg in args: 
        if "=" in arg:
            name, _, cmd = arg.partition("=")
            # we strip the quotes around the command if user typed them
            _ALIASES[name.strip()] = cmd.strip("'\"")
        else:
            if arg in _ALIASES:
                sys.stdout.write(f"alias {arg}='{_ALIASES[arg]}'\n")
            else:
                sys.stderr.write(f"alias: {arg}: not found\n")


# this function is called when user runs the "unalias" command.
def builtin_unalias(args):
    if not args:
        sys.stderr.write("unalias: usage: unalias name [name ...]\n")
        return
    # we loop through the provided names and 
    # remove them from _ALIASES if they exist
    for name in args:
        if name not in _ALIASES:
            sys.stderr.write(f"unalias: {name}: not found\n")
        else:
            _ALIASES.pop(name)


# this function is called when user runs the "source" or "." command.
def builtin_source(args):
    if not args:
        sys.stderr.write("source: usage: source <file>\n")
        return

    path = os.path.expanduser(args[0])
    if not os.path.isfile(path):
        sys.stderr.write(f"source: {path}: No such file\n")
        return

    try:
        # we open the file and read it line by line,
        with open(path, encoding = "utf-8") as f:
            for line in f:
                line = line.strip()
                # if line is empty or starts with #, we skip it
                if not line or line.startswith("#"):
                    continue
                # make it pretend the line is a command the user typed,
                # so we can reuse the same expansion and execution logic
                line = line.replace("$?", str(_LAST_EXIT_CODE))
                line = expand_variables(line)
                line = expand_command_substitution(line)
                try:
                    # finally we hand the line over to our parse_line
                    chains, background = parse_line(line)
                    # then give it to the execute to actually run it
                    execute(chains, background)
                except ParseError as e:
                    sys.stderr.write(f"source: parse error in {path}: {e}\n")
    except OSError as e:
        sys.stderr.write(f"source: {e}\n")


# user types jobs to see everything currently running in the background
def builtin_jobs(args):
    # if it is empty, we just print nothing.
    if not _JOBS:
        return
    # we loop through the jobs sorted by their job ID
    for jid, job in sorted(_JOBS.items()):
        # we check if the process is still running by calling poll(),
        status = "Running" if job["proc"].poll() is None else "Done"
        # we update the job status in case it has changed since last check
        job["status"] = status.lower()
        # we print the job ID, status, and command for each job
        sys.stdout.write(f"[{jid}] {status}    {job['cmd']}\n")


# this function is called when user runs "fg" 
# to bring a background job to the foreground.
def builtin_fg(args):
    jid = _resolve_job_id(args)
    if jid is None:
        return 
    job = _JOBS[jid]
    # if the job has just finished but we haven't reaped it yet, 
    # we print an error
    if job["proc"].poll() is not None:
        sys.stderr.write(f"fg: job {jid} has already finished\n")
        return
    # we print the command that is being brought to foreground,
    sys.stdout.write(f"{job['cmd']}\n")
    # we tell shell to not draw a new prompt until this job finishes,
    # by waiting for the process to end
    job["proc"].wait()
    # once it finishes, we mark it "done" and remove it from _JOBS
    job["status"] = "done"
    del _JOBS[jid]


# this function is called when user runs "bg"
# to resume a paused background job.
def builtin_bg(args):
    jid = _resolve_job_id(args)
    if jid is None:
        return
    job = _JOBS[jid]
    if job["proc"].poll() is not None:
        sys.stderr.write(f"bg: job {jid} has already finished\n")
        return
    try:
        # os.kill with signal.SIGCONT is a way to tell 
        # the operating system to resume a paused process.
        os.kill(job["proc"].pid, signal.SIGCONT)
        job["status"] = "running"
        sys.stdout.write(f"[{jid}] {job['cmd']} &\n")
    except (ProcessLookupError, AttributeError):
        sys.stderr.write(f"bg: could not resume job {jid}\n")


def _resolve_job_id(args) -> int | None:
    if not _JOBS:
        sys.stderr.write("no current jobs\n")
        return None
    # we strip the "%" and check if its a valid number
    # then we check if it exists in _JOBS
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
    # if user didnt provide a job ID, we default to the most recent job
    return max(_JOBS.keys())


# this function is called when user runs the "type" command 
# checks if a command is a builtin or an external program.
def builtin_type(user_inputs):
    for user_input in user_inputs:
        # we first check if it is in our builtin_functions
        if user_input in builtin_functions:
            sys.stdout.write(f"{user_input} is a shell builtin\n")
            # if not, we ask python to search the entire computer
        elif path := shutil.which(user_input):
            sys.stdout.write(f"{user_input} is {path}\n")
        else:
            sys.stdout.write(f"{user_input}: not found\n")


# this is a dictionary that maps the names of builtin commands
# to their corresponding functions.
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



#Completion 
# if the user trying to type a file or folder name,
# we use this function to look at the hard drive and find matches
def complete_path(text, dirs_only=False):
    # we expand ~ to home directory and environment variables in the text
    expanded = os.path.expanduser(os.path.expandvars(text)) if text else ""
    # "*" is a wildcard that matches anything, so we add it to the end
    pattern = (expanded + "*") if expanded else "*"
    candidates = []
    # we use glob to find all the files and folders that match
    for match in sorted(glob.glob(pattern)):
        is_dir = os.path.isdir(match)
        # if dirs_only is True, 
        # skip any matches that are not directories
        if dirs_only and not is_dir:
            continue
        display = match
        if text.startswith("~"):
            # if the user typed ~, 
            # we want to show that instead of the full home path
            display = "~" + match[len(os.path.expanduser("~")):]
        # if the match is directory, 
        # we add a "/" at the end to indicate that
        display += "/" if is_dir else " "
        candidates.append(display)
    return candidates


# this is the main function 
# that readline calls to get the list of possible completions
def command_completion(text, state):
    try:
        # we grab the entire line the user has typed so far
        buffer = readline.get_line_buffer()
        try:
            # we chop the line into individual words
            tokens = shlex.split(buffer, posix=True)
        except ValueError:
            tokens = buffer.split()

        if buffer.endswith(" "):
            tokens.append("")
    
        if len(tokens) <= 1:
            # if user is typing the first word of the command, 
            # we want to suggest both builtins and executables
            candidates = sorted(
                name for name in (set(builtin_functions) | get_executables_cached())
                if name.startswith(text)
            )
            # we auto add a space after the command 
            # if there is only one match
            if len(candidates) == 1:
                candidates = [candidates[0] + " "]
        else:
            # if user is typing the second or later word, 
            # we assume they are typing a file name or folder.
            # if the first word is "cd", we only suggest directories, 
            # otherwise we suggest both files and directories
            dirs_only = tokens[0] == "cd"
            candidates = complete_path(text, dirs_only=dirs_only)

        # we hand back specific match readline asked for
        return candidates[state] if state < len(candidates) else None

    except Exception:
        return None

# if readline is available, we set up the command completion function 
# and tell it to use tab for completion
# we also set the delimiters for readline to split words, 
# so it knows what part to complete
readline.set_completer(command_completion)
readline.set_completer_delims(" \t\n")
readline.parse_and_bind("tab: complete")



#Parsing
class ParseError(Exception):
    pass

def parse_line(line):
    try:
        # we use shlex.split to chop the line into words
        raw_tokens = shlex.split(line)
    except ValueError as e:
        raise ParseError(str(e))

    # this dictionary maps the redirection operators 
    # to a tuple of (file descriptor, mode)
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

    # we loop through every single word
    # if we see one of our logic operators (&&, ||, ;),
    # we treat it as a split point for separate command chains,
    # and we take everyting we have collected so far as one chain,
    # then start a new chain with the new operator.
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


    # this function takes one of the chains that parse_line just split
    # and splits it up even further based on pipes and redirections
    def parse_pipeline(chain_tokens):
        segments_raw = []
        current = []
        # we loop through the words in the chain,
        for tok in chain_tokens:
            # when we see a pipe "|", we take everything we collected
            if tok  == "|":
                if not current:
                    raise ParseError("syntax error: empty command before |")
                # and append it to our segments_raw list
                segments_raw.append(current)
                # then we clear current to start looking at the next
                current = []
            else:
                current.append(tok)
        if not current:
            if segments_raw:
                raise ParseError("syntax error: empty command after |")
        else:
            # make sure to save the very last chunk when loop finishes
            segments_raw.append(current)

        segments = []
        # next we loop through each chunk in segments_raw,
        for raw in segments_raw:
            # we set up tokens to hold the actual command
            tokens = []
            # and redirects to hold the redirection info we find
            redirects = []
            i = 0
            # if we find a redirection operator, 
            # we check if it's followed by a file name,
            while i < len(raw):
                tok = raw[i]
                if tok in redirect_ops:
                    if i + 1 >= len(raw):
                        raise ParseError(f"syntax error: expected file after {tok}")
                    # we look up the rule for that operator
                    fd, mode = redirect_ops[tok]
                    # and save the file descriptor, mode, and file name
                    # as a tuple in redirects
                    redirects.append((fd, mode, raw[i + 1]))
                    # we skip ahead 2 spots so we dont accidentally
                    # process the file name as part of the command
                    i += 2
                else:
                    # if the word is not a redirection operator,
                    # we assume its just a normal command or argument
                    # and add it to the tokens list
                    tokens.append(tok)
                    i += 1
            if not tokens:
                raise ParseError("syntax error: empty command in pipeline")
            segments.append((tokens, redirects))

        return segments

    # we check if the last chain ends with "&", 
    # which means the user wants to run it in the background.
    # if yes, we set background = True and remove the "&"
    # from the command chain, so it doesn't interfere with execution.
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



#Execution
# this class is a context manager
class RedirectContext:
    # we feed it the list of redirections we found in the parsing phase
    def __init__(self, redirects):
        # we save them to keep track of the files we open
        # and original pipes we need to save
        self.redirects = redirects
        self._open_files = []
        self.saved = {}


    # this code runs the moment we say "with RedirectContext(...)"
    def __enter__(self):
        stream_map = {0: "stdin", 1: "stdout",  2: "stderr"}
        # it loops through our instructions
        for fd, mode, path in self.redirects:
            # it physically creates/opens the file on the hard drive
            # and saves a reference to it in _open_files
            f = open(path, mode, encoding="utf-8")
            self._open_files.append(f)
            # this is the pipe-swapping
            attr = stream_map[fd]
            self.saved[attr] = getattr(sys, attr)
            setattr(sys, attr, f)
        return self


    # this runs exactly when "with" block finishes
    def __exit__(self, *_):
        # it looks at our saved original pipes and 
        # restores them back to sys.stdin, sys.stdout, sys.stderr
        for attr, original in self.saved.items():
            setattr(sys, attr, original)
        # then it closes all the files
        for f in self._open_files:
            f.close()


# this function is called to execute a builtin command,
def execute_builtin(cmd, args, redirects):
    # this triggers the __enter__ function to swap the pipes
    with RedirectContext(redirects):
        # then we simply call our builtin function
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


# this function is called to execute an external command
def execute_external(cmd, args, redirects):
    # first we check if the command exists anywhere on the computer
    path = shutil.which(cmd)
    if not path:
        sys.stderr.write(f"{cmd}: command not found\n")
        return 127

    # we prepare empty variables for our three main pipes
    stdout_target = None
    stderr_target = None
    stdin_target = None
    open_files = []

    try:
        # we loop through the redirection instructions
        # if they want to redirect output,
        # we open the file and assign it to the correct target variable
        for fd, mode, filepath in redirects:
            f = open(filepath, mode, encoding="utf-8")
            open_files.append(f)
            if fd == 0:
                stdin_target = f
            elif fd == 1:
                stdout_target = f
            elif fd == 2:
                stderr_target = f

        # then we call subprocess.run to actually execute the command,
        # OS directly wires the program's output into our open files
        result = subprocess.run(
            [cmd] + args,
            stdin=stdin_target,
            stdout=stdout_target,
            stderr=stderr_target,
            text=True,
            errors="replace"
        )
        # then we return the exit code of the program
        return result.returncode

    # no matter what happens, we ensure to close any open files safely
    finally:
        for f in open_files:
            f.close()


# this function handles piping "|"
def execute_pipeline(segments):
    # keeps track of every program we start on the assembly line
    processes = []
    # we store the output of the previous command in the pipeline
    prev_read_fd = None
    # we capture builtin output and save it here to feed into the next
    prev_builtin_out = None

    # we loop through each command in the pipeline,
    for i, (tokens, redirects) in enumerate(segments):
        cmd, args = tokens[0], tokens[1:]
        # we check if we are on the very last program
        is_last = (i == len(segments) - 1)
        is_builtin = cmd in builtin_functions

        # if the command is a builtin, we handle it differently
        if is_builtin:
            if not is_last:
                if prev_read_fd:
                    prev_read_fd.close()
                    prev_read_fd = None
                prev_builtin_out = capture_builtin(cmd, args)
            else:
                # if it's the last command, we grab whatever text came
                # from the previous program in the pipeline,
                # and feed it into the builtin's stdin then print it
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

                # we wait for all the previous processes 
                # on the assembly line to finish before moving on
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
            return 127

        # if there is output from the previous builtin, 
        # we create a pipe and feed it in
        if prev_builtin_out is not None:
            stdin_source = subprocess.PIPE
        # if the previous command was an external program,
        # we grab its output pipe
        elif prev_read_fd is not None:
            stdin_source = prev_read_fd
        else:
            stdin_source = None

        # last command goes to the screen,
        # commands in the middle go to a brand new pipe
        # so the next command can read it 
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
            # we start the program, hook the output of the old pipe
            # to its input, and hook a new pipe to its output
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
        
        # if we saved text from a builtin earlier,
        # we write it into the new program's stdin pipe
        # then we close the pipe to indicate we're done sending input
        if prev_builtin_out is not None:
            proc.stdin.write(prev_builtin_out)
            proc.stdin.close()
            prev_builtin_out = None

        # before we move on to the next command in the pipeline,
        # we close the old pipe, because we don't need it anymore.
        if prev_read_fd:
            prev_read_fd.close()

        processes.append((proc, open_files))
        # we save the new pipe that the current program is writing to,
        # so the next loop iteration can grab it
        prev_read_fd = proc.stdout

    # once we've started every program in the pipeline,
    # we force the shell to wait for all of them to finish
    for proc, open_files in processes:
        proc.wait()
        last_code = proc.returncode
        for fd, f in open_files:
            f.close()
    # we return the exit code of the last program in the pipeline
    return last_code


def execute(chains, background: bool = False):
    global _LAST_EXIT_CODE

    # we save the entire command string for the background job,
    # so we can show it to the user later when they type "jobs"
    if background:
        cmd_string = " ".join(
            " | ".join(" ".join(tokens) for tokens, _ in segments)
            for _, segments in chains
        ) + " &"

        # its grabs the command and checks if it exists
        _, segments = chains[0]
        tokens, redirects = segments[0] if len(segments) == 1 else segments[-1]
        cmd = tokens[0]
        args = tokens[1:]
        path = shutil.which(cmd)
        if not path:
            sys.stderr.write(f"{cmd}: command not found\n")
            return
        try:
            # we launch the program without waiting for it to finish
            proc = subprocess.Popen(
                [cmd] + args,
                stdin=subprocess.DEVNULL,#block program from reading input
                text=True,
                errors="replace",
            )
            # we hand the process to the job manager
            jid = register_job(proc, cmd_string)
            sys.stdout.write(f"[{jid}] {proc.pid}\n")
            _LAST_EXIT_CODE = 0
        except Exception as e:
            sys.stderr.write(f"{cmd}: {e}\n")
        return

    # we loop through each chain
    for op, segments in chains:
        if op == "&&" and _LAST_EXIT_CODE != 0:
            continue
        if op == "||" and _LAST_EXIT_CODE == 0:
            continue
        # it means there are no pipes, we can use execute_single
        if len(segments) == 1:
            tokens, redirects = segments[0]
            _LAST_EXIT_CODE = execute_single(tokens, redirects)
        else:
            # if there are pipes, we hand it over to execute_pipeline 
            _LAST_EXIT_CODE = execute_pipeline(segments)


def execute_single(tokens, redirects):
    # if the line is blank, do nothing and return success
    if not tokens:
        return 0
    # we check if the user is trying to set a variable.
    # currently the shell doesnt support temporary environment variable
    # for a single command, so it ignores it
    if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*=.*', tokens[0]) and len(tokens) == 1:
        name, _, value = tokens[0].partition("=")
        _SHELL_VARS[name] = value
        return 0

    # seperate the command from its arguments
    cmd, args = tokens[0], tokens[1:]

    # we check if the command is an alias and 
    # we use a safety feature to prevent infinite loop 
    # in case of circular alias definitions
    if cmd in _ALIASES and cmd not in _ALIASES.get(_ALIASES[cmd].split()[0], {}):
        expanded = shlex.split(_ALIASES[cmd]) + args
        cmd = expanded[0]
        args = expanded[1:]

    # lastly we check if the command is a builtin, 
    # if yes we execute it with execute_builtin,
    if cmd in builtin_functions:
        execute_builtin(cmd, args, redirects)
        return 0
    else:
        # if not, we hand it off to the execute_external
        return execute_external(cmd, args, redirects)



#Prompt
def build_prompt() -> str:
    # first, we check if the user set a custom prompt
    ps1 = os.environ.get("PS1") or _SHELL_VARS.get("PS1")
    # if they did, 
    if ps1:
        cwd = os.getcwd()
        # if the user's current folder is inside their home directory,
        # we replace that part with "~" 
        home = os.path.expanduser("~")
        if cwd.startswith(home):
            cwd = "~" + cwd[len(home):]
        # if user set PS1="\w" replace \w with their full current path
        # if PS1="\W", replace \W with the name of the current folder
        return ps1.replace(r"\w", cwd).replace(r"\W", os.path.basename(cwd))
    # if they didn't set PS1, we just show a simple "$" prompt
    return "$ "


# looks for a file called .myshellrc in the user's home directory
def _load_rc():
    rc = os.path.expanduser("~/.myshellrc")
    # if the file exists, we execute all the aliases and exports in it
    if os.path.isfile(rc):
        builtin_source([rc])



#Main loop
def run_cli():
    setup_history()
    # loads saved settings and aliases
    _load_rc()

    while True:
        reap_jobs()
        try:
            # we build the prompt and wait for user input
            user_inputs = input(build_prompt()) 
        # if user sends an EOF signal (Ctrl+D), we exit the shell
        except EOFError:
            sys.stdout.write("\n")
            break
        # if user sends an interrupt signal (Ctrl+C), give fresh prompt
        except KeyboardInterrupt:
            sys.stdout.write("\n")
            continue

        # if user hits enter without typing anything, restart the loop
        if not user_inputs.strip():
            continue

        # before anything, swap $? with the last exit code
        user_inputs = user_inputs.replace("$?", str(_LAST_EXIT_CODE))
        # swap $HOME with actual path
        user_inputs = expand_variables(user_inputs)
        # run any sub-commands in $(...) and paster their text back in
        user_inputs = expand_command_substitution(user_inputs)

        # we peek at the last command in history
        last = readline.get_history_item(readline.get_current_history_length())
        # if the command just type is different from the last one,
        # we add it to history
        if user_inputs != last:
            readline.add_history(user_inputs)
        
        try:
            # hand the clean, expanded text over to the parser
            chains, background = parse_line(user_inputs)
        # prints an error message for any syntax errors
        except ParseError as e:
            sys.stderr.write(f"parse error: {e}\n")
            continue
        
        #finally hand the chains to the execute to actually run
        execute(chains, background)



if __name__ == "__main__":
    run_cli()