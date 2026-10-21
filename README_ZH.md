<h1 align="center">🎬 Colourway · 色彩转移</h1>

<p align="center">
  <b>Colourway 是「配色方案」。这一套，从参考里搬过来。</b><br/>
  把你羡慕的那种颜色涂到自己的素材上——产出调好色的成片，外加一份能读、能改、改完能重渲的颜色参数文件。不烘 LUT。
</p>

<p align="center">
  <a href="README.md">English</a> ｜ <a href="README_ZH.md"><b>简体中文</b></a> ｜ <a href="docs/CLI.md">命令行文档</a> ｜ <a href="SKILL.md">Agent Skill</a>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-3DA639.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/python-3.9%2B-3776AB.svg" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/runtime-ffmpeg-007808.svg" alt="ffmpeg">
  <a href="https://github.com/Gadfly-Yang/Colourway/stargazers"><img src="https://img.shields.io/github/stars/Gadfly-Yang/Colourway.svg" alt="Stars"></a>
  <a href="https://github.com/Gadfly-Yang/Colourway/issues"><img src="https://img.shields.io/github/issues/Gadfly-Yang/Colourway.svg" alt="Issues"></a>
</p>

<p align="center">
  <img src="docs/images/look-transfer-three-panel.png" alt="原片、参考图、调色后" width="100%">
</p>

<p align="center">
  <i>左 → 右：色彩平庸的原片 · 当作风格来源的落日参考图 · 同一段素材调色后的样子。<br/>
  同一套参数，没有烘 LUT。素材来自 Pexels（免费商用）。</i>
</p>

<p align="center">
  <b>输入：</b>一段素材 + 一个参考（照片或视频） &nbsp;·&nbsp;
  <b>输出：</b>调好的 <code>.mp4</code> + 一份 26 个数字的 <code>.json</code> &nbsp;·&nbsp;
  <b>要装：</b>Python 3.9+、<code>numpy imageio pillow</code>、<code>ffmpeg</code>
</p>

---

## 📦 一眼看清：输入 / 输出 / 要装什么

| 🎬 你给什么 | 📤 你拿到什么 | 🧰 你先装什么 |
|:--|:--|:--|
| **1 段要调的片子** —— `myclip.mp4`，ffmpeg 能读的格式都行<br><br>**1 个参考** —— 一张照片（`ref.jpg`、`ref.png`）**或**一段视频（`ref.mp4`）。同题材、完全不同题材都可以。 | **`myclip_graded.mp4`** —— 调好色的成片，H.264，原音轨原样复制<br><br>**`myclip.json`** —— 产出它的 26 个数字，改完可以重渲<br><br>**`look.cube`** —— 可选，给 Premiere / 达芬奇用的 LUT<br><br>**PNG 预览图** —— 任意时间点的前后对比帧 | **Python 3.9+**<br><br>**3 个包**：`numpy imageio pillow`<br><br>**ffmpeg + ffprobe** 在 PATH 里<br><br>不需要显卡 · 不需要 API Key · 不需要注册 · 不上传任何素材 |

```
调色前/                            调色后/
├── myclip.mp4    ────────────▶    ├── myclip_graded.mp4   ← 留下的成片
└── ref.jpg                        ├── myclip.json         ← 26 个数字（改完可重渲）
                                   ├── LUTs/look.cube     ← 可选，只有颜色
                                   └── _grade/look/*.png  ← 预览图和对比图
```

## 🌟 这是什么

你有一段拍得很平的视频，和一张（或一段）你羡慕它颜色的参考素材。
Colourway 会把参考读成一个**风格签名**——影调分位、冷暖分离、饱和度、光晕、
垂直结构——然后用**参数化**的管线把你的素材调成同样的关系。

产出不只是一段视频：还有产出它的那 **26 个数字**组成的 JSON。改一个数，重渲，对比。
全程没有黑箱。

