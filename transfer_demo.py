"""
On the XRPL Testnet: create a new account and demo a round-trip transfer between two accounts.

Flow (never touches the faucet, so no rate-limit):
  1. Use an existing, already-activated funder wallet as the payer.
  2. Create a new account B locally (random keypair).
  3. funder -> B, send 25 XRP (this also activates B).
  4. B -> funder, send back 5 XRP (demonstrates the reverse transfer).
  5. Print both balances before/after + the transaction results + explorer links.
"""


from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.transactions import Payment
from xrpl.models.requests import AccountInfo
from xrpl.transaction import submit_and_wait
from xrpl.utils import xrp_to_drops

client = JsonRpcClient("https://s.altnet.rippletest.net:51234")

# Already-activated funder wallet holding test XRP (the random wallet from the faucet earlier)
FUNDER_SEED = "sEdVojLtK4cuYDvLEvNiZJcbDJawRc9"


def balance_xrp(address: str):
    resp = client.request(AccountInfo(account=address))
    if not resp.is_successful():
        return None  # unactivated
    return int(resp.result["account_data"]["Balance"]) / 1_000_000


def transfer(sender: Wallet, dest: str, xrp: int) -> str:
    tx = Payment(
        account=sender.classic_address,
        destination=dest,
        amount=xrp_to_drops(xrp),
    )
    resp = submit_and_wait(tx, client, sender)
    return resp.result["meta"]["TransactionResult"]


def explorer(addr: str) -> str:
    return f"https://testnet.xrpl.org/accounts/{addr}"


def main() -> None:
    funder = Wallet.from_seed(FUNDER_SEED)
    account_b = Wallet.create()  # create new account B

    print("=" * 64)
    print(f"account A (funder): {funder.classic_address}")
    print(f"account B (new)   : {account_b.classic_address}")
    print(f"account B seed     : {account_b.seed}")
    print("=" * 64)

    print(f"\n[initial] A balance: {balance_xrp(funder.classic_address)} XRP")
    print(f"[initial] B balance: {balance_xrp(account_b.classic_address)} (None = unactivated)")

    # 1) A -> B 25 XRP (activates B)
    print("\n[transfer 1] A -> B  25 XRP (also activates B)...")
    r1 = transfer(funder, account_b.classic_address, 25)
    print(f"        result: {r1}")
    print(f"        A balance: {balance_xrp(funder.classic_address)} XRP")
    print(f"        B balance: {balance_xrp(account_b.classic_address)} XRP")

    # 2) B -> A 5 XRP (reverse transfer)
    print("\n[transfer 2] B -> A  5 XRP (reverse)...")
    r2 = transfer(account_b, funder.classic_address, 5)
    print(f"        result: {r2}")
    print(f"        A balance: {balance_xrp(funder.classic_address)} XRP")
    print(f"        B balance: {balance_xrp(account_b.classic_address)} XRP")

    print("\n" + "=" * 64)
    print("Round-trip transfer complete. View in the explorer:")
    print(f"   A: {explorer(funder.classic_address)}")
    print(f"   B: {explorer(account_b.classic_address)}")


if __name__ == "__main__":
    main()
