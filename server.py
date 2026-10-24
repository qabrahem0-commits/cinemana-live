import os
import shutil
import subprocess
import sys
import threading
import time
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent
HLS_DIR = Path(os.environ.get("HLS_DIR", str(BASE_DIR / "hls_streams")))
DB_FILE = Path(os.environ.get("DB_FILE", str(BASE_DIR / "db.json")))
HLS_DIR.mkdir(parents=True, exist_ok=True)

FFMPEG_WIN = r"C:\Users\mk\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin\ffmpeg.exe"
FFMPEG_PATH = FFMPEG_WIN if os.path.exists(FFMPEG_WIN) else (shutil.which("ffmpeg") or "ffmpeg")

app = Flask(__name__, static_folder=str(BASE_DIR))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
}

# Popular Leagues Configuration (365Scores IDs)
LEAGUES = [
    {"id": 572,  "name": "دوري أبطال أوروبا",     "short": "أبطال أوروبا",   "country": "أوروبا",   "badge": "🇪🇺"},
    {"id": 7,    "name": "الدوري الإنجليزي الممتاز", "short": "الدوري الإنجليزي", "country": "إنجلترا", "badge": "🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    {"id": 11,   "name": "الدوري الإسباني (لاليغا)", "short": "الدوري الإسباني", "country": "إسبانيا", "badge": "🇪🇸"},
    {"id": 17,   "name": "الدوري الإيطالي (سيريا آ)", "short": "الدوري الإيطالي", "country": "إيطاليا", "badge": "🇮🇹"},
    {"id": 25,   "name": "الدوري الألماني (بوندسليغا)", "short": "الدوري الألماني", "country": "ألمانيا", "badge": "🇩🇪"},
    {"id": 35,   "name": "الدوري الفرنسي (ليغ 1)",   "short": "الدوري الفرنسي", "country": "فرنسا",   "badge": "🇫🇷"},
    {"id": 6822, "name": "دوري نجوم العراق",       "short": "الدوري العراقي", "country": "العراق",  "badge": "🇮🇶"},
    {"id": 649,  "name": "الدوري السعودي (روشن)",   "short": "الدوري السعودي", "country": "السعودية", "badge": "🇸🇦"},
    {"id": 623,  "name": "دوري أبطال آسيا للنخبة",   "short": "أبطال آسيا",     "country": "آسيا",    "badge": "🌏"},
]

PRIORITY_COMP_IDS = {l["id"]: idx for idx, l in enumerate(LEAGUES)}

# Strictly the 5 requested beIN Sports channels (1 to 5) with multi-server failover URLs
DEFAULT_CHANNELS = [
    {
        "id": "bein1",
        "num": "1",
        "name": "beIN Sports HD 1",
        "category": "beIN Sports",
        "quality": "1080p FHD",
        "source_url": "http://amlive.cc:80/live/51821482/45726168/489394.ts",
        "backup_urls": [
            "http://amlive.cc:80/live/51821482/45726168/589768.ts",
            "http://amlive.cc:80/live/51821482/45726168/513309.ts",
            "http://amlive.cc:80/live/51821482/45726168/489405.ts"
        ],
        "use_restream": True,
        "commentator": "عصام الشوالي"
    },
    {
        "id": "bein2",
        "num": "2",
        "name": "beIN Sports HD 2",
        "category": "beIN Sports",
        "quality": "1080p FHD",
        "source_url": "http://amlive.cc:80/live/51821482/45726168/489395.ts",
        "backup_urls": [
            "http://amlive.cc:80/live/51821482/45726168/589769.ts",
            "http://amlive.cc:80/live/51821482/45726168/513310.ts",
            "http://amlive.cc:80/live/51821482/45726168/489406.ts"
        ],
        "use_restream": True,
        "commentator": "حفيظ دراجي"
    },
    {
        "id": "bein3",
        "num": "3",
        "name": "beIN Sports HD 3",
        "category": "beIN Sports",
        "quality": "1080p FHD",
        "source_url": "http://amlive.cc:80/live/51821482/45726168/489396.ts",
        "backup_urls": [
            "http://amlive.cc:80/live/51821482/45726168/589770.ts",
            "http://amlive.cc:80/live/51821482/45726168/513311.ts",
            "http://amlive.cc:80/live/51821482/45726168/589760.ts"
        ],
        "use_restream": True,
        "commentator": "خليل البلوشي"
    },
    {
        "id": "bein4",
        "num": "4",
        "name": "beIN Sports HD 4",
        "category": "beIN Sports",
        "quality": "1080p FHD",
        "source_url": "http://amlive.cc:80/live/51821482/45726168/489397.ts",
        "backup_urls": [
            "http://amlive.cc:80/live/51821482/45726168/589771.ts",
            "http://amlive.cc:80/live/51821482/45726168/513312.ts"
        ],
        "use_restream": True,
        "commentator": "رؤوف خليف"
    },
    {
        "id": "bein5",
        "num": "5",
        "name": "beIN Sports HD 5",
        "category": "beIN Sports",
        "quality": "1080p FHD",
        "source_url": "http://amlive.cc:80/live/51821482/45726168/489398.ts",
        "backup_urls": [
            "http://amlive.cc:80/live/51821482/45726168/589772.ts",
            "http://amlive.cc:80/live/51821482/45726168/513313.ts"
        ],
        "use_restream": True,
        "commentator": "حسن العيدروس"
    }
]


def load_db():
    if DB_FILE.exists():
        try:
            data = json.loads(DB_FILE.read_text(encoding="utf-8"))
            if len(data.get("channels", [])) == 5:
                return data
        except Exception:
            pass
    default_db = {
        "iptv_panel": {
            "host": "http://amlive.cc:80",
            "username": "51821482",
            "password": "45726168",
            "max_connections": 1
        },
        "channels": DEFAULT_CHANNELS,
        "match_Overrides": {}
    }
    save_db(default_db)
    return default_db


def save_db(data):
    try:
        DB_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


# --- IN-MEMORY CACHE FOR 365SCORES API ---
API_CACHE = {}
CACHE_LOCK = threading.Lock()


def cached_fetch_json(url, ttl=30):
    now = time.time()
    with CACHE_LOCK:
        if url in API_CACHE and (now - API_CACHE[url]["ts"] < ttl):
            return API_CACHE[url]["data"]
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=12) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    with CACHE_LOCK:
        API_CACHE[url] = {"ts": now, "data": data}
    return data


