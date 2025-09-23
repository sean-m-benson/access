"""
Tag helper functions for FastAPI.
Pure implementation without Flask dependencies.
"""

from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from api_v2.config import get_settings
from api_v2.models.core_models import Tag


def coalesce_constraints(constraint_key: str, tags: list[Tag]) -> Any:
    """Coalesce constraint values from multiple tags"""
    coalesced_constraint_value = None
    constraint = Tag.CONSTRAINTS[constraint_key]
    for tag in tags:
        if tag.enabled and constraint_key in tag.constraints:
            if coalesced_constraint_value is None:
                coalesced_constraint_value = tag.constraints[constraint_key]
            else:
                coalesced_constraint_value = constraint.coalesce(
                    coalesced_constraint_value, tag.constraints[constraint_key]
                )
    return coalesced_constraint_value


def coalesce_constraints_with_scope(
    constraint_key: str,
    tags: list[Tag],
    entity_type: str = "user"
) -> Any:
    """
    Coalesce constraint values with scope pre-filtering for entity-specific constraints.

    Args:
        constraint_key: The constraint to coalesce (e.g., "member_time_limit")
        tags: List of tags to consider
        entity_type: "user" or "role" - filters constraints by scope

    Returns:
        Coalesced constraint value, or None if no applicable constraints
    """
    settings = get_settings()

    # If entity-specific constraints are disabled, use traditional coalescing
    if not settings.enable_entity_specific_constraints:
        return coalesce_constraints(constraint_key, tags)

    # Filter constraints by scope before coalescing
    applicable_constraints = []
    constraint = Tag.CONSTRAINTS[constraint_key]
    scope_key = f"{constraint_key}_scope"

    for tag in tags:
        if tag.enabled and constraint_key in tag.constraints:
            # Get the scope for this constraint (default to "both" for backward compatibility)
            scope = tag.constraints.get(scope_key, "both")

            # Apply constraint if scope matches or is "both"
            if scope == "both" or scope == f"{entity_type}s_only":
                applicable_constraints.append(tag.constraints[constraint_key])

    # Coalesce only the applicable constraints
    if not applicable_constraints:
        return None

    coalesced_value = applicable_constraints[0]
    for constraint_value in applicable_constraints[1:]:
        coalesced_value = constraint.coalesce(coalesced_value, constraint_value)

    return coalesced_value


def coalesce_ended_at(
    constraint_key: str,
    tags: list[Tag],
    initial_ended_at: Optional[datetime],
    group_is_managed: bool,
    entity_type: str = "user",
) -> Optional[datetime]:
    """
    Calculate the effective ended_at timestamp based on tag constraints.
    Supports entity-specific constraints when feature flag is enabled.

    Args:
        constraint_key: The constraint to apply (e.g., "member_time_limit")
        tags: List of tags to consider
        initial_ended_at: Initial ended_at value to compare against
        group_is_managed: Only apply constraints if the group is managed
        entity_type: "user" or "role" - enables scope-aware filtering

    Returns:
        The most restrictive ended_at timestamp, or initial_ended_at if no constraints apply
    """
    if not group_is_managed:
        return initial_ended_at

    # Use scope-aware coalescing (falls back to traditional if feature disabled)
    seconds_limit = coalesce_constraints_with_scope(
        constraint_key=constraint_key,
        tags=tags,
        entity_type=entity_type
    )

    if seconds_limit is None:
        return initial_ended_at
    else:
        constraint_ended_at = datetime.now(UTC) + timedelta(seconds=seconds_limit)
        if initial_ended_at is None:
            return constraint_ended_at
        else:
            return min(constraint_ended_at, initial_ended_at.replace(tzinfo=UTC))