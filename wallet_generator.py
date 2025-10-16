from eth_account import Account
from mnemonic import Mnemonic
from google.cloud import firestore
import logging

# Enable unaudited HD wallet features to allow mnemonic generation
Account.enable_unaudited_hdwallet_features()

# Initialize Firestore client
db = firestore.Client()

# Wallet generation logic
def generate_shadow_wallets(mnemonic_phrase, shadow_wallets_per_wallet):
    """Generate shadow wallets from a mnemonic phrase."""
    shadow_wallets = []
    for i in range(shadow_wallets_per_wallet):
        try:
            shadow_account = Account.from_mnemonic(mnemonic_phrase, account_path=f"m/44'/60'/0'/0/{i}")
            shadow_wallets.append({
                'address': shadow_account.address,
                'private_key': shadow_account.privateKey.hex()
            })
        except Exception as e:
            logging.error(f"Error generating shadow wallet {i}: {str(e)}")
    return shadow_wallets


def generate_wallets(count, mnemonic_phrase, shadows_per_wallet):
    """Generate base wallets and associated shadow wallets."""
    wallets = []
    for i in range(count):
        try:
            account = Account.from_mnemonic(mnemonic_phrase, account_path=f"m/44'/60'/0'/0/{i}")
            shadow_wallets = generate_shadow_wallets(mnemonic_phrase, shadows_per_wallet)
            wallet_data = {
                'address': account.address,
                'private_key': account.privateKey.hex(),
                'shadow_wallets': shadow_wallets
            }
            wallets.append(wallet_data)

            # Store wallet in Firestore
            doc_ref = db.collection("wallets").document(account.address.lower())
            doc_ref.set(wallet_data)
            logging.info(f"Wallet {account.address} stored in Firestore.")
        except Exception as e:
            logging.error(f"Error generating wallet {i}: {str(e)}")
    
    return wallets

# Sample generation function for testing (replace with FastAPI if you need an API)
def create_and_store_wallets(num_wallets=5, mnemonic_phrase="correct horse battery staple correct horse battery staple", shadows_per_wallet=2):
    """Create wallets and store them."""
    wallets = generate_wallets(num_wallets, mnemonic_phrase, shadows_per_wallet)
    logging.info(f"Created {len(wallets)} wallets with {shadows_per_wallet} shadows each.")
    return wallets

if __name__ == "__main__":
    # Example: Generate 5 wallets with 2 shadows per wallet
    create_and_store_wallets(5, "correct horse battery staple correct horse battery staple", 2)
