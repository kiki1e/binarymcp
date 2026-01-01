"""
漏洞利用模板生成器

生成 pwntools 脚本模板
"""

from typing import Dict, Any, Optional


def generate_pwntools_template(
    binary_path: str,
    facts: Optional[Dict[str, Any]] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    libc_path: Optional[str] = None # 添加 libc_path 参数
) -> str:
    """
    根据用户偏好和动态分析结果生成 pwntools 利用脚本模板
    
    Args:
        binary_path: 二进制文件路径
        facts: 二进制分析结果
        host: 远程主机
        port: 远程端口
        libc_path: libc 文件路径 (可选)
        
    Returns:
        Python 脚本内容
    """
    
    # 从 facts 中获取动态信息，如果不存在则使用默认值
    arch = facts.get("arch", "amd64") if facts else "amd64"

    # 基础模板，包含用户的快捷函数和 context 设置
    template = f"""import os
import sys
import time
from pwn import *
from ctypes import *
#from LibcSearcher import*

# ----- 配置 -----
context.os = 'linux'
context.arch = '{arch}'
context.log_level = "debug"
context.terminal=["tmux","splitw","-h"]

# ----- 路径 -----
# 本地二进制路径
binary_path = '{binary_path}'

# ----- 连接 -----
elf = ELF(binary_path)
"""
    if libc_path: # 如果提供了 libc_path, 则添加 libc 加载行
        template += f"libc = ELF('{libc_path}')\n"
    else:
        template += "# libc = ELF('/path/to/libc.so.6') # 如果需要\n"

    template += """
io = None
if args.REMOTE:
    io = remote(args.HOST or 'localhost', args.PORT or 9999)
elif args.DEBUG: # 允许用户传入 --debug 调试本地
    io = process(binary_path) # 或指定 LD_PRELOAD
else:
    io = process(binary_path)

# ----- 快捷函数 -----
s       = lambda data               :io.send(str(data))
sa      = lambda delim,data         :io.sendafter(str(delim), str(data))
sl      = lambda data               :io.sendline(str(data))
sla     = lambda delim,data         :io.sendlineafter(str(delim), str(data))
r       = lambda num                :io.recv(num)
ru      = lambda delims, drop=True  :io.recvuntil(delims, drop)
itr     = lambda                    :io.interactive()
uu32    = lambda data               :u32(data.ljust(4,b'\\x00'))
uu64    = lambda data               :u64(data.ljust(8,b'\\x00'))
leak    = lambda name,addr          :log.success('{} = {:#x}'.format(name, addr)) # 修正 leak 格式

# ----- 调试 -----
def duan():
    if args.DEBUG: # 只有在 --debug 模式下才 GDB attach
        gdb.attach(io)
        pause()

# =============== 漏洞利用代码 START ===============

# 在这里编写您的漏洞利用逻辑
# duan() # 在需要时取消注释以附加 gdb



# =============== 漏洞利用代码 END =================

io.interactive()
"""
    return template


def generate_gdb_profile(
    binary_path: str,
    breakpoints: Optional[list] = None
) -> str:
    """
    生成 GDB 调试配置
    
    Args:
        binary_path: 二进制文件路径
        breakpoints: 断点列表
        
    Returns:
        GDB 脚本内容
    """
    script = f'''# GDB 调试配置
# 生成工具: PwnMCP Kiki1e

# 加载二进制
file {binary_path}

# GDB 设置
set pagination off
set confirm off
set follow-fork-mode parent

# pwndbg 设置
set context-sections regs disasm code stack backtrace

'''
    
    # 添加断点
    if breakpoints:
        script += "# 断点\n"
        for bp in breakpoints:
            script += f"break {bp}\n"
    else:
        script += '''# 断点
# break main
# break *0x400000
'''
    
    script += '''
# 运行程序
# run

# 常用命令提示:
# c       - continue
# n       - next
# s       - step
# ni      - nexti
# si      - stepi
# vmmap   - 查看内存映射
# checksec- 查看保护
# telescope - 查看内存
# heap    - 查看堆
# search  - 搜索内存
'''
    
    return script


def generate_exploit_report(
    binary_path: str,
    facts: Optional[Dict[str, Any]] = None,
    strategy: Optional[Dict[str, Any]] = None,
    offsets: Optional[Dict[str, Any]] = None
) -> str:
    """
    生成漏洞利用报告
    
    Args:
        binary_path: 二进制文件路径
        facts: 分析结果
        strategy: 利用策略
        offsets: 偏移量信息
        
    Returns:
        Markdown 报告
    """
    report = f'''# PWN 漏洞利用分析报告

## 目标信息

- **文件**: `{binary_path}`
'''
    
    if facts:
        report += f'''- **架构**: {facts.get('arch', 'unknown')}
- **位数**: {facts.get('bits', 'unknown')}
- **字节序**: {facts.get('endian', 'unknown')}

### 保护机制

'''
        if "protections" in facts:
            prot = facts["protections"]
            report += f'''| 保护 | 状态 |
|------|------|
| NX | {'✅ 启用' if prot.get('NX') else '❌ 禁用'} |
| PIE | {'✅ 启用' if prot.get('PIE') else '❌ 禁用'} |
| Canary | {'✅ 启用' if prot.get('Canary') else '❌ 禁用'} |
| RELRO | {prot.get('RELRO', 'unknown')} |

'''
        
        # 危险函数
        if facts.get("dangerousFunctions"):
            report += '''### 危险函数

'''
            for func in facts["dangerousFunctions"]:
                report += f"- `{func}`\n"
            report += "\n"
        
        # 可能的漏洞
        if facts.get("suspicions"):
            report += '''### 潜在漏洞

'''
            for vuln in facts["suspicions"]:
                report += f"- {vuln}\n"
            report += "\n"
    
    # 利用策略
    if strategy:
        report += '''## 利用策略

'''
        if "approach" in strategy:
            report += f"**方法**: {strategy['approach']}\n\n"
        
        if "steps" in strategy:
            report += "**步骤**:\n\n"
            for i, step in enumerate(strategy["steps"], 1):
                report += f"{i}. {step}\n"
            report += "\n"
    
    # 偏移量信息
    if offsets:
        report += '''## 偏移量信息

'''
        for key, value in offsets.items():
            report += f"- **{key}**: {value}\n"
        report += "\n"
    
    report += '''## 建议

1. 仔细检查所有输入点
2. 分析程序控制流
3. 寻找可利用的函数调用
4. 构建 ROP 链或 shellcode
5. 测试和调试 payload

---

*报告由 PwnMCP Kiki1e 自动生成*
'''
    
    return report
