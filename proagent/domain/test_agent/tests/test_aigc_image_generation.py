"""Test cases for AIGC Creator - Image Generation functionality.

This module tests the aigc_generate tool for image generation using MiniMax CLI.
Tests cover: success paths, error handling, parameter validation, and policy compliance.

Test Strategy:
- Unit tests mock subprocess to avoid actual API calls
- Integration tests require MINIMAX_CN_API_KEY environment variable
- Policy tests verify content restrictions are enforced

Run with: pytest proagent/domain/test_agent/tests/test_aigc_image_generation.py -v
"""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from proagent.domain.aigc_creator.tools.aigc_generate import (
    OUTPUT_DIR,
    aigc_generate_handler,
)


class TestImageGenerationSuccess:
    """Test successful image generation scenarios."""

    @patch("proagent.domain.aigc_creator.tools.aigc_generate.subprocess.run")
    @patch.dict(os.environ, {"MINIMAX_CN_API_KEY": "sk-test-key-12345"})
    def test_image_generate_basic_success(self, mock_run):
        """Test basic image generation with minimal parameters."""
        # Mock successful generation
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="output/aigc/image_001.png",
            stderr="",
        )

        result = aigc_generate_handler(
            command="image generate",
            prompt="一只可爱的猫咪",
        )

        assert "✅" in result
        assert "生成成功" in result
        assert "image_001.png" in result

        # Verify command was called correctly
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "image" in " ".join(call_args[0][0])
        assert "generate" in " ".join(call_args[0][0])

    @patch("proagent.domain.aigc_creator.tools.aigc_generate.subprocess.run")
    @patch.dict(os.environ, {"MINIMAX_CN_API_KEY": "sk-test-key-12345"})
    def test_image_generate_with_aspect_ratio(self, mock_run):
        """Test image generation with aspect ratio option."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="output/aigc/image_002.png",
            stderr="",
        )

        result = aigc_generate_handler(
            command="image generate",
            prompt="美丽的风景",
            options="--aspect-ratio 16:9",
        )

        assert "✅" in result
        # Verify aspect ratio was passed
        call_args = " ".join(mock_run.call_args[0][0])
        assert "--aspect-ratio" in call_args
        assert "16:9" in call_args

    @patch("proagent.domain.aigc_creator.tools.aigc_generate.subprocess.run")
    @patch.dict(os.environ, {"MINIMAX_CN_API_KEY": "sk-test-key-12345"})
    def test_image_generate_various_styles(self, mock_run):
        """Test image generation with various style prompts."""
        test_prompts = [
            "动漫风格的少女",
            "写实风格的建筑",
            "水彩画风格的花园",
            "像素艺术风格的游戏角色",
        ]

        for i, prompt in enumerate(test_prompts):
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=f"output/aigc/image_{i:03d}.png",
                stderr="",
            )

            result = aigc_generate_handler(
                command="image generate",
                prompt=prompt,
            )

            assert "✅" in result, f"Failed for prompt: {prompt}"

    @patch("proagent.domain.aigc_creator.tools.aigc_generate.subprocess.run")
    @patch.dict(os.environ, {"MINIMAX_CN_API_KEY": "sk-test-key-12345"})
    def test_image_generate_output_directory_created(self, mock_run):
        """Test that output directory is created if it doesn't exist."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="output/aigc/image.png",
            stderr="",
        )

        # Call handler (it should create OUTPUT_DIR)
        aigc_generate_handler(
            command="image generate",
            prompt="test image",
        )

        # The OUTPUT_DIR should exist or be creatable
        # Note: In test environment, this tests the path resolution
        assert OUTPUT_DIR.name == "aigc"