# --- ON-DEMAND FFMPEG RESTREAM ENGINE ---
ACTIVE_STREAMS = {}  # channel_id -> {"proc": Popen, "last_access": timestamp, "source": url}
STREAM_LOCK = threading.Lock()


def _spawn_ffmpeg(channel_id, source_url):
    ch_dir = HLS_DIR / channel_id
    if ch_dir.exists():
        shutil.rmtree(ch_dir, ignore_errors=True)
    ch_dir.mkdir(parents=True, exist_ok=True)

    m3u8_out = ch_dir / "index.m3u8"
    seg_pattern = str(ch_dir / "seg_%03d.ts")

    cmd = [
        FFMPEG_PATH, "-y",
        "-loglevel", "warning",
        "-user_agent", "IPTVSmartersPro",
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "5",
        "-i", source_url,
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        "-f", "hls",
        "-hls_time", "2",
        "-hls_list_size", "6",
        "-hls_flags", "delete_segments+append_list+independent_segments",
        "-hls_segment_filename", seg_pattern,
        str(m3u8_out)
    ]

    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ACTIVE_STREAMS[channel_id] = {
        "proc": proc,
        "last_access": time.time(),
        "source": source_url,
        "started_at": datetime.now().strftime("%H:%M:%S")
    }
    return m3u8_out


