#!/bin/bash

# Define directories and services
WALLET_DIR=~/infinity-x-one-swarm-system/wallet-balance-sync
SHADOW_WALLET_DIR=~/infinity-x-one-swarm-system/wallet-fabric

# Function to create wallets
function create_wallets {
    # Run the Python script for wallet generation
    python3 $WALLET_DIR/wallet_generator.py
}

# Parallel execution to create wallets
echo "Starting wallet generation..."
{
    create_wallets &
    wait
} && echo "Wallet generation completed successfully!" || echo "Wallet generation failed!"

