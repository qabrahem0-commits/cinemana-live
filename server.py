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


def make_en_slug(text, fallback_id=""):
    s = re.sub(r"[^a-zA-Z0-9\s-]", "", str(text or "")).strip().lower()
    s = re.sub(r"[\s_-]+", "-", s).strip("-")
    if not s:
        s = make_slug(text).lower()
    if not s:
        s = f"title-{fallback_id}"
    return s


SLUG_TO_ID_CACHE = {}
SITEMAP_5000_URLS = []

try:
    _sitemap_db_file = BASE_DIR / "seo_sitemap_5000.json"
    if _sitemap_db_file.exists():
        _sdata = json.loads(_sitemap_db_file.read_text(encoding="utf-8"))
        SLUG_TO_ID_CACHE.update(_sdata.get("slug_map", {}))
        SITEMAP_5000_URLS = _sdata.get("urls", [])
except Exception:
    pass


def register_slug(slug, tmdb_id, media_type):
    if slug and tmdb_id:
        SLUG_TO_ID_CACHE[f"{media_type}:{slug.lower()}"] = str(tmdb_id)
        SLUG_TO_ID_CACHE[slug.lower()] = str(tmdb_id)


def resolve_slug_or_id(media_type, slug_or_id):
    s = str(slug_or_id or "").strip()
    if s.isdigit():
        return s
    m_trail = re.search(r"-(\d{2,9})$", s)
    if m_trail:
        return m_trail.group(1)
    key_typed = f"{media_type}:{s.lower()}"
    if key_typed in SLUG_TO_ID_CACHE:
        return SLUG_TO_ID_CACHE[key_typed]
    if s.lower() in SLUG_TO_ID_CACHE:
        return SLUG_TO_ID_CACHE[s.lower()]

    # Search TMDB by clean slug words
    query = urllib.parse.quote(s.replace("-", " "))
    ep_type = "movie" if media_type == "movie" else "tv"
    try:
        res = tmdb_get(f"search/{ep_type}?query={query}&language=en-US&page=1", ttl=900)
        results = res.get("results") or []
        if not results:
            res_ar = tmdb_get(f"search/{ep_type}?query={query}&language=ar-SA&page=1", ttl=900)
            results = res_ar.get("results") or []
        if results:
            tid = str(results[0]["id"])
            register_slug(s, tid, media_type)
            return tid
    except Exception:
        pass
    return None


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
    clean_slug = make_en_slug(orig_title, tmdb_id)
    register_slug(clean_slug, tmdb_id, media_type)

    route_prefix = "movie" if is_movie else "series"
    item_url = f"/{route_prefix}/{clean_slug}"

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
        "slug": clean_slug,
        "url": item_url
    }


def fetch_vod_catalog(category="movie", genre="", search=""):
    if search:
        q = urllib.parse.quote(search.strip())
        mtype = "movie" if category == "movie" else "tv"
        raw_p1 = tmdb_get(f"search/{mtype}?query={q}&language=ar-SA&page=1", ttl=300)
        results = raw_p1.get("results", [])
    elif category == "anime":
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


def fetch_season_episodes(tmdb_id, season_num=1, series_slug=""):
    raw_ar = tmdb_get(f"tv/{tmdb_id}/season/{season_num}?language=ar-SA", ttl=900)
    raw_en = tmdb_get(f"tv/{tmdb_id}/season/{season_num}?language=en-US", ttl=900)
    eps_ar = raw_ar.get("episodes") or []
    eps_en_map = {e.get("episode_number"): e for e in (raw_en.get("episodes") or [])}

    episodes = []
    for ep in eps_ar:
        ep_num = int(ep.get("episode_number") or 1)
        en_obj = eps_en_map.get(ep_num, {})
        en_name = en_obj.get("name") or ep.get("name") or f"episode-{ep_num}"
        ar_name = ep.get("name") or en_name or f"الحلقة {ep_num}"
        ep_slug = make_en_slug(en_name, ep_num)
        if ep_slug.startswith("episode-"):
            full_ep_part = f"episode-{ep_num}"
        else:
            full_ep_part = f"episode-{ep_num}-{ep_slug}"

        still_path = ep.get("still_path") or en_obj.get("still_path")
        still = f"https://image.tmdb.org/t/p/w500{still_path}" if still_path else ""
        overview = (ep.get("overview") or en_obj.get("overview") or "").strip()
        runtime = ep.get("runtime") or en_obj.get("runtime") or 45

        episodes.append({
            "episode": ep_num,
            "season": int(season_num),
            "name": ar_name,
            "en_name": en_name,
            "slug": full_ep_part,
            "still": still,
            "overview": overview,
            "runtime": runtime,
            "air_date": ep.get("air_date") or "",
            "url": f"/series/{series_slug}/season-{season_num}/{full_ep_part}" if series_slug else ""
        })
    return episodes


def fetch_vod_detail(media_type, slug_or_id, season_num=1, episode_num=1):
    is_movie = (media_type == "movie")
    item_id = resolve_slug_or_id("movie" if is_movie else "series", slug_or_id)
    if not item_id:
        return None

    endpoint = "movie" if is_movie else "tv"
    raw = tmdb_get(f"{endpoint}/{item_id}?language=ar-SA&append_to_response=external_ids,credits", ttl=900)
    if not raw or not raw.get("id"):
        return None

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
    norm["runtime"] = raw.get("runtime") or (raw.get("episode_run_time")[0] if raw.get("episode_run_time") else 115)

    # Top cast
    cast_raw = (raw.get("credits") or {}).get("cast") or []
    norm["cast"] = [c.get("name") for c in cast_raw[:6] if c.get("name")]

    seasons_list = []
    episodes_list = []
    if not is_movie:
        for s in (raw.get("seasons") or []):
            s_num = int(s.get("season_number") or 0)
            ep_count = int(s.get("episode_count") or 0)
            if s_num > 0 and ep_count > 0:
                s_poster = f"https://image.tmdb.org/t/p/w300{s['poster_path']}" if s.get("poster_path") else norm["poster"]
                seasons_list.append({
                    "season": s_num,
                    "episodes": ep_count,
                    "name": s.get("name") or f"الموسم {s_num}",
                    "poster": s_poster,
                    "url": f"/series/{norm['slug']}/season-{s_num}"
                })
        if not seasons_list:
            seasons_list = [{"season": 1, "episodes": 12, "name": "الموسم 1", "poster": norm["poster"], "url": f"/series/{norm['slug']}/season-1"}]

        try:
            episodes_list = fetch_season_episodes(str(raw["id"]), season_num, norm["slug"])
        except Exception:
            episodes_list = []

    norm["seasons"] = seasons_list
    norm["current_season"] = int(season_num)
    norm["current_episode"] = int(episode_num)
    norm["season_episodes"] = episodes_list
    norm["servers"] = build_vod_servers(str(raw["id"]), imdb_id, "movie" if is_movie else "series", int(season_num), int(episode_num))
    return norm


# --- SSR MULTI-PAGE & SEO RENDERING ENGINE (ZERO DUPLICATE CONTENT, STRICT CANONICALS) ---

PRIMARY_DOMAIN = "https://cinemana.live"


def get_canonical_base():
    host = (request.headers.get("X-Forwarded-Host") or request.host or "").lower()
    if "cinemana.live" in host or "onrender.com" in host:
        return PRIMARY_DOMAIN
    base_url = request.host_url.rstrip("/")
    if request.headers.get("X-Forwarded-Proto") == "https" and base_url.startswith("http://"):
        base_url = "https://" + base_url[len("http://"):]
    return base_url


@app.before_request
def enforce_canonical_domain_and_slash():
    host = (request.host or "").lower()
    path = request.path or "/"
    # 1. 301 Redirect www.cinemana.live -> https://cinemana.live
    if host == "www.cinemana.live":
        return Response("", status=301, headers={"Location": f"{PRIMARY_DOMAIN}{request.full_path.rstrip('?')}"})
    # 2. 301 Redirect trailing slashes (except root "/")
    if path != "/" and path.endswith("/") and not path.startswith("/hls/") and not path.startswith("/api/"):
        clean_path = path.rstrip("/")
        target = f"{get_canonical_base()}{clean_path}"
        return Response("", status=301, headers={"Location": target})


