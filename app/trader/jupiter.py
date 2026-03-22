"""
jupiter.py — Jupiter v6 DEX execution for SignalMesh AutoTrader

Flow: Quote → Swap Transaction → Sign → Send via Helius RPC → Confirm
Uses Jupiter v6 API (free, no key required)
"""

import asyncio
import base64
import json
import logging
from typing import Optional
import aiohttp
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
JUPITER_QUOTE  = "https://quote-api.jup.ag/v6/quote"
JUPITER_SWAP   = "https://quote-api.jup.ag/v6/swap"
HELIUS_RPC     = "https://mainnet.helius-rpc.com/?api-key={key}"
FALLBACK_RPC   = "https://api.mainnet-beta.solana.com"

SOL_MINT  = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

# Well-known Solana token mints
MINT_MAP = {
    "BONK":     "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "WIF":      "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
    "POPCAT":   "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",
    "MEW":      "MEW1gQWJ3nEXg2qgERiKu7FAFj79PHvQVREQUzScPP5",
    "BOME":     "ukHH6c7mMyiWCf1b9pnWe25TSpkDDt3H5pQZgZ74J82",
    "SAMO":     "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
    "FARTCOIN": "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump",
    "JUP":      "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
    "PENGU":    "2zMMhcVQEXDtdE6vsFS7S7D5oUodfJHE8vd1gnBouauv",
}


def get_mint(symbol: str) -> Optional[str]:
    """Get mint address for a token symbol"""
    sym = symbol.upper()
    if sym == "SOL":
        return SOL_MINT
    return MINT_MAP.get(sym)


def get_rpc(helius_key: Optional[str] = None) -> str:
    import os
    key = helius_key or os.getenv("HELIUS_API_KEY")
    if key:
        return HELIUS_RPC.format(key=key)
    return FALLBACK_RPC


# ── Quote ────────────────────────────────────────────────────────────────────

async def get_quote(
    input_mint: str,
    output_mint: str,
    amount_lamports: int,
    slippage_bps: int = 300  # 3% default
) -> Optional[dict]:
    """Get a Jupiter swap quote. Returns quote data or None."""
    params = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": str(amount_lamports),
        "slippageBps": str(slippage_bps),
        "onlyDirectRoutes": "false",
        "asLegacyTransaction": "false",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                JUPITER_QUOTE, params=params,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                if r.status == 200:
                    return await r.json()
                logger.error(f"Jupiter quote error: {r.status} {await r.text()}")
    except Exception as e:
        logger.error(f"Jupiter quote exception: {e}")
    return None


# ── Build Swap Transaction ────────────────────────────────────────────────────

async def build_swap_tx(
    quote: dict,
    user_pubkey: str,
    wrap_unwrap_sol: bool = True
) -> Optional[str]:
    """Build a swap transaction from a Jupiter quote. Returns base64 tx."""
    payload = {
        "quoteResponse": quote,
        "userPublicKey": user_pubkey,
        "wrapAndUnwrapSol": wrap_unwrap_sol,
        "computeUnitPriceMicroLamports": 50000,  # Priority fee
        "dynamicComputeUnitLimit": True,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                JUPITER_SWAP,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=15)
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    return data.get("swapTransaction")
                logger.error(f"Jupiter swap build error: {r.status} {await r.text()}")
    except Exception as e:
        logger.error(f"Jupiter swap build exception: {e}")
    return None


# ── Sign + Send ───────────────────────────────────────────────────────────────

async def sign_and_send(
    tx_b64: str,
    keypair: Keypair,
    helius_key: Optional[str] = None
) -> Optional[str]:
    """Sign a transaction and send it. Returns tx signature or None."""
    try:
        # Deserialize
        tx_bytes = base64.b64decode(tx_b64)
        tx = VersionedTransaction.from_bytes(tx_bytes)

        # Sign
        tx.sign([keypair])
        signed_bytes = bytes(tx)

        # Send via RPC
        rpc_url = get_rpc(helius_key)
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendTransaction",
            "params": [
                base64.b64encode(signed_bytes).decode(),
                {
                    "encoding": "base64",
                    "skipPreflight": False,
                    "preflightCommitment": "confirmed",
                    "maxRetries": 3
                }
            ]
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                rpc_url, json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as r:
                data = await r.json()
                if "result" in data:
                    return data["result"]
                logger.error(f"RPC send error: {data.get('error')}")
    except Exception as e:
        logger.error(f"sign_and_send exception: {e}")
    return None


# ── Confirm Transaction ───────────────────────────────────────────────────────

