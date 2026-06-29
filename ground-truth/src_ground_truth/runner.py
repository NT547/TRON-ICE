"""Core ground-truth pipeline runner (callable from CLI or main.py)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src_ground_truth.export_labels import export_training_pairs
from src_ground_truth.io import (
    calendar_year_window_ms,
    ensure_dirs,
    history_time_window_ms,
    load_history_jsonl,
    load_onchain_generic_json,
    load_tron_classified_json,
    json_default,
    write_jsonl_line,
)
from src_ground_truth.match import GroundTruthMatcher, MatchConfig
from src_ground_truth.paths import default_outputs, offchain_history_path, priced_paths, tron_classified_paths
from src_ground_truth.schemas import format_ground_truth_record
from src_ground_truth.trace import TraceConfig, TronMultiHopTracer
from src_ground_truth.trongrid_client import TronGridClient

logger = logging.getLogger(__name__)


@dataclass
class GroundTruthRunConfig:
    service: str
    year: int
    history_jsonl: Path | None = None
    tron_deposits_json: Path | None = None
    tron_withdrawals_json: Path | None = None
    deposits_json: Path | None = None
    withdrawals_json: Path | None = None
    td_sec: int = 1800
    vd_rel: float = 0.01
    tw_sec: int = 7200
    vw_rel: float = 0.02
    tron_tolerance_mult: float = 2.0
    trace_depth: int = 0
    trace_window_min: int = 30
    filter_onchain_by_history: bool = True
    out_jsonl: Path | None = None
    out_json: Path | None = None
    log_file: Path | None = None
    export_training: bool = False
    min_match_score: float = 0.3
    negatives_per_positive: int = 3
    history_network_filter: str = "all"


def _enrich_history(records: list[dict[str, Any]], service: str) -> list[dict[str, Any]]:
    return [{**h, "service": h.get("service", service)} for h in records]


def _network_is_tron(value: Any) -> bool:
    return isinstance(value, str) and value.lower() in {"tron", "trx", "trc20"}


def _filter_history_by_network(
    history: list[dict[str, Any]],
    mode: str,
) -> list[dict[str, Any]]:
    if mode == "all":
        return history
    if mode not in {"tron-any", "tron-both"}:
        raise ValueError("history_network_filter must be one of: all, tron-any, tron-both")

    out: list[dict[str, Any]] = []
    for h in history:
        raw = h.get("raw") if isinstance(h.get("raw"), dict) else {}
        dep_is_tron = _network_is_tron(raw.get("depositNetwork"))
        sett_is_tron = _network_is_tron(raw.get("settleNetwork"))
        if mode == "tron-any" and (dep_is_tron or sett_is_tron):
            out.append(h)
        elif mode == "tron-both" and dep_is_tron and sett_is_tron:
            out.append(h)
    return out


def _load_onchain(cfg: GroundTruthRunConfig, history: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    td_ms = cfg.td_sec * 1000
    tw_ms = cfg.tw_sec * 1000
    min_ts, max_ts = None, None
    if cfg.filter_onchain_by_history:
        min_ts, max_ts = history_time_window_ms(history, td_ms, tw_ms)
    return _load_onchain_with_window(cfg, min_ts, max_ts)


def _load_onchain_with_window(
    cfg: GroundTruthRunConfig,
    min_ts: int | None,
    max_ts: int | None,
) -> tuple[list[dict], list[dict]]:
    deposits: list[dict[str, Any]] = []
    withdrawals: list[dict[str, Any]] = []

    if cfg.deposits_json and cfg.withdrawals_json:
        deposits = load_onchain_generic_json(cfg.deposits_json, min_ts, max_ts)
        withdrawals = load_onchain_generic_json(cfg.withdrawals_json, min_ts, max_ts)
    elif cfg.tron_deposits_json and cfg.tron_withdrawals_json:
        deposits = load_tron_classified_json(cfg.tron_deposits_json, min_ts, max_ts)
        withdrawals = load_tron_classified_json(cfg.tron_withdrawals_json, min_ts, max_ts)
    else:
        dep_p, wit_p = tron_classified_paths(cfg.service, cfg.year)
        if dep_p.exists() and wit_p.exists():
            deposits = load_tron_classified_json(dep_p, min_ts, max_ts)
            withdrawals = load_tron_classified_json(wit_p, min_ts, max_ts)
            logger.info("On-chain classified %s (window filter active)", dep_p.name)
        else:
            dep_p, wit_p = priced_paths(cfg.service, cfg.year)
            if dep_p.exists() and wit_p.exists():
                deposits = load_onchain_generic_json(dep_p, min_ts, max_ts)
                withdrawals = load_onchain_generic_json(wit_p, min_ts, max_ts)
                logger.info("On-chain priced %s", dep_p.name)

    return deposits, withdrawals


def run_ground_truth(cfg: GroundTruthRunConfig) -> dict[str, Any]:
    outs = default_outputs(cfg.service, cfg.year)
    history_path = cfg.history_jsonl or offchain_history_path(cfg.service)
    out_jsonl = cfg.out_jsonl or outs["jsonl"]
    out_json = cfg.out_json or outs["json"]
    training_path = outs["training"]

    raw_history = _enrich_history(load_history_jsonl(history_path), cfg.service)
    history = _filter_history_by_network(raw_history, cfg.history_network_filter)
    logger.info(
        "History records: %s from %s (filter=%s, original=%s)",
        len(history),
        history_path,
        cfg.history_network_filter,
        len(raw_history),
    )

    deposits, withdrawals = _load_onchain(cfg, history)
    if (not deposits or not withdrawals) and cfg.filter_onchain_by_history:
        logger.warning(
            "No on-chain txs in off-chain time window; retrying with calendar year %s",
            cfg.year,
        )
        min_ts, max_ts = calendar_year_window_ms(cfg.year)
        deposits, withdrawals = _load_onchain_with_window(cfg, min_ts, max_ts)

    if not deposits or not withdrawals:
        raise FileNotFoundError(
            "Missing on-chain deposits/withdrawals. Run transaction_normalizer for this service/year."
        )
    logger.info("On-chain loaded: deposits=%s withdrawals=%s", len(deposits), len(withdrawals))

    match_cfg = MatchConfig(
        TD_ms=cfg.td_sec * 1000,
        VD_rel=cfg.vd_rel,
        TW_ms=cfg.tw_sec * 1000,
        VW_rel=cfg.vw_rel,
        tron_tolerance_mult=cfg.tron_tolerance_mult,
    )

    tracer = None
    if cfg.trace_depth > 0:
        tracer = TronMultiHopTracer(
            TronGridClient(),
            TraceConfig(max_depth=cfg.trace_depth, hop_window_ms=cfg.trace_window_min * 60 * 1000),
        )
        logger.info("TRON trace depth=%s", cfg.trace_depth)

    matcher = GroundTruthMatcher(match_cfg, deposits=deposits, withdrawals=withdrawals, tracer=tracer)

    if out_jsonl.exists():
        out_jsonl.unlink()

    results: list[dict[str, Any]] = []
    for i, h in enumerate(history, start=1):
        m = matcher.match_one(h)
        rec = format_ground_truth_record(
            service=cfg.service,
            history=h,
            deposit=m.get("deposit"),
            settlement=m.get("settlement"),
            deposit_path=m.get("deposit_path"),
            settlement_path=m.get("settlement_path"),
            deposit_trace=m.get("deposit_trace"),
            settlement_trace=m.get("settlement_trace"),
            match_score=m.get("match_score", 0.0),
        )
        rec["_deposit_full"] = m.get("deposit")
        rec["_settlement_full"] = m.get("settlement")
        results.append(rec)
        write_jsonl_line(out_jsonl, rec)
        if i % 50 == 0:
            logger.info("Matched progress %s/%s", i, len(history))

    out_json.parent.mkdir(parents=True, exist_ok=True)
    with out_json.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=json_default)

    stats = matcher.stats()
    summary = {
        "history_count": len(history),
        "history_original_count": len(raw_history),
        "history_network_filter": cfg.history_network_filter,
        "matched_h": stats["matched_h"],
        "matched_deposit": stats["matched_deposit"],
        "matched_settlement": stats["matched_settlement"],
        "out_jsonl": str(out_jsonl),
        "out_json": str(out_json),
    }

    if cfg.export_training:
        label_stats = export_training_pairs(
            results,
            deposits,
            withdrawals,
            training_path,
            min_match_score=cfg.min_match_score,
            negatives_per_positive=cfg.negatives_per_positive,
        )
        summary["training_path"] = str(training_path)
        summary["training_stats"] = label_stats

    return summary
