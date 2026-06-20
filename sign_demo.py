"""
Proof that the non-custodial signing function works.

The two-trip model:
  1. Sunshine builds an UNSIGNED tx and autofills it (no private key involved).
  2. The agent signs it LOCALLY with its own key — the key never leaves the agent.
  3. Sunshine would submit the signed blob (NOT done here — no funds move).

Run:
  .venv/bin/python sign_demo.py
"""

import json

from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.transactions import Payment
from xrpl.transaction import autofill, sign
from xrpl.core.binarycodec import encode

TESTNET_URL = "https://s.altnet.rippletest.net:51234"


def main() -> None:
    client = JsonRpcClient(TESTNET_URL)
    seed = json.load(open("demo_wallets.json"))["main"]["seed"]
    alice = Wallet.from_seed(seed)

    # Trip 1: Sunshine constructs an UNSIGNED tx (no key touched).
    unsigned = Payment(
        account=alice.classic_address,
        destination="rPT1Sjq2YGrBMTttX4GZHjKu9dyfzbpAYe",
        amount="1000000",  # 1 XRP, demo
    )
    filled = autofill(unsigned, client)
    print("UNSIGNED tx (what /prepare returns to the agent):")
    print("  account      :", filled.account)
    print("  sequence     :", filled.sequence)
    print("  fee          :", filled.fee)
    print("  txn_signature:", filled.txn_signature, "<- empty, not signed yet")

    # The agent signs LOCALLY with its own key (the function in question).
    signed = sign(filled, alice)
    print("\nSIGNED locally by the agent (private key never leaves):")
    print("  txn_signature:", (signed.txn_signature or "")[:48], "...")
    print("  signed blob  :", encode(signed.to_xrpl())[:64], "...")
    print("  tx hash      :", signed.get_hash())

    # Trip 2 would submit `signed` via submit_and_wait — intentionally NOT done here.
    print("\n=> NOT submitted. No funds moved. Signing works.")


if __name__ == "__main__":
    main()
