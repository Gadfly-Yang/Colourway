---
name: video-color-transfer
description: 把一条片子的调色风格迁移到另一条片子上——给一个参考视频或参考图片（或一组颜色/氛围词），产出同款风格的成片、LUT 和对比图。Use when the user asks to 调色/风格迁移/参照某个视频调色/统一镜头色彩/套 LUT/film look/teal & orange grade, or hands over a reference clip or still and asks for another clip to match it.
---

# 视频风格迁移调色（look transfer）

参考片定义的是**签名**，不是逐像素函数：影调分布 + 冷暖分离 + 饱和度 + 光晕颗粒。
把签名参数化，套到别的素材上，再用数字和 100% 裁切证明它成立。
引擎：`scripts/lookgrade.py`（numpy + ffmpeg，无需 scipy/cv2）。对比图：`scripts/contact_sheet.py`。

## 何时用

- 「把 X.mp4 调成和 Y.mp4/Y.png 一样的风格」
- 「这几条镜头颜色不统一，统一一下」
- 「要电影感青橙 / 胶片 / 逆光日落 / 夜戏霓虹」
- 已有 LUT 但不好使，想改成可控的曲线 + 分离色

不适用：单纯转码、剪接、加字幕。

## 唯一路径：读签名 → 参数化 → 眼睛收尾

参考（视频或图片）只提供**方向**，不提供逐像素答案：内容不同，绝对数值不可比。
所以流程固定为「读签名 → 定起手参数 → 预览循环 → 渲染校验」。

- 参考是视频：`sig REF.mp4`，按下面的对照表翻译成参数。
- 参考是图片：先 `sig` 出全局底子，再用 `match` 给一个起点参数，然后按同一套规则微调。

### 参考是图片（静帧）

```bash
python scripts/lookgrade.py match REF.png SRC.mp4 --out _grade/params_match.json
```

`match` 做的事：把静帧和素材都按亮度分三段（暗/中/亮），取每段的**色相 + 彩度**（不是 R−B：参考的暗部常常是纯黑剪影，R−B 在那里没有意义），加上整体饱和度和对比落差，然后从 base 参数（默认是一份中性参数）出发做带正则的坐标下降——正则把它按在起点附近，所以结果是一版「可用的起点」而不是跑到边界的怪参数。实测 6.mp4 对一张海边落日静帧：饱和 0.393→0.466（静帧 0.463）、亮部彩度 0.267→0.389（静帧 0.390），但中段色相只从 0.531 挪到 0.570（静帧 0.860，是紫色天空）——因为素材中段是水面、静帧中段是天，**颜色长在不同物体上，统计量搬不过去**。所以：`match` 出起点 → 拿 `variant` 试两三版 → 眼睛定案。

### 读签名（参考是什么内容都一样）

```bash
python scripts/lookgrade.py sig REF.mp4      # 全局 + 上/中/下三分之一的 luma 与 R−B
```

把签名翻译成方向，而不是照抄绝对值（内容不同，绝对值不可比）：

| 签名特征 | 含义 | 对应参数 |
|---|---|---|
| shadow_rb 明显 < 0 | 暗部偏青 | 抬 `teal`、`teal_mid`，必要时 `teal_g` |
| high_rb > +0.2 | 高光偏暖 | 抬 `orange`、`rose` |
| p95/p99 低、p50 中 | 高光被压、中间调厚 | 压 `white`/`c4`，抬 `c2`/`c3` |
| 三分区 top 暗且偏蓝、bot 暖 | 顶部冷渐变 | `grad_cool` |
| sat 低但观感浓 | 局部饱和而非全局 | `warm_sat`，别硬抬 `sat` |

## 流程（每条片子都走一遍）

1. **探针**：`probe` 拿分辨率/帧率/帧数/有无音轨；`metrics` 拿原片底子（luma、p99、sat、sh_rb）。
   sat < 0.2 的素材（雾霾、灰片）要先想清楚：全局提饱和会连带把噪声染色。
2. **取帧**：抽 3 个不同时间点看内容（逆光？夜景？大面积单色？），决定从 `defaults` 还是上一条片子的参数出发。
3. **起手参数**：`python scripts/lookgrade.py defaults --out _grade/params_clip.json` 出一份中性参数；或沿用上一条片子的 params。逐条只允许改 tone 曲线和 `grad_cool`/`grad_dark`。
4. **预览循环**：`variant` 出 1280 宽的静帧，**看图 + 看数字**，一次只动 2–3 个参数，改完立刻重出。
   同一场景至少看两个时间点（构图不同，容易一处过一处欠）。
