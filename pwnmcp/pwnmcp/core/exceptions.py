"""异常模块 - 定义所有自定义异常"""

from typing import Dict, Any, Optional


class PwnMcpError(Exception):
    """PwnMCP 基础异常"""
    
    def __init__(self, message: str, error_type: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        初始化异常
        
        Args:
            message: 错误消息
            error_type: 错误类型标识
            details: 额外的错误详情
        """
        super().__init__(message)
        self.message = message
        self.error_type = error_type or self.__class__.__name__
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error_type": self.error_type,
            "message": self.message,
            "details": self.details,
        }


class BinaryNotFoundError(PwnMcpError):
    """二进制文件未找到"""
    
    def __init__(self, path: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"二进制文件未找到: {path}",
            error_type="BinaryNotFoundError",
            details={"path": path, **(details or {})}
        )


class AnalysisError(PwnMcpError):
    """分析错误"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_type="AnalysisError",
            details=details
        )


class GdbError(PwnMcpError):
    """GDB 相关错误"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_type="GdbError",
            details=details
        )


class ExecutionError(PwnMcpError):
    """执行错误"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_type="ExecutionError",
            details=details
        )


__all__ = [
    "PwnMcpError",
    "BinaryNotFoundError",
    "AnalysisError",
    "GdbError",
    "ExecutionError",
]