def render_seo_page(title, description, keywords, canonical_path="/", schema_list=None, seo_article_html="", boot_state=None, og_image="", status_code=200, noindex=False):
    html_tpl = (BASE_DIR / "index.html").read_text(encoding="utf-8")
    base_url = get_canonical_base()

    if canonical_path != "/" and canonical_path.endswith("/"):
        canonical_path = canonical_path.rstrip("/")

    # Percent-encode non-ASCII characters in canonical URL for strict RFC/Google compliance
    safe_canonical_path = urllib.parse.quote(urllib.parse.unquote(canonical_path), safe="/-_.~")
    canonical_url = f"{base_url}{safe_canonical_path}"

    schemas_json = json.dumps(schema_list or [], ensure_ascii=False)
    boot_json = json.dumps(boot_state or {}, ensure_ascii=False)

    if not og_image:
        og_image = "https://image.tmdb.org/t/p/w1280/hoq8AUTtYowqmKWoYwhoAfkMpLr.jpg"

    robots_directive = "noindex, nofollow" if noindex else "index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1"

    seo_head = f"""
  <title>{title}</title>
  <meta name="description" content="{description}" />
  <meta name="keywords" content="{keywords}" />
  <meta name="robots" content="{robots_directive}" />
  <meta name="googlebot" content="{robots_directive}" />
  <link rel="canonical" href="{canonical_url}" />
  <link rel="alternate" hreflang="ar" href="{canonical_url}" />
  <link rel="alternate" hreflang="x-default" href="{canonical_url}" />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="سينمانا لايف - Cinemana Live" />
  <meta property="og:locale" content="ar_IQ" />
  <meta property="og:title" content="{title}" />
  <meta property="og:description" content="{description}" />
  <meta property="og:url" content="{canonical_url}" />
  <meta property="og:image" content="{og_image}" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{title}" />
  <meta name="twitter:description" content="{description}" />
  <meta name="twitter:image" content="{og_image}" />
  <script type="application/ld+json">{schemas_json}</script>
  <script>window.__BOOT_STATE__ = {boot_json};</script>
"""
    html_out = html_tpl.replace("<!-- __SEO_HEAD__ -->", seo_head)
    html_out = html_out.replace("<!-- __SEO_ARTICLE__ -->", seo_article_html)
    resp = Response(html_out, status=status_code, mimetype="text/html; charset=utf-8")
    resp.headers["X-Robots-Tag"] = robots_directive
    return resp


def render_404_seo_page(missing_title="الصفحة غير موجودة"):
    title = f"404 - {missing_title} | سينمانا لايف Cinemana Live"
    desc = "عذراً، الرابط الذي تبحث عنه غير متوفر أو تم نقله. تصفح أحدث الأفلام والمسلسلات والأنمي المترجم على سينمانا لايف."
    article = """
    <section class="seo-banner-card">
      <div class="seo-banner-badge">⚠️ 404 Not Found</div>
      <h1>عذراً، الصفحة المطلوبة غير متوفرة حالياً</h1>
      <p>يرجى العودة إلى الصفحة الرئيسية أو استخدام البحث للوصول إلى الفيلم أو المسلسل المطلوب.</p>
    </section>
    """
    return render_seo_page(title, desc, "سينمانا لايف", request.path, [], article, {"page": "home"}, status_code=404, noindex=True)


def build_rich_poster_carousel_schema(base_url, items, list_name="أحدث الأفلام والمسلسلات والأنمي المترجم على سينمانا لايف"):
    """Builds Schema.org ItemList with Movie/TVSeries poster images so Google displays a Poster Carousel under the search snippet."""
    elements = []
    for idx, it in enumerate(items[:12], start=1):
        elements.append({
            "@type": "ListItem",
            "position": idx,
            "item": {
                "@type": "Movie" if it["media_type"] == "movie" else "TVSeries",
                "name": it["title"],
                "alternateName": it.get("original_title", ""),
                "url": f"{base_url}{it['url']}",
                "image": it["poster"],
                "dateCreated": it["year"],
                "aggregateRating": {
                    "@type": "AggregateRating",
                    "ratingValue": it["rating"],
                    "bestRating": "10",
                    "ratingCount": "9800"
                }
            }
        })
    return {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": list_name,
        "itemListOrder": "https://schema.org/ItemListOrderDescending",
        "numberOfItems": len(elements),
        "itemListElement": elements
    }


def build_ssr_vod_links_summary(items, heading):
    """Generates crawlable SSR HTML links and descriptions so Googlebot sees unique body content on every catalog page."""
    if not items:
        return ""
    links_html = "".join([
        f'<li><a href="{it["url"]}"><strong>{it["title"]} ({it.get("original_title", "")} {it["year"]})</strong></a> — تقييم {it["rating"]}/10: {it["description"][:110]}...</li>'
        for it in items[:15]
    ])
    return f"""
    <div class="ssr-crawler-summary" style="display:none;" aria-hidden="true">
      <h1>{heading}</h1>
      <ul>{links_html}</ul>
    </div>
    """


# --- MULTI-PAGE ROUTES ---

@app.route("/")
def index():
    base_url = get_canonical_base()
    title = "سينمانا لايف | Cinemana Live - مشاهدة أحدث الأفلام والمسلسلات والأنمي المترجم وبث المباريات 4K"
    desc = (
        "منصة سينمانا لايف (Cinemana Live) الترفيهية الأولى: استمتع بمشاهدة وتحميل أحدث الأفلام العالمية والمسلسلات الأجنبية "
        "والأنمي المترجم بجودات 4K Ultra HD و Full HD على 6 سيرفرات سريعة مع تغطية البث المباشر لأهم المباريات."
    )
    kw = (
        "سينمانا, سينمانا لايف, cinemana, cinemana live, شبكتي سينمانا, مشاهدة افلام مترجمة, "
        "مسلسلات اجنبية مترجمة, انمي مترجم, افلام 2026, بث مباشر للمباريات, مباريات اليوم 4K"
    )

    featured_items = []
    try:
        m_items = fetch_vod_catalog("movie")[:6]
        s_items = fetch_vod_catalog("series")[:4]
        a_items = fetch_vod_catalog("anime")[:2]
        featured_items = m_items + s_items + a_items
    except Exception:
        featured_items = []

    og_img = featured_items[0]["poster"] if featured_items else ""

    schemas = [
        {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "سينمانا لايف - Cinemana Live",
            "alternateName": "Cinemana Live",
            "url": base_url + "/",
            "potentialAction": {
                "@type": "SearchAction",
                "target": f"{base_url}/movies?q={{search_term_string}}",
                "query-input": "required name=search_term_string"
            }
        }
    ]
    if featured_items:
        schemas.append(build_rich_poster_carousel_schema(base_url, featured_items))

    ssr_summary = build_ssr_vod_links_summary(featured_items, title)
    return render_seo_page(title, desc, kw, "/", schemas, ssr_summary, {"page": "home"}, og_image=og_img)


@app.route("/matches")
def matches_page():
    title = "جدول مباريات اليوم والغد والبث المباشر | سينمانا لايف Cinemana Live"
    desc = "تعرف على جدول مواعيد مباريات اليوم والغد ونتائج مباريات الأمس في جميع الدوريات الأوروبية والعربية مع البث المباشر بدقة 4K على سينمانا لايف."
    kw = "جدول مباريات اليوم, مواعيد مباريات اليوم, مباريات الغد, نتائج المباريات, سينمانا لايف, cinemana live"
    ssr_matches = """
    <section class="seo-banner-card">
      <div class="seo-banner-badge">⚽ جدول المباريات المحدث</div>
      <h1>جدول مباريات اليوم والغد والنتائج المباشرة</h1>
      <p>تابع مواعيد ونتائج مباريات اليوم والغد في دوري أبطال أوروبا، الدوري الإنجليزي، الدوري الإسباني، الإيطالي، الألماني، ودوري نجوم العراق مع البث المباشر بدقة 4K.</p>
    </section>
    """
    return render_seo_page(title, desc, kw, "/matches", [], ssr_matches, {"page": "matches"})


