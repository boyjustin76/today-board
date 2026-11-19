# 오늘 상황판 — 에이전트 지침 (Codex · GPT · 그 밖의 에이전트용)

이 조각을 프로젝트의 `AGENTS.md`에 붙여 넣으세요. 상황판은 **사람이 "지금 내가 할 일이 뭐지?"를 한눈에 보는 화면**이고, 채우는 것은 당신(에이전트)입니다. 자료는 `board-data.json` 한 파일이며, 직접 편집하지 말고 반드시 아래 `board` 명령으로 고칩니다(두 파일을 함께 쓰고, 동시에 고쳐도 깨지지 않게 해 줍니다).

**상황판 폴더: `<여기에 today-board 폴더를 둔 곳을 적으세요>`**

아래에서 `board`는 이렇게 부릅니다. 어느 폴더에서 불러도 됩니다(도구가 자기가 놓인 폴더를 기준으로 자료를 찾습니다).

| | `board` = |
|---|---|
| Windows | `<상황판 폴더>\board.cmd` — 이 PC에 파이썬이 없으면 처음 한 번 전용 파이썬을 폴더 안(`tools\python`)에 내려받습니다. 설치·관리자 권한 없음 |
| macOS · Linux | `python3 <상황판 폴더>/tools/board.py` (파이썬 3.8 이상) |

이 지침과 카드에는 특정 PC의 절대 경로(`C:\…`, `/Users/…`)를 적지 말고, 카드의 `path`는 프로젝트 폴더 기준 상대 경로로 씁니다.

## 처음 한 번 (상황판이 아직 없을 때)
```
board init --empty                       # 빈 상황판. 예시를 보고 싶으면 --empty 없이
board set-meta me="사용자 이름" agent="내 이름(예: 비서)"
board card set run-me zone=run state=idle title="대기" who="내 이름"     # 내 카드 한 장을 만들어 둠
board serve                              # 터미널 하나를 차지합니다. 따로 띄워 두세요
```
- 사용자가 `start.bat`(또는 `start.sh`)으로 이미 켰다면 `init`과 `serve`는 건너뜁니다. 예시 자료가 들어 있으면 `board init --empty --force`로 비웁니다.
- `serve`가 찍어 주는 주소(보통 `http://127.0.0.1:8765`)를 사용자에게 알려 줍니다. 그 PC에서만 열립니다.
- 8765번이 쓰는 중이면 다음 번호로 저절로 엽니다. 번호를 정하려면 `board serve --port 8772`. 끄려면 그 터미널에서 Ctrl+C.
- 들어갔는지 확인: `board list`, 또는 브라우저·`curl`로 `http://127.0.0.1:8765/api/board`.

## 언제 고치나 — 시키지 않아도, 답을 쓰기 전에
| 때 | 할 일 |
|---|---|
| 일을 받은 즉시 | 내 `run` 카드를 "하는 중"으로 |
| 사용자에게 물을 것·봐 달라고 할 것이 생긴 즉시 | `now`(지금 해 줄 일) 또는 `park`(결정 대기) 카드를 만들고, 채팅에도 같은 말을 씀 |
| 일을 끝낸 즉시 | 내 `run` 카드를 "대기"로, 결과 경로를 적음 |
| 막힌 즉시 | 내 `run` 카드를 `state=stop`으로, 무엇이 필요한지 `now` 카드로 |
| 매 턴 시작할 때 | `board inbox`로 사용자가 화면에서 남긴 답·체크를 읽음 |

## 카드 = 한 줄짜리 일 하나
카드마다 `id`(영문·숫자·`-`)와 `zone`(어느 칸)이 있습니다.

