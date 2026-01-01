import os
import pytest
from pwnmcp.static.analyzer import StaticAnalyzer
from pwnmcp.static.models import Architecture
from pwnmcp.tools import SubprocessTools

# 将此测试标记为可能需要较长时间，并且需要外部工具
@pytest.mark.slow
@pytest.mark.integration
def test_analyze_chall_binary():
    """
    测试静态分析器是否能正确分析 workspace/chall 文件。
    这是一个集成测试，因为它依赖于文件系统和外部命令行工具。
    """
    # 构造测试文件的路径
    # __file__ 是当前测试文件的路径
    # os.path.dirname() 用于获取目录
    # os.path.join() 用于安全地构造路径
    project_root = os.path.dirname(os.path.dirname(__file__))
    chall_path = os.path.join(project_root, "workspace", "chall")

    # 确认测试文件存在
    assert os.path.exists(chall_path), f"测试文件不存在: {chall_path}"

    # 创建分析器所需的依赖
    runner = SubprocessTools()
    analyzer = StaticAnalyzer(subprocess_runner=runner, enable_deep_analysis=False)

    # 执行分析
    try:
        facts = analyzer.analyze_binary(chall_path)
    except Exception as e:
        pytest.fail(f"分析器在分析 '{chall_path}' 时抛出异常: {e}")

    # 断言分析结果的关键部分
    assert facts is not None, "分析结果不应为 None"
    assert facts.arch == Architecture.AMD64, f"预期的架构是 AMD64, 但分析结果是 {facts.arch}"
    assert facts.bits == 64, f"预期的位数是 64, 但分析结果是 {facts.bits}"
    assert facts.protections.NX is True, "预期 NX 保护应为启用状态"

    print(f"\n成功分析 {chall_path}:")
    print(f"  架构: {facts.arch.value}")
    print(f"  保护: NX={facts.protections.NX}, PIE={facts.protections.PIE}, Canary={facts.protections.Canary}")