def start_restream_process(channel_id, ch_obj, max_conn=1):
    source_url = ch_obj.get("source_url", "")
    candidates = [source_url] + [u for u in ch_obj.get("backup_urls", []) if u != source_url]

    with STREAM_LOCK:
        info = ACTIVE_STREAMS.get(channel_id)
        m3u8_existing = HLS_DIR / channel_id / "index.m3u8"
        if info and info["proc"].poll() is None and m3u8_existing.exists():
            info["last_access"] = time.time()
            return True

        # Clean dead processes
        for cid, inf in list(ACTIVE_STREAMS.items()):
            if inf["proc"].poll() is not None:
                ACTIVE_STREAMS.pop(cid, None)

        # Enforce max_conn so single-connection or 5-connection IPTV panel never blocks
        while len(ACTIVE_STREAMS) >= max(1, int(max_conn)):
            oldest_cid = min(ACTIVE_STREAMS.keys(), key=lambda k: ACTIVE_STREAMS[k]["last_access"])
            old_info = ACTIVE_STREAMS.pop(oldest_cid, None)
            if old_info and old_info["proc"].poll() is None:
                try:
                    old_info["proc"].terminate()
                    old_info["proc"].wait(timeout=1.5)
                except Exception:
                    try:
                        old_info["proc"].kill()
                    except Exception:
                        pass

        # Try primary URL, then failover to backup URLs if stream doesn't produce segments
        for cand_url in candidates:
            if not cand_url:
                continue
            m3u8_out = _spawn_ffmpeg(channel_id, cand_url)
            for _ in range(28):  # Wait up to 7s
                if m3u8_out.exists() and m3u8_out.stat().st_size > 40:
                    return True
                if ACTIVE_STREAMS[channel_id]["proc"].poll() is not None:
                    break
                time.sleep(0.25)

            # Current candidate failed, kill before trying next
            inf = ACTIVE_STREAMS.pop(channel_id, None)
            if inf and inf["proc"].poll() is None:
                try:
                    inf["proc"].kill()
                except Exception:
                    pass

        return False


def stop_restream_process(channel_id):
    with STREAM_LOCK:
        info = ACTIVE_STREAMS.pop(channel_id, None)
        if info and info["proc"].poll() is None:
            try:
                info["proc"].terminate()
            except Exception:
                pass


def reaper_loop():
    """Automatically stop restream processes that have had no viewers for >90 seconds."""
    while True:
        time.sleep(15)
        now = time.time()
        with STREAM_LOCK:
            to_stop = [
                cid for cid, inf in ACTIVE_STREAMS.items()
                if (now - inf["last_access"] > 90) or (inf["proc"].poll() is not None)
            ]
        for cid in to_stop:
            stop_restream_process(cid)


threading.Thread(target=reaper_loop, daemon=True).start()


def auto_assign_channel(comp_id):
    if comp_id in (572, 7):
        return "bein1", "عصام الشوالي"
    if comp_id == 11:
        return "bein2", "حفيظ دراجي"
    if comp_id == 17:
        return "bein3", "خليل البلوشي"
    if comp_id in (25, 35):
        return "bein4", "رؤوف خليف"
    if comp_id in (649, 623, 6822):
        return "bein5", "حسن العيدروس"
    return "bein1", "عصام الشوالي"


# --- ROUTES ---

@app.route("/")
def index():
    return send_from_directory(str(BASE_DIR), "index.html")


@app.route("/api/init")
def api_init():
    db = load_db()
    return jsonify({
        "leagues": LEAGUES,
        "channels": db.get("channels", DEFAULT_CHANNELS),
        "active_streams": list(ACTIVE_STREAMS.keys())
    })


