from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google.cloud import firestore, secretmanager
import os, time, requests, decimal

app = FastAPI(title="wallet-balance-sync")
START = time.time()
_db = None; _sm = None; _rpc = None

def db():
    global _db
    if _db is None: _db = firestore.Client()
    return _db

def sm():
    global _sm
    if _sm is None: _sm = secretmanager.SecretManagerServiceClient()
    return _sm

def get_rpc_url():
    global _rpc
    if _rpc: return _rpc
    secret_id = os.getenv("CHAIN_RPC_URL_SECRET","chain-rpc-url")
    project_id = os.getenv("GCP_PROJECT_ID") or db().project
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    _rpc = sm().access_secret_version(request={"name": name}).payload.data.decode()
    return _rpc

def wei_to_eth(wei_hex: str) -> float:
    return float(decimal.Decimal(int(wei_hex,16)) / decimal.Decimal(10**18))

def eth_get_balance(addr: str) -> dict:
    url = get_rpc_url()
    payload = {"jsonrpc":"2.0","method":"eth_getBalance","params":[addr,"latest"],"id":1}
    r = requests.post(url, json=payload, timeout=20)
    r.raise_for_status()
    data = r.json()
    if "result" not in data:
        raise HTTPException(502, f"Bad RPC: {data}")
    return {"balanceWeiHex": data["result"], "balance": wei_to_eth(data["result"])}

class SyncRequest(BaseModel):
    run_mode: str | None = "incremental"
    chain: str | None = "eth"
    limit: int | None = 200

@app.get("/health")
def health():
    ok_db = ok_secret = True
    try: next(db().collections(), None)
    except Exception: ok_db = False
    try: _ = get_rpc_url()
    except Exception: ok_secret = False
    return {"ok": ok_db and ok_secret, "uptime_sec": round(time.time()-START,2),
            "service":"wallet-balance-sync", "firestore_ok": ok_db, "secrets_ok": ok_secret}

@app.post("/sync")
def sync(req: SyncRequest):
    d = db()
    q = d.collection("wallets").where("active","==",True)
    if req.chain: q = q.where("chain","==",req.chain)
    if req.limit: q = q.limit(req.limit)
    wallets = list(q.stream())
    if not wallets: return {"accepted": True, "processed": 0, "note":"no wallets found"}

    processed, fails = 0, []
    for w in wallets:
        doc = w.to_dict()
        addr = (doc.get("address") or w.id).lower()
        chain = doc.get("chain","eth")
        try:
            b = eth_get_balance(addr)
            bal_id = f"{addr}_{chain}"
            d.collection("balances").document(bal_id).set({
                "address": addr, "chain": chain,
                "balanceWeiHex": b["balanceWeiHex"], "balance": b["balance"],
                "updatedAt": firestore.SERVER_TIMESTAMP
            }, merge=True)
            processed += 1
        except Exception as e:
            fails.append({"address": addr, "err": str(e)})
    return {"accepted": True, "processed": processed, "failures": fails}
