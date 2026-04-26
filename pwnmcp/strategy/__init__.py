"""
策略规划器

基于二进制分析结果生成利用策略
"""

from typing import Dict, Any, List


class StrategyPlanner:
    """利用策略规划器"""
    
    def plan_from_facts(self, facts: Dict[str, Any]) -> Dict[str, Any]:
        """
        从二进制分析结果生成策略
        
        Args:
            facts: 二进制分析结果
            
        Returns:
            策略计划
        """
        protections = facts.get("protections", {})
        dangerous_funcs = facts.get("dangerousFunctions", [])
        suspicions = facts.get("suspicions", [])
        
        # 确定主要攻击向量
        approach = self._determine_approach(protections, dangerous_funcs, suspicions)
        
        # 生成步骤
        steps = self._generate_steps(approach, protections, dangerous_funcs)
        
        # 建议的工具和技术
        recommendations = self._generate_recommendations(approach, protections)
        
        return {
            "approach": approach,
            "steps": steps,
            "recommendations": recommendations,
            "difficulty": self._assess_difficulty(protections),
            "protections_summary": self._summarize_protections(protections),
        }
    
    def _determine_approach(
        self,
        protections: Dict[str, Any],
        dangerous_funcs: List[str],
        suspicions: List[str]
    ) -> str:
        """确定攻击方法"""
        
        # 检查是否有明显的溢出点
        has_overflow_funcs = any(
            func in ['strcpy', 'gets', 'sprintf', 'scanf']
            for func in dangerous_funcs
        )
        
        # 检查是否有 system 调用
        has_system = 'system' in dangerous_funcs or 'execve' in dangerous_funcs
        
        # 基于保护机制和函数选择策略
        if has_overflow_funcs and not protections.get("Canary"):
            if has_system and not protections.get("PIE"):
                return "ret2libc - 返回到 system 函数"
            elif not protections.get("NX"):
                return "shellcode injection - 栈溢出注入 shellcode"
            else:
                return "ROP chain - 返回导向编程"
        
        elif "heap" in str(suspicions).lower():
            return "heap exploitation - 堆利用"
        
        elif protections.get("PIE") and protections.get("NX"):
            return "information leak + ROP - 信息泄露配合 ROP"
        
        else:
            return "stack overflow - 栈溢出"
    
    def _generate_steps(
        self,
        approach: str,
        protections: Dict[str, Any],
        dangerous_funcs: List[str]
    ) -> List[str]:
        """生成利用步骤"""
        
        steps = []
        
        if "shellcode" in approach.lower():
            steps = [
                "1. 确定溢出点和偏移量",
                "2. 编写或选择合适的 shellcode",
                "3. 找到可执行的栈地址",
                "4. 构造 payload: padding + shellcode_addr",
                "5. 发送 payload 并获取 shell",
            ]
        
        elif "ret2libc" in approach.lower():
            steps = [
                "1. 确定溢出点和偏移量",
                "2. 找到 system 函数地址",
                "3. 找到 '/bin/sh' 字符串地址",
                "4. 构造 payload: padding + system_addr + ret_addr + binsh_addr",
                "5. 发送 payload 并获取 shell",
            ]
        
        elif "rop" in approach.lower():
            steps = [
                "1. 确定溢出点和偏移量",
                "2. 收集 ROP gadgets",
                "3. 构建 ROP 链",
            ]
            
            if protections.get("PIE"):
                steps.append("4. 泄露程序基址（如果需要）")
            
            steps.extend([
                f"{len(steps)+1}. 执行 ROP 链获取 shell 或泄露 libc",
                f"{len(steps)+2}. 如需要，二次利用",
            ])
        
        elif "heap" in approach.lower():
            steps = [
                "1. 分析堆分配和释放模式",
                "2. 寻找 UAF、double free 或堆溢出",
                "3. 伪造堆块结构",
                "4. 触发漏洞获取任意写",
                "5. 劫持控制流",
            ]
        
        elif "leak" in approach.lower():
            steps = [
                "1. 寻找信息泄露点",
                "2. 泄露程序和 libc 基址",
                "3. 计算 system 和 '/bin/sh' 地址",
                "4. 构造 ROP 链",
                "5. 发送最终 payload",
            ]
        
        else:
            steps = [
                "1. 动态调试确定崩溃点",
                "2. 计算溢出偏移量",
                "3. 分析可利用的函数和 gadgets",
                "4. 构造利用链",
                "5. 测试和调整 payload",
            ]
        
        return steps
    
    def _generate_recommendations(
        self,
        approach: str,
        protections: Dict[str, Any]
    ) -> List[str]:
        """生成建议和技巧"""
        
        recommendations = []
        
        # 通用建议
        recommendations.append("使用 pwntools 简化开发")
        recommendations.append("使用 pwndbg/gef 进行调试")
        
        # 基于保护机制的建议
        if protections.get("PIE"):
            recommendations.append("需要泄露程序基址来绕过 PIE")
        
        if protections.get("Canary"):
            recommendations.append("需要泄露或绕过栈金丝雀")
        
        if protections.get("NX"):
            recommendations.append("栈不可执行，使用 ROP 技术")
        
        if protections.get("RELRO") == "full":
            recommendations.append("Full RELRO 启用，GOT 不可写")
        
        # 基于方法的建议
        if "rop" in approach.lower():
            recommendations.append("使用 ROPgadget 或 ropper 查找 gadgets")
            recommendations.append("考虑使用 one_gadget 简化利用")
        
        if "heap" in approach.lower():
            recommendations.append("使用 pwndbg 的 heap 命令分析堆结构")
            recommendations.append("考虑 tcache poisoning 或 fastbin attack")
        
        return recommendations
    
    def _assess_difficulty(self, protections: Dict[str, Any]) -> str:
        """评估利用难度"""
        
        score = 0
        
        if protections.get("NX"):
            score += 1
        if protections.get("PIE"):
            score += 2
        if protections.get("Canary"):
            score += 2
        if protections.get("RELRO") == "full":
            score += 1
        
        if score == 0:
            return "简单 (无保护)"
        elif score <= 2:
            return "中等 (部分保护)"
        elif score <= 4:
            return "困难 (多重保护)"
        else:
            return "非常困难 (全保护)"
    
    def _summarize_protections(self, protections: Dict[str, Any]) -> Dict[str, str]:
        """总结保护机制"""
        return {
            "NX": "启用" if protections.get("NX") else "禁用",
            "PIE": "启用" if protections.get("PIE") else "禁用",
            "Canary": "启用" if protections.get("Canary") else "禁用",
            "RELRO": protections.get("RELRO", "unknown"),
        }
