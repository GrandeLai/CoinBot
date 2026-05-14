"""Deterministic strategy retrospective memory and Markdown rendering."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

from trading_assistant.config.schema import StrategyRuntimeConfig
from trading_assistant.strategies.guard import StrategyRuntimeGuard
from trading_assistant.strategies.journal import StrategyJournal
from trading_assistant.strategies.models import ExecutionMode
from trading_assistant.utils.serialization import to_jsonable


Severity = Literal["info", "warning", "critical"]
IssueStatus = Literal["open", "improved"]

MANUAL_START = "<!-- RETROSPECTIVE_MANUAL_NOTES_START -->"
MANUAL_END = "<!-- RETROSPECTIVE_MANUAL_NOTES_END -->"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class RetrospectiveIssue:
    """One deduplicated strategy retrospective issue."""

    issue_id: str
    dedupe_key: str
    strategy_name: str
    execution_mode: str
    category: str
    reason: str
    severity: Severity
    status: IssueStatus = "open"
    occurrences: int = 1
    first_seen_at: str = field(default_factory=_now_iso)
    last_seen_at: str = field(default_factory=_now_iso)
    recommendation: str = ""
    last_context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe issue data."""
        return to_jsonable(self)


class StrategyRetrospectiveService:
    """Maintain a living retrospective document for strategy execution problems."""

    def __init__(self, config: StrategyRuntimeConfig) -> None:
        self.config = config
        self.document_path = _repo_root() / config.retrospective_path
        self.state_path = _repo_root() / config.retrospective_state_path
        self.journal = StrategyJournal(config.journal_path)

    def before_summary(self) -> dict[str, Any]:
        """Return unresolved retrospective context before a strategy action."""
        if not self.config.retrospective_enabled:
            return self._disabled_summary()
        return self._summary_from_state(self._load_state())

    def refresh_from_journal(self, execution_mode: ExecutionMode | None = None) -> dict[str, Any]:
        """Refresh retrospective memory from the current journal and guard state."""
        if not self.config.retrospective_enabled:
            return self._disabled_summary()
        events = [
            event
            for event in self.journal.read_events()
            if event.get("event") == "strategy_cycle" and (execution_mode is None or event.get("execution_mode") == execution_mode)
        ][-50:]
        issues, observed_modes, observed_strategy_modes = self._issues_from_results(events)
        issues.extend(self._guard_issues())
        observed_modes.update(issue.execution_mode for issue in issues if issue.execution_mode in {"paper", "demo"})
        observed_strategy_modes.update(
            (issue.strategy_name, issue.execution_mode)
            for issue in issues
            if issue.execution_mode in {"paper", "demo"}
        )
        state = self._update_state(
            issues=issues,
            observed_modes=observed_modes,
            observed_strategy_modes=observed_strategy_modes,
            operation="strategy_retrospective",
            run_summary={"journal_events": len(events), "execution_mode": execution_mode or "all"},
            increment_occurrences=False,
        )
        self._write_state(state)
        self._render_document(state)
        return self._summary_from_state(state)

    def update_after_payload(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Update retrospective memory after a strategy run or validation payload."""
        if not self.config.retrospective_enabled:
            return self._disabled_summary()
        issues, observed_modes, observed_strategy_modes = self._issues_from_payload(payload)
        issues.extend(self._guard_issues())
        observed_modes.update(issue.execution_mode for issue in issues if issue.execution_mode in {"paper", "demo"})
        observed_strategy_modes.update(
            (issue.strategy_name, issue.execution_mode)
            for issue in issues
            if issue.execution_mode in {"paper", "demo"}
        )
        state = self._update_state(
            issues=issues,
            observed_modes=observed_modes,
            observed_strategy_modes=observed_strategy_modes,
            operation=operation,
            run_summary=self._run_summary_from_payload(operation, payload),
        )
        self._write_state(state)
        self._render_document(state)
        return self._summary_from_state(state)

    def _issues_from_payload(self, payload: dict[str, Any]) -> tuple[list[RetrospectiveIssue], set[str], set[tuple[str, str]]]:
        issues: list[RetrospectiveIssue] = []
        observed_modes: set[str] = set()
        observed_strategy_modes: set[tuple[str, str]] = set()
        run = payload.get("strategy_run")
        if isinstance(run, dict):
            run_issues, run_modes, run_strategy_modes = self._issues_from_results(_as_dicts(run.get("results", [])))
            issues.extend(run_issues)
            observed_modes.update(run_modes)
            observed_strategy_modes.update(run_strategy_modes)
        for key, mode in (("local_validation", "paper"), ("demo_window_validation", "demo")):
            validation = payload.get(key)
            if isinstance(validation, dict):
                observed_modes.add(mode)
                strategy_name = str(validation.get("strategy_name", "all"))
                observed_strategy_modes.add((strategy_name, mode))
                issues.extend(self._issues_from_validation(validation, mode))
        post_run_open_risk = payload.get("post_run_open_risk")
        if isinstance(post_run_open_risk, dict):
            issues.extend(self._issues_from_open_risk(post_run_open_risk))
            observed_modes.add("demo")
        return issues, observed_modes, observed_strategy_modes

    def _issues_from_results(self, results: list[dict[str, Any]]) -> tuple[list[RetrospectiveIssue], set[str], set[tuple[str, str]]]:
        issues: list[RetrospectiveIssue] = []
        observed_modes: set[str] = set()
        observed_strategy_modes: set[tuple[str, str]] = set()
        latest_profitable_execution_index = _latest_profitable_execution_index(results)
        for index, result in enumerate(results):
            strategy_name = str(result.get("strategy_name", "unknown"))
            execution_mode = str(result.get("execution_mode", "unknown"))
            if execution_mode in {"paper", "demo"}:
                observed_modes.add(execution_mode)
                observed_strategy_modes.add((strategy_name, execution_mode))
            decision = str(result.get("decision", "skipped"))
            net_profit = _decimal(result.get("net_profit", "0"))
            risk_reasons = [str(item) for item in result.get("risk_reasons", []) if item is not None]
            raw_execution = result.get("execution")
            execution: dict[str, Any] = dict(raw_execution) if isinstance(raw_execution, dict) else {}
            recovered_by_later_profit = latest_profitable_execution_index.get((strategy_name, execution_mode), -1) > index
            context = {
                "cycle": result.get("cycle"),
                "decision": decision,
                "net_profit": str(net_profit),
                "message": result.get("message"),
                "selected_opportunity_id": result.get("selected_opportunity_id"),
            }
            if "demo_preflight_not_profitable" in risk_reasons and not recovered_by_later_profit:
                issues.append(
                    self._issue(
                        strategy_name,
                        execution_mode,
                        "preflight_not_profitable",
                        "demo_preflight_not_profitable",
                        "info",
                        context,
                    )
                )
            if decision == "blocked":
                issues.append(
                    self._issue(
                        strategy_name,
                        execution_mode,
                        "blocked_decision",
                        ",".join(risk_reasons) or "blocked",
                        "warning",
                        context,
                    )
                )
            if decision == "executed" and net_profit <= 0:
                issues.append(self._issue(strategy_name, execution_mode, "execution_loss", "net_profit_non_positive", "warning", context))
            abort_reason = str(execution.get("abort_reason") or "")
            if str(execution.get("status") or "") == "aborted_unwound" or abort_reason:
                issues.append(
                    self._issue(
                        strategy_name,
                        execution_mode,
                        "leg_not_filled_abort",
                        abort_reason or "aborted_unwound",
                        "warning",
                        {**context, "abort_reason": abort_reason},
                    )
                )
            raw_pnl_validation = execution.get("pnl_validation")
            pnl_validation: dict[str, Any] = dict(raw_pnl_validation) if isinstance(raw_pnl_validation, dict) else {}
            if pnl_validation:
                if pnl_validation.get("within_tolerance") is False:
                    issues.append(self._issue(strategy_name, execution_mode, "pnl_out_of_tolerance", "pnl_validation_failed", "critical", context))
                if pnl_validation.get("residual_inventory_within_tolerance") is False:
                    issues.append(
                        self._issue(strategy_name, execution_mode, "residual_inventory_out_of_tolerance", "residual_inventory_failed", "critical", context)
                    )
                raw_receipts = pnl_validation.get("exchange_receipts")
                receipts: dict[str, Any] = dict(raw_receipts) if isinstance(raw_receipts, dict) else {}
                if receipts.get("complete") is False:
                    issues.append(self._issue(strategy_name, execution_mode, "receipt_incomplete", "exchange_receipts_incomplete", "critical", context))
            for reason in risk_reasons:
                if "market_data" in reason and not recovered_by_later_profit:
                    issues.append(self._issue(strategy_name, execution_mode, "market_data_failure", reason, "warning", context))
                if "rate_limit" in reason and not recovered_by_later_profit:
                    issues.append(self._issue(strategy_name, execution_mode, "rate_limit_failure", reason, "warning", context))
        return issues, observed_modes, observed_strategy_modes

    def _issues_from_validation(self, validation: dict[str, Any], execution_mode: str) -> list[RetrospectiveIssue]:
        strategy_name = str(validation.get("strategy_name", "all"))
        issues: list[RetrospectiveIssue] = []
        for reason in [str(item) for item in validation.get("reasons", []) if item is not None]:
            category = "insufficient_samples" if reason.startswith("minimum_samples_not_met") else "validation_failed"
            severity: Severity = "info" if category == "insufficient_samples" else "warning"
            issues.append(self._issue(strategy_name, execution_mode, category, reason, severity, {"status": validation.get("status")}))
        return issues

    def _issues_from_open_risk(self, open_risk: dict[str, Any]) -> list[RetrospectiveIssue]:
        if not open_risk.get("checked"):
            return []
        open_spot = int(open_risk.get("open_spot_orders", 0) or 0)
        open_swap = int(open_risk.get("open_swap_orders", 0) or 0)
        swap_positions = int(open_risk.get("swap_positions", 0) or 0)
        if open_spot == 0 and open_swap == 0 and swap_positions == 0:
            return []
        return [
            self._issue(
                "all",
                "demo",
                "open_risk_after_run",
                "post_run_open_risk_nonzero",
                "critical",
                {
                    "open_spot_orders": open_spot,
                    "open_swap_orders": open_swap,
                    "swap_positions": swap_positions,
                },
            )
        ]

    def _guard_issues(self) -> list[RetrospectiveIssue]:
        issues: list[RetrospectiveIssue] = []
        for entry in StrategyRuntimeGuard(self.config).status()["entries"]:
            if not entry.get("cooldown_active"):
                continue
            issues.append(
                self._issue(
                    str(entry.get("strategy_name", "unknown")),
                    str(entry.get("execution_mode", "unknown")),
                    "runtime_guard_cooldown",
                    str(entry.get("last_reason") or "runtime_guard_cooldown"),
                    "critical",
                    {"cooldown_until": entry.get("cooldown_until"), "last_net_profit": entry.get("last_net_profit")},
                )
            )
        return issues

    def _issue(
        self,
        strategy_name: str,
        execution_mode: str,
        category: str,
        reason: str,
        severity: Severity,
        context: dict[str, Any],
    ) -> RetrospectiveIssue:
        dedupe_key = "|".join([strategy_name, execution_mode, category, reason])
        issue_id = "ri-" + hashlib.sha1(dedupe_key.encode("utf-8")).hexdigest()[:12]
        return RetrospectiveIssue(
            issue_id=issue_id,
            dedupe_key=dedupe_key,
            strategy_name=strategy_name,
            execution_mode=execution_mode,
            category=category,
            reason=reason,
            severity=severity,
            recommendation=_recommendation(category),
            last_context=context,
        )

    def _update_state(
        self,
        issues: list[RetrospectiveIssue],
        observed_modes: set[str],
        observed_strategy_modes: set[tuple[str, str]],
        operation: str,
        run_summary: dict[str, Any],
        increment_occurrences: bool = True,
    ) -> dict[str, Any]:
        state = self._load_state()
        now = _now_iso()
        existing = {str(key): dict(value) for key, value in state.get("issues", {}).items() if isinstance(value, dict)}
        issue_counts = Counter(issue.dedupe_key for issue in issues)
        latest_issues = {issue.dedupe_key: issue for issue in issues}
        observed_keys = set(latest_issues)
        for dedupe_key, issue in latest_issues.items():
            current = dict(existing.get(dedupe_key, issue.to_dict()))
            previous_occurrences = int(current.get("occurrences", 0)) if dedupe_key in existing else 0
            occurrences = (
                previous_occurrences + issue_counts[dedupe_key]
                if increment_occurrences
                else max(previous_occurrences, issue_counts[dedupe_key])
            )
            severity = _max_severity(str(current.get("severity", issue.severity)), issue.severity)
            if occurrences >= self.config.retrospective_repeat_warning_threshold and severity == "info":
                severity = "warning"
            current.update(
                {
                    **issue.to_dict(),
                    "severity": severity,
                    "status": "open",
                    "occurrences": occurrences,
                    "first_seen_at": current.get("first_seen_at", now),
                    "last_seen_at": now,
                }
            )
            existing[dedupe_key] = current
        for key, current in list(existing.items()):
            if current.get("status") != "open":
                continue
            current_mode = str(current.get("execution_mode"))
            if current_mode not in observed_modes:
                continue
            current_strategy = str(current.get("strategy_name"))
            if (current_strategy, current_mode) not in observed_strategy_modes and ("all", current_mode) not in observed_strategy_modes:
                continue
            if key not in observed_keys:
                current["status"] = "improved"
                current["improved_at"] = now
                existing[key] = current
        recent_runs = [dict(item) for item in state.get("recent_runs", []) if isinstance(item, dict)]
        recent_runs.insert(
            0,
            {
                "operation": operation,
                "created_at": now,
                "observed_issue_count": len(issues),
                "observed_modes": sorted(observed_modes),
                "observed_strategy_modes": [f"{strategy}:{mode}" for strategy, mode in sorted(observed_strategy_modes)],
                "summary": run_summary,
            },
        )
        return {
            "version": 1,
            "updated_at": now,
            "issues": existing,
            "recent_runs": recent_runs[:20],
        }

    def _run_summary_from_payload(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        raw_run = payload.get("strategy_run")
        run: dict[str, Any] = dict(raw_run) if isinstance(raw_run, dict) else {}
        raw_validation = payload.get("demo_window_validation") or payload.get("local_validation")
        validation: dict[str, Any] = dict(raw_validation) if isinstance(raw_validation, dict) else {}
        raw_metrics = validation.get("metrics")
        metrics: dict[str, Any] = dict(raw_metrics) if isinstance(raw_metrics, dict) else {}
        return {
            "operation": operation,
            "run_completed": run.get("completed"),
            "cycles_completed": run.get("cycles_completed"),
            "execution_mode": run.get("execution_mode"),
            "validation_status": validation.get("status"),
            "executed": metrics.get("executed"),
            "skipped": metrics.get("skipped"),
            "net_profit": metrics.get("net_profit") or run.get("demo_cumulative_net_pnl"),
        }

    def _summary_from_state(self, state: dict[str, Any]) -> dict[str, Any]:
        issues = [dict(item) for item in state.get("issues", {}).values() if isinstance(item, dict)]
        open_issues = [item for item in issues if item.get("status") == "open"]
        repeated = [item for item in open_issues if int(item.get("occurrences", 0)) >= self.config.retrospective_repeat_warning_threshold]
        highest = _highest_severity(open_issues)
        return {
            "enabled": self.config.retrospective_enabled,
            "retrospective_path": str(self.document_path),
            "state_path": str(self.state_path),
            "open_issue_count": len(open_issues),
            "repeated_issue_count": len(repeated),
            "highest_severity": highest,
            "top_open_issues": [
                _public_issue(item)
                for item in sorted(open_issues, key=lambda issue: (_severity_rank(str(issue.get("severity", "info"))), int(issue.get("occurrences", 0))), reverse=True)[:5]
            ],
            "next_run_checklist": _next_run_checklist(open_issues),
            "optimization_pressure": _optimization_pressure(open_issues, self.config.retrospective_repeat_warning_threshold),
            "updated_at": state.get("updated_at"),
        }

    def _disabled_summary(self) -> dict[str, Any]:
        return {
            "enabled": False,
            "retrospective_path": str(self.document_path),
            "state_path": str(self.state_path),
            "open_issue_count": 0,
            "repeated_issue_count": 0,
            "highest_severity": None,
            "top_open_issues": [],
            "next_run_checklist": [],
            "optimization_pressure": [],
            "updated_at": None,
        }

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"version": 1, "updated_at": None, "issues": {}, "recent_runs": []}
        payload = json.loads(self.state_path.read_text(encoding="utf-8") or "{}")
        if not isinstance(payload, dict):
            return {"version": 1, "updated_at": None, "issues": {}, "recent_runs": []}
        payload.setdefault("issues", {})
        payload.setdefault("recent_runs", [])
        return payload

    def _write_state(self, state: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(to_jsonable(state), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _render_document(self, state: dict[str, Any]) -> None:
        self.document_path.parent.mkdir(parents=True, exist_ok=True)
        manual_notes = _extract_manual_notes(self.document_path)
        issues = [dict(item) for item in state.get("issues", {}).values() if isinstance(item, dict)]
        open_issues = [item for item in issues if item.get("status") == "open"]
        repeated = [item for item in open_issues if int(item.get("occurrences", 0)) >= self.config.retrospective_repeat_warning_threshold]
        improved = [item for item in issues if item.get("status") == "improved"]
        content = "\n".join(
            [
                "# Strategy Retrospective",
                "",
                f"Last updated: {state.get('updated_at') or _now_iso()}",
                "",
                "This document is auto-updated after strategy execution and validation. It is advisory and never enables live trading.",
                "",
                "## Current Open Issues",
                "",
                _issue_table(open_issues, empty="No open issues recorded."),
                "",
                "## Repeated Issues",
                "",
                _issue_table(repeated, empty="No repeated issues above the configured threshold."),
                "",
                "## Improved Issues",
                "",
                _issue_table(improved[:20], empty="No improved issues recorded yet."),
                "",
                "## Next Run Checklist",
                "",
                _checklist_markdown(_next_run_checklist(open_issues)),
                "",
                "## Test Evolution Pressure",
                "",
                _test_pressure_markdown(open_issues),
                "",
                "## Strategy Optimization Pressure",
                "",
                _optimization_pressure_markdown(_optimization_pressure(open_issues, self.config.retrospective_repeat_warning_threshold)),
                "",
                "## Recent Run Summary",
                "",
                _recent_runs_markdown(_as_dicts(state.get("recent_runs", []))[:10]),
                "",
                "## Manual Notes",
                "",
                MANUAL_START,
                manual_notes,
                MANUAL_END,
                "",
            ]
        )
        self.document_path.write_text(content, encoding="utf-8")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _as_dicts(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    return [dict(item) for item in values if isinstance(item, dict)]


def _latest_profitable_execution_index(results: list[dict[str, Any]]) -> dict[tuple[str, str], int]:
    latest: dict[tuple[str, str], int] = {}
    for index, result in enumerate(results):
        strategy_name = str(result.get("strategy_name", "unknown"))
        execution_mode = str(result.get("execution_mode", "unknown"))
        if str(result.get("decision", "skipped")) == "executed" and _decimal(result.get("net_profit", "0")) > 0:
            latest[(strategy_name, execution_mode)] = index
    return latest


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _max_severity(first: str, second: str) -> Severity:
    return _severity_from_rank(max(_severity_rank(first), _severity_rank(second)))


def _highest_severity(issues: list[dict[str, Any]]) -> str | None:
    if not issues:
        return None
    return _severity_from_rank(max(_severity_rank(str(issue.get("severity", "info"))) for issue in issues))


def _severity_rank(severity: str) -> int:
    return {"info": 1, "warning": 2, "critical": 3}.get(severity, 1)


def _severity_from_rank(rank: int) -> Severity:
    if rank >= 3:
        return "critical"
    if rank == 2:
        return "warning"
    return "info"


def _public_issue(issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "issue_id": issue.get("issue_id"),
        "strategy_name": issue.get("strategy_name"),
        "execution_mode": issue.get("execution_mode"),
        "category": issue.get("category"),
        "reason": issue.get("reason"),
        "severity": issue.get("severity"),
        "status": issue.get("status"),
        "occurrences": issue.get("occurrences"),
        "last_seen_at": issue.get("last_seen_at"),
        "recommendation": issue.get("recommendation"),
    }


def _recommendation(category: str) -> str:
    recommendations = {
        "preflight_not_profitable": "Do not force demo orders; wait for a profitable preflight or improve scanner pricing.",
        "execution_loss": "Keep size unchanged and inspect fees, slippage, fills, and route assumptions before rerunning.",
        "leg_not_filled_abort": "Review leg marketability, orderbook depth, and unwind evidence before another demo window.",
        "receipt_incomplete": "Do not increase size until OKX fills-history evidence is complete for every executed order.",
        "pnl_out_of_tolerance": "Investigate account-equity delta versus order cash-flow before trusting the PnL sample.",
        "residual_inventory_out_of_tolerance": "Reduce or unwind residual inventory before any further autonomy or size increase.",
        "open_risk_after_run": "Clear open orders or positions and verify account state before the next run.",
        "runtime_guard_cooldown": "Respect the runtime guard cooldown and inspect the last failure reason.",
        "insufficient_samples": "Collect more local/demo samples before promotion or size decisions.",
        "blocked_decision": "Inspect risk and budget reasons before changing thresholds or increasing autonomy.",
        "market_data_failure": "Wait for healthy market data or reduce polling before rerunning.",
        "rate_limit_failure": "Back off API usage and keep guard cooldowns intact.",
    }
    return recommendations.get(category, "Review this issue before the next strategy execution.")


def _next_run_checklist(open_issues: list[dict[str, Any]]) -> list[str]:
    checklist = [
        "Run local validation before any OKX Demo Trading window.",
        "Check strategy guard status before repeated demo execution.",
        "Keep live trading and live-canary gates disabled unless a separate approval explicitly changes them.",
    ]
    categories = {str(issue.get("category")) for issue in open_issues}
    if "preflight_not_profitable" in categories:
        checklist.append("Do not force strategies that are currently skipped by demo_preflight_not_profitable.")
    if "leg_not_filled_abort" in categories:
        checklist.append("Review triangular leg fill reliability and unwind evidence before another size change.")
    if {"receipt_incomplete", "pnl_out_of_tolerance", "residual_inventory_out_of_tolerance", "open_risk_after_run"} & categories:
        checklist.append("Resolve receipt, PnL, residual inventory, or open-risk evidence before increasing demo size.")
    if "insufficient_samples" in categories:
        checklist.append("Collect enough samples to satisfy validation_min_* thresholds before promotion decisions.")
    return checklist


def _issue_table(issues: list[dict[str, Any]], empty: str) -> str:
    if not issues:
        return empty
    rows = ["| ID | Strategy | Mode | Category | Severity | Occurrences | Last Seen | Recommendation |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for issue in sorted(issues, key=lambda item: (_severity_rank(str(item.get("severity", "info"))), int(item.get("occurrences", 0))), reverse=True):
        rows.append(
            "| {issue_id} | {strategy} | {mode} | {category} | {severity} | {occurrences} | {last_seen} | {recommendation} |".format(
                issue_id=issue.get("issue_id", ""),
                strategy=issue.get("strategy_name", ""),
                mode=issue.get("execution_mode", ""),
                category=issue.get("category", ""),
                severity=issue.get("severity", ""),
                occurrences=issue.get("occurrences", ""),
                last_seen=issue.get("last_seen_at", ""),
                recommendation=str(issue.get("recommendation", "")).replace("|", "/"),
            )
        )
    return "\n".join(rows)


def _checklist_markdown(items: list[str]) -> str:
    return "\n".join(f"- [ ] {item}" for item in items) if items else "- [x] No open retrospective checklist items."


def _test_pressure_markdown(open_issues: list[dict[str, Any]]) -> str:
    categories = {str(issue.get("category")) for issue in open_issues}
    if not categories:
        return "- Current tests should continue covering the clean path; no new pressure item is active."
    lines = []
    if "preflight_not_profitable" in categories:
        lines.append("- Add or keep tests proving negative preflight skips before any demo order is submitted.")
    if "leg_not_filled_abort" in categories:
        lines.append("- Add or keep tests proving unfilled legs abort and unwind without continuing the route.")
    if "receipt_incomplete" in categories:
        lines.append("- Add or keep tests proving incomplete exchange receipts block escalation decisions.")
    if "pnl_out_of_tolerance" in categories or "residual_inventory_out_of_tolerance" in categories:
        lines.append("- Add or keep tests proving PnL and residual-inventory failures appear in validation output.")
    if "open_risk_after_run" in categories:
        lines.append("- Add or keep tests proving nonzero post-run open risk is surfaced before promotion.")
    return "\n".join(lines) if lines else "- Keep regression tests aligned with the open retrospective issues."


def _optimization_pressure(open_issues: list[dict[str, Any]], repeat_threshold: int) -> list[dict[str, Any]]:
    """Return strategy-specific optimization pressure from open retrospective issues."""
    pressure: list[dict[str, Any]] = []
    for issue in sorted(open_issues, key=lambda item: int(item.get("occurrences", 0)), reverse=True):
        category = str(issue.get("category", ""))
        strategy_name = str(issue.get("strategy_name", "unknown"))
        occurrences = int(issue.get("occurrences", 0))
        if category == "preflight_not_profitable":
            last_context = _issue_context(issue)
            observed_net = _decimal(last_context.get("net_profit", "0"))
            gap = max(-observed_net, Decimal("0"))
            pressure.append(
                {
                    "strategy_name": strategy_name,
                    "execution_mode": str(issue.get("execution_mode", "")),
                    "category": category,
                    "priority": "high" if occurrences >= repeat_threshold else "normal",
                    "occurrences": occurrences,
                    "observed_net_profit_usdt": str(observed_net),
                    "break_even_gap_usdt": str(gap),
                    "action": _preflight_optimization_action(strategy_name),
                    "suggested_config_fields": _preflight_config_fields(strategy_name),
                    "guardrails": [
                        "do_not_lower_demo_min_preflight_net_pnl_below_zero",
                        "do_not_force_demo_orders_when_preflight_is_negative",
                        "rerun_strategy_validate_local_before_okx_demo",
                        "do_not_increase_demo_size_until_repeated_clean_passes",
                    ],
                }
            )
        elif category in {"pnl_out_of_tolerance", "receipt_incomplete", "residual_inventory_out_of_tolerance", "open_risk_after_run"}:
            pressure.append(
                {
                    "strategy_name": strategy_name,
                    "execution_mode": str(issue.get("execution_mode", "")),
                    "category": category,
                    "priority": "critical",
                    "occurrences": occurrences,
                    "observed_net_profit_usdt": str(_decimal(_issue_context(issue).get("net_profit", "0"))),
                    "break_even_gap_usdt": "0",
                    "action": "Resolve execution evidence quality before changing thresholds or increasing size.",
                    "suggested_config_fields": [
                        "strategy_runtime.demo_pnl_reconciliation_tolerance_usdt",
                        "strategy_runtime.demo_residual_inventory_tolerance_usdt",
                    ],
                    "guardrails": [
                        "do_not_treat_incomplete_receipts_as_success",
                        "clear_open_orders_and_positions_before_next_window",
                        "keep_live_canary_disabled",
                    ],
                }
            )
    return pressure


def _issue_context(issue: dict[str, Any]) -> dict[str, Any]:
    """Return issue context as a dict."""
    context = issue.get("last_context")
    return dict(context) if isinstance(context, dict) else {}


def _preflight_optimization_action(strategy_name: str) -> str:
    """Return a concrete safe optimization action for a negative demo preflight."""
    actions = {
        "cross-exchange": (
            "Keep OKX demo orders blocked until scanner emits a venue-pair spread that remains positive after fees, "
            "transfer cost, latency drift, and sell-leg availability checks."
        ),
        "funding-carry-hedged": (
            "Rank funding symbols and require projected next-window funding to exceed hedge cost, fees, slippage, "
            "and the observed break-even gap before demo execution."
        ),
        "spot-perp-carry": (
            "Require positive spot/perp basis plus projected funding carry to exceed entry/exit fees, slippage, "
            "holding cost, and the observed break-even gap before demo execution."
        ),
        "futures-perp-basis": (
            "Require dated-futures/perp basis to exceed fees, slippage, holding cost, and the observed break-even gap; "
            "treat flat or unavailable futures basis as wait."
        ),
    }
    return actions.get(strategy_name, "Keep demo orders blocked until current scanner edge is net-positive after all configured costs.")


def _preflight_config_fields(strategy_name: str) -> list[str]:
    """Return configuration fields worth reviewing for a negative preflight issue."""
    base = [
        "strategy_runtime.demo_min_preflight_net_pnl_usdt",
        "arbitrage.min_net_profit_pct",
        "arbitrage.taker_fee_pct",
        "arbitrage.slippage_pct",
    ]
    if strategy_name in {"funding-carry-hedged", "spot-perp-carry"}:
        return [
            *base,
            "arbitrage.funding_holding_hours",
            "arbitrage.funding_settlement_interval_hours",
            "arbitrage.funding_hedge_cost_pct",
            "arbitrage.basis_holding_hours",
        ]
    if strategy_name == "futures-perp-basis":
        return [
            *base,
            "arbitrage.basis_holding_hours",
            "arbitrage.futures_basis_min_days_to_expiry",
        ]
    if strategy_name == "cross-exchange":
        return [
            *base,
            "arbitrage.withdrawal_fee_usdt",
            "arbitrage.transfer_delay_risk_pct",
            "arbitrage.min_spread_persistence_pct",
        ]
    return base


def _optimization_pressure_markdown(items: list[dict[str, Any]]) -> str:
    """Render optimization pressure items as Markdown."""
    if not items:
        return "- No strategy optimization pressure is active."
    rows = [
        "| Strategy | Category | Priority | Occurrences | Break-even Gap USDT | Action | Guardrails |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in items:
        rows.append(
            "| {strategy} | {category} | {priority} | {occurrences} | {gap} | {action} | {guardrails} |".format(
                strategy=item.get("strategy_name", ""),
                category=item.get("category", ""),
                priority=item.get("priority", ""),
                occurrences=item.get("occurrences", ""),
                gap=item.get("break_even_gap_usdt", ""),
                action=str(item.get("action", "")).replace("|", "/"),
                guardrails=", ".join(str(value) for value in item.get("guardrails", [])).replace("|", "/"),
            )
        )
    return "\n".join(rows)


def _recent_runs_markdown(recent_runs: list[dict[str, Any]]) -> str:
    if not recent_runs:
        return "No retrospective run summaries recorded yet."
    rows = ["| Time | Operation | Issues | Modes | Summary |", "| --- | --- | --- | --- | --- |"]
    for item in recent_runs:
        rows.append(
            "| {time} | {operation} | {issues} | {modes} | {summary} |".format(
                time=item.get("created_at", ""),
                operation=item.get("operation", ""),
                issues=item.get("observed_issue_count", 0),
                modes=",".join(str(mode) for mode in item.get("observed_modes", [])),
                summary=json.dumps(item.get("summary", {}), ensure_ascii=False, sort_keys=True).replace("|", "/"),
            )
        )
    return "\n".join(rows)


def _extract_manual_notes(path: Path) -> str:
    if not path.exists():
        return "No manual notes yet."
    text = path.read_text(encoding="utf-8")
    if MANUAL_START not in text or MANUAL_END not in text:
        return "No manual notes yet."
    return text.split(MANUAL_START, 1)[1].split(MANUAL_END, 1)[0].strip() or "No manual notes yet."
