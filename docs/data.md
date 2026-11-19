# 상황판 자료 모양

화면(`board.html`)은 자료 두 가지만 읽습니다.
- **meta** 한 장: 내 이름, 하루 시간, 프로젝트 목록, 달력 표시
- **cards** 여러 장: 할 일·마감·끝난 일·에이전트 상태 등. 한 장이 한 줄

| 쓰는 길 | 자료가 있는 곳 |
|---|---|
| Claude (Artifact) | Artifact 자료: `meta/board` 한 장 + `cards/<id>` 여러 장 |
| 파일 방식 (`tools/board.py`) | `board-data.json` = `{"meta": {...}, "cards": {"<id>": {...}}}` |

- 카드 id는 영문·숫자·`-`로 짧게 씁니다(예: `now-banner-look`).
- 모르는 칸은 화면이 무시하니 메모용 칸을 더 넣어도 됩니다.
- 예시 전체는 `board-data.sample.json`에 있습니다.

## 날짜·시각 쓰는 법
- 날짜는 `YYYY-MM-DD`, 시각은 `HH:MM`(24시간)으로 씁니다.
- 예시 자료처럼 **여는 날·시각 기준**으로도 쓸 수 있습니다.
  - 날짜: `today`, `today+1`, `today-3`. 적용 칸: `date`, `by`, `answerDate`, `meta.cal[].date`
  - 시각: `now`, `now-25`(25분 전). 적용 칸: `at`, `since`, `checkedAt`, `answeredAt`, `eta`, `meta.updated`

## meta

| 칸 | 뜻 | 예 |
|---|---|---|
| `me` | 화면에 나오는 내 이름 | `"민지"` |
| `agent` | 에이전트를 부르는 이름(제안·알림 글에 씀) | `"비서"` |
| `headline` | 맨 아래 한 줄 요약 | `"여름 이벤트 영상 마무리 중"` |
| `updated` | 에이전트가 마지막으로 고친 시각 | `"10:30"` |
| `day` | 근무 시간. '퇴근까지 n시간'에 씀 | `{"start":"09:00","end":"18:00"}` |
| `projects` | 프로젝트 목록(아래) | |
| `cal` | 월 달력에 찍을 점 `[{date, label, kind}]`. kind = `done`(끝, 초록) · `plan`(예정, 노랑). 마감(빨강)은 `due` 카드에서 자동 | `[{"date":"today+6","label":"시작","kind":"plan"}]` |

### projects 한 항목
| 칸 | 뜻 |
|---|---|
| `id` | 카드의 `proj`가 가리키는 이름. `etc`는 '기타'로 늘 맨 아래 |
| `name` | 화면에 나오는 이름(짧게) |
| `order` | 위에서부터 순서 |
| `when` | 이름 옆 노란 표시(예: `"다음 주"`) |
| `past` | `true`면 맨 아래 접힌 '지난 업무'로. 빨강·마감 표시 없음 |
| `tag` | 지난 업무 머리에 붙는 짧은 글(예: `"납품 끝"`) |
| `note` | 지난 업무를 펼치면 나오는 한 줄 |

## cards — 모든 카드에 공통
| 칸 | 뜻 |
|---|---|
| `zone` | 어느 칸에 놓이나(아래 표). 꼭 씀 |
| `proj` | 프로젝트 `id`. 없거나 모르는 값이면 '기타' |
| `title` | 한 줄 제목. 꼭 씀 |
| `order` | 같은 칸 안에서의 순서 |
| `detail` | 한 줄 설명 |
| `path` | 결과 파일·폴더 경로. '경로 복사' 버튼이 생김 |

