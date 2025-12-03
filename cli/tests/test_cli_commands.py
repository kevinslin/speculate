"""Tests for CLI commands."""

import os
from pathlib import Path

import pytest
import yaml
from pytest import MonkeyPatch

from speculate.cli.cli_commands import (
    SPECULATE_HEADER,
    SPECULATE_MARKER,
    _ensure_speculate_header,
    _remove_cursor_rules,
    _remove_speculate_header,
    _setup_cursor_rules,
    _update_speculate_settings,
    install,
    status,
    uninstall,
)


class TestUpdateSpeculateSettings:
    """Tests for _update_speculate_settings function."""

    def test_creates_settings_file(self, tmp_path: Path):
        """Should create .speculate/settings.yml if it doesn't exist."""
        _update_speculate_settings(tmp_path)

        settings_file = tmp_path / ".speculate" / "settings.yml"
        assert settings_file.exists()

        settings = yaml.safe_load(settings_file.read_text())
        assert "last_update" in settings
        assert "last_cli_version" in settings

    def test_updates_existing_settings(self, tmp_path: Path):
        """Should update existing settings file."""
        settings_dir = tmp_path / ".speculate"
        settings_dir.mkdir()
        settings_file = settings_dir / "settings.yml"
        settings_file.write_text(yaml.dump({"custom_key": "custom_value"}))

        _update_speculate_settings(tmp_path)

        settings = yaml.safe_load(settings_file.read_text())
        # Existing keys should be preserved
        assert settings.get("custom_key") == "custom_value"
        # New keys should be added
        assert "last_update" in settings

    def test_reads_docs_version_from_copier_answers(self, tmp_path: Path):
        """Should read docs version from .speculate/copier-answers.yml."""
        speculate_dir = tmp_path / ".speculate"
        speculate_dir.mkdir()
        copier_answers = speculate_dir / "copier-answers.yml"
        copier_answers.write_text(yaml.dump({"_commit": "v1.2.3", "_src_path": "gh:test/repo"}))

        _update_speculate_settings(tmp_path)

        settings_file = tmp_path / ".speculate" / "settings.yml"
        settings = yaml.safe_load(settings_file.read_text())
        assert settings.get("last_docs_version") == "v1.2.3"


class TestSetupCursorRules:
    """Tests for _setup_cursor_rules function."""

    def test_creates_cursor_rules_directory(self, tmp_path: Path):
        """Should create .cursor/rules/ directory."""
        rules_dir = tmp_path / "docs" / "general" / "agent-rules"
        rules_dir.mkdir(parents=True)

        _setup_cursor_rules(tmp_path)

        cursor_dir = tmp_path / ".cursor" / "rules"
        assert cursor_dir.exists()

    def test_creates_symlinks_for_md_files(self, tmp_path: Path):
        """Should create symlinks with .mdc extension."""
        rules_dir = tmp_path / "docs" / "general" / "agent-rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "general-rules.md").write_text("# General Rules")
        (rules_dir / "python-rules.md").write_text("# Python Rules")

        _setup_cursor_rules(tmp_path)

        cursor_dir = tmp_path / ".cursor" / "rules"
        assert (cursor_dir / "general-rules.mdc").is_symlink()
        assert (cursor_dir / "python-rules.mdc").is_symlink()

    def test_symlinks_are_relative(self, tmp_path: Path):
        """Symlinks should be relative paths."""
        rules_dir = tmp_path / "docs" / "general" / "agent-rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "test.md").write_text("# Test")

        _setup_cursor_rules(tmp_path)

        link = tmp_path / ".cursor" / "rules" / "test.mdc"
        target = os.readlink(link)
        assert not target.startswith("/")
        assert "docs/general/agent-rules/test.md" in target

    def test_include_pattern_filters_rules(self, tmp_path: Path):
        """Include pattern should filter which rules are linked."""
        rules_dir = tmp_path / "docs" / "general" / "agent-rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "general-rules.md").write_text("# General Rules")
        (rules_dir / "python-rules.md").write_text("# Python Rules")

        _setup_cursor_rules(tmp_path, include=["general-*.md"])

        cursor_dir = tmp_path / ".cursor" / "rules"
        assert (cursor_dir / "general-rules.mdc").exists()
        assert not (cursor_dir / "python-rules.mdc").exists()

    def test_exclude_pattern_filters_rules(self, tmp_path: Path):
        """Exclude pattern should filter out matching rules."""
        rules_dir = tmp_path / "docs" / "general" / "agent-rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "general-rules.md").write_text("# General Rules")
        (rules_dir / "convex-rules.md").write_text("# Convex Rules")

        _setup_cursor_rules(tmp_path, exclude=["convex-*.md"])

        cursor_dir = tmp_path / ".cursor" / "rules"
        assert (cursor_dir / "general-rules.mdc").exists()
        assert not (cursor_dir / "convex-rules.mdc").exists()

    def test_warns_when_rules_dir_missing(self, tmp_path: Path):
        """Should warn when docs/general/agent-rules/ doesn't exist."""
        _setup_cursor_rules(tmp_path)
        # The function prints a warning via rich - we just verify it doesn't raise