| zone | 뜻 | 꼭 넣을 것 | 자주 쓰는 것 |
|---|---|---|---|
| `now` | **사용자가 지금 할 일** (확인·승인·파일 주기) | `title`, `kind`, `at`(올린 HH:MM) | `impact`(안 하면 무엇이 멈추나), `detail`(덧붙일 말), `effort`(걸리는 시간, 예: 3분), `options`(답 고르기), `path`(볼 파일), `order` |
| `park` | 급하지 않은 결정 대기 | `title`, `ask`(물음 한 문장) | `detail`, `options`, `effort` |
| `run` | 에이전트가 하는 일 (에이전트마다 한 장) | `title`, `state`, `who`(에이전트 이름 — 화면에는 이름과 상태 점이 보이고 제목은 마우스를 올려야 보입니다) | `since`(시작 HH:MM), `path`(결과) |
| `due` | 마감 | `title`, `date`(YYYY-MM-DD) | `time`(HH:MM), `mine`(사용자 몫) |
| `later` | 나중에 할 일 | `title` | `when`, `detail`, `said`(사용자가 한 말) |
| `vary` | 변형 표(언어×크기처럼 칸이 많은 일) | `title`, `langs`, `ratios` | `cells`, `branch`(갈래 이름) |
| `done` | 끝난 일 | `title` | `at`(끝난 HH:MM, `move`가 자동으로 넣음) |

- `now` 카드의 `kind`: `click`(눌러 주기·해 주기 — ✓만) · `look`(봐 주기) · `decide`(고르기) · `answer`(답 쓰기). **답 버튼은 `look`·`decide`·`answer`일 때만 나옵니다.** `options`를 줬다면 `kind`를 꼭 넣습니다.
- `run` 카드의 `state`: `run`(하는 중) · `idle`(쉼 — 일이 없을 때) · `wait`(사용자·다른 일을 기다림) · `stop`(막힘).
- `vary` 칸의 `state`: `make`(만드는 중) · `look`(봐 주세요) · `ok`(승인) · `redo`(다시) · `up`(올림·끝). 없으면 시작 전.
- `proj`에 프로젝트 id를 넣으면 프로젝트별로 묶여 보입니다. 프로젝트 목록은 `meta.projects`(`[{"id":"a","name":"…","order":1}]`)에 있습니다. 모르면 `etc`.
- 칸의 전체 목록과 화면에서의 쓰임은 `docs/data.md`에 있습니다.

## 명령
```
board list                                   # 지금 카드 전부
board card set now-review zone=now title="보고서 초안 확인" impact="확인돼야 인쇄 넘김" path="out/report.pdf"
board card update run-me state=run title="표 3 다시 계산 중" since=14:05
board card update run-me state=idle title="대기 — 표 3 끝" path="out/table3.csv"
board card set due-report zone=due title="보고서" date=2030-01-31 mine="초안 확인"
board move now-review done                   # 끝난 카드를 '끝남'으로
board vary vary-banner "KO|9:16" look        # 변형 표 한 칸 (칸 이름은 "언어|크기")
board set-meta headline="오늘은 보고서 마감"
board inbox                                  # 사용자가 화면에서 남긴 답·체크
board inbox --ack                            # 처리했으면 읽음으로
board card update <id> seenAt=HH:MM          # 답을 읽었다고 화면에 표시(보냄 → 읽음)
```
- 값은 `key=value`로 씁니다. 숫자·`true`·`false`는 그대로, 나머지는 글로 들어갑니다. `key=null`은 그 칸을 지웁니다.
- 값에 빈칸이 있으면 따옴표로 쌉니다. PowerShell에서는 `'title=보고서 초안 확인'`처럼 전체를 작은따옴표로 싸면 안전합니다.
- 따옴표가 꼬이면 JSON을 파일에 쓰고 `--file card.json`을 쓰세요. `--json '{…}'`도 됩니다.
- **`card set`은 카드를 통째로 바꿉니다.** 있는 카드를 고칠 때는 `card update`만 씁니다. 사용자의 답(`answer`, `checked` …)이 지워지지 않게 하기 위해서입니다.
- 실패하면 이유와 다음에 할 일을 알려 줍니다. 그 말대로 하세요.

## 지킬 것
1. 사용자가 남긴 칸(`checked`, `answer`로 시작하는 칸)은 고치지 않습니다. 읽고 그에 따라 일합니다.
2. `now` 카드는 **사용자가 해야만 하는 것**만. 에이전트 혼자 할 수 있는 일을 올리지 않습니다. 제목은 한 줄, 무엇을 하면 되는지가 보이게.
3. 사용자가 답한 `now`·`park` 카드는 처리한 뒤 `board move <id> done`.
4. 내 `run` 카드는 한 장만 두고 계속 고쳐 씁니다(일마다 새로 만들지 않음).
5. 비밀번호·토큰·개인 정보는 카드에 쓰지 않습니다.
6. `board-data.json`, `board-data.js`, `inbox/`를 손으로 고치지 않습니다.