5. **校验**：全片 `render` → `metrics` 复核 → 100% 裁切看天空/暗部/高光边缘 → 出对比图。
6. **交付**：成片 + 对比图 + 参数 JSON(+ LUT)。

## 参数表（全部在 0..1 显示空间）

| 参数 | 作用 | 常用区间 | 备注 |
|---|---|---|---|
| `black,c1..c4,white` | 6 点 tone 曲线（x=0,0.12,0.35,0.60,0.85,1.0） | 见铁律 | 只能单调递增，代码会强制累积最大值 |
| `sat` | 全局饱和 | 1.05–1.5 | 灰片可到 1.5，但先看 `warm_sat` |
| `warm_sat` | 只加强暖像素（R>B）的饱和 | 0–0.6 | 保住中性灰，不动噪声 |
| `teal` | 暗部推青（权重 (1−luma)²） | 0.06–0.20 | 太大会让黑位发蓝 |
| `teal_mid` | 中间调推青（高斯，中心 0.30） | 0–0.11 | 楼群、雾霾中景用它 |
| `teal_g` | 青色偏绿（青 vs 宝蓝） | 0–0.6 | 天空发紫时用它拉回青 |
| `orange` | 高光推暖（权重 luma²） | 0.10–0.30 | 逆光日落吃这个 |
| `rose` | 高光偏玫红 | 0–0.15 | 粉紫黄昏 |
| `cool_amt` / `warm_amt` | **按色相**分离：只推冷像素/只推暖像素 | 0.10–0.17 | 夜景混合光源必用（见铁律 2） |
| `glow_thr`,`glow_amt` | 辉光阈值/强度 | 0.50–0.62 / 0.15–0.50 | 有光源/逆光才给大值 |
| `glow_r1,glow_r2` | 两级半径（≈3% 与 ≈15% 画幅） | 6 / 30 | 1080p 尺度下的像素半径 |
| `grad_cool` | 顶部冷渐变（垂直，1.6 次幂） | 0–0.14 | 天空大的一律加一点 |
| `grad_dark` | 顶部压暗（垂直，1.5 次幂） | 0–0.25 | 想做出「上方暗、地平线亮」的黄昏感时用，参考片有紫黑天顶时最有效 |
| `vignette` | 暗角 | 0.15–0.22 | 超过 0.25 会看出圈 |
| `grain` / `grain_chroma` | 颗粒强度 / 色度颗粒比例 | 0.010–0.016 / **暗片设 0** | 见铁律 4；亮片 0.2 无妨 |
| `knee`,`knee_gain` | 逐通道高光软膝 | 0.94 / 0.45 | 见铁律 3 |

## 铁律（都是踩过的坑）

1. **别试图把调色烘成 3D LUT**。调色版里含辉光(halation)与上采样，颜色不是纯函数：45³ LUT 留出帧 PSNR 只有 14.7 dB，高光 R−B 预测 0.256、实际 0.385。参数化才留得住辉光与渐变。
2. **亮度分层在混合光源场景会翻车**。夜景里钠灯橘色墙在暗部，按 luma 推青会把它染灰。改用 `cool_amt`/`warm_amt` 按色相分离：偏蓝的更蓝、偏红的更红，中性灰不动。
3. **高光要软膝，不要硬夹**。直接 clip 会让暖色高光某个通道先撞顶（实测通道裁剪 19.7%，参考只有 0.4%），出现色相跳变。`knee 0.94 / gain 0.45` 把裁剪压到 ~5%。
4. **暗片必须关色度颗粒**。`grain_chroma 0.22` 在 4:2:0 下会把暗部噪点放大成块状色斑（100% 裁切可见），码率还虚高（74MB→54MB）。纯亮度颗粒同时充当天空渐变的抖动，防色带。
5. **一次只改 2–3 个参数**。同时改 6 个只能在"更糟"和"另一种糟"之间选。
6. **看两个时间点**。单帧好看的参数常常在另一构图上过曝或死黑。
7. **别拿统计量当目标求解**。同一「参考」下，手调的四条成片冷暖落差从 0.15 到 0.68（参考 0.396），用这些统计量做代价函数时，手调那版打分 4.05，而「什么都不做」是 3.26 —— 优化器更喜欢原片。统计量只能指方向，定案必须靠看图。
8. **别追求和参考相同的绝对值**。内容不同，`sat`/`p99` 绝对值不可比；只对齐方向：暗部 R−B 转负、高光 R−B 转正、p99 下降、sat 上升。

