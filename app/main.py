from genericpath import exists
import sys
import shutil
import os
import subprocess
import shlex

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
    "echo": lambda user_inputs: sys.stdout.write(f"{' '.join(user_inputs)}\n"),
    "pwd": lambda user_inputs: sys.stdout.write(f"{os.getcwd()}\n"),
    "cd": cd_function,
}


def run_cli():
    while True:
        try:
            sys.stdout.write("$ ")
            sys.stdout.flush()

            user_inputs = sys.stdin.readline()
            
            try:
                user_inputs = shlex.split(user_inputs)
            except ValueError as e:
                sys.stderr.write(f"parse error: {e}\n")
                continue

            if len(user_inputs) == 0:
                continue
            
            cmd = user_inputs[0]
            args = user_inputs[1:]

            if cmd in builtin_functions:
                builtin_functions[cmd](args)
                continue


            path = shutil.which(cmd)
            if not path:
                sys.stderr.write(f"{cmd}: command not found\n")
                continue

            result = subprocess.run(
                [cmd] + args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text = True,
                errors="replace",
            )

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
