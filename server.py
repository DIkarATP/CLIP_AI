import json, os, time, urllib.parse, urllib.request, urllib.error, threading, subprocess, sys, shutil
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
RECORDINGS = ROOT / 'recordings'
SOURCES_FILE = DATA / 'sources.json'
DATA.mkdir(exist_ok=True)
RECORDINGS.mkdir(exist_ok=True)

def load_env():
    p = ROOT / '.env'
    if not p.exists(): return
    for raw in p.read_text(encoding='utf-8-sig').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line: continue
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
load_env()
CLIENT_ID = os.getenv('TWITCH_CLIENT_ID', '').strip()
CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET', '').strip()
_token = None
_token_expiry = 0
worker_lock = threading.RLock()
worker_running = False
worker_thread = None
active_recordings = {}
source_runtime = {}
worker_events = []


def event(message, level='info'):
    item = {'time': datetime.now().astimezone().isoformat(timespec='seconds'), 'message': message, 'level': level}
    with worker_lock:
        worker_events.insert(0, item)
        del worker_events[100:]
    print('[CLIP AI]', message, flush=True)


def read_sources():
    try:
        data = json.loads(SOURCES_FILE.read_text(encoding='utf-8'))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def write_sources(items):
    tmp = SOURCES_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(SOURCES_FILE)


def get_token():
    global _token, _token_expiry
    if _token and time.time() < _token_expiry - 60: return _token
    if not CLIENT_ID or not CLIENT_SECRET: raise RuntimeError('Заполни TWITCH_CLIENT_ID и TWITCH_CLIENT_SECRET в .env')
    data = urllib.parse.urlencode({'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 'grant_type': 'client_credentials'}).encode()
    req = urllib.request.Request('https://id.twitch.tv/oauth2/token', data=data, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=20) as r: payload = json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'Twitch OAuth HTTP {e.code}: {e.read().decode("utf-8", "replace")[:400]}')
    _token = payload['access_token']; _token_expiry = time.time() + int(payload.get('expires_in', 3600))
    return _token


def twitch_get(path, params=None):
    token = get_token(); url = 'https://api.twitch.tv/helix/' + path
    if params: url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'Client-ID': CLIENT_ID, 'Authorization': 'Bearer ' + token, 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=25) as r: return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'Twitch API HTTP {e.code}: {e.read().decode("utf-8", "replace")[:400]}')


def twitch_login(url):
    try:
        u = urllib.parse.urlparse(url)
        if not (u.hostname or '').lower().endswith('twitch.tv'): return None
        parts = [p for p in u.path.split('/') if p]
        if not parts: return None
        reserved = {'videos', 'directory', 'downloads', 'p', 'settings', 'subscriptions', 'inventory'}
        return parts[0].lower() if parts[0].lower() not in reserved else None
    except Exception: return None


def tool_status():
    try:
        import streamlink
        streamlink_ok = True
        streamlink_version = getattr(streamlink, '__version__', 'installed')
    except Exception:
        streamlink_ok = False; streamlink_version = None
    try:
        import yt_dlp
        ytdlp_ok = True
    except Exception:
        ytdlp_ok = False
    return {'streamlink': streamlink_ok, 'streamlink_version': streamlink_version, 'yt_dlp': ytdlp_ok, 'ffmpeg': bool(shutil.which('ffmpeg'))}


def launch_recording(source, login):
    safe_login = ''.join(c for c in login if c.isalnum() or c in '_-')
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    outfile = RECORDINGS / f'{safe_login}_{stamp}.ts'
    cmd = [sys.executable, '-m', 'streamlink', '--output', str(outfile), f'https://www.twitch.tv/{safe_login}', 'best']
    try:
        proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        with worker_lock:
            active_recordings[source['id']] = {'process': proc, 'file': str(outfile), 'login': safe_login, 'started_at': datetime.now().astimezone().isoformat(timespec='seconds')}
            source_runtime.setdefault(source['id'], {}).update({'status': 'recording', 'last_message': 'Запись LIVE началась', 'last_seen': datetime.now().astimezone().isoformat(timespec='seconds')})
        event(f'Началась запись Twitch LIVE: {safe_login}')
    except Exception as e:
        source_runtime.setdefault(source['id'], {}).update({'status': 'error', 'last_message': str(e)})
        event(f'Не удалось начать запись {safe_login}: {e}', 'error')


