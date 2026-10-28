---
name: hookcut
description: Free local AI clipper. Turns a long video (file or link) into 30-60s vertical 9:16 clips with face-centered reframing, 2-3 word burned-in captions, punch-in zooms on emphasis words, and optional sound effects. Uses Whisper (local), OpenCV and ffmpeg. No paid APIs, no credits. Use when the user says "clip this", "make shorts/reels/tiktoks from this video", "find the best moments", or pastes a long video link or file and wants vertical clips.
---

# HookCut: free vertical clipper

## When to use
- The user gives a long video (podcast, interview, stream, talk, vlog) as a file path or URL and wants short vertical clips.
- The user asks to find the most viral or hook-heavy moments in a video.
- Do NOT use for videos the user has no rights to. Only clip the user's own content or content they have permission to repurpose. If unclear, ask once.

## Prerequisites (one-time)
1. Python 3.10+ (`python --version`)
2. ffmpeg 5+ (`ffmpeg -version`)
   - Windows: `winget install Gyan.FFmpeg`
   - Mac: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg`
3. Python packages:
   `pip install -U openai-whisper yt-dlp "opencv-python<5"`
   (Add `--break-system-packages` on Linux if pip refuses. On a headless server, `"opencv-python-headless<5"` works the same. Keep OpenCV on 4.x: 5.0 removed the face detector `face_center.py` uses.)
4. Optional SFX: put free CC0 sound files in `~/.claude/skills/hookcut/sfx/`
   as `whoosh.wav` and `pop.wav`. Good sources are Pixabay Sound Effects and freesound.org (filter by CC0). The skill works without them.

Before the first run, check each prerequisite with `which`/`where` and install anything missing. Then confirm both scripts exist in `scripts/`. If they are missing, create them from the "Bundled scripts" section at the bottom of this file.

Skill location: commands below use `~/.claude/skills/hookcut/`. If the skill is installed in the project instead (`.claude/skills/hookcut/`, e.g. in a fresh cloud session), use that path for `scripts/` and `sfx/`.

## Folder structure
```
~/.claude/skills/hookcut/
  SKILL.md
  scripts/face_center.py
  scripts/make_captions.py

  sfx/                      (optional: whoosh.wav, pop.wav)

./hookcut_out/<video-slug>/  (created per job, in the current directory)
  source.mp4
  audio.wav
  audio.json                (Whisper transcript with word timestamps)
  clips.json                (chosen moments + scores)
  ass/clip01.ass ...        (caption files)
  final/01_<title>.mp4 ...  (finished clips)
  qc/                       (QC frames)
  POSTING.md                (titles + captions for each clip)
```

## Settings (defaults, user can override)
- Number of clips: 5
- Clip length: 30-60 s
- Whisper model: `small` (use `base` on slow machines, `medium` for accuracy)
- Output: 1080x1920, 30 fps, H.264 + AAC, loudness -14 LUFS

## Workflow

### Step 0: Get the video
Make the job folder `hookcut_out/<slug>/`.
- Local file: copy it to `source.mp4`. If it is not .mp4, re-encode it:
  `ffmpeg -i input.mov -c:v libx264 -preset veryfast -crf 18 -c:a aac source.mp4`
- URL (user's own/permitted content only):
  `yt-dlp -f "bv*[height<=1080]+ba/b" --merge-output-format mp4 -o source.mp4 "URL"`

Then probe it:
`ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -show_entries format=duration -of json source.mp4`

### Step 1: Transcribe with Whisper (free, local)

```
ffmpeg -y -i source.mp4 -vn -ac 1 -ar 16000 audio.wav
whisper audio.wav --model small --language en --word_timestamps True --output_format json --output_dir .
```
This produces `audio.json` with `segments[].words[]`, each word carrying `start` and `end` in seconds.
Drop `--language en` to auto-detect. Long videos on CPU take a while. Tell the user to expect roughly real-time with `small`.

### Step 2: Score the moments for hook strength
Read `audio.json`. Build candidate windows of 30-60 s. Each window starts at a sentence start and ends at a sentence end. Score each window from 1 to 10 on:

| Factor | Weight | What earns a high score |
|---|---|---|
| Hook (first 3 s) | x3 | Opens with a bold claim, question, number, conflict, or "nobody tells you..." |
| Curiosity gap | x2 | Sets up a question the viewer needs answered |
| Emotion | x2 | Laughter, anger, shock, vulnerability, strong opinion |
| Payoff | x2 | Delivers the answer, punchline or twist before the end |
| Quotability | x1 | Has a line that works as an on-screen title |
| Standalone | x1 | Makes sense with zero context (no "like I said earlier") |

Total = weighted sum (max 110). Pick the top N windows that do not overlap.

Then tighten each pick:
- Start exactly on the hook sentence, not on filler ("so", "um", "yeah").
- End right after the payoff line, plus 0.3 s.
- Snap to word timestamps. Pad the start by -0.10 s.
- Choose 2-5 emphasis words per clip: numbers, strong verbs, the punchline word. Space them at least 4 s apart.

Write `clips.json`:
```json
[
  {"id": "01", "start": 312.40, "end": 359.10, "score": 92,
   "title": "The $0 trick nobody uses",

   "hook_line": "Nobody talks about this, but...",
   "emphasis": ["zero", "never", "doubled"],
   "why": "Bold claim in first 2s, clear payoff at 41s"}
]
```
Show the user the list (title, timestamps, score, why) before rendering. If they are not watching, proceed with the top N.

### Step 3: Find the speaker's face for the 9:16 reframe
For each clip:
`python ~/.claude/skills/hookcut/scripts/face_center.py source.mp4 <start> <duration>`
It prints JSON like: `{"crop_w": 608, "crop_x": 742, "faces_found": 87, "vertical_already": false}`
- `faces_found` = 0: use the center crop the script returns, and flag the clip for QC.
- `vertical_already` = true: skip the crop and only scale.
- Two speakers in a wide shot: the script locks onto the largest face. If the clip alternates between people, split it at the switch and run the script per part (advanced).

### Step 4: Build captions (2-3 words at a time) and zoom times
`python ~/.claude/skills/hookcut/scripts/make_captions.py audio.json <start> <end> ass/clip01.ass "zero,never,doubled"`
- Writes an `.ass` subtitle file: white, uppercase, heavy black outline, centered in the lower third. Each group pops in. Emphasis words turn yellow.
- Prints the zoom windows (seconds relative to the clip) for the emphasis words, e.g. `{"zooms": [[2.05, 2.85], [11.4, 12.2]]}`

### Step 5: Render the clip in one pass (cut + reframe + zoom + captions + loudness)
Build the zoom expression from the zoom windows:
`Z = if(between(on/30,2.05,2.85)+between(on/30,11.4,12.2),1.15,1)`
(No zooms: use `Z = 1`.)

Then run:
```
ffmpeg -y -ss START -t DURATION -i source.mp4 \
 -vf "fps=30,crop=CROP_W:ih:CROP_X:0,scale=1080:1920,zoompan=z='Z':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30,subtitles=ass/clip01.ass" \
 -af "loudnorm=I=-14:TP=-1.5:LRA=11" \
 -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p \
 -c:a aac -b:a 160k -movflags +faststart final/01_title.mp4

