import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from google.cloud import firestore, secretmanager
from eth_account import Account
Account.enable_unaudited_hdwallet_features()

app = FastAPI(title="wallet-fabric")
_db=None; _sm=None
ROOT_MNEMONIC_SECRET=os.getenv("ROOT_MNEMONIC_SECRET","wallet-root-mnemonic")
CHAIN=os.getenv("CHAIN","eth")
DERIVATION_PREFIX=os.getenv("DERIVATION_PREFIX","m/44'/60'/0'/0")
STORE_PRIVKEYS=os.getenv("STORE_PRIVKEYS","true").lower()=="true"
LABEL_DEFAULT=os.getenv("WALLET_LABEL","fabric")

def db():
    global _db
    if _db is None: _db = firestore.Client()
    return _db

def sm():
    global _sm
    if _sm is None: _sm = secretmanager.SecretManagerServiceClient()
    return _sm

def project_id():
    return os.getenv("GCP_PROJECT_ID") or db().project

def get_or_create_root():
    pid = project_id()
    name = f"projects/{pid}/secrets/{ROOT_MNEMONIC_SECRET}/versions/latest"
    try:
        return sm().access_secret_version(request={"name": name}).payload.data.decode()
    except Exception:
        # create new mnemonic
        mnemonic = Account.create_with_mnemonic()[1]
        parent = f"projects/{pid}"
        try:
            sm().create_secret(request={"parent": parent,"secret_id": ROOT_MNEMONIC_SECRET,"secret":{"replication":{"automatic":{}}}})
        except Exception:
            pass
        sm().add_secret_version(request={"parent": f"{parent}/secrets/{ROOT_MNEMONIC_SECRET}","payload":{"data": mnemonic.encode()}})
        return mnemonic

def derive(mnemonic: str, index: int):
    path = f"{DERIVATION_PREFIX}/{index}"
    acct = Account.from_mnemonic(mnemonic, account_path=path)
    return acct, path

class InitRequest(BaseModel):
    mnemonic: str | None = None

class PreviewRequest(BaseModel):
    start_index: int = Field(0, ge=0)
    count: int = Field(5, ge=1, le=50)

class MintRequest(BaseModel):
    count: int = Field(1, ge=1, le=1000)
    label: str | None = None

@app.get("/health")
def health():
    ok_db=ok_sec=True
    try: next(db().collections(), None)
    except Exception: ok_db=False
    try: _ = get_or_create_root()
    except Exception: ok_sec=False
    return {"ok": ok_db and ok_sec, "firestore_ok": ok_db, "secrets_ok": ok_sec, "service":"wallet-fabric"}

@app.post("/init")
def init(req: InitRequest):
    pid = project_id()
    if req.mnemonic:
        # validate
        Account.from_mnemonic(req.mnemonic, account_path=f"{DERIVATION_PREFIX}/0")
        parent=f"projects/{pid}"
        try: sm().create_secret(request={"parent":parent,"secret_id":ROOT_MNEMONIC_SECRET,"secret":{"replication":{"automatic":{}}}})
        except Exception: pass
        sm().add_secret_version(request={"parent": f"{parent}/secrets/{ROOT_MNEMONIC_SECRET}","payload":{"data": req.mnemonic.encode()}})
    else:
        _ = get_or_create_root()
    # init state doc
    db().collection("wallet_fabric").document("default").set({"next_index": 0}, merge=True)
    return {"ok": True}

@app.post("/addresses/preview")
def preview(req: PreviewRequest):
    mnemonic = get_or_create_root()
    out=[]
    for i in range(req.start_index, req.start_index+req.count):
        acct, path = derive(mnemonic, i)
        out.append({"index": i, "address": acct.address, "derivationPath": path})
    return {"ok": True, "addresses": out}

@app.post("/addresses/mint")
def mint(req: MintRequest):
    label = req.label or LABEL_DEFAULT
    pid = project_id()
    mnemonic = get_or_create_root()
    state_ref = db().collection("wallet_fabric").document("default")

    @firestore.transactional
    def reserve(tx):
        snap = state_ref.get(transaction=tx)
        start = (snap.to_dict() or {}).get("next_index", 0)
        tx.update(state_ref, {"next_index": start + req.count})
        return start
    start = reserve(db().transaction())

    batch = db().batch(); minted=[]
    for i in range(start, start+req.count):
        acct, path = derive(mnemonic, i)
        addr = acct.address.lower()
        if STORE_PRIVKEYS:
            sk_name = f"wallet-key-{addr}"
            try:
                sm().create_secret(request={"parent": f"projects/{pid}","secret_id": sk_name,"secret":{"replication":{"automatic":{}}}})
            except Exception:
                pass
            sm().add_secret_version(request={"parent": f"projects/{pid}/secrets/{sk_name}","payload":{"data": acct.key.hex().encode()}})
        doc = db().collection("wallets").document(addr)
        batch.set(doc, {"address": addr, "chain": CHAIN, "label": label, "active": True,
                        "derivationPath": path, "source":"wallet-fabric",
                        "createdAt": firestore.SERVER_TIMESTAMP, "updatedAt": firestore.SERVER_TIMESTAMP}, merge=True)
        minted.append({"index": i, "address": addr, "derivationPath": path})
    batch.commit()
    return {"ok": True, "count": len(minted), "minted": minted}
