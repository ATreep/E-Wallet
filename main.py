import colorama
import server
import os


def cls():
    print(colorama.Fore.RESET)
    print(colorama.Back.RESET)
    os.system('cls || clear')


colorama.init(autoreset=True)

print(colorama.Fore.LIGHTBLUE_EX + "Guide of Configure E-Wallet")
print()
port = input(colorama.Fore.BLACK + colorama.Back.LIGHTYELLOW_EX +
             "Set the port of current node server (default 5000): ").strip()
if port == "":
    port = 5000
cls()
print(colorama.Fore.LIGHTBLUE_EX + "Guide of Configure E-Wallet")
print()
print("Now, you need to synchronize this node from a valid node address.")
print("The node you will synchronize from must be in the same area network with this node.")
print("If this node is the first, only an ENTER without anything inputted please.")
valid_address = input(colorama.Fore.BLACK +
                      colorama.Back.LIGHTYELLOW_EX + "Synchronize this node from a valid node address: ").strip()
cls()
server.start(ser_port=port, valid_address=valid_address)