def monitor_loop():
    global worker_running
    event('Фоновый мониторинг запущен')
    while True:
        with worker_lock:
            if not worker_running: break
        try:
            sources = read_sources()
            for source in sources:
                with worker_lock:
                    if not worker_running: break
                if source.get('platform') != 'Twitch': continue
                if not (source.get('authorized') and source.get('enabled')): continue
                login = twitch_login(source.get('url', ''))
                if not login:
                    source_runtime.setdefault(source['id'], {}).update({'status': 'invalid', 'last_message': 'Не удалось определить Twitch-логин'})
                    continue
                existing = active_recordings.get(source['id'])
                if existing and existing['process'].poll() is not None:
                    code = existing['process'].returncode
                    with worker_lock: active_recordings.pop(source['id'], None)
                    source_runtime.setdefault(source['id'], {}).update({'status': 'saved' if Path(existing['file']).exists() and Path(existing['file']).stat().st_size > 0 else 'offline', 'last_message': f'Процесс записи завершился (код {code})', 'last_file': existing['file']})
                    event(f'Запись завершена: {login} · {Path(existing["file"]).name}')
                    existing = None
                try:
                    live = twitch_get('streams', {'user_login': login, 'first': 1}).get('data', [])
                    if live:
                        if existing is None:
                            if not tool_status()['streamlink']:
                                source_runtime.setdefault(source['id'], {}).update({'status': 'needs_setup', 'last_message': 'Установи зависимости через setup.bat'})
                            else:
                                launch_recording(source, login)
                        else:
                            source_runtime.setdefault(source['id'], {}).update({'status': 'recording', 'last_message': 'Эфир идёт, запись активна'})
                    else:
                        if existing is None:
                            source_runtime.setdefault(source['id'], {}).update({'status': 'offline', 'last_message': 'Сейчас канал не в эфире'})
                except Exception as e:
                    source_runtime.setdefault(source['id'], {}).update({'status': 'error', 'last_message': str(e)[:250]})
                    event(f'Ошибка мониторинга {login}: {e}', 'error')
        except Exception as e:
            event(f'Ошибка фонового цикла: {e}', 'error')
        for _ in range(30):
            with worker_lock:
                if not worker_running: break
            time.sleep(1)
    event('Фоновый мониторинг остановлен')


def start_worker():
    global worker_running, worker_thread
    with worker_lock:
        if worker_running: return
        worker_running = True
        worker_thread = threading.Thread(target=monitor_loop, daemon=True)
        worker_thread.start()


def stop_worker():
    global worker_running
    with worker_lock:
        worker_running = False
        procs = list(active_recordings.items())
    for sid, info in procs:
        try: info['process'].terminate()
        except Exception: pass
        source_runtime.setdefault(sid, {}).update({'status': 'stopped', 'last_message': 'Запись остановлена пользователем'})
    event('Получена команда остановки мониторинга')


