from typing import Dict, List, Optional
from google.cloud import firestore

def upsert_wallet(db, w: Dict[str, str], label: Optional[str] = None, chain: str = "eth"):
    doc = {
        "address": w["address"].lower(),
        "private_key": w["private_key"],  # ⚠️ consider encrypting before storing
        "active": True,
        "chain": chain,
    }
    if label: doc["label"] = label
    db.collection("wallets").document(doc["address"]).set(doc, merge=True)

def upsert_many(db, wallets: List[Dict[str, str]], chain: str = "eth"):
    batch = db.batch()
    for w in wallets:
        addr = w["address"].lower()
        batch.set(db.collection("wallets").document(addr), {
            "address": addr,
            "private_key": w["private_key"],
            "active": True,
            "chain": chain,
        }, merge=True)
    batch.commit()

def get_db():
    return firestore.Client()
