"""TradePulse - SQL Server veritabanı katmanı.

Bağlantı ayarları config.ini dosyasındadır. server = auto ise sırayla
localhost, localhost\\SQLEXPRESS ve (localdb)\\MSSQLLocalDB denenir ve
çalışan sunucu config.ini'ye yazılır.
"""
import configparser
import datetime as dt
import re
from decimal import Decimal, InvalidOperation

import pyodbc

CANDIDATE_SERVERS = ["localhost", r"localhost\SQLEXPRESS", r".\SQLEXPRESS", r"(localdb)\MSSQLLocalDB"]

SCHEMA = [
    """
    IF OBJECT_ID(N'dbo.Trades', N'U') IS NULL
    CREATE TABLE dbo.Trades (
        Id             NVARCHAR(40)   NOT NULL PRIMARY KEY,
        TradeDate      DATE           NOT NULL,
        TradeTime      NVARCHAR(5)    NULL,
        Session        NVARCHAR(40)   NULL,
        Instrument     NVARCHAR(30)   NULL,
        Direction      NVARCHAR(5)    NULL,
        Kind           NVARCHAR(10)   NULL,
        EntryPrice     DECIMAL(19,6)  NULL,
        StopPrice      DECIMAL(19,6)  NULL,
        TargetPrice    DECIMAL(19,6)  NULL,
        ExitPrice      DECIMAL(19,6)  NULL,
        RiskUsd        DECIMAL(19,4)  NULL,
        RiskPct        DECIMAL(9,4)   NULL,
        PnlUsd         DECIMAL(19,4)  NULL,
        RMultiple      DECIMAL(12,4)  NULL,
        Result         NVARCHAR(10)   NULL,
        RulesScore     TINYINT        NULL,
        EmoIn          NVARCHAR(40)   NULL,
        EmoInNote      NVARCHAR(MAX)  NULL,
        EmoDuring      NVARCHAR(40)   NULL,
        EmoDuringNote  NVARCHAR(MAX)  NULL,
        EmoAfter       NVARCHAR(40)   NULL,
        EmoAfterNote   NVARCHAR(MAX)  NULL,
        Notes          NVARCHAR(MAX)  NULL,
        Lesson         NVARCHAR(MAX)  NULL,
        CreatedAt      DATETIME2      NOT NULL DEFAULT SYSDATETIME(),
        UpdatedAt      DATETIME2      NOT NULL DEFAULT SYSDATETIME()
    )
    """,
    """
    IF OBJECT_ID(N'dbo.TradeTags', N'U') IS NULL
    CREATE TABLE dbo.TradeTags (
        TradeId  NVARCHAR(40) NOT NULL REFERENCES dbo.Trades(Id) ON DELETE CASCADE,
        TagType  NVARCHAR(10) NOT NULL,   -- 'setup' veya 'mistake'
        Name     NVARCHAR(60) NOT NULL,
        PRIMARY KEY (TradeId, TagType, Name)
    )
    """,
    """
    IF OBJECT_ID(N'dbo.TradeImages', N'U') IS NULL
    CREATE TABLE dbo.TradeImages (
        Id         INT IDENTITY(1,1) PRIMARY KEY,
        TradeId    NVARCHAR(40)  NOT NULL REFERENCES dbo.Trades(Id) ON DELETE CASCADE,
        Timeframe  NVARCHAR(3)   NOT NULL,   -- 'HTF' veya 'LTF'
        FileName   NVARCHAR(200) NOT NULL,
        SortOrder  INT           NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE OR ALTER VIEW dbo.vTradeSummary AS
    SELECT t.Id, t.TradeDate, t.TradeTime, t.Session, t.Instrument, t.Direction, t.Kind,
           t.EntryPrice, t.StopPrice, t.TargetPrice, t.ExitPrice, t.RiskUsd,
           r.R,
           COALESCE(t.PnlUsd, r.R * t.RiskUsd) AS PnlUsd,
           COALESCE(NULLIF(t.Result, N'auto'),
                    CASE WHEN r.R > 0.05 THEN N'Win' WHEN r.R < -0.05 THEN N'Loss'
                         WHEN r.R IS NOT NULL THEN N'BE' END) AS Result,
           t.EmoIn, t.EmoDuring, t.EmoAfter, t.RulesScore
    FROM dbo.Trades t
    CROSS APPLY (SELECT COALESCE(t.RMultiple,
        CASE WHEN t.EntryPrice IS NOT NULL AND t.StopPrice IS NOT NULL AND t.ExitPrice IS NOT NULL
                  AND t.EntryPrice <> t.StopPrice
             THEN (CASE WHEN t.Direction = N'Short' THEN t.EntryPrice - t.ExitPrice
                        ELSE t.ExitPrice - t.EntryPrice END) / ABS(t.EntryPrice - t.StopPrice)
        END) AS R) r
    """,
]

