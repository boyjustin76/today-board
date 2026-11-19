#!/usr/bin/env python3
"""오늘 상황판 — 파일 모드 도구. 파이썬 표준 라이브러리만 쓴다(3.8 이상).

상황판 자료는 폴더 안 board-data.json 한 파일이다. 이 도구가 그 파일을 고치고,
화면(board.html)이 읽을 board-data.js도 함께 다시 쓴다.

  board.py init                         예시 자료로 board-data.json·board-data.js 만들기
  board.py list [--zone now]            카드 목록
  board.py card set <id> title=... zone=now      카드 새로 쓰기(있으면 통째로 바꿈)
  board.py card update <id> state=idle           카드의 일부만 고치기
  board.py card delete <id>
  board.py move <id> <zone>             카드를 다른 칸으로
  board.py vary <id> "KR|9:16" done     변형 표의 한 칸 상태
  board.py set-meta headline="..."      맨 위 정보 고치기
  board.py serve [--port 8765]          내 PC에서만 열리는 화면 서버(답·체크를 받음)
  board.py inbox [--ack]                화면에서 사람이 남긴 답·체크 읽기

값 넣는 법 세 가지(섞어 써도 됨):
  title="보고서 초안"        글·숫자·true/false 를 key=value 로
  --json '{"title":"…"}'    JSON 한 덩어리
  --file card.json          JSON 파일(따옴표가 꼬일 때 가장 안전)

자료 폴더는 기본이 이 도구의 윗폴더(board.html이 있는 곳)다. 바꾸려면 --dir <폴더> 또는 환경변수 BOARD_DIR.
"""
import argparse
import datetime
import json
import os
import shutil
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ZONES = ('now', 'run', 'due', 'park', 'later', 'vary', 'done')
ZONE_HELP = 'now=지금 내가 할 일 · run=에이전트가 하는 일 · due=마감 · park=내 결정 대기 · later=나중에 · vary=변형 표 · done=끝남'
EMPTY = {'meta': {'me': '', 'agent': '', 'updated': '', 'headline': '', 'projects': [{'id': 'etc', 'name': '기타', 'order': 99}]}, 'cards': {}}
STATIC = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8',
          '.css': 'text/css; charset=utf-8', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.ico': 'image/x-icon',
          '.woff2': 'font/woff2'}
MAX_BODY = 1024 * 1024


def gone(value):
    """이 값은 '그 칸을 지워라'는 뜻인가: null 또는 {"__delete__": true} (Artifact 자료의 지움 표시와 같음)."""
    return value is None or (isinstance(value, dict) and value.get('__delete__') is True and len(value) == 1)


class Board:
    def __init__(self, folder):
        self.dir = Path(folder).resolve()
        self.json = self.dir / 'board-data.json'
        self.js = self.dir / 'board-data.js'
        self.lock = self.dir / '.board.lock'
        self.inbox = self.dir / 'inbox'

    # ---- 읽기·쓰기 -------------------------------------------------------------------------
    def read(self):
        if not self.json.exists():
            sys.exit(f'자료 파일이 없습니다: {self.json}\n먼저 "board.py init"을 실행하세요.')
        for _ in range(20):                      # 다른 쪽이 바꿔치기하는 순간이면 잠깐 뒤 다시
            try:
                data = json.loads(self.json.read_text(encoding='utf-8-sig'))
                break
            except (OSError, ValueError):
                time.sleep(0.05)
        else:
            sys.exit(f'자료 파일을 읽지 못했습니다(JSON이 깨졌을 수 있음): {self.json}')
        if not isinstance(data, dict):
            sys.exit('자료 파일의 맨 바깥이 {"meta":…,"cards":…} 모양이 아닙니다.')
        data.setdefault('meta', {})
        data.setdefault('cards', {})
        return data

    def _replace(self, path, text):
        tmp = path.with_name(path.name + f'.tmp{os.getpid()}')
        tmp.write_text(text, encoding='utf-8')
        for i in range(40):                      # Windows: 누가 읽는 중이면 바꿔치기가 거부될 수 있다
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                time.sleep(0.05)
        tmp.unlink(missing_ok=True)
        raise SystemExit(f'파일을 바꾸지 못했습니다(다른 프로그램이 잡고 있음): {path}')

    def write(self, data):
        text = json.dumps(data, ensure_ascii=False, indent=1)
        self._replace(self.json, text + '\n')
        self._replace(self.js, 'window.__BOARD__ = ' + text + ';\n')

    def change(self, fn, touch=True):
        """잠그고 → 읽고 → fn(data) → 쓴다. 두 프로그램이 동시에 고쳐도 한쪽 변경이 사라지지 않는다."""
        deadline = time.time() + 10
        while True:
            try:
                fd = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                break
            except (FileExistsError, PermissionError):   # Windows: 잠금이 막 지워지는 순간에는 '권한 없음'으로 온다
                try:                              # 죽은 프로그램이 남긴 잠금(30초 넘음)은 치운다
                    if time.time() - self.lock.stat().st_mtime > 30:
                        self.lock.unlink()
                        continue
                except OSError:
                    pass
                if time.time() > deadline:
                    sys.exit('다른 프로그램이 상황판을 고치는 중입니다. 잠시 뒤 다시 하세요.')
                time.sleep(0.05)
        try:
            data = self.read()
            out = fn(data)
            if touch:
                data['meta']['updated'] = datetime.datetime.now().strftime('%H:%M')
            self.write(data)
            return out
        finally:
            try:
                self.lock.unlink()
            except OSError:
                pass