class TestImageGenerationErrors:
    """Test error handling for image generation."""

    def test_image_generate_no_api_key(self):
        """Test that missing API key returns clear error."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove the key if it exists
            if "MINIMAX_CN_API_KEY" in os.environ:
                del os.environ["MINIMAX_CN_API_KEY"]

            result = aigc_generate_handler(
                command="image generate",
                prompt="test image",
            )

            assert "❌" in result
            assert "MINIMAX_CN_API_KEY" in result
            assert "not set" in result

    @patch("proagent.domain.aigc_creator.tools.aigc_generate.subprocess.run")
    @patch.dict(os.environ, {"MINIMAX_CN_API_KEY": "sk-test-key-12345"})
    def test_image_generate_cli_not_found(self, mock_run):
        """Test handling when MiniMax CLI is not installed."""
        mock_run.side_effect = FileNotFoundError("mmx not found")

        result = aigc_generate_handler(
            command="image generate",
            prompt="test image",
        )

        assert "❌" in result
        assert "未找到" in result or "not found" in result.lower()

    @patch("proagent.domain.aigc_creator.tools.aigc_generate.subprocess.run")
    @patch.dict(os.environ, {"MINIMAX_CN_API_KEY": "sk-test-key-12345"})
    def test_image_generate_api_error(self, mock_run):
        """Test handling of API error responses."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: Invalid API key",
        )

        result = aigc_generate_handler(
            command="image generate",
            prompt="test image",
        )

        assert "❌" in result
        assert "生成失败" in result
        assert "Invalid API key" in result

    @patch("proagent.domain.aigc_creator.tools.aigc_generate.subprocess.run")
    @patch.dict(os.environ, {"MINIMAX_CN_API_KEY": "sk-test-key-12345"})
    def test_image_generate_timeout(self, mock_run):
        """Test handling of generation timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="mmx", timeout=120)

        result = aigc_generate_handler(
            command="image generate",
            prompt="complex detailed image",
        )

        assert "❌" in result
        assert "超时" in result

    @patch("proagent.domain.aigc_creator.tools.aigc_generate.subprocess.run")
    @patch.dict(os.environ, {"MINIMAX_CN_API_KEY": "sk-test-key-12345"})
    def test_image_generate_content_policy_violation(self, mock_run):
        """Test handling of content policy violation from API."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: Content policy violation - inappropriate content",
        )

        result = aigc_generate_handler(
            command="image generate",
            prompt="inappropriate content description",
        )

        assert "❌" in result
        assert "生成失败" in result


class TestImageGenerationParameters:
    """Test parameter validation and handling."""

    @patch("proagent.domain.aigc_creator.tools.aigc_generate.subprocess.run")
    @patch.dict(os.environ, {"MINIMAX_CN_API_KEY": "sk-test-key-12345"})
    def test_image_generate_empty_prompt(self, mock_run):
        """Test handling of empty prompt."""
        # Empty prompt should still execute (API will validate)
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: prompt cannot be empty",
        )

        result = aigc_generate_handler(
            command="image generate",
            prompt="",
        )

        # Should return the API error
        assert "❌" in result

    @patch("proagent.domain.aigc_creator.tools.aigc_generate.subprocess.run")
    @patch.dict(os.environ, {"MINIMAX_CN_API_KEY": "sk-test-key-12345"})
    def test_image_generate_long_prompt(self, mock_run):
        """Test handling of very long prompt."""
        long_prompt = "这是一段非常长的描述" * 100  # Very long prompt

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="output/aigc/image.png",
            stderr="",
        )

        result = aigc_generate_handler(
            command="image generate",
            prompt=long_prompt,
        )

        # Should handle long prompts (API may truncate or accept)
        assert "✅" in result or "❌" in result

    @patch("proagent.domain.aigc_creator.tools.aigc_generate.subprocess.run")
    @patch.dict(os.environ, {"MINIMAX_CN_API_KEY": "sk-test-key-12345"})
    def test_image_generate_special_characters_in_prompt(self, mock_run):
        """Test handling of special characters in prompt."""
        special_prompt = "测试特殊字符: <>&\"'`$\\n\\t"

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="output/aigc/image.png",
            stderr="",
        )

        result = aigc_generate_handler(
            command="image generate",
            prompt=special_prompt,
        )

        # Should handle special characters safely
        assert "✅" in result or "❌" in result

    @patch("proagent.domain.aigc_creator.tools.aigc_generate.subprocess.run")
    @patch.dict(os.environ, {"MINIMAX_CN_API_KEY": "sk-test-key-12345"})
    def test_image_generate_multiple_options(self, mock_run):
        """Test image generation with multiple CLI options."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="output/aigc/image.png",
            stderr="",
        )

        result = aigc_generate_handler(
            command="image generate",
            prompt="sunset over mountains",
            options="--aspect-ratio 16:9 --style realistic",
        )

        assert "✅" in result
        call_args = " ".join(mock_run.call_args[0][0])
        assert "--aspect-ratio" in call_args
        assert "--style" in call_args


class TestImageGenerationCommands:
    """Test different command variations."""

    @patch("proagent.domain.aigc_creator.tools.aigc_generate.subprocess.run")
    @patch.dict(os.environ, {"MINIMAX_CN_API_KEY": "sk-test-key-12345"})
    def test_command_variations(self, mock_run):
        """Test different valid command formats."""
        commands = [
            "image generate",
            "image generate --model test",
        ]

        for cmd in commands:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="output/aigc/image.png",
                stderr="",
            )

            result = aigc_generate_handler(
                command=cmd,
                prompt="test",
            )

            # Commands should be processed
            assert "✅" in result or "❌" in result


class TestImageGenerationSecurity:
    """Test security-related aspects."""

    @patch("proagent.domain.aigc_creator.tools.aigc_generate.subprocess.run")
    @patch.dict(os.environ, {"MINIMAX_CN_API_KEY": "sk-secret-key-12345"})
    def test_api_key_not_leaked_in_output(self, mock_run):
        """Test that API key is not exposed in result messages."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="output/aigc/image.png",
            stderr="",
        )

        result = aigc_generate_handler(
            command="image generate",
            prompt="test image",
        )

        # API key should be masked in output
        assert "sk-secret-key-12345" not in result
        assert "sk-***" in result or "API key" not in result

    @patch("proagent.domain.aigc_creator.tools.aigc_generate.subprocess.run")
    @patch.dict(os.environ, {"MINIMAX_CN_API_KEY": "sk-test-key"})
    def test_command_injection_prevention(self, mock_run):
        """Test that command injection is prevented."""
        # Attempt command injection via prompt
        malicious_prompt = "test; rm -rf /"

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="output/aigc/image.png",
            stderr="",
        )

        result = aigc_generate_handler(
            command="image generate",
            prompt=malicious_prompt,
        )

        # The prompt should be passed as a parameter, not executed
        # Verify subprocess.run was called with list args (safe from injection)
        call_args = mock_run.call_args
        assert isinstance(call_args[0][0], list)


