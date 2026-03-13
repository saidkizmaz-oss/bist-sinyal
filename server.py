#!/usr/bin/env python3
“””
BIST Sinyal Sistemi v3.0
Kullanım: python3 server.py
“””

import sqlite3, json, os, threading, webbrowser, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta

try:
import yfinance as yf
VERI_MODU = “gercek”
except ImportError:
VERI_MODU = “demo”
print(“⚠️  pip install yfinance pandas numpy”)

DB_PATH = os.path.join(os.path.dirname(**file**), “bist.db”)
PORT = int(os.environ.get(“PORT”, 8765))

# ── SEMBOL LİSTELERİ ───────────────────────────────────────────

BIST100 = [
“THYAO”,“GARAN”,“AKBNK”,“YKBNK”,“EREGL”,“ASELS”,“SISE”,“KCHOL”,
“SAHOL”,“BIMAS”,“TCELL”,“TUPRS”,“PETKM”,“KRDMD”,“FROTO”,“TOASO”,
“ARCLK”,“TTKOM”,“ISCTR”,“VAKBN”,“HALKB”,“MGROS”,“OTKAR”,“PGSUS”,
“LOGO”,“ENKAI”,“EKGYO”,“TAVHL”,“AGHOL”,“DOHOL”,“ULKER”,“SASA”,
“ALARK”,“VESTL”,“AEFES”,“CCOLA”,“BRISA”,“AKSEN”,“ALFAS”,“ALCTL”,
“ANACM”,“ATAGY”,“ATAKP”,“AVISA”,“BAGFS”,“BANVT”,“BERA”,“BIOEN”,
“BIZIM”,“BMELV”,“BMEKS”,“BNTAS”,“BOSSA”,“BRKO”,“BRYAT”,“BUCIM”,
“BURCE”,“BURVA”,“CANTE”,“CARFA”,“CEMAS”,“CEMTS”,“CIMSA”,“CLEBI”,
“CMBTN”,“CMENT”,“COKAS”,“COSMO”,“DENGE”,“DESA”,“DEVA”,“DGATE”,
“DOAS”,“DOGUB”,“DURDO”,“DYOBY”,“ECILC”,“ECZYT”,“EGEEN”,“EGPRO”,
“EKGYO”,“ELITE”,“EMKEL”,“EMNIS”,“ENJSA”,“ERBOS”,“EREGL”,“ERSU”,
“ESCOM”,“EUPWR”,“EUREN”,“FENER”,“FLAP”,“FMIZP”,“FONET”,“FORMT”,
“FRIGO”,“GARFA”,“GEDZA”,“GENIL”,“GENTS”,“GEREL”,“GLBMD”,“GLRYH”,
“GMTAS”,“GOKNR”,“GOLTS”,“GOZDE”,“GRSEL”,“GSDDE”,“GSDHO”,“GSRAY”,
]

# Tekrar eden ve hatalı olanları temizle, 100’e tamamla

BIST100 = list(dict.fromkeys(BIST100))[:100]

EMTIALAR = {
“ALTIN”:    “GC=F”,
“GUMUS”:    “SI=F”,
“PETROL”:   “CL=F”,
“BRENT”:    “BZ=F”,
“DOGALGAZ”: “NG=F”,
“BAKIR”:    “HG=F”,
“PLATIN”:   “PL=F”,
}

DOVIZLER = {
“USDTRY”: “USDTRY=X”,
“EURTRY”: “EURTRY=X”,
“GBPTRY”: “GBPTRY=X”,
“EURUSD”: “EURUSD=X”,
}

KRIPTOLAR = {
“BITCOIN”:  “BTC-USD”,
“ETHEREUM”: “ETH-USD”,
“BNB”:      “BNB-USD”,
}

TUM_SEMBOLLER = {}
for s in BIST100:
TUM_SEMBOLLER[s] = {“yahoo”: s + “.IS”, “tip”: “hisse”, “para”: “TL”}
for isim, yahoo in EMTIALAR.items():
TUM_SEMBOLLER[isim] = {“yahoo”: yahoo, “tip”: “emtia”, “para”: “USD”}
for isim, yahoo in DOVIZLER.items():
TUM_SEMBOLLER[isim] = {“yahoo”: yahoo, “tip”: “doviz”, “para”: “TL”}
for isim, yahoo in KRIPTOLAR.items():
TUM_SEMBOLLER[isim] = {“yahoo”: yahoo, “tip”: “kripto”, “para”: “USD”}