# ---- 값 읽기 ------------------------------------------------------------------------------
def parse_value(text):
    try:
        return json.loads(text)
    except ValueError:
        return text


def fields_from(args):
    out = {}
    if getattr(args, 'file', None):
        loaded = json.loads(Path(args.file).read_text(encoding='utf-8-sig'))
        if not isinstance(loaded, dict):
            sys.exit('--file 의 내용은 { } 로 싸인 JSON이어야 합니다.')
        out.update(loaded)
    if getattr(args, 'json', None):
        try:
            loaded = json.loads(args.json)
        except ValueError as exc:
            sys.exit(f'--json 을 읽지 못했습니다: {exc}\n따옴표가 꼬이면 key=value 로 쓰거나 --file 을 쓰세요.')
        if not isinstance(loaded, dict):
            sys.exit('--json 의 내용은 { } 로 싸인 JSON이어야 합니다.')
        out.update(loaded)
    for pair in getattr(args, 'pairs', None) or []:
        if '=' not in pair:
            sys.exit(f'"{pair}" 를 이해하지 못했습니다. key=value 모양으로 쓰세요(예: title="보고서 초안").')
        key, value = pair.split('=', 1)
        out[key.strip()] = parse_value(value)
    return out


def check_id(card_id):
    if not card_id or any(ch in card_id for ch in '/\\ \t"\'') or card_id.startswith('.'):
        sys.exit(f'카드 id "{card_id}" 는 쓸 수 없습니다. 영문·숫자·-·_ 로 쓰세요(예: now-report).')
    return card_id


def check_zone(zone):
    if zone not in ZONES:
        sys.exit(f'zone "{zone}" 은 없습니다. 쓸 수 있는 값: {", ".join(ZONES)}\n({ZONE_HELP})')
    return zone


# ---- 명령 ---------------------------------------------------------------------------------
def cmd_init(board, args):
    if board.json.exists() and not args.force:
        sys.exit(f'이미 자료가 있습니다: {board.json}\n지우고 새로 만들려면 --force 를 붙이세요.')
    board.dir.mkdir(parents=True, exist_ok=True)
    sample = board.dir / 'board-data.sample.json'
    if args.empty or not sample.exists():
        data = json.loads(json.dumps(EMPTY))
        note = '빈 상황판'
    else:
        data = json.loads(sample.read_text(encoding='utf-8-sig'))
        note = '예시 자료(board-data.sample.json)'
    data.setdefault('meta', {})
    data.setdefault('cards', {})
    data['meta']['updated'] = datetime.datetime.now().strftime('%H:%M')
    board.write(data)
    print(f'만들었습니다 — {note}, 카드 {len(data["cards"])}장')
    print(f'  {board.json}\n  {board.js}')
    print('다음: board.py serve  (브라우저에서 http://127.0.0.1:8765 )')


