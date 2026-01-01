"""
子进程管理工具

提供执行命令、后台任务等功能
"""

import subprocess
import shlex
import os
from typing import Dict, Any, List, Optional

from pwnmcp.core.exceptions import ExecutionError


class SubprocessTools:
    """子进程工具"""

    def run_command(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
        env: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """执行命令并返回结果"""
        if isinstance(command, str):
            cmd_list = shlex.split(command)
        else:
            cmd_list = command

        process_env = os.environ.copy()
        if env:
            process_env.update(env)

        try:
            result = subprocess.run(
                cmd_list,
                cwd=cwd,
                env=process_env,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            return {
                "command": command,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0,
            }
        except subprocess.TimeoutExpired as e:
            raise ExecutionError("命令执行超时", details={"command": command, "timeout": timeout}) from e
        except FileNotFoundError as e:
            raise ExecutionError("命令不存在", details={"command": command}) from e
        except Exception as e:
            raise ExecutionError(str(e), details={"command": command})
