#!/usr/bin/env python3
"""TODO-001 basic-capabilities verification (V-01..V-04).

Reproducible entry required by the Plan (§6):
    python tests/basic/verify_basic.py --profile vue
    python tests/basic/verify_basic.py --profile vm
    python tests/basic/verify_basic.py --api-only

Drives the REAL app: real rust backend service (`auto service --server rust`)
with an isolated AUTO_TODO_DATA, real HTTP API battery, real UI via Playwright
Chromium (tests/basic/ui_drive.mjs) when a UI profile is requested.

Toolchain resolution:
    AUTO_CLI        path to `auto` executable (default: auto-man debug build)
    PLAYWRIGHT_MODULE  path to playwright/index.mjs (npx cache probed automatically)

Exit code 0 = all checks passed. Evidence: stdout log (kept by caller under
docs/plans/attachments/, local-only).
"""

import argparse
import hashlib
import json
import os
import glob
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CLI = r"D:/autostack/auto-man/target/debug/auto.exe"

results = []


def record(step, ok, detail=""):
    results.append({"step": step, "ok": bool(ok), "detail": detail})
    print(("PASS" if ok else "FAIL") + ": " + step + ((" — " + detail) if detail else ""), flush=True)
    return ok


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def http(method, url, body=None, timeout=8):
    req = urllib.request.Request(url, method=method)
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw
    except Exception as e:
        return 0, {"ok": False, "err_code": "conn_failed", "err_detail": str(e)[:120]}


def pid_on_port(port):
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-NetTCPConnection -LocalPort %d -State Listen -ErrorAction SilentlyContinue)"
         ".OwningProcess | Select-Object -First 1" % port],
        capture_output=True, text=True).stdout.strip()
    return int(out) if out.isdigit() else None


def kill_port(port):
    killed = False
    for _ in range(6):
        pid = pid_on_port(port)
        if pid is None:
            return killed
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        killed = True
        time.sleep(1.5)
    return killed


def kill_stale_backends():
    """Kill leftover auto-todo-back processes AND `auto` CLI wrappers whose
    command line references this repo (scoped: other repos' autos untouched).
    Zombie wrappers hold the project AutoCache lock and hang new runs at init."""
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='auto-todo-back.exe' OR Name='auto.exe'\" | "
          "Where-Object { $_.CommandLine -like '*auto-todo*' } | "
          "ForEach-Object { $_.ProcessId }")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                         capture_output=True, text=True).stdout.split()
    for pid in out:
        if pid.isdigit():
            subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
    if out:
        time.sleep(2)


def start_service(cli, port, data_dir, fault=None, log_path=None):
    env = dict(os.environ)
    env["AUTO_TODO_DATA"] = data_dir
    if fault:
        env["AUTO_TODO_FAULT"] = fault
    log = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [cli, "service", "--server", "rust", "--back-port", str(port)],
        cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT)
    return proc, log


def wait_ready(port, timeout_s=240):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            code, body = http("GET", "http://127.0.0.1:%d/api/todos" % port, timeout=3)
            if code == 200 and isinstance(body, dict):
                return True
        except Exception:
            pass
        time.sleep(3)
    return False


def stop_service(proc, log, port, known_pid=None):
    """Stop `auto service` AND its spawned backend child.

    Terminate the CLI wrapper FIRST (it owns the project cache lock; a live
    wrapper blocks the next start at init), then free the port owned by the
    spawned auto-todo-back child, retrying until the port is actually free.
    """
    try:
        proc.terminate()
    except Exception:
        pass
    kill_port(port)
    try:
        log.close()
    except Exception:
        pass
    time.sleep(1)


def start_verified(cli, port, data_dir, log_path, fault=None, timeout_s=240, retries=1):
    """Start the service and wait for readiness; on timeout, kill everything
    and retry (the CLI occasionally stalls at init when locks linger)."""
    proc, log = start_service(cli, port, data_dir, fault=fault, log_path=log_path)
    for attempt in range(retries + 1):
        if wait_ready(port, timeout_s=timeout_s):
            return proc, log
        tail = ""
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                tail = "".join(f.readlines()[-6:])
        except Exception:
            pass
        print("WARN: service start not ready (attempt %d); log tail: %s" % (attempt + 1, tail[-300:]), flush=True)
        stop_service(proc, log, port)
        proc, log = start_service(cli, port, data_dir, fault=fault, log_path=log_path)
    return proc, log


