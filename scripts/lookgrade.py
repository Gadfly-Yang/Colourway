#!/usr/bin/env python3
"""lookgrade.py - parametric look transfer for video (teal & orange, filmic, dusk/night).

A reference clip or still defines a *look signature*: tone distribution, cool/warm
separation, saturation, halation, grain. This script applies a parameterised grade
with the same signature to other clips, and reports the numbers that prove it.

Requires: numpy, imageio (only for PNG writing), ffmpeg/ffprobe on PATH or FFMPEG/FFPROBE env.
Pillow is only needed by contact_sheet.py.

  python lookgrade.py probe   CLIP
  python lookgrade.py metrics CLIP [--frames N]
  python lookgrade.py sig     CLIP [--frames N]
  python lookgrade.py preview CLIP T [T ...] [--params P.json] [--width 1280]
  python lookgrade.py variant CLIP T OVERRIDES TAG [--params P.json]
  python lookgrade.py render  CLIP OUT [--params P.json] [--size 1920x1080] [--crf 18] [--limit N]
  python lookgrade.py lut     P.json OUT.cube [--size 45] [--title NAME]
  python lookgrade.py match   STILL CLIP [--out P.json] [--base preset.json]
  python lookgrade.py defaults [--out P.json]

Everything renders into ./_grade/look/ so previews and sheets are easy to find.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys

import numpy as np

WORKDIR = os.environ.get("LOOKGRADE_DIR", "_grade")
LOOK_DIR = os.path.join(WORKDIR, "look")

LUMA_W = np.array([0.2126, 0.7152, 0.0722], np.float32)
DIR_TEAL = np.array([-0.55, 0.12, 0.55], np.float32)
DIR_ORANGE = np.array([0.55, 0.20, -0.45], np.float32)
DIR_HAL = np.array([1.15, 0.90, 0.65], np.float32)
DIR_ROSE = np.array([0.30, -0.16, 0.06], np.float32)
DIR_COOLTOP = np.array([-0.10, 0.04, 0.26], np.float32)

CP_X = np.array([0.0, 0.12, 0.35, 0.60, 0.85, 1.0], np.float32)
CURVE_KEYS = ["black", "c1", "c2", "c3", "c4", "white"]

DEFAULT = dict(
    # tone curve control points (display space, 0..1)
    black=0.008, c1=0.080, c2=0.300, c3=0.620, c4=0.860, white=0.960,
    # split toning
    teal=0.060, teal_mid=0.000, teal_g=0.000, orange=0.100, rose=0.000,
    # chroma
    sat=1.20, warm_sat=0.000, cool_amt=0.000, warm_amt=0.000,
    # halation / bloom
    glow_thr=0.55, glow_amt=0.300, glow_r1=6.0, glow_r2=30.0,
    # spatial finishing
    grad_cool=0.0, grad_dark=0.000, vignette=0.150,
    # texture
    grain=0.010, grain_chroma=0.220,
    # highlight soft knee (per channel): above `knee` the slope becomes `knee_gain`
    knee=0.940, knee_gain=0.450,
)


# --------------------------------------------------------------------------- tools
def _tool(name: str) -> str:
    env = os.environ.get(name.upper())
    if env and os.path.exists(env):
        return env
    found = shutil.which(name) or shutil.which(name + ".exe")
    if found:
        return found
    for cand in (
        rf"C:\Users\{os.environ.get('USERNAME','')}\AppData\Local\Microsoft\WinGet\Packages"
        r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin\%s.exe" % name,
        rf"C:\ffmpeg\bin\%s.exe" % name,
    ):
        if os.path.exists(cand):
            return cand
    raise SystemExit(f"{name} not found: put it on PATH or set {name.upper()}=<path>")


FF = None
FP = None


def tools():
    global FF, FP
    if FF is None:
        FF, FP = _tool("ffmpeg"), _tool("ffprobe")
    return FF, FP


def probe(path: str) -> dict:
    ff, fp = tools()
    out = subprocess.run(
        [fp, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate,nb_frames,codec_name,pix_fmt:format=duration",
         "-of", "json", path],
        capture_output=True, text=True).stdout
    j = json.loads(out)
    st = j["streams"][0]
    num, den = (st.get("r_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den or 1)
    return dict(width=int(st["width"]), height=int(st["height"]), fps=round(fps, 3),
                frames=int(st.get("nb_frames") or 0),
                duration=float(j.get("format", {}).get("duration") or 0),
                codec=st.get("codec_name"), pix_fmt=st.get("pix_fmt"))


def has_audio(path: str) -> bool:
    _, fp = tools()
    out = subprocess.run([fp, "-v", "error", "-select_streams", "a",
                          "-show_entries", "stream=index", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout
    return bool(out.strip())


# --------------------------------------------------------------------------- colour math
def srgb_to_lin(x):
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4).astype(np.float32)


def lin_to_srgb(x):
    x = np.clip(x, 0.0, None)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055).astype(np.float32)


def gauss(img, sigma):
    """Gaussian blur via the frequency domain (no scipy needed)."""
    h, w = img.shape[:2]
    fy = np.fft.fftfreq(h).astype(np.float32)[:, None]
    fx = np.fft.rfftfreq(w).astype(np.float32)[None, :]
    g = np.exp(-2 * np.pi ** 2 * sigma ** 2 * (fx * fx + fy * fy)).astype(np.float32)
    F = np.fft.rfft2(img, axes=(0, 1))
    out = np.fft.irfft2(F * (g[..., None] if img.ndim == 3 else g), s=(h, w), axes=(0, 1))
    return out.astype(np.float32)


def tone_table(p, n=4096):
    ys = np.array([p[k] for k in CURVE_KEYS], np.float32)
    ys = np.maximum.accumulate(np.clip(ys, 0.0, 1.0))
    return np.interp(np.linspace(0, 1, n, dtype=np.float32), CP_X, ys).astype(np.float32)


def color_grade(rgb, p, table=None, with_glow=True):
    """rgb: float32 HxWx3, display-encoded sRGB 0..1 -> graded float32."""
    if table is None:
        table = tone_table(p)
    n = table.shape[0]
    y = table[np.clip((rgb * (n - 1)).astype(np.int32), 0, n - 1)]

    luma = (y * LUMA_W).sum(-1)
    ws, wh = (1.0 - luma) ** 2, luma ** 2
    wm = np.exp(-(((luma - 0.30) / 0.22) ** 2))
    teal_dir = DIR_TEAL + p.get("teal_g", 0.0) * np.array([0.0, 1.0, 0.0], np.float32)
    y = (y + ws[..., None] * p["teal"] * teal_dir
           + wm[..., None] * p.get("teal_mid", 0.0) * teal_dir
           + wh[..., None] * p["orange"] * DIR_ORANGE
           + wh[..., None] * p.get("rose", 0.0) * DIR_ROSE)

    luma = (y * LUMA_W).sum(-1)[..., None]
    y = luma + (y - luma) * p["sat"]

    if p.get("warm_sat", 0.0) > 0:  # saturation weighted by warmness (R>B)
        luma = (y * LUMA_W).sum(-1)[..., None]
        warm = np.clip((y[..., 0] - y[..., 2]) / np.maximum(y.max(-1), 1e-3), 0.0, 1.0)[..., None]
        y = luma + (y - luma) * (1.0 + p["warm_sat"] * warm)

    ca, wa = p.get("cool_amt", 0.0), p.get("warm_amt", 0.0)
    if ca > 0 or wa > 0:  # hue-selective push: cool pixels cooler, warm pixels warmer
        mx = np.maximum(y.max(-1), 1e-3)
        ww = np.clip((y[..., 0] - y[..., 2]) / mx, 0.0, 1.0)[..., None]
        cw = np.clip((y[..., 2] - y[..., 0]) / mx, 0.0, 1.0)[..., None]
        y = y + ww * wa * DIR_ORANGE + cw * ca * DIR_TEAL

    if with_glow and p["glow_amt"] > 0:
        lin = srgb_to_lin(np.clip(y, 0.0, 1.0))
        thr = p["glow_thr"]
        hi = np.clip((lin - thr) / max(1.0 - thr, 1e-3), 0.0, 1.0) ** 1.4
        add = (0.55 * gauss(hi, p["glow_r1"]) + 0.45 * gauss(hi, p["glow_r2"]))
        add = add * p["glow_amt"] * DIR_HAL
        lin = 1.0 - (1.0 - lin) * (1.0 - np.clip(add, 0.0, 1.0))
        y = lin_to_srgb(lin)

    knee, gain = p.get("knee", 0.94), p.get("knee_gain", 0.45)
    if knee < 1.0:
        y = np.where(y > knee, knee + (y - knee) * gain, y)
    return np.clip(y, 0.0, 1.0).astype(np.float32)


def finish(y, p, rng):
    """Vertical cool gradient, vignette and grain (display space)."""
    h, w = y.shape[:2]
    if p.get("grad_cool", 0.0) > 0:
        yv = (np.linspace(1.0, 0.0, h, dtype=np.float32) ** 1.6)[:, None, None]
        y = np.clip(y + p["grad_cool"] * yv * DIR_COOLTOP, 0.0, 1.0)
    if p.get("grad_dark", 0.0) > 0:
        yv = (np.linspace(1.0, 0.0, h, dtype=np.float32) ** 1.5)[:, None, None]
        y = y * (1.0 - p["grad_dark"] * yv)
    if p.get("vignette", 0.0) > 0:
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
        y = y * (1.0 - p["vignette"] * np.clip(r - 0.55, 0, None) ** 1.4)[..., None]
    if p.get("grain", 0.0) > 0:
        luma = (y * LUMA_W).sum(-1)
        amp = p["grain"] * (0.55 + 0.9 * (1.0 - luma))
        mono = rng.normal(0.0, 1.0, (h, w)).astype(np.float32)
        y = y + (mono * amp)[..., None]
        if p.get("grain_chroma", 0.0) > 0:  # keep 0 for dark clips: 4:2:0 makes it blotchy
            chroma = rng.normal(0.0, 1.0, (h, w, 3)).astype(np.float32)
            y = y + chroma * (p["grain"] * p["grain_chroma"])
    return np.clip(y, 0.0, 1.0).astype(np.float32)


# --------------------------------------------------------------------------- frame I/O
def _read_exact(stream, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = stream.read(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return bytes(buf)


def frames(path, w, h, limit=None):
    ff, _ = tools()
    cmd = [ff, "-v", "error", "-i", path, "-vf", f"scale={w}:{h}:flags=lanczos",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    # stderr is dropped: we stop reading early on purpose (limit) and ffmpeg's
    # "broken pipe" complaint about a deliberate close is pure noise.
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    size = w * h * 3
    n = 0
    try:
        while limit is None or n < limit:
            b = _read_exact(proc.stdout, size)
            if b is None:
                break
            n += 1
            yield np.frombuffer(b, np.uint8).reshape(h, w, 3).astype(np.float32) / 255.0
    finally:
        proc.stdout.close()
        proc.wait()


def grab(path, t, w, h):
    ff, _ = tools()
    cmd = [ff, "-v", "error", "-ss", str(t), "-i", path, "-frames:v", "1",
           "-vf", f"scale={w}:{h}:flags=lanczos", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    buf = subprocess.run(cmd, capture_output=True).stdout
    need = w * h * 3
    if len(buf) < need:
        raise SystemExit(f"could not decode a frame at t={t} from {path} (t beyond duration?)")
    return np.frombuffer(buf[:need], np.uint8).reshape(h, w, 3).astype(np.float32) / 255.0


def write_png(path, img):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    try:
        import imageio.v3 as iio
        iio.imwrite(path, (np.clip(img, 0, 1) * 255).astype(np.uint8))
    except ImportError:
        from PIL import Image
        Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(path)
    return path


# --------------------------------------------------------------------------- metrics
def metrics(img):
    x = img.reshape(-1, 3)
    luma = x @ LUMA_W
    mx, mn = x.max(1), x.min(1)
    sat = np.where(mx > 1e-4, (mx - mn) / np.maximum(mx, 1e-4), 0)
    sh, hi = luma < 0.25, luma > 0.70
    return dict(
        luma=float(luma.mean()), luma_std=float(luma.std()),
        p5=float(np.percentile(luma, 5)), p50=float(np.percentile(luma, 50)),
        p95=float(np.percentile(luma, 95)), p99=float(np.percentile(luma, 99)),
        sat=float(sat.mean()),
        shadow_rb=float((x[sh, 0] - x[sh, 2]).mean()) if sh.any() else 0.0,
        high_rb=float((x[hi, 0] - x[hi, 2]).mean()) if hi.any() else 0.0,
        clip=float(((mx > 0.995) | (mn < 0.005)).mean()),
    )


STYLE_KEYS = ["luma", "p5", "p50", "p95", "p99", "sat", "shadow_rb", "high_rb", "clip"]


def clip_metrics(path, w=480, h=270, n=40):
    acc = {}
    for i, fr in enumerate(frames(path, w, h, limit=n)):
        for k, v in metrics(fr).items():
            acc.setdefault(k, []).append(v)
    return {k: round(float(np.mean(v)), 4) for k, v in acc.items()}


def signature(path, n=24):
    """Style signature: global numbers + top/middle/bottom thirds (sky vs ground)."""
    acc, thirds = {}, {}
    for i, fr in enumerate(frames(path, 480, 270, limit=n)):
        m = metrics(fr)
        for k in STYLE_KEYS:
            acc.setdefault(k, []).append(m[k])
        h = fr.shape[0]
        for name, sl in (("top", slice(0, h // 3)), ("mid", slice(h // 3, 2 * h // 3)),
                         ("bot", slice(2 * h // 3, h))):
            mm = metrics(fr[sl])
            thirds.setdefault(name, {}).setdefault("luma", []).append(mm["luma"])
            thirds.setdefault(name, {}).setdefault("rb", []).append(
                float((fr[sl][..., 0] - fr[sl][..., 2]).mean()))
    sig = {k: round(float(np.mean(v)), 4) for k, v in acc.items()}
    sig["thirds"] = {k: {kk: round(float(np.mean(vv)), 4) for kk, vv in v.items()}
                     for k, v in thirds.items()}
    return sig


def print_metrics(tag, m):
    print(f"{tag:16s} luma={m['luma']:.3f} p50={m['p50']:.3f} p95={m['p95']:.3f} "
          f"p99={m['p99']:.3f} sat={m['sat']:.3f} sh_rb={m['shadow_rb']:+.3f} "
          f"hi_rb={m['high_rb']:+.3f} clip={m['clip']:.3f}")


# --------------------------------------------------------------------------- params
def defaults():
    return {k: float(v) for k, v in DEFAULT.items()}


def load_params(path=None, **overrides):
    p = defaults()
    if path:
        with open(path, encoding="utf-8-sig") as f:
            p.update({k: float(v) for k, v in json.load(f).items() if not k.startswith("_")})
    p.update({k: float(v) for k, v in overrides.items() if v is not None})
    return p


def save_params(path, p):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({k: round(float(v), 5) for k, v in p.items()}, f, indent=2)
    print("wrote", path)


# --------------------------------------------------------------------------- commands
def cmd_probe(path):
    info = probe(path)
    print(json.dumps({**info, "audio": has_audio(path)}, indent=2))


def cmd_metrics(path, n=40):
    m = clip_metrics(path, n=n)
    print_metrics(os.path.basename(path), m)
    return m


def cmd_sig(path, n=24):
    print(json.dumps(signature(path, n=n), indent=2))


def apply_still(path, t, p, w=1280, seed=7):
    h = int(round(w * 9 / 16 / 2) * 2)
    a = grab(path, t, w, h)
    g = finish(color_grade(a, p, table=tone_table(p), with_glow=True), p, np.random.default_rng(seed))
    return a, g


def cmd_preview(path, times, params=None, width=1280):
    p = load_params(params)
    stem = os.path.splitext(os.path.basename(path))[0]
    for t in times:
        _, g = apply_still(path, t, p, width)
        print("wrote", write_png(os.path.join(LOOK_DIR, f"prev_{stem}_{t}.png"), g))
        print_metrics(f"  t={t}", metrics(g))


def cmd_variant(path, t, overrides, tag, params=None, width=1280):
    p = load_params(params)
    p.update({k: float(v) for k, v in overrides.items() if not k.startswith("_")})
    _, g = apply_still(path, t, p, width)
    print("wrote", write_png(os.path.join(LOOK_DIR, f"v_{tag}.png"), g))
    m = metrics(g)
    print_metrics(f"  {tag}", m)
    return p


def cmd_render(path, out, params=None, size="1920x1080", crf=18, limit=None, fps=None,
               preset="slow", audio="copy", seed=None):
    ff, _ = tools()
    p = load_params(params)
    table = tone_table(p)
    w, h = (int(x) for x in size.lower().split("x"))
    info = probe(path)
    fps = fps or info["fps"] or 30
    seed = seed if seed is not None else int(hashlib.sha1(os.path.basename(path).encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    log_path = os.path.join(WORKDIR, "render.log")
    os.makedirs(WORKDIR, exist_ok=True)
    log = open(log_path, "wb")
    acodec = ["-c:a", "copy"] if audio == "copy" and has_audio(path) else ["-c:a", "aac", "-b:a", "192k"]
    enc = subprocess.Popen(
        [ff, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
         "-r", str(fps), "-i", "-", "-i", path, "-map", "0:v", "-map", "1:a?",
         "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-tune", "film",
         "-profile:v", "high", "-pix_fmt", "yuv420p",
         "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
         *acodec, "-shortest", "-movflags", "+faststart", out],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log)
    n = 0
    try:
        for fr in frames(path, w, h, limit=limit):
            g = finish(color_grade(fr, p, table=table, with_glow=True), p, rng)
            enc.stdin.write((g * 255).astype(np.uint8).tobytes())
            n += 1
            if n % 25 == 0:
                print(f"  {n} frames", flush=True)
    finally:
        enc.stdin.close()
        enc.wait()
        log.close()
    if enc.returncode != 0:
        raise SystemExit(f"ffmpeg failed, see {log_path}")
    print(f"{out}: frames={n} size={os.path.getsize(out)/1e6:.1f}MB "
          f"({w}x{h} @ {fps}fps, crf{crf})")


def cmd_lut(pfile, out, size=45, title=None):
    p = load_params(pfile)
    n = int(size)
    v = np.linspace(0, 1, n, dtype=np.float32)
    B, G, R = np.meshgrid(v, v, v, indexing="ij")
    flat = np.stack([R.ravel(), G.ravel(), B.ravel()], -1).reshape(1, -1, 3)
    graded = color_grade(flat, p, table=tone_table(p), with_glow=False).reshape(-1, 3)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(f'TITLE "{title or os.path.splitext(os.path.basename(out))[0]}"\n')
        f.write(f"LUT_3D_SIZE {n}\nDOMAIN_MIN 0.0 0.0 0.0\nDOMAIN_MAX 1.0 1.0 1.0\n")
        for c in graded:
            f.write("%.6f %.6f %.6f\n" % tuple(c))
    print("wrote", out, f"({n}^3, colour only: no halation/grain/vignette)")


# --------------------------------------------------------------------------- still matching
MATCH_SPACE = [
    ("sat", 0.85, 2.20),
    ("teal", 0.00, 0.35),
    ("teal_mid", 0.00, 0.25),
    ("orange", 0.00, 0.60),
    ("rose", 0.00, 0.50),
    ("c2", 0.10, 0.40),
    ("c3", 0.30, 0.65),
    ("c4", 0.60, 0.92),
    ("white", 0.75, 0.98),
    ("grad_cool", 0.00, 0.25),
    ("grad_dark", 0.00, 0.30),
]


def _hue_chroma(rgb):
    """Chroma-weighted circular mean hue (0..1) and mean chroma of an RGB block."""
    mx, mn = rgb.max(1), rgb.min(1)
    d = mx - mn
    c = np.where(mx > 1e-4, d / np.maximum(mx, 1e-4), 0.0)
    r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    h = np.zeros(len(rgb), np.float32)
    m = d > 1e-4
    i = m & (mx == r); h[i] = ((g[i] - b[i]) / d[i]) % 6.0
    i = m & (mx == g); h[i] = ((b[i] - r[i]) / d[i]) + 2.0
    i = m & (mx == b); h[i] = ((r[i] - g[i]) / d[i]) + 4.0
    h = h / 6.0
    w = c
    if w.sum() < 1e-6:
        return 0.0, 0.0
    ang = h * 2 * np.pi
    hs = (np.arctan2((np.sin(ang) * w).sum(), (np.cos(ang) * w).sum()) / (2 * np.pi)) % 1.0
    return float(hs), float(c.mean())


BANDS = (("dark", 0.00, 0.25), ("mid", 0.25, 0.62), ("bright", 0.62, 1.00))


def color_feats(img):
    """Band-wise hue/chroma + saturation. Hue survives dark, near-black areas where R-B does not."""
    x = img.reshape(-1, 3).astype(np.float32)
    l = x @ LUMA_W
    order = np.argsort(l)
    n = len(l)
    out = {}
    for name, lo, hi in BANDS:
        seg = x[order[int(lo * n):max(int(lo * n) + 1, int(hi * n))]]
        hue, chroma = _hue_chroma(seg)
        out[f"hue_{name}"] = hue
        out[f"chr_{name}"] = chroma
    mx, mn = x.max(1), x.min(1)
    out["sat"] = float(np.where(mx > 1e-4, (mx - mn) / np.maximum(mx, 1e-4), 0.0).mean())
    out["contrast"] = float(np.percentile(l, 95) - np.percentile(l, 20))
    out["luma"] = float(l.mean())
    return out


def _circ(a, b):
    d = abs(a - b) % 1.0
    return min(d, 1.0 - d)


def _feat_dist(g, t):
    j = 0.0
    for name, _lo, _hi in BANDS:
        w = min(t[f"chr_{name}"], 0.35) / 0.35      # only bands that actually carry colour
        j += w * (2.2 * _circ(g[f"hue_{name}"], t[f"hue_{name}"])
                  + 2.0 * abs(g[f"chr_{name}"] - t[f"chr_{name}"]))
    j += 1.2 * abs(g["sat"] - t["sat"])
    j += 0.5 * abs(g["contrast"] - t["contrast"])
    return j


def cmd_match(still, clip, out, base=None, width=960, samples=3, steps=(0.10, 0.04, 0.015), rounds=3):
    """Copy a still's colour relationships onto a clip. Exposure stays the clip's own."""
    h = int(round(width * 9 / 16 / 2) * 2)
    p = load_params(base)
    t_feat = color_feats(grab(still, 0, width, h))
    print("still :", {k: round(v, 3) for k, v in t_feat.items()})

    dur = probe(clip)["duration"] or 1.0
    n = max(1, samples)
    times = [round(dur * (i + 0.5) / n, 2) for i in range(n)]
    srcs = [grab(clip, t, width, h) for t in times]
    print(f"clip  : {n} frames @ {width}x{h} ({', '.join(str(t) for t in times)}s)")

    base_p = dict(p)

    def _reg(pp):
        return float(np.mean([abs(pp[k] - base_p[k]) / (hi - lo) for k, lo, hi in MATCH_SPACE]))

    def score(pp):
        feats = [color_feats(finish(color_grade(a, pp, table=tone_table(pp)),
                                    pp, np.random.default_rng(5))) for a in srcs]
        m = {k: float(np.mean([f[k] for f in feats])) for k in t_feat}
        return _feat_dist(m, t_feat) + 0.35 * _reg(pp), m

    before, m0 = score(p)
    print("start :", {k: round(v, 3) for k, v in m0.items()}, f"J={before:.3f}")

    best = before
    for step in steps:
        for _ in range(rounds):
            moved = False
            for key, lo, hi in MATCH_SPACE:
                span = hi - lo
                for sign in (1, -1):
                    cand = dict(p)
                    cand[key] = float(np.clip(p[key] + sign * step * span, lo, hi))
                    if abs(cand[key] - p[key]) < 1e-6:
                        continue
                    j, _m = score(cand)
                    if j < best - 1e-4:
                        best, p, moved = j, cand, True
                        print(f"  {key:10s} -> {p[key]:.3f}   J={best:.3f}")
            if not moved:
                break

    j, m1 = score(p)
    print("final :", {k: round(v, 3) for k, v in m1.items()}, f"J={j:.3f}  ({before - j:+.3f})")
    print(f"\n{'feature':10s} {'still':>8s} {'clip':>8s} {'graded':>8s}")
    for k in list(t_feat):
        print(f"{k:11s} {t_feat[k]:8.3f} {m0[k]:8.3f} {m1[k]:8.3f}")
    save_params(out, p)
    print(f"\nparams -> {out}")
    print("colour relationships come from the still; tone curve keeps the clip's own exposure.")
    return p


# --------------------------------------------------------------------------- cli
def _flags(argv):
    """Split '--key value' pairs from positionals."""
    pos, flags = [], {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            key = a[2:]
            if "=" in key:
                key, val = key.split("=", 1)
                flags[key] = val
                i += 1
            elif i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                flags[key] = argv[i + 1]
                i += 2
            else:
                flags[key] = "1"
                i += 1
        else:
            pos.append(a)
            i += 1
    return pos, flags


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        raise SystemExit(__doc__)
    cmd, rest = argv[0], argv[1:]
    pos, f = _flags(rest)

    if cmd == "probe":
        cmd_probe(pos[0])
    elif cmd == "metrics":
        cmd_metrics(pos[0], int(f.get("frames", 40)))
    elif cmd == "sig":
        cmd_sig(pos[0], int(f.get("frames", 24)))
    elif cmd == "defaults":
        save_params(f.get("out", os.path.join(WORKDIR, "params_default.json")), defaults())
    elif cmd == "preview":
        cmd_preview(pos[0], [float(x) for x in pos[1:]], f.get("params"), int(f.get("width", 1280)))
    elif cmd == "variant":
        ov = pos[2]
        ov = json.load(open(ov, encoding="utf-8-sig")) if ov.endswith(".json") else json.loads(ov)
        cmd_variant(pos[0], float(pos[1]), ov, pos[3], f.get("params"), int(f.get("width", 1280)))
    elif cmd == "render":
        cmd_render(pos[0], pos[1], f.get("params"), f.get("size", "1920x1080"),
                   int(f.get("crf", 18)), int(f["limit"]) if "limit" in f else None,
                   float(f["fps"]) if "fps" in f else None, f.get("preset", "slow"),
                   f.get("audio", "copy"))
    elif cmd == "lut":
        cmd_lut(pos[0], pos[1], int(f.get("size", 45)), f.get("title"))
    elif cmd == "match":
        cmd_match(pos[0], pos[1], f.get("out", os.path.join(WORKDIR, "params_match.json")),
                  f.get("base"), int(f.get("width", 960)), int(f.get("samples", 3)))
    else:
        raise SystemExit(f"unknown command {cmd!r}\n{__doc__}")


if __name__ == "__main__":
    main(sys.argv[1:])
