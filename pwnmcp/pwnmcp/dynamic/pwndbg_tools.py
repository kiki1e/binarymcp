"""
Pwndbg 工具集

整合 pwno-mcp 的 pwndbg 工具功能
为 MCP 提供高级调试命令
"""

import logging
from typing import Dict, Any, Optional, List, Tuple

from pwnmcp.gdb.controller import GdbController
from pwnmcp.core.exceptions import GdbError

logger = logging.getLogger(__name__)


class PwndbgTools:
    """Pwndbg 工具集 - 高级调试功能"""
    
    def __init__(self, gdb_controller: GdbController):
        """
        初始化 Pwndbg 工具
        
        Args:
            gdb_controller: GDB 控制器实例
        """
        self.gdb = gdb_controller
        self._session_history: List[Dict[str, Any]] = []
    
    def execute(self, command: str) -> Dict[str, Any]:
        """
        执行任意 GDB/pwndbg 命令
        
        Args:
            command: 命令字符串
            
        Returns:
            执行结果
        """
        logger.info(f"执行命令: {command}")
        
        try:
            result = self.gdb.execute_command(command)
            self._record_command(command, result)
            return result
            
        except (BrokenPipeError, ConnectionError, OSError) as e:
            raise GdbError(
                "GDB 连接已断开。这通常是因为 GDB 进程崩溃或未正确初始化。",
                details={
                    "command": command,
                    "error": str(e),
                    "hint": "请尝试重新加载二进制文件 (pwndbg_set_file) 或重启 MCP 服务器"
                }
            )
    
    def set_file(self, binary_path: str, clean_session: bool = True) -> Dict[str, Any]:
        """
        加载二进制文件（自动管理 GDB 会话）
        
        此方法会自动确保 GDB 环境正确初始化。如果检测到 GDB 
        进程异常，会尝试自动恢复。
        
        Args:
            binary_path: 文件路径
            clean_session: 是否在加载前清理会话状态（删除断点、watchpoints等）
            
        Returns:
            加载结果
        """
        logger.info(f"加载文件: {binary_path} (clean_session={clean_session})")
        
        try:
            # 如果需要清理会话，先执行清理命令
            if clean_session:
                cleanup_commands = [
                    "delete breakpoints",  # 删除所有断点
                    "delete display",      # 删除所有 display
                    "delete mem",          # 删除内存区域
                ]
                
                for cmd in cleanup_commands:
                    try:
                        self.gdb.execute_command(cmd, timeout=1.0, raise_on_timeout=False)
                        logger.debug(f"已执行清理命令: {cmd}")
                    except Exception as e:
                        # 清理命令失败不应阻止文件加载
                        logger.debug(f"清理命令失败（可忽略）: {cmd} - {e}")
            
            # 尝试加载文件
            result = self.gdb.set_file(binary_path)
            result["clean_session"] = clean_session
            self._record_command(f"set_file {binary_path}", result)
            return result
            
        except (BrokenPipeError, ConnectionError, OSError) as e:
            # GDB 进程可能已崩溃，尝试恢复
            logger.warning(f"GDB 进程异常 ({type(e).__name__}), 尝试重新初始化...")
            
            try:
                # 关闭旧的 GDB 连接
                try:
                    self.gdb.close()
                except:
                    pass
                
                # 重新初始化
                self.gdb.initialize()
                
                # 再次尝试加载文件
                result = self.gdb.set_file(binary_path)
                result["recovered"] = True
                result["recovery_message"] = "GDB 进程已自动恢复并重新初始化"
                
                self._record_command(f"set_file {binary_path} (recovered)", result)
                return result
                
            except Exception as recovery_error:
                # 恢复失败，返回清晰的错误信息
                raise GdbError(
                    "GDB 环境初始化失败。请检查二进制文件是否有效，或尝试重新启动 MCP 服务器。",
                    details={
                        "binary_path": binary_path,
                        "original_error": str(e),
                        "recovery_error": str(recovery_error),
                        "hint": "确保二进制文件存在且为有效的 ELF 可执行文件"
                    }
                )
    
    def attach(self, pid: int) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        附加到进程
        
        Args:
            pid: 进程ID
            
        Returns:
            (附加结果, 上下文信息)
        """
        logger.info(f"附加到进程: {pid}")
        result, context = self.gdb.attach(pid)
        self._record_command(f"attach {pid}", result)
        return result, context
    
    def run(self, args: str = "", start: bool = False) -> Dict[str, Any]:
        """
        运行程序（自动会话管理）
        
        Args:
            args: 命令行参数
            start: 是否在入口点停止（使用 starti 并尝试定位到 main）
            
        Returns:
            运行结果
        """
        logger.info(f"运行程序: args='{args}', start={start}")
        
        try:
            result = self.gdb.run(args, start)
            self._record_command(f"run {args}", result)
            return result
            
        except (BrokenPipeError, ConnectionError, OSError) as e:
            raise GdbError(
                "无法启动程序。GDB 进程可能未正确初始化或已崩溃。",
                details={
                    "args": args,
                    "start": start,
                    "error": str(e),
                    "hint": "请确保已使用 pwndbg_set_file 加载有效的二进制文件"
                }
            )
    
    def step_control(self, command: str) -> Dict[str, Any]:
        """
        步进控制
        
        Args:
            command: 步进命令 (c, n, s, ni, si)
            
        Returns:
            执行结果
        """
        command_map = {
            "c": self.gdb.continue_execution,
            "continue": self.gdb.continue_execution,
            "n": self.gdb.next,
            "next": self.gdb.next,
            "s": self.gdb.step,
            "step": self.gdb.step,
            "ni": self.gdb.nexti,
            "nexti": self.gdb.nexti,
            "si": self.gdb.stepi,
            "stepi": self.gdb.stepi,
        }
        
        func = command_map.get(command.lower())
        if not func:
            raise GdbError(f"未知的步进命令: {command}", details={"command": command, "valid_commands": list(command_map.keys())})
        
        result = func()
        self._record_command(command, result)
        return result
    
    def finish(self) -> Dict[str, Any]:
        """执行到当前函数返回"""
        result = self.gdb.finish()
        self._record_command("finish", result)
        return result
    
    def until(self, locspec: Optional[str] = None) -> Dict[str, Any]:
        """执行到指定位置"""
        result = self.gdb.until(locspec)
        self._record_command(f"until {locspec or ''}", result)
        return result
    
    def jump(self, locspec: str) -> Dict[str, Any]:
        """跳转到指定位置"""
        result = self.gdb.jump(locspec)
        self._record_command(f"jump {locspec}", result)
        return result
    
    def return_from_function(self) -> Dict[str, Any]:
        """强制从当前函数返回"""
        result = self.gdb.return_from_function()
        self._record_command("return", result)
        return result
    
    def get_context(self, context_type: str = "all") -> Dict[str, Any]:
        """
        获取调试上下文
        
        Args:
            context_type: 上下文类型
                - all: 所有上下文
                - regs/registers: 寄存器
                - stack: 栈
                - code/disasm: 反汇编
                - backtrace: 调用栈
                
        Returns:
            上下文信息
        """
        logger.info(f"获取上下文: {context_type}")
        return self.gdb.get_context(context_type)
    
    def set_breakpoint(
        self,
        location: str,
        condition: Optional[str] = None,
        temporary: bool = False
    ) -> Dict[str, Any]:
        """
        设置断点
        
        Args:
            location: 断点位置
            condition: 条件表达式
            temporary: 是否为临时断点
            
        Returns:
            断点设置结果
        """
        result = self.gdb.set_breakpoint(location, condition, temporary)
        self._record_command(f"break {location}", result)
        return result
    
    def delete_breakpoint(self, breakpoint_id: int) -> Dict[str, Any]:
        """删除断点"""
        result = self.gdb.delete_breakpoint(breakpoint_id)
        self._record_command(f"delete {breakpoint_id}", result)
        return result
    
    def list_breakpoints(self) -> Dict[str, Any]:
        """列出所有断点"""
        return self.gdb.list_breakpoints()
    
    def read_memory(
        self,
        address: str,
        size: int = 64,
        format: str = "x"
    ) -> Dict[str, Any]:
        """
        读取内存
        
        Args:
            address: 内存地址
            size: 读取大小
            format: 格式 (x=hex, d=dec, s=string, i=instruction)
            
        Returns:
            内存内容
        """
        return self.gdb.read_memory(address, size, format)
    
    def get_registers(self) -> Dict[str, Any]:
        """获取寄存器"""
        return self.gdb.get_registers()
    
    def get_backtrace(self) -> Dict[str, Any]:
        """获取调用栈"""
        return self.gdb.get_backtrace()
    
    # Pwndbg 特殊命令
    
    def checksec(self) -> Dict[str, Any]:
        """检查二进制保护"""
        return self.execute("checksec")
    
    def vmmap(self) -> Dict[str, Any]:
        """显示虚拟内存映射"""
        return self.execute("vmmap")
    
    def heap(self) -> Dict[str, Any]:
        """显示堆信息"""
        return self.execute("heap")
    
    def bins(self) -> Dict[str, Any]:
        """显示堆 bins"""
        return self.execute("bins")
    
    def telescope(self, address: Optional[str] = None, count: int = 10) -> Dict[str, Any]:
        """
        Telescope 命令 - 递归解引用
        
        Args:
            address: 起始地址
            count: 显示数量
            
        Returns:
            结果
        """
        cmd = "telescope"
        if address:
            cmd += f" {address}"
        cmd += f" {count}"
        return self.execute(cmd)
    
    def search(self, pattern: str, mapping: Optional[str] = None) -> Dict[str, Any]:
        """
        搜索内存
        
        Args:
            pattern: 搜索模式
            mapping: 内存映射名称
            
        Returns:
            搜索结果
        """
        cmd = f"search {pattern}"
        if mapping:
            cmd += f" {mapping}"
        return self.execute(cmd)
    
    def rop(self) -> Dict[str, Any]:
        """查找 ROP gadgets"""
        return self.execute("rop")
    
    def got(self) -> Dict[str, Any]:
        """显示 GOT 表"""
        return self.execute("got")
    
    def plt(self) -> Dict[str, Any]:
        """显示 PLT 表"""
        return self.execute("plt")
    
    def canary(self) -> Dict[str, Any]:
        """显示栈金丝雀值"""
        return self.execute("canary")
    
    def piebase(self) -> Dict[str, Any]:
        """显示 PIE 基址"""
        return self.execute("piebase")
    
    def procinfo(self) -> Dict[str, Any]:
        """显示进程信息"""
        return self.execute("procinfo")
    
    def get_session_history(self) -> List[Dict[str, Any]]:
        """获取会话历史"""
        return self._session_history
    
    def clear_session_history(self):
        """清空会话历史"""
        self._session_history = []
    
    def _record_command(self, command: str, result: Dict[str, Any]):
        """记录命令历史"""
        self._session_history.append({
            "command": command,
            "success": result.get("success", False),
            "state": result.get("state", "unknown"),
        })
        
        # 限制历史记录数量
        if len(self._session_history) > 100:
            self._session_history = self._session_history[-100:]
    
    # ===== 高级抽象工具 =====
    
    def break_at_main(self, args: str = "") -> Dict[str, Any]:
        """
        在 main 函数入口设置断点并运行（高级封装）
        
        自动处理动态链接、PIE 等复杂情况，最终停在 main 函数的第一条指令。
        这是一个常见操作的高级封装，避免手动执行多步命令。
        
        工作流程:
        1. 使用 starti 在第一条指令停止
        2. 尝试解析 main 函数地址
        3. 设置临时断点到 main
        4. 继续执行直到命中断点
        
        Args:
            args: 传递给程序的命令行参数
            
        Returns:
            包含执行结果和 main 函数信息的字典
        """
        logger.info(f"智能定位到 main 函数: args='{args}'")
        
        result = {
            "success": False,
            "steps": [],
            "main_address": None,
            "state": "unknown"
        }
        
        try:
            # 步骤 1: 设置参数（如果有）
            if args:
                self.gdb.execute_mi_command(f"-exec-arguments {args}")
                result["steps"].append("设置命令行参数")
            
            # 步骤 2: 使用 starti 在第一条指令停止
            logger.info("使用 starti 启动程序...")
            start_result = self.gdb.execute_command("starti", timeout=10.0, raise_on_timeout=False)
            result["steps"].append("starti 执行完成")
            
            # 等待程序停止
            import time
            for _ in range(50):
                if self.gdb.get_state() == "stopped":
                    break
                time.sleep(0.1)
            
            if self.gdb.get_state() != "stopped":
                raise GdbError("程序未能在 starti 后停止", details={})
            
            result["steps"].append("程序已在第一条指令停止")
            
            # 步骤 3: 尝试获取 main 地址
            logger.info("尝试解析 main 函数地址...")
            
            # 方法 1: 直接查询符号
            info_result = self.gdb.execute_command("info address main", timeout=2.0, raise_on_timeout=False)
            main_addr = None
            
            if info_result.get("success") and "no symbol" not in info_result.get("output", "").lower():
                # 解析输出获取地址
                import re
                addr_match = re.search(r'0x[0-9a-fA-F]+', info_result.get("output", ""))
                if addr_match:
                    main_addr = addr_match.group(0)
                    result["steps"].append(f"通过符号表找到 main 地址: {main_addr}")
            
            # 方法 2: 通过 __libc_start_main 的参数获取
            if not main_addr:
                logger.info("尝试通过 __libc_start_main 获取 main 地址...")
                
                # 在 __libc_start_main 设置断点
                bp_result = self.gdb.execute_command("b __libc_start_main", timeout=2.0, raise_on_timeout=False)
                if bp_result.get("success"):
                    result["steps"].append("在 __libc_start_main 设置断点")
                    
                    # 继续执行
                    self.gdb.continue_execution()
                    time.sleep(0.5)
                    
                    # 读取 RDI 寄存器（main 的地址在第一个参数）
                    reg_result = self.gdb.execute_command("p/x $rdi", timeout=2.0, raise_on_timeout=False)
                    if reg_result.get("success"):
                        addr_match = re.search(r'0x[0-9a-fA-F]+', reg_result.get("output", ""))
                        if addr_match:
                            main_addr = addr_match.group(0)
                            result["steps"].append(f"通过 __libc_start_main 参数找到 main 地址: {main_addr}")
            
            # 步骤 4: 在 main 设置断点并跳转
            if main_addr:
                result["main_address"] = main_addr
                
                # 删除之前的断点
                self.gdb.execute_command("delete breakpoints", timeout=1.0, raise_on_timeout=False)
                result["steps"].append("清理临时断点")
                
                # 在 main 设置断点
                bp_cmd = f"b *{main_addr}"
                bp_result = self.gdb.execute_command(bp_cmd, timeout=2.0, raise_on_timeout=False)
                if bp_result.get("success"):
                    result["steps"].append(f"在 main ({main_addr}) 设置断点")
                    
                    # 继续执行到 main
                    self.gdb.continue_execution()
                    time.sleep(0.5)
                    
                    # 检查是否成功到达 main
                    if self.gdb.get_state() == "stopped":
                        result["success"] = True
                        result["state"] = "stopped"
                        result["steps"].append("成功停在 main 函数入口")
                        logger.info(f"成功定位到 main 函数: {main_addr}")
                    else:
                        result["state"] = self.gdb.get_state()
                        result["note"] = "程序未停在预期位置"
                else:
                    result["note"] = "无法在 main 设置断点"
            else:
                # 无法获取 main 地址，但程序已在第一条指令停止
                result["success"] = True  # 部分成功
                result["state"] = "stopped"
                result["note"] = "未找到 main 符号，程序停在第一条指令。可以手动使用 'ni' 单步执行。"
                result["steps"].append("未找到 main 符号，保持在第一条指令")
            
            return result
            
        except Exception as e:
            logger.error(f"break_at_main 失败: {e}")
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            return result
    
    def get_function_address(self, function_name: str) -> Dict[str, Any]:
        """
        智能解析函数地址（处理 PIE 和符号）
        
        此工具能够在程序运行时解析函数的实际地址，自动处理 PIE、
        ASLR 和符号解析等复杂情况。
        
        Args:
            function_name: 函数名（如 "main", "system", "__libc_start_main"）
            
        Returns:
            包含函数地址和相关信息的字典
        """
        logger.info(f"解析函数地址: {function_name}")
        
        result = {
            "success": False,
            "function": function_name,
            "address": None,
            "method": None,
        }
        
        try:
            # 确保程序正在运行或已停止
            state = self.gdb.get_state()
            if state not in ("stopped", "running"):
                result["error"] = f"程序未运行，当前状态: {state}"
                return result
            
            # 方法 1: 使用 info address
            info_result = self.gdb.execute_command(
                f"info address {function_name}", 
                timeout=2.0, 
                raise_on_timeout=False
            )
            
            if info_result.get("success") and "no symbol" not in info_result.get("output", "").lower():
                import re
                addr_match = re.search(r'0x[0-9a-fA-F]+', info_result.get("output", ""))
                if addr_match:
                    result["success"] = True
                    result["address"] = addr_match.group(0)
                    result["method"] = "symbol_table"
                    result["output"] = info_result.get("output", "")
                    return result
            
            # 方法 2: 使用 p &function_name
            print_result = self.gdb.execute_command(
                f"p &{function_name}",
                timeout=2.0,
                raise_on_timeout=False
            )
            
            if print_result.get("success"):
                import re
                addr_match = re.search(r'0x[0-9a-fA-F]+', print_result.get("output", ""))
                if addr_match:
                    result["success"] = True
                    result["address"] = addr_match.group(0)
                    result["method"] = "print_expression"
                    result["output"] = print_result.get("output", "")
                    return result
            
            # 未能解析
            result["error"] = f"无法解析函数 '{function_name}' 的地址"
            result["hint"] = "确保程序已启动且符号可用"
            return result
            
        except Exception as e:
            logger.error(f"get_function_address 失败: {e}")
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            return result
