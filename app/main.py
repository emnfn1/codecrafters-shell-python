import sys


def main():
    while True:
        sys.stdout.write("$ ")
        user_input = input()
        user_input = user_input.split()

        if user_input[0] == "exit":
            break
        elif user_input[0] == "echo ":
            print(command[5:])
        elif user_input[0] == "type":
            if user_input[1] in ["echo", "type", "exit"]:
                print(f"{user_input[1]} is a shell builtin")
            else:
                print(f"{user_input[1]}: not found")
        else:
            print(f"{user_input[0]}: command not found")



if __name__ == "__main__":
    main()