def cmd_list(board, args):
    data = board.read()
    cards = sorted(data['cards'].items(), key=lambda kv: (ZONES.index(kv[1].get('zone')) if kv[1].get('zone') in ZONES else 99, kv[1].get('order', 0), kv[0]))
    if args.zone:
        check_zone(args.zone)
        cards = [kv for kv in cards if kv[1].get('zone') == args.zone]
    if args.as_json:
        print(json.dumps({k: v for k, v in cards}, ensure_ascii=False, indent=1))
        return
    meta = data['meta']
    print(f"상황판: {meta.get('me') or '(이름 없음)'} · 갱신 {meta.get('updated') or '-'} · 카드 {len(data['cards'])}장")
    for cid, c in cards:
        mark = ''
        if c.get('checked'):
            mark += ' [체크됨]'
        if c.get('answer'):
            mark += f" [답: {c.get('answer')}]"
        print(f"  {c.get('zone', '?'):5} {cid:22} {c.get('state', ''):5} {c.get('title', '')}{mark}")
    if not cards:
        print('  (카드 없음)')


def cmd_card(board, args):
    cid = check_id(args.id)
    fields = {} if args.action == 'delete' else fields_from(args)
    if 'zone' in fields:
        check_zone(fields['zone'])

    def fn(data):
        cards = data['cards']
        if args.action == 'set':
            if not fields.get('zone'):
                sys.exit(f'새 카드에는 zone 이 있어야 합니다(예: zone=now). 쓸 수 있는 값: {", ".join(ZONES)}')
            cards[cid] = fields
            return f'카드를 썼습니다: {cid}'
        if cid not in cards:
            sys.exit(f'카드가 없습니다: {cid}\n"board.py list"로 id를 확인하세요. 새로 만들려면 "card set".')
        if args.action == 'delete':
            del cards[cid]
            return f'카드를 지웠습니다: {cid}'
        if not fields:
            sys.exit('고칠 값이 없습니다. key=value 를 하나 이상 주세요.')
        for key, value in fields.items():
            if gone(value):
                cards[cid].pop(key, None)        # key=null 이면 그 칸을 지운다
            else:
                cards[cid][key] = value
        return f'카드를 고쳤습니다: {cid} ({", ".join(fields)})'
    print(board.change(fn))


def cmd_move(board, args):
    cid, zone = check_id(args.id), check_zone(args.zone)

    def fn(data):
        if cid not in data['cards']:
            sys.exit(f'카드가 없습니다: {cid}')
        card = data['cards'][cid]
        was = card.get('zone')
        card['zone'] = zone
        if zone == 'done' and not card.get('at'):
            card['at'] = datetime.datetime.now().strftime('%H:%M')
        return f'{cid}: {was} → {zone}'
    print(board.change(fn))


def cmd_vary(board, args):
    cid = check_id(args.id)

    def fn(data):
        if cid not in data['cards']:
            sys.exit(f'카드가 없습니다: {cid}')
        card = data['cards'][cid]
        if card.get('zone') != 'vary':
            sys.exit(f'{cid} 는 변형 표 카드가 아닙니다(zone 이 vary 여야 함).')
        cells = card.setdefault('cells', {})
        if args.state in ('none', '-', ''):
            cells.pop(args.cell, None)
            return f'{cid} [{args.cell}] 비움'
        cell = cells.setdefault(args.cell, {})
        cell['state'] = args.state
        if args.note is not None:
            cell['note'] = args.note
        if args.path is not None:
            cell['path'] = args.path
        return f'{cid} [{args.cell}] = {args.state}'
    print(board.change(fn))


def cmd_set_meta(board, args):
    fields = fields_from(args)
    if not fields:
        sys.exit('고칠 값이 없습니다. 예: board.py set-meta me="내 이름" agent="비서"')

    def fn(data):
        for key, value in fields.items():
            if gone(value):
                data['meta'].pop(key, None)
            else:
                data['meta'][key] = value
        return f'맨 위 정보를 고쳤습니다: {", ".join(fields)}'
    print(board.change(fn))


