"""
在 XRPL Testnet 上：新建一个账户，并演示两个账户互相转账一次。

流程（全程不碰 faucet，避开限流）：
  1. 用已有的、已激活有余额的 funder 钱包当出资人。
  2. 本地新建一个账户 B（随机 keypair）。
  3. funder -> B 转 25 XRP（这一步同时激活 B）。
  4. B -> funder 回转 5 XRP（演示反向转账）。
  5. 打印两边转账前后的余额 + 交易结果 + 浏览器链接。
"""

from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.transactions import Payment
from xrpl.models.requests import AccountInfo
from xrpl.transaction import submit_and_wait
from xrpl.utils import xrp_to_drops

client = JsonRpcClient("https://s.altnet.rippletest.net:51234")

# 已激活、有测试 XRP 的出资钱包（上一步 faucet 生成的随机钱包）
FUNDER_SEED = "sEdVojLtK4cuYDvLEvNiZJcbDJawRc9"


def balance_xrp(address: str):
    resp = client.request(AccountInfo(account=address))
    if not resp.is_successful():
        return None  # 未激活
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
    account_b = Wallet.create()  # 新建账户 B

    print("=" * 64)
    print(f"账户 A (funder): {funder.classic_address}")
    print(f"账户 B (new)   : {account_b.classic_address}")
    print(f"账户 B seed     : {account_b.seed}")
    print("=" * 64)

    print(f"\n[初始] A 余额: {balance_xrp(funder.classic_address)} XRP")
    print(f"[初始] B 余额: {balance_xrp(account_b.classic_address)} (None = 未激活)")

    # 1) A -> B 25 XRP（激活 B）
    print("\n[转账1] A -> B  25 XRP（同时激活 B）...")
    r1 = transfer(funder, account_b.classic_address, 25)
    print(f"        结果: {r1}")
    print(f"        A 余额: {balance_xrp(funder.classic_address)} XRP")
    print(f"        B 余额: {balance_xrp(account_b.classic_address)} XRP")

    # 2) B -> A 5 XRP（反向转账）
    print("\n[转账2] B -> A  5 XRP（反向）...")
    r2 = transfer(account_b, funder.classic_address, 5)
    print(f"        结果: {r2}")
    print(f"        A 余额: {balance_xrp(funder.classic_address)} XRP")
    print(f"        B 余额: {balance_xrp(account_b.classic_address)} XRP")

    print("\n" + "=" * 64)
    print("✅ 互相转账完成。浏览器查看：")
    print(f"   A: {explorer(funder.classic_address)}")
    print(f"   B: {explorer(account_b.classic_address)}")


if __name__ == "__main__":
    main()