- 🎯 **参考 → 数字**：`sig` 把任意视频或图片读成可比较的签名。
- 🧮 **参数化，不是 LUT**：光晕、颗粒、垂直渐变都能保留——LUT 存不下这些空间效果。
- 🎛️ **26 个可读旋钮**：影调曲线（`black … white`）、分离调色、按色相推色、光晕半径、颗粒、暗角。
- 🖼️ **图片也能用**：可以用一张照片当参考给视频调色，也可以直接给照片调色。
- 🎞️ **保留原声**：`render` 直接复制原音轨，不重编码。
- 🧩 **给 AI Agent 用**：自带 `SKILL.md`，含「数字 → 参数」的翻译表和踩坑记录。
- 🐍 **依赖极轻**：numpy + ffmpeg。没有 OpenCV、没有 scipy、没有需要编译的扩展。

## 🤔 为什么不直接烘一个 LUT？

因为调过色的画面不是颜色函数。你想复刻的那种「质感」里有**光晕**（高光边缘的光溢出）、
局部辉光、垂直渐变和颗粒——全是空间性的东西。把它们烘进 45³ LUT，平均颜色能对上，但让
参考片看起来「贵」的那层辉光没了。

拿一对真实素材（一条片子和它的调色版，128 帧）实测：

| 做法 | 留出帧误差 |
|---|---|
| 从帧对学出来的 45³ 3D LUT | **14.7 dB PSNR** —— 不可用 |
| 参数化（影调 + 分离调色 + 光晕），16 个旋钮 | **平均绝对误差 0.0196** |

所以这里把调色保留成数字：能读、能 diff、能重渲、能解释。

## 🚀 快速开始

### 1 · 先装环境（约两分钟）

```bash
# Python 3.9+ 和三个包（Pillow 只有 contact_sheet.py 用得到）
pip install numpy imageio pillow

# ffmpeg + ffprobe —— 按你的系统挑一行
winget install Gyan.FFmpeg     # Windows
brew install ffmpeg            # macOS
sudo apt install ffmpeg        # Ubuntu / Debian

ffmpeg -version                # 能打印版本号就算装好了
```

不需要显卡、不需要账号、不需要 API Key。渲染是 CPU 上的 numpy 加管道喂给 ffmpeg。

### 2 · 先看它能不能跑（30 秒）

```bash
python scripts/lookgrade.py render myclip.mp4 out.mp4 \
       --params examples/params_sea_sunset.json --limit 30
```

`--limit 30` 只渲前 30 帧——先确认管线通、顺便看一眼效果，再决定要不要整片渲。

### 3 · 用你自己的参考调你自己的片子

```bash
# 先看清楚手上是什么
python scripts/lookgrade.py probe   myclip.mp4
python scripts/lookgrade.py metrics myclip.mp4

# 看清楚参考是什么（视频或图片都行）
python scripts/lookgrade.py sig     reference.mp4

# 生成一份中性起点——这个 JSON 就是全部的调参界面
python scripts/lookgrade.py defaults --out _grade/params_myclip.json

# 迭代：每次改 2–3 个键，看两个时间点，再决定留或退
python scripts/lookgrade.py variant myclip.mp4 3.5 _grade/_ov.json v3 --params _grade/params_myclip.json
python scripts/lookgrade.py preview myclip.mp4 1.0 4.5 --params _grade/params_myclip.json

# 整片渲染 + 数据验证
python scripts/lookgrade.py render  myclip.mp4 myclip_graded.mp4 --params _grade/params_myclip.json
python scripts/lookgrade.py metrics myclip_graded.mp4

# 可选：导出 .cube 给 Premiere / Resolve（只有颜色，没有光晕和颗粒）
python scripts/lookgrade.py lut _grade/params_myclip.json LUTs/look.cube
```

> 💡 **提示**：所有截图、预览和日志都落在 `_grade/`，不会往素材目录里乱丢文件。
> 整片渲染前，先让 `variant` 出两三个时间点——一帧好看很会骗人，三帧才说真话。

## 🧠 「读风格」读的是什么

`sig` 把参考读成数字——影调分位、暗部/高光的冷暖分离、饱和度，以及垂直三分区：