# ── VERİTABANI ─────────────────────────────────────────────────

def init_db():
con = sqlite3.connect(DB_PATH)
c = con.cursor()
c.execute(””“CREATE TABLE IF NOT EXISTS hisse_cache (
sembol TEXT PRIMARY KEY, tip TEXT, fiyat REAL, degisim REAL,
ema20 REAL, ema50 REAL, rsi REAL, hacim_guclu INTEGER,
sinyal TEXT, sinyal_saati TEXT, stop_loss REAL, hedef1 REAL, hedef2 REAL,
onceki_sinyal TEXT, guncelleme TEXT)”””)
c.execute(””“CREATE TABLE IF NOT EXISTS performans_cache (
sembol TEXT, periyot TEXT, degisim REAL, guncelleme TEXT,
PRIMARY KEY (sembol, periyot))”””)
c.execute(””“CREATE TABLE IF NOT EXISTS stratejiler (
id INTEGER PRIMARY KEY AUTOINCREMENT,
isim TEXT UNIQUE, kod TEXT, aciklama TEXT, olusturma TEXT)”””)
c.execute(””“CREATE TABLE IF NOT EXISTS backtest_sonuc (
sembol TEXT, strateji TEXT, net_kar REAL, basari_oran REAL,
profit_factor REAL, max_dd REAL, islem_sayisi INTEGER,
skor INTEGER, guncelleme TEXT,
PRIMARY KEY (sembol, strateji))”””)
c.execute(””“CREATE TABLE IF NOT EXISTS trade_gunlugu (
id INTEGER PRIMARY KEY AUTOINCREMENT,
sembol TEXT, yon TEXT, giris REAL, cikis REAL,
lot INTEGER, kar_zarar REAL, tarih TEXT, notlar TEXT)”””)
c.execute(””“CREATE TABLE IF NOT EXISTS portfoy (
sembol TEXT PRIMARY KEY, lot INTEGER, ort_maliyet REAL,
giris_tarihi TEXT, stop_loss REAL, hedef REAL, notlar TEXT)”””)

```
# Varsayılan strateji ekle
c.execute("""INSERT OR IGNORE INTO stratejiler (isim, kod, aciklama, olusturma) VALUES (?,?,?,?)""",
    ("EMA_RSI_Hacim", json.dumps({
        "ema_kisa": 20, "ema_uzun": 50, "rsi_alt": 38, "rsi_ust": 68,
        "hacim_carpan": 1.3, "stop_p": 4.0, "tp_p": 8.0
    }), "Varsayılan: EMA Cross + RSI + Hacim filtresi", datetime.now().strftime("%Y-%m-%d")))
c.execute("""INSERT OR IGNORE INTO stratejiler (isim, kod, aciklama, olusturma) VALUES (?,?,?,?)""",
    ("RSI_Dönüş", json.dumps({
        "ema_kisa": 14, "ema_uzun": 28, "rsi_alt": 30, "rsi_ust": 70,
        "hacim_carpan": 1.0, "stop_p": 5.0, "tp_p": 10.0
    }), "RSI aşırı satımdan dönüş stratejisi", datetime.now().strftime("%Y-%m-%d")))
c.execute("""INSERT OR IGNORE INTO stratejiler (isim, kod, aciklama, olusturma) VALUES (?,?,?,?)""",
    ("Agresif_Momentum", json.dumps({
        "ema_kisa": 9, "ema_uzun": 21, "rsi_alt": 45, "rsi_ust": 75,
        "hacim_carpan": 1.5, "stop_p": 3.0, "tp_p": 6.0
    }), "Kısa EMA + güçlü hacim momentum stratejisi", datetime.now().strftime("%Y-%m-%d")))

con.commit()
con.close()
```

def get_db():
return sqlite3.connect(DB_PATH)

# ── TEKNİK ANALİZ ──────────────────────────────────────────────

