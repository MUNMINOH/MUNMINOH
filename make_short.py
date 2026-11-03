"""주제 하나로 유튜브 쇼츠(세로 1080x1920) 영상을 자동으로 만드는 스크립트.

흐름: 주제 → 대본(Claude) → 음성(edge-tts) → 배경 + 자막 → mp4

사용 예:
    python make_short.py "블랙홀에 대한 놀라운 사실"
    python make_short.py --script my_script.txt
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
FPS = 30
GAP_AFTER_LINE = 0.25  # 문장 사이 쉬는 시간(초)

DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_VOICE = "ko-KR-SunHiNeural"

FONT_CANDIDATES = [
    # Windows
    "C:/Windows/Fonts/malgunbd.ttf",
    "C:/Windows/Fonts/malgun.ttf",
    # macOS
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/Library/Fonts/NanumGothicBold.ttf",
    # Linux
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]

PALETTES = [
    ((20, 30, 70), (120, 40, 140)),
    ((10, 60, 80), (20, 150, 140)),
    ((70, 20, 40), (220, 90, 60)),
    ((25, 25, 35), (80, 90, 130)),
    ((30, 70, 30), (160, 170, 50)),
    ((60, 30, 90), (230, 120, 160)),
]


@dataclass
class Script:
    title: str
    lines: list[str]
    keywords: list[str] = field(default_factory=list)  # 장면별 배경 이미지 검색어(영어)
    description: str = ""
    hashtags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- 1. 대본

SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "image_keyword": {"type": "string"},
                },
                "required": ["text", "image_keyword"],
                "additionalProperties": False,
            },
        },
        "description": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "lines", "description", "hashtags"],
    "additionalProperties": False,
}


def write_script_with_claude(topic: str, n_lines: int, language: str, model: str) -> Script:
    try:
        import anthropic
    except ImportError:
        sys.exit("anthropic 패키지가 없습니다. pip install -r requirements.txt 를 먼저 실행하세요.")

    prompt = f"""유튜브 쇼츠(약 30~50초) 나레이션 대본을 써 주세요.

주제: {topic}
언어: {language}

조건:
- 문장은 {n_lines}개 안팎. 각 문장은 소리 내어 읽기 좋은 짧은 문장(한국어 기준 35자 이내).
- 첫 문장은 시청자가 넘기지 않도록 강하게 궁금증을 주는 훅.
- 마지막 문장은 짧은 마무리나 구독/댓글 유도.
- 이모지, 괄호, 특수기호는 쓰지 않음(음성으로 읽기 때문).
- 확실하지 않은 사실은 쓰지 않음.
- title: 화면 상단에 계속 보일 짧은 제목(15자 이내).
- image_keyword: 그 문장에 어울리는 배경 사진 검색어(영어 1~3단어).
- description: 업로드용 설명 2~3문장.
- hashtags: 해시태그 5개(# 포함)."""

    client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model=model,
        max_tokens=16000,
        # 안전 필터에 걸리면 서버가 다른 모델로 자동 재시도
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={
            "effort": "medium",
            "format": {"type": "json_schema", "schema": SCRIPT_SCHEMA},
        },
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        sys.exit("Claude가 이 주제의 대본 작성을 거절했습니다. 다른 주제로 시도해 보세요.")

    text = "".join(b.text for b in response.content if b.type == "text")
    data = json.loads(text)
    return Script(
        title=data["title"],
        lines=[l["text"].strip() for l in data["lines"] if l["text"].strip()],
        keywords=[l["image_keyword"] for l in data["lines"] if l["text"].strip()],
        description=data["description"],
        hashtags=data["hashtags"],
    )


def read_script_file(path: Path) -> Script:
    """첫 줄 = 제목, 나머지 줄 = 문장(빈 줄은 무시)."""
    rows = [r.strip() for r in path.read_text(encoding="utf-8-sig").splitlines() if r.strip()]
    if len(rows) < 2:
        sys.exit("대본 파일은 첫 줄에 제목, 그 다음 줄부터 문장을 한 줄씩 적어 주세요.")
    return Script(title=rows[0].lstrip("# ").strip(), lines=rows[1:])


# ---------------------------------------------------------------- 2. 음성

def ffmpeg_exe() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("ffmpeg를 찾을 수 없습니다. pip install -r requirements.txt 를 실행하세요.")


def run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        print(result.stderr[-3000:], file=sys.stderr)
        raise RuntimeError("ffmpeg 실행 실패")


def media_duration(path: Path) -> float:
    out = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", str(path)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", out)
    if not m:
        raise RuntimeError(f"길이를 읽을 수 없습니다: {path}")
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