### zone별
| zone | 화면에서 | 주로 쓰는 칸 |
|---|---|---|
| `now` | 맨 위 **지금 내가 할 일**. ✓를 누르면 `checked:true, checkedAt` | `kind`(`click` 버튼 · `decide` 결정 · `look` 확인 · `answer` 답), `at`(언제부터 기다렸나), `effort`(걸리는 시간), `waiting`(누가 기다리나), `impact`('안 하면 →' 한 줄), `by`(언제까지), `for`(이어진 `due` 카드 id), `options`(답 선택지) |
| `park` | 프로젝트 안 **정할 것**(질문) | `ask`(질문 문장), `options`, `effort`, `impact` |
| `due` | 프로젝트 **마감**. 내일까지면 프로젝트 상자가 빨강 | `date`, `mine`(내 몫), `mineDone` |
| `done` | **오늘 끝난 일** | `at` |
| `run` | **에이전트 상태**(누가 무엇을 하는 중) | `who`, `state`(`run` 진행 · `wait` 대기 · `stop` 막힘 · `idle` 쉼), `since`, `needsMe`(true면 정할 것으로 올라옴), `toMe`·`eta`(나한테 올 것과 시각 — 시간표에 표시) |
| `later` | **나중에 할 것**. `when`이 있으면 '다음 주 할 것' 묶음(펼쳐진 채) | `when`, `said`(내가 했던 말 그대로) |
| `vary` | **변형 표**: 언어 × 사이즈 격자. 프로젝트 이름 옆 작은 격자, 펼치면 큰 격자 | `branch`(가지 이름, 예: `A안`), `langs`, `ratios`, `cells` |

### vary의 cells
- `cells`는 `"언어|사이즈"`를 열쇠로 씁니다. 예: `{"KO|9:16": {"state": "ok", "note": "…", "path": "…"}}`
- state와 칸 색:
  - 초록: `up` 업로드됨 · `ok` 승인
  - 빨강: `look` 내 확인 대기. 비어 있으면 시작 전으로 보고 연한 빨강
  - 노랑: `make` 제작 중 · `redo` 다시 만들기
- 칸에 `note`가 있으면 점이 찍히고, 누르면 그 메모가 한 줄 나옵니다.

## 화면이 쓰는 칸(사람이 누른 것)
화면은 카드의 **일부 칸만** 고칩니다(부분 병합).

| 누른 것 | 고치는 칸 |
|---|---|
| ✓ | `checked: true`, `checkedAt: "HH:MM"` |
| 답 보내기 | `answer`(고른 것, 기타면 `"기타"`), `answerNote`(메모), `answeredAt`, `answerDate`, `answerAsk`(그때 질문), `answerOptions`(그때 보인 선택지 전부), `answerLog`(고칠 때마다 한 줄씩 쌓임), `answerNotified`. `now` 카드는 `checked`·`checkedAt`도 같이 |

- `answerNotified`는 에이전트에게 알렸는지를 남깁니다.
  - Claude 방식: `claude`(Artifact 댓글로 보냄) 또는 `no`
  - 파일 방식: `inbox`(서버가 `inbox/`에 한 장 남김)
- 에이전트가 답을 읽었으면 그 카드에 `seenAt: "HH:MM"`을 써 주세요. 화면에 '○○ 읽음'으로 바뀝니다.
- 지나간 일(`done`, 체크된 `now`)에 답이 있으면, 그때 선택지와 고른 답·메모를 읽기 전용으로 보여 줍니다. 그러니 카드를 `done`으로 옮길 때 `answer…` 칸을 지우지 마세요.

## 파일 방식의 길(서버 `tools/board.py serve`)
- `GET /api/board` → `board-data.json` 그대로. 화면이 3초마다 읽습니다.
- `POST /api/card/<id>`
  - 본문: 고칠 칸만 담은 JSON. 값이 `{"__delete__": true}` 또는 `null`이면 그 칸을 지웁니다.
  - 응답: `{"ok": true, "id", "card"}`. 없는 id면 404이고, 새 카드는 만들지 못합니다.
  - 받을 때마다 `inbox/<시각>_<id>.json`이 한 장 생깁니다: `{"id", "at", "title", "fields"}`.
- 서버 없이 `board.html`을 바로 열면 `board-data.js`(`window.__BOARD__ = {...};`)를 5초마다 다시 읽습니다. 이때는 보기만 할 수 있습니다.