def calc_ema(prices, period):
if len(prices) < period:
return [None] * len(prices)
k = 2 / (period + 1)
res = [None] * (period - 1)
res.append(sum(prices[:period]) / period)
for p in prices[period:]:
res.append(p * k + res[-1] * (1 - k))
return res

def calc_rsi(prices, period=14):
if len(prices) < period + 1:
return [50.0] * len(prices)
deltas = [prices[i+1] - prices[i] for i in range(len(prices)-1)]
gains  = [max(d, 0) for d in deltas]
losses = [abs(min(d, 0)) for d in deltas]
avg_g  = sum(gains[:period]) / period
avg_l  = sum(losses[:period]) / period
result = [None] * period
for i in range(period, len(deltas)):
avg_g = (avg_g * (period-1) + gains[i]) / period
avg_l = (avg_l * (period-1) + losses[i]) / period
rs = avg_g / avg_l if avg_l else 100
result.append(100 - 100 / (1 + rs))
result.append(result[-1] or 50)
return result

def analiz(closes, volumes, params=None):
if params is None:
params = {“ema_kisa”: 20, “ema_uzun”: 50, “rsi_alt”: 38, “rsi_ust”: 68, “hacim_carpan”: 1.3, “stop_p”: 4.0, “tp_p”: 8.0}
ek = params.get(“ema_kisa”, 20)
eu = params.get(“ema_uzun”, 50)
if len(closes) < eu + 5:
return None
e20 = calc_ema(closes, ek)
e50 = calc_ema(closes, eu)
rsi_vals = calc_rsi(closes)
vol_ort  = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else 1
v20  = next((v for v in reversed(e20) if v), None)
v50  = next((v for v in reversed(e50) if v), None)
vrsi = next((v for v in reversed(rsi_vals) if v), 50)
fiyat = closes[-1]
hacim_g = volumes[-1] > vol_ort * params.get(“hacim_carpan”, 1.3) if volumes else False
yukari = v20 and v50 and v20 > v50
rsi_ok = params[“rsi_alt”] < vrsi < params[“rsi_ust”]
f_ust  = v20 and fiyat > v20
p20 = next((v for v in reversed(e20[:-1]) if v), None)
p50 = next((v for v in reversed(e50[:-1]) if v), None)
golden = p20 and p50 and v20 and v50 and p20 <= p50 and v20 > v50
death  = p20 and p50 and v20 and v50 and p20 >= p50 and v20 < v50
alim  = (golden or (yukari and f_ust)) and rsi_ok and hacim_g
satim = death or vrsi > 76 or (not yukari and not f_ust)
sinyal = “AL” if alim else (“SAT” if satim else “BEKLE”)
stop_loss = round(fiyat * (1 - params[“stop_p”] / 100), 2) if alim else None
hedef1    = round(fiyat * (1 + params[“tp_p”] / 100), 2) if alim else None
hedef2    = round(fiyat * (1 + params[“tp_p”] * 1.5 / 100), 2) if alim else None
return {
“fiyat”: round(fiyat, 4),
“ema20”: round(v20, 4) if v20 else None,
“ema50”: round(v50, 4) if v50 else None,
“rsi”:   round(vrsi, 1),
“hacim_guclu”: int(hacim_g),
“sinyal”: sinyal,
“stop_loss”: stop_loss,
“hedef1”: hedef1,
“hedef2”: hedef2,
}

