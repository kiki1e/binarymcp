"""
封装常用的 PWN 命令行工具
- checksec
- ROPgadget
- one_gadget
- patchelf
"""
import subprocess
import json
from typing import Dict, Any, Optional, List
import shutil

class PwnCliTools:
    """封装对 checksec, ROPgadget, one_gadget, patchelf 的调用"""

    def _is_tool_available(self, name: str) -> bool:
        """检查工具是否存在于 PATH 中"""
        return shutil.which(name) is not None

    def _execute(self, command: List[str]) -> Dict[str, Any]:
        """执行命令并返回结构化输出"""
        tool_name = command[0]
        if not self._is_tool_available(tool_name):
            return {
                "success": False,
                "error": f"命令 '{tool_name}' 不存在。请确认它已安装并在系统的 PATH 环境变量中。",
                "command": " ".join(command),
            }
        
        try:
            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,  # 不要对非零退出码抛出异常
            )
            
            # 即使命令成功，也可能在 stderr 中输出警告
            output_data = {
                "stdout": process.stdout.strip(),
                "stderr": process.stderr.strip(),
            }

            if process.returncode != 0:
                return {
                    "success": False,
                    "error": f"命令执行失败，返回码: {process.returncode}",
                    "data": output_data,
                    "command": " ".join(command),
                }

            return {
                "success": True,
                "data": output_data,
                "command": " ".join(command),
            }
        except Exception as e:
            return {"success": False, "error": str(e), "command": " ".join(command)}

    def checksec(self, file_path: str) -> Dict[str, Any]:
        """运行 checksec 并以 JSON 格式返回结果"""
        result = self._execute(["checksec", "--file", file_path, "--format", "json"])
        if result["success"]:
            try:
                # checksec 的 JSON 输出在 stdout
                result["data"] = json.loads(result["data"]["stdout"])
            except json.JSONDecodeError:
                result["success"] = False
                result["error"] = "解析 checksec 的 JSON 输出失败。"
                # 保留原始输出以供调试
                result["data"]["raw_stdout"] = result["data"]["stdout"]
        return result

    def ropgadget(self, binary_path: str, options: Optional[str] = None) -> Dict[str, Any]:
        """运行 ROPgadget。options 是一个包含额外参数的字符串。"""
        command = ["ROPgadget", "--binary", binary_path]
        if options:
            command.extend(options.split())
        return self._execute(command)

    def onegadget(self, libc_path: str) -> Dict[str, Any]:
        """运行 one_gadget"""
        return self._execute(["one_gadget", libc_path])

    def patchelf(self, binary_path: str, set_interpreter: Optional[str] = None, set_rpath: Optional[str] = None) -> Dict[str, Any]:
        """运行 patchelf 修改二进制文件"""
        if not set_interpreter and not set_rpath:
            return {"success": False, "error": "必须提供 --set-interpreter 或 --set-rpath 参数之一。"}
        
        command = ["patchelf"]
        if set_interpreter:
            command.extend(["--set-interpreter", set_interpreter])
        if set_rpath:
            command.extend(["--set-rpath", set_rpath])
        
        command.append(binary_path)
        return self._execute(command)
