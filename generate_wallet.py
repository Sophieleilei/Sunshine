"""
在 XRPL Testnet 上生成一个【固定 seed（可复现）】的钱包并激活它。

用法：
    python generate_wallet.py            # 复用/生成固定 seed，激活，验证
    XRPL_SEED=sEd7... python generate_wallet.py   # 用你已有的固定 seed

说明：
  - 仅限 TESTNET，零风险（faucet 免费发测试 XRP）。seed 不要用于 mainnet。
  - 首次运行：生成一个 seed，存到 demo_wallets.json，并激活。
  - 之后每次运行：复用 demo_wallets.json 里的同一个 seed -> 地址永远不变（可复现）。
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
    """链上是否存在 AccountRoot（未激活会返回 actNotFound）。"""
    resp = client.request(AccountInfo(account=address))
    return resp.is_successful()


def fund_with_retry(wallet: Wallet, attempts: int = 5) -> None:
    """给已有的固定钱包注资激活；faucet 限流(429)时指数退避重试。"""
    for i in range(attempts):
        try:
            # 传入已有 wallet -> faucet 给这个固定地址注资，而非生成随机钱包
            generate_faucet_wallet(client, wallet, debug=True)
            return
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and i < attempts - 1:
                delay = 15 * (i + 1)  # 15s, 30s, 45s, 60s ...
                print(f"[activate] faucet 限流(429)，{delay}s 后重试 ({i + 1}/{attempts})")
                time.sleep(delay)
            else:
                raise


def load_or_create_fixed_seed() -> str:
    """优先级：环境变量 XRPL_SEED -> demo_wallets.json -> 新生成并持久化。"""
    env_seed = os.environ.get("XRPL_SEED")
    if env_seed:
        print(f"[seed] 使用环境变量 XRPL_SEED")
        return env_seed

    if WALLETS_FILE.exists():
        data = json.loads(WALLETS_FILE.read_text())
        seed = data.get("main", {}).get("seed")
        if seed:
            print(f"[seed] 复用 {WALLETS_FILE.name} 中已固化的 seed（可复现）")
            return seed

    # 首次：生成一个新 seed 并固化，之后就固定了
    new_wallet = Wallet.create()
    print(f"[seed] 首次运行，生成新 seed 并固化到 {WALLETS_FILE.name}")
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
    print(f"[save] 已写入 {WALLETS_FILE}")


def main() -> int:
    seed = load_or_create_fixed_seed()
    wallet = Wallet.from_seed(seed)

    print("=" * 60)
    print(f"固定钱包地址 : {wallet.classic_address}")
    print(f"seed (固定)  : {wallet.seed}")
    print("=" * 60)

    # 持久化（地址/seed/公钥），保证可复现
    save_wallet(wallet)

    if is_active(wallet.classic_address):
        print("[activate] 账户已激活（链上已存在 AccountRoot），跳过。")
    else:
        print("[activate] 账户未激活，向 testnet faucet 申请测试 XRP 并激活...")
        fund_with_retry(wallet)

    # 验证
    active = is_active(wallet.classic_address)
    print(f"[verify] is_active = {active}")
    if active:
        info = client.request(AccountInfo(account=wallet.classic_address))
        drops = int(info.result["account_data"]["Balance"])
        print(f"[verify] 余额 = {drops / 1_000_000} XRP")
        print(f"[verify] 浏览器: https://testnet.xrpl.org/accounts/{wallet.classic_address}")
        print("\n✅ 完成：固定 seed 钱包已生成并激活。")
        return 0

    print("\n❌ 激活验证失败（faucet 可能限流，稍后重试）。", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
