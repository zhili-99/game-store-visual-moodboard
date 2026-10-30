# Analysis JSON schema

Use UTF-8 JSON. Text fields may be Chinese or English. Paths in `representatives` refer to the zero-based `unique_images` order in `scan.json`.

## Required structure

```json
{
  "title": "Top Tycoon 商店图情绪板与配色区域",
  "subtitle": "玩具沙盘经营 × 主题乐园刺激 × 失控喜剧 × 金币暴富感",
  "positioning": {
    "category": "轻度模拟经营 × Tycoon 爽感表达",
    "statement": "把复杂经营包装成一眼可懂、即时回报的玩具沙盘狂欢",
    "description": "商店图不强调严肃经营深度，而是用巨大主体、夸张事件和密集奖励，把建造与扩张转译成轻松、亢奋、可立即获得满足的视觉体验。",
    "audience": "喜欢轻操作、强反馈、快速成长的泛休闲经营用户",
    "emotional_goal": "先感到欢乐与失控，再期待富足和扩张",
    "visual_promise": "每张图都承诺一个清晰动作和一个可见奖励"
  },
  "mood_keywords": ["欢乐", "亢奋", "富足", "轻喜剧"],
  "sample_note": "24 个文件，SHA-256 去重后 8 张有效样本",
  "representatives": [
    {"source_index": 0, "label": "生产效率", "lane": "玩具沙盘实机线"}
  ],
  "lanes": [
    {
      "name": "玩具沙盘实机线",
      "description": "等距俯视、机制清晰、生产—管理—扩张",
      "colors": ["#7ED040", "#37C6F1"]
    }
  ],
  "palette": [
    {
      "hex": "#B425A5",
      "name": "品牌洋红",
      "usage": "底部口号条",
      "share": "11–15% · measured",
      "text": "light"
    }
  ],
  "zones": [
    {
      "name": "顶部 HUD",
      "range": "6–8%",
      "description": "等级、金币、体力与菜单，传达成熟度和资源富足",
      "color": "#F4F2EC",
      "text": "dark"
    }
  ],
  "allocation": [
    {"label": "场景主色", "value": 70, "color": "#37C6F1"},
    {"label": "品牌／UI", "value": 20, "color": "#B425A5"},
    {"label": "反馈高光", "value": 10, "color": "#F7D426"}
  ],
  "allocation_note": "recommended",
  "rules": [
    {"name": "色调", "description": "高明度、高饱和；冷蓝阴影配黄白高光，避免脏灰"},
    {"name": "材质", "description": "圆角 PVC 玩具感；宽高光、低粗糙度、柔和 AO"}
  ],
  "formula": ["一个动作动词", "一个巨大主体", "一个引导手势", "一个奖励色"],
  "formula_result": "缩略图可读的爽感事件",
  "conclusion": "用固定品牌锚点统一实机机制图和高精度事件海报。"
}
```

## Field guidance

- `representatives`: 4–12 entries. Use `source_index` from `scan.json`; do not duplicate the same image.
- `positioning`: required. `statement` gives the one-sentence positioning conclusion; `description` explains how the images create that positioning. `category`, `audience`, `emotional_goal`, and `visual_promise` provide the compact labels shown in the image and text report.
- `lanes`: 1–3 entries. Add multiple lanes only when the samples materially differ in camera, rendering, or communication goal.
- `palette`: 6–10 tokens. Merge near-identical clusters and assign a semantic role.
- `text`: `light` or `dark`, controlling swatch and zone label contrast.
- `zones`: usually 3–5 composition regions. They need not be vertical if the source uses another stable structure.
- `allocation`: a normalized list whose `value` fields total 100. Mark whether it is measured or recommended in `allocation_note`.
- `rules`: normally cover tone, material, lighting, camera, characters, typography, feedback, and density. Keep each description short enough for the moodboard.
- `formula`: 3–5 reusable ingredients, not a sentence copied from one screenshot.

Unknown optional fields are ignored by the renderer.

