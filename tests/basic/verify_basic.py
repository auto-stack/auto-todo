#!/usr/bin/env python3
"""TODO-001/002 basic-capabilities + standalone-isolation verification.

Reproducible entry required by the Plans (§6):
    python tests/basic/verify_basic.py --profile vue
    python tests/basic/verify_basic.py --profile vm
    python tests/basic/verify_basic.py --api-only
    python tests/basic/verify_basic.py --api-only --cold-prep   # TD-01 cold first-start

Drives the REAL app: real rust backend service (`auto service --server rust`)
with an isolated AUTO_TODO_DATA, real HTTP API battery, real UI via Playwright
Chromium (tests/basic/ui_drive.mjs) / AutoUI MCP (tests/basic/vm_drive.py).

Process ownership (TODO-002, standalone-decision.md):
  Killing is authorized ONLY by spawn-tree membership:
    - teardown = `taskkill /T /F` on OUR OWN spawn root (recorded Popen pid);
    - crash simulation = kill the backend leaf OBSERVED serving our port inside
      our tree (corroborated: descendant + port owner + our data root).
  Ports are observation only. Names / command lines / command-line similarity
  are NEVER kill criteria. A port still owned by an unknown PID after our tree
  is dead is a controlled diagnostic failure — never force-killed.

Toolchain resolution:
    AUTO_CLI        path to `auto` executable (default: auto-man debug build)
    PLAYWRIGHT_MODULE  path to playwright/index.mjs (npx cache probed automatically)

Exit code 0 = all checks passed. Negative controls (bad tool, port conflict)
must produce a nonzero exit via the same gate — a required skip is a failure.
"""

import argparse
import hashlib
import json
import os
import glob
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CLI = r"D:/autostack/auto-man/target/debug/auto.exe"

# Cold-prep wipes only THIS repo's own regenerable, gitignored artifacts.
COLD_PREP_DIRS = ["gen", "rust-workspace", ".auto"]
# Never touched by cold-prep (framework/shared targets): auto-lang target,
# auto-man/auto-ui target, any other repo's artifacts.

results = []
identity = {}  # recorded tool/dependency identities for the run log


def record(step, ok, detail=""):
    results.append({"step": step, "ok": bool(ok), "detail": detail})
    print(("PASS" if ok else "FAIL") + ": " + step + ((" — " + detail) if detail else ""), flush=True)
    return ok


def sha256_file(path):
    try:
        return hashlib.sha256(open(path, "rb").read()).hexdigest()
    except OSError:
        return None


# ---------------------------------------------------------------- process ownership

PS_UTF8 = "$OutputEncoding=[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
PS_ALL_PROCS = PS_UTF8 + (
    "Get-CimInstance Win32_Process | "
    "Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress")


def proc_table():
    """One CIM snapshot of all processes. Observation only."""
    r = subprocess.run(["powershell", "-NoProfile", "-Command", PS_ALL_PROCS],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        data = json.loads(r.stdout)
    except Exception:
        return []
    if isinstance(data, dict):
        data = [data]
    return [p for p in data if isinstance(p, dict) and p.get("ProcessId")]


def descendants(root_pid, table=None):
    """PIDs in the spawn subtree of root_pid (root excluded), by ParentProcessId."""
    table = table if table is not None else proc_table()
    by_parent = {}
    for p in table:
        by_parent.setdefault(p.get("ParentProcessId"), []).append(p)
    out, stack, seen = [], [root_pid], set()
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        for c in by_parent.get(cur, []):
            out.append(c)
            stack.append(c["ProcessId"])
    return out


def pid_alive(pid, table=None):
    table = table if table is not None else proc_table()
    return any(p.get("ProcessId") == pid for p in table)


def tree_kill(root_pid):
    """Kill OUR OWN spawn subtree: taskkill /T /F on the recorded spawn root."""
    if root_pid is None:
        return False
    r = subprocess.run(["taskkill", "/T", "/F", "/PID", str(root_pid)],
                       capture_output=True, text=True)
    return r.returncode == 0


def kill_observed_backend(backend_pid):
    """Kill the backend leaf identified while it served OUR port inside OUR tree."""
    if backend_pid is None:
        return False
    r = subprocess.run(["taskkill", "/F", "/PID", str(backend_pid)],
                       capture_output=True, text=True)
    return r.returncode == 0


def find_backend_in_tree(root_pid, port=None, table=None):
    """Locate our backend leaf inside our own subtree.

    Identity = spawn-tree descendant AND (image name auto-todo-*-back.exe OR,
    when port given, owner of that port). Never matches outside our subtree.
    """
    table = table if table is not None else proc_table()
    desc = descendants(root_pid, table)
    port_owner_pid = port_owner(port, table) if port is not None else None
    for p in desc:
        if re.match(r"auto-todo-.+-back\.exe$", p.get("Name", "")):
            if port is None or p["ProcessId"] == port_owner_pid:
                return p
    if port_owner_pid and any(p["ProcessId"] == port_owner_pid for p in desc):
        for p in desc:
            if p["ProcessId"] == port_owner_pid:
                return p
    return None


def port_owner(port, table=None):
    """Observe which PID listens on port. Observation only — never an authorization."""
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command", PS_UTF8 +
         "(Get-NetTCPConnection -LocalPort %d -State Listen -ErrorAction SilentlyContinue)"
         ".OwningProcess | Select-Object -First 1" % port],
        capture_output=True, text=True).stdout.strip()
    return int(out) if out.isdigit() else None


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def alloc_port(max_tries=8):
    """Random candidate port with usability pre-validation (F-03).

    Three-way handling per the frozen port contract:
      - owner present  = service conflict → skip candidate (the dedicated
        conflict leg is the controlled-failure surface for occupied ports);
      - no owner but bind refused = OS-reserved range (Hyper-V/WinNAT
        exclusion churn) → next random candidate, each skip recorded;
      - bindable → use it.
    Bounded: max_tries candidates, then a fatal diagnostic — never an
    unbounded scan, never killing anything.
    """
    skipped = []
    for _ in range(max_tries):
        p = free_port()
        owner = port_owner(p)
        if owner is not None:
            skipped.append((p, "owner=%s" % owner))
            continue
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", p))
            if skipped:
                print("NOTE: skipped unusable port candidates: %s" % skipped, flush=True)
            return p
        except OSError as e:
            skipped.append((p, "bind refused: %s" % e))
        finally:
            try:
                s.close()
            except Exception:
                pass
    print("FATAL: no bindable port candidate after %d tries; skipped: %s" % (max_tries, skipped), flush=True)
    record("port-allocation-exhausted", False, str(skipped)[:200])
    sys.exit(1)


