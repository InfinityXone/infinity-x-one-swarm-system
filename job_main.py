import os
from firestore_store import get_db, upsert_many
from wallet_lib import make_account, derive_from_mnemonic

COUNT = int(os.getenv("COUNT", "1000"))
CHAIN = os.getenv("CHAIN", "eth")
MNEMONIC = os.getenv("MNEMONIC", "")
SHADOWS = int(os.getenv("SHADOWS_PER_WALLET", "0"))

def run():
    db = get_db()
    for _ in range(COUNT):
        base = make_account()
        bundle = [base]
        if MNEMONIC and SHADOWS > 0:
            bundle.extend(derive_from_mnemonic(MNEMONIC, SHADOWS))
        upsert_many(db, bundle, chain=CHAIN)
    print(f"Generated base wallets: {COUNT} (shadows per wallet: {SHADOWS})")

if __name__ == "__main__":
    run()
