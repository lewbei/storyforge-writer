"""
Settings Agent - Validates environment and configuration before story generation.

Responsibilities:
- Check .env file exists and is properly formatted
- Verify API keys are present and valid
- Validate model configuration
- Check output folder permissions
- Verify required dependencies
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class SettingsAgent:
    """Agent responsible for validating environment and settings."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.config: Dict = {}

    def validate(self) -> Tuple[bool, Dict, List[str], List[str]]:
        """
        Validate all settings and environment.

        Returns:
            Tuple of (success, config, errors, warnings)
        """
        logger.info("SettingsAgent: Starting validation...")

        # Check .env file
        self._check_env_file()

        # Check API keys
        self._check_api_keys()

        # Check output directory
        self._check_output_directory()

        # Check dependencies
        self._check_dependencies()

        # Build config
        self._build_config()

        success = len(self.errors) == 0

        if success:
            logger.info("SettingsAgent: Validation PASSED [OK]")
        else:
            logger.error(f"SettingsAgent: Validation FAILED with {len(self.errors)} errors")

        return success, self.config, self.errors, self.warnings

    def _check_env_file(self):
        """Check if .env file exists and is readable."""
        env_path = Path(".env")
        if not env_path.exists():
            self.warnings.append(".env file not found - will use environment variables or defaults")
            logger.warning(".env file not found")
        else:
            try:
                with open(env_path, 'r') as f:
                    content = f.read()
                if not content.strip():
                    self.warnings.append(".env file is empty")
                logger.info(f".env file found and readable ({len(content)} bytes)")
            except Exception as e:
                self.errors.append(f"Cannot read .env file: {e}")

    def _check_api_keys(self):
        """Check if at least one API key is configured."""
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        moonshot_key = os.getenv("MOONSHOT_API_KEY")
        ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")

        if openrouter_key:
            logger.info("[OK] OpenRouter API key found")
            self.config['provider'] = 'openrouter'
            self.config['api_key'] = openrouter_key
        elif moonshot_key:
            logger.info("[OK] Moonshot API key found")
            self.config['provider'] = 'moonshot'
            self.config['api_key'] = moonshot_key
        else:
            logger.info("No API keys found - will attempt to use Ollama (local)")
            self.warnings.append(f"No API keys found - attempting Ollama at {ollama_base}")
            self.config['provider'] = 'ollama'
            self.config['base_url'] = ollama_base

    def _check_output_directory(self):
        """Check if output directory exists and is writable."""
        output_dir = Path("output")
        try:
            output_dir.mkdir(exist_ok=True)
            # Test write permissions
            test_file = output_dir / ".write_test"
            test_file.write_text("test")
            test_file.unlink()
            logger.info(f"[OK] Output directory: {output_dir.absolute()}")
        except Exception as e:
            self.errors.append(f"Cannot write to output directory: {e}")

    def _check_dependencies(self):
        """Check if required Python packages are installed."""
        required = ["openai", "rich", "dotenv", "prompt_toolkit"]
        missing = []

        for package in required:
            try:
                if package == "dotenv":
                    __import__("dotenv")
                elif package == "prompt_toolkit":
                    __import__("prompt_toolkit")
                else:
                    __import__(package)
                logger.debug(f"[OK] {package} installed")
            except ImportError:
                missing.append(package)

        if missing:
            self.errors.append(f"Missing required packages: {', '.join(missing)}")
            self.errors.append("Run: pip install -r requirements.txt")

    def _build_config(self):
        """Build configuration dictionary from environment."""
        # Add common config
        self.config['output_dir'] = str(Path("output").absolute())
        self.config['log_dir'] = str(Path("logs").absolute())

        # Model settings
        if self.config.get('provider') == 'openrouter':
            self.config['model'] = os.getenv("OPENROUTER_MODEL")
            self.config['base_url'] = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        elif self.config.get('provider') == 'moonshot':
            self.config['model'] = os.getenv("MOONSHOT_MODEL", "moonshot-v1")
            self.config['base_url'] = os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.ai/v1")
        elif self.config.get('provider') == 'ollama':
            self.config['model'] = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
            self.config['api_key'] = "ollama"  # Dummy key for local

        logger.info(f"Config built: provider={self.config.get('provider')}, model={self.config.get('model')}")

    def print_report(self, console=None):
        """Print validation report."""
        if console:
            from rich.panel import Panel
            from rich.text import Text

            report = Text()
            report.append("Settings Validation Report\n\n", style="bold cyan")

            if self.errors:
                report.append("[ERROR] ERRORS:\n", style="bold red")
                for error in self.errors:
                    report.append(f"  - {error}\n", style="red")
                report.append("\n")

            if self.warnings:
                report.append("[WARN] WARNINGS:\n", style="bold yellow")
                for warning in self.warnings:
                    report.append(f"  - {warning}\n", style="yellow")
                report.append("\n")

            if not self.errors:
                report.append("[OK] All validations passed\n", style="bold green")
                report.append(f"Provider: {self.config.get('provider')}\n", style="green")
                report.append(f"Model: {self.config.get('model')}\n", style="green")

            console.print(Panel(report, title="Agent 1: Settings", border_style="cyan"))
        else:
            # Plain text output
            print("\n=== Settings Validation Report ===")
            if self.errors:
                print("\n[ERROR] ERRORS:")
                for error in self.errors:
                    print(f"  - {error}")
            if self.warnings:
                print("\n[WARN] WARNINGS:")
                for warning in self.warnings:
                    print(f"  - {warning}")
            if not self.errors:
                print(f"\n[OK] All validations passed")
                print(f"Provider: {self.config.get('provider')}")
                print(f"Model: {self.config.get('model')}")
            print("")
