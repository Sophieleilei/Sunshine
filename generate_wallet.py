"""
Generate a fixed-seed (reproducible) wallet on the XRPL Testnet and activate it.

Usage:
    python generate_wallet.py            # reuse/generate fixed seed, activate, verify
    XRPL_SEED=sEd7... python generate_wallet.py   # use your own fixed seed

Notes:
  - TESTNET only, zero risk (the faucet hands out free test XRP). Never use the seed on mainnet.
  - First run: generates a seed, saves it to demo_wallets.json, and activates it.
  - Every later run: reuses the same seed from demo_wallets.json -> address never changes (reproducible).
"""

import json
import os
import sys
import time
from pathlib import Path

import httpx
from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet, generate_faucet_wallet
from xrpl.models.requests import AccountInfo

TESTNET_URL = "https://s.altnet.rippletest.net:51234"
WALLETS_FILE = Path(__file__).parent / "demo_wallets.json"

client = JsonRpcClient(TESTNET_URL)


def is_active(address: str) -> bool:
    """Whether an AccountRoot exists on-chain (unactivated accounts return actNotFound)."""
    resp = client.request(AccountInfo(account=address))
    return resp.is_successful()


def fund_with_retry(wallet: Wallet, attempts: int = 5) -> None:
    """Fund/activate an existing fixed wallet; back off and retry on faucet rate-limit (429)."""
    for i in range(attempts):
        try:
            # Passing an existing wallet -> faucet funds this fixed address instead of a random one
            generate_faucet_wallet(client, wallet, debug=True)
            return
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and i < attempts - 1:
                delay = 15 * (i + 1)  # 15s, 30s, 45s, 60s ...
                print(f"[activate] faucet rate-limited (429); retrying in {delay}s ({i + 1}/{attempts})")
                time.sleep(delay)
            else:
                raise


def load_or_create_fixed_seed() -> str:
    """Priority: env var XRPL_SEED -> demo_wallets.json -> generate a new one and persist it."""
    env_seed = os.environ.get("XRPL_SEED")
    if env_seed:
        print("[seed] using env var XRPL_SEED")
        return env_seed

    if WALLETS_FILE.exists():
        data = json.loads(WALLETS_FILE.read_text())
        seed = data.get("main", {}).get("seed")
        if seed:
            print(f"[seed] reusing the persisted seed in {WALLETS_FILE.name} (reproducible)")
            return seed

    # First time: generate a new seed and persist it; it stays fixed from then on
    new_wallet = Wallet.create()
    print(f"[seed] first run: generating a new seed and persisting it to {WALLETS_FILE.name}")
    return new_wallet.seed


def save_wallet(wallet: Wallet) -> None:
    data = {}
    if WALLETS_FILE.exists():
        data = json.loads(WALLETS_FILE.read_text())
    data["main"] = {
        "address": wallet.classic_address,
        "seed": wallet.seed,
        "public_key": wallet.public_key,
    }
    WALLETS_FILE.write_text(json.dumps(data, indent=2))
    print(f"[save] wrote {WALLETS_FILE}")


def main() -> int:
    seed = load_or_create_fixed_seed()
    wallet = Wallet.from_seed(seed)

    print("=" * 60)
    print(f"fixed wallet address : {wallet.classic_address}")
    print(f"seed (fixed)         : {wallet.seed}")
    print("=" * 60)

    # Persist address/seed/public key so the wallet stays reproducible
    save_wallet(wallet)

    if is_active(wallet.classic_address):
        print("[activate] account already active (AccountRoot exists on-chain); skipping.")
    else:
        print("[activate] account not active; requesting test XRP from the testnet faucet...")
        fund_with_retry(wallet)

    # Verify
    active = is_active(wallet.classic_address)
    print(f"[verify] is_active = {active}")
    if active:
        info = client.request(AccountInfo(account=wallet.classic_address))
        drops = int(info.result["account_data"]["Balance"])
        print(f"[verify] balance = {drops / 1_000_000} XRP")
        print(f"[verify] explorer: https://testnet.xrpl.org/accounts/{wallet.classic_address}")
        print("\nDone: fixed-seed wallet generated and activated.")
        return 0

    print("\nActivation verification failed (faucet may be rate-limited; try again later).", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