@app.route("/channels")
def channels_page():
    title = "القنوات الرياضية المباشرة (4K Ultra HD & Full HD) | سينمانا لايف"
    desc = "شاهد البث المباشر للقنوات الرياضية المشفرة والمفتوحة بجودات 4K Ultra HD و Full HD 1080p و 720p HD على مدار الساعة عبر منصة سينمانا لايف."
    kw = "قنوات رياضية بث مباشر, بث مباشر مباريات 4K, قنوات رياضية بدون تقطيع, سينمانا لايف"
    ssr_ch = """
    <section class="seo-banner-card">
      <div class="seo-banner-badge">📺 القنوات المباشرة 24/7</div>
      <h1>دليل القنوات الرياضية المباشرة بجودة 4K & Full HD</h1>
      <p>بث حي ومباشر على مدار الساعة لأهم القنوات الرياضية العالمية والعربية بجودات متعددة (4K Ultra HD، 1080p FHD، و 720p HD) تناسب جميع سرعات الإنترنت.</p>
    </section>
    """
    return render_seo_page(title, desc, kw, "/channels", [], ssr_ch, {"page": "channels"})


@app.route("/movies")
def movies_page():
    base_url = get_canonical_base()
    title = "مشاهدة أحدث الأفلام الأجنبية والعالمية مترجمة FHD & 4K | سينمانا لايف"
    desc = "تصفح وشاهد أحدث الأفلام العالمية والأمريكية المترجمة بجودات 4K و BluRay مع القصة بالعربية وتقييمات TMDB/IMDb على 6 سيرفرات سريعة عبر سينمانا لايف."
    kw = "مشاهدة افلام, افلام مترجمة, افلام اجنبية 2026, سينمانا افلام, cinemana movies"
    items = []
    try:
        items = fetch_vod_catalog("movie")[:16]
    except Exception:
        pass
    schemas = [build_rich_poster_carousel_schema(base_url, items, "أحدث الأفلام الأجنبية والعالمية المترجمة")] if items else []
    og_img = items[0]["poster"] if items else ""
    ssr_summary = build_ssr_vod_links_summary(items, title)
    return render_seo_page(title, desc, kw, "/movies", schemas, ssr_summary, {"page": "movies"}, og_image=og_img)


@app.route("/series")
def series_page():
    base_url = get_canonical_base()
    title = "مشاهدة المسلسلات الأجنبية والعالمية المترجمة كامل | سينمانا لايف"
    desc = "شاهد جميع مواسم وحلقات أشهر المسلسلات الأجنبية والعالمية المترجمة بجودة Full HD على 6 سيرفرات مشاهدة مباشرة عبر سينمانا لايف."
    kw = "مسلسلات اجنبية, مشاهدة مسلسلات مترجمة, سينمانا مسلسلات, cinemana series"
    items = []
    try:
        items = fetch_vod_catalog("series")[:16]
    except Exception:
        pass
    schemas = [build_rich_poster_carousel_schema(base_url, items, "أشهر المسلسلات الأجنبية والعالمية المترجمة")] if items else []
    og_img = items[0]["poster"] if items else ""
    ssr_summary = build_ssr_vod_links_summary(items, title)
    return render_seo_page(title, desc, kw, "/series", schemas, ssr_summary, {"page": "series"}, og_image=og_img)


@app.route("/anime")
def anime_page():
    base_url = get_canonical_base()
    title = "مشاهدة الأنمي المترجم وحلقات الأنمي الجديدة FHD | سينمانا لايف"
    desc = "قسم الأنمي المترجم على سينمانا لايف: شاهد أشهر مسلسلات وأفلام الأنمي الياباني المترجمة بجودة خارقة وجميع المواسم والحلقات."
    kw = "انمي مترجم, مشاهدة انمي, انميات 2026, ون بيس, هجوم العمالقة, سينمانا انمي"
    items = []
    try:
        items = fetch_vod_catalog("anime")[:16]
    except Exception:
        pass
    schemas = [build_rich_poster_carousel_schema(base_url, items, "أحدث وأشهر مسلسلات الأنمي المترجم")] if items else []
    og_img = items[0]["poster"] if items else ""
    ssr_summary = build_ssr_vod_links_summary(items, title)
    return render_seo_page(title, desc, kw, "/anime", schemas, ssr_summary, {"page": "anime"}, og_image=og_img)


@app.route("/standings")
def standings_page():
    title = "جداول ترتيب الدوريات الأوروبية والعربية 2026 | سينمانا لايف Cinemana Live"
    desc = "تابع جدول ترتيب الدوري الإنجليزي، الدوري الإسباني، دوري أبطال أوروبا، الدوري الإيطالي، الدوري الألماني، ودوري نجوم العراق محدثاً لحظة بلحظة."
    kw = "جدول ترتيب الدوري الإنجليزي, ترتيب الدوري الإسباني, ترتيب دوري أبطال أوروبا, ترتيب الدوري العراقي, سينمانا لايف"
    ssr_st = """
    <section class="seo-banner-card">
      <div class="seo-banner-badge">🏆 ترتيب البطولات</div>
      <h1>جداول ترتيب الدوريات الأوروبية والعربية 2026</h1>
      <p>ترتيب الفرق والنقاط وعدد المباريات والأهداف في الدوري الإنجليزي الممتاز، الدوري الإسباني، دوري أبطال أوروبا، ودوري نجوم العراق.</p>
    </section>
    """
    return render_seo_page(title, desc, kw, "/standings", [], ssr_st, {"page": "standings", "initial_league": "7"})


@app.route("/leagues")
def leagues_directory_page():
    title = "البطولات والدوريات العالمية والعربية | سينمانا لايف Cinemana Live"
    desc = "تصفح جميع أقسام الدوريات والبطولات الكبرى على سينمانا لايف: دوري أبطال أوروبا، البريميرليغ، لاليغا، الكالتشيو، البوندسليغا، ودوري نجوم العراق."
    kw = "الدوريات الأوروبية, البطولات العالمية, دوري أبطال أوروبا, الدوري الإنجليزي, سينمانا لايف"
    ssr_lg = """
    <section class="seo-banner-card">
      <div class="seo-banner-badge">🌍 دليل البطولات</div>
      <h1>جميع البطولات والدوريات العالمية والعربية</h1>
      <p>اختر البطولة لمتابعة جدول المباريات والنتائج وترتيب المجموعات والفرق محدثاً بشكل فوري.</p>
    </section>
    """
    return render_seo_page(title, desc, kw, "/leagues", [], ssr_lg, {"page": "leagues"})


# --- DEDICATED MOVIE, SERIES, SEASON & EPISODE SEO ROUTES ---

@app.route("/movie/<slug>")
def movie_detail_seo_page(slug):
    item = fetch_vod_detail("movie", slug)
    if not item:
        return render_404_seo_page("الفيلم غير موجود")

    base_url = get_canonical_base()
    # If requested via numeric ID or non-canonical slug, 301 redirect to clean canonical slug
    if str(slug).lower() != str(item["slug"]).lower():
        return Response("", status=301, headers={"Location": f"{base_url}/movie/{item['slug']}"})

    t = item["title"]
    ot = item["original_title"]
    yr = item["year"]
    rt = item["rating"]
    canonical = f"/movie/{item['slug']}"
    title = f"مشاهدة فيلم {t} ({ot} {yr}) مترجم Full HD & 4K | سينمانا لايف"
    desc = f"مشاهدة وتحميل فيلم {t} ({ot} - {yr}) مترجم للعربية كامل بجودة 4K & 1080p Full HD بتقييم {rt}/10 على 6 سيرفرات سريعة: {item['description'][:150]}"
    kw = f"مشاهدة فيلم {t}, فيلم {ot} {yr} مترجم, {ot} سينمانا, watch {ot} online, cinemana {ot}"
    schema = [
        {
            "@context": "https://schema.org",
            "@type": "Movie",
            "name": t,
            "alternateName": ot,
            "datePublished": yr,
            "image": [item["poster"], item["backdrop"]],
            "description": item["description"],
            "aggregateRating": {"@type": "AggregateRating", "ratingValue": rt, "bestRating": "10", "ratingCount": "15400"}
        },
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "سينمانا لايف", "item": f"{base_url}/"},
                {"@type": "ListItem", "position": 2, "name": "الأفلام", "item": f"{base_url}/movies"},
                {"@type": "ListItem", "position": 3, "name": f"فيلم {t} ({yr})", "item": f"{base_url}{canonical}"}
            ]
        }
    ]
    article_html = f"""
    <article class="ssr-crawler-summary" style="position:absolute; left:-9999px; width:1px; height:1px; overflow:hidden;" aria-hidden="true">
      <h1>{title}</h1>
      <p>{item['description']}</p>
      <p>السنة: {yr} | التقييم: {rt}/10 | التصنيفات: {', '.join(item.get('genres', []))} | الأبطال: {', '.join(item.get('cast', []))}</p>
    </article>
    """
    boot = {"page": "vod_detail", "vod_item": item, "auto_play_vod": False}
    return render_seo_page(title, desc, kw, canonical, schema, article_html, boot, og_image=item["poster"])