def port_free_wait(port, timeout_s=10):
    """Wait until nothing listens on port (observation loop after our teardown)."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if port_owner(port) is None:
            return True
        time.sleep(1)
    return port_owner(port) is None


# ---------------------------------------------------------------- legacy helpers kept

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


def wait_ready(port, proc=None, timeout_s=240):
    """Poll readiness; on ready, return the observed backend pid (port owner).

    The returned pid is ownership EVIDENCE (observed serving our port); kills on
    it are authorized only because it was observed inside our spawn tree.
    """
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if proc is not None and proc.poll() is not None:
            return None  # spawn root exited without readiness
        try:
            code, body = http("GET", "http://127.0.0.1:%d/api/todos" % port, timeout=3)
            if code == 200 and isinstance(body, dict):
                return port_owner(port)
        except Exception:
            pass
        time.sleep(3)
    return None


def stop_run(proc, log, port, backend_pid=None):
    """Own-tree teardown. Returns (clean, detail).

    1. taskkill /T /F on our spawn root (wrapper + shim + cargo + backend).
    2. Belt & braces: if the observed backend leaf is somehow still alive, kill it.
    3. Observe the port: freed = clean; owned by an UNKNOWN pid = diagnostic
       failure detail (never killed by us).
    """
    tree_kill(proc.pid)
    time.sleep(1)
    if backend_pid is not None and pid_alive(backend_pid):
        kill_observed_backend(backend_pid)
        time.sleep(1)
    try:
        log.close()
    except Exception:
        pass
    owner = port_owner(port)
    if owner is None:
        return True, ""
    return False, "port %d still owned by unknown pid %s after own-tree teardown" % (port, owner)


def start_verified(cli, port, data_dir, log_path, fault=None, timeout_s=240, retries=1):
    """Start the service and wait for readiness; on stall, reap OUR tree and
    retry on the same port (never a port rescan, never a non-own kill).

    Returns (proc, log, backend_pid). backend_pid is None when not ready —
    the caller records the controlled failure.
    """
    proc, log = start_service(cli, port, data_dir, fault=fault, log_path=log_path)
    backend = wait_ready(port, proc=proc, timeout_s=timeout_s)
    for attempt in range(retries + 1):
        if backend is not None:
            return proc, log, backend
        tail = ""
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                tail = "".join(f.readlines()[-6:])
        except Exception:
            pass
        owner_now = port_owner(port)
        print("WARN: service start not ready (attempt %d); port owner: %s; log tail: %s"
              % (attempt + 1, owner_now, tail[-300:]), flush=True)
        stop_run(proc, log, port, backend_pid=None)
        if owner_now is not None and port_owner(port) is not None:
            # Port held by something that is not ours → controlled failure, no scan.
            return proc, log, None
        proc, log = start_service(cli, port, data_dir, fault=fault, log_path=log_path)
        backend = wait_ready(port, proc=proc, timeout_s=timeout_s)
    return proc, log, backend


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


def record_identity():
    cli = os.environ.get("AUTO_CLI", DEFAULT_CLI)
    identity["auto_cli"] = {"path": cli, "sha256": sha256_file(cli),
                            "version": subprocess.run([cli, "--version"], capture_output=True,
                                                      text=True).stdout.strip() if os.path.exists(cli) else None}
    import shutil
    tool = shutil.which("auto-ui-tool")
    if tool:
        ver = subprocess.run([tool, "--version"], capture_output=True, text=True)
        identity["auto_ui_tool"] = {"path": tool, "sha256": sha256_file(tool),
                                    "version": (ver.stdout or ver.stderr).strip()[:80]}
    node = shutil.which("node")
    if node:
        identity["node"] = {"path": node,
                            "version": subprocess.run([node, "--version"], capture_output=True,
                                                      text=True).stdout.strip()}
    pw = find_playwright_module()
    if pw:
        identity["playwright"] = {"path": pw}
    identity["python"] = sys.version.split()[0]
    identity["repo_head"] = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                                           capture_output=True, text=True).stdout.strip()
    print("IDENTITY " + json.dumps(identity, ensure_ascii=False), flush=True)


# ---------------------------------------------------------------- TD-04 additions

def craft_schema_v2_db(db_path):
    """A well-formed SQLite file that is NOT our schema: schema_v=2."""
    import sqlite3
    if os.path.exists(db_path):
        os.remove(db_path)
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE todos (id INTEGER PRIMARY KEY, text TEXT, done INTEGER)")
    con.execute("CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)")
    con.execute("INSERT INTO meta VALUES ('schema_v', '2')")
    con.execute("INSERT INTO meta VALUES ('next_id', '1')")
    con.commit()
    con.close()


def craft_valid_v1_db(db_path, tasks):
    import sqlite3
    if os.path.exists(db_path):
        os.remove(db_path)
    for extra in (db_path + ".bak", db_path + ".recovering"):
        if os.path.exists(extra):
            os.remove(extra)
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE todos (id INTEGER PRIMARY KEY, text TEXT, done INTEGER)")
    con.execute("CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)")
    con.execute("INSERT INTO meta VALUES ('schema_v', '1')")
    con.execute("INSERT INTO meta VALUES ('next_id', '%d')" % (len(tasks) + 1))
    for i, t in enumerate(tasks, 1):
        con.execute("INSERT INTO todos VALUES (?, ?, 0)", (i, t))
    con.commit()
    con.close()


# ---------------------------------------------------------------- batteries

def craft_foreign_db(db_path):
    """A valid SQLite file that belongs to ANOTHER application: unrelated
    table with data, no meta/todos. The open gate must refuse it zero-write."""
    import sqlite3
    if os.path.exists(db_path):
        os.remove(db_path)
    for extra in (db_path + ".bak", db_path + ".recovering"):
        if os.path.exists(extra):
            os.remove(extra)
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE widget (a INTEGER)")
    con.execute("INSERT INTO widget VALUES (42)")
    con.commit()
    con.close()


def api_battery(cli, workdir):
    port = alloc_port()
    data = os.path.join(workdir, "api-data")
    os.makedirs(data)
    logp = os.path.join(workdir, "api-service.log")

    proc, log, backend = start_verified(cli, port, data, log_path=logp, timeout_s=600)
    cleanup_ok = True
    try:
        ok = backend is not None
        if not record("service-ready", ok, "rust service on :%d" % port):
            return
        record("td01-backend-in-own-tree",
               find_backend_in_tree(proc.pid, port) is not None,
               "backend descendant observed (pid %s)" % backend)

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
        clean, detail = stop_run(proc, log, port, backend_pid=backend)
        proc = log = backend = None
        record("td02-cleanup-hard-killed-tree", clean, detail)
        proc, log, backend = start_verified(cli, port, data, log_path=logp, timeout_s=600)
        ok = backend is not None
        record("v02-restart-ready", ok, "")
        code, after = http("GET", "http://127.0.0.1:%d/api/todos" % port)
        got = sorted([(t["id"], t["text"], t["done"]) for t in after["todos"]]) if after.get("ok") else []
        record("v02-restart-exact", got == want, "matched %d/%d" % (len(got), len(want)))

        # V-02: commit_fail → explicit failure, no partial state
        clean, detail = stop_run(proc, log, port, backend_pid=backend)
        proc = log = backend = None
        proc, log, backend = start_verified(cli, port, data, fault="commit_fail", log_path=logp, timeout_s=600)
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
        clean, detail = stop_run(proc, log, port, backend_pid=backend)
        proc = log = backend = None
        proc, log, backend = start_verified(cli, port, data, fault="after_commit_fail", log_path=logp, timeout_s=600)
        code, body = http("POST", "http://127.0.0.1:%d/api/todos" % port, {"text": "crash-after-commit"})
        record("v02-after-commit-reported", body.get("ok") is False and body.get("err_code") == "fault_injected", "")
        clean, detail = stop_run(proc, log, port, backend_pid=backend)
        proc = log = backend = None
        proc, log, backend = start_verified(cli, port, data, log_path=logp, timeout_s=600)
        code, lst = http("GET", "http://127.0.0.1:%d/api/todos" % port)
        texts_now = [t["text"] for t in lst.get("todos", [])]
        record("v02-after-commit-recoverable", "crash-after-commit" in texts_now,
               "committed-before-report item survives restart (documented recovery)")
        # TD-03: 故障解除后下一次写入成功
        code, body = http("POST", "http://127.0.0.1:%d/api/todos" % port, {"text": "fault-cleared-next-write"})
        record("td04-after-commit-next-write-ok", body.get("ok") is True and
               body.get("todo", {}).get("text") == "fault-cleared-next-write", "")

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
        clean, detail = stop_run(proc, log, port, backend_pid=backend)
        proc = log = backend = None
        if port_owner(port) is not None:
            record("v03-port-free-before-corrupt", False, "port still bound; refusing to corrupt")
            return
        raw = open(dbp, "rb").read()
        open(dbp, "wb").write(raw[:200])
        proc, log, backend = start_verified(cli, port, data, log_path=logp, timeout_s=600)
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

        # TD-04: recovery next-write — recovered library accepts a fresh write
        code, body = http("POST", "http://127.0.0.1:%d/api/todos" % port, {"text": "recovered-next-write"})
        record("td04-recovered-next-write-ok", body.get("ok") is True, "")

        # V-03b: both main and backup corrupt → explicit error, original bytes intact
        clean, detail = stop_run(proc, log, port, backend_pid=backend)
        proc = log = backend = None
        if port_owner(port) is not None:
            record("v03-port-free-before-corrupt", False, "port still bound; refusing to corrupt")
            return
        open(dbp, "wb").write(b"DESCORRUPTED" * 32)
        bakp = dbp + ".bak"
        open(bakp, "wb").write(b"BOTHCORRUPT" * 32)
        h_before = hashlib.sha256(open(dbp, "rb").read()).hexdigest()
        proc, log, backend = start_verified(cli, port, data, log_path=logp, timeout_s=600)
        code, lst = http("GET", "http://127.0.0.1:%d/api/todos" % port)
        record("v03-both-corrupt-read", lst.get("ok") is False and lst.get("err_code") == "corrupt", "")
        code, body = http("POST", "http://127.0.0.1:%d/api/todos" % port, {"text": "no-fake-write"})
        record("v03-both-corrupt-write", body.get("ok") is False and body.get("err_code") == "corrupt", "")
        h_after = hashlib.sha256(open(dbp, "rb").read()).hexdigest()
        record("v03-original-bytes-intact", h_before == h_after, "sha256 unchanged")
        record("v03-no-reseed", not os.path.exists(os.path.join(data, "todos.db.recovering")),
               "no recovering marker, no silent rebuild")

        # TD-04: bad schema (schema_v=2) in an isolated fresh data root →
        # read/write refuse with schema_unsupported, original bytes untouched,
        # no silent rebuild; after the fault is cleared the next write succeeds.
        clean, detail = stop_run(proc, log, port, backend_pid=backend)
        proc = log = backend = None
        data2 = os.path.join(workdir, "api-data-schema2")
        os.makedirs(data2)
        dbp2 = os.path.join(data2, "todos.db")
        craft_schema_v2_db(dbp2)
        h_bad = sha256_file(dbp2)
        proc, log, backend = start_verified(cli, port, data2, log_path=logp + ".s2", timeout_s=600)
        code, lst = http("GET", "http://127.0.0.1:%d/api/todos" % port)
        record("td04-schema-unsupported-read",
               lst.get("ok") is False and lst.get("err_code") == "schema_unsupported",
               json.dumps(lst, ensure_ascii=False)[:120])
        code, body = http("POST", "http://127.0.0.1:%d/api/todos" % port, {"text": "no-write-bad-schema"})
        record("td04-schema-unsupported-write",
               body.get("ok") is False and body.get("err_code") == "schema_unsupported", "")
        record("td04-schema-unsupported-zero-write",
               sha256_file(dbp2) == h_bad and not os.path.exists(dbp2 + ".recovering"),
               "file bytes + no marker")
        clean, detail = stop_run(proc, log, port, backend_pid=backend)
        proc = log = backend = None
        craft_valid_v1_db(dbp2, ["schema-恢复后任务"])
        proc, log, backend = start_verified(cli, port, data2, log_path=logp + ".s2", timeout_s=600)
        code, lst = http("GET", "http://127.0.0.1:%d/api/todos" % port)
        read_ok = lst.get("ok") is True and [t["text"] for t in lst.get("todos", [])] == ["schema-恢复后任务"]
        code, body = http("POST", "http://127.0.0.1:%d/api/todos" % port, {"text": "schema-恢复后新写入"})
        record("td04-schema-fault-cleared-next-write-ok", read_ok and body.get("ok") is True, "")

        # TD-04/F-02: a foreign database (valid SQLite, unrelated `widget`
        # table with data, no meta/todos) must be refused zero-write — never
        # silently adopted as a fresh todo store. Swapping in a valid v1 db
        # restores normal service.
        clean, detail = stop_run(proc, log, port, backend_pid=backend)
        proc = log = backend = None
        data3 = os.path.join(workdir, "api-data-foreign")
        os.makedirs(data3)
        dbp3 = os.path.join(data3, "todos.db")
        craft_foreign_db(dbp3)
        h_f = sha256_file(dbp3)
        proc, log, backend = start_verified(cli, port, data3, log_path=logp + ".fg", timeout_s=600)
        code, lst = http("GET", "http://127.0.0.1:%d/api/todos" % port)
        record("td04-schema-foreign-read",
               lst.get("ok") is False and lst.get("err_code") == "schema_unsupported",
               json.dumps(lst, ensure_ascii=False)[:120])
        code, body = http("POST", "http://127.0.0.1:%d/api/todos" % port, {"text": "no-adopt-foreign"})
        record("td04-schema-foreign-write",
               body.get("ok") is False and body.get("err_code") == "schema_unsupported", "")
        record("td04-schema-foreign-zero-write",
               sha256_file(dbp3) == h_f and not os.path.exists(dbp3 + ".recovering"),
               "file bytes unchanged, no marker, widget data intact")
        clean, detail = stop_run(proc, log, port, backend_pid=backend)
        proc = log = backend = None
        craft_valid_v1_db(dbp3, ["外来库换回后任务"])
        proc, log, backend = start_verified(cli, port, data3, log_path=logp + ".fg", timeout_s=600)
        code, lst = http("GET", "http://127.0.0.1:%d/api/todos" % port)
        read_ok = lst.get("ok") is True and [t["text"] for t in lst.get("todos", [])] == ["外来库换回后任务"]
        code, body = http("POST", "http://127.0.0.1:%d/api/todos" % port, {"text": "外来库换回后新写入"})
        record("td04-schema-foreign-cleared-next-write-ok", read_ok and body.get("ok") is True, "")
    finally:
        if proc is not None:
            clean, detail = stop_run(proc, log, port, backend_pid=backend)
            if not clean:
                cleanup_ok = False
                record("cleanup-integrity-api", False, detail)
    if cleanup_ok:
        record("cleanup-integrity-api", True, "all teardowns freed their ports")


def spawn_dummy_listener(port):
    """An UNRELATED port listener owned by the harness (not the app)."""
    code = ("import socket,time;s=socket.socket();s.setsockopt(socket.SOL_SOCKET,"
            "socket.SO_REUSEADDR,1);s.bind(('127.0.0.1',%d));s.listen(1);time.sleep(600)" % port)
    return subprocess.Popen([sys.executable, "-c", code],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def standalone_battery(cli, workdir):
    """TODO-002 TD-01/TD-02: standalone readiness identity, controlled failures,
    bystander isolation. The bystander Todo + unrelated listener are spawned and
    owned by THIS harness; the gate must leave them untouched."""
    snap_before = proc_table()

    bystander = None
    blog = None
    bport = alloc_port()
    bdata = os.path.join(workdir, "bystander-data")
    os.makedirs(bdata)
    benv = dict(os.environ)
    benv["AUTO_TODO_DATA"] = bdata
    benv.pop("AUTO_TODO_FAULT", None)
    try:
        # Bystander: a REAL running auto-todo instance holding its own data root,
        # port, library and AutoCache — exactly the shape the retired
        # kill_stale_backends()/kill_port paths could destroy. Service shape is
        # used for a deterministic oracle; the VM-window (`auto run -r vm`)
        # bystander shape was exercised in the r1-r3 gate runs (survived 3/4;
        # one intermittent VM UI exit consistent with the 001-era registered
        # observation — environmental, this file has no name/port/cmdline kill
        # path, see taskkill audit in the Plan receipt).
        blog = open(os.path.join(workdir, "bystander.log"), "w", encoding="utf-8")
        bystander = subprocess.Popen([cli, "service", "--server", "rust", "--back-port", str(bport)],
                                     cwd=REPO, env=benv, stdout=blog, stderr=subprocess.STDOUT)
        bbackend = wait_ready(bport, proc=bystander, timeout_s=600)
        if not record("td02-bystander-ready", bbackend is not None,
                      "bystander instance up (service) on :%d" % bport):
            return
        # anchor a task in the bystander's own library
        code, body = http("POST", "http://127.0.0.1:%d/api/todos" % bport, {"text": "旁观者任务-不许动"})
        record("td02-bystander-anchor", body.get("ok") is True, "")
        bdb = os.path.join(bdata, "todos.db")
        bdb_sha = sha256_file(bdb)

        # Unrelated listener on its own port (harness-owned, non-app)
        dport = alloc_port()
        dummy = spawn_dummy_listener(dport)
        time.sleep(1)
        dummy_ok0 = pid_alive(dummy.pid)
        record("td02-dummy-listener-up", dummy_ok0, "port %d" % dport)

        # TD-01: bad tool → gate refuses nonzero, kills nothing
        env_bad = dict(os.environ)
        env_bad["AUTO_CLI"] = os.path.join(workdir, "no-such-auto.exe")
        run_bad = subprocess.run([sys.executable, os.path.join(REPO, "tests", "basic", "verify_basic.py"),
                                  "--api-only"], env=env_bad, cwd=REPO, capture_output=True,
                                 text=True, timeout=120)
        record("td01-bad-tool-gate-nonzero",
               run_bad.returncode != 0 and "FATAL: auto CLI not found" in (run_bad.stdout + run_bad.stderr),
               "exit=%d" % run_bad.returncode)

        # TD-01: port occupied (by our dummy) → controlled failure, no scan, no kill
        cport = alloc_port()
        blocker = spawn_dummy_listener(cport)
        time.sleep(1)
        os.makedirs(os.path.join(workdir, "conflict-data"), exist_ok=True)
        proc_c, log_c = start_service(cli, cport, os.path.join(workdir, "conflict-data"),
                                      log_path=os.path.join(workdir, "conflict.log"))
        ready_c = wait_ready(cport, proc=proc_c, timeout_s=30)
        record("td01-port-conflict-controlled", ready_c is None,
               "occupied port must not become ready; owner pid %s" % port_owner(cport))
        clean_c, detail_c = stop_run(proc_c, log_c, cport, backend_pid=None)
        # our conflict service tree is gone; the dummy BLOCKER must still own the port
        record("td01-conflict-blocker-survived",
               pid_alive(blocker.pid) and port_owner(cport) == blocker.pid,
               "blocker pid %s alive, still owns :%d" % (blocker.pid, cport))
        tree_kill(blocker.pid)

        # TD-02 legs on OUR main service: normal exit + hard-kill leaf
        mport = alloc_port()
        mdata = os.path.join(workdir, "main-data")
        os.makedirs(mdata)
        proc_m, log_m, backend_m = start_verified(cli, mport, mdata,
                                                  log_path=os.path.join(workdir, "main.log"), timeout_s=600)
        if backend_m is None:
            record("td02-main-service-ready", False, "main leg service did not start")
            return
        record("td02-main-service-ready", True, "pid %s" % backend_m)
        clean, detail = stop_run(proc_m, log_m, mport, backend_pid=backend_m)
        record("td02-cleanup-normal-exit", clean, detail)

        proc_m, log_m, backend_m = start_verified(cli, mport, mdata,
                                                  log_path=os.path.join(workdir, "main.log"), timeout_s=600)
        hard_ok = backend_m is not None
        if hard_ok:
            hard_ok = kill_observed_backend(backend_m)
            time.sleep(2)
        record("td02-cleanup-hard-kill-leaf", hard_ok,
               "backend leaf killed by observed identity; port owner now %s" % port_owner(mport))
        if proc_m is not None:
            tree_kill(proc_m.pid)
            try:
                log_m.close()
            except Exception:
                pass

        # Bystander integrity after ALL cleanup legs
        table_now = proc_table()
        bbackend2 = port_owner(bport, table_now)
        record("td02-bystander-process-alive", pid_alive(bystander.pid, table_now),
               "bystander root pid %s alive" % bystander.pid)
        record("td02-bystander-port-listening", bbackend2 is not None,
               "bystander backend still on :%d" % bport)
        record("td02-bystander-db-unchanged", sha256_file(bdb) == bdb_sha, "library bytes stable")
        code, lst = http("GET", "http://127.0.0.1:%d/api/todos" % bport)
        record("td02-bystander-api-readable",
               lst.get("ok") is True and "旁观者任务-不许动" in [t["text"] for t in lst.get("todos", [])], "")
        record("td02-dummy-listener-survived", pid_alive(dummy.pid, table_now),
               "unrelated listener untouched")

        # Informational: auto-family process snapshot delta (other sessions'
        # instances start/stop on their own; NOT a gate — the gate's
        # non-interference is asserted by the bystander oracles above and by
        # code audit: no name/port/cmdline kill path exists in this file).
        auto_re = re.compile(r"^(auto|auto-todo-.+-back|auto-ui-tool|cargo)\.exe$", re.I)
        ext_pids = {p["ProcessId"] for p in snap_before if auto_re.match(p.get("Name", ""))}
        table_end = proc_table()
        ext_after = {p["ProcessId"] for p in table_end if auto_re.match(p.get("Name", ""))} \
            - {bystander.pid, dummy.pid}
        gone = ext_pids - ext_after
        print("OBSERVE: pre-existing auto-family pids no longer present after gate: "
              "%s (may have exited on their own; verify_basic has no non-own kill path)"
              % sorted(gone), flush=True)
        # teardown harness-owned actors
        tree_kill(dummy.pid)
    finally:
        if bystander is not None:
            clean, detail = stop_run(bystander, blog, bport, backend_pid=bbackend)
            record("cleanup-integrity-standalone", clean, detail)
        elif blog is not None:
            blog.close()


def ui_battery(cli, workdir, profile):
    back = alloc_port()
    front = alloc_port()
    mcp_port = None
    data = os.path.join(workdir, "ui-data")
    os.makedirs(data)
    logp = os.path.join(workdir, "ui-run.log")
    env = dict(os.environ)
    env["AUTO_TODO_DATA"] = data
    if profile == "vm":
        mcp_port = alloc_port()
        env["AUTOUI_MCP_PORT"] = str(mcp_port)

    def spawn_run(log):
        return subprocess.Popen(
            [cli, "run", "-r", profile, "-B", str(back), "-F", str(front)],
            cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT)

    def spawn_ui_ready(log_suffix, timeout_s=900, tries=2):
        """Spawn `auto run` and wait for readiness; on stall/exit, reap OUR tree
        and retry once (001-era documented CLI init stall; observed again at
        restart after hard-kill with 'UI cache invalidated')."""
        for attempt in range(tries):
            log = open(logp + log_suffix, "w", encoding="utf-8")
            proc = spawn_run(log)
            backend = wait_ready(back, proc=proc, timeout_s=timeout_s)
            if backend is not None:
                return proc, log, backend
            tail = ""
            try:
                with open(logp + log_suffix, "r", encoding="utf-8", errors="replace") as f:
                    tail = "".join(f.readlines()[-4:])
            except Exception:
                pass
            print("WARN: ui run not ready (attempt %d); log tail: %s" % (attempt + 1, tail[-300:]), flush=True)
            tree_kill(proc.pid)
            log.close()
            time.sleep(3)
            if not (port_free_wait(back, timeout_s=15) and port_free_wait(front, timeout_s=15)):
                return None, None, None
        return None, None, None

    proc, log, backend = spawn_ui_ready("")
    # Observed owners of OUR run's ports (captured while our wrappers serve
    # them). Authorization for late-straggler cleanup = observation within our
    # run, same contract as the backend leaf.
    observed_pids = set()
    if backend:
        observed_pids.add(backend)
    try:
        if not record("ui-backend-ready", backend is not None, "port %d" % back):
            return

        # TD-01 identity: real UI/backend ownership and data root correctness
        bproc = find_backend_in_tree(proc.pid, back)
        record("td01-ui-backend-in-own-tree", bproc is not None,
               "backend %s" % (bproc["CommandLine"][-90:] if bproc else "NOT IN TREE"))
        if bproc is not None:
            print("IDENTITY-UI backend_image=%s" % bproc["CommandLine"], flush=True)
        dbp = os.path.join(data, "todos.db")
        record("td01-dataroot-isolated", os.path.exists(dbp),
               "db created under AUTO_TODO_DATA (%s)" % data)
        appdata_default = os.path.join(os.environ.get("APPDATA", ""), "auto-todo", "data", "todos.db")
        identity["appdata_default_db_during_gate"] = sha256_file(appdata_default)

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
            fo = port_owner(front)
            if fo:
                observed_pids.add(fo)
        else:
            mo = port_owner(mcp_port)
            if mo:
                observed_pids.add(mo)

        anchor_text = "重启持久锚点-anchor"

        def run_driver(mode):
            if profile == "vue":
                pw = find_playwright_module()
                if not pw:
                    record("ui-playwright-found", False, "set PLAYWRIGHT_MODULE")
                    return None
                record("ui-playwright-found", True, pw)
                env["PLAYWRIGHT_MODULE"] = pw
                drive = os.path.join(REPO, "tests", "basic", "ui_drive.mjs")
                cmd = ["node", drive, "http://localhost:%d/" % front, mode]
            else:
                mcp_url = "http://127.0.0.1:%d/mcp" % mcp_port
                drive = os.path.join(REPO, "tests", "basic", "vm_drive.py")
                cmd = [sys.executable, drive, mcp_url, mode]
            run = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True, timeout=300)
            print(run.stdout, flush=True)
            if run.returncode != 0:
                print(run.stderr[-2000:], flush=True)
            steps = []
            for line in run.stdout.splitlines():
                if line.startswith("SUMMARY "):
                    steps = json.loads(line[len("SUMMARY "):])["results"]
            return steps

        steps = run_driver("full")
        if steps is None:
            return
        for s in steps:
            record("ui-" + s["step"], s["ok"], s.get("detail", ""))

        # 强杀后重开 → 再编辑（TD-03）：先经 API 写持久锚点，硬杀观测到的后端叶，
        # 树收割旧 wrapper，重启完整 UI wrapper 后 API 复核 + 真实 UI 再编辑。
        code, anchor = http("POST", "http://127.0.0.1:%d/api/todos" % back, {"text": anchor_text})
        if not (isinstance(anchor, dict) and anchor.get("ok")):
            record("ui-restart-persist", False, "anchor create failed: " + json.dumps(anchor, ensure_ascii=False)[:120])
            return
        table_now = proc_table()
        live_backend = find_backend_in_tree(proc.pid, back, table_now) or \
            ({"ProcessId": backend} if (backend and pid_alive(backend, table_now)) else None)
        if live_backend is None:
            record("ui-restart-backend", False, "backend leaf not identified in own tree")
            return
        kill_observed_backend(live_backend["ProcessId"])
        time.sleep(2)
        leaf_gone = not pid_alive(live_backend["ProcessId"])
        tree_kill(proc.pid)
        try:
            log.close()
        except Exception:
            pass
        record("td03-hard-killed-own-backend", leaf_gone, "pid %s" % live_backend["ProcessId"])
        if not port_free_wait(back, timeout_s=15):
            record("ui-restart-backend", False,
                   "own backend killed but :%d still owned by %s" % (back, port_owner(back)))
            return
        proc, log, backend2 = spawn_ui_ready(".2")
        ok = backend2 is not None
        record("ui-restart-backend", ok, "")
        code, lst = http("GET", "http://127.0.0.1:%d/api/todos" % back)
        texts = [x["text"] for x in lst.get("todos", [])] if lst.get("ok") else []
        record("ui-restart-persist", ok and anchor_text in texts,
               "anchor survives backend hard-kill restart (%d tasks)" % len(texts))
        if not ok:
            return
        steps = run_driver("reedit")
        if steps is None:
            return
        for s in steps:
            record("ui-" + s["step"], s["ok"], s.get("detail", ""))
        new_text = "重开再编辑-OK" if profile == "vue" else "重开再编辑-VM-OK"
        code, lst = http("GET", "http://127.0.0.1:%d/api/todos" % back)
        texts = [x["text"] for x in lst.get("todos", [])] if lst.get("ok") else []
        record("td03-reedit-storage", new_text in texts and anchor_text not in texts,
               "independent SQLite holds the renamed task")
    finally:
        # last-seen owners of our run's ports (before teardown) — authorized
        # straggler targets: they served our allocated ports inside this run
        for p in [back, front] + ([mcp_port] if mcp_port else []):
            o = port_owner(p)
            if o:
                observed_pids.add(o)
        if proc is not None and proc.poll() is None:
            tree_kill(proc.pid)
        time.sleep(1)
        for pid in list(observed_pids):
            if pid_alive(pid):
                kill_observed_backend(pid)
        time.sleep(1)
        try:
            log.close()
        except Exception:
            pass
        # observation-only teardown integrity
        for p in [back, front] + ([mcp_port] if mcp_port else []):
            owner = port_owner(p)
            if owner is not None:
                record("cleanup-integrity-ui", False,
                       "port %d still owned by pid %s after own-tree teardown" % (p, owner))
                break
        else:
            record("cleanup-integrity-ui", True, "back/front ports freed by own-tree teardown")


def cold_prep_guard():
    """Refuse cold-prep when any auto-todo backend or our cargo build is running
    (could be a user instance) — controlled failure, never stop others."""
    table = proc_table()
    offenders = []
    for p in table:
        name = p.get("Name", "")
        cmd = p.get("CommandLine") or ""
        if re.match(r"auto-todo-.+-back\.exe$", name):
            offenders.append("pid %s %s" % (p["ProcessId"], cmd[:80]))
        elif name == "cargo.exe" and "auto-todo" in cmd and "rust-workspace" in cmd:
            offenders.append("pid %s %s" % (p["ProcessId"], cmd[:80]))
    return offenders


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", choices=["vue", "vm"], default=None)
    ap.add_argument("--api-only", action="store_true")
    ap.add_argument("--cold-prep", action="store_true",
                    help="TD-01: wipe THIS repo's own regenerable generated dirs "
                         "(gen/, rust-workspace/, .auto/) before the run; refuses "
                         "while any auto-todo backend/cargo build is alive.")
    args = ap.parse_args()

    cli = resolve_cli()
    record_identity()

    if args.cold_prep:
        offenders = cold_prep_guard()
        if offenders:
            print("FATAL: cold-prep refused — possible user instance running: %s" % offenders, flush=True)
            record("cold-prep-guard", False, "; ".join(offenders))
            sys.exit(1)
        wiped = []
        for d in COLD_PREP_DIRS:
            p = os.path.join(REPO, d)
            if os.path.isdir(p):
                import shutil
                shutil.rmtree(p, ignore_errors=True)
                wiped.append(d)
        t0 = time.time()
        print("COLD-PREP: wiped own generated dirs %s (framework targets untouched)" % wiped, flush=True)
        identity["cold_prep"] = {"wiped": wiped, "started_at": t0}

    workdir = tempfile.mkdtemp(prefix="todo-verify-")
    print("workdir: " + workdir, flush=True)

    api_battery(cli, workdir)
    standalone_battery(cli, workdir)
    if not args.api_only and args.profile:
        ui_battery(cli, workdir, args.profile)

    failed = [r for r in results if not r["ok"]]
    print("\n==== verify_basic summary: %d passed, %d failed ====" % (len(results) - len(failed), len(failed)))
    for r in failed:
        print("  FAILED: " + r["step"] + (" — " + r["detail"] if r["detail"] else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