def backtest_strateji(closes, volumes, params):
ek = params.get(“ema_kisa”, 20)
eu = params.get(“ema_uzun”, 50)
stop_p = params.get(“stop_p”, 4.0)
tp_p   = params.get(“tp_p”,   8.0)
if len(closes) < eu + 10:
return None
e20 = calc_ema(closes, ek)
e50 = calc_ema(closes, eu)
rsi_vals = calc_rsi(closes)
pozisyon = None
islemler = []
peak = closes[0]
max_dd = 0
for i in range(eu + 5, len(closes)):
f = closes[i]
peak = max(peak, f)
max_dd = max(max_dd, (peak - f) / peak * 100)
v20 = e20[i]; v50 = e50[i]
vrsi = rsi_vals[i] or 50
if not v20 or not v50:
continue
start = max(0, i-20)
vol_ort = sum(volumes[start:i]) / (i - start) if i > start else 1
hacim_g = volumes[i] > vol_ort * params.get(“hacim_carpan”, 1.3)
yukari  = v20 > v50
rsi_ok  = params[“rsi_alt”] < vrsi < params[“rsi_ust”]
f_ust   = f > v20
p20 = e20[i-1]; p50 = e50[i-1]
golden = p20 and p50 and p20 <= p50 and v20 > v50
death  = p20 and p50 and p20 >= p50 and v20 < v50
alim   = (golden or (yukari and f_ust)) and rsi_ok and hacim_g
satim  = death or vrsi > 76
if pozisyon is None and alim:
pozisyon = f
elif pozisyon is not None:
stop = pozisyon * (1 - stop_p / 100)
tp   = pozisyon * (1 + tp_p  / 100)
if f <= stop or f >= tp or satim:
islemler.append((f - pozisyon) / pozisyon * 100)
pozisyon = None
if not islemler:
return {“net_kar”: 0, “basari_oran”: 0, “profit_factor”: 0,
“max_dd”: round(max_dd, 2), “islem_sayisi”: 0, “skor”: 0}
kazanan  = [x for x in islemler if x > 0]
kaybeden = [x for x in islemler if x <= 0]
net_kar  = sum(islemler)
basari   = len(kazanan) / len(islemler) * 100
gk = sum(kazanan) if kazanan else 0
gz = abs(sum(kaybeden)) if kaybeden else 0.001
pf = gk / gz
s1 = 25 if net_kar > 0 else 0
s2 = min(basari / 100 * 30, 30)
s3 = min(pf / 3 * 25, 25)
s4 = max(20 - max_dd / 5, 0)
return {
“net_kar”:       round(net_kar, 2),
“basari_oran”:   round(basari, 1),
“profit_factor”: round(pf, 2),
“max_dd”:        round(max_dd, 2),
“islem_sayisi”:  len(islemler),
“skor”:          round(s1 + s2 + s3 + s4),
}

# ── VERİ ÇEKME ─────────────────────────────────────────────────

_cache = {}
_lock  = threading.Lock()

PERIYOT_MAP = {
“15dk”: (“5d”,  “15m”),
“1sa”:  (“5d”,  “60m”),
“4sa”:  (“1mo”, “60m”),
“1G”:   (“5d”,  “1d”),
“2G”:   (“5d”,  “1d”),
“3G”:   (“1mo”, “1d”),
“5G”:   (“1mo”, “1d”),
“7G”:   (“1mo”, “1d”),
}
PERIYOT_BARS = {“15dk”: 1, “1sa”: 1, “4sa”: 4, “1G”: 1, “2G”: 2, “3G”: 3, “5G”: 5, “7G”: 7}

def veri_cek_gercek(sembol, yahoo_sembol):
try:
t  = yf.Ticker(yahoo_sembol)
df = t.history(period=“3mo”, interval=“1d”)
if df is None or df.empty or len(df) < 10:
return None
closes  = [float(x) for x in df[“Close”].tolist()]
volumes = [int(x) for x in df[“Volume”].tolist()]
degisim = (closes[-1] - closes[-2]) / closes[-2] * 100 if len(closes) >= 2 else 0
sonuc = analiz(closes, volumes)
if sonuc:
sonuc[“degisim”] = round(degisim, 2)
sonuc[“closes”]  = closes
sonuc[“volumes”] = volumes
return sonuc
except Exception as e:
return None

def veri_cek_demo(sembol):
import random, math
random.seed(abs(hash(sembol)) % 9999)
base = random.uniform(10, 500)
closes, vols = [], []
f = base
for i in range(90):
f *= random.uniform(0.975, 1.025)
closes.append(round(f, 4))
vols.append(int(random.uniform(500000, 8000000)))
deg = (closes[-1] - closes[-2]) / closes[-2] * 100
sonuc = analiz(closes, vols)
if sonuc:
sonuc[“degisim”] = round(deg, 2)
sonuc[“closes”]  = closes
sonuc[“volumes”] = vols
return sonuc