def cmd_inbox(board, args):
    items = sorted(board.inbox.glob('*.json')) if board.inbox.exists() else []
    if not items:
        print('받은 답 없음')
        return
    for p in items:
        try:
            d = json.loads(p.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            print(f'  (읽지 못함) {p.name}')
            continue
        fields = d.get('fields', {})
        if args.as_json:
            print(json.dumps(d, ensure_ascii=False))
            continue
        said = []
        if 'answer' in fields:
            said.append(f"답: {fields.get('answer')}" + (f" (메모: {fields.get('answerNote')})" if fields.get('answerNote') else ''))
        elif fields.get('checked'):
            said.append('체크함')
        if not said:
            said.append(json.dumps(fields, ensure_ascii=False))
        print(f"  {d.get('at', '')}  {d.get('id', '')}  \"{d.get('title', '')}\"  → {' · '.join(said)}")
    if args.ack:
        read = board.inbox / 'read'
        read.mkdir(exist_ok=True)
        for p in items:
            os.replace(p, read / p.name)
        print(f'{len(items)}건을 읽음으로 옮겼습니다(inbox/read).')
    else:
        print(f'{len(items)}건. 처리했으면 "board.py inbox --ack".')


# ---- 서버 ---------------------------------------------------------------------------------
def make_handler(board, port):
    allowed_hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}

    class Handler(BaseHTTPRequestHandler):
        server_version = 'today-board'

        def log_message(self, fmt, *a):          # 화면 폴링(3초마다)은 찍지 않는다
            if self.command != 'GET':
                sys.stderr.write('%s %s\n' % (datetime.datetime.now().strftime('%H:%M:%S'), fmt % a))

        def _send(self, code, body, ctype='application/json; charset=utf-8'):
            raw = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(raw)

        def _local(self):
            # 다른 웹사이트가 내 PC의 상황판을 읽거나 고치지 못하게: 주소가 내 PC 이름일 때만 답한다.
            if self.headers.get('Host', '') not in allowed_hosts:
                self._send(403, {'ok': False, 'error': 'local only'})
                return False
            return True

        def do_GET(self):
            if not self._local():
                return
            path = unquote(urlparse(self.path).path)
            if path == '/api/board':
                self._send(200, board.read())
                return
            if path in ('/', ''):
                path = '/board.html'
            target = (board.dir / path.lstrip('/')).resolve()
            ok = (board.dir in target.parents and target.is_file() and target.suffix.lower() in STATIC
                  and not any(part.startswith('.') or part in ('inbox', 'tools', 'agents') for part in target.relative_to(board.dir).parts))
            if not ok:
                self._send(404, {'ok': False, 'error': 'not found'})
                return
            self._send(200, target.read_bytes(), STATIC[target.suffix.lower()])

        def do_POST(self):
            if not self._local():
                return
            origin = self.headers.get('Origin')
            if origin and urlparse(origin).netloc not in allowed_hosts:
                self._send(403, {'ok': False, 'error': 'cross-site'})
                return
            path = unquote(urlparse(self.path).path)
            if not path.startswith('/api/card/'):
                self._send(404, {'ok': False, 'error': 'not found'})
                return
            if 'application/json' not in self.headers.get('Content-Type', ''):
                self._send(415, {'ok': False, 'error': 'Content-Type must be application/json'})
                return
            cid = path[len('/api/card/'):]
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if size > MAX_BODY:
                    raise ValueError('too large')
                fields = json.loads(self.rfile.read(size).decode('utf-8'))
                if not isinstance(fields, dict) or not fields:
                    raise ValueError('body must be a non-empty JSON object')
            except (ValueError, UnicodeDecodeError) as exc:
                self._send(400, {'ok': False, 'error': str(exc)})
                return
            if fields.get('zone') is not None and fields['zone'] not in ZONES:
                self._send(400, {'ok': False, 'error': 'unknown zone'})
                return
            result = {}

            def fn(data):
                card = data['cards'].get(cid)
                if card is None:
                    return None
                for key, value in fields.items():
                    if gone(value):
                        card.pop(key, None)
                    else:
                        card[key] = value
                result['card'] = dict(card)
                return True
            try:
                found = board.change(fn, touch=False)   # 사람이 누른 것은 '에이전트 갱신 시각'을 바꾸지 않는다
            except SystemExit as exc:
                self._send(503, {'ok': False, 'error': str(exc)})
                return
            if not found:
                self._send(404, {'ok': False, 'error': f'no card {cid}'})
                return
            now = datetime.datetime.now()
            board.inbox.mkdir(exist_ok=True)
            note = {'id': cid, 'at': now.strftime('%Y-%m-%d %H:%M:%S'), 'title': result['card'].get('title', ''), 'fields': fields}
            name = now.strftime('%Y%m%d-%H%M%S-%f') + '_' + ''.join(ch if ch.isalnum() or ch in '-_' else '_' for ch in cid) + '.json'
            (board.inbox / name).write_text(json.dumps(note, ensure_ascii=False, indent=1), encoding='utf-8')
            self._send(200, {'ok': True, 'id': cid, 'card': result['card']})

    return Handler


