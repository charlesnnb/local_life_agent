"""Validate whether a place candidate can satisfy one planned task."""

from dataclasses import dataclass, field

from src.core.task_category import (
    CATEGORY_RULES,
    normalize_task_category,
    task_text_for_category,
)
from src.schemas.models import PlannedTask


@dataclass(frozen=True)
class CandidateValidation:
    is_relevant: bool
    relevance_score: float
    reason: str
    matched_terms: list[str] = field(default_factory=list)
    excluded_terms: list[str] = field(default_factory=list)
    negative_terms: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    category: str = "unknown"


def validate_candidate(
    candidate: dict,
    task: PlannedTask,
) -> CandidateValidation:
    """Return strict task relevance before preference scoring is applied."""
    task_text = task_text_for_category(task)
    candidate_text = _candidate_text(candidate)
    category = normalize_task_category(task)

    if task.target in {"休闲活动", "亲子活动"}:
        return _validation(
            True,
            0.65,
            "通用活动候选",
            category=category,
        )

    rule = CATEGORY_RULES.get(category)
    if rule is None:
        target = (task.target or "").strip().lower()
        if not target or target in candidate_text:
            return _validation(
                True,
                0.8 if target else 0.6,
                "候选与任务目标匹配",
                matched_terms=[target] if target else [],
                category=category,
            )
        return _validation(
            False,
            0.0,
            f"不符合{task.target or '当前'}任务，未命中目标词“{target}”",
            category=category,
        )

    excluded = [
        word for word in rule["negative"] if word.lower() in candidate_text
    ]
    matched = [
        word for word in rule["positive"] if word.lower() in candidate_text
    ]

    if excluded:
        return _validation(
            False,
            0.0,
            (
                f"不符合{task.target or task.description}任务，"
                f"命中排除词“{'、'.join(excluded)}”"
            ),
            matched_terms=matched,
            negative_terms=excluded,
            category=category,
        )
    if not matched:
        return _validation(
            False,
            0.0,
            (
                f"不符合{task.target or task.description}任务，"
                "未命中相关地点类型"
            ),
            category=category,
        )

    score = min(1.0, 0.72 + 0.1 * len(set(matched)))
    if category == "bar" and _is_hotel_lobby(candidate_text):
        explicitly_wants_hotel = any(
            word in task_text for word in ("高档酒店", "酒店酒廊", "大堂吧")
        )
        if not explicitly_wants_hotel:
            score = min(score, 0.55)
            return _validation(
                True,
                score,
                "属于酒吧候选，但普通酒吧查询降低酒店大堂吧优先级",
                matched_terms=matched,
                category=category,
            )

    return _validation(
        True,
        score,
        f"命中任务相关词：{'、'.join(matched)}",
        matched_terms=matched,
        category=category,
    )


def _validation(
    is_relevant: bool,
    relevance_score: float,
    reason: str,
    matched_terms: list[str] | None = None,
    negative_terms: list[str] | None = None,
    category: str = "unknown",
) -> CandidateValidation:
    matched = list(dict.fromkeys(matched_terms or []))
    negative = list(dict.fromkeys(negative_terms or []))
    return CandidateValidation(
        is_relevant=is_relevant,
        relevance_score=relevance_score,
        reason=reason,
        matched_terms=matched,
        excluded_terms=negative,
        negative_terms=negative,
        reasons=[reason],
        category=category,
    )


def _candidate_text(candidate: dict) -> str:
    tags = " ".join(str(tag) for tag in candidate.get("tags", []))
    return " ".join(
        str(value or "").lower()
        for value in (
            candidate.get("name"),
            candidate.get("type"),
            candidate.get("address"),
            tags,
        )
    )


def _is_hotel_lobby(candidate_text: str) -> bool:
    return any(
        hotel_word in candidate_text
        for hotel_word in ("酒店", "宾馆", "hotel")
    ) and any(
        word in candidate_text for word in ("大堂吧", "酒廊", "lounge")
    )
