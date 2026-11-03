# 쇼츠 자동 생성기

주제 하나만 넣으면 **대본 → 음성 → 자막 → 세로 쇼츠 영상(mp4)** 까지 자동으로 만들어 줍니다.

```
python make_short.py "블랙홀에 대한 놀라운 사실"
```

| 단계 | 사용하는 것 | 비용 |
|---|---|---|
| 대본 작성 | Claude API | 유료 (영상 1개당 몇십 원 수준) |
| 음성(TTS) | edge-tts (Microsoft 무료 음성) | 무료 |
| 배경 | 자동 그라데이션 / 내 이미지 폴더 / Pexels 무료 사진 | 무료 |
| 자막 + 영상 합치기 | Pillow + ffmpeg | 무료 |

결과물 (`output/<제목>/` 폴더):

- `short.mp4`: 완성된 1080x1920 쇼츠 영상
- `subtitles.srt`: 자막 파일
- `upload_info.txt`: 업로드할 때 쓸 제목, 설명, 해시태그
- `script.txt`: 대본 (고쳐서 `--script` 로 다시 만들 수 있음)

---

## 1. 설치 (Windows 기준, 처음 한 번만)

1. **Python 설치**: https://www.python.org/downloads/ 에서 설치합니다.
   설치 첫 화면에서 **"Add python.exe to PATH"** 를 꼭 체크하세요.
2. **이 저장소 받기**: GitHub에서 `Code → Download ZIP` 으로 받아 압축을 풀거나, `git clone` 합니다.
3. **PowerShell 에서 폴더로 이동한 뒤 패키지 설치**:

```powershell
cd 압축푼폴더경로
pip install -r requirements.txt
```

ffmpeg는 `imageio-ffmpeg` 패키지가 자동으로 받아오므로 따로 설치할 필요가 없습니다.

## 2. Claude API 키 설정

1. https://console.anthropic.com 에서 API 키를 만듭니다 (결제 수단 등록 필요).
2. PowerShell 에서 아래처럼 등록합니다 (한 번 하면 계속 유지됨). 등록 후 **PowerShell 을 새로 열어야** 적용됩니다.

```powershell
setx ANTHROPIC_API_KEY "sk-ant-여기에키붙여넣기"
```

> API 키가 없어도 됩니다. 대본을 직접 쓰거나 Claude Code 에게 써 달라고 한 뒤 `--script` 로 넣으면 됩니다. (아래 "대본 직접 넣기" 참고)

## 3. 영상 만들기

```powershell
python make_short.py "블랙홀에 대한 놀라운 사실"
```

자주 쓰는 옵션:

```powershell
# 남자 목소리, 조금 더 빠르게
python make_short.py "커피의 역사" --voice ko-KR-InJoonNeural --rate +20%

# 내 이미지 폴더를 배경으로 + 배경음악
python make_short.py "제주도 여행 꿀팁" --images C:\사진\제주 --bgm C:\음악\bgm.mp3

# 문장 수 조절 (기본 8문장, 약 30~40초)
python make_short.py "고양이 상식" --lines 12

# 영어 쇼츠
python make_short.py "fun facts about octopus" --language English --voice en-US-AriaNeural
```

| 옵션 | 설명 |
|---|---|
| `--voice` | 목소리. 한국어: `ko-KR-SunHiNeural`(여, 기본), `ko-KR-InJoonNeural`(남), `ko-KR-HyunsuMultilingualNeural`(남) |
| `--rate` | 말하기 속도. 예: `+0%`, `+10%`(기본), `+25%` |
| `--lines` | 대본 문장 수 (기본 8) |
| `--language` | 대본 언어 (기본 한국어) |
| `--images` | 배경으로 쓸 이미지 폴더 (장면마다 순서대로 사용) |
| `--bgm` / `--bgm-volume` | 배경음악 파일 / 볼륨 (기본 0.12) |
| `--script` | 직접 쓴 대본 파일 사용 (API 키 불필요) |
| `--font` | 자막 폰트 파일 (기본: 맑은 고딕 Bold) |
| `--out` | 결과 폴더 (기본 `output`) |
| `--tts silent` | 음성 없이 빠르게 화면만 테스트 |

### 배경 사진 자동으로 넣기 (선택, 무료)

https://www.pexels.com/api/ 에서 무료 API 키를 받아 등록하면, 각 문장에 어울리는 사진을 자동으로 찾아 배경으로 씁니다.

```powershell
setx PEXELS_API_KEY "여기에키붙여넣기"
```

키가 없으면 색 그라데이션 배경이 자동으로 들어갑니다.

### 대본 직접 넣기

텍스트 파일의 **첫 줄은 제목, 다음 줄부터 한 줄에 한 문장**씩 씁니다. (예: `examples/sample_script.txt`)

```
블랙홀의 비밀
지금 이 순간에도 우주에는 빛조차 빠져나올 수 없는 곳이 있습니다.
바로 블랙홀입니다.
...
```

```powershell
python make_short.py --script examples/sample_script.txt
```

Claude Code 를 쓰고 있다면 이렇게 부탁하면 됩니다:
> "'커피의 역사' 주제로 쇼츠 대본을 my_script.txt 에 써줘. 첫 줄은 제목, 다음 줄부터 한 문장씩. 그리고 make_short.py --script 로 영상까지 만들어줘."

---

## 여러 개 한 번에 만들기

`topics.txt` 에 주제를 한 줄에 하나씩 적고 PowerShell 에서:

```powershell
Get-Content topics.txt -Encoding UTF8 | ForEach-Object { python make_short.py $_ }
```

## 문제 해결

- **`python` 을 찾을 수 없음**: Python 설치 때 "Add to PATH" 를 체크했는지 확인하고 PowerShell 을 새로 여세요.
- **음성 생성 실패**: edge-tts 는 인터넷 연결이 필요합니다. 회사망 등에서 막혀 있으면 다른 네트워크에서 시도하세요.
- **자막 글자가 네모(□)로 보임**: `--font` 로 한글 폰트(.ttf) 경로를 지정하세요.
- **ANTHROPIC_API_KEY 오류**: `setx` 후 PowerShell 을 새로 열었는지 확인하세요.
