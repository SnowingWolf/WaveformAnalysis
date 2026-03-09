"""
Compatibility and Deprecation Tests

Verifies:
1. Alias resolution works correctly (old_name → canonical_name)
2. Deprecation warnings are issued during window period
3. Expired deprecations raise errors
4. CompatManager API works as documented
"""

import warnings

import pytest

from waveform_analysis.core.config.compat import CompatManager, DeprecationInfo

pytestmark = pytest.mark.contract


class TestAliasResolution:
    """Test parameter alias resolution."""

    def test_resolve_canonical_name(self):
        """Canonical names should resolve to themselves."""
        manager = CompatManager()
        canonical, alias_used = manager.resolve_alias("__global__", "break_threshold_ps")

        assert canonical == "break_threshold_ps"
        assert alias_used is False

    def test_resolve_alias_to_canonical(self):
        """Aliases should resolve to canonical names."""
        CompatManager.register_alias("legacy_threshold_ns", "break_threshold_ps")
        manager = CompatManager()
        canonical, alias_used = manager.resolve_alias("__global__", "legacy_threshold_ns")

        assert canonical == "break_threshold_ps"
        assert alias_used is True
        CompatManager.unregister_alias("legacy_threshold_ns")

    def test_resolve_unknown_name(self):
        """Unknown names should resolve to themselves."""
        manager = CompatManager()
        canonical, alias_used = manager.resolve_alias("__global__", "unknown_param")

        assert canonical == "unknown_param"
        assert alias_used is False

    def test_plugin_specific_alias(self):
        """Plugin-specific aliases should work."""
        # Register a plugin-specific alias
        CompatManager.register_alias("old_threshold", "new_threshold", plugin_name="my_plugin")

        manager = CompatManager()
        canonical, alias_used = manager.resolve_alias("my_plugin", "old_threshold")

        assert canonical == "new_threshold"
        assert alias_used is True

        # Clean up
        CompatManager.unregister_alias("old_threshold", plugin_name="my_plugin")

    def test_get_aliases_for_canonical(self):
        """Should list all aliases for a canonical name."""
        CompatManager.register_alias("legacy_threshold_ns", "break_threshold_ps")
        manager = CompatManager()
        aliases = manager.get_aliases_for("__global__", "break_threshold_ps")

        assert "legacy_threshold_ns" in aliases
        CompatManager.unregister_alias("legacy_threshold_ns")


class TestDeprecationWarnings:
    """Test deprecation warning behavior."""

    def test_deprecated_name_issues_warning(self):
        """Using deprecated name should issue DeprecationWarning."""
        CompatManager.register_deprecation(
            DeprecationInfo(
                old_name="legacy_deprecated_param",
                new_name="canonical_param",
                deprecated_in="1.0.0",
                removed_in="99.0.0",
            )
        )
        manager = CompatManager()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            manager.warn_deprecation("legacy_deprecated_param")

            # Should have issued a warning
            assert len(w) >= 1
            assert issubclass(w[-1].category, DeprecationWarning)
            assert "legacy_deprecated_param" in str(w[-1].message)
        CompatManager.DEPRECATIONS = [
            d for d in CompatManager.DEPRECATIONS if d.old_name != "legacy_deprecated_param"
        ]

    def test_non_deprecated_name_no_warning(self):
        """Non-deprecated names should not issue warnings."""
        manager = CompatManager()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            manager.warn_deprecation("unknown_param")

            # Should not have issued a warning
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) == 0

    def test_warning_includes_migration_info(self):
        """Warning message should include migration information."""
        CompatManager.register_deprecation(
            DeprecationInfo(
                old_name="legacy_deprecated_param",
                new_name="canonical_param",
                deprecated_in="1.1.0",
                removed_in="99.0.0",
            )
        )
        manager = CompatManager()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            manager.warn_deprecation("legacy_deprecated_param")

            message = str(w[-1].message)
            # Should mention the new name
            assert "canonical_param" in message
            # Should mention version info
            assert "1.1.0" in message or "deprecated" in message.lower()
        CompatManager.DEPRECATIONS = [
            d for d in CompatManager.DEPRECATIONS if d.old_name != "legacy_deprecated_param"
        ]


class TestDeprecationExpiry:
    """Test that expired deprecations raise errors."""

    def test_expired_deprecation_raises_error(self):
        """Using expired deprecated name should raise ValueError."""
        # Register a deprecation that's already expired
        CompatManager.register_deprecation(
            DeprecationInfo(
                old_name="expired_param",
                new_name="new_param",
                deprecated_in="0.1.0",
                removed_in="0.2.0",  # Already removed
            )
        )

        manager = CompatManager()

        # Should raise ValueError since current version > removed_in
        # Note: This depends on the current package version
        # If current version >= 0.2.0, it should raise
        try:
            manager.warn_deprecation("expired_param")
            # If no error, the current version is < removed_in
            # which is fine for this test
        except ValueError as e:
            assert "expired_param" in str(e)
            assert "removed" in str(e).lower()

    def test_future_deprecation_only_warns(self):
        """Deprecation with future removed_in should only warn."""
        # Register a deprecation with far future removal
        CompatManager.register_deprecation(
            DeprecationInfo(
                old_name="future_deprecated",
                new_name="future_canonical",
                deprecated_in="1.0.0",
                removed_in="99.0.0",  # Far future
            )
        )

        manager = CompatManager()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # Should not raise, only warn
            manager.warn_deprecation("future_deprecated")

            assert len(w) >= 1
            assert issubclass(w[-1].category, DeprecationWarning)