@app.route("/api/matches")
def api_matches():
    date_offset = int(request.args.get("offset", "0"))
    comp_filter = request.args.get("competition_id", "")

    target_date = (datetime.now() + timedelta(days=date_offset)).strftime("%d/%m/%Y")

    if comp_filter and comp_filter.isdigit():
        url = (
            f"https://webws.365scores.com/web/games/allscores/?"
            f"appTypeId=5&langId=27&timezoneName=Asia/Baghdad&userCountryId=110"
            f"&sports=1&competitions={comp_filter}"
        )
    else:
        url = (
            f"https://webws.365scores.com/web/games/allscores/?"
            f"appTypeId=5&langId=27&timezoneName=Asia/Baghdad&userCountryId=110"
            f"&sports=1&startDate={target_date}&endDate={target_date}"
        )

    try:
        raw = cached_fetch_json(url, ttl=25)
    except Exception as e:
        return jsonify({"error": str(e), "matches": []}), 500

    db = load_db()
    overrides = db.get("match_Overrides", {})
    channels_map = {c["id"]: c for c in db.get("channels", DEFAULT_CHANNELS)}
    comps_map = {c["id"]: c["name"] for c in raw.get("competitions", [])}

    matches = []
    for g in raw.get("games", []):
        gid = str(g.get("id"))
        cid = g.get("competitionId")
        comp_name = comps_map.get(cid) or g.get("competitionDisplayName", "مباريات عالمية")

        h = g.get("homeCompetitor", {})
        a = g.get("awayCompetitor", {})

        status_group = g.get("statusGroup", 2)  # 2=Scheduled, 3=Live, 4=Ended
        is_live = (status_group == 3)
        is_ended = (status_group == 4)

        default_ch_id, default_comm = auto_assign_channel(cid)
        ov = overrides.get(gid, {})
        ch_id = ov.get("channel_id", default_ch_id)
        if ch_id not in channels_map:
            ch_id = "bein1"
        ch_obj = channels_map.get(ch_id, DEFAULT_CHANNELS[0])
        commentator = ov.get("commentator") or ch_obj.get("commentator") or default_comm

        start_iso = g.get("startTime", "")
        time_str = ""
        date_str = ""
        if start_iso:
            try:
                dt = datetime.fromisoformat(start_iso)
                time_str = dt.strftime("%I:%M %p").replace("AM", "ص").replace("PM", "م")
                date_str = dt.strftime("%Y-%m-%d")
            except Exception:
                time_str = start_iso[11:16]

        priority = PRIORITY_COMP_IDS.get(cid, 999)

        matches.append({
            "id": gid,
            "competition_id": cid,
            "competition_name": comp_name,
            "competition_logo": f"https://imagecache.365scores.com/image/upload/f_png,w_64,h_64,c_limit,q_auto:eco,dpr_2,d_Countries:Round:default.png/v1/Competitions/{cid}",
            "home_name": h.get("name", ""),
            "home_score": int(h["score"]) if h.get("score", -1) >= 0 else None,
            "home_logo": f"https://imagecache.365scores.com/image/upload/f_png,w_96,h_96,c_limit,q_auto:eco,dpr_2,d_Competitors:default1.png/v1/Competitors/{h.get('id')}",
            "away_name": a.get("name", ""),
            "away_score": int(a["score"]) if a.get("score", -1) >= 0 else None,
            "away_logo": f"https://imagecache.365scores.com/image/upload/f_png,w_96,h_96,c_limit,q_auto:eco,dpr_2,d_Competitors:default1.png/v1/Competitors/{a.get('id')}",
            "status_text": g.get("statusText", ""),
            "game_time": int(g["gameTime"]) if g.get("gameTime", -1) > 0 else None,
            "is_live": is_live,
            "is_ended": is_ended,
            "start_time": time_str,
            "start_date": date_str,
            "start_iso": start_iso,
            "channel_id": ch_id,
            "channel_name": ch_obj.get("name", "beIN Sports HD 1"),
            "commentator": commentator,
            "priority": priority
        })

    matches.sort(key=lambda m: (0 if m["is_live"] else (1 if not m["is_ended"] else 2), m["priority"], m["start_iso"]))
    live_count = sum(1 for m in matches if m["is_live"])

    return jsonify({
        "date": target_date,
        "total": len(matches),
        "live_count": live_count,
        "matches": matches[:120]
    })


