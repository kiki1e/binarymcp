"""
CTF 分析专用 Prompt 模板库

为不同赛题类型 (PWN/Reverse/Crypto/IoT) 构建结构化分析 Prompt。
"""

SYSTEM_PROMPT = """你是一位经验丰富的 CTF 安全竞赛专家，擅长 PWN、逆向工程、密码学和 IoT 安全分析。
你的任务是分析给定的二进制程序或密码学挑战，识别漏洞并提供详细的利用思路。
请用中文回答，回答要结构化、精确、可操作。"""


def build_pwn_prompt(binary_facts: dict, decompiled: str = "", gadgets: str = "") -> list[dict]:
    """构建 PWN 赛题分析 Prompt"""
    user_content = f"""## 赛题类型: PWN (二进制漏洞利用)

## 基本信息
- 架构: {binary_facts.get('arch', '未知')}
- 位数: {binary_facts.get('bits', '未知')}
- 保护机制: {binary_facts.get('protections', '未知')}
- 危险函数: {binary_facts.get('dangerous_functions', '无')}

## 反编译代码
```c
{decompiled or '暂无反编译结果'}
```

## ROP Gadgets (部分)
```
{gadgets[:2000] if gadgets else '暂无'}
```

## 请分析:
1. **漏洞类型**: 识别存在的漏洞 (栈溢出/堆溢出/格式化字符串/UAF 等)
2. **利用思路**: 给出详细的利用步骤
3. **关键偏移**: 计算需要的偏移量
4. **利用链**: 如果需要 ROP/ret2libc, 给出构造思路
5. **Exploit 脚本**: 生成完整的 pwntools exploit 脚本
"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def build_reverse_prompt(binary_facts: dict, decompiled: str = "", strings_info: str = "") -> list[dict]:
    """构建逆向分析 Prompt"""
    user_content = f"""## 赛题类型: Reverse (逆向工程)

## 基本信息
- 架构: {binary_facts.get('arch', '未知')}
- 位数: {binary_facts.get('bits', '未知')}
- 保护机制: {binary_facts.get('protections', '未知')}

## 字符串信息
```
{strings_info[:2000] if strings_info else '暂无'}
```

## 反编译代码
```c
{decompiled or '暂无反编译结果'}
```

## 请分析:
1. **程序逻辑**: 概括程序的核心验证逻辑
2. **加密/编码算法**: 识别使用的算法 (XOR/AES/自定义变换等)
3. **约束条件**: 列出 flag 需要满足的所有约束
4. **求解方法**: 给出求解思路 (逆算法/z3约束求解/angr符号执行)
5. **Flag 或求解脚本**: 如果可以直接求出 flag, 给出结果; 否则给出求解脚本
"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def build_crypto_prompt(challenge_info: dict, source_code: str = "") -> list[dict]:
    """构建密码学赛题分析 Prompt"""
    user_content = f"""## 赛题类型: Crypto (密码学)

## 题目信息
- 加密算法: {challenge_info.get('algorithm', '未知')}
- 已知信息: {challenge_info.get('known_info', '无')}

## 源代码/密文
```python
{source_code or '暂无'}
```

## 请分析:
1. **算法识别**: 识别使用的密码学算法和参数
2. **弱点分析**: 分析算法实现中的弱点 (弱密钥/padding oracle/CBC翻转等)
3. **攻击方法**: 详细说明攻击方法
4. **求解脚本**: 给出完整的 Python 求解脚本 (使用 pycryptodome/sympy/sage 等)
"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def build_iot_prompt(firmware_info: dict, binary_facts: dict = None, decompiled: str = "") -> list[dict]:
    """构建 IoT 固件分析 Prompt"""
    user_content = f"""## 赛题类型: IoT (物联网安全)

## 固件信息
- 架构: {firmware_info.get('arch', '未知')}
- 文件系统: {firmware_info.get('filesystem', '未知')}
- 提取的文件列表: {firmware_info.get('extracted_files', '无')}

## 关键二进制分析
```
{binary_facts or '暂无'}
```

## 反编译代码
```c
{decompiled or '暂无'}
```

## 请分析:
1. **固件结构**: 分析固件的组成和文件系统结构
2. **攻击面**: 识别网络服务/命令注入/硬编码密钥等攻击面
3. **漏洞识别**: 找出固件中的安全漏洞
4. **利用方法**: 给出利用思路和步骤
5. **Exploit**: 给出利用脚本或命令
"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def build_general_prompt(question: str, context: str = "") -> list[dict]:
    """通用分析 Prompt"""
    user_content = f"""## 分析请求

{question}

## 上下文信息
```
{context or '无额外上下文'}
```
"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
