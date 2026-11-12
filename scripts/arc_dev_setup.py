#Generate arc private key - Development
from eth_account import Account


account = Account.create()

print("ARC Testnet Wallet")
print("===================")
print(f"Address:     {account.address}")
print(f"Private Key: {account.key.hex()}")