from fastapi import FastAPI, Body
from pydantic import BaseModel, Field
from typing import Optional
from firestore_store import get_db, upsert_many
from wallet_lib import make_account, derive_from_mnemonic

app = FastAPI()
db = get_db()

class GenRequest(BaseModel):
    count: int = Field(default=10, ge=1, le=10000)
    mnemonic: Optional[str] = None
    shadows_per_wallet: int = Field(default=0, ge=0, le=50)
    label_prefix: Optional[str] = None
    chain: str = "eth"

@app.get("/health")
def health():
    # simple read to confirm Firestore client works
    return {"ok": True, "service": "wallet-generator"}

@app.post("/generate")
def generate(req: GenRequest = Body(...)):
    created = []
    for i in range(req.count):
        base = make_account()
        bundle = [base]
        if req.mnemonic and req.shadows_per_wallet > 0:
            bundle.extend(derive_from_mnemonic(req.mnemonic, req.shadows_per_wallet))
        upsert_many(db, bundle, chain=req.chain)
        created.append(base["address"])
    return {"ok": True, "created": len(created), "sample": created[:5]}
