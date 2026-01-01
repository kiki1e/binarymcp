"""
GDB 控制器

整合 pwno-mcp 和 pwndbg-MCP_for_WSL 的 GDB 控制功能
使用 GDB/MI (Machine Interface) 提供稳定的程序化接口
"""

import logging
import select
import time
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pygdbmi import gdbcontroller

from pwnmcp.core.exceptions import GdbError

logger = logging.getLogger(__name__)


class GdbController:
    """GDB 控制器 - 使用 Machine Interface 进行稳定通信"""
    
    _logged_paths: set[str] = set()

    def __init__(self, gdb_path: str = "gdb"):
        """
        初始化 GDB 控制器
        
        Args:
            gdb_path: GDB 可执行文件路径 (默认: "gdb", 可使用 "pwndbg" 作为别名)
        """
        self.gdb_path = gdb_path
        self.controller = None
        self._initialized = False
        self._state = "idle"  # idle, running, stopped, exited
        self._inferior_pid = None
        self._binary_path = None
        
    def initialize(self) -> Dict[str, Any]:
        """
        初始化 GDB 并加载 pwndbg
        
        Returns:
            初始化状态字典
        """
        if self._initialized:
            return {"status": "already_initialized", "messages": []}
        
        try:
            resolved = self._resolve_gdb_binary(self.gdb_path)
            if resolved not in self._logged_paths:
                logger.info("使用 GDB 可执行文件: %s", resolved)
                self._logged_paths.add(resolved)
            else:
                logger.debug("重复使用已解析的 GDB 可执行文件: %s", resolved)

            # 启动 GDB 进程 (MI3 模式)
            self.controller = gdbcontroller.GdbController(
                command=[resolved, "--interpreter=mi3", "--quiet"]
            )
            
            # 立即标记为已初始化，避免 execute_mi_command 递归调用
            self._initialized = True
            
            results = []
            
            # 配置 GDB 设置
            try:
                for setting in [
                    "-gdb-set mi-async on",
                    "-gdb-set pagination off",
                    "-gdb-set confirm off",
                    "-gdb-set detach-on-fork off",
                    "-gdb-set follow-fork-mode parent",
                    "-gdb-set follow-exec-mode same",
                ]:
                    results.append(self.execute_mi_command(setting))
            except Exception as setup_error:
                # 如果初始化命令失败，重置状态以便重试
                self._initialized = False
                logger.error("GDB 配置失败: %s", setup_error)
                raise
            
            logger.info("GDB 初始化成功")
            
            return {
                "status": "initialized",
                "messages": results,
                "gdb_path": self.gdb_path
            }
            
        except Exception as e:
            logger.error("GDB 初始化失败: %s", e)
            raise GdbError("初始化失败", details={"gdb_path": self.gdb_path, "error": str(e)})

    def _resolve_gdb_binary(self, preferred: str) -> str:
        """解析 GDB 可执行文件路径，支持回退"""
        candidates = [preferred]

        # 若用户期望 pwndbg，则尝试常见别名
        if preferred != "gdb":
            candidates.extend(["pwndbg", "pwndbg-gdb"])

        candidates.append("gdb")

        for candidate in candidates:
            if Path(candidate).exists():
                return str(candidate)
            resolved = shutil.which(candidate)
            if resolved:
                return resolved

        raise GdbError("未找到可用的 GDB/Pwndbg 可执行文件", details={"candidates": candidates})
    
    def execute_mi_command(self, command: str) -> Dict[str, Any]:
        """
        执行 GDB/MI 命令
        
        Args:
            command: MI 命令字符串
            
        Returns:
            命令执行结果
        """
        if not self._initialized:
            self.initialize()
        
        logger.debug(f"执行 MI 命令: {command}")
        
        try:
            responses = self.controller.write(command)
            
            error_found = False
            for response in responses:
                if response.get("type") == "notify":
                    self._handle_notify(response)
                elif response.get("type") == "result" and response.get("message") == "error":
                    error_found = True
            
            return {
                "command": command,
                "responses": responses,
                "success": not error_found,
                "state": self._state,
            }
        except Exception as e:
            logger.error("命令执行失败 %s: %s", command, e)
            raise GdbError("执行命令失败", details={"command": command, "error": str(e)})
    
    def execute_command(self, command: str, timeout: float = 5.0, raise_on_timeout: bool = True) -> Dict[str, Any]:
        """
        执行传统 GDB 命令 (非 MI)
        
        Args:
            command: GDB 命令字符串
            timeout: 等待输出的超时时间（秒）
            raise_on_timeout: 超时时是否抛出异常
            
        Returns:
            命令执行结果
        """
        if not self._initialized:
            self.initialize()
        
        logger.debug(f"执行 GDB 命令: {command}")
        
        try:
            # 发送命令并立即获取初始响应
            responses = self.controller.write(command, timeout_sec=timeout, raise_error_on_timeout=False)
            all_responses = list(responses) if responses else []
            
            # 处理响应
            error_found = False
            output_lines = []
            
            for response in all_responses:
                resp_type = response.get("type", "")
                
                if resp_type == "notify":
                    self._handle_notify(response)
                elif resp_type == "result":
                    if response.get("message") == "error":
                        error_found = True
                elif resp_type == "console":
                    # 收集控制台输出
                    payload = response.get("payload", "")
                    if payload:
                        output_lines.append(payload)
                elif resp_type == "output":
                    # 某些输出类型
                    payload = response.get("payload", "")
                    if payload:
                        output_lines.append(payload)
            
            # 合并输出
            full_output = "".join(output_lines)
            
            # 如果没有收到任何响应，可能是超时
            if not all_responses and raise_on_timeout:
                logger.warning(f"命令 '{command}' 未收到响应（可能超时）")
            
            return {
                "command": command,
                "responses": all_responses,
                "output": full_output,
                "success": not error_found and len(all_responses) > 0,
                "state": self._state,
            }
        except Exception as e:
            logger.error("命令执行失败 %s: %s", command, e)
            raise GdbError("执行命令失败", details={"command": command, "error": str(e)})
    
    def _handle_notify(self, response: Dict[str, Any]):
        """
        处理 GDB 通知消息以跟踪状态
        
        Args:
            response: GDB 响应字典
        """
        message = response.get("message", "")
        
        if message == "running":
            self._state = "running"
            logger.debug("程序状态: 运行中")
            
        elif message == "stopped":
            self._state = "stopped"
            payload = response.get("payload", {})
            reason = payload.get("reason", "unknown")
            logger.debug(f"程序状态: 已停止 (原因: {reason})")
            
        elif message == "thread-group-exited":
            self._state = "exited"
            logger.debug("程序状态: 已退出")
            
        elif message == "thread-group-started":
            payload = response.get("payload", {})
            self._inferior_pid = payload.get("pid")
            logger.debug(f"线程组已启动, PID: {self._inferior_pid}")
    
    def set_file(self, binary_path: str) -> Dict[str, Any]:
        """
        加载二进制文件
        
        Args:
            binary_path: 二进制文件路径
            
        Returns:
            加载结果
        """
        target_path = Path(binary_path)

        if not target_path.exists():
            raise GdbError(f"文件不存在: {binary_path}", details={"path": binary_path})

        if target_path.is_dir():
            raise GdbError(f"路径指向的是目录，请提供可执行文件: {binary_path}", details={"path": binary_path})
        
        # 使用绝对路径并用引号包围以处理空格
        abs_path = str(target_path.resolve())
        result = self.execute_mi_command(f'-file-exec-and-symbols "{abs_path}"')
        
        if result.get("success"):
            self._binary_path = abs_path
            logger.info(f"已加载二进制文件: {abs_path}")
        
        return result
    
    def attach(self, pid: int) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        附加到现有进程
        
        Args:
            pid: 进程 ID
            
        Returns:
            (附加结果, 上下文信息)
        """
        result = self.execute_mi_command(f"-target-attach {pid}")
        
        # 获取上下文
        context = []
        if result.get("success"):
            self._inferior_pid = pid
            context = self._get_full_context()
        
        return result, context
    
    def run(self, args: str = "", start: bool = False) -> Dict[str, Any]:
        """
        运行程序
        
        Args:
            args: 命令行参数
            start: 是否在入口点停止
            
        Returns:
            运行结果
        """
        if not self._binary_path:
            raise GdbError("未加载二进制文件，请先使用 set_file", details={})
        
        if args:
            self.execute_mi_command(f"-exec-arguments {args}")
        
        if start:
            # 使用 starti 命令在第一条指令处停止
            # 这会停在动态链接器或程序的第一条指令
            logger.info("使用 starti 在第一条指令停止")
            result = self.execute_command("starti", timeout=10.0, raise_on_timeout=False)
            
            # 等待停止状态
            import time
            for _ in range(50):  # 最多等待5秒
                if self._state == "stopped":
                    break
                time.sleep(0.1)
                try:
                    responses = self.controller.get_gdb_response(timeout_sec=0.05, raise_error_on_timeout=False)
                    for response in responses or []:
                        if response.get("type") == "notify":
                            self._handle_notify(response)
                except:
                    pass
            
            # 如果成功停止，尝试继续到 main
            if self._state == "stopped":
                logger.info("已停在第一条指令，尝试定位到 main 函数")
                try:
                    # 尝试获取 main 地址
                    info_result = self.execute_command("info address main", timeout=2.0, raise_on_timeout=False)
                    if info_result.get("success") and "no symbol" not in info_result.get("output", "").lower():
                        # main 符号存在，设置临时断点并继续
                        self.execute_mi_command("-break-insert -t main")
                        continue_result = self.execute_mi_command("-exec-continue")
                        
                        # 等待断点命中
                        for _ in range(50):
                            if self._state == "stopped":
                                break
                            time.sleep(0.1)
                            try:
                                responses = self.controller.get_gdb_response(timeout_sec=0.05, raise_error_on_timeout=False)
                                for response in responses or []:
                                    if response.get("type") == "notify":
                                        self._handle_notify(response)
                            except:
                                pass
                        
                        result["continued_to_main"] = True
                    else:
                        # main 符号不存在，停在第一条指令也可以
                        logger.info("未找到 main 符号，停在第一条指令")
                        result["note"] = "No main symbol, stopped at first instruction"
                except Exception as e:
                    logger.warning(f"尝试定位 main 失败: {e}")
        else:
            result = self.execute_mi_command("-exec-run")
            
            # 等待程序到达停止或退出状态
            import time
            for _ in range(50):  # 最多等待5秒
                if self._state in ("stopped", "exited"):
                    break
                time.sleep(0.1)
                try:
                    responses = self.controller.get_gdb_response(timeout_sec=0.05, raise_error_on_timeout=False)
                    for response in responses or []:
                        if response.get("type") == "notify":
                            self._handle_notify(response)
                except:
                    pass
        
        # 更新结果中的状态
        result["state"] = self._state
        result["final_state"] = self._state
        
        return result
    
    def continue_execution(self) -> Dict[str, Any]:
        """继续执行"""
        return self.execute_mi_command("-exec-continue")
    
    def step(self) -> Dict[str, Any]:
        """单步执行 (进入函数)"""
        return self.execute_mi_command("-exec-step")
    
    def next(self) -> Dict[str, Any]:
        """单步执行 (跳过函数)"""
        return self.execute_mi_command("-exec-next")
    
    def stepi(self) -> Dict[str, Any]:
        """单步执行一条指令 (进入)"""
        return self.execute_mi_command("-exec-step-instruction")
    
    def nexti(self) -> Dict[str, Any]:
        """单步执行一条指令 (跳过)"""
        return self.execute_mi_command("-exec-next-instruction")
    
    def finish(self) -> Dict[str, Any]:
        """执行到当前函数返回"""
        return self.execute_mi_command("-exec-finish")
    
    def until(self, locspec: Optional[str] = None) -> Dict[str, Any]:
        """执行到指定位置或下一行"""
        if locspec:
            return self.execute_mi_command(f"-exec-until {locspec}")
        else:
            return self.execute_mi_command("-exec-until")
    
    def jump(self, locspec: str) -> Dict[str, Any]:
        """跳转到指定位置"""
        return self.execute_command(f"jump {locspec}")
    
    def return_from_function(self) -> Dict[str, Any]:
        """强制从当前函数返回"""
        return self.execute_command("return")
    
    def set_breakpoint(self, location: str, condition: Optional[str] = None, temporary: bool = False) -> Dict[str, Any]:
        """
        设置断点
        
        Args:
            location: 断点位置 (函数名、地址、文件:行号)
            condition: 条件表达式
            temporary: 是否为临时断点
            
        Returns:
            断点设置结果
        """
        cmd = "-break-insert"
        if temporary:
            cmd += " -t"
        if condition:
            cmd += f" -c '{condition}'"
        cmd += f" {location}"
        
        return self.execute_mi_command(cmd)
    
    def delete_breakpoint(self, breakpoint_id: int) -> Dict[str, Any]:
        """删除断点"""
        return self.execute_mi_command(f"-break-delete {breakpoint_id}")
    
    def list_breakpoints(self) -> Dict[str, Any]:
        """列出所有断点"""
        return self.execute_mi_command("-break-list")
    
    def read_memory(self, address: str, size: int = 64, format: str = "x") -> Dict[str, Any]:
        """
        读取内存
        
        Args:
            address: 内存地址
            size: 读取大小
            format: 格式 (x=hex, d=dec, s=string, i=instruction)
            
        Returns:
            内存内容
        """
        return self.execute_command(f"x/{size}{format} {address}")
    
    def get_registers(self) -> Dict[str, Any]:
        """获取寄存器信息"""
        return self.execute_mi_command("-data-list-register-values x")
    
    def get_backtrace(self) -> Dict[str, Any]:
        """获取调用栈"""
        return self.execute_mi_command("-stack-list-frames")
    
    def get_context(self, context_type: str = "all") -> Dict[str, Any]:
        """
        获取 pwndbg 上下文
        
        Args:
            context_type: 上下文类型 (regs, stack, code, backtrace, all)
            
        Returns:
            上下文信息
        """
        if self._state != "stopped":
            return {
                "command": f"context {context_type}",
                "responses": [],
                "output": "",
                "success": False,
                "state": self._state,
                "error": f"程序未停止，当前状态: {self._state}",
            }
        
        # context 命令产生大量格式化输出，需要更长的超时和特殊处理
        # 使用更长的超时（5秒）以确保捕获完整输出
        result = self.execute_command(f"context {context_type}", timeout=5.0, raise_on_timeout=False)
        
        # 如果输出为空或很短，可能是捕获问题
        # 在这种情况下，建议使用 pwndbg_command 直接执行
        if result.get("output", "") and len(result["output"]) < 100:
            result["note"] = "输出可能不完整。建议使用 pwndbg_command('context') 获取完整输出"
        
        return result
    
    def _get_full_context(self) -> List[Dict[str, Any]]:
        """获取完整上下文信息"""
        contexts = []
        for ctx_type in ["regs", "stack", "code", "backtrace"]:
            try:
                result = self.get_context(ctx_type)
                if result.get("success"):
                    contexts.append({
                        "type": ctx_type,
                        "data": result
                    })
            except Exception as e:
                logger.warning(f"获取 {ctx_type} 上下文失败: {e}")
        
        return contexts
    
    def get_state(self) -> str:
        """获取当前状态"""
        return self._state
    
    def close(self):
        """关闭 GDB 连接"""
        if self.controller:
            try:
                self.controller.exit()
            except Exception as e:
                logger.warning(f"关闭 GDB 时出错: {e}")
            finally:
                self.controller = None
                self._initialized = False
                self._state = "idle"
                logger.info("GDB 连接已关闭")