async def _edge_tts_all(lines: list[str], paths: list[Path], voice: str, rate: str) -> None:
    import edge_tts
    for text, path in zip(lines, paths):
        await edge_tts.Communicate(text, voice, rate=rate).save(str(path))


def make_voice(lines: list[str], work: Path, voice: str, rate: str, engine: str) -> list[Path]:
    paths = [work / f"voice_{i:03d}.mp3" for i in range(len(lines))]
    if engine == "edge":
        try:
            asyncio.run(_edge_tts_all(lines, paths, voice, rate))
        except Exception as e:  # 네트워크 문제 등
            sys.exit(f"음성 생성 실패: {e}\n인터넷 연결을 확인하거나 --tts silent 로 테스트해 보세요.")
    else:  # silent: 음성 없이 글자 수로 길이를 추정 (테스트용)
        for text, path in zip(lines, paths):
            dur = max(1.5, len(text) * 0.13)
            run([ffmpeg_exe(), "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                 "-t", f"{dur:.2f}", "-c:a", "libmp3lame", str(path)])
    return paths


# ---------------------------------------------------------------- 3. 배경

def find_font(user_font: str | None) -> str:
    for cand in ([user_font] if user_font else []) + FONT_CANDIDATES:
        if cand and Path(cand).exists():
            return cand
    sys.exit("한글 폰트를 찾지 못했습니다. --font 로 .ttf 파일 경로를 지정해 주세요.")


def cover_fit(img: Image.Image) -> Image.Image:
    img = img.convert("RGB")
    scale = max(W / img.width, H / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left, top = (img.width - W) // 2, (img.height - H) // 2
    return img.crop((left, top, left + W, top + H))


def gradient_background(seed: int) -> Image.Image:
    rnd = random.Random(seed)
    c1, c2 = PALETTES[seed % len(PALETTES)]
    mask = Image.linear_gradient("L").resize((W, H))
    if rnd.random() < 0.5:
        mask = mask.transpose(Image.FLIP_TOP_BOTTOM)
    img = Image.composite(Image.new("RGB", (W, H), c2), Image.new("RGB", (W, H), c1), mask)
    # 은은한 빛 번짐
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(glow)
    for _ in range(5):
        r = rnd.randint(150, 420)
        x, y = rnd.randint(0, W), rnd.randint(0, H)
        tint = tuple(min(255, v + 60) for v in c2)
        d.ellipse((x - r, y - r, x + r, y + r), fill=tint)
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    return Image.blend(img, glow, 0.35)


def pexels_photo(query: str, dest: Path, api_key: str) -> bool:
    url = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode(
        {"query": query, "orientation": "portrait", "per_page": 5})
    try:
        req = urllib.request.Request(url, headers={"Authorization": api_key, "User-Agent": "shorts-maker"})
        with urllib.request.urlopen(req, timeout=20) as r:
            photos = json.load(r).get("photos", [])
        if not photos:
            return False
        src = random.choice(photos)["src"]["large2x"]
        req = urllib.request.Request(src, headers={"User-Agent": "shorts-maker"})
        with urllib.request.urlopen(req, timeout=30) as r:
            dest.write_bytes(r.read())
        return True
    except Exception as e:
        print(f"  (Pexels 이미지 실패: {query} - {e})")
        return False


def make_backgrounds(script: Script, work: Path, images_dir: Path | None) -> list[Image.Image]:
    n = len(script.lines)
    user_images = []
    if images_dir:
        user_images = sorted(p for p in images_dir.iterdir()
                             if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
        if not user_images:
            print(f"  ({images_dir} 에 이미지가 없어 기본 배경을 씁니다)")
    pexels_key = os.environ.get("PEXELS_API_KEY")

    backgrounds = []
    for i in range(n):
        img = None
        if user_images:
            img = Image.open(user_images[i % len(user_images)])
        elif pexels_key:
            query = script.keywords[i] if i < len(script.keywords) else script.title
            dest = work / f"photo_{i:03d}.jpg"
            if pexels_photo(query, dest, pexels_key):
                img = Image.open(dest)
        if img is not None:
            bg = cover_fit(img)
            bg = Image.blend(bg, Image.new("RGB", (W, H), (0, 0, 0)), 0.35)  # 자막이 잘 보이게 어둡게
        else:
            bg = gradient_background(i)
        backgrounds.append(bg)
    return backgrounds


# ---------------------------------------------------------------- 4. 자막

def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """단어 단위로 줄바꿈하고, 한 단어가 너무 길면 글자 단위로 자릅니다."""
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if font.getlength(trial) <= max_width:
            cur = trial
            continue
        if cur:
            lines.append(cur)
        cur = ""
        for ch in word:
            if font.getlength(cur + ch) > max_width and cur:
                lines.append(cur)
                cur = ""
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def caption_overlay(text: str, title: str, font_path: str) -> Image.Image:
    """투명 배경 위에 상단 제목 + 가운데 자막을 그린 이미지."""
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    # 상단 제목 박스
    tfont = ImageFont.truetype(font_path, 64)
    tlines = wrap_text(title, tfont, W - 160)[:2]
    th = len(tlines) * 84
    d.rounded_rectangle((60, 170, W - 60, 170 + th + 60), radius=36, fill=(0, 0, 0, 170))
    y = 200
    for line in tlines:
        d.text((W // 2, y), line, font=tfont, fill=(255, 221, 0), anchor="ma")
        y += 84

    # 가운데 자막 (길면 글자를 줄여서 4줄 안에 맞춤)
    for size in (84, 76, 68, 60):
        cfont = ImageFont.truetype(font_path, size)
        clines = wrap_text(text, cfont, W - 140)
        if len(clines) <= 4:
            break
    line_h = int(size * 1.3)
    y = int(H * 0.62) - len(clines) * line_h // 2
    for line in clines:
        d.text((W // 2, y), line, font=cfont, fill=(255, 255, 255), anchor="ma",
               stroke_width=8, stroke_fill=(0, 0, 0))
        y += line_h
    return overlay


def srt_time(t: float) -> str:
    ms = round(t * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ---------------------------------------------------------------- 5. 영상 합치기

def render_scene(bg: Path, cap: Path, voice: Path, dur: float, out: Path, seed: int) -> None:
    frames = max(1, round(dur * FPS))
    # 천천히 확대/축소되는 효과(켄 번스). 확대 후 축소해서 화면 떨림을 줄임.
    zoom_in = seed % 2 == 0
    z = f"1+0.10*on/{frames}" if zoom_in else f"1.10-0.10*on/{frames}"
    vf = (f"[0:v]scale={W * 2}:{H * 2},"
          f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS}[bg];"
          f"[bg][1:v]overlay=0:0,format=yuv420p[v];"
          f"[2:a]aresample=44100,apad[a]")
    run([ffmpeg_exe(), "-y", "-loop", "1", "-i", str(bg), "-loop", "1", "-i", str(cap), "-i", str(voice),
         "-filter_complex", vf, "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}",
         "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-c:a", "aac", "-b:a", "192k", "-ac", "2", str(out)])


def concat_scenes(scenes: list[Path], work: Path, out: Path, bgm: Path | None, bgm_volume: float) -> None:
    listfile = work / "scenes.txt"
    listfile.write_text("".join(f"file '{p.name}'\n" for p in scenes), encoding="utf-8")
    joined = work / "joined.mp4" if bgm else out
    run([ffmpeg_exe(), "-y", "-f", "concat", "-safe", "0", "-i", str(listfile), "-c", "copy",
         "-movflags", "+faststart", str(joined)])
    if bgm:
        run([ffmpeg_exe(), "-y", "-i", str(joined), "-stream_loop", "-1", "-i", str(bgm),
             "-filter_complex",
             f"[1:a]volume={bgm_volume}[b];[0:a][b]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]",
             "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             "-movflags", "+faststart", str(out)])


def safe_name(text: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\s]+', "_", text).strip("_")
    return name[:40] or "short"


# ---------------------------------------------------------------- main

def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    p = argparse.ArgumentParser(description="주제 하나로 쇼츠 영상 자동 생성")
    p.add_argument("topic", nargs="?", help="영상 주제 (예: '블랙홀에 대한 놀라운 사실')")
    p.add_argument("--script", type=Path, help="직접 쓴 대본 파일 (첫 줄 제목, 다음 줄부터 한 줄에 한 문장)")
    p.add_argument("--lines", type=int, default=8, help="대본 문장 수 (기본 8)")
    p.add_argument("--language", default="한국어", help="대본 언어 (기본 한국어)")
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"대본을 쓸 Claude 모델 (기본 {DEFAULT_MODEL})")
    p.add_argument("--voice", default=DEFAULT_VOICE,
                   help="edge-tts 목소리 (예: ko-KR-SunHiNeural 여성, ko-KR-InJoonNeural 남성)")
    p.add_argument("--rate", default="+10%", help="말하기 속도 (기본 +10%%)")
    p.add_argument("--tts", choices=["edge", "silent"], default="edge", help="silent: 음성 없이 테스트")
    p.add_argument("--images", type=Path, help="배경으로 쓸 내 이미지 폴더")
    p.add_argument("--bgm", type=Path, help="배경음악 파일 (mp3 등)")
    p.add_argument("--bgm-volume", type=float, default=0.12, help="배경음악 볼륨 (기본 0.12)")
    p.add_argument("--font", help="자막 폰트 파일 경로 (.ttf/.ttc)")
    p.add_argument("--out", type=Path, default=Path("output"), help="결과 폴더 (기본 output)")
    args = p.parse_args()

    if not args.topic and not args.script:
        p.error("주제를 넣거나 --script 로 대본 파일을 지정해 주세요.")

    font = find_font(args.font)

    # 1. 대본
    if args.script:
        print(f"[1/5] 대본 파일 읽는 중: {args.script}")
        script = read_script_file(args.script)
    else:
        if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
            sys.exit("ANTHROPIC_API_KEY 가 설정되어 있지 않습니다.\n"
                     "API 키를 설정하거나, 대본을 직접 써서 --script 로 넣어 주세요. (README 참고)")
        print(f"[1/5] Claude가 대본을 쓰는 중: {args.topic}")
        script = write_script_with_claude(args.topic, args.lines, args.language, args.model)
    for i, line in enumerate(script.lines, 1):
        print(f"      {i}. {line}")

    out_dir = args.out / safe_name(script.title)
    work = out_dir / "work"
    work.mkdir(parents=True, exist_ok=True)

    # 2. 음성
    print(f"[2/5] 음성 만드는 중 ({args.voice if args.tts == 'edge' else '무음 테스트'})")
    voices = make_voice(script.lines, work, args.voice, args.rate, args.tts)
    durations = [media_duration(v) + GAP_AFTER_LINE for v in voices]

    # 3. 배경 + 자막 이미지
    print("[3/5] 배경과 자막 이미지 만드는 중")
    backgrounds = make_backgrounds(script, work, args.images)
    bg_paths, cap_paths = [], []
    for i, (bg, line) in enumerate(zip(backgrounds, script.lines)):
        bg_path, cap_path = work / f"bg_{i:03d}.png", work / f"cap_{i:03d}.png"
        bg.save(bg_path)
        caption_overlay(line, script.title, font).save(cap_path)
        bg_paths.append(bg_path)
        cap_paths.append(cap_path)

    # 4. 장면별 영상
    print("[4/5] 장면 영상 렌더링 중")
    scenes = []
    for i in range(len(script.lines)):
        scene = work / f"scene_{i:03d}.mp4"
        render_scene(bg_paths[i], cap_paths[i], voices[i], durations[i], scene, i)
        scenes.append(scene)
        print(f"      장면 {i + 1}/{len(script.lines)} 완료")

    # 5. 합치기 + 부가 파일
    print("[5/5] 하나의 영상으로 합치는 중")
    video = out_dir / "short.mp4"
    concat_scenes(scenes, work, video, args.bgm, args.bgm_volume)

    t, srt = 0.0, []
    for i, (line, dur) in enumerate(zip(script.lines, durations), 1):
        srt.append(f"{i}\n{srt_time(t)} --> {srt_time(t + dur - GAP_AFTER_LINE)}\n{line}\n")
        t += dur
    (out_dir / "subtitles.srt").write_text("\n".join(srt), encoding="utf-8")
    (out_dir / "upload_info.txt").write_text(
        f"제목: {script.title}\n\n설명:\n{script.description}\n\n"
        f"해시태그: {' '.join(script.hashtags)}\n\n대본:\n" + "\n".join(script.lines) + "\n",
        encoding="utf-8")
    (out_dir / "script.txt").write_text(script.title + "\n" + "\n".join(script.lines) + "\n", encoding="utf-8")

    print(f"\n완료! {video}  (길이 약 {sum(durations):.0f}초)")
    print(f"자막 파일: {out_dir / 'subtitles.srt'}")
    print(f"업로드 정보: {out_dir / 'upload_info.txt'}")


if __name__ == "__main__":
    main()
