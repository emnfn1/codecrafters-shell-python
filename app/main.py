import sys
import shutil
import os
import subprocess


def main():
    while True:
        sys.stdout.write("$ ")
        user_input = input()
        user_input = user_input.split()

        if user_input[0] == "exit":
            break
        elif user_input[0] == "echo":
            print(" ".join(user_input[1:]))
        elif user_input[0] == "type":
            if user_input[1] in ["echo", "type", "exit", "pwd"]:
                print(f"{user_input[1]} is a shell builtin")
            else:
                path = shutil.which(user_input[1], mode = os.F_OK | os.X_OK)
                if path:
                    print(f"{user_input[1]} is {path}")
                else:
                    print(f"{user_input[1]}: not found")
        elif user_input[0] == "pwd":
            return os.getcwd()
        else:
            executable = shutil.which(user_input[0])
            if executable:
                subprocess.run(user_input, executable = executable)
            else:
                print(f"{user_input[0]}: command not found")



if __name__ == "__main__":
    main()
