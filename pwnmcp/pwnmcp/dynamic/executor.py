"""
动态执行器

整合 pwn-mcp 的动态执行功能：
- 本地程序运行
- 偏移量计算
- 崩溃分析
"""

import logging
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from pwn import cyclic, cyclic_find
except Exception:  # pragma: no cover - optional dependency failures handled at runtime
    cyclic = cyclic_find = None

from pwnmcp.core.exceptions import ExecutionError

logger = logging.getLogger(__name__)


class DynamicExecutor:
    """动态执行器 - 程序运行和崩溃分析"""
    
    def __init__(self):
        """初始化动态执行器"""
        self.timeout_default = 5  # 默认超时秒数
    
    def run_local(
        self,
        binary_path: str,
        args: Optional[List[str]] = None,
        input_data: Optional[str] = None,
        timeout_ms: Optional[int] = None,
        aslr: bool = True,
    ) -> Dict[str, Any]:
        """
        运行本地二进制文件
        
        Args:
            binary_path: 二进制文件路径
            args: 命令行参数
            input_data: 标准输入数据
            timeout_ms: 超时时间（毫秒）
            aslr: 是否启用 ASLR
            
        Returns:
            执行结果字典
        """
        if not Path(binary_path).exists():
            raise ExecutionError(f"文件不存在: {binary_path}", details={"path": binary_path})
        
        # 确保文件可执行
        if not os.access(binary_path, os.X_OK):
            try:
                os.chmod(binary_path, 0o755)
            except Exception as e:
                raise ExecutionError(f"无法设置执行权限: {e}", details={"path": binary_path, "error": str(e)})
        
        timeout_sec = (timeout_ms / 1000) if timeout_ms else self.timeout_default
        
        # 构建命令
        cmd = [binary_path]
        if args:
            cmd.extend(args)
        
        # 构建环境
        env = os.environ.copy()
        if not aslr:
            setarch = shutil.which("setarch")
            if setarch:
                cmd = [setarch, "x86_64", "-R", *cmd]
            else:
                logger.warning("setarch 不可用，无法禁用 ASLR，继续启用 ASLR 运行")
        
        logger.info(f"运行程序: {' '.join(cmd)}")
        
        try:
            start_time = time.time()
            
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
            )
            
            # 发送输入数据
            input_bytes = input_data.encode() if input_data else None
            
            try:
                stdout, stderr = process.communicate(input=input_bytes, timeout=timeout_sec)
                returncode = process.returncode
                timed_out = False
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                returncode = -1
                timed_out = True
            
            execution_time = time.time() - start_time
            
            result = {
                "success": True,
                "returncode": returncode,
                "stdout": stdout.decode('utf-8', errors='replace'),
                "stderr": stderr.decode('utf-8', errors='replace'),
                "timed_out": timed_out,
                "execution_time_ms": int(execution_time * 1000),
                "crashed": returncode < 0 and not timed_out,
                "signal": None
            }
            
            # 检测崩溃信号
            if returncode < 0 and not timed_out:
                sig = -returncode
                result["signal"] = signal.Signals(sig).name if sig < 32 else f"SIGNAL_{sig}"
                logger.warning(f"程序崩溃: {result['signal']}")
            
            return result
            
        except Exception as e:
            logger.error(f"执行失败: {e}")
            raise ExecutionError(f"程序执行失败: {e}", details={"path": binary_path})
    
    def calculate_offsets(self, pattern_dump: str) -> Dict[str, Any]:
        """
        计算偏移量（从崩溃转储）
        
        Args:
            pattern_dump: 模式转储字符串（十六进制）
            
        Returns:
            偏移量计算结果
        """
        try:
            cleaned = pattern_dump.strip().replace("0x", "")

            if cyclic and cyclic_find:
                try:
                    target_bytes = bytes.fromhex(cleaned)
                    # 尝试小端序
                    offset = cyclic_find(target_bytes[::-1])
                    if offset == -1:
                        offset = cyclic_find(target_bytes)
                except ValueError:
                    # cleaned 可能是字符串或已经是 bytes
                    if isinstance(cleaned, bytes):
                        target_bytes = cleaned
                    else:
                        target_bytes = cleaned.encode()
                    offset = cyclic_find(target_bytes)
                pattern_length = 8192
            else:
                pattern = self._generate_pattern(8192)
                try:
                    target_bytes = bytes.fromhex(cleaned)[::-1]
                except ValueError:
                    # cleaned 可能是字符串或已经是 bytes
                    if isinstance(cleaned, bytes):
                        target_bytes = cleaned
                    else:
                        target_bytes = cleaned.encode()
                offset = pattern.find(target_bytes)
                if offset == -1:
                    try:
                        target_bytes = bytes.fromhex(cleaned)
                        offset = pattern.find(target_bytes)
                    except ValueError:
                        offset = -1
                pattern_length = len(pattern)

            success = offset is not None and offset != -1
            if success:
                logger.info("找到偏移量: %s", offset)
            else:
                logger.warning("未找到偏移量，输入: %s", pattern_dump)

            return {
                "success": success,
                "offset": int(offset) if success else None,
                "pattern_length": pattern_length,
                "input_dump": pattern_dump,
            }
            
        except Exception as e:
            logger.error(f"偏移量计算失败: {e}")
            raise ExecutionError(f"偏移量计算失败: {e}", details={"error": str(e)})
    
    def _generate_pattern(self, length: int) -> bytes:
        """
        生成循环模式（De Bruijn 序列）
        
        Args:
            length: 模式长度
            
        Returns:
            模式字节串
        """
        # 使用简化的循环模式生成
        charset = b'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        pattern = b''
        
        for i in range(length):
            pattern += bytes([charset[i % len(charset)]])
            if (i + 1) % len(charset) == 0:
                pattern += bytes([charset[(i // len(charset)) % len(charset)]])
        
        return pattern[:length]
    
    def run_with_gdb_pattern(
        self,
        binary_path: str,
        pattern_length: int = 1000
    ) -> Dict[str, Any]:
        """
        使用 GDB 运行程序并自动检测崩溃偏移量
        
        Args:
            binary_path: 二进制文件路径
            pattern_length: 模式长度
            
        Returns:
            崩溃分析结果
        """
        if not Path(binary_path).exists():
            raise ExecutionError(f"文件不存在: {binary_path}", details={"path": binary_path})
        
        # 生成模式（在 try 外，便于调试）
        if cyclic:
            pattern = cyclic(pattern_length)
        else:
            pattern = self._generate_pattern(pattern_length)
        
        # 确保 pattern 是 bytes 类型，并转换为可打印字符串
        if isinstance(pattern, str):
            pattern_bytes = pattern.encode('latin-1')
        elif isinstance(pattern, bytes):
            pattern_bytes = pattern
        else:
            # 如果是其他类型（如 bytearray），转换为 bytes
            pattern_bytes = bytes(pattern)
        
        # 将 bytes 转换为字符串用于 GDB 脚本
        # 使用 latin-1 编码确保所有字节都能正确表示
        try:
            pattern_str = pattern_bytes.decode('latin-1')
        except Exception as e:
            logger.error(f"模式解码失败: {e}, pattern_bytes 类型: {type(pattern_bytes)}")
            raise ExecutionError(
                f"模式解码失败: {e}",
                details={"pattern_type": str(type(pattern_bytes)), "error": str(e)}
            )
        
        # 创建临时 GDB 脚本（确保是字符串）
        gdb_script = f"""set pagination off
set confirm off
run <<< "{pattern_str}"
info registers
quit
"""
        
        # 确保 gdb_script 是字符串类型
        if not isinstance(gdb_script, str):
            logger.error(f"gdb_script 类型错误: {type(gdb_script)}")
            raise ExecutionError(
                "GDB 脚本类型错误",
                details={"script_type": str(type(gdb_script))}
            )
        
        try:
            result = subprocess.run(
                ["gdb", "-batch", "-x", "/dev/stdin", binary_path],
                input=gdb_script.encode('utf-8'),  # 显式指定编码
                capture_output=True,
                text=True,
                timeout=10
            )
        except subprocess.TimeoutExpired:
            raise ExecutionError("GDB 执行超时", details={"timeout": 10, "binary": binary_path})
        except Exception as e:
            logger.error(f"GDB 模式运行失败: {e}")
            raise ExecutionError(
                "GDB 模式运行失败。这可能是由于 GDB 未安装、二进制文件损坏或环境问题。",
                details={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "binary": binary_path,
                    "hint": "请确保 GDB 已安装且二进制文件为有效的 ELF 可执行文件"
                }
            )
        
        # 解析 GDB 输出
        output = result.stdout + result.stderr
        
        # 解析寄存器值
        import re
        rip_pattern = r'rip\s+0x([0-9a-fA-F]+)'
        rsp_pattern = r'rsp\s+0x([0-9a-fA-F]+)'
        
        rip_match = re.search(rip_pattern, output)
        rsp_match = re.search(rsp_pattern, output)
        
        result_dict = {
            "success": True,
            "crashed": "SIGSEGV" in output or "SIGBUS" in output,
            "output": output[:2000],  # 限制输出长度
            "pattern_length": pattern_length,
        }
        
        # 尝试计算偏移量
        if rip_match:
            rip_value = rip_match.group(1)
            try:
                # 如果有 pwntools，使用 cyclic_find
                if cyclic_find:
                    # 将十六进制地址转换为字节用于查找
                    addr_int = int(rip_value, 16)
                    # 提取可能的模式字节
                    addr_bytes = addr_int.to_bytes(8, byteorder='little', signed=False)
                    offset = cyclic_find(addr_bytes[:4])  # 尝试查找前4字节
                    if offset != -1:
                        result_dict["rip_offset"] = offset
                    else:
                        result_dict["rip_value"] = f"0x{rip_value}"
                        result_dict["rip_offset_note"] = "无法在模式中找到匹配"
                else:
                    result_dict["rip_value"] = f"0x{rip_value}"
                    result_dict["rip_offset_note"] = "需要 pwntools 来计算偏移"
            except Exception as e:
                logger.warning(f"计算 RIP 偏移失败: {e}")
                result_dict["rip_value"] = f"0x{rip_value}"
                result_dict["rip_offset_error"] = str(e)
        
        if rsp_match:
            rsp_value = rsp_match.group(1)
            try:
                if cyclic_find:
                    addr_int = int(rsp_value, 16)
                    addr_bytes = addr_int.to_bytes(8, byteorder='little', signed=False)
                    offset = cyclic_find(addr_bytes[:4])
                    if offset != -1:
                        result_dict["rsp_offset"] = offset
                    else:
                        result_dict["rsp_value"] = f"0x{rsp_value}"
                        result_dict["rsp_offset_note"] = "无法在模式中找到匹配"
                else:
                    result_dict["rsp_value"] = f"0x{rsp_value}"
                    result_dict["rsp_offset_note"] = "需要 pwntools 来计算偏移"
            except Exception as e:
                logger.warning(f"计算 RSP 偏移失败: {e}")
                result_dict["rsp_value"] = f"0x{rsp_value}"
                result_dict["rsp_offset_error"] = str(e)
        
        return result_dict
