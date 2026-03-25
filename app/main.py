import sys


def main():
    while True:
        sys.stdout.write("$ ")
        command = input()
        if command == "exit":
            break
        print(f"{command}: command not found")
        if command.startswith("echo "):
            print(command[5:])


if __name__ == "__main__":
    main()