class TestInstallCommand:
    """Tests for install command."""

    def test_fails_without_docs_directory(self, tmp_path: Path, monkeypatch: MonkeyPatch):
        """Should fail if docs/ directory doesn't exist."""
        monkeypatch.chdir(tmp_path)

        with pytest.raises(SystemExit) as exc_info:
            install()
        assert exc_info.value.code == 1

    def test_creates_all_configs(self, tmp_path: Path, monkeypatch: MonkeyPatch):
        """Should create all tool configurations."""
        # Setup minimal docs structure
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        rules_dir = tmp_path / "docs" / "general" / "agent-rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "test-rule.md").write_text("# Test")

        monkeypatch.chdir(tmp_path)
        install()

        # Check all configs exist
        assert (tmp_path / ".speculate" / "settings.yml").exists()
        assert (tmp_path / "CLAUDE.md").exists()
        assert (tmp_path / "AGENTS.md").exists()
        assert (tmp_path / ".cursor" / "rules").exists()


class TestStatusCommand:
    """Tests for status command."""

    def test_fails_without_development_md(self, tmp_path: Path, monkeypatch: MonkeyPatch):
        """Should fail if development.md is missing."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        # Create copier-answers so it doesn't fail on that first
        speculate_dir = tmp_path / ".speculate"
        speculate_dir.mkdir()
        (speculate_dir / "copier-answers.yml").write_text(
            yaml.dump({"_commit": "abc123", "_src_path": "test"})
        )

        monkeypatch.chdir(tmp_path)

        with pytest.raises(SystemExit) as exc_info:
            status()
        assert exc_info.value.code == 1

    def test_fails_without_copier_answers(self, tmp_path: Path, monkeypatch: MonkeyPatch):
        """Should fail if .speculate/copier-answers.yml is missing."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "development.md").write_text("# Development")

        monkeypatch.chdir(tmp_path)

        with pytest.raises(SystemExit) as exc_info:
            status()
        assert exc_info.value.code == 1

    def test_succeeds_with_all_required_files(self, tmp_path: Path, monkeypatch: MonkeyPatch):
        """Should succeed if development.md and .speculate/copier-answers.yml exist."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "development.md").write_text("# Development")
        speculate_dir = tmp_path / ".speculate"
        speculate_dir.mkdir()
        (speculate_dir / "copier-answers.yml").write_text(
            yaml.dump({"_commit": "abc123", "_src_path": "test"})
        )

        monkeypatch.chdir(tmp_path)

        # Should not raise
        status()


class TestEnsureSpeculateHeader:
    """Tests for _ensure_speculate_header function."""

    def test_creates_new_file_with_header(self, tmp_path: Path):
        """Should create file with header if it doesn't exist."""
        test_file = tmp_path / "CLAUDE.md"

        _ensure_speculate_header(test_file)

        assert test_file.exists()
        content = test_file.read_text()
        assert SPECULATE_MARKER in content

    def test_prepends_header_to_existing_content(self, tmp_path: Path):
        """Should prepend header to existing file content."""
        test_file = tmp_path / "CLAUDE.md"
        existing_content = "# My Custom Instructions\n\nDo this and that."
        test_file.write_text(existing_content)

        _ensure_speculate_header(test_file)

        content = test_file.read_text()
        assert content.startswith(SPECULATE_HEADER)
        assert existing_content in content

    def test_idempotent_when_header_present(self, tmp_path: Path):
        """Should not modify file if header already present."""
        test_file = tmp_path / "CLAUDE.md"
        original_content = SPECULATE_HEADER + "\n\n# Custom stuff"
        test_file.write_text(original_content)

        _ensure_speculate_header(test_file)

        assert test_file.read_text() == original_content


class TestRemoveSpeculateHeader:
    """Tests for _remove_speculate_header function."""

    def test_removes_header_preserves_content(self, tmp_path: Path):
        """Should remove header but preserve other content."""
        test_file = tmp_path / "CLAUDE.md"
        custom_content = "# My Custom Instructions\n\nDo this and that."
        test_file.write_text(SPECULATE_HEADER + "\n\n" + custom_content)

        _remove_speculate_header(test_file)

        assert test_file.exists()
        content = test_file.read_text()
        assert SPECULATE_MARKER not in content
        assert "My Custom Instructions" in content

    def test_removes_header_when_not_at_top(self, tmp_path: Path):
        """Should remove header even when user added content above it."""
        test_file = tmp_path / "CLAUDE.md"
        prefix = "# My prefix content\n\n"
        suffix = "\n\n# My suffix content"
        test_file.write_text(prefix + SPECULATE_HEADER + suffix)

        _remove_speculate_header(test_file)

        content = test_file.read_text()
        assert SPECULATE_MARKER not in content
        assert "My prefix content" in content
        assert "My suffix content" in content

    def test_deletes_file_if_empty_after_removal(self, tmp_path: Path):
        """Should delete file if it becomes empty after header removal."""
        test_file = tmp_path / "CLAUDE.md"
        test_file.write_text(SPECULATE_HEADER + "\n")

        _remove_speculate_header(test_file)

        assert not test_file.exists()

    def test_no_op_if_no_marker(self, tmp_path: Path):
        """Should not modify file if marker is not present."""
        test_file = tmp_path / "CLAUDE.md"
        original_content = "# My custom content\n\nNothing speculate here."
        test_file.write_text(original_content)

        _remove_speculate_header(test_file)

        assert test_file.read_text() == original_content

    def test_no_error_if_file_missing(self, tmp_path: Path):
        """Should not raise error if file doesn't exist."""
        test_file = tmp_path / "CLAUDE.md"

        # Should not raise
        _remove_speculate_header(test_file)

        assert not test_file.exists()