def find_playwright_module():
    env = os.environ.get("PLAYWRIGHT_MODULE")
    if env:
        return env
    cache = os.path.join(os.environ.get("LOCALAPPDATA", ""), "npm-cache", "_npx")
    best = None
    for pdir in glob.glob(os.path.join(cache, "*", "node_modules", "playwright", "package.json")):
        try:
            with open(pdir, encoding="utf-8") as f:
                ver = json.load(f)["version"]
            base = os.path.dirname(pdir)
            browsers = os.path.join(os.path.dirname(base), "playwright-core", "browsers.json")
            with open(browsers, encoding="utf-8") as f:
                bl = json.load(f)["browsers"]
            need = [b["revision"] for b in bl if b["name"] in ("chromium", "chromium-headless-shell")]
            pw_root = os.environ.get("LOCALAPPDATA", "") + os.sep + "ms-playwright"
            have = all(os.path.isdir(os.path.join(pw_root, "chromium_headless_shell-" + r)) or
                       os.path.isdir(os.path.join(pw_root, "chromium-" + r)) for r in need)
            cand = os.path.join(base, "index.mjs")
            if have:
                return cand
            best = best or cand
        except Exception:
            continue
    return best


def resolve_cli():
    cli = os.environ.get("AUTO_CLI", DEFAULT_CLI)
    if not os.path.exists(cli):
        print("FATAL: auto CLI not found at " + cli + " (set AUTO_CLI)")
        sys.exit(2)
    return cli