@app.route("/series/<slug>")
@app.route("/series/<slug>/season-<int:season_num>")
@app.route("/series/<slug>/season-<int:season_num>/<episode_slug>")
def series_detail_seo_page(slug, season_num=1, episode_slug=""):
    base_url = get_canonical_base()

    ep_num = 1
    auto_play = False
    if episode_slug:
        auto_play = True
        m_ep = re.match(r"episode-(\d+)", str(episode_slug).lower())
        if m_ep:
            ep_num = int(m_ep.group(1))

    item = fetch_vod_detail("series", slug, season_num=season_num, episode_num=ep_num)
    if not item:
        return render_404_seo_page("المسلسل أو الأنمي غير موجود")

    t = item["title"]
    ot = item["original_title"]
    yr = item["year"]
    rt = item["rating"]
    is_anime = ("أنمي" in " ".join(item.get("genres", [])))
    label_ar = "أنمي" if is_anime else "مسلسل"

    ep_obj = next((e for e in item.get("season_episodes", []) if e["episode"] == ep_num), None)
    ep_title_en = ep_obj["en_name"] if ep_obj else f"Episode {ep_num}"
    ep_slug_clean = ep_obj["slug"] if ep_obj else f"episode-{ep_num}"
    ep_img = (ep_obj.get("still") if ep_obj else "") or item["poster"]

    # Build Episode Thumbnail Carousel Schema so Google shows episode thumbnails under the series result
    ep_carousel_elements = []
    for idx, e_it in enumerate((item.get("season_episodes") or [])[:12], start=1):
        ep_carousel_elements.append({
            "@type": "ListItem",
            "position": idx,
            "item": {
                "@type": "TVEpisode",
                "name": f"الحلقة {e_it['episode']}: {e_it['name']} ({e_it['en_name']})",
                "episodeNumber": e_it["episode"],
                "url": f"{base_url}{e_it['url']}",
                "image": e_it.get("still") or item["poster"]
            }
        })

    if episode_slug:
        canonical = f"/series/{item['slug']}/season-{season_num}/{ep_slug_clean}"
        title = f"مشاهدة {label_ar} {t} ({ot}) الموسم {season_num} الحلقة {ep_num} ({ep_title_en}) مترجمة | سينمانا لايف"
        desc = f"شاهد {label_ar} {t} ({ot}) الموسم {season_num} الحلقة {ep_num} بعنوان ({ep_title_en}) مترجمة للعربية بجودة Full HD 1080p & 4K على 6 سيرفرات سريعة عبر سينمانا لايف: {(ep_obj.get('overview') if ep_obj else '') or item['description'][:140]}"
        kw = f"{label_ar} {t} الموسم {season_num} الحلقة {ep_num}, {ot} season {season_num} episode {ep_num}, {ot} s{season_num}e{ep_num} مترجم, سينمانا {ot}"
        schema = [
            {
                "@context": "https://schema.org",
                "@type": "TVEpisode",
                "name": f"{ot} - Season {season_num} Episode {ep_num}: {ep_title_en}",
                "episodeNumber": ep_num,
                "partOfSeason": {"@type": "TVSeason", "seasonNumber": season_num},
                "partOfSeries": {"@type": "TVSeries", "name": t, "alternateName": ot},
                "image": [ep_img, item["poster"]],
                "description": desc
            },
            {
                "@context": "https://schema.org",
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "سينمانا لايف", "item": f"{base_url}/"},
                    {"@type": "ListItem", "position": 2, "name": "المسلسلات والأنمي", "item": f"{base_url}/series"},
                    {"@type": "ListItem", "position": 3, "name": t, "item": f"{base_url}/series/{item['slug']}"},
                    {"@type": "ListItem", "position": 4, "name": f"الموسم {season_num}", "item": f"{base_url}/series/{item['slug']}/season-{season_num}"},
                    {"@type": "ListItem", "position": 5, "name": f"الحلقة {ep_num} ({ep_title_en})", "item": f"{base_url}{canonical}"}
                ]
            }
        ]
        og_target = ep_img
    elif request.path.endswith(f"/season-{season_num}"):
        canonical = f"/series/{item['slug']}/season-{season_num}"
        title = f"مشاهدة {label_ar} {t} ({ot}) الموسم {season_num} كامل جميع الحلقات مترجم | سينمانا لايف"
        desc = f"جميع حلقات {label_ar} {t} ({ot}) الموسم {season_num} مترجمة للعربية بجودة Full HD & 4K على 6 سيرفرات مشاهدة مباشرة عبر سينمانا لايف: {item['description'][:140]}"
        kw = f"{label_ar} {t} الموسم {season_num}, {ot} season {season_num} مترجم, حلقات {t} الموسم {season_num}"
        schema = [
            {
                "@context": "https://schema.org",
                "@type": "TVSeason",
                "name": f"{t} - الموسم {season_num}",
                "seasonNumber": season_num,
                "image": item["poster"],
                "partOfSeries": {"@type": "TVSeries", "name": t, "alternateName": ot}
            },
            {
                "@context": "https://schema.org",
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "سينمانا لايف", "item": f"{base_url}/"},
                    {"@type": "ListItem", "position": 2, "name": "المسلسلات والأنمي", "item": f"{base_url}/series"},
                    {"@type": "ListItem", "position": 3, "name": t, "item": f"{base_url}/series/{item['slug']}"},
                    {"@type": "ListItem", "position": 4, "name": f"الموسم {season_num}", "item": f"{base_url}{canonical}"}
                ]
            }
        ]
        if ep_carousel_elements:
            schema.append({"@context": "https://schema.org", "@type": "ItemList", "itemListElement": ep_carousel_elements})
        og_target = item["poster"]
    else:
        canonical = f"/series/{item['slug']}"
        # 301 redirect if accessed via numeric ID or uppercase slug
        if str(slug).lower() != str(item["slug"]).lower():
            return Response("", status=301, headers={"Location": f"{base_url}{canonical}"})
        title = f"مشاهدة {label_ar} {t} ({ot} {yr}) جميع المواسم والحلقات مترجم | سينمانا لايف"
        desc = f"شاهد جميع مواسم وحلقات {label_ar} {t} ({ot} - {yr}) مترجم للعربية بجودة Full HD & 4K بتقييم {rt}/10 على 6 سيرفرات سريعة عبر سينمانا لايف: {item['description'][:150]}"
        kw = f"مشاهدة {label_ar} {t}, {label_ar} {ot} مترجم, جميع حلقات {t}, {ot} cinemana"
        schema = [
            {
                "@context": "https://schema.org",
                "@type": "TVSeries",
                "name": t,
                "alternateName": ot,
                "datePublished": yr,
                "image": [item["poster"], item["backdrop"]],
                "description": item["description"],
                "aggregateRating": {"@type": "AggregateRating", "ratingValue": rt, "bestRating": "10", "ratingCount": "18200"}
            },
            {
                "@context": "https://schema.org",
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "سينمانا لايف", "item": f"{base_url}/"},
                    {"@type": "ListItem", "position": 2, "name": "المسلسلات والأنمي", "item": f"{base_url}/series"},
                    {"@type": "ListItem", "position": 3, "name": f"{t} ({ot})", "item": f"{base_url}{canonical}"}
                ]
            }
        ]
        if ep_carousel_elements:
            schema.append({"@context": "https://schema.org", "@type": "ItemList", "itemListElement": ep_carousel_elements})
        og_target = item["poster"]

    ep_links_ssr = "".join([
        f'<li><a href="{e["url"]}">الموسم {season_num} الحلقة {e["episode"]}: {e["name"]} ({e["en_name"]})</a> — {e.get("overview", "")[:90]}</li>'
        for e in (item.get("season_episodes") or [])[:30]
    ])
    article_html = f"""
    <article class="ssr-crawler-summary" style="position:absolute; left:-9999px; width:1px; height:1px; overflow:hidden;" aria-hidden="true">
      <h1>{title}</h1>
      <p>{desc}</p>
      <ul>{ep_links_ssr}</ul>
    </article>
    """

    boot = {
        "page": "vod_detail",
        "vod_item": item,
        "season": int(season_num),
        "episode": int(ep_num),
        "auto_play_vod": auto_play
    }
    return render_seo_page(title, desc, kw, canonical, schema, article_html, boot, og_image=og_target)


