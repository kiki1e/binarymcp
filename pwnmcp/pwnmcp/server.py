"""
PwnMCP Kiki1e 服务器

整合静态分析、动态执行、pwndbg 调试、策略规划等功能
"""

import json
import logging
import os
from typing import Any, Dict, Optional
from uuid import uuid4

from mcp.server.fastmcp import FastMCP

from pwnmcp.core.exceptions import PwnMcpError, AnalysisError, ExecutionError, GdbError
from pwnmcp.static import StaticAnalyzer
from pwnmcp.dynamic import DynamicExecutor, PwndbgTools
from pwnmcp.gdb import GdbController
from pwnmcp.strategy import StrategyPlanner
from pwnmcp.templates import (
    generate_pwntools_template,
    generate_gdb_profile,
    generate_exploit_report,
)
from pwnmcp.state import SessionState
from pwnmcp.tools import SubprocessTools, GitTools, PythonTools
from pwnmcp.tools.pwn_cli_tools import PwnCliTools
from pwnmcp.retdec import RetDecAnalyzer

logger = logging.getLogger(__name__)


def _json_ok(data: Any) -> str:
    return json.dumps({"success": True, "data": data}, ensure_ascii=False)


def _json_error(error: Exception) -> str:
    if isinstance(error, PwnMcpError):
        payload = error.to_dict()
    else:
        payload = {
            "error_type": error.__class__.__name__,
            "message": str(error),
        }
    return json.dumps({"success": False, "error": payload}, ensure_ascii=False)