def api_battery(cli, workdir):
    port = free_port()
    data = os.path.join(workdir, "api-data")
    os.makedirs(data)
    logp = os.path.join(workdir, "api-service.log")

    proc, log = start_verified(cli, port, data, log_path=logp)
    try:
        ok = pid_on_port(port) is not None
        if not record("service-ready", ok, "rust service on :%d" % port):
            return

        # V-01a: fresh db is empty, no demo seed
        code, body = http("GET", "http://127.0.0.1:%d/api/todos" % port)
        record("v01-fresh-empty", code == 200 and body.get("ok") is True and body.get("todos") == [],
               json.dumps(body, ensure_ascii=False)[:120])

        # V-01b: create with 中文/引号/换行, exact round-trip
        texts = ["买牛奶 \"fresh\"", "中文‘单引号’任务", "line1\nline2\ttab"]
        created = []
        for t in texts:
            code, body = http("POST", "http://127.0.0.1:%d/api/todos" % port, {"text": t})
            created.append(body)
        exact = all(c.get("ok") and c["todo"]["text"] == t for c, t in zip(created, texts))
        record("v01-create-unicode", exact, json.dumps(created, ensure_ascii=False)[:200])

        # V-01c: CRUD semantics
        code, body = http("PUT", "http://127.0.0.1:%d/api/todos/%d" % (port, created[0]["todo"]["id"]),
                          {"text": texts[0], "done": True})
        record("v01-update-done", body.get("ok") is True and body["todo"]["done"] is True, "")
        code, body = http("PUT", "http://127.0.0.1:%d/api/todos/99999" % port, {"text": "x", "done": False})
        record("v03-missing-id-not-found", body.get("ok") is False and body.get("err_code") == "not_found",
               json.dumps(body, ensure_ascii=False)[:120])
        code, body = http("POST", "http://127.0.0.1:%d/api/todos" % port, {"text": "   "})
        record("v03-blank-input", body.get("ok") is False and body.get("err_code") == "blank_input", "")

        # V-04a: delete max id → next create must not reuse
        max_id = max(c["todo"]["id"] for c in created)
        code, body = http("DELETE", "http://127.0.0.1:%d/api/todos/%d" % (port, max_id))
        record("v04-delete-max", body.get("ok") is True and body["todo"]["id"] == max_id, "")
        code, body = http("POST", "http://127.0.0.1:%d/api/todos" % port, {"text": "after-max-delete"})
        new_id = body.get("todo", {}).get("id", -1)
        record("v04-id-no-reuse", body.get("ok") is True and new_id > max_id,
               "deleted %d, created %d" % (max_id, new_id))

        # AC-02 sample: 200 mixed tasks
        mix = [{"text": ("批量任务-%03d \"quote\"\n换行" % i) if i % 3 == 0 else ("plain-%03d" % i),
                "done": i % 4 == 0} for i in range(200)]
        all_ok = True
        first_fail = ""
        for m in mix:
            code, body = http("POST", "http://127.0.0.1:%d/api/todos" % port, {"text": m["text"]})
            if not (isinstance(body, dict) and body.get("ok")):
                all_ok = False
                first_fail = "i=%d resp=%s" % (mix.index(m), json.dumps(body, ensure_ascii=False)[:160])
                break
            if m["done"]:
                http("PUT", "http://127.0.0.1:%d/api/todos/%d" % (port, body["todo"]["id"]),
                     {"text": m["text"], "done": True})
        record("v01-200-creates", all_ok, first_fail)

        code, before = http("GET", "http://127.0.0.1:%d/api/todos" % port)
        want = sorted([(t["id"], t["text"], t["done"]) for t in before["todos"]])
        record("v01-200-listed", len(want) >= 200, "count=%d" % len(want))

        # V-01d: hard-kill backend, restart, exact recovery
        stop_service(proc, log, port)
        proc, log = start_verified(cli, port, data, log_path=logp)
        ok = pid_on_port(port) is not None
        record("v02-restart-ready", ok, "")
        code, after = http("GET", "http://127.0.0.1:%d/api/todos" % port)
        got = sorted([(t["id"], t["text"], t["done"]) for t in after["todos"]]) if after.get("ok") else []
        record("v02-restart-exact", got == want, "matched %d/%d" % (len(got), len(want)))

        # V-02: commit_fail → explicit failure, no partial state
        stop_service(proc, log, port)
        stop_service(proc, log, port)
        proc, log = start_verified(cli, port, data, fault="commit_fail", log_path=logp)
        code, body = http("POST", "http://127.0.0.1:%d/api/todos" % port, {"text": "commit-fail-never"})
        record("v02-commit-fail-reported",
               body.get("ok") is False and body.get("err_code") == "fault_injected",
               json.dumps(body, ensure_ascii=False)[:140])
        code, lst = http("GET", "http://127.0.0.1:%d/api/todos" % port)
        got_ids = [t["id"] for t in lst.get("todos", [])]
        record("v02-commit-fail-no-state", "commit-fail-never" not in json.dumps(lst, ensure_ascii=False)
               and got == want, "")
        code, st = http("GET", "http://127.0.0.1:%d/api/storage-status" % port)
        if isinstance(st, str):
            st = json.loads(st)
        record("v02-allocator-unchanged", st.get("next_id") == max(got_ids) + 1,
               "next_id=%s" % st.get("next_id"))

        # V-02b: after_commit_fail → failure reported, commit actually durable;
        # recovery choice documented in Spec (no fake success receipt).
        stop_service(proc, log, port)
        stop_service(proc, log, port)
        proc, log = start_verified(cli, port, data, fault="after_commit_fail", log_path=logp)
        code, body = http("POST", "http://127.0.0.1:%d/api/todos" % port, {"text": "crash-after-commit"})
        record("v02-after-commit-reported", body.get("ok") is False and body.get("err_code") == "fault_injected", "")
        stop_service(proc, log, port)
        proc, log = start_verified(cli, port, data, log_path=logp)
        code, lst = http("GET", "http://127.0.0.1:%d/api/todos" % port)
        texts_now = [t["text"] for t in lst.get("todos", [])]
        record("v02-after-commit-recoverable", "crash-after-commit" in texts_now,
               "committed-before-report item survives restart (documented recovery)")

        # V-04b: second writer holding the file lock → create reports second_writer
        #（在损坏阶段之前执行：需要健康库文件）
        import sqlite3
        dbp = os.path.join(data, "todos.db")
        lock = sqlite3.connect(dbp, timeout=1)
        lock.execute("BEGIN IMMEDIATE")
        try:
            code, body = http("POST", "http://127.0.0.1:%d/api/todos" % port,
                              {"text": "blocked-by-second-writer"}, timeout=15)
            record("v04-second-writer", body.get("ok") is False and body.get("err_code") == "second_writer",
                   json.dumps(body, ensure_ascii=False)[:140])
        finally:
            lock.rollback()
            lock.close()

        # V-03a: truncate main db with valid backup → auto-recover
        code, lst = http("GET", "http://127.0.0.1:%d/api/todos" % port)
        expected_after_recovery = sorted([(t["id"], t["text"], t["done"]) for t in lst["todos"]])
        stop_service(proc, log, port)
        if pid_on_port(port) is not None:
            record("v03-port-free-before-corrupt", False, "port still bound; refusing to corrupt")
            return
        raw = open(dbp, "rb").read()
        open(dbp, "wb").write(raw[:200])
        proc, log = start_verified(cli, port, data, log_path=logp)
        code, lst = http("GET", "http://127.0.0.1:%d/api/todos" % port)
        got = sorted([(t["id"], t["text"], t["done"]) for t in lst["todos"]]) if lst.get("ok") else None
        if got == expected_after_recovery:
            record("v03-recover-from-backup", True, "truncated main restored from VACUUM INTO backup")
        else:
            gs = len(got) if got is not None else "not-ok"
            es = len(expected_after_recovery)
            diff = ""
            if isinstance(got, list):
                gset = set(got)
                eset = set(expected_after_recovery)
                only_g = [x for x in got if x not in eset][:3]
                only_e = [x for x in expected_after_recovery if x not in gset][:3]
                diff = " only_in_got=%s only_in_expected=%s" % (only_g, only_e)
            record("v03-recover-from-backup", False,
                   "got=%s expected=%s err=%s%s" % (gs, es, lst.get("err_code"), diff))

        # V-03b: both main and backup corrupt → explicit error, original bytes intact
        stop_service(proc, log, port)
        if pid_on_port(port) is not None:
            record("v03-port-free-before-corrupt", False, "port still bound; refusing to corrupt")
            return
        open(dbp, "wb").write(b"DESCORRUPTED" * 32)
        bakp = dbp + ".bak"
        open(bakp, "wb").write(b"BOTHCORRUPT" * 32)
        h_before = hashlib.sha256(open(dbp, "rb").read()).hexdigest()
        proc, log = start_verified(cli, port, data, log_path=logp)
        code, lst = http("GET", "http://127.0.0.1:%d/api/todos" % port)
        record("v03-both-corrupt-read", lst.get("ok") is False and lst.get("err_code") == "corrupt", "")
        code, body = http("POST", "http://127.0.0.1:%d/api/todos" % port, {"text": "no-fake-write"})
        record("v03-both-corrupt-write", body.get("ok") is False and body.get("err_code") == "corrupt", "")
        h_after = hashlib.sha256(open(dbp, "rb").read()).hexdigest()
        record("v03-original-bytes-intact", h_before == h_after, "sha256 unchanged")
        record("v03-no-reseed", not os.path.exists(os.path.join(data, "todos.db.recovering")),
               "no recovering marker, no silent rebuild")
    finally:
        stop_service(proc, log, port)