## 校验清单（交付前逐条过）

- `metrics` 复核成片：`sat` 相对原片提升 1.5–3×（原片越灰倍率越高）；`p99` 黄昏 0.75–0.85、夜戏 0.55–0.65；`shadow_rb < −0.05`；`high_rb > +0.15`（夜戏可放宽到 +0.05）；`clip < 5%`。
- `satp90 ≈ 1.0` **不一定**是过饱和：大面积单色场景（整片暖光/整片江面）本身就是 1.0，别据此降饱和。
- 100% 裁切看三处：天空/渐变区（色带）、最暗部（色斑、噪点染色）、高光边缘（色相跳变）。
- `ffprobe`：时长、帧数、分辨率与源一致；音轨保留。
- 出对比图（原片 / 成片 / 参考），确认"三格并排时风格是一家人"。

## 交付物命名

```
<clip>_graded.mp4          成片（默认 1920×1080，crf 18，preset slow，音频 copy）
调色对比_<clip>.png         三格对比图
_grade/params_<clip>.json  该条的全部参数（可复现、可微调）
_grade/look/*.png          预览与变体静帧
LUTs/<look>.cube           可选：给 NLE 的近似 LUT
```

多条片子统一风格时：先定一条"锚片"，其余片子只允许改 tone 曲线和 `grad_cool`，分离色/颗粒保持一致。

## 命令速查

```bash
# 0) 环境自检（ffmpeg/ffprobe 在 PATH 或 FFMPEG=/path）
python scripts/lookgrade.py probe CLIP.mp4

# 1) 读底子 / 读参考签名
python scripts/lookgrade.py metrics CLIP.mp4 --frames 40
python scripts/lookgrade.py sig REF.mp4

# 2) 起手参数
python scripts/lookgrade.py defaults --out _grade/params_clip.json

# 3) 预览循环（1280 宽静帧）
python scripts/lookgrade.py variant CLIP.mp4 3.5 '{"teal":0.14,"orange":0.22}' v1 --params _grade/params_clip.json
python scripts/lookgrade.py preview CLIP.mp4 1.0 4.5 --params _grade/params_clip.json

# 4) 整片渲染（--limit 20 可先试渲 20 帧）
python scripts/lookgrade.py render CLIP.mp4 CLIP_graded.mp4 --params _grade/params_clip.json
python scripts/lookgrade.py render CLIP.mp4 _grade/test.mp4 --params _grade/params_clip.json --limit 20

# 5) 对比图
python scripts/contact_sheet.py 调色对比_clip.png "原片=before.png" "调色后=after.png" "风格参考=ref.png"

# 6) LUT（仅颜色；辉光/颗粒/渐变无法进 LUT）
python scripts/lookgrade.py lut _grade/params_clip.json LUTs/look.cube --size 45
```

## 抽帧与字体（Windows）

```powershell
# 原片对照帧
ffmpeg -y -v error -ss 3.5 -i CLIP.mp4 -frames:v 1 -vf "scale=960:540:flags=lanczos" before.png
# 成片同点
ffmpeg -y -v error -ss 3.5 -i CLIP_graded.mp4 -frames:v 1 -vf "scale=960:540:flags=lanczos" after.png
# 100% 裁切（检查颗粒/色带）
ffmpeg -y -v error -ss 3.0 -i CLIP_graded.mp4 -frames:v 1 -vf "crop=720:400:200:300" crop.png
```

中文标签字体 `C:\Windows\Fonts\msyhbd.ttc`；`contact_sheet.py` 会自动找，也可 `SHEET_FONT=<path>` 指定。

## 故障排查

- **JSON 报 `Unexpected UTF-8 BOM`**：PowerShell `Set-Content -Encoding UTF8` 会写 BOM。用 python 写，或 `encoding="utf-8-sig"` 读（`load_params` 已兼容）。
- **`json.decoder` / 参数没生效**：`variant` 的第三个参数既可以是 JSON 文件路径也可以是内联 JSON；Windows 下内联 JSON 用单引号包住。
- **渲染完音轨消失**：源无音轨时 `-c:a copy` 会失败，脚本已自动回落 aac；手写命令时用 `-map 1:a?`。
- **成片比源暗一档**：检查是否把 `--size` 给成了非源尺寸（缩放会改变观感），以及 `crf` 是否过高。
- **预览很好看、成片发灰**：多半是预览分辨率下颗粒被忽略；成片看 100% 裁切再判断。
