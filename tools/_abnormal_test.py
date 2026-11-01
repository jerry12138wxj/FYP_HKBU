#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""级联 Web 应用异常/鲁棒性测试：模拟「不正常用户」的各种操作。

场景：
  1. 非音频文件上传 -> job error，服务存活
  2. 未知模型 key -> 400
  3. 空 body / 坏 base64 -> 400
  4. 路径穿越 -> 404
  5. 运行中重复 /api/run 同一 sid -> 409
  6. 运行中上传第二个音频并 run -> 排队串行，不崩
  7. 运行中反复 GET /api/job（模拟刷新）-> 状态持久
  8. GET 打在 POST 路由上 -> 405/404
  9. 对不存在的 sid 查 job -> 404
每个场景判定 PASS/FAIL，末尾汇总，并逐条写 JSONL 供 slides 读取。
"""
import argparse, base64, io, json, os, time, urllib.request, urllib.error
import numpy as np
import soundfile as sf


def req(base, method, path, obj=None, raw=None, timeout=30):
    data = None
    hdr = {}
    if raw is not None:
        data = raw
        hdr["Content-Type"] = "application/octet-stream"
    elif obj is not None:
        data = json.dumps(obj).encode("utf-8")
        hdr["Content-Type"] = "application/json"
    r = urllib.request.Request(base + path, data=data, headers=hdr, method=method)
    try:
        resp = urllib.request.urlopen(r, timeout=timeout)
        body = resp.read()
        try:
            return resp.status, json.loads(body)
        except Exception:
            return resp.status, body[:200]
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, body[:200]
    except Exception as e:
        return -1, "%s: %s" % (type(e).__name__, e)


def tone_b64(sr=16000, sec=3):
    t = np.arange(sr * sec) / sr
    x = (0.3 * np.sin(2 * np.pi * 440 * t)).astype("float32")[:, None]
    buf = io.BytesIO()
    sf.write(buf, x, sr, format="WAV", subtype="PCM_16")
    return base64.b64encode(buf.getvalue()).decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8123")
    ap.add_argument("--out", default="tools/_logs/abnormal_test.jsonl")
    args = ap.parse_args()
    B = args.base

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    out = open(args.out, "a", encoding="utf-8")
    results = []

    def check(name, cond, detail=""):
        results.append((name, bool(cond), detail))
        out.write(json.dumps({"name": name, "ok": bool(cond), "detail": str(detail)}, ensure_ascii=False) + "\n")
        out.flush()
        print("[%s] %s  %s" % ("PASS" if cond else "FAIL", name, detail))

    # 0. health
    code, h = req(B, "GET", "/api/health")
    check("health", code == 200 and "device" in h, "code=%s" % code)

    # 1. 非音频文件
    code, up = req(B, "POST", "/api/upload",
                   {"name": "evil.txt", "b64": base64.b64encode(b"not audio").decode()})
    sid1 = up.get("sid") if isinstance(up, dict) else None
    req(B, "POST", "/api/run", {"sid": sid1, "sep": "demucs", "den": "denoiser_master64"})
    st = None
    for _ in range(40):
        _, j = req(B, "GET", "/api/job/" + sid1)
        if j.get("status") in ("done", "error"):
            st = j.get("status")
            break
        time.sleep(1)
    check("non-audio -> error", st == "error", "status=%s" % st)

    # 2. 未知模型 key
    code, r = req(B, "POST", "/api/upload", {"name": "a.wav", "b64": tone_b64()})
    sid2 = r["sid"]
    code, r = req(B, "POST", "/api/run", {"sid": sid2, "sep": "NOPE", "den": "denoiser_master64"})
    check("unknown sep key -> 400", code == 400, "code=%s" % code)

    # 3. 坏 base64 / 空 body
    code, r = req(B, "POST", "/api/upload", {"name": "a.wav", "b64": "###not-b64###"})
    check("bad base64 -> 400", code == 400, "code=%s" % code)
    code, r = req(B, "POST", "/api/upload", {})
    check("empty upload -> 400", code == 400, "code=%s" % code)

    # 4. 路径穿越
    code, r = req(B, "GET", "/media/%s/../../etc/passwd" % sid2)
    check("path traversal -> 404", code == 404, "code=%s" % code)

    # 5. 运行中重复 run（先起一个真实长任务）
    code, r = req(B, "POST", "/api/upload", {"name": "tone_long.wav", "b64": tone_b64(16000, 8)})
    sid3 = r["sid"]
    req(B, "POST", "/api/run", {"sid": sid3, "sep": "demucs", "den": "denoiser_master64"})
    time.sleep(1.0)
    code, r = req(B, "POST", "/api/run", {"sid": sid3, "sep": "demucs", "den": "denoiser_master64"})
    check("running -> re-run 409", code == 409, "code=%s" % code)

    # 6. 运行中上传第二个音频并 run（应排队串行，最终两个都 done）
    code, r = req(B, "POST", "/api/upload", {"name": "second.wav", "b64": tone_b64(16000, 5)})
    sid4 = r["sid"]
    code, r = req(B, "POST", "/api/run", {"sid": sid4, "sep": "demucs", "den": "denoiser_master64"})
    queued_ok = code == 200
    st3 = st4 = None
    for _ in range(120):
        _, j3 = req(B, "GET", "/api/job/" + sid3)
        _, j4 = req(B, "GET", "/api/job/" + sid4)
        st3, st4 = j3.get("status"), j4.get("status")
        if st3 in ("done", "error") and st4 in ("done", "error"):
            break
        time.sleep(1)
    check("2nd upload during run -> both settle", queued_ok and st3 == "done" and st4 == "done",
          "queued=%s st3=%s st4=%s" % (queued_ok, st3, st4))

    # 7. 运行中反复轮询（模拟刷新）
    code, r = req(B, "POST", "/api/upload", {"name": "poll.wav", "b64": tone_b64(16000, 6)})
    sid5 = r["sid"]
    req(B, "POST", "/api/run", {"sid": sid5, "sep": "demucs", "den": "denoiser_master64"})
    statuses = set()
    for _ in range(20):
        _, j = req(B, "GET", "/api/job/" + sid5)
        statuses.add(j.get("status"))
        time.sleep(0.4)
    check("poll during run -> state persists", ("running" in statuses) or ("done" in statuses),
          "statuses=%s" % sorted(statuses))

    # 8. GET 打在 POST 路由
    code, r = req(B, "GET", "/api/upload")
    check("GET on /api/upload -> not 200", code != 200, "code=%s" % code)

    # 9. 不存在 sid
    code, r = req(B, "GET", "/api/job/nonexistent-1234")
    check("unknown sid -> 404", code == 404, "code=%s" % code)

    # 10. 服务仍存活
    code, h = req(B, "GET", "/api/health")
    check("server alive after all", code == 200, "code=%s" % code)

    out.close()
    n_pass = sum(1 for _, c, _ in results if c)
    print("\nABNORMAL DONE: %d/%d PASS" % (n_pass, len(results)))


if __name__ == "__main__":
    main()