```json
{ "luma": 0.224, "p50": 0.080, "p99": 0.935, "sat": 0.643,
  "shadow_rb": 0.087, "high_rb": 0.278, "clip": 0.233,
  "thirds": { "top": {"luma": 0.179, "rb": 0.173},
              "mid": {"luma": 0.337, "rb": 0.217},
              "bot": {"luma": 0.156, "rb": 0.043} } }
```

这些数字是**方向，不是目标**：内容不同，两段片子的绝对值本来就不可比。
`shadow_rb` 明显小于 0 说明暗部偏青；`high_rb` 大于 +0.2 说明高光偏暖；
顶区暗、底区暖，说明你需要一个垂直渐变。

| 签名读数 | 含义 | 该动的旋钮 |
|---|---|---|
| `shadow_rb` ≪ 0 | 暗部偏青 | `teal`、`teal_mid` |
| `high_rb` > +0.2 | 高光偏暖 | `orange`、`rose` |
| `p99` 贴近 1.0 | 参考里高光爆了 | `white`、`knee` |
| `thirds.top` 暗 + `thirds.bot` 暖 | 垂直色阶 | `grad_dark`、`grad_cool` |
| `sat` 远高于你的片子 | 参考饱和很重 | `sat`、`warm_sat` |

完整翻译表在 [SKILL.md](SKILL.md)。

## 🛠 命令

| 命令 | 作用 |
|---|---|
| `probe CLIP` | 分辨率 / 帧率 / 帧数 / 时长 / 有无音轨 |
| `metrics CLIP` | 影调分位、饱和度、冷暖分离、过曝欠曝 |
| `sig REF` | 同上，外加垂直三分区——参考侧专用 |
| `defaults --out P.json` | 中性参数集（26 个键全在里面） |
| `match STILL CLIP` | 图片参考 + 不同内容：有界搜索一个起点 |
| `preview CLIP T…` | 把指定时间点的帧调色成 1280 宽 PNG |
| `variant CLIP T OV TAG` | 单个时间点 + 一个覆盖字典——迭代循环用它 |
| `render CLIP OUT` | 整片渲染，H.264 crf 18，复制音轨，进度写 `_grade/render.log` |
| `lut P.json OUT.cube` | 把颜色部分烘成 `.cube` |

完整参数、退出码、环境变量见 [docs/CLI.md](docs/CLI.md)。

## 🎛 参数

全部在显示空间，0–1。先有六个影调控制点（`black, c1 … c4, white`），然后：

| 组 | 键 |
|---|---|
| 分离调色 | `teal`（暗部）、`teal_mid`（中间调）、`teal_g`（青 ↔ 蓝）、`orange`（高光）、`rose`（高光偏洋红） |
| 按色相推色 | `cool_amt`、`warm_amt`——只推本来就偏蓝 / 本来就偏红的像素 |
| 彩度 | `sat`、`warm_sat`（只作用于暖色像素） |
| 光晕 | `glow_thr`、`glow_amt`、`glow_r1`、`glow_r2`（两级半径，约画幅的 3 % 和 15 %） |
| 空间 | `grad_cool`、`grad_dark`（垂直）、`vignette` |
| 质感 | `grain`、`grain_chroma` |
| 保护 | `knee`、`knee_gain`——逐通道高光软膝 |

每个键的建议取值范围都在 [SKILL.md](SKILL.md)。

## 📊 用数字验收

下面这些变化是**这个 look 想要的**，不是通用标准：

| | 原片 | 调色后 |
|---|---|---|
| 饱和度 | 0.187 | **0.487** |
| 亮度 | 0.678 | **0.412** |
| p50（中间调） | 0.745 | **0.416** |
| p99（高光） | 0.904 | **0.623** |
| `shadow_rb`（暗部） | −0.175 | **−0.356** |

原片是一段灰白的阴天海景：饱和度 ×2.6，整段高位被压下来（p99 0.904 → 0.623，已经没有
像素高于 0.70，所以 `high_rb` 不再报告），暗部进一步推向青，顶部压暗加冷，让海平线成为
画面最亮的一条。

