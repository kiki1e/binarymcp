"""二进制分析数据模型"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class Architecture(Enum):
    """支持的架构"""
    AMD64 = "amd64"
    I386 = "i386"
    ARM = "arm"
    ARM64 = "arm64"
    MIPS = "mips"
    UNKNOWN = "unknown"


class ProtectionLevel(Enum):
    """保护机制级别"""
    NONE = "none"
    PARTIAL = "partial"
    FULL = "full"


@dataclass
class ProtectionInfo:
    """二进制保护信息"""
    NX: bool = False          # 数据执行保护
    PIE: bool = False         # 位置无关可执行文件
    RELRO: ProtectionLevel = ProtectionLevel.NONE  # 重定位只读
    Canary: bool = False      # 栈金丝雀
    ASLR: bool = False        # 地址空间布局随机化
    FORTIFY: bool = False     # 源码保护


@dataclass
class BinaryFacts:
    """二进制文件分析结果"""
    # 基本信息
    path: str
    arch: Architecture
    bits: int
    endian: str = "little"
    
    # 保护机制
    protections: ProtectionInfo = None
    
    # 符号信息
    plt: List[str] = None      # PLT 表函数
    got: List[str] = None      # GOT 表条目
    imports: List[str] = None   # 导入函数
    exports: List[str] = None   # 导出函数
    
    # 字符串和常量
    strings_sample: List[str] = None  # 字符串样本
    interesting_strings: List[str] = None  # 有趣的字符串
    
    # 安全分析
    vulnerabilities: List[str] = None      # 可能的漏洞
    dangerous_functions: List[str] = None   # 危险函数
    
    # 段信息
    sections: Dict[str, Any] = None
    
    # 其他元数据
    file_size: int = 0
    entry_point: Optional[str] = None
    
    def __post_init__(self):
        """初始化默认值"""
        if self.protections is None:
            self.protections = ProtectionInfo()
        if self.plt is None:
            self.plt = []
        if self.got is None:
            self.got = []
        if self.imports is None:
            self.imports = []
        if self.exports is None:
            self.exports = []
        if self.strings_sample is None:
            self.strings_sample = []
        if self.interesting_strings is None:
            self.interesting_strings = []
        if self.vulnerabilities is None:
            self.vulnerabilities = []
        if self.dangerous_functions is None:
            self.dangerous_functions = []
        if self.sections is None:
            self.sections = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "path": self.path,
            "arch": self.arch.value,
            "bits": self.bits,
            "endian": self.endian,
            "protections": {
                "NX": self.protections.NX,
                "PIE": self.protections.PIE,
                "RELRO": self.protections.RELRO.value,
                "Canary": self.protections.Canary,
                "ASLR": self.protections.ASLR,
                "FORTIFY": self.protections.FORTIFY,
            },
            "plt": self.plt,
            "got": self.got,
            "imports": self.imports,
            "exports": self.exports,
            "stringsSample": self.strings_sample,
            "interestingStrings": self.interesting_strings,
            "suspicions": self.vulnerabilities,
            "dangerousFunctions": self.dangerous_functions,
            "sections": self.sections,
            "fileSize": self.file_size,
            "entryPoint": self.entry_point,
        }