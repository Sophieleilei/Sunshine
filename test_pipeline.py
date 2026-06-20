import json
from pipeline import run_pipeline

alice = json.load(open("demo_wallets.json"))["main"]["address"]
print("Alice:", alice, "\n")


def show(title, intent, unverified=False):
    r = run_pipeline(intent, unverified=unverified)
    print(f"=== {title} ===  ok={r['ok']} halted_at={r['halted_at']}")
    for t in r["tasks"]:
        print(f"  [{t['status']:7s}] {t['id']:6s} {t['log']}")
    print()


base = {"payer_xrpl": alice, "payee_xrpl": "rPay7Hn", "amount": 2.50,
        "source_currency": "RLUSD", "target_currency": "EUR"}

show("PASS (够钱 2.50)", base)
show("FAIL 余额不足 (要付 100)", {**base, "amount": 100})
show("FAIL 未验证 agent (KYA DENY)", base, unverified=True)