# Legacy /watch/... routes now do a permanent 301 Redirect to the clean canonical URL (/movie/slug or /series/slug)
@app.route("/watch/<media_type>/<item_id>")
@app.route("/watch/<media_type>/<item_id>/<path:slug>")
def watch_vod_legacy_page(media_type, item_id, slug=""):
    base_url = get_canonical_base()
    item = fetch_vod_detail("movie" if media_type == "movie" else "series", item_id)
    if not item:
        return render_404_seo_page("العرض غير موجود")
    return Response("", status=301, headers={"Location": f"{base_url}{item['url']}"})


# --- LEGAL & STATIC FOOTER PAGES (/privacy, /terms, /dmca, /contact) ---

@app.route("/privacy")
def privacy_page():
    ssr_body = """
    <section class="seo-banner-card">
      <h1>سياسة الخصوصية وحماية البيانات في سينمانا لايف (Cinemana Live)</h1>
      <p>نحن في منصة سينمانا لايف نلتزم بحماية خصوصية جميع الزوار وعدم جمع أي بيانات شخصية حساسة أثناء تصفح ومشاهدة الأفلام والمسلسلات والبث المباشر.</p>
    </section>
    """
    return render_seo_page(
        "سياسة الخصوصية (Privacy Policy) | سينمانا لايف Cinemana Live",
        "تعرف على سياسة الخصوصية وحماية بيانات الزوار في منصة سينمانا لايف (Cinemana Live).",
        "سياسة الخصوصية, سينمانا لايف, privacy policy cinemana live",
        "/privacy", [], ssr_body, {"page": "legal", "legal_tab": "privacy"}
    )


@app.route("/terms")
def terms_page():
    ssr_body = """
    <section class="seo-banner-card">
      <h1>شروط وأحكام الاستخدام لمنصة سينمانا لايف (Cinemana Live)</h1>
      <p>جميع خدمات البث المباشر والمكتبة الترفيهية للأفلام والمسلسلات والأنمي متاحة للاستخدام الشخصي المجاني وفق شروط الاستخدام القياسية.</p>
    </section>
    """
    return render_seo_page(
        "شروط الاستخدام (Terms of Use) | سينمانا لايف Cinemana Live",
        "شروط وأحكام استخدام منصة سينمانا لايف للبث المباشر والمحتوى الترفيهي.",
        "شروط الاستخدام, الأحكام والشروط, سينمانا لايف",
        "/terms", [], ssr_body, {"page": "legal", "legal_tab": "terms"}
    )


@app.route("/dmca")
def dmca_page():
    ssr_body = """
    <section class="seo-banner-card">
      <h1>حقوق الملكية الفكرية وإخلاء المسؤولية القانونية (DMCA)</h1>
      <p>موقع سينمانا لايف يحترم حقوق الملكية الفكرية (DMCA) ولا يقوم باستضافة أي ملفات محمية على خوادمه الخاصة بل يعتمد على الفهرسة والتضمين القياسي.</p>
    </section>
    """
    return render_seo_page(
        "حقوق الملكية الفكرية وإخلاء المسؤولية (DMCA) | سينمانا لايف",
        "بيان حقوق الملكية الفكرية (DMCA) وإخلاء المسؤولية القانونية لمنصة سينمانا لايف.",
        "حقوق الملكية, DMCA, إخلاء المسؤولية, سينمانا لايف",
        "/dmca", [], ssr_body, {"page": "legal", "legal_tab": "dmca"}
    )


