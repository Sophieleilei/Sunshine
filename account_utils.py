"""
XRPL 账户激活检查 —— 发交易前的 fail-fast 守卫。

原理：
    AccountInfo 请求一个【未上链】的地址时，rippled 返回错误 `actNotFound`，
    表示该账户根本没有 AccountRoot（没被激活）。这种账户：
      - 不能作为 sender 发任何交易（没法签名上链）；
      - 作为 destination 时，第一笔 >= base reserve 的 Payment 才会创建它。
    所以在动手发交易前先查一下，能最早、最便宜地失败。
"""

from xrpl.clients import JsonRpcClient
from xrpl.models.requests import AccountInfo

# Testnet 当前 base reserve（激活一个账户需要的最低锁定 XRP）。
# 余额里这部分不能动，所以"可花的钱" = 余额 - reserve。
BASE_RESERVE_XRP = 1.0


def is_account_active(client: JsonRpcClient, address: str) -> bool:
    """账户是否已激活（链上存在 AccountRoot）。

    未激活 -> rippled 返回 actNotFound -> resp.is_successful() 为 False。
    """
    resp = client.request(AccountInfo(account=address))
    if resp.is_successful():
        return True
    # 明确区分 "未激活" 和 "其他错误（网络/参数）"
    if resp.result.get("error") == "actNotFound":
        return False
    # 其他错误不该被当成 "未激活" 静默吞掉
    raise RuntimeError(
        f"AccountInfo query failed for {address}: {resp.result.get('error')} "
        f"- {resp.result.get('error_message', '')}"
    )


def require_active(client: JsonRpcClient, address: str, role: str = "账户") -> None:
    """fail-fast 守卫：账户未激活就立刻抛错，别等交易提交失败。

    用法：
        require_active(client, alice.classic_address, role="Alice")
        # 通过这行 = Alice 已上链，后面发交易才有意义
    """
    if not is_account_active(client, address):
        raise ValueError(
            f"{role} account not activated: {address}. "
            f"No AccountRoot on-chain (actNotFound); it cannot send transactions. "
            f"Fund it with >= base reserve (~1 XRP) via faucet or another active account first."
        )


def get_xrp_balance(client: JsonRpcClient, address: str) -> float:
    """读取账户链上真实 XRP 余额（单位 XRP）。未激活则抛错。"""
    resp = client.request(AccountInfo(account=address))
    if not resp.is_successful():
        raise ValueError(
            f"Cannot read balance for {address}: {resp.result.get('error')} "
            f"(account may be unactivated)"
        )
    return int(resp.result["account_data"]["Balance"]) / 1_000_000


def has_sufficient_balance(
    client: JsonRpcClient, address: str, required_xrp: float
) -> tuple[bool, float, float]:
    """Alice 的钱够不够付 required_xrp？

    返回 (是否够, 真实余额, 可花余额=余额-reserve)。
    """
    balance = get_xrp_balance(client, address)
    spendable = balance - BASE_RESERVE_XRP
    return spendable >= required_xrp, balance, spendable


def require_sufficient_balance(
    client: JsonRpcClient, address: str, required_xrp: float, role: str = "账户"
) -> None:
    """fail-fast 守卫：Alice 钱不够付 required_xrp 就立刻抛错。

    用法：
        require_sufficient_balance(client, alice.classic_address, 2.50, role="Alice")
        # 走过这行 = Alice 余额足够，发交易才有意义
    """
    ok, balance, spendable = has_sufficient_balance(client, address, required_xrp)
    if not ok:
        raise ValueError(
            f"{role} insufficient balance: {address}. "
            f"On-chain balance {balance} XRP, spendable {spendable} XRP after base reserve "
            f"{BASE_RESERVE_XRP}, required {required_xrp} XRP. "
            f"Short by {required_xrp - spendable:.6f} XRP; transaction cannot complete."
        )


if __name__ == "__main__":
    # 用现有账户自测
    client = JsonRpcClient("https://s.altnet.rippletest.net:51234")
    samples = {
        "B (active)": "rBTJw7LEo85VjZENPPCqNQe2cWRW6EMZKk",
        "fixed-seed wallet": "rEaWeFokUU4ZGuVNCcz99wpNM9ZsujjQ6h",
    }
    for role, addr in samples.items():
        print(f"{role:24s} {addr}  active={is_account_active(client, addr)}")

    # fail-fast demo: calling the guard on an unactivated account raises
    print("\n--- require_active guard demo ---")
    try:
        require_active(client, "rEaWeFokUU4ZGuVNCcz99wpNM9ZsujjQ6h", role="Alice")
    except ValueError as e:
        print(e)