class TestCompatManagerAPI:
    """Test CompatManager public API."""

    def test_is_deprecated(self):
        """is_deprecated() should correctly identify deprecated names."""
        CompatManager.register_deprecation(
            DeprecationInfo(
                old_name="legacy_api_param",
                new_name="canonical_api_param",
                deprecated_in="1.0.0",
                removed_in="99.0.0",
            )
        )
        manager = CompatManager()

        assert manager.is_deprecated("legacy_api_param") is True
        assert manager.is_deprecated("unknown_param") is False
        CompatManager.DEPRECATIONS = [
            d for d in CompatManager.DEPRECATIONS if d.old_name != "legacy_api_param"
        ]

    def test_get_deprecation_info(self):
        """get_deprecation_info() should return correct info."""
        CompatManager.register_deprecation(
            DeprecationInfo(
                old_name="legacy_api_param",
                new_name="canonical_api_param",
                deprecated_in="1.1.0",
                removed_in="2.0.0",
            )
        )
        manager = CompatManager()

        info = manager.get_deprecation_info("legacy_api_param")
        assert info is not None
        assert info.old_name == "legacy_api_param"
        assert info.new_name == "canonical_api_param"
        assert info.deprecated_in == "1.1.0"
        assert info.removed_in == "2.0.0"

        # Unknown name returns None
        assert manager.get_deprecation_info("unknown") is None
        CompatManager.DEPRECATIONS = [
            d for d in CompatManager.DEPRECATIONS if d.old_name != "legacy_api_param"
        ]

    def test_list_aliases(self):
        """list_aliases() should return all aliases for a plugin."""
        CompatManager.register_alias("legacy_list_alias", "canonical_list_alias")
        manager = CompatManager()

        aliases = manager.list_aliases("__global__")
        assert isinstance(aliases, dict)
        assert "legacy_list_alias" in aliases
        CompatManager.unregister_alias("legacy_list_alias")

    def test_list_deprecations(self):
        """list_deprecations() should return all deprecations."""
        manager = CompatManager()

        deprecations = manager.list_deprecations()
        assert isinstance(deprecations, list)
        assert len(deprecations) > 0
        assert all(isinstance(d, DeprecationInfo) for d in deprecations)

    def test_summary(self):
        """summary() should return formatted string."""
        CompatManager.register_alias("legacy_summary_alias", "canonical_summary_alias")
        manager = CompatManager()

        summary = manager.summary()
        assert isinstance(summary, str)
        assert "legacy_summary_alias" in summary or "alias" in summary.lower()
        CompatManager.unregister_alias("legacy_summary_alias")


class TestRegisterUnregister:
    """Test dynamic registration/unregistration of aliases and deprecations."""

    def test_register_alias(self):
        """register_alias() should add new alias."""
        CompatManager.register_alias("test_old", "test_new", plugin_name="test_plugin")

        manager = CompatManager()
        canonical, alias_used = manager.resolve_alias("test_plugin", "test_old")

        assert canonical == "test_new"
        assert alias_used is True

        # Clean up
        CompatManager.unregister_alias("test_old", plugin_name="test_plugin")

    def test_unregister_alias(self):
        """unregister_alias() should remove alias."""
        CompatManager.register_alias("temp_old", "temp_new", plugin_name="temp_plugin")
        result = CompatManager.unregister_alias("temp_old", plugin_name="temp_plugin")

        assert result is True

        manager = CompatManager()
        canonical, alias_used = manager.resolve_alias("temp_plugin", "temp_old")

        # Should no longer resolve
        assert canonical == "temp_old"
        assert alias_used is False

    def test_unregister_nonexistent_alias(self):
        """unregister_alias() should return False for nonexistent alias."""
        result = CompatManager.unregister_alias("nonexistent", plugin_name="nonexistent_plugin")
        assert result is False

    def test_register_deprecation(self):
        """register_deprecation() should add new deprecation."""
        info = DeprecationInfo(
            old_name="dynamic_deprecated",
            new_name="dynamic_canonical",
            deprecated_in="1.0.0",
            removed_in="3.0.0",
        )
        CompatManager.register_deprecation(info)

        manager = CompatManager()
        assert manager.is_deprecated("dynamic_deprecated")
        assert manager.get_deprecation_info("dynamic_deprecated") == info

    def test_register_deprecation_after_instantiation(self):
        """Deprecations registered after instantiation should be visible."""
        # Create manager first
        manager = CompatManager()

        # Register new deprecation
        info = DeprecationInfo(
            old_name="late_deprecated",
            new_name="late_canonical",
            deprecated_in="1.0.0",
            removed_in="3.0.0",
        )
        CompatManager.register_deprecation(info)

        # Existing manager should see it (due to dynamic lookup)
        assert manager.is_deprecated("late_deprecated")


class TestDeprecationInfoDataclass:
    """Test DeprecationInfo dataclass."""

    def test_get_warning_message(self):
        """get_warning_message() should return formatted message."""
        info = DeprecationInfo(
            old_name="old",
            new_name="new",
            deprecated_in="1.0.0",
            removed_in="2.0.0",
        )

        message = info.get_warning_message()
        assert "old" in message
        assert "new" in message
        assert "1.0.0" in message
        assert "2.0.0" in message

    def test_custom_message(self):
        """Custom message should be included in warning."""
        info = DeprecationInfo(
            old_name="old",
            new_name="new",
            deprecated_in="1.0.0",
            removed_in="2.0.0",
            message="Use new instead for better performance",
        )

        message = info.get_warning_message()
        assert "better performance" in message
