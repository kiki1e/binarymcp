"""
Python 环境工具

提供在隔离环境中运行 Python 代码
"""

import subprocess
import tempfile
import os
from typing import Dict, Any, Optional

from pwnmcp.core.exceptions import ExecutionError


class PythonTools:
    """Python 工具"""

    def run_script(self, code: str, cwd: Optional[str] = None) -> Dict[str, Any]:
        """运行临时 Python 脚本"""
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tmp:
            tmp.write(code)
            tmp_path = tmp.name

        try:
            result = subprocess.run(
                ["python3", tmp_path],
                cwd=cwd,
                capture_output=True,
                text=True
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except FileNotFoundError as e:
            raise ExecutionError("Python 未安装", details={}) from e
        finally:
            os.unlink(tmp_path)
