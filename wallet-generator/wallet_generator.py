from fastapi import FastAPI
from web3 import Web3
from eth_account import Account
from mnemonic import Mnemonic
import json
from google.cloud import firestore

app = FastAPI()

w3 = Web3(Web3.HTTPProvider('https://mainnet.infura.io/v3/YOUR_INFURA_PROJECT_ID'))
db = firestore.Client()

def generate_wallets(mnemonic, shadows_per_wallet):
    accounts = []
    base_account = Account.from_mnemonic(mnemonic)
    accounts.append({
        'address': base_account.address,
        'private_key': base_account.privateKey.hex()
    })

    shadow_accounts = []
    for i in range(shadows_per_wallet):
        shadow_account = Account.from_mnemonic(mnemonic, account_path=f"m/44'/60'/0'/0/{i}")
        shadow_accounts.append({
            'address': shadow_account.address,
            'private_key': shadow_account.privateKey.hex()
        })

    return accounts, shadow_accounts

@app.get("/health")
def health():
    return {"ok": True, "service": "wallet-generator"}

@app.post("/generate")
def generate_wallets_endpoint(request: dict):
    count = request.get("count", 1)
    mnemonic_phrase = request.get("mnemonic", "")
    shadows_per_wallet = request.get("shadows_per_wallet", 0)
    wallet_data = []

    for _ in range(count):
        wallets, shadows = generate_wallets(mnemonic_phrase, shadows_per_wallet)
        wallet_data.append({'wallet': wallets, 'shadows': shadows})

    for wallet_set in wallet_data:
        db.collection('wallets').add(wallet_set)

    return {"ok": True, "service": "wallet-generator", "generated_wallets": wallet_data}
