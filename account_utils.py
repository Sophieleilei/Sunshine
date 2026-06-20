"""
XRPL account activation check — a fail-fast guard to run before sending a transaction.

Why:
    When AccountInfo is asked about an address that is NOT on-chain, rippled returns
    the error `actNotFound`, meaning the account has no AccountRoot (it is unactivated).
    Such an account:
      - cannot act as a sender for any transaction (it cannot sign on-chain);
      - as a destination, only the first Payment of >= base reserve will create it.
    So checking before you act lets you fail as early and as cheaply as possible.
"""

from xrpl.clients import JsonRpcClient
from xrpl.models.requests import AccountInfo

# Current testnet base reserve (the minimum XRP locked to activate an account).
# This portion of the balance cannot be spent, so "spendable" = balance - reserve.
BASE_RESERVE_XRP = 1.0


def is_account_active(client: JsonRpcClient, address: str) -> bool:
    """Whether the account is activated (an AccountRoot exists on-chain).

    Unactivated -> rippled returns actNotFound -> resp.is_successful() is False.
    """
    resp = client.request(AccountInfo(account=address))
    if resp.is_successful():
        return True
    # Clearly distinguish "unactivated" from "other errors (network/params)"
    if resp.result.get("error") == "actNotFound":
        return False
    # Other errors must not be silently swallowed as "unactivated"
    raise RuntimeError(
        f"AccountInfo query failed for {address}: {resp.result.get('error')} "
        f"- {resp.result.get('error_message', '')}"
    )


def require_active(client: JsonRpcClient, address: str, role: str = "account") -> None:
    """fail-fast guard: raise immediately if the account is unactivated, instead of
    waiting for the transaction submit to fail.

    Usage:
        require_active(client, alice.classic_address, role="Alice")
        # Passing this line = Alice is on-chain, so sending a transaction now makes sense
    """
    if not is_account_active(client, address):
        raise ValueError(
            f"{role} account not activated: {address}. "
            f"No AccountRoot on-chain (actNotFound); it cannot send transactions. "
            f"Fund it with >= base reserve (~1 XRP) via faucet or another active account first."
        )


def get_xrp_balance(client: JsonRpcClient, address: str) -> float:
    """Read the account's real on-chain XRP balance (in XRP). Raises if unactivated."""
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
    """Does the account have enough to pay required_xrp?

    Returns (is_enough, real_balance, spendable=balance-reserve).
    """
    balance = get_xrp_balance(client, address)
    spendable = balance - BASE_RESERVE_XRP
    return spendable >= required_xrp, balance, spendable


def require_sufficient_balance(
    client: JsonRpcClient, address: str, required_xrp: float, role: str = "account"
) -> None:
    """fail-fast guard: raise immediately if the account cannot pay required_xrp.

    Usage:
        require_sufficient_balance(client, alice.classic_address, 2.50, role="Alice")
        # Passing this line = Alice has enough, so sending a transaction now makes sense
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
    # Self-test against existing accounts
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
