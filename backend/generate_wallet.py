"""Generate a FRESH, dedicated bot wallet for this trading bot.

Run once, on your own machine:

    python generate_wallet.py

It prints a brand-new Solana keypair:
  - PUBLIC ADDRESS  -> this is what you fund. Send the SOL you're willing to
                       risk to THIS address (and nothing you can't afford to lose).
  - PRIVATE KEY     -> paste into backend/.env as SOLANA_PRIVATE_KEY_B58.

SECURITY RULES (read them):
  * This key controls real money. Whoever has it can drain the wallet.
  * NEVER commit it, paste it into chat, screenshots, or a repo. backend/.env
    is already gitignored — keep it there.
  * NEVER reuse a key that has ever appeared in a document, chat, or old repo.
    Any such key is compromised. Generate a fresh one with this script.
  * Only keep as much SOL in this wallet as you want the bot to be able to trade.
"""
from solders.keypair import Keypair


def main():
    kp = Keypair()
    print("\n=== NEW DEDICATED BOT WALLET ===\n")
    print("PUBLIC ADDRESS (fund this):")
    print(f"  {kp.pubkey()}\n")
    print("PRIVATE KEY (base58) -> backend/.env as SOLANA_PRIVATE_KEY_B58:")
    print(f"  {kp}\n")
    print("Add to backend/.env:")
    print(f"  SOLANA_PRIVATE_KEY_B58={kp}\n")
    print("Do NOT share the private key. Do NOT commit it. Fund only what you")
    print("can afford to lose.\n")


if __name__ == "__main__":
    main()
