import json, sys, re

tr, start, end, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
emph = {w.strip().lower() for w in (sys.argv[5] if len(sys.argv) > 5 else "").split(",") if w.strip()}

data = json.load(open(tr, encoding="utf-8"))
words = [w for s in data["segments"] for w in s.get("words", [])]
words = [w for w in words if w["start"] >= start - 0.05 and w["end"] <= end + 0.05]

def ts(t):

    t = max(t, 0)
    h, m, s = int(t // 3600), int(t % 3600 // 60), t % 60
    return f"{h}:{m:02d}:{s:05.2f}"

def clean(w):
    return re.sub(r"[^\w'$%?!-]", "", w.strip()).upper()

# group 2-3 words; break on pauses and sentence punctuation
groups, cur = [], []
for w in words:
    if cur and (len(cur) == 3 or w["start"] - cur[-1]["end"] > 0.35
                or re.search(r"[.!?,]$", cur[-1]["word"].strip())):
        groups.append(cur)
        cur = []
    cur.append(w)
if cur:
    groups.append(cur)

header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Arial Black,96,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,3,2,60,60,560,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


lines, zooms, last_zoom = [], [], -10.0
for i, g in enumerate(groups):
    g_start = g[0]["start"] - start
    nxt = groups[i + 1][0]["start"] - start if i + 1 < len(groups) else g[-1]["end"] - start + 0.3
    g_end = max(min(nxt, g[-1]["end"] - start + 0.6), g_start + 0.25)
    parts = []
    for w in g:
        word = clean(w["word"])
        if not word:
            continue
        key = re.sub(r"[^\w]", "", word.lower())
        if key in emph:
            parts.append("{\\c&H00FFFF&}" + word + "{\\c&HFFFFFF&}")  # yellow
            ws = w["start"] - start
            if ws - last_zoom >= 4:
                zooms.append([round(max(ws - 0.05, 0), 2), round(ws + 0.8, 2)])
                last_zoom = ws
        else:
            parts.append(word)
    if parts:
        pop = "{\\fscx80\\fscy80\\t(0,80,\\fscx100\\fscy100)}"
        lines.append(f"Dialogue: 0,{ts(g_start)},{ts(g_end)},Cap,,0,0,0,,{pop}{' '.join(parts)}")

with open(out, "w", encoding="utf-8") as f:
    f.write(header + "\n".join(lines) + "\n")
print(json.dumps({"captions": len(lines), "zooms": zooms}))
