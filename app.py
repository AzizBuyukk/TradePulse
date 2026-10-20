"""TradePulse masaüstü uygulaması.

Çalıştırmak için: TradePulse.bat (veya: python app.py)
- Arayüz: web/index.html
- Veriler: SQL Server (ayarlar config.ini)
- Ekran görüntüleri: data/images

Pencere: pywebview kuruluysa kendi penceresi açılır; değilse Microsoft Edge
"uygulama modu"nda (adres çubuğu olmadan) açılır.
"""
import base64
import json
import mimetypes
import os
import secrets
import shutil
import subprocess
import sys
import threading
import time
import traceback
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

from db import SAFE_FILE, Database

# exe olarak paketlenince program dosyaları geçici klasörde, veriler exe'nin yanında durur
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
    RES_DIR = getattr(sys, "_MEIPASS", BASE_DIR)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    RES_DIR = BASE_DIR

WEB_DIR = os.path.join(RES_DIR, "web")
DATA_DIR = os.path.join(BASE_DIR, "data")
IMG_DIR = os.path.join(DATA_DIR, "images")
IMPORT_DIR = os.path.join(DATA_DIR, "import")
CONFIG_PATH = os.path.join(BASE_DIR, "config.ini")
LOG_PATH = os.path.join(DATA_DIR, "hata.log")
os.makedirs(IMG_DIR, exist_ok=True)

IMAGE_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}
MAX_IMAGE_BYTES = 25 * 1024 * 1024
TOKEN = secrets.token_urlsafe(16)
LAST_PING = [0.0]


def log_error(where):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} {where}\n{traceback.format_exc()}\n")
    except OSError:
        pass


# ---------------- arayüzün çağırdığı işlemler ----------------
class Api:
    METHODS = {"status", "set_server", "list_trades", "save_trade", "delete_trade",
               "save_image", "open_images_folder", "ping"}

    def __init__(self):
        self._db = None
        self._error = None
        self._lock = threading.Lock()
        self._connect()

    def _connect(self, server=None):
        try:
            if self._db is None:
                self._db = Database(CONFIG_PATH)
            if server is not None:
                self._db.set_server(server)
            else:
                self._db.connect()
            self._error = None
            self._import_old_data()
            self._cleanup_images()
        except Exception as e:
            log_error("connect")
            self._error = str(e)

    @staticmethod
    def _fail(e, where):
        log_error(where)
        return {"ok": False, "error": str(e)}

    def ping(self):
        LAST_PING[0] = time.time()
        return {"ok": True}

    def status(self):
        info = self._db.info() if self._db else {}
        if self._error:
            return {"ok": False, "error": self._error, **info}
        return {"ok": True, **info}

    def set_server(self, server):
        with self._lock:
            self._connect(server or "auto")
        return self.status()

    def list_trades(self):
        if self._error:
            return {"ok": False, "error": self._error}
        try:
            with self._lock:
                return {"ok": True, "trades": self._db.list_trades()}
        except Exception as e:
            return self._fail(e, "list_trades")

    def save_trade(self, trade):
        try:
            with self._lock:
                before = self._db.image_files(trade.get("id"))
                self._db.save_trade(trade)
                still_used = self._db.image_files()
            for fn in before - still_used:
                self._remove_image(fn)
            return {"ok": True}
        except Exception as e:
            return self._fail(e, "save_trade")

    def delete_trade(self, trade_id):
        try:
            with self._lock:
                files = self._db.image_files(trade_id)
                self._db.delete_trade(trade_id)
                still_used = self._db.image_files()
            for fn in files - still_used:
                self._remove_image(fn)
            return {"ok": True}
        except Exception as e:
            return self._fail(e, "delete_trade")

    def save_image(self, data_url):
        try:
            head, _, b64 = str(data_url).partition(",")
            mime = head[5:].split(";")[0] if head.startswith("data:") else ""
            ext = IMAGE_TYPES.get(mime)
            if not ext or not b64:
                return {"ok": False, "error": "Bu görsel türü desteklenmiyor (PNG, JPG, WEBP, GIF)."}
            raw = base64.b64decode(b64)
            if len(raw) > MAX_IMAGE_BYTES:
                return {"ok": False, "error": "Görsel 25 MB'tan büyük."}
            name = uuid.uuid4().hex + ext
            with open(os.path.join(IMG_DIR, name), "wb") as f:
                f.write(raw)
            return {"ok": True, "file": name}
        except Exception as e:
            return self._fail(e, "save_image")

    def open_images_folder(self):
        try:
            os.startfile(IMG_DIR)  # yalnızca Windows
            return {"ok": True}
        except Exception as e:
            return self._fail(e, "open_images_folder")

    # ---- yardımcılar ----
    @staticmethod
    def _remove_image(fn):
        if SAFE_FILE.match(fn):
            try:
                os.remove(os.path.join(IMG_DIR, fn))
            except OSError:
                pass

    def _cleanup_images(self):
        """Hiçbir işleme bağlı olmayan ve 1 günden eski görselleri siler (form iptal edilince kalanlar)."""
        used = self._db.image_files()
        for fn in os.listdir(IMG_DIR):
            full = os.path.join(IMG_DIR, fn)
            if fn not in used and os.path.isfile(full) and time.time() - os.path.getmtime(full) > 86400:
                self._remove_image(fn)

    def _import_old_data(self):
        """data/import/trades.json varsa (web sürümünden gelen işlemler) bir kez içe aktarır."""
        src = os.path.join(IMPORT_DIR, "trades.json")
        if not os.path.isfile(src):
            return
        with open(src, encoding="utf-8") as f:
            items = json.load(f)
        for t in items:
            if self._db.trade_exists(t["id"]):
                continue
            for key in ("htf", "ltf"):
                files = []
                for asset_id in t.get(key) or []:
                    old = os.path.join(IMPORT_DIR, "images", f"{asset_id}.png")
                    if os.path.isfile(old):
                        new = f"{asset_id}.png"
                        shutil.copyfile(old, os.path.join(IMG_DIR, new))
                        files.append(new)
                t[key] = files
            t.pop("example", None)
            self._db.save_trade(t)
        os.replace(src, os.path.join(IMPORT_DIR, "trades.imported.json"))