```
Notes:
- If the source is already vertical, replace `crop=...,scale=1080:1920` with `scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920`.
- Zoom comes BEFORE subtitles, so the captions stay still while the picture punches in.
- `on/30` works because of `fps=30`. If you change the fps, change both numbers.
- Windows: run this on one line without the `\`. Use forward slashes in the subtitles path, and keep the .ass path relative.
- Filenames: lowercase with underscores, no spaces or quotes.

### Step 6: Sound effects (optional, only if sfx/ has files)
Add a whoosh at each zoom start. The delay is in milliseconds:
```
ffmpeg -y -i final/01_title.mp4 -i ~/.claude/skills/hookcut/sfx/whoosh.wav -i ~/.claude/skills/hookcut/sfx/whoosh.wav \
 -filter_complex "[1:a]adelay=2050|2050,volume=0.35[s1];[2:a]adelay=11400|11400,volume=0.35[s2];[0:a][s1][s2]amix=inputs=3:duration=first:normalize=0[a]" \
 -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 160k final/01_title_sfx.mp4
```
Add one `-i sfx` input and one `[n:a]adelay...` chain per zoom. Keep SFX quiet (0.25-0.4). They should feel like punctuation, not noise. Replace the original file with the sfx version once it passes QC.

### Step 7: QC every clip (do not skip)
For each final clip:
1. Check the specs:
   `ffprobe -v error -show_entries stream=width,height,codec_name -show_entries format=duration -of compact final/01_title.mp4`
   It must be 1080x1920, 30-60 s, h264 + aac.
2. Grab frames at 0.5 s, the middle, and 2 s before the end:
   `ffmpeg -y -ss 0.5 -i final/01_title.mp4 -frames:v 1 qc/01_a.jpg` (repeat for the other two times)
   Open the images and check that the face is in frame, the captions are readable and not covering the face, and nothing is cut off.
3. Check the hook: the first 3 s must contain the hook line. Check the ending: it must land on the payoff, not mid-sentence.
4. Fix and re-render any failures. Never deliver a clip that failed QC.

### Step 8: Deliver
Write `POSTING.md` with, for each clip: file name, title (under 60 characters, no invented claims), a 1-2 line description, 3-5 hashtags, and its timestamp in the source video.
Report to the user: number of clips, the folder path, and one line per clip (title, length, score).
Never post or upload anything. Posting is the user's job.


## Example run
User: "clip this: ~/Videos/podcast_ep12.mp4, give me 3"
1. Creates `hookcut_out/podcast_ep12/`, copies the source, extracts audio.
2. `whisper audio.wav --model small --word_timestamps True --output_format json --output_dir .`
3. Scores 40 candidate windows and picks the top 3: "Why I quit at 30" (score 94), "The pricing mistake" (88), "My worst client ever" (85).
4. For each one: face_center.py, then make_captions.py, then one ffmpeg render, then QC frames.
5. Output: `final/01_why_i_quit_at_30.mp4` (47 s), `final/02_the_pricing_mistake.mp4` (38 s), `final/03_my_worst_client_ever.mp4` (55 s), plus `POSTING.md`.

## Troubleshooting
- "No words in transcript": the `--word_timestamps True` flag was missed. Re-run Whisper.
- Captions out of sync: the clip start in make_captions.py must equal the `-ss` value exactly.
- Font looks wrong on Linux: run `sudo apt install fonts-liberation`, or change `Fontname` in the script to a font you have. You can also add `:fontsdir=/path/to/fonts` after the .ass path in the subtitles filter.
- Face drifts out of frame: the speaker moves a lot. Split the clip into 2-3 parts, reframe each, then join them:
  `ffmpeg -f concat -safe 0 -i list.txt -c copy joined.mp4`
- Slow: use `--model base`, and keep `-preset veryfast`.

## Bundled scripts
The scripts live in `scripts/face_center.py` and `scripts/make_captions.py` next to this file. If they are missing, recreate them from the original HookCut SKILL.md "Bundled scripts" section (or copy them from this project's `.claude/skills/hookcut/scripts/`).