class Handler(BaseHTTPRequestHandler):
    def send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code); self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*'); self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization'); self.send_header('Access-Control-Allow-Private-Network', 'true')
        self.send_header('Vary', 'Origin'); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
    def read_json(self):
        n = int(self.headers.get('Content-Length', '0') or 0)
        return json.loads(self.rfile.read(n).decode('utf-8')) if n else {}
    def do_OPTIONS(self): self.send_json(200, {'ok': True})
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path); path = parsed.path
        if path in ('/', '/index.html'):
            app = ROOT / 'index.html'
            if not app.exists(): return self.send_json(404, {'ok': False, 'message': 'index.html не найден'})
            body = app.read_bytes(); self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8'); self.send_header('Content-Length', str(len(body))); self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(body); return
        if path == '/api/health': return self.send_json(200, {'ok': True, 'service': 'CLIP AI Local Worker', 'credentials_configured': bool(CLIENT_ID and CLIENT_SECRET), 'tools': tool_status()})
        if path == '/api/twitch/status':
            try: get_token(); return self.send_json(200, {'ok': True, 'connected': True, 'message': 'Twitch API подключён. App access token получен.'})
            except Exception as e: return self.send_json(400, {'ok': False, 'connected': False, 'message': str(e)})
        if path == '/api/twitch/streams':
            qs = urllib.parse.parse_qs(parsed.query); params = {'first': min(max(int(qs.get('first', ['10'])[0]), 1), 100)}
            if qs.get('user_login'): params['user_login'] = qs['user_login'][0]
            if qs.get('game_id'): params['game_id'] = qs['game_id'][0]
            try:
                data = twitch_get('streams', params); return self.send_json(200, {'ok': True, 'data': data.get('data', []), 'pagination': data.get('pagination', {})})
            except Exception as e: return self.send_json(400, {'ok': False, 'message': str(e)})
        if path == '/api/sources': return self.send_json(200, {'ok': True, 'data': read_sources()})
        if path == '/api/worker/status':
            with worker_lock:
                active = [{'source_id': sid, 'login': v['login'], 'file': v['file'], 'started_at': v['started_at']} for sid, v in active_recordings.items() if v['process'].poll() is None]
                runtime = dict(source_runtime); events = list(worker_events[:20]); running = worker_running
            recs = sorted([{'name': p.name, 'size': p.stat().st_size, 'modified': datetime.fromtimestamp(p.stat().st_mtime).astimezone().isoformat(timespec='seconds')} for p in RECORDINGS.glob('*') if p.is_file()], key=lambda x:x['modified'], reverse=True)[:20]
            return self.send_json(200, {'ok': True, 'running': running, 'tools': tool_status(), 'active_recordings': active, 'runtime': runtime, 'events': events, 'recordings': recs, 'recordings_dir': str(RECORDINGS)})
        return self.send_json(404, {'ok': False, 'message': 'Not found'})
    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        try: data = self.read_json()
        except Exception: return self.send_json(400, {'ok': False, 'message': 'Некорректный JSON'})
        if path == '/api/sources':
            items = read_sources(); url = str(data.get('url','')).strip(); platform = str(data.get('platform','Twitch'))
            if not url.startswith(('https://','http://')): return self.send_json(400, {'ok': False, 'message': 'Некорректная ссылка'})
            if any(x.get('url','').lower() == url.lower() for x in items): return self.send_json(200, {'ok': True, 'data': items, 'message': 'Источник уже существует'})
            item = {'id': str(data.get('id') or ('src_'+str(int(time.time()*1000)))), 'url': url, 'platform': platform, 'mode': str(data.get('mode','LIVE + VOD')), 'target': max(1,min(50,int(data.get('target',15)))), 'label': str(data.get('label') or url), 'addedAt': data.get('addedAt') or datetime.now(timezone.utc).isoformat(), 'authorized': bool(data.get('authorized', False)), 'enabled': bool(data.get('enabled', False))}
            items.insert(0,item); write_sources(items); return self.send_json(200, {'ok': True, 'data': items, 'message': 'Источник сохранён на сервере'})
        if path == '/api/worker/start':
            start_worker(); return self.send_json(200, {'ok': True, 'running': True, 'message': 'Мониторинг запущен'})
        if path == '/api/worker/stop':
            stop_worker(); return self.send_json(200, {'ok': True, 'running': False, 'message': 'Мониторинг остановлен'})
        return self.send_json(404, {'ok': False, 'message': 'Not found'})
    def do_PATCH(self):
        path = urllib.parse.urlparse(self.path).path
        try: data = self.read_json()
        except Exception: return self.send_json(400, {'ok': False, 'message': 'Некорректный JSON'})
        if path.startswith('/api/sources/'):
            sid = urllib.parse.unquote(path.split('/')[-1]); items = read_sources(); found = False
            for item in items:
                if item.get('id') == sid:
                    item['authorized'] = bool(data.get('authorized', item.get('authorized', False)))
                    item['enabled'] = bool(data.get('enabled', item.get('enabled', False))) and item['authorized']
                    found = True; break
            if not found: return self.send_json(404, {'ok': False, 'message': 'Источник не найден'})
            write_sources(items); return self.send_json(200, {'ok': True, 'data': items})
        return self.send_json(404, {'ok': False, 'message': 'Not found'})
    def do_DELETE(self):
        path = urllib.parse.urlparse(self.path).path
        if path.startswith('/api/sources/'):
            sid = urllib.parse.unquote(path.split('/')[-1]); items = [x for x in read_sources() if x.get('id') != sid]; write_sources(items)
            info = active_recordings.pop(sid, None)
            if info:
                try: info['process'].terminate()
                except Exception: pass
            source_runtime.pop(sid, None); return self.send_json(200, {'ok': True, 'data': items})
        return self.send_json(404, {'ok': False, 'message': 'Not found'})
    def log_message(self, fmt, *args): print('[CLIP AI]', fmt % args, flush=True)

if __name__ == '__main__':
    print('CLIP AI Local Worker: http://127.0.0.1:8765', flush=True)
    print('Twitch status: http://127.0.0.1:8765/api/twitch/status', flush=True)
    print('Worker status: http://127.0.0.1:8765/api/worker/status', flush=True)
    start_worker()  # автоматически запускает мониторинг разрешённых источников при старте сервера
    ThreadingHTTPServer(('127.0.0.1', 8765), Handler).serve_forever()