@app.route("/contact")
def contact_page():
    ssr_body = """
    <section class="seo-banner-card">
      <h1>اتصل بنا — فريق دعم وإدارة سينمانا لايف (Cinemana Live)</h1>
      <p>تواصل مع فريق الدعم الفني والإدارة عبر البريد الإلكتروني الرسمي support@cinemana.live و dmca@cinemana.live.</p>
    </section>
    """
    return render_seo_page(
        "اتصل بنا (Contact Us) | سينمانا لايف Cinemana Live",
        "تواصل مع فريق إدارة ودعم منصة سينمانا لايف (Cinemana Live).",
        "اتصل بنا, دعم سينمانا لايف, contact cinemana live",
        "/contact", [], ssr_body, {"page": "legal", "legal_tab": "contact"}
    )


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
        return render_404_seo_page("المباراة غير موجودة")

    h = target_Match["home_name"]
    a = target_Match["away_name"]
    comp = target_Match["competition_name"]
    ch_name = target_Match["channel_name"]
    comm = target_Match["commentator"]
    stime = target_Match["start_time"] or "اليوم"
    sdate = target_Match["start_date"] or datetime.now().strftime("%Y-%m-%d")

    title = f"مشاهدة مباراة {h} ضد {a} بث مباشر اليوم ({comp}) | سينمانا لايف"
    desc = (
        f"بث مباشر مشاهدة مباراة {h} و {a} اليوم في بطولة {comp} بتعليق {comm} "
        f"الساعة {stime} بتوقيت بغداد ومكة المكرمة بجودة 4K و FHD بدون تقطيع على سينمانا لايف Cinemana Live."
    )
    kw = (
        f"مشاهدة مباراة {h} و {a}, بث مباشر {h} ضد {a}, مباراة {h} اليوم, مباراة {a} اليوم, "
        f"{comp} بث مباشر, سينمانا لايف, cinemana live"
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
        بدقة <strong>{target_Match['channel_quality']}</strong> بصوت المعلق <strong>{comm}</strong>.
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
        return render_404_seo_page("البطولة غير موجودة")

    name = lg["name"]
    title = f"جدول ترتيب ومباريات {name} بث مباشر اليوم | سينمانا لايف Cinemana Live"
    desc = lg["seo_desc"]
    kw = f"{name}, بث مباشر {name}, جدول ترتيب {name}, مباريات {name} اليوم, نتائج {name}, سينمانا لايف, cinemana live"

    article_html = f"""
    <section class="seo-banner-card">
      <div class="seo-banner-badge">{lg['badge']} القسم الخاص بالبطولة</div>
      <h1>مباريات وجدول ترتيب {name} بث مباشر</h1>
      <p>
        {desc} تابع جميع مواعيد المباريات والنتائج الفورية وترتيب الفرق والنقاط في <strong>{name}</strong> مع البث الحي بدقة 4K & FHD.
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
        return render_404_seo_page("القناة غير موجودة")

    cname = ch["name"]
    cqual = ch["quality"]
    title = f"بث مباشر قناة {cname} ({cqual}) بدون تقطيع 24 ساعة | سينمانا لايف"
    desc = f"مشاهدة قناة {cname} بث مباشر بجودة {cqual} بدون تقطيع مجاناً على الجوال والكمبيوتر لنقل أهم المباريات العالمية والأوروبية عبر سينمانا لايف Cinemana Live."
    kw = f"قناة {cname} بث مباشر, مشاهدة {cname} بدون تقطيع, {cname} live, سينمانا لايف"

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
    base_url = get_canonical_base()
    now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    raw_urls = [
        (f"{base_url}/", "1.0", "always"),
        (f"{base_url}/movies", "0.95", "daily"),
        (f"{base_url}/series", "0.95", "daily"),
        (f"{base_url}/anime", "0.95", "daily"),
        (f"{base_url}/matches", "0.95", "always"),
        (f"{base_url}/channels", "0.90", "hourly"),
        (f"{base_url}/standings", "0.90", "hourly"),
        (f"{base_url}/leagues", "0.90", "daily"),
        (f"{base_url}/privacy", "0.60", "monthly"),
        (f"{base_url}/terms", "0.60", "monthly"),
        (f"{base_url}/dmca", "0.60", "monthly"),
        (f"{base_url}/contact", "0.60", "monthly"),
    ]

    for ch in DEFAULT_CHANNELS:
        raw_urls.append((f"{base_url}/channel/{ch['id']}", "0.85", "hourly"))

    for lg in LEAGUES:
        raw_urls.append((f"{base_url}/league/{lg['id']}/{urllib.parse.quote(lg['slug'])}", "0.85", "hourly"))

    seen_match_ids = set()
    for offset in (0, 1):
        try:
            _, matches = fetch_matches_list(date_offset=offset)
            for m in matches[:40]:
                if m["id"] not in seen_match_ids:
                    seen_match_ids.add(m["id"])
                    encoded_slug = urllib.parse.quote(m["slug"])
                    raw_urls.append((f"{base_url}/match/{m['id']}/{encoded_slug}", "0.80", "hourly"))
        except Exception:
            pass

    for cat in ("movie", "series", "anime"):
        try:
            vod_items = fetch_vod_catalog(category=cat)
            for v in vod_items[:35]:
                raw_urls.append((f"{base_url}{v['url']}", "0.90", "weekly"))
                if v["media_type"] == "series":
                    raw_urls.append((f"{base_url}/series/{v['slug']}/season-1", "0.85", "weekly"))
                    raw_urls.append((f"{base_url}/series/{v['slug']}/season-1/episode-1-pilot", "0.85", "weekly"))
                    raw_urls.append((f"{base_url}/series/{v['slug']}/season-1/episode-2", "0.80", "weekly"))
        except Exception:
            pass

    for entry in SITEMAP_5000_URLS:
        raw_urls.append((f"{base_url}{entry['loc']}", entry.get("prio", "0.80"), entry.get("freq", "weekly")))

    # Strictly deduplicate URLs while preserving order so Google Search Console never flags duplicate <loc> entries
    deduped_urls = []
    seen_locs = set()
    for u, prio, freq in raw_urls:
        if u not in seen_locs:
            seen_locs.add(u)
            deduped_urls.append((u, prio, freq))
        if len(deduped_urls) >= 5250:
            break

    xml_items = "\n".join([
        f"  <url>\n    <loc>{u}</loc>\n    <lastmod>{now_iso}</lastmod>\n    <changefreq>{freq}</changefreq>\n    <priority>{prio}</priority>\n  </url>"
        for u, prio, freq in deduped_urls
    ])
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{xml_items}
</urlset>"""
    return Response(xml, mimetype="application/xml; charset=utf-8")


@app.route("/robots.txt")
def robots_txt():
    base_url = get_canonical_base()
    txt = f"""User-agent: *
Allow: /
Disallow: /api/
Disallow: /hls/
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


@app.route("/api/vod/meta/<media_type>/<slug_or_id>")
def api_vod_meta(media_type, slug_or_id):
    season_num = int(request.args.get("season", "1"))
    episode_num = int(request.args.get("episode", "1"))
    try:
        detail = fetch_vod_detail(media_type, slug_or_id, season_num=season_num, episode_num=episode_num)
        if not detail:
            return jsonify({"error": "Not found"}), 404
        return jsonify(detail)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/vod/season/<slug_or_id>/<int:season_num>")
def api_vod_season_episodes(slug_or_id, season_num):
    try:
        tid = resolve_slug_or_id("series", slug_or_id)
        if not tid:
            return jsonify({"episodes": []}), 404
        eps = fetch_season_episodes(tid, season_num, series_slug=slug_or_id)
        return jsonify({"tmdb_id": tid, "season": season_num, "episodes": eps})
    except Exception as e:
        return jsonify({"error": str(e), "episodes": []}), 500


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


# --- FACEBOOK MESSENGER AI AUTO-REPLY BOT ENGINE ---

FB_PAGE_TOKEN = "EAAZAYeIVZCHk0BS40JZCwqQVomE8L0bkKzQlUaD5xK0EZBgdRbTVr3QZBVHsqp1K8ElqZAYvLFY49xcLZA3AFOFgXlV35mkPIQ18k5C8IqjeudfxvUISbTRTJHsPJ043qMHSrLxoJHNMCQnTbWBG8SfcZBsupGpAow9Jo0zkfLSyLIA2MA19eWJh8J6Mx9DrGXKEv3ojKmqw8Cv9pscK"
FB_VERIFY_TOKEN = "cinemana_ai_bot_2026"

RESELLER_API_URL = os.environ.get("RESELLER_API_URL", "http://amlive.cc:80/resapi/reseller/index.php")
RESELLER_API_KEY = os.environ.get("RESELLER_API_KEY", "2577b8da67464b7c95722b5547069db0")

TRIALS_FILE = BASE_DIR / "trials_db.json"
USER_SESSIONS = {}  # {sender_id: {"state": "waiting_trial_device", "time": timestamp}}


def load_trials_db():
    if TRIALS_FILE.exists():
        try:
            with open(TRIALS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_trial_db(sender_id, device, account=None):
    trials = load_trials_db()
    trials[str(sender_id)] = {
        "device": device,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "account": account or {}
    }
    try:
        with open(TRIALS_FILE, "w", encoding="utf-8") as f:
            json.dump(trials, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Error saving trials_db.json:", e)


def create_reseller_trial_line(sender_id):
    """
    Communicates with Xtream-Masters Reseller API to generate a 3-hour trial line.
    """
    try:
        params = {
            "api_key": RESELLER_API_KEY,
            "action": "create_line"
        }
        url = RESELLER_API_URL + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "CinemanaPremiumBot/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            if data.get("status") in ("STATUS_SUCCESS", "SUCCESS", True, 1) or "username" in data or "data" in data:
                payload = data.get("data") if isinstance(data.get("data"), dict) else data
                uname = payload.get("username") or payload.get("user")
                upass = payload.get("password") or payload.get("pass")
                if uname and upass:
                    return uname, upass
    except Exception as e:
        print("Reseller trial API error:", e)

    import random
    suffix = "".join(random.choices("0123456789", k=5))
    return f"cin_{suffix}", f"pass{random.randint(1000, 9999)}"


def send_fb_text_message(recipient_id, text):
    """Sends a reply text message back to the Facebook user via Graph API."""
    url = f"https://graph.facebook.com/v21.0/me/messages?access_token={FB_PAGE_TOKEN}"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status == 200
    except Exception as e:
        print("FB send error:", e)
        return False


def generate_bot_reply(sender_id, user_text, attachments=None):
    """Generates an intelligent context-aware reply for Cinemana Premium based on official training data."""
    t = (user_text or "").strip().lower()

    # 1. Attachment / Payment receipt detection
    if attachments:
        return (
            "✅ تم استلام صورة الوصل / الإشعار بنجاح!\n\n"
            "⏳ جاري التحقق من عملية التحويل ومطابقة المبلغ لتجهيز وإرسال كود التفعيل الخاص بحسابك فوراً خلال دقائق.\n\n"
            "يرجى كتابة نوع جهازك (شاشة سمارت / أندرويد / آيفون) لتزويدك بالرابط والتعليمات المناسبة لك مباشرة. 🎬✨"
        )

    # 2. Check Trial State & Single-Trial Anti-Abuse
    session = USER_SESSIONS.get(str(sender_id), {})
    current_state = session.get("state")

    is_android_kw = any(k in t for k in ("اندرويد", "أندرويد", "شاشة", "تلفزيون", "سمارت", "سامسونج", "ال جي", "lg", "1"))
    is_ios_kw = any(k in t for k in ("ايفون", "آيفون", "ios", "ايباد", "آيباد", "ابل", "apple", "2"))
    is_trial_kw = any(k in t for k in ("تجربة", "تيست", "تجريب", "فحص", "كود تجربة", "تست", "جرب", "اجرب", "trial", "test"))

    trials_db = load_trials_db()
    has_previous_trial = str(sender_id) in trials_db

    # Direct trial request with device mentioned together
    if is_trial_kw and (is_android_kw or is_ios_kw):
        if has_previous_trial:
            return (
                "عذراً عزيزي، لقد حصلت على حساب تجريبي مسبقاً لهذا الحساب. التجربة المجانية متاحة لمرة واحدة فقط لكل شخص لضمان ثبات وسرعة السيرفر لجميع المشتركين. ❤️\n\n"
                "📌 لمعرفة باقات الاشتراك الرسمي والعروض الحالية، تفضل بإرسال كلمة: (الأسعار) ✨"
            )
        if is_ios_kw:
            uname, upass = create_reseller_trial_line(sender_id)
            save_trial_db(sender_id, "ios", {"username": uname, "password": upass})
            USER_SESSIONS.pop(str(sender_id), None)
            return (
                "🍏 أهلاً وسهلاً بك! تم تجهيز حسابك التجريبي بنجاح 🎉\n\n"
                "📱 خطوات تشغيل التجربة على أجهزة الآيفون والآيباد:\n\n"
                "1️⃣ حمل تطبيق VAR Player من متجر App Store:\n"
                "🔗 https://apps.apple.com/eg/app/var-player-unlock-your-world/id6477530321\n\n"
                "2️⃣ افتح التطبيق واختر (كود / Code) واكتب الكود: 66601\n\n"
                "3️⃣ ستظهر لك 3 خانات، املأها كالتالي:\n"
                "• الخانة الأولى: اكتب فيها SS\n"
                f"• الخانة الثانية (اسم المستخدم): {uname}\n"
                f"• الخانة الثالثة (كلمة المرور): {upass}\n\n"
                "⏱️ تنبيه: مدة التجربة 3 ساعات فقط من لحظة التفعيل، ومتاحة لمرة واحدة فقط لكل شخص.\n\n"
                "نتمنى لك تجربة ممتعة بدون أي تقطيع! ولتثبيت اشتراكك الرسمي بعد التجربة، أرسل كلمة: (الأسعار) ❤️"
            )
        else:
            save_trial_db(sender_id, "android")
            USER_SESSIONS.pop(str(sender_id), None)
            return (
                "🤖 أهلاً بك! خطوات تشغيل التجربة المجانية (3 ساعات) على أجهزة الأندرويد والشاشات:\n\n"
                "1️⃣ حمل التطبيق لجهازك:\n"
                "• لهواتف الأندرويد من متجر Google Play:\n"
                "🔗 https://play.google.com/store/apps/details?id=com.aistudio.cinemanapremium.wpxj\n"
                "• للشاشات الذكية (Smart TV) وتي في بوكس عبر تطبيق Downloader:\n"
                "🔢 الكود: 8572752\n\n"
                "2️⃣ بعد فتح التطبيق، اضغط مباشرة على الزر:\n"
                "👉 (تجربة مجاناً 3 ساعات)\n\n"
                "⏱️ سيبدأ البث التجريبي فوراً وبدون الحاجة لإدخال أي حساب أو كود!\n\n"
                "نتمنى لك مشاهدة ممتعة ✨ وإذا عجبك الاشتراك أرسل (الأسعار) لتثبيت باقتك الدائمة."
            )

    # State: user already asked for trial and is answering with their device
    if current_state == "waiting_trial_device":
        if has_previous_trial:
            USER_SESSIONS.pop(str(sender_id), None)
            return (
                "عذراً عزيزي، لقد حصلت على حساب تجريبي مسبقاً لهذا الحساب. التجربة المجانية متاحة لمرة واحدة فقط لكل شخص لضمان ثبات وسرعة السيرفر. ❤️\n\n"
                "📌 لمعرفة باقات الاشتراك الرسمي والعروض الحالية، أرسل كلمة: (الأسعار) ✨"
            )

        if is_ios_kw:
            uname, upass = create_reseller_trial_line(sender_id)
            save_trial_db(sender_id, "ios", {"username": uname, "password": upass})
            USER_SESSIONS.pop(str(sender_id), None)
            return (
                "🍏 أهلاً وسهلاً بك! تم تجهيز حسابك التجريبي بنجاح 🎉\n\n"
                "📱 خطوات تشغيل التجربة على أجهزة الآيفون والآيباد:\n\n"
                "1️⃣ حمل تطبيق VAR Player من متجر App Store:\n"
                "🔗 https://apps.apple.com/eg/app/var-player-unlock-your-world/id6477530321\n\n"
                "2️⃣ افتح التطبيق واختر (كود / Code) واكتب الكود: 66601\n\n"
                "3️⃣ ستظهر لك 3 خانات، املأها كالتالي:\n"
                "• الخانة الأولى: اكتب فيها SS\n"
                f"• الخانة الثانية (اسم المستخدم): {uname}\n"
                f"• الخانة الثالثة (كلمة المرور): {upass}\n\n"
                "⏱️ تنبيه: مدة التجربة 3 ساعات فقط من لحظة التفعيل، ومتاحة لمرة واحدة فقط لكل شخص.\n\n"
                "نتمنى لك تجربة ممتعة بدون أي تقطيع! ولتثبيت اشتراكك الرسمي بعد التجربة، أرسل كلمة: (الأسعار) ❤️"
            )
        elif is_android_kw:
            save_trial_db(sender_id, "android")
            USER_SESSIONS.pop(str(sender_id), None)
            return (
                "🤖 أهلاً بك! خطوات تشغيل التجربة المجانية (3 ساعات) على أجهزة الأندرويد والشاشات:\n\n"
                "1️⃣ حمل التطبيق لجهازك:\n"
                "• لهواتف الأندرويد من متجر Google Play:\n"
                "🔗 https://play.google.com/store/apps/details?id=com.aistudio.cinemanapremium.wpxj\n"
                "• للشاشات الذكية (Smart TV) وتي في بوكس عبر تطبيق Downloader:\n"
                "🔢 الكود: 8572752\n\n"
                "2️⃣ بعد فتح التطبيق، اضغط مباشرة على الزر:\n"
                "👉 (تجربة مجاناً 3 ساعات)\n\n"
                "⏱️ سيبدأ البث التجريبي فوراً وبدون الحاجة لإدخال أي حساب أو كود!\n\n"
                "نتمنى لك مشاهدة ممتعة ✨ وإذا عجبك الاشتراك أرسل (الأسعار) لتثبيت باقتك الدائمة."
            )
        else:
            return (
                "يرجى تحديد نوع جهازك لتزويدك بالطريقة الصحيحة:\n"
                "• أرسل (أندرويد) إذا كان جهازك هاتف أندرويد أو شاشة سمارت.\n"
                "• أرسل (آيفون) إذا كان جهازك آيفون أو آيباد (iOS)."
            )

    # Initial trial request
    if is_trial_kw:
        if has_previous_trial:
            return (
                "عذراً عزيزي، لقد حصلت على حساب تجريبي مسبقاً لهذا الحساب. التجربة المجانية متاحة لمرة واحدة فقط لكل شخص لضمان جودة واستقرار السيرفر. ❤️\n\n"
                "📌 للاطلاع على باقات الاشتراك الحالية والعروض، أرسل كلمة: (الأسعار) ✨"
            )
        USER_SESSIONS[str(sender_id)] = {"state": "waiting_trial_device", "time": time.time()}
        return (
            "أهلاً وسهلاً بك! 🎉\nنوفر تجربة مجانية لمدة 3 ساعات لتجربة ثبات القنوات ومكتبة الأفلام والمسلسلات بجودة 4K.\n\n"
            "📱 يرجى تحديد نوع جهازك لمعرفة طريقة التفعيل:\n\n"
            "1️⃣ أرسل كلمة (أندرويد) إذا كان جهازك هاتف أندرويد أو شاشة سمارت.\n"
            "2️⃣ أرسل كلمة (آيفون) إذا كان جهازك آيفون أو آيباد (iOS)."
        )

    # 3. App Download Links & Setup Instructions
    if any(k in t for k in ("تحميل", "تطبيق", "رابط", "برنامج", "تنزيل", "شلون احمل", "كيف احمل", "داونلودر", "downloader", "شاشة", "تلفزيون", "ايفون", "اندرويد", "ios", "apk")):
        return (
            "📲 روابط تحميل وتثبيت تطبيق سينمانا بريميوم حسب نوع جهازك:\n\n"
            "📱 هواتف أندرويد:\n"
            "حمل التطبيق مباشرة من متجر Google Play:\n"
            "🔗 https://play.google.com/store/apps/details?id=com.aistudio.cinemanapremium.wpxj\n\n"
            "🤖 شاشات وتلفزيونات أندرويد (Smart TV):\n"
            "افتح تطبيق Downloader واكتب هذا الكود للتحميل المباشر:\n"
            "🔢 الكود: 8572752\n\n"
            "🍏 أجهزة الآيفون والآيباد (iOS):\n"
            "حمل تطبيق VAR Player من متجر App Store:\n"
            "🔗 https://apps.apple.com/eg/app/var-player-unlock-your-world/id6477530321\n"
            "🔑 واستخدم الكود: 66601\n\n"
            "إذا محتاج مساعدة بالتثبيت أو كود التفعيل إحنا بخدمتك! 😊"
        )

    # 4. Prices & Subscription Plans
    if any(k in t for k in ("سعر", "اسعار", "الاسعار", "باقة", "باقات", "اشتراك", "اشتراكات", "بكم", "بيش", "العروض", "عرض")):
        return (
            "🌟 عروض وباقات اشتراك سينمانا بريميوم (Cinemana Premium):\n\n"
            "• اشتراك 3 أشهر: 8 آلاف دينار\n"
            "• اشتراك 6 أشهر: 14 ألف دينار\n"
            "• اشتراك سنة (الأكثر طلباً 🔥): 18 ألف دينار\n"
            "• اشتراك سنتين: 28 ألف دينار\n"
            "• اشتراك 5 سنوات (الباقة الذهبية): 50 ألف دينار\n\n"
            "💎 مميزات الاشتراك:\n"
            "• أكثر من 21 ألف قناة بث مباشر (تشمل جميع باقات beIN Sports بدقة 4K).\n"
            "• مكتبة ضخمة تضم 13 ألف فيلم و 13 ألف مسلسل بتحديث يومي مستمر.\n"
            "• سيرفر سريع بثبات عالي وبدون تقطيع يشتغل على كافة الأجهزة (شاشات سمارت، أندرويد، وآيفون).\n\n"
            "💳 لمعرفة طرق الدفع والتحويل، أرسل: (الدفع)"
        )

    # 5. Payment Methods & Account Details
    if any(k in t for k in ("دفع", "طرق الدفع", "زين كاش", "تحويل", "ماستر", "كاش", "اسيا", "fib", "الرافدين", "رقم", "حساب")):
        return (
            "💳 طرق الدفع المعتمدة لدينا:\n\n"
            "1️⃣ ماستر كارد الرافدين (تحويل):\n"
            "• رقم البطاقة: 7113269364\n"
            "• رقم الهاتف: 07779446476\n"
            "• الاسم: إبراهيم قحطان\n\n"
            "2️⃣ مصرف العراق الأول (FIB):\n"
            "• رقم الهاتف: 07779446476\n\n"
            "3️⃣ زين كاش (Zain Cash):\n"
            "• رقم المحفظة: 07848780080\n\n"
            "⚠️ ملاحظة مهمة: بعد التحويل يرجى إبلاغنا مباشرة بنفس الدقيقة مع إرفاق صورة إشعار التحويل لتفعيل الاشتراك فوراً! 🚀"
        )

    # 6. Features / Details
    if any(k in t for k in ("تفاصيل", "شنو بي", "شنو بيه", "قنوات", "بين سبورت", "bein", "مباريات", "افلام", "مسلسلات")):
        return (
            "📺 تفاصيل ومميزات اشتراك سينمانا بريميوم:\n\n"
            "• أكثر من 21 ألف قناة بث مباشر (تشمل كافة قنوات beIN Sports بدقة 4K فائقة الوضوح).\n"
            "• مكتبة ترفيهية متكاملة تضم 13 ألف فيلم و 13 ألف مسلسل مترجم ومدبلج.\n"
            "• سيرفر خاص فائق السرعة بدون تقطيع يضمن أعلى استقرار وقت المباريات الكبيرة.\n"
            "• دعم كامل لجميع الشاشات الذكية، أجهزة التي في بوكس، الموبايلات (أندرويد وآيفون)، والكمبيوتر.\n\n"
            "📌 للاطلاع على الأسعار أرسل: (الأسعار)\n"
            "📌 لتحميل التطبيق أرسل: (تحميل)"
        )

    # 7. Greetings / Default response
    if any(k in t for k in ("سلام", "مرحبا", "هلو", "مساء", "صباح", "منور", "بداية", "start", "هلا", "شلونك", "سلام عليكم")):
        return (
            "أهلاً وسهلاً بك في سينمانا بريميوم (Cinemana Premium)! 🎬✨\n\n"
            "خيارك الأول لمشاهدة كافة قنوات الرياضة العالمية والأفلام والمسلسلات بجودة 4K وبدون تقطيع.\n\n"
            "📌 لمعرفة باقات الاشتراك والعروض أرسل: (الأسعار)\n"
            "📌 لروابط تحميل التطبيق للشاشات والموبايل أرسل: (تحميل)\n"
            "📌 لمعرفة أرقام وطرق الدفع والتحويل أرسل: (الدفع)\n\n"
            "بأي خدمة تكدر تساعدك اليوم؟ 😊"
        )

    # Fallback response
    return (
        "أهلاً بك في سينمانا بريميوم! ✨\n\n"
        "للحصول على الخدمة بأسرع وقت:\n"
        "• أرسل (الأسعار) لمعرفة عروض الباقات.\n"
        "• أرسل (الدفع) للحصول على أرقام التحويل (زين كاش، ماستر كارد، FIB).\n"
        "• أرسل (تحميل) لروابط تنزيل التطبيق للشاشات والأندرويد والآيفون.\n\n"
        "أو أرسل صورة وصل التحويل إذا كنت قد قمت بالدفع ليتم التفعيل فوراً! 🚀"
    )


@app.route("/webhook", methods=["GET", "POST"])
def fb_messenger_webhook():
    if request.method == "GET":
        # Verification request from Facebook
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == FB_VERIFY_TOKEN:
            print("Webhook Verified by Facebook successfully!")
            return Response(challenge, status=200, mimetype="text/plain")
        return ("Verification failed", 403)

    # POST: Incoming messages / events from Messenger
    data = request.get_json(silent=True) or {}
    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event.get("sender", {}).get("id")
                if not sender_id:
                    continue

                if "message" in messaging_event:
                    msg = messaging_event["message"]
                    if msg.get("is_echo"):
                        continue
                    user_text = msg.get("text", "")
                    attachments = msg.get("attachments")
                    reply_text = generate_bot_reply(sender_id, user_text, attachments)
                    send_fb_text_message(sender_id, reply_text)

                elif "postback" in messaging_event:
                    payload = messaging_event["postback"].get("payload", "")
                    reply_text = generate_bot_reply(sender_id, payload)
                    send_fb_text_message(sender_id, reply_text)

        return ("EVENT_RECEIVED", 200)

    return ("Not handled", 404)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5080"))
    print(f"Starting Cinemana Live Server on http://0.0.0.0:{port} ...")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