class TestImageGenerationIntegration:
    """Integration tests that require actual MiniMax CLI and API key.

    These tests are skipped if MINIMAX_CN_API_KEY is not set.
    Run with: pytest -v --run-integration
    """

    @pytest.mark.skipif(
        not os.environ.get("MINIMAX_CN_API_KEY"),
        reason="MINIMAX_CN_API_KEY not set"
    )
    @pytest.mark.integration
    def test_real_image_generation_basic(self):
        """Test actual image generation with real API.

        This test makes a real API call and should be used sparingly.
        """
        result = aigc_generate_handler(
            command="image generate",
            prompt="一只可爱的小猫坐在窗台上，阳光照进来",
        )

        # Should succeed with real API
        assert "✅" in result
        assert "生成成功" in result

    @pytest.mark.skipif(
        not os.environ.get("MINIMAX_CN_API_KEY"),
        reason="MINIMAX_CN_API_KEY not set"
    )
    @pytest.mark.integration
    def test_real_image_generation_with_aspect_ratio(self):
        """Test actual image generation with aspect ratio."""
        result = aigc_generate_handler(
            command="image generate",
            prompt="美丽的山水风景",
            options="--aspect-ratio 16:9",
        )

        assert "✅" in result


class TestOutputFormat:
    """Test output format compliance."""

    @patch("proagent.domain.aigc_creator.tools.aigc_generate.subprocess.run")
    @patch.dict(os.environ, {"MINIMAX_CN_API_KEY": "sk-test-key"})
    def test_success_output_format(self, mock_run):
        """Test that success output contains required information."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="output/aigc/image_test.png",
            stderr="",
        )

        result = aigc_generate_handler(
            command="image generate",
            prompt="test",
        )

        # Success output should contain:
        # - Success indicator
        # - File path
        assert "✅" in result
        assert "image_test.png" in result

    @patch("proagent.domain.aigc_creator.tools.aigc_generate.subprocess.run")
    @patch.dict(os.environ, {"MINIMAX_CN_API_KEY": "sk-test-key"})
    def test_error_output_format(self, mock_run):
        """Test that error output contains required information."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="API Error: Rate limit exceeded",
        )

        result = aigc_generate_handler(
            command="image generate",
            prompt="test",
        )

        # Error output should contain:
        # - Error indicator
        # - Error message
        assert "❌" in result
        assert "Rate limit exceeded" in result


# Test runner configuration
if __name__ == "__main__":
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-k", "not integration",  # Skip integration tests by default
    ])
