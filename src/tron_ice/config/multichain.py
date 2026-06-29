from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / ".env")


@dataclass(frozen=True)
class ChainConfig:
    name: str
    chain_id: int
    api_key_env: str
    native_token: str
    legacy_api_url: str | None = None

    @property
    def api_key(self) -> str | None:
        return os.getenv(self.api_key_env) or os.getenv("ETHERSCAN_API_KEY")


EVM_CHAINS: dict[str, ChainConfig] = {
    "ethereum": ChainConfig("ethereum", 1, "ETHERSCAN_API_KEY", "ETH", "https://api.etherscan.io/api"),
    "bsc": ChainConfig("bsc", 56, "BSCSCAN_API_KEY", "BNB", "https://api.bscscan.com/api"),
    "polygon": ChainConfig("polygon", 137, "POLYGONSCAN_API_KEY", "POL", "https://api.polygonscan.com/api"),
    "arbitrum": ChainConfig("arbitrum", 42161, "ARBISCAN_API_KEY", "ETH", "https://api.arbiscan.io/api"),
    "base": ChainConfig("base", 8453, "BASESCAN_API_KEY", "ETH", "https://api.basescan.org/api"),
    "optimism": ChainConfig("optimism", 10, "OPTIMISTIC_ETHERSCAN_API_KEY", "ETH", "https://api-optimistic.etherscan.io/api"),
    "avalanche": ChainConfig("avalanche", 43114, "SNOWTRACE_API_KEY", "AVAX", "https://api.snowtrace.io/api"),
}


NETWORK_ALIASES = {
    "eth": "ethereum",
    "ethereum": "ethereum",
    "erc20": "ethereum",
    "binance-smart-chain": "bsc",
    "bnb": "bsc",
    "bsc": "bsc",
    "polygon": "polygon",
    "matic": "polygon",
    "arbitrum": "arbitrum",
    "arb": "arbitrum",
    "base": "base",
    "optimism": "optimism",
    "op": "optimism",
    "avax": "avalanche",
    "avalanche": "avalanche",
    "tron": "tron",
    "trx": "tron",
    "trc20": "tron",
    "sol": "solana",
    "solana": "solana",
    "btc": "bitcoin",
    "bitcoin": "bitcoin",
    "liquid": "liquid",
    "lbtc": "liquid",
}


SOLANA_TOKEN_MINTS: dict[str, str] = {
    "So11111111111111111111111111111111111111112": "SOL",
    "Es9vMFrzaCERmJfrF4H2FYD4dWhsA7UnAb5XcPTmAJ7": "USDT",
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
}


def canonical_chain(name: str | None) -> str | None:
    if not name:
        return None
    return NETWORK_ALIASES.get(name.strip().lower(), name.strip().lower())


def env_key(service: str, chain: str) -> str:
    return f"{service.upper()}_HOT_WALLETS_{chain.upper()}"


def service_hot_wallets(service: str, chain: str) -> list[str]:
    raw = os.getenv(env_key(service, chain))
    if not raw and chain == "tron":
        raw = os.getenv(f"{service}_hot_wallet") or os.getenv(f"{service.upper()}_HOT_WALLETS_TRON")
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]
