import time
import json
import logging
import sys
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solana.rpc.api import Client
from solana.rpc.types import TokenAccountOpts

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('monitor.log')
    ]
)

# RPC Endpoint - Mainnet
RPC_URL = "https://api.mainnet-beta.solana.com"
client = Client(RPC_URL)

def get_keypair_from_line(line):
    """
    Parses a private key line. Supports Base58 string or JSON array.
    """
    line = line.strip()
    if not line:
        return None

    try:
        if line.startswith('[') and line.endswith(']'):
            # JSON array format
            raw_key = json.loads(line)
            return Keypair.from_bytes(bytes(raw_key))
        else:
            # Base58 format
            return Keypair.from_base58_string(line)
    except Exception as e:
        logging.error(f"Failed to parse key: {e}")
        return None

def get_sol_balance(pubkey):
    """
    Fetches the SOL balance for a given public key.
    """
    try:
        resp = client.get_balance(pubkey)
        # resp.value is in lamports (1 SOL = 10^9 lamports)
        return resp.value / 10**9
    except Exception as e:
        logging.error(f"Error fetching SOL balance for {pubkey}: {e}")
        return 0.0

def get_token_accounts(pubkey):
    """
    Fetches SPL token accounts for a given public key.
    """
    try:
        # Standard Token Program ID
        token_program_id = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
        opts = TokenAccountOpts(program_id=token_program_id, encoding='jsonParsed')
        resp = client.get_token_accounts_by_owner(pubkey, opts)
        return resp.value
    except Exception as e:
        logging.error(f"Error fetching token accounts for {pubkey}: {e}")
        return []

def main():
    input_file = 'wallets.txt'
    output_file = 'report.txt'

    print(f"Reading wallets from {input_file}...")

    try:
        with open(input_file, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Error: {input_file} not found.")
        return

    # Filter out comments and empty lines
    valid_lines = [line for line in lines if line.strip() and not line.strip().startswith('#')]

    if not valid_lines:
        print("No wallets found in wallets.txt")
        return

    results = []

    print(f"Found {len(valid_lines)} wallets. Starting scan...")
    print("-" * 60)

    for i, line in enumerate(valid_lines):
        keypair = get_keypair_from_line(line)
        if not keypair:
            print(f"Skipping invalid key at line {i+1}")
            continue

        pubkey = keypair.pubkey()
        addr = str(pubkey)

        print(f"Scanning: {addr}...")

        # Get SOL Balance
        sol_balance = get_sol_balance(pubkey)

        # Get Token Accounts
        token_accounts = get_token_accounts(pubkey)

        wallet_data = {
            'address': addr,
            'sol_balance': sol_balance,
            'tokens': []
        }

        # Process tokens
        if token_accounts:
            for account in token_accounts:
                try:
                    # Parse the account data
                    # structure: account.account.data.parsed.info.tokenAmount...
                    parsed_data = account.account.data.parsed['info']
                    mint = parsed_data['mint']
                    token_amount = parsed_data['tokenAmount']
                    ui_amount = token_amount['uiAmount']
                    decimals = token_amount['decimals']

                    if ui_amount is not None and ui_amount > 0:
                        wallet_data['tokens'].append({
                            'mint': mint,
                            'amount': ui_amount,
                            'decimals': decimals
                        })
                except Exception as e:
                    # Skip malformed token data
                    continue

        results.append(wallet_data)

        # Simple rate limiting to avoid hitting public RPC limits hard
        time.sleep(0.5)

    # Generate Report
    print("-" * 60)
    print("Scan Complete. Generating Report...")

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("Solana Wallet Monitor Report\n")
        f.write("=" * 60 + "\n\n")

        for wallet in results:
            line_header = f"Wallet: {wallet['address']}\n"
            line_sol = f"SOL Balance: {wallet['sol_balance']:.9f} SOL\n"

            f.write(line_header)
            print(line_header.strip())
            f.write(line_sol)
            print(line_sol.strip())

            if wallet['tokens']:
                f.write("Tokens:\n")
                print("Tokens:")
                for token in wallet['tokens']:
                    # Try to identify common tokens (simple mapping)
                    # Note: This is a basic mapping, for a full list we'd need a token list API
                    symbol = token['mint']
                    if token['mint'] == "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": symbol = "USDT"
                    elif token['mint'] == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": symbol = "USDC"
                    elif token['mint'] == "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": symbol = "Bonk"

                    line_token = f"  - {symbol}: {token['amount']}\n"
                    f.write(line_token)
                    print(line_token.strip())
            else:
                f.write("  No SPL Tokens found.\n")
                print("  No SPL Tokens found.")

            f.write("\n" + "-" * 40 + "\n")
            print("-" * 40)

    print(f"\nReport saved to {output_file}")

if __name__ == "__main__":
    main()
