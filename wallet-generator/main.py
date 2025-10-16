from fastapi import FastAPI
from pydantic import BaseModel
import logging

# Initialize FastAPI
app = FastAPI()

# Define Pydantic models
class WalletRequest(BaseModel):
    count: int
    mnemonic: str
    shadows_per_wallet: int

# API Endpoint to generate wallets
@app.post("/generate")
async def generate_wallets(request: WalletRequest):
    try:
        wallets = create_and_store_wallets(
            num_wallets=request.count,
            mnemonic_phrase=request.mnemonic,
            shadows_per_wallet=request.shadows_per_wallet
        )
        return {"ok": True, "service": "wallet-generator", "wallets": wallets}
    except Exception as e:
        logging.error(f"Failed to generate wallets: {str(e)}")
        return {"ok": False, "error": str(e)}

# Health check endpoint for Cloud Run
@app.get("/health")
async def health_check():
    return {"ok": True, "service": "wallet-generator"}
