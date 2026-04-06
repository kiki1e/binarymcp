"""
静态分析器

整合 pwn-mcp 的静态分析功能，支持：
- 基础分析（file, readelf, objdump）
- 高级分析（Rizin/radare2）
- 安全评估
"""

import logging
import re
from pathlib import Path
from typing import Dict, Any, List

from pwnmcp.static.models import BinaryFacts, Architecture, ProtectionInfo, ProtectionLevel
from pwnmcp.core.exceptions import AnalysisError, BinaryNotFoundError, ExecutionError
from pwnmcp.tools import SubprocessTools

logger = logging.getLogger(__name__)


class StaticAnalyzer:
    """静态分析器 - 支持基础和高级分析"""
    
    def __init__(self, subprocess_runner: SubprocessTools, enable_deep_analysis: bool = False):
        """
        初始化静态分析器
        
        Args:
            subprocess_runner: 用于执行外部命令的工具实例。
            enable_deep_analysis: 是否启用深度分析（需要 Rizin）。
        """
        self.runner = subprocess_runner
        self.enable_deep_analysis = enable_deep_analysis
        self._check_tools()
    
    def _check_tools(self):
        """检查可用的分析工具"""
        self._has_file = self._check_command("file --version")
        self._has_readelf = self._check_command("readelf --version")
        self._has_objdump = self._check_command("objdump --version")
        self._has_rizin = self._check_command("rizin -v") if self.enable_deep_analysis else False
        self._has_strings = self._check_command("strings --version")
        # checksec 有多种形式：pwn checksec（pwntools）或 checksec.sh
        self._has_checksec = self._check_command("checksec --help") or self._check_pwn_checksec()
        
        logger.info(f"可用工具: file={self._has_file}, readelf={self._has_readelf}, "
                   f"objdump={self._has_objdump}, rizin={self._has_rizin}, checksec={self._has_checksec}")
    
    def _check_command(self, command: str) -> bool:
        """检查命令是否可用"""
        try:
            result = self.runner.run_command(command, timeout=5)
            # 返回码为 0 或者有输出都认为命令可用
            return result["success"] or len(result["stdout"]) > 0 or len(result["stderr"]) > 0
        except ExecutionError:
            return False
    
    def _check_pwn_checksec(self) -> bool:
        """检查 pwntools 的 checksec 命令"""
        try:
            import pwn # noqa
            return True
        except ImportError:
            return False
    
    def analyze_binary(self, binary_path: str) -> BinaryFacts:
        """
        分析二进制文件
        
        Args:
            binary_path: 二进制文件路径
            
        Returns:
            分析结果
        """
        if not Path(binary_path).exists():
            raise BinaryNotFoundError(binary_path)
        
        logger.info(f"开始分析二进制文件: {binary_path}")
        
        facts = BinaryFacts(path=binary_path, arch=Architecture.UNKNOWN, bits=64)
        
        try:
            self._analyze_basic_info(facts)
            self._analyze_protections(facts)
            self._analyze_symbols(facts)
            self._analyze_strings(facts)
            self._analyze_sections(facts)
            self._security_assessment(facts)
            
            if self.enable_deep_analysis and self._has_rizin:
                self._deep_analysis_with_rizin(facts)
            
            logger.info(f"分析完成: {facts.arch.value} {facts.bits}位, "
                       f"保护: NX={facts.protections.NX}, PIE={facts.protections.PIE}")
            
            return facts
            
        except Exception as e:
            logger.exception(f"分析失败: {e}")
            raise AnalysisError(f"二进制分析失败: {e}", details={"path": binary_path, "error": str(e)})
    
    def _analyze_basic_info(self, facts: BinaryFacts):
        """分析基础信息"""
        if not self._has_file:
            logger.warning("file 命令不可用，跳过基础信息分析")
            return
        
        try:
            result = self.runner.run_command(f"file {facts.path}", timeout=10)
            output = result["stdout"].lower()
            
            if "x86-64" in output or "x86_64" in output:
                facts.arch, facts.bits = Architecture.AMD64, 64
            elif "i386" in output or "80386" in output:
                facts.arch, facts.bits = Architecture.I386, 32
            # ... 其他架构
            
            if "lsb" in output or "little endian" in output:
                facts.endian = "little"
            elif "msb" in output or "big endian" in output:
                facts.endian = "big"
            
            facts.file_size = Path(facts.path).stat().st_size
            
            if self._has_readelf:
                try:
                    entry_result = self.runner.run_command(f"readelf -h {facts.path}", timeout=5)
                    for line in entry_result["stdout"].split('\n'):
                        if 'Entry point address:' in line:
                            facts.entry_point = line.split(':')[1].strip()
                            break
                except ExecutionError as e:
                    logger.debug(f"获取入口点失败: {e}")
        except ExecutionError as e:
            logger.warning(f"基础信息分析失败: {e}")

    def _analyze_protections(self, facts: BinaryFacts):
        """分析保护机制"""
        if self._has_checksec:
            try:
                result = self.runner.run_command(f"checksec --file {facts.path}", timeout=15)
                output = result["stdout"].lower()
                facts.protections.NX = "nx enabled" in output
                facts.protections.PIE = "pie enabled" in output
                facts.protections.Canary = "canary found" in output
                if "full relro" in output: facts.protections.RELRO = ProtectionLevel.FULL
                elif "partial relro" in output: facts.protections.RELRO = ProtectionLevel.PARTIAL
                else: facts.protections.RELRO = ProtectionLevel.NONE
                return
            except ExecutionError as e:
                logger.warning(f"checksec 分析失败: {e}，回退到 readelf")
        
        if self._has_readelf:
            try:
                result_l = self.runner.run_command(f"readelf -l {facts.path}", timeout=10)
                facts.protections.NX = "GNU_STACK" in result_l["stdout"] and "RWE" not in result_l["stdout"]
                facts.protections.PIE = "INTERP" in result_l["stdout"] and "DYN" in result_l["stdout"]
                
                result_d = self.runner.run_command(f"readelf -d {facts.path}", timeout=10)
                if "BIND_NOW" in result_d["stdout"]:
                    facts.protections.RELRO = ProtectionLevel.FULL
                elif "GNU_RELRO" in result_d["stdout"]:
                    facts.protections.RELRO = ProtectionLevel.PARTIAL
                
                result_s = self.runner.run_command(f"readelf -s {facts.path}", timeout=10)
                facts.protections.Canary = "__stack_chk_fail" in result_s["stdout"]
            except ExecutionError as e:
                logger.warning(f"readelf 保护分析失败: {e}")

    def _analyze_symbols(self, facts: BinaryFacts):
        """分析符号信息"""
        if not self._has_readelf: return
        try:
            result = self.runner.run_command(f"readelf -s {facts.path}", timeout=15)
            output = result["stdout"]
            
            imports = {m.group(1) for m in re.finditer(r'(\w+)@', output) if 'UND' in m.string and 'FUNC' in m.string}
            exports = {m.group(1) for m in re.finditer(r'\s+(\w+)$', output, re.MULTILINE) if 'FUNC' in m.string and 'GLOBAL' in m.string}
            
            facts.imports, facts.exports = list(imports), list(exports)
            
            if self._has_objdump: self._analyze_plt_got(facts)
        except ExecutionError as e:
            logger.warning(f"符号分析失败: {e}")

    def _analyze_plt_got(self, facts: BinaryFacts):
        """分析 PLT 和 GOT 表"""
        try:
            plt_result = self.runner.run_command(f"objdump -d -j .plt {facts.path}", timeout=10)
            facts.plt = list({m.group(1) for m in re.finditer(r'<(.+)@plt>', plt_result["stdout"])})
            
            got_result = self.runner.run_command(f"objdump -R {facts.path}", timeout=10)
            facts.got = list({p.split()[-1] for p in got_result["stdout"].split('\n') if 'R_' in p and len(p.split()) >= 3})
        except ExecutionError as e:
            logger.warning(f"PLT/GOT 分析失败: {e}")

    def _analyze_strings(self, facts: BinaryFacts):
        """分析字符串"""
        if not self._has_strings: return
        try:
            result = self.runner.run_command(f"strings -n 4 {facts.path}", timeout=15)
            strings = result["stdout"].strip().split('\n')
            facts.strings_sample = strings[:50]
            
            interesting_patterns = [r'flag', r'password', r'admin', r'root', r'shell', r'/bin/', r'http[s]?://', r'\.so$', r'vulnerable', r'debug']
            facts.interesting_strings = list({s for s in strings for p in interesting_patterns if re.search(p, s, re.IGNORECASE)})[:20]
        except ExecutionError as e:
            logger.warning(f"字符串分析失败: {e}")

    def _analyze_sections(self, facts: BinaryFacts):
        """分析段信息"""
        if not self._has_readelf: return
        try:
            result = self.runner.run_command(f"readelf -S {facts.path}", timeout=10)
            sections = {}
            for line in result["stdout"].split('\n'):
                if line.strip().startswith('[') and ']' in line:
                    parts = line.split()
                    if len(parts) >= 7 and parts[5].startswith('0x'):
                        sections[parts[1]] = {"size": int(parts[5], 16), "flags": parts[7] if len(parts) > 7 else ""}
            facts.sections = sections
        except ExecutionError as e:
            logger.warning(f"段分析失败: {e}")

    def _security_assessment(self, facts: BinaryFacts):
        """安全评估"""
        vulnerabilities, dangerous_functions = [], []
        
        dangerous_func_patterns = ['strcpy', 'strcat', 'sprintf', 'gets', 'scanf', 'system', 'exec', 'popen', 'eval']
        all_funcs = facts.imports + facts.plt
        dangerous_functions.extend({func for func in all_funcs for pattern in dangerous_func_patterns if pattern in func.lower()})
        
        if not facts.protections.NX: vulnerabilities.append("Stack execution enabled - possible shellcode injection")
        if not facts.protections.Canary: vulnerabilities.append("No stack canary - possible buffer overflow")
        if not facts.protections.PIE: vulnerabilities.append("No PIE - fixed memory layout")
        if facts.protections.RELRO == ProtectionLevel.NONE: vulnerabilities.append("No RELRO - GOT overwrite possible")
        if 'system' in {f.lower() for f in all_funcs}: vulnerabilities.append("system() function available")
        
        facts.vulnerabilities, facts.dangerous_functions = vulnerabilities, list(set(dangerous_functions))

    def _deep_analysis_with_rizin(self, facts: BinaryFacts):
        """使用 Rizin 进行深度分析"""
        try:
            result = self.runner.run_command(f'rizin -c "ie" -q {facts.path}', timeout=30)
            if result["stdout"]:
                for line in result["stdout"].strip().split('\n'):
                    if 'entry0' in line:
                        parts = line.split()
                        if len(parts) >= 2: facts.entry_point = parts[1]
                        break
            logger.info("Rizin 深度分析完成")
        except ExecutionError as e:
            logger.warning(f"Rizin 深度分析失败: {e}")
