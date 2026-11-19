#!/usr/bin/env python3
"""board.py 파일 모드 처음부터 끝까지 시험. 임시 폴더에서 돌고 끝나면 지운다(진짜 상황판은 안 건드림).

  python tools/test_board.py        → 마지막 줄이 "ALL PASS (n)" 이면 통과
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

TOOL = Path(__file__).resolve().parent / 'board.py'
PORT = 8799
passed = []


def run(folder, *args, ok=True):
    p = subprocess.run([sys.executable, '-X', 'utf8', str(TOOL), '--dir', str(folder), *args], capture_output=True, text=True, encoding='utf-8')
    if ok and p.returncode != 0:
        raise AssertionError(f'{args} failed: {p.stdout}{p.stderr}')
    return p


def data(folder):
    return json.loads((folder / 'board-data.json').read_text(encoding='utf-8'))


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    passed.append(name)
    print('ok  ', name)


def http(method, path, body=None, headers=None):
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}{path}', method=method,
                                 data=None if body is None else json.dumps(body).encode('utf-8'), headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def main():
    folder = Path(tempfile.mkdtemp(prefix='board_test_'))
    server = None
    try:
        # 1. 시작
        check('자료 없이 list 하면 init 안내', 'init' in (run(folder, 'list', ok=False).stderr))
        run(folder, 'init', '--empty')
        check('init 이 json·js 둘 다 만듦', (folder / 'board-data.json').exists() and (folder / 'board-data.js').exists())
        check('init 은 있는 자료를 덮어쓰지 않음', run(folder, 'init', ok=False).returncode != 0)
        run(folder, 'set-meta', 'me=홍길동', 'agent=비서', 'headline=오늘은 보고서 마감')
        check('set-meta', data(folder)['meta']['me'] == '홍길동')

        # 2. 카드 세 가지 방법으로 넣기
        run(folder, 'card', 'set', 'now-report', 'zone=now', 'title=보고서 초안 확인', 'proj=etc', 'order=1')
        run(folder, 'card', 'set', 'run-agent', '--json', '{"zone":"run","state":"run","title":"자료 조사 중","since":"09:10"}')
        f = folder / 'card.json'
        f.write_text(json.dumps({'zone': 'vary', 'title': '배너', 'langs': ['KR', 'EN'], 'ratios': ['9:16', '1:1'], 'cells': {}}, ensure_ascii=False), encoding='utf-8')
        run(folder, 'card', 'set', 'vary-banner', '--file', str(f))
        d = data(folder)
        check('카드 3장(key=value · --json · --file)', set(d['cards']) == {'now-report', 'run-agent', 'vary-banner'})
        check('숫자는 숫자로, 글은 글로', d['cards']['now-report']['order'] == 1 and d['cards']['now-report']['title'] == '보고서 초안 확인')
        check('zone 없는 새 카드는 거절', run(folder, 'card', 'set', 'x', 'title=없음', ok=False).returncode != 0)
        check('없는 zone 은 거절', run(folder, 'card', 'set', 'x', 'zone=todo', ok=False).returncode != 0)

        # 3. 고치기·옮기기·변형·지우기
        run(folder, 'card', 'update', 'run-agent', 'state=idle', 'title=대기 — 자료 조사 끝', 'since=null')
        c = data(folder)['cards']['run-agent']
        check('update 는 일부만 고치고 null 은 칸을 지움', c['state'] == 'idle' and 'since' not in c and c['zone'] == 'run')
        check('없는 카드 update 는 거절', run(folder, 'card', 'update', 'nope', 'a=1', ok=False).returncode != 0)
        run(folder, 'vary', 'vary-banner', 'KR|9:16', 'done', '--note', '확인함')
        run(folder, 'vary', 'vary-banner', 'EN|1:1', 'run')
        run(folder, 'vary', 'vary-banner', 'EN|1:1', 'none')
        cells = data(folder)['cards']['vary-banner']['cells']
        check('vary 칸 쓰기·비우기', cells == {'KR|9:16': {'state': 'done', 'note': '확인함'}})
        check('vary 가 아닌 카드에는 거절', run(folder, 'vary', 'now-report', 'KR|9:16', 'done', ok=False).returncode != 0)
        js = (folder / 'board-data.js').read_text(encoding='utf-8')
        check('js 파일이 json 과 같은 내용', js.startswith('window.__BOARD__ = ') and json.loads(js[len('window.__BOARD__ = '):].rstrip().rstrip(';')) == data(folder))
        check('갱신 시각이 자동으로 찍힘', len(data(folder)['meta']['updated']) == 5)

        # 4. 동시에 고쳐도 안 사라짐
        with ThreadPoolExecutor(8) as ex:
            list(ex.map(lambda i: run(folder, 'card', 'set', f'c{i}', 'zone=later', f'title=동시 {i}'), range(16)))
        d = data(folder)
        check('동시에 16장 넣어도 모두 남음', sum(1 for k in d['cards'] if k.startswith('c')) == 16)
        check('list 출력', 'now-report' in run(folder, 'list').stdout and 'c3' in run(folder, 'list', '--zone', 'later').stdout)

        # 5. 서버
        (folder / 'board.html').write_text('<!doctype html><title>t</title>board', encoding='utf-8')
        server = subprocess.Popen([sys.executable, '-X', 'utf8', str(TOOL), '--dir', str(folder), 'serve', '--port', str(PORT)],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                http('GET', '/api/board')
                break
            except OSError:
                time.sleep(0.1)
        code, body, head = http('GET', '/api/board')
        check('GET /api/board', code == 200 and json.loads(body)['cards']['now-report']['zone'] == 'now' and head.get('Cache-Control') == 'no-store')
        check('GET / 는 board.html', http('GET', '/')[1].endswith(b'board'))
        check('도구·받은함·숨김 파일은 안 줌', http('GET', '/inbox/x.json')[0] == 404 and http('GET', '/../board-data.json')[0] in (200, 404) and http('GET', '/tools/board.py')[0] == 404)
        J = {'Content-Type': 'application/json'}
        code, body, _ = http('POST', '/api/card/now-report', {'checked': True, 'checkedAt': '10:30', 'answer': 'OK', 'order': {'__delete__': True}}, J)
        r = json.loads(body)
        check('POST 로 체크·답', code == 200 and r['ok'] and r['card']['checked'] is True and 'order' not in r['card'])
        check('파일에 반영됨', data(folder)['cards']['now-report']['answer'] == 'OK')
        check('한글 id 도 됨', run(folder, 'card', 'set', '할일-1', 'zone=now', 'title=한글 id') and http('POST', '/api/card/%ED%95%A0%EC%9D%BC-1', {'checked': True}, J)[0] == 200)
        run(folder, 'set-meta', 'headline=서버 시험')                 # 이때 갱신 시각이 찍힌다
        raw = data(folder); raw['meta']['updated'] = '00:00'          # 표식으로 바꿔 두고, 사람이 눌러도 그대로인지 본다
        (folder / 'board-data.json').write_text(json.dumps(raw, ensure_ascii=False), encoding='utf-8')
        http('POST', '/api/card/now-report', {'seenAt': '10:31'}, J)
        check('없는 카드는 404', http('POST', '/api/card/nope', {'checked': True}, J)[0] == 404)
        check('JSON 이 아니면 415', http('POST', '/api/card/now-report', {'a': 1}, {'Content-Type': 'text/plain'})[0] == 415)
        check('다른 사이트에서 온 요청은 403', http('POST', '/api/card/now-report', {'a': 1}, {**J, 'Origin': 'https://example.com'})[0] == 403)
        check('주소가 내 PC 가 아니면 403', http('GET', '/api/board', headers={'Host': 'evil.example:8799'})[0] == 403)
        check('사람이 누른 것은 갱신 시각을 안 바꿈', data(folder)['meta']['updated'] == '00:00')

        # 6. 받은함
        out = run(folder, 'inbox').stdout
        check('inbox 에 3건', 'now-report' in out and '3건' in out)
        note = json.loads(sorted((folder / 'inbox').glob('*.json'))[0].read_text(encoding='utf-8'))
        check('inbox 한 장의 모양', set(note) >= {'id', 'at', 'fields'} and note['fields']['answer'] == 'OK')
        run(folder, 'inbox', '--ack')
        check('ack 뒤 비어 있음', '없음' in run(folder, 'inbox').stdout and len(list((folder / 'inbox' / 'read').glob('*.json'))) == 3)
        run(folder, 'move', 'now-report', 'done')
        run(folder, 'card', 'delete', 'c0')
        d = data(folder)
        check('move·delete', d['cards']['now-report']['zone'] == 'done' and d['cards']['now-report'].get('at') and 'c0' not in d['cards'])
        check('잠금 파일이 남지 않음', not (folder / '.board.lock').exists())
        print(f'ALL PASS ({len(passed)})')
    finally:
        if server:
            server.terminate()
            server.wait(timeout=5)
        shutil.rmtree(folder, ignore_errors=True)


if __name__ == '__main__':
    main()
