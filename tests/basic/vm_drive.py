#!/usr/bin/env python3
"""vm_drive.py — TODO-001 T-05 VM 端真实 UI 验收驱动（AutoUI MCP）。

由 tests/basic/verify_basic.py 调度；驱动 `auto run -r vm` 的原生 VM 界面：
autoui_snapshot / autoui_state / autoui_type / autoui_keyboard / autoui_action。
前置：全新隔离数据目录（无种子）；AUTOUI_MCP_PORT 已由调度方设置。

用法: python vm_drive.py <mcp-url> <mode>
  mode = full      ：创建/勾选/重启持久（重启由调度方负责，见 persist 子模式）
  mode = readonly  ：只读渲染 + 无种子检查（重启后的持久复核面）
输出：逐行 PASS/FAIL，末行 SUMMARY {json}；退出码 0/1。
"""

import json
import os
import re
import sys
import time

try:
    import requests
except ImportError:
    print("FAIL: requests not installed")
    sys.exit(2)

results = []


def record(step, ok, detail=""):
    results.append({"step": step, "ok": bool(ok), "detail": detail})
    print(("PASS" if ok else "FAIL") + ": " + step + ((" — " + detail) if detail else ""), flush=True)


class Mcp:
    def __init__(self, url):
        self.url = url
        self.n = 0

    def call(self, tool, **args):
        self.n += 1
        r = requests.post(self.url, json={"jsonrpc": "2.0", "method": "tools/call",
                                          "params": {"name": tool, "arguments": args},
                                          "id": self.n}, timeout=15)
        data = r.json()
        if "error" in data:
            raise RuntimeError("MCP error: %s" % data["error"])
        content = data.get("result", {}).get("content", [])
        return content[0]["text"] if content else ""

    def snapshot(self):
        return self.call("autoui_snapshot")

    def state(self, *fields):
        return self.call("autoui_state", fields=list(fields))

    def find_by_event(self, snap, event, attr="onclick"):
        pat = re.compile(r"#(aura_\d+|vnode_\d+)")
        cur = None
        target = attr + ": ." + event
        for line in snap.splitlines():
            m = pat.search(line)
            if m:
                cur = m.group(1)
            if target in line and cur is not None:
                return cur
        return None

    def click(self, element_id, action="press"):
        return self.call("autoui_action", element_id=element_id, action=action)

    def row_checkbox(self, snap, text):
        """含指定任务文本的行块内 checkbox 元素 id（checkbox 在文本之上）。"""
        lines = snap.splitlines()
        for i, l in enumerate(lines):
            if ('"%s"' % text) in l:
                for j in range(i, max(0, i - 12), -1):
                    m = re.match(r"\s*checkbox #(\S+)", lines[j])
                    if m:
                        return m.group(1)
        return None

    def item_rendered(self, snap, text):
        """任务已作为列表项渲染（text/button 节点），与输入框 value 区分。"""
        return re.search(r'(?:text|button) #\S+ "%s"' % re.escape(text), snap) is not None

    def type_and_enter(self, text):
        snap = self.snapshot()
        inp = self.find_by_event(snap, "AddTodo", "onenter")
        if not inp:
            return None
        self.call("autoui_type", element_id=inp, text=text)
        self.call("autoui_keyboard", key="Enter")
        return inp


def todos_from_state(st):
    m = re.search(r"todos:\s*\[", st)
    if not m:
        return []
    rest = st[m.end():]
    end = rest.find("]")
    if end == -1:
        return []
    inner = rest[:end].strip()
    if not inner:
        return []
    return [x.strip() for x in inner.split(",") if x.strip()]


def main():
    url = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "full"

    deadline = time.time() + 60
    up = False
    while time.time() < deadline:
        try:
            requests.post(url, json={"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}, timeout=2)
            up = True
            break
        except Exception:
            time.sleep(2)
    record("vm-mcp-ready", up, url)
    if not up:
        print("SUMMARY " + json.dumps({"results": results}))
        sys.exit(1)

    mcp = Mcp(url)
    # UI 树在 MCP 端口就绪后仍需一拍完成首次状态同步——轮询到主输入框出现
    snap = ""
    deadline = time.time() + 45
    while time.time() < deadline:
        snap = mcp.snapshot()
        if "What needs to be done?" in snap:
            break
        time.sleep(2)
    record("vm-render", "todos" in snap and "What needs to be done?" in snap, "App title + input visible")
    record("vm-no-seed", "Learn Auto Language" not in snap, "demo seed absent")

    if mode == "readonly":
        print("SUMMARY " + json.dumps({"results": results}))
        sys.exit(0 if all(r["ok"] for r in results) else 1)

    # 创建两条任务（真实 UI 输入 + Enter）
    t1 = "VM验收-中文\"引号\""
    t2 = "VM验收-second"
    inp = mcp.type_and_enter(t1)
    record("vm-input-found", inp is not None, "onenter element located")
    ok1 = False
    deadline = time.time() + 15
    while time.time() < deadline:
        if mcp.item_rendered(mcp.snapshot(), t1):
            ok1 = True
            break
        time.sleep(1.5)
    record("vm-create", ok1, "task item rendered after Enter")
    mcp.type_and_enter(t2)
    ok2 = False
    deadline = time.time() + 15
    while time.time() < deadline:
        if mcp.item_rendered(mcp.snapshot(), t2):
            ok2 = True
            break
        time.sleep(1.5)
    record("vm-create-2", ok2, "")

    # 勾选第二条完成：行定位 checkbox，VM 侧 checkbox 的动作是 toggle
    # （autoui_action press 对 Checkbox 无效）；行绑定 ToggleTodo(item.id)
    # 由 VM 行上下文解析（快照按字面显示，实测 resolved，见 Plan 证据）。
    time.sleep(1.0)
    snap = mcp.snapshot()
    cb2 = mcp.row_checkbox(snap, t2)
    if cb2:
        mcp.click(cb2, action="toggle")
        time.sleep(2)
    st = mcp.state("active_count")
    m = re.search(r"active_count:\s*(-?\d+)", st)
    active = int(m.group(1)) if m else -1
    record("vm-toggle", active == 1 and cb2 is not None,
           "active_count after completing one of two = %s (cb=%s)" % (active, cb2))

    # 重启持久由调度方处理（进程级重启后以 readonly 模式复核）
    print("PERSIST-MARK " + json.dumps({"t1": t1}))
    print("SUMMARY " + json.dumps({"results": results}))
    sys.exit(0 if all(r["ok"] for r in results) else 1)


if __name__ == "__main__":
    main()