async def confirm_tx(
    signature: str,
    helius_key: Optional[str] = None,
    timeout_secs: int = 60
) -> bool:
    """Poll for tx confirmation. Returns True if confirmed."""
    rpc_url = get_rpc(helius_key)
    deadline = asyncio.get_event_loop().time() + timeout_secs
    
    while asyncio.get_event_loop().time() < deadline:
        try:
            payload = {
                "jsonrpc": "2.0", "id": 1,
                "method": "getSignatureStatuses",
                "params": [[signature], {"searchTransactionHistory": True}]
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(rpc_url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    data = await r.json()
                    statuses = data.get("result", {}).get("value", [None])
                    status = statuses[0] if statuses else None
                    if status:
                        if status.get("err"):
                            logger.error(f"TX failed: {status['err']}")
                            return False
                        if status.get("confirmationStatus") in ("confirmed", "finalized"):
                            return True
        except Exception:
            pass
        await asyncio.sleep(3)
    return False


# ── Get SOL Balance ───────────────────────────────────────────────────────────

async def get_sol_balance(pubkey: str, helius_key: Optional[str] = None) -> float:
    """Get SOL balance in SOL (not lamports)."""
    rpc_url = get_rpc(helius_key)
    try:
        payload = {
            "jsonrpc": "2.0", "id": 1,
            "method": "getBalance",
            "params": [pubkey, {"commitment": "confirmed"}]
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(rpc_url, json=payload, timeout=aiohttp.ClientTimeout(total=8)) as r:
                data = await r.json()
                lamports = data.get("result", {}).get("value", 0)
                return lamports / 1e9
    except Exception as e:
        logger.error(f"Balance check error: {e}")
    return 0.0


# ── High-level Buy / Sell ─────────────────────────────────────────────────────

async def buy_token(
    keypair: Keypair,
    token_symbol: str,
    sol_amount: float,
    slippage_bps: int = 300,
    helius_key: Optional[str] = None
) -> dict:
    """
    Buy a token with SOL.
    Returns: {success, signature, token_symbol, sol_spent, tokens_received, error}
    """
    mint = get_mint(token_symbol)
    if not mint:
        return {"success": False, "error": f"Unknown token: {token_symbol}"}

    lamports = int(sol_amount * 1e9)
    pubkey = str(keypair.pubkey())

    # 1. Get quote
    quote = await get_quote(SOL_MINT, mint, lamports, slippage_bps)
    if not quote:
        return {"success": False, "error": "Could not get Jupiter quote"}

    out_amount = int(quote.get("outAmount", 0))
    price_impact = float(quote.get("priceImpactPct", 0))

    # Safety: reject if price impact > 5%
    if price_impact > 5.0:
        return {"success": False, "error": f"Price impact too high: {price_impact:.2f}%"}

    # 2. Build transaction
    tx_b64 = await build_swap_tx(quote, pubkey)
    if not tx_b64:
        return {"success": False, "error": "Could not build swap transaction"}

    # 3. Sign + send
    sig = await sign_and_send(tx_b64, keypair, helius_key)
    if not sig:
        return {"success": False, "error": "Transaction failed to send"}

    # 4. Confirm
    confirmed = await confirm_tx(sig, helius_key)
    if not confirmed:
        return {"success": False, "error": f"TX not confirmed: {sig[:16]}..."}

    return {
        "success": True,
        "signature": sig,
        "token_symbol": token_symbol.upper(),
        "sol_spent": sol_amount,
        "tokens_received": out_amount,
        "price_impact_pct": price_impact,
        "explorer": f"https://solscan.io/tx/{sig}"
    }


async def sell_token(
    keypair: Keypair,
    token_symbol: str,
    token_amount: int,  # raw token units
    slippage_bps: int = 500,  # slightly wider for exit
    helius_key: Optional[str] = None
) -> dict:
    """
    Sell a token for SOL.
    Returns: {success, signature, sol_received, error}
    """
    mint = get_mint(token_symbol)
    if not mint:
        return {"success": False, "error": f"Unknown token: {token_symbol}"}

    pubkey = str(keypair.pubkey())

    quote = await get_quote(mint, SOL_MINT, token_amount, slippage_bps)
    if not quote:
        return {"success": False, "error": "Could not get exit quote"}

    sol_out = int(quote.get("outAmount", 0)) / 1e9

    tx_b64 = await build_swap_tx(quote, pubkey)
    if not tx_b64:
        return {"success": False, "error": "Could not build exit transaction"}

    sig = await sign_and_send(tx_b64, keypair, helius_key)
    if not sig:
        return {"success": False, "error": "Exit transaction failed to send"}

    confirmed = await confirm_tx(sig, helius_key)
    if not confirmed:
        return {"success": False, "error": f"Exit TX not confirmed: {sig[:16]}..."}

    return {
        "success": True,
        "signature": sig,
        "token_symbol": token_symbol.upper(),
        "sol_received": sol_out,
        "explorer": f"https://solscan.io/tx/{sig}"
    }