def cmd_serve(board, args):
    board.read()                                 # 자료가 없으면 여기서 안내하고 끝난다
    if not (board.dir / 'board.html').exists():
        print(f'알림: {board.dir / "board.html"} 이 없습니다. /api/board 는 열리지만 화면은 안 뜹니다.', file=sys.stderr)
    httpd, port = None, args.port
    for port in ([args.port] if args.strict_port else range(args.port, args.port + 10)):   # 막혀 있으면 다음 번호로
        try:
            httpd = ThreadingHTTPServer(('127.0.0.1', port), make_handler(board, port))
            break
        except OSError as exc:
            last = exc
    if httpd is None:
        sys.exit(f'{args.port}번 포트를 열지 못했습니다({last}). 이미 켜져 있거나 다른 프로그램이 쓰는 중입니다. --port 8790 처럼 바꿔 보세요.')
    url = f'http://127.0.0.1:{port}'
    print(f'상황판: {url}   (이 PC에서만 열립니다. 끄려면 Ctrl+C)')
    if port != args.port:
        print(f'({args.port}번이 쓰는 중이라 {port}번으로 열었습니다)')
    print(f'자료: {board.json}')
    sys.stdout.flush()
    if args.open and not os.environ.get('BOARD_NO_OPEN'):   # BOARD_NO_OPEN=1 이면 브라우저를 열지 않는다(시험용)
        import webbrowser
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\n껐습니다.')


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dir', default=os.environ.get('BOARD_DIR') or str(Path(__file__).resolve().parent.parent), help='자료 폴더(기본: 이 도구의 윗폴더)')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('init', help='예시 자료로 시작')
    p.add_argument('--empty', action='store_true', help='예시 없이 빈 상황판으로')
    p.add_argument('--force', action='store_true', help='있는 자료를 덮어씀')
    p = sub.add_parser('list', help='카드 목록')
    p.add_argument('--zone')
    p.add_argument('--json', dest='as_json', action='store_true', help='JSON으로 출력')

    def values(parser):
        parser.add_argument('pairs', nargs='*', metavar='key=value')
        parser.add_argument('--json')
        parser.add_argument('--file')

    p = sub.add_parser('card', help='카드 쓰기·고치기·지우기')
    p.add_argument('action', choices=['set', 'update', 'delete'])
    p.add_argument('id')
    values(p)
    p = sub.add_parser('move', help='카드를 다른 칸으로')
    p.add_argument('id')
    p.add_argument('zone')
    p = sub.add_parser('vary', help='변형 표 한 칸의 상태')
    p.add_argument('id')
    p.add_argument('cell', help='예: "KR|9:16"')
    p.add_argument('state', help='예: run, done, hold. 비우려면 none')
    p.add_argument('--note')
    p.add_argument('--path')
    p = sub.add_parser('set-meta', help='맨 위 정보(me, agent, headline, projects …)')
    values(p)
    p = sub.add_parser('serve', help='내 PC 전용 화면 서버')
    p.add_argument('--port', type=int, default=8765)
    p.add_argument('--strict-port', action='store_true', help='그 포트가 막혀 있으면 다음 번호로 넘어가지 않고 끝냄')
    p.add_argument('--open', action='store_true', help='켠 뒤 브라우저로 바로 엶')
    p = sub.add_parser('inbox', help='사람이 화면에서 남긴 답·체크')
    p.add_argument('--ack', action='store_true', help='읽음 처리')
    p.add_argument('--json', dest='as_json', action='store_true', help='보낸 내용 전체를 JSON으로')

    args = ap.parse_args()
    board = Board(args.dir)
    {'init': cmd_init, 'list': cmd_list, 'card': cmd_card, 'move': cmd_move, 'vary': cmd_vary,
     'set-meta': cmd_set_meta, 'serve': cmd_serve, 'inbox': cmd_inbox}[args.cmd](board, args)


if __name__ == '__main__':
    main()
