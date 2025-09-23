#!/usr/bin/env python3
"""
Test script for entity-specific tag constraint functionality.
Tests the scope-aware filtering logic in api_v2.models.tag
"""

from datetime import datetime, timedelta, UTC
from unittest.mock import patch, Mock

from api_v2.models.tag import coalesce_constraints_with_scope, coalesce_ended_at


class MockTag:
    """Mock Tag for testing without database dependencies"""
    def __init__(self, enabled=True, constraints=None):
        self.enabled = enabled
        self.constraints = constraints or {}


@patch('api_v2.models.tag.get_settings')
def test_scope_aware_filtering_mixed_scopes(mock_get_settings):
    """Test mixed entity scopes: users get 1 day, roles get 7 days"""
    # Enable feature flag
    mock_settings = Mock()
    mock_settings.enable_entity_specific_constraints = True
    mock_get_settings.return_value = mock_settings

    # Tag A: 1 day for users, Tag B: 7 days for roles
    tags = [
        MockTag(constraints={"member_time_limit": 86400, "member_time_limit_scope": "users_only"}),
        MockTag(constraints={"member_time_limit": 604800, "member_time_limit_scope": "roles_only"})
    ]

    user_result = coalesce_constraints_with_scope("member_time_limit", tags, "user")
    role_result = coalesce_constraints_with_scope("member_time_limit", tags, "role")

    assert user_result == 86400  # 1 day
    assert role_result == 604800  # 7 days


@patch('api_v2.models.tag.get_settings')
def test_scope_aware_filtering_same_entity(mock_get_settings):
    """Test multiple constraints for same entity: users get min, roles get nothing"""
    # Enable feature flag
    mock_settings = Mock()
    mock_settings.enable_entity_specific_constraints = True
    mock_get_settings.return_value = mock_settings

    # Both tags target users with different limits
    tags = [
        MockTag(constraints={"member_time_limit": 86400, "member_time_limit_scope": "users_only"}),
        MockTag(constraints={"member_time_limit": 604800, "member_time_limit_scope": "users_only"})
    ]

    user_result = coalesce_constraints_with_scope("member_time_limit", tags, "user")
    role_result = coalesce_constraints_with_scope("member_time_limit", tags, "role")

    assert user_result == 86400  # min(86400, 604800)
    assert role_result is None  # no applicable constraints


@patch('api_v2.models.tag.get_settings')
def test_feature_flag_disabled(mock_get_settings):
    """Test that disabled feature flag falls back to traditional coalescing"""
    # Disable feature flag
    mock_settings = Mock()
    mock_settings.enable_entity_specific_constraints = False
    mock_get_settings.return_value = mock_settings

    # Mixed scope tags
    tags = [
        MockTag(constraints={"member_time_limit": 86400, "member_time_limit_scope": "users_only"}),
        MockTag(constraints={"member_time_limit": 604800, "member_time_limit_scope": "roles_only"})
    ]

    user_result = coalesce_constraints_with_scope("member_time_limit", tags, "user")
    role_result = coalesce_constraints_with_scope("member_time_limit", tags, "role")

    # Both should get same result when feature disabled
    assert user_result == 86400  # min(86400, 604800)
    assert role_result == 86400  # same as user


@patch('api_v2.models.tag.get_settings')
def test_default_scope_backward_compatibility(mock_get_settings):
    """Test that missing scope defaults to 'both'"""
    # Enable feature flag
    mock_settings = Mock()
    mock_settings.enable_entity_specific_constraints = True
    mock_get_settings.return_value = mock_settings

    # Tag without scope (should default to "both")
    tags = [MockTag(constraints={"member_time_limit": 86400})]  # No scope

    user_result = coalesce_constraints_with_scope("member_time_limit", tags, "user")
    role_result = coalesce_constraints_with_scope("member_time_limit", tags, "role")

    assert user_result == 86400
    assert role_result == 86400


@patch('api_v2.models.tag.get_settings')
def test_coalesce_ended_at_with_entity_type(mock_get_settings):
    """Test coalesce_ended_at respects entity_type parameter"""
    # Enable feature flag
    mock_settings = Mock()
    mock_settings.enable_entity_specific_constraints = True
    mock_get_settings.return_value = mock_settings

    # User-only constraint
    tags = [MockTag(constraints={"member_time_limit": 86400, "member_time_limit_scope": "users_only"})]

    base_time = datetime.now(UTC)

    # Users should get constraint applied
    user_result = coalesce_ended_at("member_time_limit", tags, None, True, "user")
    assert user_result is not None
    assert user_result > base_time

    # Roles should get no constraint
    role_result = coalesce_ended_at("member_time_limit", tags, None, True, "role")
    assert role_result is None


def test_empty_tags():
    """Test behavior with empty tags list"""
    result = coalesce_constraints_with_scope("member_time_limit", [], "user")
    assert result is None


def test_disabled_tags_ignored():
    """Test that disabled tags are ignored"""
    tags = [
        MockTag(enabled=True, constraints={"member_time_limit": 86400}),
        MockTag(enabled=False, constraints={"member_time_limit": 3600})  # Should be ignored
    ]

    with patch('api_v2.models.tag.get_settings') as mock_get_settings:
        mock_settings = Mock()
        mock_settings.enable_entity_specific_constraints = True
        mock_get_settings.return_value = mock_settings

        result = coalesce_constraints_with_scope("member_time_limit", tags, "user")
        assert result == 86400  # Not 3600 from disabled tag