#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""级联 Web 应用冒烟测试：从 high_res_wham 随机抽 N 条走完整 上传→分离→降噪→下载 链路。

用法:
  python _smoke_test.py [--n 15] [--seed 42] [--base http://127.0.0.1:8123]
                        [--cap 15] [--sep demucs] [--den denoiser_master64]
                        [--out tools/_logs/smoke_test.jsonl]

只读测试，不落模型；结果逐条写 JSONL，可断点续跑（已 sid 完成则跳过重测）。
"""
import argparse, base64, glob, io, json, os, random, sys, time, urllib.request, urllib.error
import numpy as np
import soundfile as sf

B64CHUNK = 0


def post(base, path, obj, timeout=120):
    req = urllib.request.Request(base + path, data=json.dumps(obj).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def get(base, path, timeout=120):
    return json.loads(urllib.request.urlopen(base + path, timeout=timeout).read())


def get_bytes(base, path, timeout=120):
    return urllib.request.urlopen(base + path, timeout=timeout).read()


def wav_to_b64(data, sr):
    """data: (n, ch) float32 -> 16-bit PCM WAV -> base64"""
    buf = io.BytesIO()
    sf.write(buf, data, sr, format="WAV", subtype="PCM_16")
    return base64.b64encode(buf.getvalue()).decode()


def load_truncated(path, cap_s):
    x, sr = sf.read(path, dtype="float32", always_2d=True)
    n = min(x.shape[0], int(sr * cap_s))
    return x[:n], sr


def verify_output(raw, out_sr, in_dur):
    """返回 (ok, msg)：时长近似一致 + 非静音 + 有限值"""
    if not np.all(np.isfinite(raw)):
        return False, "non-finite samples"
    if raw.ndim == 1:
        raw = raw[:, None]
    if raw.shape[0] < out_sr * 0.5:
        return False, "too short (%ds)" % (raw.shape[0] / out_sr)
    dur = raw.shape[0] / out_sr
    if abs(dur - in_dur) > max(0.5, in_dur * 0.15):
        return False, "duration mismatch (in %.2f out %.2f)" % (in_dur, dur)
    rms = float(np.sqrt(np.mean(raw ** 2)))
    if rms < 1e-4:
        return False, "silent (rms %.2e)" % rms
    return True, "dur %.2fs rms %.4f" % (dur, rms)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=15)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--base", default="http://127.0.0.1:8123")
    ap.add_argument("--cap", type=float, default=15.0)
    ap.add_argument("--sep", default="demucs")
    ap.add_argument("--den", default="denoiser_master64")
    ap.add_argument("--out", default="tools/_logs/smoke_test.jsonl")
    ap.add_argument("--timeout", type=int, default=400)
    args = ap.parse_args()

    audio_dir = "F:/high_res_wham/audio"
    files = sorted(glob.glob(audio_dir + "/*.wav"))
    rng = random.Random(args.seed)
    picks = rng.sample(files, min(args.n, len(files)))

    # 续跑：读已完成的 sid
    done = set()
    if os.path.exists(args.out):
        for line in open(args.out, encoding="utf-8"):
            try:
                r = json.loads(line)
                if r.get("status") == "done":
                    done.add(r["file"])
            except Exception:
                pass

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    out = open(args.out, "a", encoding="utf-8")
    ok = 0
    for i, f in enumerate(picks, 1):
        name = os.path.basename(f)
        if name in done:
            print("[%02d/%d] SKIP (done) %s" % (i, len(picks), name))
            continue
        t0 = time.time()
        try:
            x, sr = load_truncated(f, args.cap)
            b64 = wav_to_b64(x, sr)
            up = post(args.base, "/api/upload", {"name": name, "b64": b64})
            sid = up["sid"]
            run = post(args.base, "/api/run", {"sid": sid, "sep": args.sep, "den": args.den})
            job = None
            for _ in range(args.timeout // 2):
                job = get(args.base, "/api/job/" + sid)
                if job.get("status") in ("done", "error"):
                    break
                time.sleep(2)
            if job is None or job.get("status") == "error":
                raise RuntimeError("job error: %s" % job.get("error"))
            final = job.get("result", {}).get("final")
            raw = get_bytes(args.base, "/media/%s/den/%s" % (sid, final))
            y, out_sr = sf.read(io.BytesIO(raw), dtype="float32", always_2d=True)
            vok, vmsg = verify_output(y, out_sr, x.shape[0] / sr)
            rec = {
                "file": name, "status": "done", "vok": vok, "verify": vmsg,
                "in_dur_s": round(x.shape[0] / sr, 2), "out_sr": out_sr,
                "wall_s": round(time.time() - t0, 1),
                "sep_load_s": job["result"].get("sep", {}).get("load_s"),
                "sep_infer_s": job["result"].get("sep", {}).get("infer_s"),
                "den_load_s": job["result"].get("den", {}).get("load_s"),
                "den_infer_s": job["result"].get("den", {}).get("infer_s"),
            }
            if vok:
                ok += 1
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
            print("[%02d/%d] %s %s  wall=%.1fs" % (i, len(picks),
                  "OK " if vok else "BAD", name, rec["wall_s"]))
        except Exception as e:
            rec = {"file": name, "status": "error", "error": "%s: %s" % (type(e).__name__, e),
                   "wall_s": round(time.time() - t0, 1)}
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
            print("[%02d/%d] ERR %s  %s" % (i, len(picks), name, rec["error"]))
    out.close()
    print("\nSMOKE DONE: ok=%d  total=%d" % (ok, len(picks)))


if __name__ == "__main__":
    main()