def performans_hesapla_gercek(sembol, yahoo_sembol):
sonuclar = {}
try:
t = yf.Ticker(yahoo_sembol)
df_gun = t.history(period=“1mo”, interval=“1d”)
if df_gun is not None and len(df_gun) >= 2:
closes = df_gun[“Close”].tolist()
for p, bars in PERIYOT_BARS.items():
if p in [“15dk”, “1sa”, “4sa”]:
continue
if len(closes) >= bars + 1:
deg = (closes[-1] - closes[-(bars+1)]) / closes[-(bars+1)] * 100
sonuclar[p] = round(deg, 2)
df_saat = t.history(period=“5d”, interval=“60m”)
if df_saat is not None and len(df_saat) >= 2:
closes_s = df_saat[“Close”].tolist()
for p, bars in [(“1sa”, 1), (“4sa”, 4)]:
if len(closes_s) >= bars + 1:
deg = (closes_s[-1] - closes_s[-(bars+1)]) / closes_s[-(bars+1)] * 100
sonuclar[p] = round(deg, 2)
df_15 = t.history(period=“5d”, interval=“15m”)
if df_15 is not None and len(df_15) >= 2:
closes_15 = df_15[“Close”].tolist()
deg = (closes_15[-1] - closes_15[-2]) / closes_15[-2] * 100
sonuclar[“15dk”] = round(deg, 2)
except:
pass
return sonuclar

def performans_hesapla_demo(sembol):
import random
random.seed(abs(hash(sembol + “perf”)) % 9999)
return {p: round(random.uniform(-8, 8), 2) for p in PERIYOT_BARS.keys()}

def guncelle(sembol):
info = TUM_SEMBOLLER.get(sembol)
if not info:
return
yahoo = info[“yahoo”]
if VERI_MODU == “gercek”:
sonuc = veri_cek_gercek(sembol, yahoo)
perf  = performans_hesapla_gercek(sembol, yahoo)
else:
sonuc = veri_cek_demo(sembol)
perf  = performans_hesapla_demo(sembol)

```
if not sonuc:
    return

now = datetime.now().strftime("%H:%M:%S")

# Stop-loss kontrolü
with _lock:
    eski = _cache.get(sembol, {})
    onceki_sinyal = eski.get("sinyal", "BEKLE")
    sinyal_saati  = eski.get("sinyal_saati")

    # Sinyal değiştiyse saatini kaydet
    yeni_sinyal = sonuc["sinyal"]
    if yeni_sinyal != onceki_sinyal:
        sinyal_saati = now

    # Stop-loss tetiklendi mi?
    stop_tetiklendi = False
    if eski.get("stop_loss") and sonuc["fiyat"] <= eski["stop_loss"]:
        sonuc["sinyal"]   = "SAT"
        stop_tetiklendi   = True
        sinyal_saati      = now

    sonuc["sembol"]        = sembol
    sonuc["tip"]           = info["tip"]
    sonuc["para"]          = info["para"]
    sonuc["onceki_sinyal"] = onceki_sinyal
    sonuc["sinyal_saati"]  = sinyal_saati or now
    sonuc["stop_tetiklendi"] = stop_tetiklendi
    sonuc["guncelleme"]    = now

    _cache[sembol] = sonuc

# Veritabanına kaydet
con = get_db()
con.execute("""INSERT OR REPLACE INTO hisse_cache VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    (sembol, info["tip"], sonuc["fiyat"], sonuc.get("degisim", 0),
     sonuc.get("ema20"), sonuc.get("ema50"), sonuc["rsi"],
     sonuc["hacim_guclu"], sonuc["sinyal"], sonuc["sinyal_saati"],
     sonuc.get("stop_loss"), sonuc.get("hedef1"), sonuc.get("hedef2"),
     onceki_sinyal, now))
for p, d in perf.items():
    con.execute("INSERT OR REPLACE INTO performans_cache VALUES (?,?,?,?)", (sembol, p, d, now))
con.commit()
con.close()
```

def ilk_yukleme():
semboller = list(TUM_SEMBOLLER.keys())
print(f”📡 {len(semboller)} sembol yükleniyor ({VERI_MODU} mod)…”)
for i, s in enumerate(semboller):
guncelle(s)
sinyal = _cache.get(s, {}).get(“sinyal”, “?”)
fiyat  = _cache.get(s, {}).get(“fiyat”, “?”)
print(f”  [{i+1:3}/{len(semboller)}] {s:<12} {str(fiyat):<10} {sinyal}”)
print(f”✅ {len(_cache)} sembol yüklendi!\n”)

