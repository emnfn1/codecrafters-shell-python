import sys
import shutil
import os
import subprocess


builtin = {
    "type": lambda args: custom_args(args),
    "exit": lambda args: sys.exit(0),
    "echo": lambda args: sys.stdout.write(f"{' '.join(args)}"),
    "pwd": lambda args: sys.stdout.write(f"{os.getcwd()}"),
}

def custom_args(args):
    for arg in args:
        if arg in builtin:
            sys.stdout.write(f"{arg} is a shell builtin\n")
        elif path:= shutil.which(arg, mode=os.F_OK | os.X_OK)
            sys.stdout.write(f"{arg} is {path}")
        else:
            sys.stdout.write(f"{arg}: not found")

def main():
    while True:
        sys.stdout.write("$ ")
        args = input.strip.split()

        if len(args) == 0:
            continue
        if args[0] in builtin:
            BUILTINS[args[0]](args[1:])
        elif path := shutil.which(args[0]):
            output = subprocess.run(
                args, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            sys.stdout.write(output.stdout.decode())
            if output.stderr:
                sys.stderr.write(output.stderr.decode())
        else:
            sys.stdout.write(f"{args[0]}: command not found")



if __name__ == "__main__":
    main()
