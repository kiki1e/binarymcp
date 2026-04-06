import json
import threading
import socketserver
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

import idaapi
import idautils
import idc
import ida_funcs
import ida_hexrays
import ida_lines
import ida_name

# 配置
HOST = "0.0.0.0"  # 允许 Docker 容器通过 host.docker.internal 访问
PORT = 4000

class IDARequestHandler(BaseHTTPRequestHandler):
    def _send_response(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        try:
            payload = json.loads(post_data.decode('utf-8'))
        except json.JSONDecodeError:
            self._send_response({"error": "Invalid JSON"}, 400)
            return

        path = urlparse(self.path).path
        response = {"error": "Unknown endpoint"}
        status = 404

        # 所有 IDA 操作必须在主线程执行
        def safe_execution():
            nonlocal response, status
            try:
                if path == "/ping":
                    response = self.handle_ping()
                    status = 200
                elif path == "/functions":
                    response = self.handle_functions()
                    status = 200
                elif path == "/decompile":
                    response = self.handle_decompile(payload)
                    status = 200
                elif path == "/disassemble":
                    response = self.handle_disassemble(payload)
                    status = 200
                elif path == "/xrefs":
                    response = self.handle_xrefs(payload)
                    status = 200
                elif path == "/info":
                    response = self.handle_info()
                    status = 200
                else:
                    status = 404
            except Exception as e:
                response = {"error": str(e)}
                status = 500

        # 在主线程中同步执行
        idaapi.execute_sync(safe_execution, idaapi.MFF_READ)
        self._send_response(response, status)

    # --- 处理函数 ---

    def handle_ping(self):
        return {"status": "pong", "db": idc.get_root_filename()}

    def handle_info(self):
        info = idaapi.get_inf_structure()
        return {
            "file": idc.get_root_filename(),
            "base": hex(info.min_ea),
            "proc": info.procname,
            "compiler": idc.get_compiler_name(info.cc.id)
        }

    def handle_functions(self):
        funcs = []
        for ea in idautils.Functions():
            name = idc.get_func_name(ea)
            start = ea
            end = idc.get_func_attr(ea, idc.FUNCATTR_END)
            funcs.append({"name": name, "start": hex(start), "end": hex(end)})
        return {"count": len(funcs), "functions": funcs}

    def _resolve_addr(self, target):
        """解析地址或函数名"""
        if isinstance(target, int):
            return target
        if isinstance(target, str):
            if target.startswith("0x"):
                return int(target, 16)
            # 尝试作为名称解析
            addr = idc.get_name_ea_simple(target)
            if addr != idc.BADADDR:
                return addr
        raise ValueError(f"Cannot resolve address for: {target}")

    def handle_decompile(self, payload):
        target = payload.get("target")
        if not target:
            raise ValueError("Missing 'target' parameter")
        
        ea = self._resolve_addr(target)
        if not idaapi.init_hexrays_plugin():
            return {"error": "Hex-Rays decompiler not available"}

        f = idaapi.get_func(ea)
        if not f:
            raise ValueError(f"No function at {hex(ea)}")

        try:
            cfunc = idaapi.decompile(f)
            if not cfunc:
                raise ValueError("Decompilation failed")
            
            sv = cfunc.get_pseudocode()
            code_lines = [idaapi.tag_remove(s.line) for s in sv]
            code = "\n".join(code_lines)
            
            return {
                "name": idc.get_func_name(f.start_ea),
                "address": hex(f.start_ea),
                "code": code
            }
        except Exception as e:
            return {"error": f"Decompilation error: {str(e)}"}

    def handle_disassemble(self, payload):
        target = payload.get("target")
        ea = self._resolve_addr(target)
        f = idaapi.get_func(ea)
        if not f:
            raise ValueError(f"No function at {hex(ea)}")

        lines = []
        curr = f.start_ea
        while curr < f.end_ea:
            disasm = idc.generate_disasm_line(curr, 0)
            lines.append(f"{hex(curr)}: {disasm}")
            curr = idc.next_head(curr, f.end_ea)
        
        return {
            "name": idc.get_func_name(f.start_ea),
            "assembly": "\n".join(lines)
        }

    def handle_xrefs(self, payload):
        target = payload.get("target")
        ea = self._resolve_addr(target)
        
        refs_to = []
        for ref in idautils.XrefsTo(ea, 0):
            refs_to.append({
                "from": hex(ref.frm),
                "type": "code" if idc.is_code(idc.get_full_flags(ref.frm)) else "data",
                "name": idc.get_func_name(ref.frm) or idc.get_name(ref.frm)
            })
            
        return {"address": hex(ea), "xrefs_to": refs_to}

# --- 服务器控制 ---

server = None
server_thread = None

def start_server():
    global server
    if server:
        print("[IDA-MCP] Server already running")
        return

    try:
        server = HTTPServer((HOST, PORT), IDARequestHandler)
        print(f"[IDA-MCP] Server started at http://{HOST}:{PORT}")
        server.serve_forever()
    except Exception as e:
        print(f"[IDA-MCP] Failed to start server: {e}")

def stop_server():
    global server
    if server:
        server.shutdown()
        server.server_close()
        server = None
        print("[IDA-MCP] Server stopped")

def main():
    global server_thread
    if server_thread and server_thread.is_alive():
        print("[IDA-MCP] Stopping existing server...")
        stop_server()
        server_thread.join()
    
    server_thread = threading.Thread(target=start_server)
    server_thread.daemon = True
    server_thread.start()
    print("[IDA-MCP] Plugin loaded. Ready to serve requests.")

if __name__ == "__main__":
    main()
