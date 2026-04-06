"""
Git 工具

提供仓库信息和操作能力
"""

import subprocess
from typing import Dict, Any, Optional

from pwnmcp.core.exceptions import ExecutionError


class GitTools:
    """Git 工具"""

    def _run_git(self, args: list, cwd: Optional[str] = None) -> Dict[str, Any]:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except FileNotFoundError as e:
            raise ExecutionError("Git 未安装", details={"args": args}) from e

    def status(self, cwd: Optional[str] = None) -> Dict[str, Any]:
        return self._run_git(["status", "--short"], cwd)

    def log(self, cwd: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
        return self._run_git(["log", f"-{limit}", "--oneline"], cwd)

    def diff(self, cwd: Optional[str] = None) -> Dict[str, Any]:
        return self._run_git(["diff"], cwd)
