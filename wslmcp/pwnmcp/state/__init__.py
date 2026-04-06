"""会话状态管理"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import json
from pathlib import Path


class SessionState:
    """会话状态管理器"""
    
    def __init__(self, session_dir: str = ".sessions"):
        """
        初始化会话状态
        
        Args:
            session_dir: 会话存储目录
        """
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(exist_ok=True)
        
        # 当前会话数据
        self.session_id: Optional[str] = None
        self.binary_path: Optional[str] = None
        self.binary_loaded: bool = False
        self.pid: Optional[int] = None
        self.state: str = "idle"
        
        # 分析结果
        self.facts: Optional[Dict[str, Any]] = None
        self.strategy: Optional[Dict[str, Any]] = None
        self.offsets: Optional[Dict[str, Any]] = None
        
        # 命令历史
        self.command_history: List[Dict[str, Any]] = []
    
    def create_session(self, session_id: str, binary_path: str) -> Dict[str, Any]:
        """
        创建新会话
        
        Args:
            session_id: 会话ID
            binary_path: 二进制文件路径
            
        Returns:
            会话信息
        """
        self.session_id = session_id
        self.binary_path = binary_path
        self.binary_loaded = False
        self.command_history = []
        
        session_info = {
            "session_id": session_id,
            "binary_path": binary_path,
            "created_at": datetime.now().isoformat(),
            "state": "created"
        }
        
        self._save_session()
        return session_info
    
    def update_state(self, new_state: str):
        """更新会话状态"""
        self.state = new_state
        self._save_session()
    
    def record_command(self, command: str, result: Dict[str, Any]):
        """记录命令执行"""
        self.command_history.append({
            "command": command,
            "timestamp": datetime.now().isoformat(),
            "success": result.get("success", False),
            "state": result.get("state", "unknown")
        })
        
        # 限制历史记录数量
        if len(self.command_history) > 100:
            self.command_history = self.command_history[-100:]
    
    def save_facts(self, facts: Dict[str, Any]):
        """保存分析结果"""
        self.facts = facts
        self._save_session()
    
    def save_strategy(self, strategy: Dict[str, Any]):
        """保存策略"""
        self.strategy = strategy
        self._save_session()
    
    def save_offsets(self, offsets: Dict[str, Any]):
        """保存偏移量"""
        self.offsets = offsets
        self._save_session()
    
    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        加载会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话数据
        """
        session_file = self.session_dir / f"{session_id}.json"
        
        if not session_file.exists():
            return None
        
        try:
            with open(session_file, 'r') as f:
                data = json.load(f)
            
            self.session_id = data.get("session_id")
            self.binary_path = data.get("binary_path")
            self.facts = data.get("facts")
            self.strategy = data.get("strategy")
            self.offsets = data.get("offsets")
            self.command_history = data.get("command_history", [])
            
            return data
        except Exception as e:
            print(f"加载会话失败: {e}")
            return None
    
    def _save_session(self):
        """保存会话到文件"""
        if not self.session_id:
            return
        
        session_file = self.session_dir / f"{self.session_id}.json"
        
        data = {
            "session_id": self.session_id,
            "binary_path": self.binary_path,
            "binary_loaded": self.binary_loaded,
            "pid": self.pid,
            "state": self.state,
            "facts": self.facts,
            "strategy": self.strategy,
            "offsets": self.offsets,
            "command_history": self.command_history[-50:],  # 只保存最近50条
            "updated_at": datetime.now().isoformat()
        }
        
        try:
            with open(session_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"保存会话失败: {e}")
    
    def get_session_data(self) -> Dict[str, Any]:
        """获取当前会话数据"""
        return {
            "session_id": self.session_id,
            "binary_path": self.binary_path,
            "binary_loaded": self.binary_loaded,
            "pid": self.pid,
            "state": self.state,
            "facts": self.facts,
            "strategy": self.strategy,
            "offsets": self.offsets,
        }