> ⚠️ `clip` 报 0.089，主要是**底部**裁剪——青色把深阴影像素的红通道推到了 0。
> `metrics` 故意两端都统计，先看 100 % 裁切再判断是不是问题。

## 🧪 踩过的坑

1. **不要追参考的绝对值。** 内容不同，`sat` / `p99` 不可比。要匹配的是方向：暗部转青、
   高光转暖并压低、饱和度抬高。
2. **按亮度分层在混合光下会翻车。** 夜景里钠灯照亮的墙面落在「暗部」区间，
   「暗部推青」会把它涂灰。改用 `cool_amt` / `warm_amt`：按色相分离，橘墙仍然是橘墙。
3. **高光要给软膝。** 硬裁剪会让某个通道先饱和，色相直接跳变。
   `knee 0.94 / knee_gain 0.45` 在某条测试片上把通道裁剪从 19.7 % 降到约 5 %。
4. **暗调素材把色度颗粒关掉。** 8-bit 4:2:0 会把色度噪声放大成斑块；纯亮度颗粒还能
   给平滑天空做抖动，防止色带。
5. **至少看两个时间点。** 只讨好一帧的调色，下一帧经常就糊了。
6. **统计量只能指方向，不能替你决定。** 同一个参考下，四次手工调色的冷暖落差从 0.15
   到 0.68（参考 0.396）；用这些统计量搭的评分，把手工调色版打成了比「什么都不做」
   还差（4.05 vs 3.26）——所以这工具没有「一键解到参考」的按钮。

## ❓ 常见问题

<details>
<summary><b>需要显卡吗？</b></summary>

不需要。纯 CPU 的 numpy，1080p 大约 1.5–2.5 秒一帧——几分钟的素材没问题，长片不划算。
想先看效果可以 `--limit N` 只渲一小段。
</details>

<details>
<summary><b>参考必须和我的素材是同一段内容吗？</b></summary>

不必须，通常也不是。签名给的是方向，差距靠手调收。同内容最省事（能一帧对一帧比），
但任何一张调过色的图都够开工。
</details>

<details>
<summary><b>结果能进 Premiere / 达芬奇吗？</b></summary>

两条路：直接把渲染好的片子拖进去（音轨完整），或者用 `lut` 导出 `.cube` 在 Lumetri /
Resolve 里套。注意 LUT 只带颜色——光晕、颗粒、垂直渐变是空间效果，只存在于渲染结果里。
</details>

<details>
<summary><b>为什么是九个命令，而不是一个 auto？</b></summary>

因为真正有意思的判断是创作判断：多暗、多暖、多少辉光。这工具负责把测量、预览、渲染
做快，让这些判断变便宜——而不是假装替你判断。
</details>

## 🧩 接到 AI Agent 里

`SKILL.md` 是一个自包含的 skill：流程、参数表（含建议范围）、上面的翻译规则、已知的
失败模式。把目录丢进 agent 的 skills 目录，然后说「把这条片子调成那个参考的样子」就行，
连出三格对比图用的 `scripts/contact_sheet.py` 都在里面。

## 🙏 致谢

- demo 原片 —— [Calm Sea Under Overcast Sky](https://www.pexels.com/video/34727351/)（Pexels，免费商用，[许可](https://www.pexels.com/license/)）。
- 参考静帧 —— [Cloud Over Sea At Sunset](https://www.pexels.com/photo/cloud-over-sea-at-sunset-20141165/)（Pexels，同许可）。
- 另一段海浪 demo —— [Drone View Of Big Waves](https://www.pexels.com/video/drone-view-of-big-waves-3571264/) by Coverr（`examples/params_ocean.json`）。
- 引擎调用 `ffmpeg` 外部程序，不打包它。

## 📄 许可证

MIT —— 见 [LICENSE](LICENSE)。随便用，不担保。

## ⭐ Star 趋势

[![Star History Chart](https://api.star-history.com/svg?repos=Gadfly-Yang/Colourway&type=Date)](https://star-history.com/#Gadfly-Yang/Colourway&Date)

---

<p align="center">如果它帮你省下了一个晚上的色轮，欢迎点个 ⭐，让更多剪辑的人找到它。</p>