def build_server(
    workspace: str = "/workspace",
    enable_deep_static: bool = False,
    enable_retdec: bool = False,
    gdb_path: str = "gdb",
    log_level: str = "INFO",
    allow_dangerous: bool = True,
) -> FastMCP:
    logging.basicConfig(level=getattr(logging, log_level.upper(), logging.INFO))
    logger = logging.getLogger(__name__)

    # 创建工作目录，如果失败则使用当前目录
    try:
        os.makedirs(workspace, exist_ok=True)
    except PermissionError:
        logger.warning(f"无法创建 {workspace}，使用当前目录: {os.getcwd()}/workspace")
        workspace = os.path.join(os.getcwd(), "workspace")
        os.makedirs(workspace, exist_ok=True)

    subprocess_tools = SubprocessTools()
    analyzer = StaticAnalyzer(subprocess_runner=subprocess_tools, enable_deep_analysis=enable_deep_static)
    dynamic_executor = DynamicExecutor()
    gdb_controller = GdbController(gdb_path=gdb_path)
    pwndbg_tools = PwndbgTools(gdb_controller)
    strategy_planner = StrategyPlanner()
    session_state = SessionState(session_dir=os.path.join(workspace, "sessions"))
    git_tools = GitTools()
    python_tools = PythonTools()
    pwn_cli_tools = PwnCliTools()
    retdec_analyzer = RetDecAnalyzer()

    mcp = FastMCP("pwnmcp-kiki1e", log_level=log_level)

    logger.info(
        "Server configuration: workspace=%s deep_static=%s retdec=%s gdb_path=%s allow_dangerous=%s",
        workspace,
        enable_deep_static,
        enable_retdec,
        gdb_path,
        allow_dangerous,
    )

    if not allow_dangerous:
        logger.warning("危险操作已被禁用 (allow_dangerous=false) - 某些 pwndbg 命令可能被拒绝")

    def require_session() -> None:
        if not session_state.session_id:
            raise PwnMcpError("尚未初始化会话", error_type="SESSION_NOT_INITIALIZED")

    @mcp.tool()
    def health_check() -> str:
        """健康检查"""
        return _json_ok({"status": "ok"})

    @mcp.tool()
    def init_session(binary_path: str) -> str:
        """
        初始化会话（高级功能，通常不需要手动调用）
        
        PwnMCP 会自动管理调试会话。此工具仅在需要显式管理多个
        二进制文件的分析会话时使用。对于单个二进制文件的调试，
        直接使用 pwndbg_set_file 即可，无需手动创建会话。
        """
        session_id = uuid4().hex[:12]
        info = session_state.create_session(session_id, binary_path)
        return _json_ok(info)

    @mcp.tool()
    def load_session(session_id: str) -> str:
        """
        加载之前保存的会话（高级功能）
        
        用于恢复之前的分析状态。通常情况下，PwnMCP 会自动管理
        会话状态，无需手动加载。
        """
        data = session_state.load_session(session_id)
        if not data:
            raise PwnMcpError("会话不存在", error_type="SESSION_NOT_FOUND", details={"session_id": session_id})
        return _json_ok(data)

    @mcp.tool()
    def analyze_binary(path: str, deep: Optional[bool] = None) -> str:
        """静态分析二进制文件"""
        try:
            analyzer.enable_deep_analysis = bool(deep) if deep is not None else enable_deep_static
            facts = analyzer.analyze_binary(path)
            session_state.save_facts(facts.to_dict())
            return _json_ok(facts.to_dict())
        except Exception as exc:
            return _json_error(exc)

    @mcp.tool()
    def suggest_strategy() -> str:
        """根据分析结果给出策略"""
        require_session()
        if not session_state.facts:
            raise AnalysisError("尚未进行静态分析", details={})
        plan = strategy_planner.plan_from_facts(session_state.facts)
        session_state.save_strategy(plan)
        return _json_ok(plan)

    @mcp.tool()
    def calculate_offsets(pattern_dump_hex: str) -> str:
        """根据崩溃转储计算偏移量"""
        try:
            result = dynamic_executor.calculate_offsets(pattern_dump_hex)
            session_state.save_offsets(result)
            return _json_ok(result)
        except Exception as exc:
            return _json_error(exc)

    @mcp.tool()
    def run_local(
        path: str,
        args: Optional[list] = None,
        input_data: Optional[str] = None,
        timeout_ms: Optional[int] = None,
        aslr: bool = True,
    ) -> str:
        """运行本地二进制"""
        try:
            result = dynamic_executor.run_local(path, args, input_data, timeout_ms, aslr)
            session_state.record_command(f"run_local {path}", {"success": result.get("success", False)})
            return _json_ok(result)
        except Exception as exc:
            return _json_error(exc)

    @mcp.tool()
    def run_with_gdb_pattern(path: str, pattern_length: int = 1000) -> str:
        """
        使用循环模式自动检测缓冲区溢出偏移量（增强错误处理）
        
        此工具会生成一个 De Bruijn 序列，用 GDB 运行程序并捕获
        崩溃信息，自动计算控制流劫持所需的偏移量。
        
        参数：
        - path: 二进制文件路径
        - pattern_length: 模式长度（默认 1000 字节）
        
        返回信息包括：
        - crashed: 程序是否崩溃
        - rip_offset: RIP 寄存器的偏移量（如果检测到）
        - rsp_offset: RSP 寄存器的偏移量（如果检测到）
        
        注意：需要系统安装 GDB。如果失败，会返回详细的错误诊断。
        """
        try:
            result = dynamic_executor.run_with_gdb_pattern(path, pattern_length)
            return _json_ok(result)
        except Exception as exc:
            return _json_error(exc)

    @mcp.tool()
    def pwndbg_command(command: str) -> str:
        """执行任意 pwndbg/GDB 命令。仅在已加载二进制后使用。"""
        try:
            if not allow_dangerous:
                raise GdbError("服务器已禁止危险命令", details={"command": command})
            result = pwndbg_tools.execute(command)
            return _json_ok(result)
        except Exception as exc:
            return _json_error(exc)

    @mcp.tool()
    def pwndbg_set_file(path: str, clean_session: bool = True) -> str:
        """
        加载待调试的二进制文件（自动会话管理 + 智能清理）
        
        这是开始动态调试的第一步。此工具会自动初始化 GDB 环境，
        无需手动创建会话。如果 GDB 进程出现问题，会自动尝试恢复。
        
        参数:
        - path: 二进制文件路径（必须是有效的 ELF 可执行文件）
        - clean_session: 是否在加载前清理会话（删除断点、watchpoints等）
          默认为 True，确保每次加载都从干净状态开始
        
        清理内容（当 clean_session=True）:
        - 删除所有断点（breakpoints）
        - 删除所有 display 显示
        - 删除内存区域标记
        
        使用示例:
        1. pwndbg_set_file("/path/to/binary")              # 自动清理
        2. pwndbg_set_file("/path/to/binary", False)       # 保留断点
        3. pwndbg_run(start=True)                          # 启动
        4. pwndbg_context("all")                           # 查看上下文
        
        提示: 如果遇到"已有断点"等错误，确保 clean_session=True。
        """
        try:
            result = pwndbg_tools.set_file(path, clean_session=clean_session)
            session_state.binary_loaded = result.get("success", False)
            return _json_ok(result)
        except Exception as exc:
            return _json_error(exc)

    @mcp.tool()
    def pwndbg_run(args: str = "", start: bool = False) -> str:
        """
        运行当前已加载的程序（自动同步等待）
        
        启动程序执行。此工具会等待程序到达停止状态后才返回。
        
        参数说明：
        - args: 传递给程序的命令行参数
        - start: True 时使用 starti 在第一条指令停止，并尝试自动
          定位到 main 函数（如果存在符号）
        
        注意：使用前必须先调用 pwndbg_set_file 加载二进制文件。
        """
        try:
            if not allow_dangerous:
                raise GdbError("服务器已禁止执行命令", details={"command": "run"})
            result = pwndbg_tools.run(args, start)
            session_state.record_command("pwndbg_run", result)
            return _json_ok(result)
        except Exception as exc:
            return _json_error(exc)

    @mcp.tool()
    def pwndbg_context(context_type: str = "all") -> str:
        """
        获取当前调试上下文（增强输出捕获）
        
        显示程序当前状态的详细信息。必须在程序停止时调用。
        
        参数 context_type 可选值：
        - "all": 显示所有信息（寄存器、栈、代码、回溯）
        - "regs": 仅显示寄存器
        - "stack": 仅显示栈内容
        - "code": 仅显示反汇编代码
        - "backtrace": 仅显示调用栈
        
        返回的 output 字段包含完整的 pwndbg 格式化输出。
        """
        try:
            result = pwndbg_tools.get_context(context_type)
            return _json_ok(result)
        except Exception as exc:
            return _json_error(exc)

    @mcp.tool()
    def pwndbg_step(command: str) -> str:
        """执行步进命令。支持 c/n/s/ni/si 等。"""
        try:
            if not allow_dangerous and command.strip().lower() in {"run", "c", "continue"}:
                raise GdbError("服务器已禁止继续运行", details={"command": command})
            result = pwndbg_tools.step_control(command)
            return _json_ok(result)
        except Exception as exc:
            return _json_error(exc)

    # ===== 高级抽象工具 =====
    
    @mcp.tool()
    def pwndbg_break_at_main(args: str = "") -> str:
        """
        智能定位到 main 函数并设置断点（高级封装）
        
        这是一个高级工具，自动处理复杂的调试场景，将多步操作简化为一步。
        
        功能:
        - 自动处理动态链接、PIE、ASLR 等复杂情况
        - 智能查找 main 函数地址（通过符号表或 __libc_start_main）
        - 在 main 函数入口设置断点并运行到该位置
        - 最终程序停在 main 函数的第一条指令
        
        参数:
        - args: 传递给程序的命令行参数
        
        返回:
        - success: 是否成功定位
        - main_address: main 函数的实际地址
        - steps: 执行的步骤列表
        - state: 最终程序状态
        
        使用示例:
        1. pwndbg_set_file("/path/to/binary")
        2. pwndbg_break_at_main("arg1 arg2")  # 一步到达 main
        3. pwndbg_context("all")              # 查看上下文
        
        注意: 此工具必须在已加载二进制文件后使用。
        """
        try:
            if not allow_dangerous:
                raise GdbError("服务器已禁止执行命令", details={"command": "break_at_main"})
            result = pwndbg_tools.break_at_main(args)
            session_state.record_command("break_at_main", result)
            return _json_ok(result)
        except Exception as exc:
            return _json_error(exc)
    
    @mcp.tool()
    def pwndbg_get_function_address(function_name: str) -> str:
        """
        智能解析函数地址（处理 PIE 和符号）
        
        此工具能够在程序运行时解析函数的实际地址，自动处理 PIE、
        ASLR 和符号解析等复杂情况。
        
        参数:
        - function_name: 函数名（如 "main", "system", "malloc"）
        
        返回:
        - success: 是否成功解析
        - address: 函数的实际运行时地址（十六进制字符串）
        - method: 使用的解析方法（symbol_table 或 print_expression）
        
        使用场景:
        - 在 PIE 程序中获取函数的实际地址
        - 为手动设置断点获取地址
        - 验证 ASLR 的地址随机化
        
        使用示例:
        1. pwndbg_set_file("/path/to/binary")
        2. pwndbg_run(start=True)
        3. pwndbg_get_function_address("main")  # 获取 main 的实际地址
        
        注意: 程序必须处于运行或停止状态，符号信息可用。
        """
        try:
            result = pwndbg_tools.get_function_address(function_name)
            return _json_ok(result)
        except Exception as exc:
            return _json_error(exc)

    # ===== 生成与辅助工具 =====

    @mcp.tool()
    def generate_template(target_path: str, remote_host: Optional[str] = None, remote_port: Optional[int] = None) -> str:
        """生成 pwntools 利用模板。target_path 为输出文件路径。"""
        facts = session_state.facts or {}
        content = generate_pwntools_template(target_path, facts, remote_host, remote_port)
        return _json_ok({"template": content})

    @mcp.tool()
    def generate_gdb_profile(target_path: str) -> str:
        """生成 GDB 调试脚本。target_path 为输出路径。"""
        profile = generate_gdb_profile(target_path)
        return _json_ok({"profile": profile})

    @mcp.tool()
    def export_report() -> str:
        """导出当前分析的 Markdown 报告。"""
        data = generate_exploit_report(
            session_state.binary_path or "",
            session_state.facts,
            session_state.strategy,
            session_state.offsets,
        )
        return _json_ok({"report": data})
        
    # ===== 新增的命令行工具 =====

    @mcp.tool()
    def checksec(file_path: str) -> str:
        """
        运行 checksec 工具来检查二进制文件的安全属性。
        返回 JSON 格式的分析结果。
        """
        try:
            result = pwn_cli_tools.checksec(file_path)
            return _json_ok(result)
        except Exception as exc:
            return _json_error(exc)

    @mcp.tool()
    def ropgadget(binary_path: str, options: Optional[str] = None) -> str:
        """
        运行 ROPgadget 在二进制文件中查找 gadgets。
        options: 一个包含额外参数的字符串, 例如 "--only 'pop|ret'".
        """
        try:
            result = pwn_cli_tools.ropgadget(binary_path, options)
            return _json_ok(result)
        except Exception as exc:
            return _json_error(exc)

    @mcp.tool()
    def onegadget(libc_path: str) -> str:
        """
        运行 one_gadget 在指定的 libc 文件中查找 one-gadget ROP 攻击地址。
        """
        try:
            result = pwn_cli_tools.onegadget(libc_path)
            return _json_ok(result)
        except Exception as exc:
            return _json_error(exc)

    @mcp.tool()
    def patchelf(binary_path: str, set_interpreter: Optional[str] = None, set_rpath: Optional[str] = None) -> str:
        """
        [高危] 运行 patchelf 修改二进制文件的 ELF 头。
        可以修改解释器 (loader) 或 RPATH。
        这个操作会直接修改磁盘上的文件。
        """
        try:
            if not allow_dangerous:
                raise PwnMcpError("服务器已禁止危险命令 (patchelf)", details={"command": "patchelf"})
            result = pwn_cli_tools.patchelf(binary_path, set_interpreter, set_rpath)
            return _json_ok(result)
        except Exception as exc:
            return _json_error(exc)

    @mcp.tool()
    def run_command(command: str, cwd: Optional[str] = None, timeout: Optional[int] = None) -> str:
        """在受控 shell 中执行命令。可选 cwd 指定目录，timeout 为秒。"""
        try:
            result = subprocess_tools.run_command(command, cwd=cwd, timeout=timeout)
            return _json_ok(result)
        except Exception as exc:
            return _json_error(exc)

    @mcp.tool()
    def git_status(cwd: Optional[str] = None) -> str:
        """查看 Git 状态。未指定 cwd 时使用当前工作区。"""
        try:
            result = git_tools.status(cwd)
            return _json_ok(result)
        except Exception as exc:
            return _json_error(exc)

    @mcp.tool()
    def git_log(cwd: Optional[str] = None, limit: int = 5) -> str:
        """查看 Git 提交历史。limit 控制返回条目数。"""
        try:
            result = git_tools.log(cwd, limit)
            return _json_ok(result)
        except Exception as exc:
            return _json_error(exc)

    @mcp.tool()
    def python_run(code: str, cwd: Optional[str] = None) -> str:
        """在隔离的 Python 解释器中执行脚本。"""
        try:
            result = python_tools.run_script(code, cwd)
            return _json_ok(result)
        except Exception as exc:
            return _json_error(exc)

    if enable_retdec:

        @mcp.tool()
        def retdec_decompile(path: str) -> str:
            """调用 RetDec 反编译目标文件（实验性）。"""
            try:
                result = retdec_analyzer.analyze(path)
                return _json_ok(result)
            except Exception as exc:
                return _json_error(exc)

    return mcp