API = None


# ---------------- yerel web sunucusu (arayüz + görseller + API) ----------------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path.startswith("/_img/"):
            name = path[len("/_img/"):]
            full = os.path.join(IMG_DIR, name)
            if not SAFE_FILE.match(name) or not os.path.isfile(full):
                return self.send_error(404)
        else:
            rel = "index.html" if path in ("", "/") else path.lstrip("/")
            full = os.path.normpath(os.path.join(WEB_DIR, rel))
            if not full.startswith(os.path.normpath(WEB_DIR)) or not os.path.isfile(full):
                return self.send_error(404)
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            self._send(200, f.read(), ctype)

    def do_POST(self):
        path = urlparse(self.path).path
        name = path[len("/api/"):] if path.startswith("/api/") else ""
        if self.headers.get("X-Token") != TOKEN or name not in Api.METHODS:
            return self.send_error(403)
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length) or b"{}")
            result = getattr(API, name)(*payload.get("args", []))
        except Exception as e:
            log_error(f"api {name}")
            result = {"ok": False, "error": str(e)}
        self._send(200, json.dumps(result, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")


def start_server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1]


# ---------------- pencere ----------------
def find_edge():
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
        if base:
            p = os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe")
            if os.path.isfile(p):
                return p
    return shutil.which("msedge")


def open_window(url):
    try:
        import webview  # pywebview
        webview.create_window("TradePulse", url, width=1440, height=900, min_size=(960, 640),
                              background_color="#13142a")
        webview.start(private_mode=False, storage_path=os.path.join(DATA_DIR, "webview"))
        return
    except ImportError:
        pass
    except Exception:
        log_error("pywebview")

    edge = find_edge()
    if edge:
        profile = os.path.join(DATA_DIR, "edge-profile")
        proc = subprocess.Popen([edge, f"--app={url}", f"--user-data-dir={profile}",
                                 "--window-size=1440,900", "--no-first-run", "--no-default-browser-check"])
        proc.wait()
        # Edge bazen pencereyi başka bir sürece devreder; pencere açık kaldıkça bekle
        wait_for_pings()
        return

    webbrowser.open(url)
    wait_for_pings()


def wait_for_pings():
    """Sayfa her 10 sn'de bir haber verir; 30 sn haber gelmezse pencere kapanmış sayılır."""
    start = time.time()
    while True:
        time.sleep(5)
        last = LAST_PING[0] or start
        if time.time() - last > 30:
            return


def main():
    global API
    API = Api()
    port = start_server()
    open_window(f"http://127.0.0.1:{port}/?t={TOKEN}")


if __name__ == "__main__":
    main()
