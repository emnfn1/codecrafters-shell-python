from genericpath import exists
import sys
import shutil
import os
import subprocess

def cd_function(args):
    if args[0] == "~":
        os.getenv('HOME')
    elif not os.path.isdir(args[0]):
        sys.stderr.write(f"cd: {args[0]}: No such file or directory\n")
    else:
        os.chdir(args[0])

builtin = {
    "type": lambda args: custom_args(args),
    "exit": lambda args: sys.exit(0),
    "echo": lambda args: sys.stdout.write(f"{' '.join(args)}\n"),
    "pwd": lambda args: sys.stdout.write(f"{os.getcwd()}\n"),
    "cd": cd_function,
     
    }

def custom_args(args):
    for arg in args:
        if arg in builtin:
            sys.stdout.write(f"{arg} is a shell builtin\n")
        elif path := shutil.which(arg, mode=os.F_OK | os.X_OK):
            sys.stdout.write(f"{arg} is {path}\n")
        else:
            sys.stdout.write(f"{arg}: not found\n")

def main():
    while True:
        sys.stdout.write("$ ")
        sys.stdout.flush()
        args = input()
        args = args.strip().split()

        if len(args) == 0:
            continue
        if args[0] in builtin:
            builtin[args[0]](args[1:])
        elif shutil.which(args[0]):
            output = subprocess.run(
                [args[0]] + args[1:],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            sys.stdout.write(output.stdout.decode())
            if output.stderr:
                sys.stderr.write(output.stderr.decode())
        else:
            sys.stderr.write(f"{args[0]}: command not found\n")



if __name__ == "__main__":
    main()
