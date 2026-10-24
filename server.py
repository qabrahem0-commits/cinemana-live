import os
import re
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
from flask import Flask, request, jsonify, send_from_directory, Response

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

# TMDB Official Credentials (Arabic Metadata, 4K Backdrops, Posters, Seasons & IMDb IDs)
TMDB_API_KEY = "d084ccb4f9f7ec6b8dbec136ba01eecb"
TMDB_READ_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJkMDg0Y2NiNGY5ZjdlYzZiOGRiZWMxMzZiYTAxZWVjYiIsIm5iZiI6MTc5Mjg2MzM5MS4wODYwMDAyLCJzdWIiOiI2YWRjZWM5ZjlmNzE1NGZjYzk2YmU0M2MiLCJzY29wZXMiOlsiYXBpX3JlYWQiXSwidmVyc2lvbiI6MX0.CLKgxHgNMxwDU-vGBzUPDUOPKVOWtGInUwejn3pcOUM"
TMDB_HEADERS = {
    "Authorization": f"Bearer {TMDB_READ_TOKEN}",
    "Accept": "application/json",
    "User-Agent": HEADERS["User-Agent"]
}

TMDB_GENRE_MAP = {
    "Action": (28, 10759),
    "Drama": (18, 18),
    "Sci-Fi": (878, 10765),
    "Thriller": (53, 9648),
    "Comedy": (35, 35),
    "Horror": (27, 9648),
    "Animation": (16, 16)
}

TMDB_GENRE_NAMES_AR = {
    28: "أكشن", 12: "مغامرة", 16: "أنمي ورسوم متحركة", 35: "كوميديا", 80: "جريمة",
    99: "وثائقي", 18: "دراما", 10751: "عائلي", 14: "فانتازيا", 36: "تاريخي",
    27: "رعب", 9648: "غموض", 10749: "رومانسي", 878: "خيال علمي", 53: "إثارة وتشويق",
    10752: "حرب", 10759: "أكشن ومغامرة", 10765: "خيال علمي وفانتازيا"
}

LEAGUES = [
    {
        "id": 572,
        "name": "دوري أبطال أوروبا",
        "short": "أبطال أوروبا",
        "slug": "دوري-أبطال-أوروبا",
        "country": "أوروبا",
        "badge": "🇪🇺",
        "seo_desc": "مشاهدة مباريات دوري أبطال أوروبا بث مباشر اليوم بدقة 4K و FHD بدون تقطيع مع جدول ترتيب دوري أبطال أوروبا والنتائج اللحظية عبر سينمانا لايف."
    },
    {
        "id": 7,
        "name": "الدوري الإنجليزي الممتاز",
        "short": "الدوري الإنجليزي",
        "slug": "الدوري-الإنجليزي-الممتاز",
        "country": "إنجلترا",
        "badge": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
        "seo_desc": "بث مباشر مباريات الدوري الإنجليزي الممتاز البريميرليغ اليوم وجدول ترتيب الدوري الإنجليزي والنقاط عبر قنوات beIN Sports على سينمانا لايف."
    },
    {
        "id": 11,
        "name": "الدوري الإسباني (لاليغا)",
        "short": "الدوري الإسباني",
        "slug": "الدوري-الإسباني",
        "country": "إسبانيا",
        "badge": "🇪🇸",
        "seo_desc": "مشاهدة مباريات الدوري الإسباني لاليغا اليوم بث مباشر (ريال مدريد وبرشلونة) مع جدول ترتيب الدوري الإسباني المحدث لحظة بلحظة."
    },
    {
        "id": 17,
        "name": "الدوري الإيطالي (سيريا آ)",
        "short": "الدوري الإيطالي",
        "slug": "الدوري-الإيطالي",
        "country": "إيطاليا",
        "badge": "🇮🇹",
        "seo_desc": "بث مباشر مباريات الدوري الإيطالي الكالتشيو اليوم وجدول ترتيب السيريا آ والنتائج المباشرة على موقع سينمانا لايف."
    },
    {
        "id": 25,
        "name": "الدوري الألماني (بوندسليغا)",
        "short": "الدوري الألماني",
        "slug": "الدوري-الألماني",
        "country": "ألمانيا",
        "badge": "🇩🇪",
        "seo_desc": "مشاهدة مباريات الدوري الألماني البوندسليغا بث مباشر اليوم وجدول الترتيب والنقاط بدون تقطيع."
    },
    {
        "id": 35,
        "name": "الدوري الفرنسي (ليغ 1)",
        "short": "الدوري الفرنسي",
        "slug": "الدوري-الفرنسي",
        "country": "فرنسا",
        "badge": "🇫🇷",
        "seo_desc": "بث مباشر مباريات الدوري الفرنسي ليغ 1 اليوم وجدول ترتيب الأندية والنتائج الفورية."
    },
    {
        "id": 6822,
        "name": "دوري نجوم العراق",
        "short": "الدوري العراقي",
        "slug": "دوري-نجوم-العراق",
        "country": "العراق",
        "badge": "🇮🇶",
        "seo_desc": "مشاهدة مباريات دوري نجوم العراق اليوم بث مباشر (الشرطة، القوة الجوية، الزوراء، الطلبة) مع جدول ترتيب الدوري العراقي."
    },
    {
        "id": 649,
        "name": "الدوري السعودي (روشن)",
        "short": "الدوري السعودي",
        "slug": "الدوري-السعودي-روشن",
        "country": "السعودية",
        "badge": "🇸🇦",
        "seo_desc": "بث مباشر مباريات الدوري السعودي روشن اليوم (الهلال، النصر، الاتحاد، الأهلي) وجدول ترتيب الدوري السعودي."
    },
    {
        "id": 623,
        "name": "دوري أبطال آسيا للنخبة",
        "short": "أبطال آسيا",
        "slug": "دوري-أبطال-آسيا-للنخبة",
        "country": "آسيا",
        "badge": "🌏",
        "seo_desc": "مشاهدة مباريات دوري أبطال آسيا للنخبة بث مباشر اليوم وجدول الترتيب والنتائج المباشرة."
    },
]