NUM_FIELDS = {  # arayüz alanı -> SQL kolonu
    "entry": "EntryPrice", "stop": "StopPrice", "target": "TargetPrice", "exit": "ExitPrice",
    "riskUsd": "RiskUsd", "riskPct": "RiskPct", "pnl": "PnlUsd", "r": "RMultiple",
}
TEXT_FIELDS = {
    "time": "TradeTime", "session": "Session", "instrument": "Instrument", "direction": "Direction",
    "kind": "Kind", "result": "Result", "emoIn": "EmoIn", "emoInNote": "EmoInNote",
    "emoDuring": "EmoDuring", "emoDuringNote": "EmoDuringNote", "emoAfter": "EmoAfter",
    "emoAfterNote": "EmoAfterNote", "notes": "Notes", "lesson": "Lesson",
}
SAFE_FILE = re.compile(r"^[A-Za-z0-9_.-]{1,200}$")


def _num(v):
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v).replace(",", ".").strip())
    except InvalidOperation:
        return None


def _num_str(d):
    if d is None:
        return ""
    return format(Decimal(d).normalize(), "f")


class Database:
    def __init__(self, config_path):
        self.config_path = config_path
        self.cfg = configparser.ConfigParser()
        self.cfg.read(config_path, encoding="utf-8")
        if not self.cfg.has_section("sqlserver"):
            self.cfg["sqlserver"] = {}
        s = self.cfg["sqlserver"]
        self.server = s.get("server", "auto").strip() or "auto"
        self.database = s.get("database", "TradePulse").strip() or "TradePulse"
        if not re.fullmatch(r"[A-Za-z0-9_]{1,100}", self.database):
            raise ValueError("config.ini içindeki database adı sadece harf, rakam ve _ içermeli.")
        self.user = s.get("user", "").strip()
        self.password = s.get("password", "")
        self.driver = s.get("driver", "").strip() or self.pick_driver()
        self.conn = None

    # ---------- bağlantı ----------
    @staticmethod
    def pick_driver():
        drivers = pyodbc.drivers()
        numbered = []
        for d in drivers:
            m = re.match(r"ODBC Driver (\d+) for SQL Server", d)
            if m:
                numbered.append((int(m.group(1)), d))
        if numbered:
            return max(numbered)[1]
        for d in ("SQL Server Native Client 11.0", "SQL Server"):
            if d in drivers:
                return d
        return "ODBC Driver 18 for SQL Server"

    def _conn_str(self, server, database):
        parts = [f"DRIVER={{{self.driver}}}", f"SERVER={server}", f"DATABASE={database}"]
        if self.user:
            parts += [f"UID={self.user}", f"PWD={self.password}"]
        else:
            parts.append("Trusted_Connection=yes")
        if self.driver.startswith("ODBC Driver"):
            parts.append("TrustServerCertificate=yes")
        return ";".join(parts) + ";"

    def _try(self, server, database, timeout=4):
        return pyodbc.connect(self._conn_str(server, database), timeout=timeout, autocommit=True)

    def connect(self):
        """Sunucuya bağlanır, veritabanını ve tabloları gerekirse oluşturur."""
        servers = CANDIDATE_SERVERS if self.server.lower() == "auto" else [self.server]
        errors = []
        master = None
        for srv in servers:
            try:
                master = self._try(srv, "master")
                self.server = srv
                break
            except pyodbc.Error as e:
                errors.append(f"{srv}: {e.args[-1] if e.args else e}")
        if master is None:
            raise ConnectionError("SQL Server'a bağlanılamadı.\n" + "\n".join(errors))
        cur = master.cursor()
        cur.execute(f"IF DB_ID(?) IS NULL CREATE DATABASE [{self.database}]", self.database)
        master.close()
        self.conn = self._try(self.server, self.database, timeout=10)
        self.conn.autocommit = False
        cur = self.conn.cursor()
        for stmt in SCHEMA:
            cur.execute(stmt)
        self.conn.commit()
        self._save_config()

    def _save_config(self):
        s = self.cfg["sqlserver"]
        s["server"] = self.server
        s["database"] = self.database
        s["driver"] = self.driver
        s.setdefault("user", self.user)
        s.setdefault("password", self.password)
        with open(self.config_path, "w", encoding="utf-8") as f:
            self.cfg.write(f)

    def set_server(self, server):
        self.server = server.strip() or "auto"
        self.connect()

    def info(self):
        return {"server": self.server, "database": self.database, "driver": self.driver}

    # ---------- okuma ----------
    def list_trades(self):
        cur = self.conn.cursor()
        cols = ["Id", "TradeDate", "RulesScore", "CreatedAt"] + list(NUM_FIELDS.values()) + list(TEXT_FIELDS.values())
        cur.execute(f"SELECT {', '.join(cols)} FROM dbo.Trades")
        trades = {}
        for row in cur.fetchall():
            r = dict(zip(cols, row))
            t = {"id": r["Id"], "date": r["TradeDate"].isoformat() if r["TradeDate"] else "",
                 "rules": int(r["RulesScore"] or 0),
                 "createdAt": int(r["CreatedAt"].timestamp() * 1000) if r["CreatedAt"] else 0,
                 "setups": [], "mistakes": [], "htf": [], "ltf": []}
            for k, c in NUM_FIELDS.items():
                t[k] = _num_str(r[c])
            for k, c in TEXT_FIELDS.items():
                t[k] = r[c] or ""
            if not t["result"]:
                t["result"] = "auto"
            trades[t["id"]] = t
        cur.execute("SELECT TradeId, TagType, Name FROM dbo.TradeTags ORDER BY Name")
        for tid, typ, name in cur.fetchall():
            if tid in trades:
                trades[tid]["setups" if typ == "setup" else "mistakes"].append(name)
        cur.execute("SELECT TradeId, Timeframe, FileName FROM dbo.TradeImages ORDER BY SortOrder, Id")
        for tid, tf, fn in cur.fetchall():
            if tid in trades:
                trades[tid]["htf" if tf == "HTF" else "ltf"].append(fn)
        self.conn.commit()
        return list(trades.values())

    def image_files(self, trade_id=None):
        cur = self.conn.cursor()
        if trade_id:
            cur.execute("SELECT FileName FROM dbo.TradeImages WHERE TradeId = ?", trade_id)
        else:
            cur.execute("SELECT FileName FROM dbo.TradeImages")
        files = {r[0] for r in cur.fetchall()}
        self.conn.commit()
        return files

    def trade_exists(self, trade_id):
        cur = self.conn.cursor()
        cur.execute("SELECT 1 FROM dbo.Trades WHERE Id = ?", trade_id)
        found = cur.fetchone() is not None
        self.conn.commit()
        return found

    # ---------- yazma ----------
    def save_trade(self, t):
        tid = str(t.get("id") or "").strip()
        if not tid or len(tid) > 40:
            raise ValueError("Geçersiz işlem kimliği.")
        try:
            trade_date = dt.date.fromisoformat(str(t.get("date")))
        except ValueError:
            raise ValueError("Tarih geçersiz.")
        values = {"TradeDate": trade_date}
        for k, c in NUM_FIELDS.items():
            values[c] = _num(t.get(k))
        for k, c in TEXT_FIELDS.items():
            v = t.get(k)
            values[c] = None if v in (None, "") else str(v)
        rules = int(t.get("rules") or 0)
        values["RulesScore"] = rules if 1 <= rules <= 5 else None
        created = t.get("createdAt")
        created_dt = dt.datetime.fromtimestamp(created / 1000) if isinstance(created, (int, float)) and created > 0 else dt.datetime.now()

        cur = self.conn.cursor()
        try:
            cur.execute("SELECT 1 FROM dbo.Trades WHERE Id = ?", tid)
            if cur.fetchone():
                sets = ", ".join(f"{c} = ?" for c in values) + ", UpdatedAt = SYSDATETIME()"
                cur.execute(f"UPDATE dbo.Trades SET {sets} WHERE Id = ?", *values.values(), tid)
            else:
                cols = ["Id"] + list(values) + ["CreatedAt"]
                cur.execute(f"INSERT INTO dbo.Trades ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                            tid, *values.values(), created_dt)
            cur.execute("DELETE FROM dbo.TradeTags WHERE TradeId = ?", tid)
            for typ, key in (("setup", "setups"), ("mistake", "mistakes")):
                seen = set()
                for name in (str(n).strip()[:60] for n in (t.get(key) or [])):
                    if not name or name.casefold() in seen:
                        continue
                    seen.add(name.casefold())
                    cur.execute("INSERT INTO dbo.TradeTags (TradeId, TagType, Name) VALUES (?, ?, ?)", tid, typ, name)
            cur.execute("DELETE FROM dbo.TradeImages WHERE TradeId = ?", tid)
            for tf, key in (("HTF", "htf"), ("LTF", "ltf")):
                for i, fn in enumerate(t.get(key) or []):
                    if SAFE_FILE.match(str(fn)):
                        cur.execute("INSERT INTO dbo.TradeImages (TradeId, Timeframe, FileName, SortOrder) VALUES (?, ?, ?, ?)",
                                    tid, tf, str(fn), i)
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def delete_trade(self, trade_id):
        cur = self.conn.cursor()
        try:
            cur.execute("DELETE FROM dbo.Trades WHERE Id = ?", trade_id)
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