def run_server(
    host: str = "0.0.0.0",
    port: int = 5500,
    attach_port: int = 5501,
    workspace: str = "/workspace",
    log_level: str = "INFO",
    enable_deep_static: Optional[bool] = None,
    enable_retdec: Optional[bool] = None,
    gdb_path: Optional[str] = None,
    allow_dangerous: Optional[bool] = None,
) -> None:
    """启动 MCP 服务器 (STDIO)。"""

    env_deep = os.getenv("ENABLE_DEEP_STATIC", "false").lower() == "true"
    env_retdec = os.getenv("ENABLE_RETDEC", "false").lower() == "true"
    env_gdb = os.getenv("GDB_PATH", "pwndbg")
    env_dangerous = os.getenv("ALLOW_DANGEROUS", "true").lower() != "false"

    enable_deep_static = env_deep if enable_deep_static is None else enable_deep_static
    enable_retdec = env_retdec if enable_retdec is None else enable_retdec
    gdb_path = env_gdb if gdb_path is None else gdb_path
    allow_dangerous = env_dangerous if allow_dangerous is None else allow_dangerous

    server = build_server(
        workspace=workspace,
        enable_deep_static=enable_deep_static,
        enable_retdec=enable_retdec,
        gdb_path=gdb_path,
        log_level=log_level,
        allow_dangerous=allow_dangerous,
    )

    logger.info(
        "PwnMCP Kiki1e 启动: host=%s port=%s workspace=%s deep_static=%s allow_dangerous=%s",
        host,
        port,
        workspace,
        enable_deep_static,
        allow_dangerous,
    )

    try:
        # FastMCP 使用 run() 方法运行 STDIO 传输
        server.run()
    except KeyboardInterrupt:
        logger.info("检测到中断信号，正在优雅退出...")
    except Exception as exc:  # pragma: no cover - runtime safety net
        logger.exception("服务器运行异常: %s", exc)
        raise