PRIORITY_COMP_IDS = {l["id"]: idx for idx, l in enumerate(LEAGUES)}
LEAGUES_BY_ID = {str(l["id"]): l for l in LEAGUES}

# 5 Dedicated Broadcast Channels (2x 4K + 2x Full HD 1080p + 1x 720p HD)
DEFAULT_CHANNELS = [
    {
        "id": "bein1",
        "num": "1",
        "name": "beIN Sports 1 4K",
        "category": "beIN Sports",
        "quality": "4K Ultra HD",
        "desc": "القناة الصوتية الأولى لنقل قمم دوري أبطال أوروبا والدوري الإنجليزي الممتاز بدقة 4K فائقة الوضوح.",
        "account_user": "16443423",
        "source_url": "http://s1.1234.ninja:80/live/16443423/47768244/722942.ts",
        "backup_urls": [
            "http://s1.1234.ninja:80/live/16443423/47768244/692769.ts",
            "http://s1.1234.ninja:80/live/16443423/47768244/722931.ts"
        ],
        "use_restream": True,
        "commentator": "عصام الشوالي"
    },
    {
        "id": "bein2",
        "num": "2",
        "name": "beIN Sports 2 4K",
        "category": "beIN Sports",
        "quality": "4K Ultra HD",
        "desc": "تغطية حصرية لمباريات الدوري الإسباني (لاليغا) وقمم الكرة الأوروبية بدقة 4K بدون تقطيع.",
        "account_user": "23413277",
        "source_url": "http://s1.1234.ninja:80/live/23413277/64368196/722943.ts",
        "backup_urls": [
            "http://s1.1234.ninja:80/live/23413277/64368196/692770.ts",
            "http://s1.1234.ninja:80/live/23413277/64368196/722932.ts"
        ],
        "use_restream": True,
        "commentator": "حفيظ دراجي"
    },
    {
        "id": "bein3",
        "num": "3",
        "name": "beIN Sports 3 FHD",
        "category": "beIN Sports",
        "quality": "1080p Full HD",
        "desc": "بث مباشر لمباريات الدوري الإيطالي (الكالتشيو) والبطولات القارية الكبرى بدقة Full HD 1080p.",
        "account_user": "34589374",
        "source_url": "http://s1.1234.ninja:80/live/34589374/72437113/722944.ts",
        "backup_urls": [
            "http://s1.1234.ninja:80/live/34589374/72437113/692771.ts",
            "http://s1.1234.ninja:80/live/34589374/72437113/704923.ts"
        ],
        "use_restream": True,
        "commentator": "خليل البلوشي"
    },
    {
        "id": "bein4",
        "num": "4",
        "name": "beIN Sports 4 FHD",
        "category": "beIN Sports",
        "quality": "1080p Full HD",
        "desc": "نقل حي ومباشر لمباريات الدوري الألماني (بوندسليغا) والدوري الفرنسي بدقة 1080p FHD.",
        "account_user": "71545171",
        "source_url": "http://s1.1234.ninja:80/live/71545171/64955659/722945.ts",
        "backup_urls": [
            "http://s1.1234.ninja:80/live/71545171/64955659/692772.ts",
            "http://s1.1234.ninja:80/live/71545171/64955659/704924.ts"
        ],
        "use_restream": True,
        "commentator": "رؤوف خليف"
    },
    {
        "id": "bein5",
        "num": "5",
        "name": "beIN Sports 5 HD",
        "category": "beIN Sports",
        "quality": "720p HD",
        "desc": "بث مباشر سريع ومستقر بدقة 720p HD مثالي للاتصالات المتوسطة والهواتف الذكية لنقل البطولات العربية والآسيوية.",
        "account_user": "27186725",
        "source_url": "http://s1.1234.ninja:80/live/27186725/18165811/704925.ts",
        "backup_urls": [
            "http://s1.1234.ninja:80/live/27186725/18165811/692764.ts",
            "http://s1.1234.ninja:80/live/27186725/18165811/722946.ts"
        ],
        "use_restream": True,
        "commentator": "حسن العيدروس"
    }
]


