"""
逆向工程工具封装
- Ghidra headless (反编译/分析)
- radare2 (反汇编/反编译/分析)
- binwalk / firmware-mod-kit (固件分析)
"""
import subprocess
import shutil
import os
import tempfile
import json
import re
from typing import Dict, Any, Optional, List


class ReverseTools:
    """逆向工程 CLI 工具封装"""

    def __init__(self, ghidra_home: Optional[str] = None):
        self._ghidra_home = ghidra_home or os.getenv("GHIDRA_HOME", "/opt/ghidra")

    def _is_tool_available(self, name: str) -> bool:
        return shutil.which(name) is not None

    def _execute(self, command: List[str], timeout: int = 120) -> Dict[str, Any]:
        tool_name = command[0]
        if not self._is_tool_available(tool_name):
            return {
                "success": False,
                "error": f"命令 '{tool_name}' 不存在。请确认它已安装并在 PATH 中。",
                "command": " ".join(command),
            }
        try:
            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
            output_data = {
                "stdout": process.stdout.strip(),
                "stderr": process.stderr.strip(),
            }
            if process.returncode != 0:
                return {
                    "success": False,
                    "error": f"命令执行失败，返回码: {process.returncode}",
                    "data": output_data,
                    "command": " ".join(command),
                }
            return {"success": True, "data": output_data, "command": " ".join(command)}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"命令超时 ({timeout}s)", "command": " ".join(command)}
        except Exception as e:
            return {"success": False, "error": str(e), "command": " ".join(command)}

    # ═══════════════════════════════════════
    # Ghidra Headless
    # ═══════════════════════════════════════

    def _ghidra_headless_path(self) -> Optional[str]:
        """查找 analyzeHeadless 脚本"""
        # 直接在 PATH 中
        if self._is_tool_available("analyzeHeadless"):
            return "analyzeHeadless"
        # 在 GHIDRA_HOME/support/ 下
        candidate = os.path.join(self._ghidra_home, "support", "analyzeHeadless")
        if os.path.isfile(candidate):
            return candidate
        return None

    def ghidra_decompile(self, binary_path: str, function_name: Optional[str] = None) -> Dict[str, Any]:
        """
        使用 Ghidra headless 反编译指定函数（或全部函数）。
        需要 GHIDRA_HOME 环境变量或 /opt/ghidra 路径。
        """
        headless = self._ghidra_headless_path()
        if not headless:
            return {"success": False, "error": "Ghidra 未安装。请设置 GHIDRA_HOME 或安装 Ghidra。"}

        with tempfile.TemporaryDirectory(prefix="ghidra_") as tmpdir:
            project_dir = tmpdir
            project_name = "tmp_project"
            # 生成 Ghidra 脚本
            script_content = self._gen_decompile_script(function_name)
            script_path = os.path.join(tmpdir, "DecompileScript.java")
            with open(script_path, "w") as f:
                f.write(script_content)

            command = [
                headless, project_dir, project_name,
                "-import", binary_path,
                "-postScript", script_path,
                "-scriptlog", os.path.join(tmpdir, "script.log"),
                "-deleteProject",
                "-noanalysis" if function_name else "",
            ]
            command = [c for c in command if c]  # 过滤空字符串

            result = self._execute(command, timeout=300)

            # 读取脚本日志获取反编译结果
            log_path = os.path.join(tmpdir, "script.log")
            if os.path.isfile(log_path):
                with open(log_path, "r") as f:
                    log_content = f.read()
                if result.get("success"):
                    result["data"]["decompiled"] = log_content
                else:
                    result["script_log"] = log_content

            return result

    def ghidra_analyze(self, binary_path: str) -> Dict[str, Any]:
        """
        使用 Ghidra headless 完整分析二进制文件。
        返回函数列表、字符串、导入表等信息。
        """
        headless = self._ghidra_headless_path()
        if not headless:
            return {"success": False, "error": "Ghidra 未安装。请设置 GHIDRA_HOME 或安装 Ghidra。"}

        with tempfile.TemporaryDirectory(prefix="ghidra_") as tmpdir:
            script_content = self._gen_analysis_script()
            script_path = os.path.join(tmpdir, "AnalysisScript.java")
            with open(script_path, "w") as f:
                f.write(script_content)

            output_path = os.path.join(tmpdir, "analysis_output.json")
            command = [
                headless, tmpdir, "tmp_project",
                "-import", binary_path,
                "-postScript", script_path, output_path,
                "-deleteProject",
            ]
            result = self._execute(command, timeout=600)

            if os.path.isfile(output_path):
                try:
                    with open(output_path, "r") as f:
                        analysis_data = json.load(f)
                    result["data"] = analysis_data
                    result["success"] = True
                except (json.JSONDecodeError, Exception):
                    pass
            return result

    def _gen_decompile_script(self, function_name: Optional[str] = None) -> str:
        """生成 Ghidra 反编译脚本 (GhidraScript Java)"""
        if function_name:
            filter_code = f"""
            if (!func.getName().equals("{function_name}")) continue;
            """
        else:
            filter_code = ""
        return f"""
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;

public class DecompileScript extends GhidraScript {{
    @Override
    public void run() throws Exception {{
        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);
        FunctionIterator funcs = currentProgram.getFunctionManager().getFunctions(true);
        while (funcs.hasNext()) {{
            Function func = funcs.next();
            {filter_code}
            DecompileResults results = decompiler.decompileFunction(func, 30, monitor);
            if (results.depiledFunction() != null) {{
                println("=== " + func.getName() + " @ " + func.getEntryPoint() + " ===");
                println(results.getDecompiledFunction().getC());
            }}
        }}
        decompiler.dispose();
    }}
}}
"""

    def _gen_analysis_script(self) -> str:
        """生成 Ghidra 分析脚本"""
        return """
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.io.*;

public class AnalysisScript extends GhidraScript {
    @Override
    public void run() throws Exception {
        String outputPath = getScriptArgs()[0];
        StringBuilder sb = new StringBuilder();
        sb.append("{\\n");

        // Functions
        sb.append("  \\"functions\\": [\\n");
        FunctionIterator funcs = currentProgram.getFunctionManager().getFunctions(true);
        boolean first = true;
        while (funcs.hasNext()) {
            Function f = funcs.next();
            if (!first) sb.append(",\\n");
            sb.append("    {\\"name\\": \\"" + f.getName() + "\\", \\"address\\": \\"" + f.getEntryPoint() + "\\", \\"size\\": " + f.getBody().getNumAddresses() + "}");
            first = false;
        }
        sb.append("\\n  ],\\n");

        // Imports
        sb.append("  \\"imports\\": [\\n");
        SymbolTable st = currentProgram.getSymbolTable();
        SymbolIterator extSyms = st.getExternalSymbols();
        first = true;
        while (extSyms.hasNext()) {
            Symbol s = extSyms.next();
            if (!first) sb.append(",\\n");
            sb.append("    \\"" + s.getName() + "\\"");
            first = false;
        }
        sb.append("\\n  ]\\n");

        sb.append("}\\n");

        PrintWriter pw = new PrintWriter(new FileWriter(outputPath));
        pw.print(sb.toString());
        pw.close();
    }
}
"""

    # ═══════════════════════════════════════
    # radare2
    # ═══════════════════════════════════════

    def r2_decompile(self, binary_path: str, function_name: str = "main") -> Dict[str, Any]:
        """
        使用 radare2 反编译指定函数。
        需要安装 radare2 以及 r2ghidra/r2dec 插件。
        """
        # 尝试 r2ghidra (pdg) 然后回退到 r2dec (pdd) 再回退到 pdf (反汇编)
        commands = f"aaa;s sym.{function_name};pdg"
        result = self._execute(["r2", "-q", "-c", commands, binary_path], timeout=60)
        if not result.get("success") or "Cannot find" in result.get("data", {}).get("stderr", ""):
            # 回退到 pdd
            commands = f"aaa;s sym.{function_name};pdd"
            result = self._execute(["r2", "-q", "-c", commands, binary_path], timeout=60)
        if not result.get("success") or "Cannot find" in result.get("data", {}).get("stderr", ""):
            # 回退到反汇编
            commands = f"aaa;s sym.{function_name};pdf"
            result = self._execute(["r2", "-q", "-c", commands, binary_path], timeout=60)
        return result

    def r2_analyze(self, binary_path: str) -> Dict[str, Any]:
        """
        使用 radare2 全面分析二进制文件。
        返回: 函数列表、导入表、字符串、段信息等。
        """
        commands = ";".join([
            "aaa",           # 全面分析
            "aflj",          # 函数列表 (JSON)
            "echo ===SEPARATOR===",
            "iij",           # 导入表 (JSON)
            "echo ===SEPARATOR===",
            "izj",           # 字符串 (JSON)
            "echo ===SEPARATOR===",
            "iSj",           # 段信息 (JSON)
            "echo ===SEPARATOR===",
            "iEj",           # 导出表 (JSON)
        ])
        result = self._execute(["r2", "-q", "-c", commands, binary_path], timeout=120)
        if result.get("success"):
            stdout = result["data"]["stdout"]
            parts = stdout.split("===SEPARATOR===")
            parsed = {}
            labels = ["functions", "imports", "strings", "sections", "exports"]
            for i, label in enumerate(labels):
                if i < len(parts):
                    text = parts[i].strip()
                    try:
                        parsed[label] = json.loads(text)
                    except json.JSONDecodeError:
                        parsed[label] = text
            result["data"]["analysis"] = parsed
        return result

    def r2_command(self, binary_path: str, commands: str) -> Dict[str, Any]:
        """
        在 radare2 中执行自定义命令序列。
        commands: 分号分隔的 r2 命令，如 "aaa;pdf@main;axt@sym.imp.puts"
        """
        return self._execute(["r2", "-q", "-c", commands, binary_path], timeout=120)

    # ═══════════════════════════════════════
    # Binwalk / 固件分析
    # ═══════════════════════════════════════

    def firmware_scan(self, firmware_path: str) -> Dict[str, Any]:
        """使用 binwalk 扫描固件，列出所有识别到的文件系统和组件。"""
        result = self._execute(["binwalk", firmware_path])
        if result.get("success"):
            # 解析 binwalk 输出为结构化数据
            entries = []
            for line in result["data"]["stdout"].split("\n"):
                match = re.match(r"(\d+)\s+0x([0-9A-Fa-f]+)\s+(.*)", line)
                if match:
                    entries.append({
                        "offset_dec": int(match.group(1)),
                        "offset_hex": "0x" + match.group(2),
                        "description": match.group(3).strip(),
                    })
            result["data"]["entries"] = entries
        return result

    def firmware_extract(self, firmware_path: str, output_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        使用 binwalk 提取固件中的文件。
        output_dir: 输出目录，默认为 firmware_path 同目录下的 _extracted/
        """
        command = ["binwalk", "-e", firmware_path]
        if output_dir:
            command.extend(["-C", output_dir])
        result = self._execute(command, timeout=300)
        if result.get("success"):
            # 列出提取的文件
            extract_dir = output_dir or os.path.dirname(firmware_path)
            extracted_files = []
            for root, dirs, files in os.walk(extract_dir):
                for f in files:
                    fpath = os.path.join(root, f)
                    try:
                        size = os.path.getsize(fpath)
                        extracted_files.append({"path": fpath, "size": size})
                    except OSError:
                        extracted_files.append({"path": fpath, "size": -1})
            result["data"]["extracted_files"] = extracted_files[:200]  # 限制输出
        return result

    def firmware_entropy(self, firmware_path: str) -> Dict[str, Any]:
        """使用 binwalk 进行熵分析，检测加密/压缩区域。"""
        return self._execute(["binwalk", "-E", firmware_path])
