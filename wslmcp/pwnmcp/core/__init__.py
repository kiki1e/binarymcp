"""异常定义"""

from typing import Dict, Any, Optional


class PwnMcpError(Exception):
    """PwnMCP 基础异常类"""
    
    def __init__(
        self,
        message: str,
        error_type: str = "GENERAL_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error_type": self.error_type,
            "message": self.message,
            "details": self.details
        }


class BinaryNotFoundError(PwnMcpError):
    """二进制文件未找到"""
    def __init__(self, path: str):
        super().__init__(
            f"二进制文件未找到: {path}",
            error_type="BINARY_NOT_FOUND",
            details={"path": path}
        )


class AnalysisError(PwnMcpError):
    """分析失败"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_type="ANALYSIS_ERROR", details=details)


class GdbError(PwnMcpError):
    """GDB 操作失败"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_type="GDB_ERROR", details=details)


class ExecutionError(PwnMcpError):
    """执行失败"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_type="EXECUTION_ERROR", details=details)