class TestRemoveCursorRules:
    """Tests for _remove_cursor_rules function."""

    def test_removes_symlinks(self, tmp_path: Path):
        """Should remove symlinks from .cursor/rules/."""
        rules_dir = tmp_path / "docs" / "general" / "agent-rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "test.md").write_text("# Test")

        cursor_dir = tmp_path / ".cursor" / "rules"
        cursor_dir.mkdir(parents=True)
        link = cursor_dir / "test.mdc"
        link.symlink_to(Path("..") / ".." / "docs" / "general" / "agent-rules" / "test.md")

        _remove_cursor_rules(tmp_path)

        assert not link.exists()

    def test_preserves_non_symlinks(self, tmp_path: Path):
        """Should not remove regular files."""
        cursor_dir = tmp_path / ".cursor" / "rules"
        cursor_dir.mkdir(parents=True)
        regular_file = cursor_dir / "custom.mdc"
        regular_file.write_text("# Custom rules")

        _remove_cursor_rules(tmp_path)

        assert regular_file.exists()

    def test_no_error_if_cursor_dir_missing(self, tmp_path: Path):
        """Should not raise error if .cursor/rules/ doesn't exist."""
        # Should not raise
        _remove_cursor_rules(tmp_path)


class TestUninstallCommand:
    """Tests for uninstall command."""

    def test_removes_all_tool_configs(self, tmp_path: Path, monkeypatch: MonkeyPatch):
        """Should remove all tool configurations."""
        # Setup: create docs and run install
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        rules_dir = tmp_path / "docs" / "general" / "agent-rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "test-rule.md").write_text("# Test")

        monkeypatch.chdir(tmp_path)
        install()

        # Verify configs exist
        assert (tmp_path / "CLAUDE.md").exists()
        assert (tmp_path / "AGENTS.md").exists()
        assert (tmp_path / ".speculate" / "settings.yml").exists()
        assert (tmp_path / ".cursor" / "rules" / "test-rule.mdc").is_symlink()

        # Run uninstall with force
        uninstall(force=True)

        # Verify headers removed (files may be deleted if empty)
        claude_md = tmp_path / "CLAUDE.md"
        if claude_md.exists():
            assert SPECULATE_MARKER not in claude_md.read_text()

        agents_md = tmp_path / "AGENTS.md"
        if agents_md.exists():
            assert SPECULATE_MARKER not in agents_md.read_text()

        # Settings should be removed
        assert not (tmp_path / ".speculate" / "settings.yml").exists()

        # Symlinks should be removed
        assert not (tmp_path / ".cursor" / "rules" / "test-rule.mdc").exists()

    def test_preserves_docs_directory(self, tmp_path: Path, monkeypatch: MonkeyPatch):
        """Should not remove docs/ directory."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "test.md").write_text("# Test")

        monkeypatch.chdir(tmp_path)

        # Create a marker file to test with
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(SPECULATE_HEADER + "\n")

        uninstall(force=True)

        assert docs_dir.exists()
        assert (docs_dir / "test.md").exists()

    def test_preserves_copier_answers(self, tmp_path: Path, monkeypatch: MonkeyPatch):
        """Should not remove .speculate/copier-answers.yml."""
        speculate_dir = tmp_path / ".speculate"
        speculate_dir.mkdir()
        copier_answers = speculate_dir / "copier-answers.yml"
        copier_answers.write_text(yaml.dump({"_commit": "abc123"}))

        # Create a marker file to test with
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(SPECULATE_HEADER + "\n")

        monkeypatch.chdir(tmp_path)
        uninstall(force=True)

        assert copier_answers.exists()

    def test_nothing_to_uninstall(self, tmp_path: Path, monkeypatch: MonkeyPatch):
        """Should handle case when nothing is installed."""
        monkeypatch.chdir(tmp_path)

        # Should not raise
        uninstall(force=True)

    def test_preserves_custom_content_in_claude_md(self, tmp_path: Path, monkeypatch: MonkeyPatch):
        """Should preserve custom content in CLAUDE.md after removing header."""
        custom_content = "# My Custom Instructions\n\nThese are my rules."
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(SPECULATE_HEADER + "\n\n" + custom_content)

        monkeypatch.chdir(tmp_path)
        uninstall(force=True)

        assert claude_md.exists()
        content = claude_md.read_text()
        assert SPECULATE_MARKER not in content
        assert "My Custom Instructions" in content
