"""RetDec 反编译支持"""

from typing import Dict, Any


class RetDecAnalyzer:
    """RetDec 分析器占位实现"""

    def analyze(self, binary_path: str) -> Dict[str, Any]:
        return {
            "success": False,
            "message": "RetDec 未启用或未配置"
        }
