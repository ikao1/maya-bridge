"""Bridge server for opencode <-> Maya.

Listens on 127.0.0.1:<MAYA_BRIDGE_PORT or 7789> for newline-delimited JSON
requests and executes scripts on Maya's main thread, returning stdout, the
value of the last expression, and any traceback.

Auto-started by userSetup.py. To start manually, run in the Script Editor:

    import maya_bridge
    maya_bridge.start()
"""

import ast
import io
import json
import os
import socket
import socketserver
import sys
import threading
import time
import traceback

DEFAULT_PORT = int(os.environ.get("MAYA_BRIDGE_PORT", "7789"))
HOST = "127.0.0.1"

MAX_STDOUT = 400000
MAX_RESULT = 100000
MAX_ERROR = 100000

_py_namespace = None
_server = None


def _truncate(text, limit):
    if text is None or len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated %d chars]" % (len(text) - limit)


def _safe_repr(value):
    try:
        text = repr(value)
    except Exception as exc:
        text = "<repr failed: %s>" % exc
    return _truncate(text, MAX_RESULT)


def _namespace():
    global _py_namespace
    if _py_namespace is None:
        _py_namespace = {"__name__": "__maya_bridge__"}
        try:
            import maya.cmds
            _py_namespace["cmds"] = maya.cmds
            import maya.mel
            _py_namespace["mel"] = maya.mel
        except ImportError:
            pass
    return _py_namespace


def _exec_python(code):
    stdout = io.StringIO()
    result = None
    error = None
    ns = _namespace()
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = stdout
    sys.stderr = stdout
    try:
        tree = ast.parse(code, filename="<maya-bridge>", mode="exec")
        if tree.body and isinstance(tree.body[-1], ast.Expr):
            head = ast.Module(body=tree.body[:-1], type_ignores=[])
            exec(compile(head, "<maya-bridge>", "exec"), ns)
            tail = ast.Expression(tree.body[-1].value)
            result = _safe_repr(eval(compile(tail, "<maya-bridge>", "eval"), ns))
        else:
            exec(compile(tree, "<maya-bridge>", "exec"), ns)
    except BaseException:
        error = traceback.format_exc()
    finally:
        sys.stdout = old_out
        sys.stderr = old_err
    return {
        "ok": error is None,
        "stdout": _truncate(stdout.getvalue(), MAX_STDOUT),
        "result": result,
        "error": _truncate(error, MAX_ERROR) if error else None,
    }


def _exec_mel(code):
    stdout = io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = stdout
    sys.stderr = stdout
    try:
        import maya.mel as mel
        value = mel.eval(code)
        payload = {
            "ok": True,
            "stdout": _truncate(stdout.getvalue(), MAX_STDOUT),
            "result": _safe_repr(value),
            "error": None,
        }
    except BaseException:
        payload = {
            "ok": False,
            "stdout": _truncate(stdout.getvalue(), MAX_STDOUT),
            "result": None,
            "error": _truncate(traceback.format_exc(), MAX_ERROR),
        }
    finally:
        sys.stdout = old_out
        sys.stderr = old_err
    return payload


def _execute(code, lang):
    if lang == "mel":
        return _exec_mel(code)
    return _exec_python(code)


def _run_on_main(code, lang):
    try:
        from maya.utils import executeInMainThreadWithResult
    except ImportError:
        return _execute(code, lang)
    try:
        return executeInMainThreadWithResult(lambda: _execute(code, lang))
    except BaseException:
        return {
            "ok": False,
            "stdout": "",
            "result": None,
            "error": _truncate(traceback.format_exc(), MAX_ERROR),
        }


class _Handler(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            self.connection.settimeout(600)
        except OSError:
            pass
        while True:
            try:
                line = self.rfile.readline()
            except Exception:
                break
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            response = self._dispatch(line)
            try:
                self.wfile.write((json.dumps(response) + "\n").encode("utf-8"))
                self.wfile.flush()
            except Exception:
                break

    def _dispatch(self, line):
        try:
            request = json.loads(line.decode("utf-8"))
            if not isinstance(request, dict):
                raise ValueError("request must be a JSON object")
        except Exception:
            return {"bridge": 1, "ok": False, "error": "invalid JSON request"}
        response = {"bridge": 1, "id": request.get("id")}
        code = request.get("code")
        if not isinstance(code, str):
            response.update(
                {"ok": False, "stdout": "", "result": None, "error": "missing 'code' string"}
            )
            return response
        lang = request.get("lang", "python")
        if lang not in ("python", "mel"):
            lang = "python"
        response.update(_run_on_main(code, lang))
        return response


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def _probe(port):
    try:
        sock = socket.create_connection((HOST, port), timeout=1)
    except OSError:
        return False
    try:
        sock.settimeout(2)
        sock.sendall(b'{"id": 0, "code": "pass"}\n')
        return bool(sock.makefile("rb").readline())
    except OSError:
        return False
    finally:
        sock.close()


def start(port=None):
    global _server
    if port is None:
        port = DEFAULT_PORT
    if _server is not None:
        return {"status": "already_running", "port": _server.server_address[1]}
    try:
        _server = _Server((HOST, port), _Handler)
    except OSError:
        if _probe(port):
            return {"status": "already_running", "port": port}
        raise
    thread = threading.Thread(target=_server.serve_forever, daemon=True, name="maya-bridge")
    thread.start()
    print("maya-bridge listening on %s:%d" % (HOST, port))
    return {"status": "started", "port": port}


def stop():
    global _server
    if _server is None:
        return {"status": "not_running"}
    _server.shutdown()
    _server.server_close()
    _server = None
    return {"status": "stopped"}


if __name__ == "__main__":
    info = start()
    print("maya-bridge: %s" % json.dumps(info))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop()