def ui_battery(cli, workdir, profile):
    back = free_port()
    front = free_port()
    mcp_port = None
    data = os.path.join(workdir, "ui-data")
    os.makedirs(data)
    logp = os.path.join(workdir, "ui-run.log")
    env = dict(os.environ)
    env["AUTO_TODO_DATA"] = data
    if profile == "vm":
        mcp_port = free_port()
        env["AUTOUI_MCP_PORT"] = str(mcp_port)
    log = open(logp, "w", encoding="utf-8")
    def spawn_run():
        return subprocess.Popen(
            [cli, "run", "-r", profile, "-B", str(back), "-F", str(front)],
            cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT)
    proc = spawn_run()
    ok = wait_ready(back, timeout_s=600)
    if not ok:
        # `auto run` 偶发在 CLI 初始化处停滞（证据见日志）——清场重试一次
        print("WARN: ui run not ready; log tail: " + open(logp, encoding='utf-8', errors='replace').read()[-300:], flush=True)
        try:
            proc.terminate()
        except Exception:
            pass
        kill_port(back)
        kill_port(front)
        time.sleep(3)
        log = open(logp, "w", encoding="utf-8")
        proc = spawn_run()
        ok = wait_ready(back, timeout_s=600)
    try:
        if not record("ui-backend-ready", ok, "port %d" % back):
            return

        if profile == "vue":
            # front reachability (vite binds localhost)
            front_up = False
            for host in ("http://localhost:%d/" % front, "http://127.0.0.1:%d/" % front):
                try:
                    with urllib.request.urlopen(host, timeout=5) as r:
                        front_up = r.status == 200
                    if front_up:
                        break
                except Exception:
                    continue
            record("ui-front-ready", front_up, "port %d" % front)
            if not front_up:
                return

            pw = find_playwright_module()
            if not pw:
                record("ui-playwright-found", False, "set PLAYWRIGHT_MODULE")
                return
            record("ui-playwright-found", True, pw)
            env["PLAYWRIGHT_MODULE"] = pw
            drive = os.path.join(REPO, "tests", "basic", "ui_drive.mjs")
            cmd = ["node", drive, "http://localhost:%d/" % front, "full"]
            run = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True, timeout=300)
            print(run.stdout, flush=True)
            if run.returncode != 0:
                print(run.stderr[-2000:], flush=True)
            steps = []
            for line in run.stdout.splitlines():
                if line.startswith("SUMMARY "):
                    steps = json.loads(line[len("SUMMARY "):])["results"]
            for s in steps:
                record("ui-" + s["step"], s["ok"], s.get("detail", ""))
        else:
            # VM 端：原生 AutoUI 界面经 MCP 驱动
            mcp_url = "http://127.0.0.1:%d/mcp" % mcp_port
            drive = os.path.join(REPO, "tests", "basic", "vm_drive.py")
            run = subprocess.run([sys.executable, drive, mcp_url, "full"],
                                 cwd=REPO, env=env, capture_output=True, text=True, timeout=300)
            print(run.stdout, flush=True)
            if run.returncode != 0:
                print(run.stderr[-2000:], flush=True)
            steps = []
            for line in run.stdout.splitlines():
                if line.startswith("SUMMARY "):
                    steps = json.loads(line[len("SUMMARY "):])["results"]
            for s in steps:
                record("ui-" + s["step"], s["ok"], s.get("detail", ""))

        # 后端重启后：真实存储内容仍在（vue 经页面 readonly 复核 + API 复核；
        # vm 经 MCP readonly 复核 + API 复核）。UI 全流程结束时列表可能为空
        # （清已完成），故经 API 写入持久锚点再验证。
        code, anchor = http("POST", "http://127.0.0.1:%d/api/todos" % back,
                            {"text": "重启持久锚点-anchor"})
        if not (isinstance(anchor, dict) and anchor.get("ok")):
            record("ui-restart-persist", False, "anchor create failed: " + json.dumps(anchor, ensure_ascii=False)[:120])
            return
        stop_ui_backend = pid_on_port(back)
        if stop_ui_backend:
            subprocess.run(["taskkill", "/F", "/PID", str(stop_ui_backend)], capture_output=True)
            time.sleep(2)
        proc2, log2 = start_verified(cli, back, data, log_path=logp + ".2")
        try:
            ok = pid_on_port(back) is not None
            record("ui-restart-backend", ok, "")
            code, lst = http("GET", "http://127.0.0.1:%d/api/todos" % back)
            texts = [x["text"] for x in lst.get("todos", [])] if lst.get("ok") else []
            record("ui-restart-persist", ok and "重启持久锚点-anchor" in texts,
                   "anchor survives backend restart (%d tasks)" % len(texts))
        finally:
            stop_service(proc2, log2, back)
    finally:
        kill_port(front)
        kill_port(back)
        if profile == "vm":
            kill_port(mcp_port)
        try:
            proc.terminate()
        except Exception:
            pass
        log.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", choices=["vue", "vm"], default=None)
    ap.add_argument("--api-only", action="store_true")
    args = ap.parse_args()

    cli = resolve_cli()
    kill_stale_backends()
    workdir = tempfile.mkdtemp(prefix="todo-verify-")
    print("workdir: " + workdir, flush=True)

    api_battery(cli, workdir)
    if not args.api_only and args.profile:
        ui_battery(cli, workdir, args.profile)

    failed = [r for r in results if not r["ok"]]
    print("\n==== verify_basic summary: %d passed, %d failed ====" % (len(results) - len(failed), len(failed)))
    for r in failed:
        print("  FAILED: " + r["step"] + (" — " + r["detail"] if r["detail"] else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
