# Game Store Visual Moodboard

一个可复用的 Codex Skill：分析手游或 PC 游戏的商店截图、宣传图和 Feature Graphic，反推情绪板定位、配色、色调、构图、材质、光照、镜头、角色与字体，最终交付文字分析和一张可直接分享的高分辨率视觉情绪板 PNG。

> 本仓库只包含分析工具与 Skill 说明，不包含 Top Tycoon 或其他第三方游戏的商店截图素材。

## 能做什么

- 扫描本地 PNG、JPG、JPEG、WEBP 素材并生成样本清单
- 使用 SHA-256 排除完全重复图，保留重复组记录
- 提取每张图及全局的主色信息
- 生成便于人工观察的 contact sheet
- 将视觉判断整理成结构化 `analysis.json`，先完成情绪板定位与描述
- 生成可直接阅读的 Markdown 文字分析
- 输出带截图证据、HEX 色块、视觉分支、构图区与风格结论的情绪板 PNG
- 可选输出一个独立 HTML 预览页

## 输出图片包含

最终交付由两部分组成：

1. 文字分析：情绪板定位与描述、样本证据、配色、构图、风格语法、视觉公式与结论
2. 情绪板图片：把“定位分析、图像证据和可复用设计系统”放在同一张图中

图片包含：

1. 位于顶部的情绪板定位、解释性描述、品类、受众感受、核心情绪与视觉承诺
2. 代表性商店截图与简短标签
3. 原始样本数、去重后样本数及重复说明
4. 带名称、HEX、角色、用途和占比说明的配色色块
5. 不同视觉路线或宣传图分支
6. 顶部 / 中部 / 底部等构图区域
7. 色调、材质、光照、镜头、角色、字体及反馈语言
8. 一条可供美术与设计团队直接复用的视觉公式

## 安装

### Windows PowerShell

```powershell
git clone https://github.com/zhili-99/game-store-visual-moodboard.git "$env:USERPROFILE\.codex\skills\game-store-visual-moodboard"
python -m pip install -r "$env:USERPROFILE\.codex\skills\game-store-visual-moodboard\requirements.txt"
```

### macOS / Linux

```bash
git clone https://github.com/zhili-99/game-store-visual-moodboard.git ~/.codex/skills/game-store-visual-moodboard
python3 -m pip install -r ~/.codex/skills/game-store-visual-moodboard/requirements.txt
```

安装后建议开启一个新的 Codex 对话，使 Skill 被重新发现。

## 在 Codex 中使用

直接点名 Skill，并提供本地素材目录或图片文件：

```text
$game-store-visual-moodboard
分析 D:\assets\my-game-store 中的商店图，先给出情绪板定位分析和描述，再输出中文文字报告与情绪板图片，重点拆解配色、色调、构图区域与字体风格。
```

也可以自然语言调用：

```text
分析这组游戏商店截图的视觉风格，先判断情绪板定位，再反推主色、强调色、材质和光照；最终给我文字分析和带 HEX 色块的情绪板图片。
```

Codex 会按以下流程工作：素材扫描与去重 → 视觉观察 → 编写分析 JSON → 渲染 PNG → 视觉校验。

## 命令行使用

要求 Python 3.9+ 与 Pillow。以下命令均在仓库根目录执行。

### 1. 扫描素材

```powershell
python scripts/store_moodboard.py scan .\input --out .\output\scan.json --contact-sheet .\output\contact-sheet.png
```

扫描阶段会递归发现图片、记录尺寸与重复组，并提取主色。可以把多个文件或目录同时传入。

### 2. 完成视觉判断

查看 `contact-sheet.png` 和代表性原图，然后按 [`references/analysis-schema.md`](references/analysis-schema.md) 创建 `analysis.json`。完整拆解维度见 [`references/visual-analysis-rubric.md`](references/visual-analysis-rubric.md)。

这一阶段需要人工或视觉模型判断，因为自动取色无法识别叙事作用、材质层级、视觉焦点与情绪含义。

### 3. 渲染情绪板

```powershell
python scripts/store_moodboard.py render `
  --scan .\output\scan.json `
  --analysis .\analysis.json `
  --report .\output\store-visual-analysis.md `
  --out .\output\game-store-moodboard.png `
  --html .\output\game-store-moodboard.html
```

macOS / Linux 可将 PowerShell 的反引号换成 `\`，或把命令写在一行。

如果自动选择的字体无法显示中文，可增加：

```text
--font <支持中日韩文字的字体路径>
```

Windows 环境会优先尝试 Microsoft YaHei。

## 输入与输出

| 类型 | 文件 | 说明 |
| --- | --- | --- |
| 输入 | 图片目录或图片列表 | 支持 PNG、JPG、JPEG、WEBP |
| 中间产物 | `scan.json` | 文件清单、尺寸、哈希、重复组与取色结果 |
| 中间产物 | `contact-sheet.png` | 快速观察全部样本的联系表 |
| 输入 | `analysis.json` | 视觉语义、设计色板、构图与风格结论 |
| 最终产物 | `store-visual-analysis.md` | 以情绪板定位开头的完整文字分析 |
| 最终产物 | `game-store-moodboard.png` | 高分辨率可视化分析图 |
| 可选产物 | `game-store-moodboard.html` | 独立 HTML 预览页 |

## 目录结构

```text
game-store-visual-moodboard/
├─ SKILL.md
├─ README.md
├─ requirements.txt
├─ agents/
│  └─ openai.yaml
├─ references/
│  ├─ analysis-schema.md
│  └─ visual-analysis-rubric.md
└─ scripts/
   └─ store_moodboard.py
```

## 分析原则

- 商店截图、Feature Graphic、图标和广告素材属于不同证据类型，不应静默混用。
- 自动主色提取是面积统计，可能放大天空、水面或大面积中性色的影响。
- 精确占比必须来自扫描数据并标注为 measured；`70 / 20 / 10` 等设计建议应标注为 recommended。
- SHA-256 只能发现完全重复图，不能识别裁切、改文案、本地化或轻微调色的近重复图。
- 精修 Key Art 与游戏实机图可以属于不同视觉路线，应分析二者如何衔接，而不是强行归为单一风格。
- 游戏特定结论放在项目自己的 `analysis.json` 中，不写死到 Skill 内。

## 隐私与版权

脚本只处理本地文件，不要求网络访问。发布分析结果前，请确认你有权使用其中的截图、Logo、角色和宣传素材；公开仓库或报告中建议使用自有素材、已获授权素材，或只发布不含第三方原图的分析模板。

