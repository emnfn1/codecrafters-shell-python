import sys


def main():
    while True:
        sys.stdout.write("$ ")
        user_input = input()
        user_input = user_input.split()

        if command == "exit":
            break
        elif command.startswith("echo "):
            print(command[5:])
        elif command == "type":
            if "type" or "exit" or "echo" == user_input[1]:
                print(f"{user_input[1]} is a shell builtin")
            else:
                print(f"{user_input[1]}: not found")
        else:
            print(f"{command}: command not found")



if __name__ == "__main__":
    main()