def arkaplan():
while True:
time.sleep(30)
for s in list(TUM_SEMBOLLER.keys()):
guncelle(s)

# ── HTTP SUNUCU ────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
def log_message(self, *a): pass

```
def send_json(self, data, status=200):
    body = json.dumps(data, ensure_ascii=False).encode()
    self.send_response(status)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Access-Control-Allow-Origin", "*")
    self.send_header("Content-Length", len(body))
    self.end_headers()
    self.wfile.write(body)

def do_GET(self):
    p = urlparse(self.path)
    path = p.path
    params = parse_qs(p.query)
    s = params.get("s", [""])[0]
    tip = params.get("tip", ["tumu"])[0]
    periyot = params.get("periyot", ["1G"])[0]
    strateji = params.get("strateji", ["EMA_RSI_Hacim"])[0]

    if path in ("/", "/index.html"):
        self.serve_file()
    elif path == "/manifest.json":
        self.serve_static("manifest.json", "application/json")
    elif path == "/sw.js":
        self.serve_static("sw.js", "application/javascript")
    elif path in ("/icon-192.png", "/icon-512.png"):
        self.serve_icon()

    elif path == "/api/hisseler":
        with _lock:
            data = []
            for sem, c in _cache.items():
                if tip != "tumu" and c.get("tip") != tip:
                    continue
                data.append({k: v for k, v in c.items() if k not in ("closes", "volumes")})
        data.sort(key=lambda x: x.get("sembol", ""))
        self.send_json({"hisseler": data, "mod": VERI_MODU, "zaman": datetime.now().strftime("%H:%M:%S")})

    elif path == "/api/performans":
        con = get_db()
        rows = con.execute(
            "SELECT sembol, periyot, degisim FROM performans_cache WHERE periyot=? ORDER BY degisim DESC",
            (periyot,)).fetchall()
        con.close()
        self.send_json({"sonuclar": [{"sembol": r[0], "periyot": r[1], "degisim": r[2]} for r in rows], "periyot": periyot})

    elif path == "/api/stratejiler":
        con = get_db()
        rows = con.execute("SELECT id, isim, aciklama, olusturma FROM stratejiler").fetchall()
        con.close()
        self.send_json({"stratejiler": [{"id": r[0], "isim": r[1], "aciklama": r[2], "olusturma": r[3]} for r in rows]})

    elif path == "/api/backtest":
        if not s:
            self.send_json({"hata": "sembol gerekli"}); return
        con = get_db()
        st_row = con.execute("SELECT kod FROM stratejiler WHERE isim=?", (strateji,)).fetchone()
        con.close()
        if not st_row:
            self.send_json({"hata": "Strateji bulunamadı"}); return
        params_st = json.loads(st_row[0])
        with _lock:
            c = _cache.get(s, {})
        closes  = c.get("closes", [])
        volumes = c.get("volumes", [])
        if not closes:
            guncelle(s)
            with _lock:
                c = _cache.get(s, {})
            closes  = c.get("closes", [])
            volumes = c.get("volumes", [])
        sonuc = backtest_strateji(closes, volumes, params_st)
        if sonuc:
            sonuc["sembol"] = s
            sonuc["strateji"] = strateji
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            con = get_db()
            con.execute("INSERT OR REPLACE INTO backtest_sonuc VALUES (?,?,?,?,?,?,?,?,?)",
                (s, strateji, sonuc["net_kar"], sonuc["basari_oran"],
                 sonuc["profit_factor"], sonuc["max_dd"], sonuc["islem_sayisi"], sonuc["skor"], now))
            con.commit(); con.close()
        self.send_json(sonuc or {"hata": "Yeterli veri yok"})

    elif path == "/api/backtest_toplu":
        con = get_db()
        st_row = con.execute("SELECT kod FROM stratejiler WHERE isim=?", (strateji,)).fetchone()
        con.close()
        if not st_row:
            self.send_json({"hata": "Strateji bulunamadı"}); return
        params_st = json.loads(st_row[0])
        sonuclar = []
        with _lock:
            cache_copy = dict(_cache)
        for sem, c in cache_copy.items():
            if c.get("tip") != "hisse":
                continue
            closes  = c.get("closes", [])
            volumes = c.get("volumes", [])
            bt = backtest_strateji(closes, volumes, params_st)
            if bt:
                bt["sembol"] = sem
                bt["strateji"] = strateji
                sonuclar.append(bt)
                con = get_db()
                con.execute("INSERT OR REPLACE INTO backtest_sonuc VALUES (?,?,?,?,?,?,?,?,?)",
                    (sem, strateji, bt["net_kar"], bt["basari_oran"],
                     bt["profit_factor"], bt["max_dd"], bt["islem_sayisi"], bt["skor"],
                     datetime.now().strftime("%Y-%m-%d %H:%M")))
                con.commit(); con.close()
        sonuclar.sort(key=lambda x: x["skor"], reverse=True)
        self.send_json({"sonuclar": sonuclar, "strateji": strateji})

    elif path == "/api/portfoy":
        con = get_db()
        rows = con.execute("SELECT * FROM portfoy").fetchall()
        con.close()
        cols = ["sembol","lot","ort_maliyet","giris_tarihi","stop_loss","hedef","notlar"]
        portfoy = []
        toplam_kar = 0
        for r in rows:
            d = dict(zip(cols, r))
            with _lock:
                gf = _cache.get(d["sembol"], {}).get("fiyat", d["ort_maliyet"])
                sinyal = _cache.get(d["sembol"], {}).get("sinyal", "BEKLE")
            d["guncel_fiyat"] = gf
            d["sinyal"] = sinyal
            kar_tl = (gf - d["ort_maliyet"]) * d["lot"]
            d["kar_tl"] = round(kar_tl, 2)
            d["kar_yuzde"] = round((gf - d["ort_maliyet"]) / d["ort_maliyet"] * 100, 2)
            toplam_kar += kar_tl
            portfoy.append(d)
        self.send_json({"portfoy": portfoy, "toplam_kar": round(toplam_kar, 2)})

    elif path == "/api/gunluk":
        con = get_db()
        rows = con.execute("SELECT * FROM trade_gunlugu ORDER BY id DESC LIMIT 200").fetchall()
        con.close()
        cols = ["id","sembol","yon","giris","cikis","lot","kar_zarar","tarih","notlar"]
        self.send_json({"gunluk": [dict(zip(cols, r)) for r in rows]})

    elif path == "/api/ozet":
        with _lock:
            al  = sum(1 for c in _cache.values() if c.get("sinyal") == "AL")
            sat = sum(1 for c in _cache.values() if c.get("sinyal") == "SAT")
            bek = sum(1 for c in _cache.values() if c.get("sinyal") == "BEKLE")
            stop_uyari = [s for s, c in _cache.items() if c.get("stop_tetiklendi")]
        con = get_db()
        toplam_kar = con.execute("SELECT SUM(kar_zarar) FROM trade_gunlugu").fetchone()[0] or 0
        portfoy_adet = con.execute("SELECT COUNT(*) FROM portfoy").fetchone()[0]
        bt_iyi = con.execute("SELECT COUNT(DISTINCT sembol) FROM backtest_sonuc WHERE skor>=70").fetchone()[0]
        con.close()
        self.send_json({"al": al, "sat": sat, "bekle": bek,
                        "toplam_kar": round(toplam_kar, 2),
                        "portfoy_adet": portfoy_adet, "iyi_hisse": bt_iyi,
                        "stop_uyari": stop_uyari, "mod": VERI_MODU,
                        "zaman": datetime.now().strftime("%H:%M:%S")})
    else:
        self.send_response(404); self.end_headers()

def do_POST(self):
    length = int(self.headers.get("Content-Length", 0))
    body = json.loads(self.rfile.read(length)) if length else {}
    path = urlparse(self.path).path

    if path == "/api/strateji/ekle":
        try:
            params = json.loads(body["kod"])
        except:
            self.send_json({"hata": "Geçersiz JSON parametresi"}); return
        con = get_db()
        con.execute("INSERT OR REPLACE INTO stratejiler (isim, kod, aciklama, olusturma) VALUES (?,?,?,?)",
            (body["isim"], body["kod"], body.get("aciklama", ""), datetime.now().strftime("%Y-%m-%d")))
        con.commit(); con.close()
        self.send_json({"ok": True})

    elif path == "/api/strateji/sil":
        con = get_db()
        con.execute("DELETE FROM stratejiler WHERE isim=?", (body["isim"],))
        con.execute("DELETE FROM backtest_sonuc WHERE strateji=?", (body["isim"],))
        con.commit(); con.close()
        self.send_json({"ok": True})

    elif path == "/api/portfoy/ekle":
        con = get_db()
        con.execute("INSERT OR REPLACE INTO portfoy VALUES (?,?,?,?,?,?,?)",
            (body["sembol"], body["lot"], body["ort_maliyet"],
             body.get("giris_tarihi", datetime.now().strftime("%Y-%m-%d")),
             body.get("stop_loss", 0), body.get("hedef", 0), body.get("notlar", "")))
        con.commit(); con.close()
        self.send_json({"ok": True})

    elif path == "/api/portfoy/sil":
        con = get_db()
        con.execute("DELETE FROM portfoy WHERE sembol=?", (body["sembol"],))
        con.commit(); con.close()
        self.send_json({"ok": True})

    elif path == "/api/gunluk/ekle":
        kar = (float(body["cikis"]) - float(body["giris"])) * int(body["lot"])
        con = get_db()
        con.execute("INSERT INTO trade_gunlugu (sembol,yon,giris,cikis,lot,kar_zarar,tarih,notlar) VALUES (?,?,?,?,?,?,?,?)",
            (body["sembol"], body["yon"], body["giris"], body["cikis"], body["lot"],
             round(kar, 2), body.get("tarih", datetime.now().strftime("%Y-%m-%d")), body.get("notlar", "")))
        con.commit(); con.close()
        self.send_json({"ok": True})

    elif path == "/api/gunluk/sil":
        con = get_db()
        con.execute("DELETE FROM trade_gunlugu WHERE id=?", (body["id"],))
        con.commit(); con.close()
        self.send_json({"ok": True})

    else:
        self.send_response(404); self.end_headers()

def serve_static(self, filename, content_type):
    base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, "static", filename)
    if not os.path.exists(path):
        path = os.path.join(base, filename)
    with open(path, "rb") as f:
        content = f.read()
    self.send_response(200)
    self.send_header("Content-Type", content_type)
    self.send_header("Content-Length", len(content))
    self.end_headers()
    self.wfile.write(content)

def serve_icon(self):
    # Basit PNG ikonu (mavi kare)
    import base64
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAMAAAADACAYAAABS3GwHAAAABmJLR0QA/wD/AP+gvaeTAAAA"
        "GklEQVR42mNkYGBg+M9AgAEAAAD//wMABQAB/tRoowAAAABJRU5ErkJggg==")
    self.send_response(200)
    self.send_header("Content-Type", "image/png")
    self.send_header("Content-Length", len(png))
    self.end_headers()
    self.wfile.write(png)

def serve_file(self):
    base = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(base, "static", "index.html")
    if not os.path.exists(html_path):
        html_path = os.path.join(base, "index.html")
    with open(html_path, "rb") as f:
        content = f.read()
    self.send_response(200)
    self.send_header("Content-Type", "text/html; charset=utf-8")
    self.send_header("Content-Length", len(content))
    self.end_headers()
    self.wfile.write(content)
```

# ── BAŞLAT ─────────────────────────────────────────────────────

if **name** == “**main**”:
print(”=” * 55)
print(”  BIST SİNYAL SİSTEMİ v3.0”)
print(”=” * 55)
init_db()
t1 = threading.Thread(target=ilk_yukleme, daemon=True)
t1.start()
t2 = threading.Thread(target=arkaplan, daemon=True)
t2.start()
t1.join()
url = f”http://localhost:{PORT}”
print(f”🌐 → {url}\n   Kapatmak için Ctrl+C\n”)
pass
try:
HTTPServer((“0.0.0.0”, PORT), Handler).serve_forever()
except KeyboardInterrupt:
print(”\n👋 Kapandı.”)