def load_db():
    if DB_FILE.exists():
        try:
            data = json.loads(DB_FILE.read_text(encoding="utf-8"))
            if data.get("version") == 5 and len(data.get("channels", [])) == 5:
                return data
        except Exception:
            pass
    default_db = {
        "version": 5,
        "iptv_panel": {
            "host": "http://s1.1234.ninja:80",
            "max_connections": 5
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


# --- IN-MEMORY CACHE ---
API_CACHE = {}
CACHE_LOCK = threading.Lock()


def cached_fetch_json(url, ttl=60, custom_headers=None):
    now = time.time()
    with CACHE_LOCK:
        if url in API_CACHE and (now - API_CACHE[url]["ts"] < ttl):
            return API_CACHE[url]["data"]
    req = urllib.request.Request(url, headers=custom_headers or HEADERS)
    with urllib.request.urlopen(req, timeout=12) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    with CACHE_LOCK:
        API_CACHE[url] = {"ts": now, "data": data}
    return data


def tmdb_get(path_and_query, ttl=600):
    url = f"https://api.themoviedb.org/3/{path_and_query.lstrip('/')}"
    return cached_fetch_json(url, ttl=ttl, custom_headers=TMDB_HEADERS)


# --- ON-DEMAND STREAM ENGINE (5 INDEPENDENT ACCOUNTS) ---
ACTIVE_STREAMS = {}
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


def start_restream_process(channel_id, ch_obj, max_conn=5):
    source_url = ch_obj.get("source_url", "")
    candidates = [source_url] + [u for u in ch_obj.get("backup_urls", []) if u != source_url]

    with STREAM_LOCK:
        info = ACTIVE_STREAMS.get(channel_id)
        m3u8_existing = HLS_DIR / channel_id / "index.m3u8"
        if info and info["proc"].poll() is None and m3u8_existing.exists():
            info["last_access"] = time.time()
            return True

        for cid, inf in list(ACTIVE_STREAMS.items()):
            if inf["proc"].poll() is not None:
                ACTIVE_STREAMS.pop(cid, None)

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

        for cand_url in candidates:
            if not cand_url:
                continue
            m3u8_out = _spawn_ffmpeg(channel_id, cand_url)
            for _ in range(28):
                if m3u8_out.exists() and m3u8_out.stat().st_size > 40:
                    return True
                if ACTIVE_STREAMS[channel_id]["proc"].poll() is not None:
                    break
                time.sleep(0.25)

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
    while True:
        time.sleep(15)
        now = time.time()
        with STREAM_LOCK:
            to_stop = [
                cid for cid, inf in ACTIVE_STREAMS.items()
                if (now - inf["last_access"] > 120) or (inf["proc"].poll() is not None)
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


def make_slug(text):
    s = re.sub(r"[^\w\s-]", "", str(text), flags=re.UNICODE).strip()
    return re.sub(r"[\s_]+", "-", s)


def sanitize_channel_public(ch):
    return {
        "id": ch["id"],
        "num": ch.get("num", "1"),
        "name": ch["name"],
        "category": ch.get("category", "beIN Sports"),
        "quality": ch.get("quality", "1080p FHD"),
        "desc": ch.get("desc", ""),
        "commentator": ch.get("commentator", "بث مباشر")
    }


def fetch_matches_list(date_offset=0, comp_filter=""):
    target_date = (datetime.now() + timedelta(days=date_offset)).strftime("%d/%m/%Y")
    if comp_filter and str(comp_filter).isdigit():
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

    raw = cached_fetch_json(url, ttl=30)
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

        status_group = g.get("statusGroup", 2)
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
        home_name = h.get("name", "")
        away_name = a.get("name", "")
        seo_slug = make_slug(f"مشاهدة-مباراة-{home_name}-و-{away_name}-بث-مباشر")

        matches.append({
            "id": gid,
            "slug": seo_slug,
            "url": f"/match/{gid}/{seo_slug}",
            "competition_id": cid,
            "competition_name": comp_name,
            "competition_logo": f"https://imagecache.365scores.com/image/upload/f_png,w_64,h_64,c_limit,q_auto:eco,dpr_2,d_Countries:Round:default.png/v1/Competitions/{cid}",
            "home_name": home_name,
            "home_score": int(h["score"]) if h.get("score", -1) >= 0 else None,
            "home_logo": f"https://imagecache.365scores.com/image/upload/f_png,w_96,h_96,c_limit,q_auto:eco,dpr_2,d_Competitors:default1.png/v1/Competitors/{h.get('id')}",
            "away_name": away_name,
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
            "channel_name": ch_obj.get("name", "beIN Sports 1 4K"),
            "channel_quality": ch_obj.get("quality", "4K Ultra HD"),
            "commentator": commentator,
            "priority": priority
        })

    matches.sort(key=lambda m: (0 if m["is_live"] else (1 if not m["is_ended"] else 2), m["priority"], m["start_iso"]))
    return target_date, matches


# --- OFFICIAL TMDB ARABIC VOD CATALOG ENGINE (MOVIES, SERIES, ANIME) ---

def build_vod_servers(tmdb_id, imdb_id="", media_type="movie", season=1, episode=1):
    """Returns 6 multi-server embed URLs supporting both TMDB ID and IMDb ID."""
    vid_id = imdb_id if (imdb_id and str(imdb_id).startswith("tt")) else tmdb_id
    if media_type == "movie":
        return [
            {"id": "srv1", "name": "سيرفر 1 (VidAPI HD)",    "url": f"https://vidapi.ru/embed/movie/{vid_id}"},
            {"id": "srv2", "name": "سيرفر 2 (VidSrc Pro)",   "url": f"https://vidsrc.xyz/embed/movie?tmdb={tmdb_id}"},
            {"id": "srv3", "name": "سيرفر 3 (MultiEmbed)",   "url": f"https://multiembed.mov/?video_id={tmdb_id}&tmdb=1"},
            {"id": "srv4", "name": "سيرفر 4 (2Embed FHD)",   "url": f"https://www.2embed.cc/embed/{vid_id}"},
            {"id": "srv5", "name": "سيرفر 5 (AutoEmbed)",    "url": f"https://player.autoembed.cc/embed/movie/{tmdb_id}"},
            {"id": "srv6", "name": "سيرفر 6 (VidSrc Me)",    "url": f"https://vidsrc.me/embed/movie?tmdb={tmdb_id}"},
        ]
    else:
        return [
            {"id": "srv1", "name": "سيرفر 1 (VidAPI HD)",    "url": f"https://vidapi.ru/embed/tv/{vid_id}/{season}/{episode}"},
            {"id": "srv2", "name": "سيرفر 2 (VidSrc Pro)",   "url": f"https://vidsrc.xyz/embed/tv?tmdb={tmdb_id}&season={season}&episode={episode}"},
            {"id": "srv3", "name": "سيرفر 3 (MultiEmbed)",   "url": f"https://multiembed.mov/?video_id={tmdb_id}&tmdb=1&s={season}&e={episode}"},
            {"id": "srv4", "name": "سيرفر 4 (2Embed FHD)",   "url": f"https://www.2embed.cc/embedtv/{vid_id}&s={season}&e={episode}"},
            {"id": "srv5", "name": "سيرفر 5 (AutoEmbed)",    "url": f"https://player.autoembed.cc/embed/tv/{tmdb_id}/{season}/{episode}"},
            {"id": "srv6", "name": "سيرفر 6 (VidSrc Me)",    "url": f"https://vidsrc.me/embed/tv?tmdb={tmdb_id}&season={season}&episode={episode}"},
        ]


def normalize_tmdb_item(m, category="movie"):
    tmdb_id = m.get("id")
    if not tmdb_id:
        return None
    is_movie = (category == "movie")
    title = m.get("title") or m.get("name") or m.get("original_title") or m.get("original_name") or "بدون عنوان"
    orig_title = m.get("original_title") or m.get("original_name") or title
    date_str = m.get("release_date") or m.get("first_air_date") or ""
    year = str(date_str)[:4] if date_str else "2026"
    vote = m.get("vote_average")
    rating = f"{float(vote):.1f}" if vote else "8.2"

    poster_path = m.get("poster_path")
    backdrop_path = m.get("backdrop_path")
    poster = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else ""
    backdrop = f"https://image.tmdb.org/t/p/w1280{backdrop_path}" if backdrop_path else poster

    genre_ids = m.get("genre_ids") or [g.get("id") for g in (m.get("genres") or []) if g.get("id")]
    genres_ar = [TMDB_GENRE_NAMES_AR.get(gid, "دراما") for gid in genre_ids[:2] if gid in TMDB_GENRE_NAMES_AR]
    if not genres_ar:
        genres_ar = ["أنمي مترجم"] if category == "anime" else ["مترجم FHD"]

    overview = (m.get("overview") or "").strip()
    if not overview:
        overview = f"شاهد {title} ({orig_title}) إنتاج عام {year} مترجم للعربية بجودة 4K & Full HD على منصة سينمانا لايف."

    media_type = "movie" if is_movie else "series"
    slug = make_slug(f"مشاهدة-{title}-{year}-مترجم")

    return {
        "tmdb_id": str(tmdb_id),
        "imdb_id": str(m.get("imdb_id") or tmdb_id),
        "title": title,
        "original_title": orig_title,
        "year": year,
        "rating": rating,
        "poster": poster,
        "backdrop": backdrop,
        "genres": genres_ar,
        "description": overview,
        "media_type": media_type,
        "category": category,
        "slug": slug,
        "url": f"/watch/{media_type}/{tmdb_id}/{slug}"
    }


def fetch_vod_catalog(category="movie", genre="", search=""):
    if search:
        q = urllib.parse.quote(search.strip())
        mtype = "movie" if category == "movie" else "tv"
        raw_p1 = tmdb_get(f"search/{mtype}?query={q}&language=ar-SA&page=1", ttl=300)
        results = raw_p1.get("results", [])
    elif category == "anime":
        # Japanese Anime TV Series sorted by popularity (Page 1 + Page 2 = 40 items)
        p1 = tmdb_get("discover/tv?language=ar-SA&with_genres=16&with_origin_country=JP&sort_by=popularity.desc&page=1", ttl=600)
        p2 = tmdb_get("discover/tv?language=ar-SA&with_genres=16&with_origin_country=JP&sort_by=popularity.desc&page=2", ttl=600)
        results = (p1.get("results") or []) + (p2.get("results") or [])
    elif category == "series":
        if genre and genre in TMDB_GENRE_MAP:
            gid = TMDB_GENRE_MAP[genre][1]
            p1 = tmdb_get(f"discover/tv?language=ar-SA&with_genres={gid}&sort_by=popularity.desc&page=1", ttl=600)
            p2 = tmdb_get(f"discover/tv?language=ar-SA&with_genres={gid}&sort_by=popularity.desc&page=2", ttl=600)
        else:
            p1 = tmdb_get("trending/tv/week?language=ar-SA&page=1", ttl=600)
            p2 = tmdb_get("tv/popular?language=ar-SA&page=2", ttl=600)
        results = (p1.get("results") or []) + (p2.get("results") or [])
    else:
        if genre and genre in TMDB_GENRE_MAP:
            gid = TMDB_GENRE_MAP[genre][0]
            p1 = tmdb_get(f"discover/movie?language=ar-SA&with_genres={gid}&sort_by=popularity.desc&page=1", ttl=600)
            p2 = tmdb_get(f"discover/movie?language=ar-SA&with_genres={gid}&sort_by=popularity.desc&page=2", ttl=600)
        else:
            p1 = tmdb_get("trending/movie/week?language=ar-SA&page=1", ttl=600)
            p2 = tmdb_get("movie/popular?language=ar-SA&page=2", ttl=600)
        results = (p1.get("results") or []) + (p2.get("results") or [])

    seen = set()
    items = []
    for m in results:
        tid = m.get("id")
        if not tid or tid in seen or not m.get("poster_path"):
            continue
        seen.add(tid)
        norm = normalize_tmdb_item(m, category=category)
        if norm:
            items.append(norm)
    return items


def fetch_vod_detail(media_type, item_id):
    is_movie = (media_type == "movie")
    endpoint = "movie" if is_movie else "tv"
    raw = tmdb_get(f"{endpoint}/{item_id}?language=ar-SA&append_to_response=external_ids", ttl=900)
    if not raw or not raw.get("id"):
        return None

    # If Arabic overview is empty, fall back to English overview from TMDB
    if not (raw.get("overview") or "").strip():
        try:
            raw_en = tmdb_get(f"{endpoint}/{item_id}?language=en-US", ttl=900)
            if raw_en.get("overview"):
                raw["overview"] = raw_en["overview"]
        except Exception:
            pass

    ext = raw.get("external_ids") or {}
    imdb_id = ext.get("imdb_id") or raw.get("imdb_id") or ""
    raw["imdb_id"] = imdb_id

    norm = normalize_tmdb_item(raw, category="movie" if is_movie else "series")
    norm["imdb_id"] = imdb_id or str(raw["id"])

    seasons_list = []
    if not is_movie:
        for s in (raw.get("seasons") or []):
            s_num = int(s.get("season_number") or 0)
            ep_count = int(s.get("episode_count") or 0)
            if s_num > 0 and ep_count > 0:
                seasons_list.append({"season": s_num, "episodes": ep_count, "name": s.get("name") or f"الموسم {s_num}"})
        if not seasons_list:
            seasons_list = [{"season": 1, "episodes": 12, "name": "الموسم 1"}]

    norm["seasons"] = seasons_list
    norm["servers"] = build_vod_servers(str(raw["id"]), imdb_id, "movie" if is_movie else "series", 1, 1)
    return norm


# --- SSR MULTI-PAGE & SEO RENDERING ENGINE ---

def render_seo_page(title, description, keywords, canonical_path="/", schema_list=None, seo_article_html="", boot_state=None):
    html_tpl = (BASE_DIR / "index.html").read_text(encoding="utf-8")
    base_url = request.host_url.rstrip("/")
    if request.headers.get("X-Forwarded-Proto") == "https" and base_url.startswith("http://"):
        base_url = "https://" + base_url[len("http://"):]

    canonical_url = f"{base_url}{canonical_path}"
    schemas_json = json.dumps(schema_list or [], ensure_ascii=False)
    boot_json = json.dumps(boot_state or {}, ensure_ascii=False)

    seo_head = f"""
  <title>{title}</title>
  <meta name="description" content="{description}" />
  <meta name="keywords" content="{keywords}" />
  <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1" />
  <link rel="canonical" href="{canonical_url}" />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="سينمانا لايف - Cinemana Live" />
  <meta property="og:locale" content="ar_IQ" />
  <meta property="og:title" content="{title}" />
  <meta property="og:description" content="{description}" />
  <meta property="og:url" content="{canonical_url}" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{title}" />
  <meta name="twitter:description" content="{description}" />
  <script type="application/ld+json">{schemas_json}</script>
  <script>window.__BOOT_STATE__ = {boot_json};</script>
"""
    html_out = html_tpl.replace("<!-- __SEO_HEAD__ -->", seo_head)
    html_out = html_out.replace("<!-- __SEO_ARTICLE__ -->", seo_article_html)
    return Response(html_out, mimetype="text/html; charset=utf-8")


# --- MULTI-PAGE ROUTES ---

@app.route("/")
def index():
    base_url = request.host_url.rstrip("/")
    title = "سينمانا لايف | Cinemana Live - بث مباشر للمباريات ومشاهدة الأفلام والمسلسلات والأنمي 4K"
    desc = (
        "منصة سينمانا لايف (Cinemana Live) الترفيهية والرياضية الأولى: شاهد مباريات اليوم بث مباشر بدقة 4K & FHD على قنوات beIN Sports "
        "واستمتع بأحدث الأفلام والمسلسلات العالمية والأنمي المترجم على أكثر من 6 سيرفرات سريعة بدون تقطيع."
    )
    kw = (
        "سينمانا, سينمانا لايف, cinemana, cinemana live, شبكتي سينمانا, بث مباشر للمباريات, مشاهدة افلام مترجمة, "
        "مسلسلات اجنبية, انمي مترجم, beIN Sports 1 4K, مباريات اليوم بث مباشر, دوري أبطال أوروبا, الدوري الإنجليزي"
    )
    schemas = [
        {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "سينمانا لايف - Cinemana Live",
            "alternateName": "Cinemana Live Sports & Movies",
            "url": base_url + "/",
            "potentialAction": {
                "@type": "SearchAction",
                "target": f"{base_url}/movies?q={{search_term_string}}",
                "query-input": "required name=search_term_string"
            }
        }
    ]
    return render_seo_page(title, desc, kw, "/", schemas, "", {"page": "home"})


@app.route("/matches")
def matches_page():
    title = "جدول مباريات اليوم والغد والبث المباشر | سينمانا لايف Cinemana Live"
    desc = "تعرف على جدول مواعيد مباريات اليوم والغد ونتائج مباريات الأمس في جميع الدوريات الأوروبية والعربية مع البث المباشر 4K على سينمانا لايف."
    kw = "جدول مباريات اليوم, مواعيد مباريات اليوم, مباريات الغد, نتائج المباريات, سينمانا لايف, cinemana live"
    return render_seo_page(title, desc, kw, "/matches", [], "", {"page": "matches"})


@app.route("/channels")
def channels_page():
    title = "القنوات الرياضية المباشرة (beIN Sports 1-5 4K & FHD) | سينمانا لايف"
    desc = "شاهد البث المباشر لقنوات beIN Sports الرياضية من 1 إلى 5 بجودات 4K Ultra HD و Full HD 1080p و 720p HD على مدار الساعة عبر منصة سينمانا لايف."
    kw = "قنوات بين سبورت بث مباشر, beIN Sports 1 4K, beIN Sports 2 4K, بث مباشر قنوات رياضية, سينمانا لايف"
    return render_seo_page(title, desc, kw, "/channels", [], "", {"page": "channels"})


@app.route("/movies")
def movies_page():
    title = "مشاهدة أحدث الأفلام الأجنبية والعالمية مترجمة FHD & 4K | سينمانا لايف"
    desc = "تصفح وشاهد أحدث الأفلام العالمية والأمريكية المترجمة بجودات 4K و BluRay مع القصة بالعربية وتقييمات TMDB/IMDb على 6 سيرفرات سريعة عبر سينمانا لايف."
    kw = "مشاهدة افلام, افلام مترجمة, افلام اجنبية 2026, سينمانا افلام, cinemana movies, ايجي بست, فاصل اعلاني"
    return render_seo_page(title, desc, kw, "/movies", [], "", {"page": "movies"})


@app.route("/series")
def series_page():
    title = "مشاهدة المسلسلات الأجنبية والعالمية المترجمة كامل | سينمانا لايف"
    desc = "شاهد جميع مواسم وحلقات أشهر المسلسلات الأجنبية والعالمية المترجمة بجودة Full HD على 6 سيرفرات مشاهدة مباشرة عبر سينمانا لايف."
    kw = "مسلسلات اجنبية, مشاهدة مسلسلات مترجمة, سينمانا مسلسلات, cinemana series, مسلسلات نتفلكس"
    return render_seo_page(title, desc, kw, "/series", [], "", {"page": "series"})


@app.route("/anime")
def anime_page():
    title = "مشاهدة الأنمي المترجم وحلقات الأنمي الجديدة FHD | سينمانا لايف"
    desc = "قسم الأنمي المترجم على سينمانا لايف: شاهد أشهر مسلسلات وأفلام الأنمي الياباني المترجمة بجودة خارقة وجميع المواسم والحلقات."
    kw = "انمي مترجم, مشاهدة انمي, انميات 2026, ون بيس, هجوم العمالقة, سينمانا انمي, anime streaming"
    return render_seo_page(title, desc, kw, "/anime", [], "", {"page": "anime"})


@app.route("/standings")
def standings_page():
    title = "جداول ترتيب الدوريات الأوروبية والعربية 2026 | سينمانا لايف Cinemana Live"
    desc = "تابع جدول ترتيب الدوري الإنجليزي، الدوري الإسباني، دوري أبطال أوروبا، الدوري الإيطالي، الدوري الألماني، ودوري نجوم العراق محدثاً لحظة بلحظة."
    kw = "جدول ترتيب الدوري الإنجليزي, ترتيب الدوري الإسباني, ترتيب دوري أبطال أوروبا, ترتيب الدوري العراقي, سينمانا لايف"
    return render_seo_page(title, desc, kw, "/standings", [], "", {"page": "standings", "initial_league": "7"})


@app.route("/leagues")
def leagues_directory_page():
    title = "البطولات والدوريات العالمية والعربية | سينمانا لايف Cinemana Live"
    desc = "تصفح جميع أقسام الدوريات والبطولات الكبرى على سينمانا لايف: دوري أبطال أوروبا، البريميرليغ، لاليغا، الكالتشيو، البوندسليغا، ودوري نجوم العراق."
    kw = "الدوريات الأوروبية, البطولات العالمية, دوري أبطال أوروبا, الدوري الإنجليزي, سينمانا لايف"
    return render_seo_page(title, desc, kw, "/leagues", [], "", {"page": "leagues"})


@app.route("/watch/<media_type>/<item_id>")
@app.route("/watch/<media_type>/<item_id>/<path:slug>")
def watch_vod_seo_page(media_type, item_id, slug=""):
    try:
        item = fetch_vod_detail(media_type, item_id)
    except Exception:
        item = None

    if not item:
        return index()

    t = item["title"]
    ot = item.get("original_title", "")
    yr = item["year"]
    rt = item["rating"]
    type_ar = "فيلم" if media_type == "movie" else "مسلسل / أنمي"
    title = f"مشاهدة {type_ar} {t} ({yr}) مترجم كامل Full HD | سينمانا لايف Cinemana Live"
    desc = f"شاهد {type_ar} {t} ({ot} - {yr}) مترجم للعربية بجودة 1080p Full HD و 4K بتقييم {rt}/10 على 6 سيرفرات سريعة بدون تقطيع عبر سينمانا لايف: {item['description'][:140]}"
    kw = f"مشاهدة {t}, {type_ar} {t} مترجم, {ot} {yr}, {t} سينمانا, cinemana {t}, تحميل {t}"

    schema = [
        {
            "@context": "https://schema.org",
            "@type": "Movie" if media_type == "movie" else "TVSeries",
            "name": t,
            "alternateName": ot,
            "datePublished": yr,
            "image": item["poster"],
            "description": item["description"],
            "aggregateRating": {
                "@type": "AggregateRating",
                "ratingValue": rt,
                "bestRating": "10",
                "ratingCount": "14200"
            }
        }
    ]

    article_html = f"""
    <section class="seo-banner-card">
      <div class="seo-banner-badge">🎬 سينمانا لايف • تقييم ⭐ {rt}</div>
      <h1>مشاهدة {type_ar} {t} ({yr}) مترجم كامل Full HD</h1>
      <p>{item['description']}</p>
    </section>
    """
    boot = {"page": "watch_vod", "vod_item": item}
    return render_seo_page(title, desc, kw, item["url"], schema, article_html, boot)


@app.route("/match/<game_id>")
@app.route("/match/<game_id>/<path:slug>")
def match_seo_page(game_id, slug=""):
    target_Match = None
    for offset in (0, 1, -1):
        try:
            _, matches = fetch_matches_list(date_offset=offset)
            for m in matches:
                if str(m["id"]) == str(game_id):
                    target_Match = m
                    break
            if target_Match:
                break
        except Exception:
            pass

    if not target_Match:
        return index()

    h = target_Match["home_name"]
    a = target_Match["away_name"]
    comp = target_Match["competition_name"]
    ch_name = target_Match["channel_name"]
    comm = target_Match["commentator"]
    stime = target_Match["start_time"] or "اليوم"
    sdate = target_Match["start_date"] or datetime.now().strftime("%Y-%m-%d")

    title = f"مشاهدة مباراة {h} ضد {a} بث مباشر اليوم ({comp}) | سينمانا لايف"
    desc = (
        f"بث مباشر مشاهدة مباراة {h} و {a} اليوم في بطولة {comp} عبر قناة {ch_name} بتعليق {comm} "
        f"الساعة {stime} بتوقيت بغداد ومكة المكرمة بجودة 4K و FHD بدون تقطيع على سينمانا لايف Cinemana Live."
    )
    kw = (
        f"مشاهدة مباراة {h} و {a}, بث مباشر {h} ضد {a}, مباراة {h} اليوم, مباراة {a} اليوم, "
        f"{comp} بث مباشر, قناة {ch_name} بث مباشر, سينمانا لايف, cinemana live"
    )

    schema = [
        {
            "@context": "https://schema.org",
            "@type": "SportsEvent",
            "name": f"مباراة {h} ضد {a} - {comp}",
            "description": desc,
            "startDate": target_Match["start_iso"] or sdate,
            "eventStatus": "https://schema.org/EventScheduled",
            "homeTeam": {"@type": "SportsTeam", "name": h, "logo": target_Match["home_logo"]},
            "awayTeam": {"@type": "SportsTeam", "name": a, "logo": target_Match["away_logo"]},
            "organizer": {"@type": "Organization", "name": comp}
        }
    ]

    article_html = f"""
    <section class="seo-banner-card">
      <div class="seo-banner-badge">🔴 تغطية مباشرة للمباراة</div>
      <h1>مشاهدة مباراة {h} ضد {a} بث مباشر اليوم في {comp}</h1>
      <p>
        يقدم لكم موقع <strong>سينمانا لايف (Cinemana Live)</strong> البث المباشر لمباراة <strong>{h}</strong> أمام نظيره <strong>{a}</strong>
        ضمن منافسات بطولة <strong>{comp}</strong>. تنطلق صافرة بداية اللقاء اليوم <strong>{sdate}</strong> في تمام الساعة <strong>{stime}</strong> بتوقيت بغداد ومكة المكرمة،
        وتنقل المباراة عبر قناة <strong>{ch_name} ({target_Match['channel_quality']})</strong> بصوت المعلق <strong>{comm}</strong>.
      </p>
    </section>
    """

    boot = {
        "page": "match_detail",
        "auto_channel": target_Match["channel_id"],
        "match_title": f"{h} ضد {a} ({comp})",
        "match_obj": target_Match
    }
    return render_seo_page(title, desc, kw, target_Match["url"], schema, article_html, boot)


@app.route("/league/<comp_id>")
@app.route("/league/<comp_id>/<path:slug>")
def league_seo_page(comp_id, slug=""):
    lg = LEAGUES_BY_ID.get(str(comp_id))
    if not lg:
        return index()

    name = lg["name"]
    title = f"جدول ترتيب ومباريات {name} بث مباشر اليوم | سينمانا لايف Cinemana Live"
    desc = lg["seo_desc"]
    kw = f"{name}, بث مباشر {name}, جدول ترتيب {name}, مباريات {name} اليوم, نتائج {name}, سينمانا لايف, cinemana live"

    article_html = f"""
    <section class="seo-banner-card">
      <div class="seo-banner-badge">{lg['badge']} القسم الخاص بالبطولة</div>
      <h1>مباريات وجدول ترتيب {name} بث مباشر</h1>
      <p>
        {desc} تابع جميع مواعيد المباريات والنتائج الفورية وترتيب الفرق والنقاط في <strong>{name}</strong> مع البث الحي عبر قنوات beIN Sports 4K & FHD.
      </p>
    </section>
    """
    boot = {"page": "league_detail", "initial_league": str(comp_id)}
    return render_seo_page(title, desc, kw, f"/league/{comp_id}/{lg['slug']}", [], article_html, boot)


@app.route("/channel/<channel_id>")
def channel_seo_page(channel_id):
    db = load_db()
    ch = next((c for c in db.get("channels", DEFAULT_CHANNELS) if c["id"] == channel_id), None)
    if not ch:
        return index()

    cname = ch["name"]
    cqual = ch["quality"]
    title = f"بث مباشر قناة {cname} ({cqual}) بدون تقطيع 24 ساعة | سينمانا لايف"
    desc = f"مشاهدة قناة {cname} بث مباشر بجودة {cqual} بدون تقطيع مجاناً على الجوال والكمبيوتر لنقل أهم المباريات العالمية والأوروبية عبر سينمانا لايف Cinemana Live."
    kw = f"قناة {cname} بث مباشر, مشاهدة {cname} بدون تقطيع, {cname} live, بث مباشر بين سبورت {ch['num']}, سينمانا لايف"

    article_html = f"""
    <section class="seo-banner-card">
      <div class="seo-banner-badge">📺 البث الحي للقناة • {cqual}</div>
      <h1>بث مباشر قناة {cname} ({cqual}) بدون تقطيع</h1>
      <p>
        {ch.get('desc', '')} شاهد الآن البث الحي المباشر لقناة <strong>{cname}</strong> بدقة <strong>{cqual}</strong> على مدار الساعة عبر مشغل سينمانا لايف السريع.
      </p>
    </section>
    """
    boot = {"page": "channel_detail", "auto_channel": channel_id, "match_title": f"البث المباشر لقناة {cname} ({cqual})"}
    return render_seo_page(title, desc, kw, f"/channel/{channel_id}", [], article_html, boot)


@app.route("/sitemap.xml")
def sitemap_xml():
    base_url = request.host_url.rstrip("/")
    if request.headers.get("X-Forwarded-Proto") == "https" and base_url.startswith("http://"):
        base_url = "https://" + base_url[len("http://"):]

    now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    urls = [
        (f"{base_url}/", "1.0", "always"),
        (f"{base_url}/matches", "0.95", "always"),
        (f"{base_url}/channels", "0.95", "hourly"),
        (f"{base_url}/movies", "0.95", "daily"),
        (f"{base_url}/series", "0.95", "daily"),
        (f"{base_url}/anime", "0.95", "daily"),
        (f"{base_url}/standings", "0.90", "hourly"),
        (f"{base_url}/leagues", "0.90", "daily"),
    ]

    for ch in DEFAULT_CHANNELS:
        urls.append((f"{base_url}/channel/{ch['id']}", "0.9", "hourly"))

    for lg in LEAGUES:
        urls.append((f"{base_url}/league/{lg['id']}/{urllib.parse.quote(lg['slug'])}", "0.9", "hourly"))

    seen_ids = set()
    for offset in (0, 1, -1):
        try:
            _, matches = fetch_matches_list(date_offset=offset)
            for m in matches:
                if m["id"] not in seen_ids:
                    seen_ids.add(m["id"])
                    encoded_slug = urllib.parse.quote(m["slug"])
                    urls.append((f"{base_url}/match/{m['id']}/{encoded_slug}", "0.85", "hourly"))
        except Exception:
            pass

    for cat in ("movie", "series", "anime"):
        try:
            vod_items = fetch_vod_catalog(category=cat)
            for v in vod_items[:40]:
                mtype = v["media_type"]
                enc_slug = urllib.parse.quote(v["slug"])
                urls.append((f"{base_url}/watch/{mtype}/{v['tmdb_id']}/{enc_slug}", "0.85", "weekly"))
        except Exception:
            pass

    xml_items = "\n".join([
        f"  <url>\n    <loc>{u}</loc>\n    <lastmod>{now_iso}</lastmod>\n    <changefreq>{freq}</changefreq>\n    <priority>{prio}</priority>\n  </url>"
        for u, prio, freq in urls
    ])
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{xml_items}
</urlset>"""
    return Response(xml, mimetype="application/xml; charset=utf-8")


@app.route("/robots.txt")
def robots_txt():
    base_url = request.host_url.rstrip("/")
    if request.headers.get("X-Forwarded-Proto") == "https" and base_url.startswith("http://"):
        base_url = "https://" + base_url[len("http://"):]
    txt = f"""User-agent: *
Allow: /
Sitemap: {base_url}/sitemap.xml
"""
    return Response(txt, mimetype="text/plain; charset=utf-8")


# --- JSON API ENDPOINTS ---

@app.route("/api/init")
def api_init():
    db = load_db()
    public_channels = [sanitize_channel_public(c) for c in db.get("channels", DEFAULT_CHANNELS)]
    return jsonify({
        "leagues": LEAGUES,
        "channels": public_channels,
        "active_streams": list(ACTIVE_STREAMS.keys())
    })


@app.route("/api/matches")
def api_matches():
    date_offset = int(request.args.get("offset", "0"))
    comp_filter = request.args.get("competition_id", "")
    try:
        target_date, matches = fetch_matches_list(date_offset=date_offset, comp_filter=comp_filter)
        live_count = sum(1 for m in matches if m["is_live"])
        return jsonify({
            "date": target_date,
            "total": len(matches),
            "live_count": live_count,
            "matches": matches[:120]
        })
    except Exception as e:
        return jsonify({"error": str(e), "matches": []}), 500


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


@app.route("/api/vod/catalog")
def api_vod_catalog():
    category = request.args.get("category", "movie")
    genre = request.args.get("genre", "")
    search = request.args.get("q", "")
    try:
        items = fetch_vod_catalog(category=category, genre=genre, search=search)
        return jsonify({"category": category, "total": len(items), "items": items})
    except Exception as e:
        return jsonify({"error": str(e), "items": []}), 500


@app.route("/api/vod/meta/<media_type>/<item_id>")
def api_vod_meta(media_type, item_id):
    try:
        detail = fetch_vod_detail(media_type, item_id)
        if not detail:
            return jsonify({"error": "Not found"}), 404
        return jsonify(detail)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/stream/<channel_id>")
def api_get_stream(channel_id):
    db = load_db()
    channels = {c["id"]: c for c in db.get("channels", DEFAULT_CHANNELS)}
    ch = channels.get(channel_id)
    if not ch:
        return jsonify({"error": "Channel not found"}), 404

    src = ch.get("source_url", "")
    use_restream = ch.get("use_restream", True)
    max_conn = db.get("iptv_panel", {}).get("max_connections", 5)

    if use_restream and src:
        ok = start_restream_process(channel_id, ch, max_conn=max_conn)
        return jsonify({
            "channel": sanitize_channel_public(ch),
            "ready": ok,
            "play_url": f"/hls/{channel_id}/index.m3u8?t={int(time.time())}"
        })

    return jsonify({
        "channel": sanitize_channel_public(ch),
        "ready": True,
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5080"))
    print(f"Starting Cinemana Live Server on http://0.0.0.0:{port} ...")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
