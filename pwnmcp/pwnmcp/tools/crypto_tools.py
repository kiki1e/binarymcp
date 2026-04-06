"""
密码学工具封装
- Hash 计算/识别/破解 (hashcat, john)
- RSA/数论分析 (gmpy2, sympy)
- 编码解码 (base64, hex, rot13, XOR)
- 频率分析 (古典密码)
"""
import subprocess
import shutil
import hashlib
import base64
import codecs
import os
import tempfile
import json
import re
import math
from typing import Dict, Any, Optional, List
from collections import Counter


class CryptoTools:
    """密码学分析与加解密工具"""

    def _is_tool_available(self, name: str) -> bool:
        return shutil.which(name) is not None

    def _execute(self, command: List[str], timeout: int = 300) -> Dict[str, Any]:
        tool_name = command[0]
        if not self._is_tool_available(tool_name):
            return {
                "success": False,
                "error": f"命令 '{tool_name}' 不存在。请确认它已安装并在 PATH 中。",
                "command": " ".join(command),
            }
        try:
            process = subprocess.run(command, capture_output=True, text=True, check=False, timeout=timeout)
            output_data = {"stdout": process.stdout.strip(), "stderr": process.stderr.strip()}
            if process.returncode != 0 and not output_data["stdout"]:
                return {"success": False, "error": f"返回码: {process.returncode}", "data": output_data, "command": " ".join(command)}
            return {"success": True, "data": output_data, "command": " ".join(command)}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"命令超时 ({timeout}s)", "command": " ".join(command)}
        except Exception as e:
            return {"success": False, "error": str(e), "command": " ".join(command)}

    # ═══════════════════════════════════════
    # Hash 工具
    # ═══════════════════════════════════════

    def hash_compute(self, data: str, algorithm: str = "sha256") -> Dict[str, Any]:
        """
        计算字符串的哈希值。
        支持: md5, sha1, sha224, sha256, sha384, sha512, sha3_256, sha3_512
        """
        supported = {
            "md5", "sha1", "sha224", "sha256", "sha384", "sha512",
            "sha3_256", "sha3_512", "blake2b", "blake2s",
        }
        if algorithm not in supported:
            return {"success": False, "error": f"不支持的算法: {algorithm}，支持: {', '.join(sorted(supported))}"}
        try:
            h = hashlib.new(algorithm)
            h.update(data.encode("utf-8"))
            hex_digest = h.hexdigest()
            return {
                "success": True,
                "data": {
                    "algorithm": algorithm,
                    "input": data,
                    "hash": hex_digest,
                    "length": len(hex_digest),
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def hash_compute_all(self, data: str) -> Dict[str, Any]:
        """一次性计算所有常用哈希值"""
        algos = ["md5", "sha1", "sha256", "sha512"]
        results = {}
        for algo in algos:
            h = hashlib.new(algo)
            h.update(data.encode("utf-8"))
            results[algo] = h.hexdigest()
        return {"success": True, "data": {"input": data, "hashes": results}}

    def hash_identify(self, hash_value: str) -> Dict[str, Any]:
        """
        根据哈希值的长度和格式自动识别可能的哈希类型。
        """
        hash_value = hash_value.strip().lower()
        length = len(hash_value)

        # 基于长度的匹配规则
        candidates = []
        length_map = {
            32: [("MD5", "0"), ("NTLM", "1000"), ("MD4", "900")],
            40: [("SHA-1", "100"), ("MySQL5", "300")],
            56: [("SHA-224", "1300"), ("SHA3-224", "17300")],
            64: [("SHA-256", "1400"), ("SHA3-256", "17400"), ("Keccak-256", "17800"), ("RIPEMD-256", None)],
            96: [("SHA-384", "10800"), ("SHA3-384", "17500")],
            128: [("SHA-512", "1700"), ("SHA3-512", "17600"), ("Whirlpool", "6100")],
        }

        if length in length_map:
            for name, hashcat_mode in length_map[length]:
                candidates.append({"type": name, "hashcat_mode": hashcat_mode})

        # 特殊格式检测
        if hash_value.startswith("$2b$") or hash_value.startswith("$2a$"):
            candidates.insert(0, {"type": "bcrypt", "hashcat_mode": "3200"})
        elif hash_value.startswith("$6$"):
            candidates.insert(0, {"type": "sha512crypt", "hashcat_mode": "1800"})
        elif hash_value.startswith("$5$"):
            candidates.insert(0, {"type": "sha256crypt", "hashcat_mode": "7400"})
        elif hash_value.startswith("$1$"):
            candidates.insert(0, {"type": "md5crypt", "hashcat_mode": "500"})
        elif hash_value.startswith("$apr1$"):
            candidates.insert(0, {"type": "Apache APR1", "hashcat_mode": "1600"})

        if not candidates:
            return {
                "success": True,
                "data": {"hash": hash_value, "length": length, "candidates": [], "message": "无法识别哈希类型"},
            }

        return {"success": True, "data": {"hash": hash_value, "length": length, "candidates": candidates}}

    def hash_crack(self, hash_value: str, hash_type: Optional[str] = None,
                   wordlist: Optional[str] = None, tool: str = "auto") -> Dict[str, Any]:
        """
        使用 hashcat 或 john 破解哈希。
        hash_type: hashcat 模式号 (如 "0" 表示 MD5) 或 john 格式名
        wordlist: 字典路径，默认 /usr/share/wordlists/rockyou.txt
        tool: "hashcat", "john", "auto" (自动选择可用工具)
        """
        if not wordlist:
            # 常见字典位置
            for wl in ["/usr/share/wordlists/rockyou.txt", "/usr/share/john/password.lst",
                       "/usr/share/seclists/Passwords/Leaked-Databases/rockyou.txt"]:
                if os.path.isfile(wl):
                    wordlist = wl
                    break
        if not wordlist:
            return {"success": False, "error": "未找到字典文件。请指定 wordlist 路径。"}

        use_hashcat = tool in ("hashcat", "auto") and self._is_tool_available("hashcat")
        use_john = tool in ("john", "auto") and self._is_tool_available("john")

        if not use_hashcat and not use_john:
            return {"success": False, "error": "hashcat 和 john 均未安装。"}

        # 写入临时哈希文件
        with tempfile.NamedTemporaryFile(mode="w", suffix=".hash", delete=False) as f:
            f.write(hash_value + "\n")
            hash_file = f.name

        try:
            if use_hashcat:
                command = ["hashcat", "-m", hash_type or "0", hash_file, wordlist,
                           "--force", "--quiet", "--potfile-disable", "-o", hash_file + ".out"]
                result = self._execute(command, timeout=600)
                out_file = hash_file + ".out"
                if os.path.isfile(out_file):
                    with open(out_file, "r") as f:
                        cracked = f.read().strip()
                    if cracked:
                        result["success"] = True
                        result["data"] = {"cracked": True, "result": cracked, "tool": "hashcat"}
                        return result
                result["data"] = result.get("data", {})
                result["data"]["cracked"] = False
                result["data"]["tool"] = "hashcat"
                return result
            else:
                # john
                fmt_arg = [f"--format={hash_type}"] if hash_type else []
                command = ["john", hash_file, f"--wordlist={wordlist}"] + fmt_arg
                result = self._execute(command, timeout=600)
                # 获取结果
                show_result = self._execute(["john", "--show", hash_file])
                if show_result.get("success"):
                    result["data"] = {"cracked": "0 password" not in show_result["data"]["stdout"],
                                      "result": show_result["data"]["stdout"], "tool": "john"}
                return result
        finally:
            for p in [hash_file, hash_file + ".out"]:
                try:
                    os.unlink(p)
                except OSError:
                    pass

    # ═══════════════════════════════════════
    # RSA / 数论分析
    # ═══════════════════════════════════════

    def rsa_analyze(self, n: str, e: str = "65537", c: Optional[str] = None,
                    p: Optional[str] = None, q: Optional[str] = None,
                    d: Optional[str] = None, dp: Optional[str] = None,
                    dq: Optional[str] = None) -> Dict[str, Any]:
        """
        RSA 参数分析与求解。自动尝试多种攻击方法。
        参数均为十进制或十六进制(0x前缀)字符串。

        支持场景:
        - 已知 p,q → 计算 d, 解密 c
        - 已知 n (小因子) → 尝试分解
        - 已知 dp/dq → partial key recovery
        - 小 e + 小 m → 低加密指数攻击
        """
        def to_int(val):
            if val is None:
                return None
            val = str(val).strip()
            if val.startswith("0x") or val.startswith("0X"):
                return int(val, 16)
            return int(val)

        try:
            n_int = to_int(n)
            e_int = to_int(e)
            c_int = to_int(c)
            p_int = to_int(p)
            q_int = to_int(q)
            d_int = to_int(d)
            dp_int = to_int(dp)
            dq_int = to_int(dq)
        except (ValueError, TypeError) as err:
            return {"success": False, "error": f"参数解析失败: {err}"}

        result_data = {
            "n": str(n_int),
            "e": str(e_int),
            "n_bits": n_int.bit_length() if n_int else None,
            "attacks_tried": [],
            "factored": False,
            "decrypted": False,
        }

        # 尝试加载 gmpy2，回退到 sympy
        gmpy2_available = False
        sympy_available = False
        try:
            import gmpy2
            gmpy2_available = True
        except ImportError:
            pass
        try:
            import sympy
            sympy_available = True
        except ImportError:
            pass

        if not gmpy2_available and not sympy_available:
            return {"success": False, "error": "需要 gmpy2 或 sympy 库。请运行 pip install gmpy2 sympy"}

        # Case 1: 已知 p, q
        if p_int and q_int:
            result_data["p"] = str(p_int)
            result_data["q"] = str(q_int)
            result_data["factored"] = True
        else:
            # Case 2: 尝试分解 n
            if n_int:
                # 小因子试除
                result_data["attacks_tried"].append("trial_division")
                for small_p in [2, 3, 5, 7, 11, 13]:
                    if n_int % small_p == 0:
                        p_int = small_p
                        q_int = n_int // small_p
                        result_data["factored"] = True
                        result_data["p"] = str(p_int)
                        result_data["q"] = str(q_int)
                        result_data["attack_used"] = "small_factor"
                        break

                # Fermat 分解 (n = p*q 且 p ≈ q 时有效)
                if not result_data["factored"] and n_int.bit_length() <= 512:
                    result_data["attacks_tried"].append("fermat")
                    if gmpy2_available:
                        a = gmpy2.isqrt(n_int) + 1
                        for _ in range(100000):
                            b2 = a * a - n_int
                            b = gmpy2.isqrt(b2)
                            if b * b == b2:
                                p_int = int(a + b)
                                q_int = int(a - b)
                                if p_int * q_int == n_int and p_int > 1 and q_int > 1:
                                    result_data["factored"] = True
                                    result_data["p"] = str(p_int)
                                    result_data["q"] = str(q_int)
                                    result_data["attack_used"] = "fermat"
                                    break
                            a += 1
                    elif sympy_available:
                        a = sympy.integer_nthroot(n_int, 2)[0] + 1
                        for _ in range(100000):
                            b2 = a * a - n_int
                            b, is_exact = sympy.integer_nthroot(b2, 2)
                            if is_exact:
                                p_int = int(a + b)
                                q_int = int(a - b)
                                if p_int * q_int == n_int and p_int > 1 and q_int > 1:
                                    result_data["factored"] = True
                                    result_data["p"] = str(p_int)
                                    result_data["q"] = str(q_int)
                                    result_data["attack_used"] = "fermat"
                                    break
                            a += 1

                # sympy factorint (适合较小的 n)
                if not result_data["factored"] and sympy_available and n_int.bit_length() <= 256:
                    result_data["attacks_tried"].append("sympy_factor")
                    try:
                        factors = sympy.factorint(n_int, limit=10**7)
                        if len(factors) >= 2:
                            primes = list(factors.keys())
                            p_int = primes[0]
                            q_int = n_int // p_int
                            result_data["factored"] = True
                            result_data["p"] = str(p_int)
                            result_data["q"] = str(q_int)
                            result_data["all_factors"] = {str(k): v for k, v in factors.items()}
                            result_data["attack_used"] = "sympy_factor"
                    except Exception:
                        pass

        # 计算私钥 d
        if result_data["factored"] and p_int and q_int and e_int and not d_int:
            phi = (p_int - 1) * (q_int - 1)
            if gmpy2_available:
                try:
                    d_int = int(gmpy2.invert(e_int, phi))
                except ZeroDivisionError:
                    d_int = None
            elif sympy_available:
                d_int = int(sympy.mod_inverse(e_int, phi))
            if d_int:
                result_data["d"] = str(d_int)

        # dp/dq partial key attack
        if dp_int and e_int and not result_data["factored"]:
            result_data["attacks_tried"].append("dp_leak")
            for k in range(1, e_int):
                p_candidate = (dp_int * e_int - 1 + k) // k
                if n_int % p_candidate == 0:
                    p_int = p_candidate
                    q_int = n_int // p_int
                    result_data["factored"] = True
                    result_data["p"] = str(p_int)
                    result_data["q"] = str(q_int)
                    result_data["attack_used"] = "dp_leak"
                    phi = (p_int - 1) * (q_int - 1)
                    if gmpy2_available:
                        d_int = int(gmpy2.invert(e_int, phi))
                    elif sympy_available:
                        d_int = int(sympy.mod_inverse(e_int, phi))
                    result_data["d"] = str(d_int)
                    break

        # 解密
        if c_int and d_int and n_int:
            if gmpy2_available:
                m_int = int(gmpy2.powmod(c_int, d_int, n_int))
            else:
                m_int = pow(c_int, d_int, n_int)
            result_data["decrypted"] = True
            result_data["plaintext_int"] = str(m_int)
            try:
                plaintext_bytes = m_int.to_bytes((m_int.bit_length() + 7) // 8, "big")
                result_data["plaintext_hex"] = plaintext_bytes.hex()
                result_data["plaintext_text"] = plaintext_bytes.decode("utf-8", errors="replace")
            except Exception:
                pass

        # 低加密指数攻击 (e=3, 小消息)
        if c_int and e_int <= 5 and not result_data.get("decrypted"):
            result_data["attacks_tried"].append("low_exponent")
            if gmpy2_available:
                m, exact = gmpy2.iroot(c_int, e_int)
                if exact:
                    result_data["decrypted"] = True
                    result_data["plaintext_int"] = str(int(m))
                    result_data["attack_used"] = "low_exponent"
                    try:
                        plaintext_bytes = int(m).to_bytes((int(m).bit_length() + 7) // 8, "big")
                        result_data["plaintext_hex"] = plaintext_bytes.hex()
                        result_data["plaintext_text"] = plaintext_bytes.decode("utf-8", errors="replace")
                    except Exception:
                        pass
            elif sympy_available:
                m, exact = sympy.integer_nthroot(c_int, e_int)
                if exact:
                    result_data["decrypted"] = True
                    result_data["plaintext_int"] = str(int(m))
                    result_data["attack_used"] = "low_exponent"

        return {"success": True, "data": result_data}

    # ═══════════════════════════════════════
    # 编码/解码
    # ═══════════════════════════════════════

    def encode_decode(self, data: str, method: str, direction: str = "encode") -> Dict[str, Any]:
        """
        通用编码/解码工具。
        method: base64, base32, hex, url, rot13, binary, decimal, morse
        direction: "encode" 或 "decode"
        """
        try:
            if method == "base64":
                if direction == "encode":
                    result = base64.b64encode(data.encode()).decode()
                else:
                    result = base64.b64decode(data).decode("utf-8", errors="replace")
            elif method == "base32":
                if direction == "encode":
                    result = base64.b32encode(data.encode()).decode()
                else:
                    result = base64.b32decode(data).decode("utf-8", errors="replace")
            elif method == "hex":
                if direction == "encode":
                    result = data.encode().hex()
                else:
                    result = bytes.fromhex(data.replace(" ", "").replace("0x", "")).decode("utf-8", errors="replace")
            elif method == "url":
                if direction == "encode":
                    from urllib.parse import quote
                    result = quote(data)
                else:
                    from urllib.parse import unquote
                    result = unquote(data)
            elif method == "rot13":
                result = codecs.encode(data, "rot_13")
            elif method == "binary":
                if direction == "encode":
                    result = " ".join(format(b, "08b") for b in data.encode())
                else:
                    bits = data.replace(" ", "")
                    result = "".join(chr(int(bits[i:i+8], 2)) for i in range(0, len(bits), 8))
            elif method == "decimal":
                if direction == "encode":
                    result = " ".join(str(b) for b in data.encode())
                else:
                    result = "".join(chr(int(x)) for x in data.split())
            elif method == "morse":
                morse_map = {
                    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".",
                    "F": "..-.", "G": "--.", "H": "....", "I": "..", "J": ".---",
                    "K": "-.-", "L": ".-..", "M": "--", "N": "-.", "O": "---",
                    "P": ".--.", "Q": "--.-", "R": ".-.", "S": "...", "T": "-",
                    "U": "..-", "V": "...-", "W": ".--", "X": "-..-", "Y": "-.--",
                    "Z": "--..", "0": "-----", "1": ".----", "2": "..---",
                    "3": "...--", "4": "....-", "5": ".....", "6": "-....",
                    "7": "--...", "8": "---..", "9": "----.", " ": "/",
                }
                if direction == "encode":
                    result = " ".join(morse_map.get(c.upper(), c) for c in data)
                else:
                    reverse_map = {v: k for k, v in morse_map.items()}
                    result = "".join(reverse_map.get(code, "?") for code in data.split(" "))
            else:
                return {"success": False, "error": f"不支持的编码方式: {method}，支持: base64, base32, hex, url, rot13, binary, decimal, morse"}

            return {
                "success": True,
                "data": {"method": method, "direction": direction, "input": data, "output": result},
            }
        except Exception as e:
            return {"success": False, "error": f"编码/解码失败: {str(e)}"}

    # ═══════════════════════════════════════
    # XOR 分析
    # ═══════════════════════════════════════

    def xor_analyze(self, data: str, key: Optional[str] = None, data_format: str = "hex") -> Dict[str, Any]:
        """
        XOR 加解密/分析。
        data: 输入数据
        key: XOR 密钥 (hex 格式)。不提供时尝试单字节暴力破解。
        data_format: "hex" 或 "text"
        """
        try:
            if data_format == "hex":
                data_bytes = bytes.fromhex(data.replace(" ", "").replace("0x", ""))
            else:
                data_bytes = data.encode()

            if key:
                # 已知密钥 XOR
                if key.startswith("0x"):
                    key = key[2:]
                key_bytes = bytes.fromhex(key) if all(c in "0123456789abcdefABCDEF" for c in key) else key.encode()
                result_bytes = bytes(b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(data_bytes))
                return {
                    "success": True,
                    "data": {
                        "result_hex": result_bytes.hex(),
                        "result_text": result_bytes.decode("utf-8", errors="replace"),
                        "key_used": key,
                    },
                }
            else:
                # 单字节暴力破解
                candidates = []
                for k in range(256):
                    result_bytes = bytes(b ^ k for b in data_bytes)
                    try:
                        text = result_bytes.decode("ascii")
                        if all(32 <= ord(c) < 127 or c in "\n\r\t" for c in text):
                            score = sum(1 for c in text if c.isalpha() or c == " ")
                            candidates.append({
                                "key": f"0x{k:02x}",
                                "result": text[:200],
                                "score": score,
                            })
                    except (UnicodeDecodeError, ValueError):
                        continue
                candidates.sort(key=lambda x: x["score"], reverse=True)
                return {
                    "success": True,
                    "data": {"brute_force": True, "candidates": candidates[:10]},
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ═══════════════════════════════════════
    # 频率分析 (古典密码)
    # ═══════════════════════════════════════

    def frequency_analysis(self, text: str) -> Dict[str, Any]:
        """
        对文本进行频率分析，用于破解古典密码 (Caesar, Vigenere, 替换密码等)。
        返回字母频率、二元组频率、三元组频率，以及 Caesar 暴力破解结果。
        """
        alpha_only = re.sub(r"[^a-zA-Z]", "", text).upper()
        if not alpha_only:
            return {"success": False, "error": "输入中没有字母字符"}

        total = len(alpha_only)
        freq = Counter(alpha_only)
        letter_freq = {ch: {"count": cnt, "percent": round(cnt / total * 100, 2)} for ch, cnt in freq.most_common()}

        # 英语标准频率
        english_freq = "ETAOINSHRDLCUMWFGYPBVKJXQZ"
        sorted_by_freq = "".join(ch for ch, _ in freq.most_common())

        # 二元组
        bigrams = Counter(alpha_only[i:i+2] for i in range(len(alpha_only) - 1))
        top_bigrams = dict(bigrams.most_common(15))

        # 三元组
        trigrams = Counter(alpha_only[i:i+3] for i in range(len(alpha_only) - 2))
        top_trigrams = dict(trigrams.most_common(10))

        # IC (Index of Coincidence)
        ic = sum(c * (c - 1) for c in freq.values()) / (total * (total - 1)) if total > 1 else 0

        # Caesar 暴力破解
        caesar_results = []
        for shift in range(26):
            decrypted = ""
            for c in text:
                if c.isalpha():
                    base = ord("A") if c.isupper() else ord("a")
                    decrypted += chr((ord(c) - base - shift) % 26 + base)
                else:
                    decrypted += c
            # 简单英语评分
            score = sum(1 for w in ["THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL", "CAN", "HER", "WAS", "ONE", "OUR"]
                       if w in decrypted.upper())
            caesar_results.append({"shift": shift, "text": decrypted[:100], "english_score": score})
        caesar_results.sort(key=lambda x: x["english_score"], reverse=True)

        return {
            "success": True,
            "data": {
                "total_letters": total,
                "letter_frequency": letter_freq,
                "frequency_order": sorted_by_freq,
                "english_expected": english_freq,
                "top_bigrams": top_bigrams,
                "top_trigrams": top_trigrams,
                "index_of_coincidence": round(ic, 6),
                "ic_note": "English ≈ 0.0667, Random ≈ 0.0385",
                "caesar_top5": caesar_results[:5],
            },
        }