@app.route("/api/standings")
def api_standings():
    comp_id = request.args.get("competition_id", "7")
    url = (
        f"https://webws.365scores.com/web/standings/?"
        f"appTypeId=5&langId=27&timezoneName=Asia/Baghdad&userCountryId=110&competitions={comp_id}"
    )
    try:
        raw = cached_fetch_json(url, ttl=120)
        standings_list = raw.get("standings", [])
        if not standings_list:
            return jsonify({"rows": []})
        rows_raw = standings_list[0].get("rows", [])
        rows = []
        for r in rows_raw:
            comp = r.get("competitor", {})
            rows.append({
                "position": r.get("position"),
                "team_id": comp.get("id"),
                "team_name": comp.get("name"),
                "team_logo": f"https://imagecache.365scores.com/image/upload/f_png,w_64,h_64,c_limit,q_auto:eco,dpr_2,d_Competitors:default1.png/v1/Competitors/{comp.get('id')}",
                "played": int(r.get("gamePlayed", 0)),
                "won": int(r.get("gamesWon", 0)),
                "drawn": int(r.get("gamesEven", 0)),
                "lost": int(r.get("gamesLost", 0)),
                "for": int(r.get("for", 0)),
                "against": int(r.get("against", 0)),
                "diff": int(r.get("ratio", 0)),
                "points": int(r.get("points", 0)),
            })
        return jsonify({"competition_id": comp_id, "rows": rows})
    except Exception as e:
        return jsonify({"error": str(e), "rows": []}), 500


# --- STREAM & RESTREAM ENDPOINTS ---

@app.route("/api/stream/<channel_id>")
def api_get_stream(channel_id):
    db = load_db()
    channels = {c["id"]: c for c in db.get("channels", DEFAULT_CHANNELS)}
    ch = channels.get(channel_id)
    if not ch:
        return jsonify({"error": "Channel not found"}), 404

    src = ch.get("source_url", "")
    use_restream = ch.get("use_restream", True)
    max_conn = db.get("iptv_panel", {}).get("max_connections", 1)

    if use_restream and src:
        ok = start_restream_process(channel_id, ch, max_conn=max_conn)
        return jsonify({
            "channel": ch,
            "ready": ok,
            "mode": "restream_hls",
            "play_url": f"/hls/{channel_id}/index.m3u8?t={int(time.time())}"
        })

    return jsonify({
        "channel": ch,
        "ready": True,
        "mode": "direct_hls",
        "play_url": src
    })


@app.route("/hls/<channel_id>/<path:filename>")
def serve_hls(channel_id, filename):
    with STREAM_LOCK:
        if channel_id in ACTIVE_STREAMS:
            ACTIVE_STREAMS[channel_id]["last_access"] = time.time()
    ch_dir = HLS_DIR / channel_id
    if not (ch_dir / filename).exists():
        return ("Segment not ready", 404)
    resp = send_from_directory(str(ch_dir), filename)
    if filename.endswith(".ts"):
        resp.headers["Cache-Control"] = "public, max-age=60, s-maxage=60"
        resp.headers["CDN-Cache-Control"] = "public, max-age=60"
    else:
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


# --- ADMIN & IPTV PANEL ENDPOINTS ---

@app.route("/api/admin/config", methods=["GET", "POST"])
def api_admin_config():
    db = load_db()
    if request.method == "POST":
        body = request.get_json(force=True)
        if "iptv_panel" in body:
            db["iptv_panel"] = body["iptv_panel"]
        if "channels" in body:
            db["channels"] = body["channels"]
        save_db(db)
        return jsonify({"status": "saved", "db": db})

    with STREAM_LOCK:
        active_info = {
            cid: {"source": inf["source"], "started_at": inf["started_at"]}
            for cid, inf in ACTIVE_STREAMS.items()
            if inf["proc"].poll() is None
        }
    return jsonify({
        "iptv_panel": db.get("iptv_panel", {}),
        "channels": db.get("channels", DEFAULT_CHANNELS),
        "active_restreams": active_info
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5080"))
    print(f"Starting Cinemana Live Server on http://0.0.0.0:{port} ...")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
