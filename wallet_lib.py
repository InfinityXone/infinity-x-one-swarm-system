from typing import List, Dict, Optional
from eth_account import Account

# Enable HD wallet features explicitly
Account.enable_unaudited_hdwallet_features()

def make_account() -> Dict[str, str]:
    acct = Account.create()
    # LocalAccount has ._private_key (bytes); .privateKey doesn’t exist in new versions
    pk_hex = acct._private_key.hex()
    return {"address": acct.address, "private_key": pk_hex}

def derive_from_mnemonic(mnemonic: str, count: int = 5, path_prefix: str = "m/44'/60'/0'/0/") -> List[Dict[str, str]]:
    out = []
    for i in range(count):
        acct = Account.from_mnemonic(mnemonic, account_path=f"{path_prefix}{i}")
        out.append({"address": acct.address, "private_key": acct._private_key.hex()})
    return out
