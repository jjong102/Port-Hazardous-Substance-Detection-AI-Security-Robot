# backend/app.py
import os, json, math, statistics, queue, threading, hashlib, pathlib
import datetime as dt

import firebase_admin
from firebase_admin import credentials, messaging

from functools import wraps
from sqlalchemy.pool import NullPool

from flask import Flask, request, jsonify, Response, stream_with_context, send_file, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, func
from typing import Optional, Dict

# -------- Config --------
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://43.202.250.26:5000").rstrip("/")

FIREBASE_CRED = os.getenv("FIREBASE_CRED")
FCM_DEFAULT_TOPIC = os.getenv("FCM_DEFAULT_TOPIC", "alerts")
FIREBASE_PROJECT = os.getenv("FIREBASE_PROJECT", "alter-bot-inu-3971")

# -------- Config --------
DB_PATH = os.getenv("DB_PATH", "sensor_data.db")
# WARNING_THRESHOLD = float(os.getenv("WARNING_THRESHOLD", "2.0"))
APPROVAL_TOKEN = os.getenv("APPROVAL_TOKEN", None)
COSIGN_RADIUS_M = float(os.getenv("COSIGN_RADIUS_M", "60"))
CAUTION_T = float(os.getenv("CAUTION_T", "2.0"))
DANGER_T  = float(os.getenv("DANGER_T",  "4.0"))
WARNING_THRESHOLD = CAUTION_T  # 기존 호환

UPLOAD_DIR = pathlib.Path("uploads"); UPLOAD_DIR.mkdir(exist_ok=True, parents=True)
REPORT_DIR = pathlib.Path("reports"); REPORT_DIR.mkdir(exist_ok=True, parents=True)

# -------- App / DB --------
app = Flask(__name__)
app.config.update(
    SQLALCHEMY_DATABASE_URI=f"sqlite:///{DB_PATH}?check_same_thread=False",
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SQLALCHEMY_ENGINE_OPTIONS={"poolclass": NullPool},  # SQLite 풀 고갈 방지
)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)
db = SQLAlchemy(app)

firebase_app = None
if FIREBASE_CRED and os.path.exists(FIREBASE_CRED):
    try:
        cred = credentials.Certificate(FIREBASE_CRED)
        firebase_app = firebase_admin.initialize_app(cred, {'projectId': FIREBASE_PROJECT})
        print(f"[FCM] initialized project={FIREBASE_PROJECT}")
    except Exception as e:
        print("[FCM] init failed:", e)

# --- 위에 그대로 ---
def fcm_send_topic(topic: str, title: str, body: str, data: dict = None) -> bool:
    if not firebase_app:
        return False
    msg = messaging.Message(
        topic=topic,
        notification=messaging.Notification(title=title, body=body),  # ← 시스템이 직접 표시
        data={k: str(v) for k, v in (data or {}).items()},
        android=messaging.AndroidConfig(
            priority="high",
            # ★ channel_id 절대 넣지 마세요(기본 채널 사용해야 앱 꺼져도 뜸)
            notification=messaging.AndroidNotification(sound="default"),
        ),
        apns=messaging.APNSConfig(
            headers={"apns-priority": "10"},
            payload=messaging.APNSPayload(aps=messaging.Aps(sound="default")),
        ),
    )
    try:
        mid = messaging.send(msg)
        print("[FCM] sent:", mid)
        return True
    except Exception as e:
        print("[FCM] send fail:", e)
        return False


@app.post("/devices/register")
def register_device():
    """앱에서 보낸 FCM 토큰을 서버 토픽에 구독시킨다."""
    d = request.get_json(force=True, silent=True) or {}
    token = d.get("token")
    topic = d.get("topic") or FCM_DEFAULT_TOPIC
    if not token:
        return jsonify({"error":"token required"}), 400
    if not firebase_app:
        return jsonify({"error":"fcm_not_initialized"}), 500
    try:
        messaging.subscribe_to_topic([token], topic)
        return jsonify({"ok": True, "topic": topic})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()

# -------- Models --------
class Reading(db.Model):
    __tablename__ = "readings"
    id = db.Column(db.Integer, primary_key=True)
    rtype = db.Column(db.String(32), index=True)      # GPS|NH3|VOC|CO
    value = db.Column(db.Float)
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    vehicle_id = db.Column(db.String(64), default="robot-1", index=True)
    timestamp = db.Column(db.DateTime, default=dt.datetime.utcnow, index=True)

class Event(db.Model):
    __tablename__ = "events"
    id = db.Column(db.Integer, primary_key=True)
    substance = db.Column(db.String(32), index=True)      # 최초 발생 물질(호환)
    concentration = db.Column(db.Float)                   # 최초 값(호환)
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    vehicle_id = db.Column(db.String(64), default="robot-1", index=True)
    status = db.Column(db.String(16), default="new", index=True)  # new|pending|approved|resolved
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, index=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    approved_by = db.Column(db.String(64), nullable=True)
    resolved_by = db.Column(db.String(64), nullable=True)
    substances_json = db.Column(db.Text, default="{}")    # 물질별 최대/최근시각 요약
    perimeter_m = db.Column(db.Float, default=30.0)       # AR 경계 반경
    report_url = db.Column(db.Text, nullable=True)        # 보고서 PDF URL
    requires_cosign = db.Column(db.Integer, default=0)    # 1=코사인 필요

with app.app_context():
    db.create_all()

    def has_col(table, col):
        return any(c[1]==col for c in db.session.execute(text(f"PRAGMA table_info({table})")).all())

    # 컬럼 자동 마이그레이션
    if not has_col('events','substances_json'):
        db.session.execute(text("ALTER TABLE events ADD COLUMN substances_json TEXT DEFAULT '{}'"))
    if not has_col('events','perimeter_m'):
        db.session.execute(text("ALTER TABLE events ADD COLUMN perimeter_m REAL DEFAULT 30"))
    if not has_col('events','report_url'):
        db.session.execute(text("ALTER TABLE events ADD COLUMN report_url TEXT"))
    if not has_col('events','requires_cosign'):
        db.session.execute(text("ALTER TABLE events ADD COLUMN requires_cosign INTEGER DEFAULT 0"))

    # 보조 테이블 생성
    db.session.execute(text("""
    CREATE TABLE IF NOT EXISTS evidence(
      id INTEGER PRIMARY KEY,
      event_id INTEGER,
      kind TEXT,
      url TEXT,
      note TEXT,
      sha256 TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP)
    """))
    db.session.execute(text("""
    CREATE TABLE IF NOT EXISTS sop_logs(
      id INTEGER PRIMARY KEY,
      event_id INTEGER,
      step_id TEXT,
      ok INTEGER,
      note TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP)
    """))
    db.session.execute(text("""
    CREATE TABLE IF NOT EXISTS cosigns(
      id INTEGER PRIMARY KEY,
      event_id INTEGER,
      device_id TEXT,
      lat REAL, lng REAL,
      ts DATETIME,
      sig TEXT)
    """))
    db.session.execute(text("""
    CREATE TABLE IF NOT EXISTS action_logs(
      id INTEGER PRIMARY KEY,
      event_id INTEGER,
      actor TEXT,
      action TEXT,
      detail TEXT,
      ts DATETIME DEFAULT CURRENT_TIMESTAMP)
    """))
    # evidence.note 마이그레이션(누락 시 추가)
    def _has_col(t,c):
        return any(x[1]==c for x in db.session.execute(text(f"PRAGMA table_info({t})")).all())
    if not _has_col("evidence","note"):
        db.session.execute(text("ALTER TABLE evidence ADD COLUMN note TEXT"))
    db.session.commit()

# -------- SSE Hub --------
class SSEHub:
    def __init__(self):
        self.clients = []; self.lock = threading.Lock()
    def register(self):
        q = queue.Queue(maxsize=1024)
        with self.lock: self.clients.append(q)
        return q
    def unregister(self, q):
        with self.lock:
            if q in self.clients: self.clients.remove(q)
    def broadcast(self, name, payload):
        data = json.dumps(payload, ensure_ascii=False)
        msg = f"event: {name}\n" f"data: {data}\n\n"
        with self.lock:
            dead=[]
            for q in self.clients:
                try: q.put_nowait(msg)
                except queue.Full: dead.append(q)
            for q in dead:
                if q in self.clients: self.clients.remove(q)

hub = SSEHub()
def sse_event(name, payload): hub.broadcast(name, payload)

def require_token(f):
    @wraps(f)
    def w(*a, **k):
        if APPROVAL_TOKEN is None: return f(*a, **k)
        token = request.headers.get("X-Admin-Token") or request.args.get("token")
        if token != APPROVAL_TOKEN: return jsonify({"error":"forbidden"}), 403
        return f(*a, **k)
    return w

# -------- Queries --------
@app.get("/readings/latest")
def readings_latest():
    """각 센서(NH3/VOC/CO)의 최신 1건 또는 ?type=NH3 로 단일 타입 최신 1건"""
    typ = (request.args.get("type") or "").upper()
    def last_of(t):
        r = (Reading.query
             .filter(Reading.rtype == t)
             .order_by(Reading.timestamp.desc())
             .first())
        return reading_to_dict(r) if r else None
    if typ in ("NH3","VOC","CO"):
        x = last_of(typ)
        return (jsonify(x), 200) if x else (jsonify({"error":"no data"}), 404)
    # 전체 묶음
    out = {k: last_of(k) for k in ("NH3","VOC","CO")}
    if not any(out.values()): return jsonify({"error":"no data"}), 404
    return jsonify(out)

# -------- Helpers --------
def reading_to_dict(r: Reading):
    return {"id": r.id, "type": r.rtype, "value": r.value, "lat": r.lat, "lng": r.lng,
            "vehicle_id": r.vehicle_id, "timestamp": r.timestamp.isoformat()+"Z"}

def _loads(s):
    try: return json.loads(s or "{}")
    except: return {}

def _incident_view(e: Event):
    subs = _loads(e.substances_json)
    items=[]; max_any = 0.0
    for k in ("NH3","VOC","CO"):
        if k in subs:
            m = float(subs[k].get("max", 0.0)); max_any = max(max_any, m)
            items.append({"substance": k, "max": m, "last_at": subs[k].get("last_at")})
    level = "danger" if max_any >= DANGER_T else ("warn" if max_any >= CAUTION_T else "normal")
    return {
        "id": e.id, "vehicle_id": e.vehicle_id, "status": e.status,
        "lat": e.lat, "lng": e.lng, "perimeter_m": float(e.perimeter_m or 30.0),
        "created_at": e.created_at.isoformat()+"Z",
        "approved_at": e.approved_at.isoformat()+"Z" if e.approved_at else None,
        "resolved_at": e.resolved_at.isoformat()+"Z" if e.resolved_at else None,
        "report_url": e.report_url,
        "substances": items,
        "level": level, "max_any": round(max_any,2)
    }

def _upsert_incident(vehicle_id, lat, lng, rtype, val, now):
    open_e = (Event.query.filter_by(vehicle_id=vehicle_id)
              .filter(Event.status == "pending")
              .order_by(Event.created_at.desc()).first())
    if not open_e:
        e = Event(substance=rtype, concentration=val, lat=lat, lng=lng,
                  vehicle_id=vehicle_id, status="pending", created_at=now,
                  substances_json=json.dumps({rtype: {"max": float(val), "last_at": now.isoformat()+"Z"}}))
        db.session.add(e); db.session.commit()
        _log_action(e.id, "system", "detected", f"{rtype}:{val}")
        level_kr = "위험" if val >= DANGER_T else ("주의" if val >= CAUTION_T else "정상")
        fcm_send_topic(
            FCM_DEFAULT_TOPIC,
            f"[{level_kr}] {rtype} {val:.2f}",
            f"#{e.id} • {e.vehicle_id} • {e.lat:.5f},{e.lng:.5f}",
            {"event_id": str(e.id), "vehicle_id": e.vehicle_id, "level": level_kr},
        )
        return e

    # ----- 여기부터 교체 -----
    subs = _loads(open_e.substances_json)

    # 기존 최대치로 현재 레벨 계산
    prev_max_any = 0.0
    for k in ("NH3","VOC","CO"):
        if k in subs:
            prev_max_any = max(prev_max_any, float(subs[k].get("max", 0.0)))
    old_level = "danger" if prev_max_any >= DANGER_T else ("warn" if prev_max_any >= CAUTION_T else "normal")

    # 값 갱신
    prev = subs.get(rtype, {"max": 0.0})
    if val > float(prev.get("max", 0.0)):
        prev["max"] = float(val)
    prev["last_at"] = now.isoformat()+"Z"
    subs[rtype] = prev
    open_e.substances_json = json.dumps(subs, ensure_ascii=False)
    db.session.commit()

    # 새 최대치 레벨 계산
    new_max_any = 0.0
    for k in ("NH3","VOC","CO"):
        if k in subs:
            new_max_any = max(new_max_any, float(subs[k].get("max", 0.0)))
    new_level = "danger" if new_max_any >= DANGER_T else ("warn" if new_max_any >= CAUTION_T else "normal")

    # 레벨 올랐으면 푸시
    if new_level != old_level and new_level in ("warn", "danger"):
        level_kr = "위험" if new_level == "danger" else "주의"
        fcm_send_topic(
            FCM_DEFAULT_TOPIC,
            f"[{level_kr}] {rtype} {val:.2f}",
            f"#{open_e.id} • {open_e.vehicle_id} • {lat:.5f},{lng:.5f}",
            {"event_id": str(open_e.id), "vehicle_id": open_e.vehicle_id, "level": level_kr},
        )
    return open_e
    # ----- 교체 끝 -----

def _dist_m(lat1,lng1,lat2,lng2):
    dy = (lat2-lat1)*111000.0
    dx = (lng2-lng1)*111000.0*max(math.cos(math.radians(lat1)), 1e-3)
    return (dx*dx+dy*dy)**0.5

def _log_action(event_id:int, actor:str, action:str, detail:str=""):
    db.session.execute(text("""
      INSERT INTO action_logs(event_id, actor, action, detail) VALUES(:e,:a,:c,:d)
    """), {"e":event_id, "a":actor, "c":action, "d":detail})
    db.session.commit()

# -------- Ingest --------
@app.post("/data")
def ingest():
    d = request.get_json(force=True, silent=True) or {}
    rtype = str(d.get("type","")).upper()
    vid = d.get("vehicle_id") or "robot-1"
    now = dt.datetime.utcnow()

    if rtype == "GPS":
            try:
                if "value" in d and isinstance(d["value"], str):
                    lat_s, lng_s = d["value"].split(",")
                    lat, lng = float(lat_s), float(lng_s)
                else:
                    lat, lng = float(d.get("lat")), float(d.get("lng"))
            except:
                return jsonify({"error": "bad GPS value"}), 400
            r = Reading(rtype="GPS", value=None, lat=lat, lng=lng, vehicle_id=vid, timestamp=now)
            db.session.add(r); db.session.commit()
            sse_event("gps", reading_to_dict(r))
            return jsonify({"message":"GPS saved","reading":reading_to_dict(r)})

    try:
        val = float(d.get("value")); lat=float(d.get("lat")); lng=float(d.get("lng"))
    except:
        return jsonify({"error":"bad payload"}), 400

    r = Reading(rtype=rtype, value=val, lat=lat, lng=lng, vehicle_id=vid, timestamp=now)
    db.session.add(r); db.session.commit()

    # ★ 임계치와 무관하게 항상 실시간 센서값 푸시
    sse_event("reading", reading_to_dict(r))

    # 임계치 초과 시에만 인시던트 생성/업데이트
    if rtype in ("NH3","VOC","CO") and val >= WARNING_THRESHOLD:
        inc = _upsert_incident(vid, lat, lng, rtype, val, now)
        sse_event("incident", _incident_view(inc))
        sse_event("event", {"kind":"pending_or_update", "event": _incident_view(inc)})

    return jsonify({"message":"reading saved","reading":reading_to_dict(r)})

def _to_float(x, default=None):
    try:
        if x is None: return default
        if isinstance(x, (int, float)): return float(x)
        s = str(x).strip().replace("ppm","").replace("PPM","").strip()
        return float(s)
    except:
        return default

@app.post("/data/hazard")
def ingest_hazard():
    d = request.get_json(force=True, silent=True) or {}
    rtype = str(d.get("substance","")).upper()
    val   = _to_float(d.get("concentration"))
    lat   = _to_float(d.get("lat"))
    lng   = _to_float(d.get("lng"))
    if rtype not in ("NH3","VOC","CO") or val is None or lat is None or lng is None:
        return jsonify({"error":"bad payload"}), 400

    now = dt.datetime.utcnow()
    r = Reading(rtype=rtype, value=val, lat=lat, lng=lng,
                vehicle_id=d.get("vehicle_id") or "robot-1", timestamp=now)
    db.session.add(r); db.session.commit()

    sse_event("reading", reading_to_dict(r))

    if val >= WARNING_THRESHOLD:
        inc = _upsert_incident(r.vehicle_id, lat, lng, rtype, val, now)
        sse_event("incident", _incident_view(inc))
        sse_event("event", {"kind":"pending_or_update", "event": _incident_view(inc)})

    return jsonify({"message":"reading saved","reading":reading_to_dict(r)})

# -------- Queries --------
@app.get("/gps/latest")
def gps_latest():
    x = Reading.query.filter(Reading.rtype=="GPS").order_by(Reading.timestamp.desc()).first()
    if not x: return jsonify({"error":"no gps"}), 404
    return jsonify(reading_to_dict(x))

@app.get("/incident/active")
def incident_active_single():
    vid = request.args.get("vehicle_id","robot-1")
    e = (Event.query.filter_by(vehicle_id=vid)
         .filter(Event.approved_at.is_(None))                    # 최종 승인 전만
         .filter(Event.status.in_(("pending","resolved")))       # 진행중 또는 앱해결 대기
         .order_by(Event.created_at.desc()).first())
    if not e: return jsonify({"error":"no active"}), 404
    return jsonify(_incident_view(e))

@app.get("/incidents/active")
def incidents_active_list():
    rows = (Event.query
            .filter(Event.approved_at.is_(None))
            .filter(Event.status.in_(("pending","resolved")))
            .order_by(Event.created_at.desc()).all())
    return jsonify([_incident_view(e) for e in rows])

@app.get("/events")
def events_list():
    status = request.args.get("status")
    q = Event.query
    if status: q = q.filter(Event.status==status)
    q = q.order_by(Event.created_at.desc()).limit(200)
    return jsonify([_incident_view(e) for e in q.all()])

@app.get("/events/latest")
def events_latest():
    e = Event.query.order_by(Event.created_at.desc()).first()
    if not e: return jsonify({"error":"no events"}), 404
    return jsonify(_incident_view(e))

# -------- Mutations --------
@app.post("/events/<int:eid>/approve")
@require_token
def approve_event(eid):
    e = Event.query.get_or_404(eid)
    if e.approved_at:
        return jsonify(_incident_view(e))
    if e.status not in ("pending","resolved"):
        return jsonify({"error":"invalid status", "status": e.status}), 400
    if int(e.requires_cosign or 0) == 1:
        cnt = db.session.execute(text("SELECT COUNT(DISTINCT device_id) FROM cosigns WHERE event_id=:e"),
                                 {"e": eid}).scalar() or 0
        if cnt < 2:
            return jsonify({"error":"cosign_required", "count": int(cnt)}), 400
    e.approved_at = dt.datetime.utcnow()
    e.approved_by  = request.headers.get("X-User","web")
    e.status = "approved"
    db.session.commit()
    _log_action(e.id, "web", "approve")
    sse_event("incident", _incident_view(e))
    return jsonify(_incident_view(e))

@app.post("/events/<int:eid>/resolve")
@require_token
def resolve_event(eid):
    e = Event.query.get_or_404(eid)
    e.status = "resolved"
    e.resolved_at = dt.datetime.utcnow()
    e.resolved_by = request.headers.get("X-User","app")
    db.session.commit()
    _log_action(e.id, "app", "resolve")
    sse_event("incident", _incident_view(e))
    return jsonify(_incident_view(e))

# -------- Evidence / Report / Timeline --------
@app.post("/events/<int:eid>/evidence")
@require_token
def add_evidence(eid):
    kind = (request.form.get("kind") or "photo").lower()
    note = request.form.get("note")
    f = request.files.get("file")
    sha = request.form.get("sha256")

    if kind == "note" and not note:
        return jsonify({"error":"note required"}), 400
    if kind != "note" and not f:
        return jsonify({"error":"file required"}), 400

    url = None
    if f:
        ext = (pathlib.Path(f.filename).suffix or ".bin").lower()
        tmp = UPLOAD_DIR / f"evid-{eid}-{int(dt.datetime.utcnow().timestamp())}{ext}"
        f.save(tmp)
        url_path = f"/uploads/{tmp.name}"
        base = PUBLIC_BASE_URL or request.host_url.rstrip("/")
        url = f"{base}{url_path}"                               # ← 절대 URL
        if not sha:
            sha = hashlib.sha256(tmp.read_bytes()).hexdigest()

    db.session.execute(text("""
      INSERT INTO evidence(event_id, kind, url, sha256, note)
      VALUES(:eid,:k,:u,:s,:n)
    """), {"eid":eid,"k":kind,"u":url,"s":sha,"n":note})
    db.session.commit()

    sse_event("evidence", {"event_id": eid})
    return jsonify({"ok": True, "url": url})

@app.get("/events/<int:eid>/timeline")
def event_timeline(eid: int):
    # evidence
    evs = db.session.execute(text("""
      SELECT id,
             kind,
             COALESCE(url,'')  AS url,
             COALESCE(note,'') AS note,
             strftime('%Y-%m-%dT%H:%M:%SZ', created_at) AS ts   -- ← UTC ISO8601
      FROM evidence
      WHERE event_id = :e
      ORDER BY created_at ASC
    """), {"e": eid}).mappings().all()

    def _abs(u: str) -> str:
        if not u: return ""
        if u.startswith("http://") or u.startswith("https://"): return u
        base = (os.getenv("PUBLIC_BASE_URL") or request.host_url.rstrip("/"))
        return f"{base}{u}"

    evidence = []
    for x in evs:
        d = dict(x); d["url"] = _abs(d["url"])
        evidence.append(d)

    # action logs + 이벤트 타임스탬프를 액션으로 합치기
    e = Event.query.get_or_404(eid)
    acts = db.session.execute(text("""
      SELECT id,
             actor,
             action,
             COALESCE(detail,'') AS detail,
             strftime('%Y-%m-%dT%H:%M:%SZ', ts) AS ts            -- ← UTC ISO8601
      FROM action_logs
      WHERE event_id = :e
      ORDER BY ts ASC
    """), {"e": eid}).mappings().all()

    e = Event.query.get_or_404(eid)
    synthetic = [
        {"id": -3, "actor": e.vehicle_id, "action": "created",  "detail": "", "ts": e.created_at.isoformat()+"Z"}
    ]
    if e.approved_at:
        synthetic.append({"id": -2, "actor": e.approved_by or "web", "action": "approved", "detail": "", "ts": e.approved_at.isoformat()+"Z"})
    if e.resolved_at:
        synthetic.append({"id": -1, "actor": e.resolved_by or "app", "action": "resolved", "detail": "", "ts": e.resolved_at.isoformat()+"Z"})

    all_acts = synthetic + [dict(x) for x in acts]
    all_acts.sort(key=lambda x: x["ts"])

    return jsonify({"evidence": evidence, "actions": all_acts})

@app.get("/uploads/<path:fname>")
def get_upload(fname):
    p = UPLOAD_DIR / fname
    if not p.exists(): return jsonify({"error":"not found"}), 404
    return send_from_directory(UPLOAD_DIR.as_posix(), fname)

@app.post("/events/<int:eid>/report/pdf")
@require_token
def build_report(eid):
    p = REPORT_DIR / f"event-{eid}.pdf"
    content = f"Event Report #{eid}\nGenerated: {dt.datetime.utcnow().isoformat()}Z\n"
    p.write_bytes(b"%PDF-1.1\n% demo\n" + content.encode("utf-8") + b"\n%%EOF")
    db.session.execute(text("UPDATE events SET report_url=:u WHERE id=:i"),
                       {"u":f"/reports/{p.name}", "i":eid})
    db.session.commit()
    _log_action(eid, "web", "report_build")
    return jsonify({"ok":True,"url":f"/reports/{p.name}"})

@app.get("/events/<int:eid>/report")
def get_report(eid):
    p = REPORT_DIR / f"event-{eid}.pdf"
    if not p.exists(): return jsonify({"error":"not ready"}), 404
    return send_file(p, mimetype="application/pdf")

@app.get("/reports/<path:fname>")
def get_report_file(fname):
    p = REPORT_DIR / fname
    if not p.exists(): return jsonify({"error":"not found"}), 404
    return send_from_directory(REPORT_DIR.as_posix(), fname, mimetype="application/pdf")

# -------- Perimeter --------
@app.patch("/events/<int:eid>/perimeter")
@require_token
def set_perimeter(eid):
    e = Event.query.get_or_404(eid)
    try:
        perimeter = float((request.get_json(silent=True) or {}).get("perimeter_m", 30))
    except:
        return jsonify({"error":"bad perimeter"}), 400
    e.perimeter_m = perimeter
    db.session.commit()
    _log_action(eid, "web", "perimeter", f"{perimeter}")
    return jsonify({"ok":True, "perimeter_m": perimeter})

# -------- Co-sign --------
@app.post("/events/<int:eid>/cosign")
@require_token
def post_cosign(eid):
    d = request.get_json(force=True, silent=True) or {}
    dev = d.get("device_id")
    try:
        lat = float(d.get("lat")); lng = float(d.get("lng"))
    except:
        return jsonify({"error":"bad lat/lng"}), 400
    ts = d.get("ts") or dt.datetime.utcnow().isoformat()+"Z"
    sig = d.get("sig","")
    e = Event.query.get_or_404(eid)
    if _dist_m(e.lat, e.lng, lat, lng) > COSIGN_RADIUS_M:
        return jsonify({"error":"out_of_radius"}), 400
    db.session.execute(text("""
      INSERT INTO cosigns(event_id, device_id, lat, lng, ts, sig)
      VALUES(:e,:d,:lat,:lng,:ts,:sig)
    """), {"e":eid,"d":dev,"lat":lat,"lng":lng,"ts":ts,"sig":sig})
    db.session.commit()
    _log_action(eid, "app", "cosign", dev or "")
    cnt = db.session.execute(text("SELECT COUNT(DISTINCT device_id) FROM cosigns WHERE event_id=:e"),
                             {"e":eid}).scalar() or 0
    return jsonify({"ok":True,"count":int(cnt)})

# -------- SOP --------
@app.get("/sop")
def get_sop():
    sub = (request.args.get("substance") or "NH3").upper()
    base = {
      "NH3":[{"id":"nh3-1","text":"출입 통제선 설정","type":"check"},
             {"id":"nh3-2","text":"국소 환기 확인","type":"check"},
             {"id":"nh3-note","text":"특이사항","type":"note"}],
      "VOC":[{"id":"voc-1","text":"점화원 제거","type":"check"},
             {"id":"voc-2","text":"환기 측정","type":"check"}],
      "CO":[{"id":"co-1","text":"산소농도 확인","type":"check"}]
    }
    return jsonify(base.get(sub, base["NH3"]))

@app.post("/events/<int:eid>/sop_log")
def post_sop_log(eid):
    d = request.get_json(force=True, silent=True) or {}
    db.session.execute(text("""
      INSERT INTO sop_logs(event_id, step_id, ok, note) VALUES(:e,:s,:o,:n)
    """), {"e":eid,"s":d.get("step_id"),"o":1 if d.get("ok") else 0,"n":d.get("note")})
    db.session.commit()
    _log_action(eid, "app", "sop_step", d.get("step_id") or "")
    return jsonify({"ok":True})

# -------- Stats base --------
def _series(range_key:str):
    now = dt.datetime.utcnow()
    if range_key=="7d": start=now-dt.timedelta(days=7); fmt="%Y-%m-%d %H:00"; filt=("NH3","VOC","CO")
    elif range_key=="30d": start=now-dt.timedelta(days=30); fmt="%Y-%m-%d"; filt=("NH3","VOC","CO")
    else: range_key="24h"; start=now-dt.timedelta(hours=24); fmt="%Y-%m-%d %H:%M"; filt=("NH3","VOC","CO")
    rows = (db.session.query(Reading.rtype, func.strftime(fmt, Reading.timestamp), func.avg(Reading.value))
            .filter(Reading.timestamp>=start)
            .filter(Reading.rtype.in_(filt))
            .group_by(Reading.rtype, func.strftime(fmt, Reading.timestamp))
            .order_by(func.strftime(fmt, Reading.timestamp).asc()).all())
    out={}
    for rt, tstr, avgv in rows:
        out.setdefault(rt, []).append({"t": tstr, "avg": float(avgv or 0)})
    return out

def _exceed_counts(range_key:str):
    now=dt.datetime.utcnow()
    if range_key=="7d": start=now-dt.timedelta(days=7)
    elif range_key=="30d": start=now-dt.timedelta(days=30)
    else: start=now-dt.timedelta(hours=24)
    rows = (db.session.query(Reading.rtype, func.count(Reading.id))
            .filter(Reading.timestamp>=start)
            .filter(Reading.rtype.in_(("NH3","VOC","CO")))
            .filter(Reading.value>=WARNING_THRESHOLD)
            .group_by(Reading.rtype).all())
    d={"NH3":0,"VOC":0,"CO":0}
    for rt,cnt in rows: d[rt]=int(cnt)
    return d

@app.get("/stats/series")
def stats_series():
    rk = request.args.get("range","24h")
    return jsonify(_series(rk))

@app.get("/stats/exceedance")
def stats_exceed():
    rk = request.args.get("range", "24h")
    mode = (request.args.get("mode") or "events").lower()  # "events" | "readings"
    if mode == "readings":
        return jsonify(_exceed_counts(rk))  # 기존: 초과 reading 개수
    return jsonify(_event_counts(rk))       # 기본: 사건(incident) 건수

# -------- STATS 2.0 --------
def _parse_range(range_key: str):
    now = dt.datetime.utcnow()
    rk = (range_key or "24h").lower()
    if rk == "7d":  return now - dt.timedelta(days=7), now, "hour"
    if rk == "30d": return now - dt.timedelta(days=30), now, "day"
    return now - dt.timedelta(hours=24), now, "minute"

def _readings_in_range(start, end, rtypes=("NH3","VOC","CO")):
    return (Reading.query
            .filter(Reading.timestamp >= start, Reading.timestamp <= end)
            .filter(Reading.rtype.in_(rtypes))
            .order_by(Reading.timestamp.asc())
            .all())

def _pairwise_dts(rows):
    n = len(rows); out=[]
    for i, r in enumerate(rows):
        dt_s = (rows[i+1].timestamp - r.timestamp).total_seconds() if i < n-1 else 60.0
        out.append(min(max(dt_s, 0.0), 60.0))
    return out

@app.get("/stats/duration")
def stats_duration():
    start, end, _ = _parse_range(request.args.get("range","24h"))
    rows = _readings_in_range(start, end)
    by = {"NH3": [], "VOC": [], "CO": []}
    for r in rows:
        if r.rtype in by: by[r.rtype].append(r)
    out = {}
    for k, lst in by.items():
        if not lst: out[k] = 0; continue
        dur = 0.0
        for r, dt_s in zip(lst, _pairwise_dts(lst)):
            if (r.value or 0) >= WARNING_THRESHOLD: dur += dt_s
        out[k] = round(dur/60.0, 2)
    return jsonify(out)

@app.get("/stats/intensity")
def stats_intensity():
    start, end, _ = _parse_range(request.args.get("range","24h"))
    rows = _readings_in_range(start, end)
    out = {"NH3": 0.0, "VOC": 0.0, "CO": 0.0}
    by = {"NH3": [], "VOC": [], "CO": []}
    for r in rows:
        if r.rtype in by: by[r.rtype].append(r)
    for k, lst in by.items():
        for r, dt_s in zip(lst, _pairwise_dts(lst)):
            v = float(r.value or 0.0)
            if v > WARNING_THRESHOLD: out[k] += (v - WARNING_THRESHOLD) * (dt_s / 60.0)
        out[k] = round(out[k], 2)
    return jsonify(out)

@app.get("/stats/percentiles")
def stats_percentiles():
    start, end, _ = _parse_range(request.args.get("range","24h"))
    p = float(request.args.get("p", "95")); p = min(max(p, 0.0), 100.0)
    rows = _readings_in_range(start, end)
    vals = {"NH3": [], "VOC": [], "CO": []}
    for r in rows:
        if r.value is not None and r.rtype in vals: vals[r.rtype].append(float(r.value))
    out = {}
    for k, arr in vals.items():
        if not arr: out[k] = {"max": 0, "p": 0}; continue
        arr.sort()
        idx = int(math.ceil(p/100.0 * len(arr))) - 1
        idx = min(max(idx, 0), len(arr)-1)
        out[k] = {"max": round(max(arr), 2), "p": round(arr[idx], 2)}
    return jsonify(out)

@app.get("/stats/nearmiss")
def stats_nearmiss():
    start, end, _ = _parse_range(request.args.get("range","24h"))
    low = float(os.getenv("NEARMISS_LOW", "1.6"))
    rows = _readings_in_range(start, end)
    out = {"NH3": 0, "VOC": 0, "CO": 0}
    for r in rows:
        v = float(r.value or 0.0)
        if low <= v < WARNING_THRESHOLD and r.rtype in out: out[r.rtype] += 1
    return jsonify(out)

@app.get("/stats/cooccur")
def stats_cooccur():
    start, end, _ = _parse_range(request.args.get("range","24h"))
    rows = _readings_in_range(start, end)
    buckets = {}
    for r in rows:
        if r.rtype not in ("NH3","VOC","CO") or r.value is None: continue
        if r.value < WARNING_THRESHOLD: continue
        key = r.timestamp.strftime("%Y-%m-%d %H:%M")
        buckets.setdefault(key, set()).add(r.rtype)
    two, three, total = 0, 0, len(buckets)
    pairs = {"NH3+VOC":0, "NH3+CO":0, "VOC+CO":0, "ALL3":0}
    for s in buckets.values():
        if len(s) >= 2: two += 1
        if len(s) == 3: three += 1; pairs["ALL3"] += 1
        if "NH3" in s and "VOC" in s: pairs["NH3+VOC"] += 1
        if "NH3" in s and "CO" in s: pairs["NH3+CO"] += 1
        if "VOC" in s and "CO" in s: pairs["VOC+CO"] += 1
    pct = lambda x: round((x/total*100.0), 2) if total else 0.0
    return jsonify({"minutes": total, "any_two_pct": pct(two), "all_three_pct": pct(three), "pair_counts": pairs})

@app.get("/stats/hotspots")
def stats_hotspots():
    start, end, _ = _parse_range(request.args.get("range","7d"))
    grid_m = float(request.args.get("grid", "50"))
    limit = int(request.args.get("limit", "10"))
    deg_lat = grid_m / 111000.0
    base_lat = float(request.args.get("base_lat", "37.45"))
    deg_lng = grid_m / (111000.0 * max(math.cos(math.radians(base_lat)), 1e-3))
    rows = _readings_in_range(start, end)
    cells = {}
    by = {"NH3": [], "VOC": [], "CO": []}
    for r in rows:
        if r.rtype in by: by[r.rtype].append(r)
    for lst in by.values():
        for r, dt_s in zip(lst, _pairwise_dts(lst)):
            if (r.value or 0) >= WARNING_THRESHOLD and r.lat is not None and r.lng is not None:
                iy = int(math.floor(r.lat / deg_lat)); ix = int(math.floor(r.lng / deg_lng))
                cells[(iy, ix)] = cells.get((iy, ix), 0.0) + dt_s
    ranked = sorted(cells.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    out = []
    for (iy, ix), sec in ranked:
        lat = (iy + 0.5) * deg_lat; lng = (ix + 0.5) * deg_lng
        out.append({"lat": round(lat, 6), "lng": round(lng, 6), "duration_min": round(sec/60.0, 2)})
    return jsonify(out)

# ---- Hotspots with series (for spark table) ----
def _range_and_bucket(rk: str):
    now = dt.datetime.utcnow()
    rk = (rk or "24h").lower()
    if rk == "7d":   return now - dt.timedelta(days=7), now, "hour"
    if rk == "30d":  return now - dt.timedelta(days=30), now, "day"
    return now - dt.timedelta(hours=24), now, "hour"

def _truncate(ts: dt.datetime, bucket: str):
    if bucket == "day":  return ts.replace(hour=0, minute=0, second=0, microsecond=0)
    return ts.replace(minute=0, second=0, microsecond=0)

@app.get("/stats/hotspots_series", endpoint="stats_hotspots_series")
def stats_hotspots_series():
    rk = request.args.get("range","24h")
    grid_m = float(request.args.get("grid","50"))
    limit  = int(request.args.get("limit","12"))
    base_lat = float(request.args.get("base_lat","37.45"))
    split = request.args.get("split","1") in ("1","true","yes")

    start, end, bucket = _range_and_bucket(rk)
    labels=[]; cur=_truncate(start,bucket)
    step = dt.timedelta(days=1) if bucket=="day" else dt.timedelta(hours=1)
    while cur <= end:
        labels.append(cur.strftime("%Y-%m-%d %H:00" if bucket=="hour" else "%Y-%m-%d"))
        cur += step
    idx={lab:i for i,lab in enumerate(labels)}

    deg_lat = grid_m/111000.0
    deg_lng = grid_m/(111000.0*max(math.cos(math.radians(base_lat)),1e-3))

    rows=(Reading.query
          .filter(Reading.timestamp>=start, Reading.timestamp<=end)
          .filter(Reading.rtype.in_(("NH3","VOC","CO")))
          .order_by(Reading.timestamp.asc()).all())

    by={"NH3":[], "VOC":[], "CO":[]}
    for r in rows: by[r.rtype].append(r)

    cells={}
    def bump(lat,lng,ts,dt_s,rtype):
        lab=_truncate(ts,bucket).strftime("%Y-%m-%d %H:00" if bucket=="hour" else "%Y-%m-%d")
        j=idx.get(lab)
        if j is None: return
        iy=int(math.floor(lat/deg_lat)); ix=int(math.floor(lng/deg_lng))
        rec=cells.setdefault((iy,ix),{
            "sec":0.0,
            "series":[0.0]*len(labels),
            "subs":{"NH3":0.0,"VOC":0.0,"CO":0.0},
            "series_by_sub":{"NH3":[0.0]*len(labels),"VOC":[0.0]*len(labels),"CO":[0.0]*len(labels)}
        })
        rec["sec"]+=dt_s
        rec["series"][j]+=dt_s/60.0
        rec["subs"][rtype]+=dt_s/60.0
        if split: rec["series_by_sub"][rtype][j]+=dt_s/60.0

    for typ,lst in by.items():
        for r,dt_s in zip(lst, _pairwise_dts(lst)):
            if r.lat is None or r.lng is None: continue
            if float(r.value or 0.0) >= WARNING_THRESHOLD:
                bump(r.lat,r.lng,r.timestamp,dt_s,typ)

    ranked=sorted(cells.items(), key=lambda kv: kv[1]["sec"], reverse=True)[:limit]
    out={"labels":labels,"cells":[]}
    for (iy,ix),rec in ranked:
        lat=(iy+0.5)*deg_lat; lng=(ix+0.5)*deg_lng
        item={
            "lat":round(lat,6), "lng":round(lng,6),
            "duration_min":round(rec["sec"]/60.0,2),
            "series_min":[round(x,2) for x in rec["series"]],
            "subs_min": {k: round(v,2) for k,v in rec["subs"].items()}
        }
        if split:
            item["series_by_sub"]={
                "NH3":[round(x,2) for x in rec["series_by_sub"]["NH3"]],
                "VOC":[round(x,2) for x in rec["series_by_sub"]["VOC"]],
                "CO":[round(x,2) for x in rec["series_by_sub"]["CO"]],
            }
        out["cells"].append(item)
    return jsonify(out)

def _event_counts(range_key: str):
    now = dt.datetime.utcnow()
    if range_key == "7d":
        start = now - dt.timedelta(days=7)
    elif range_key == "30d":
        start = now - dt.timedelta(days=30)
    else:
        start = now - dt.timedelta(hours=24)
    end = now

    rows = (db.session.query(Event.substance, func.count(Event.id))
            .filter(Event.created_at >= start, Event.created_at <= end)
            .filter(Event.status.in_(("pending","approved","resolved")))  # 상태 무관히 ‘1건’으로
            .group_by(Event.substance)
            .all())
    d = {"NH3": 0, "VOC": 0, "CO": 0}
    for sub, cnt in rows:
        if sub in d: d[sub] = int(cnt)
    return d

@app.get("/stats/availability")
def stats_availability():
    start, end, _ = _parse_range(request.args.get("range","24h"))
    start_m = start.replace(second=0, microsecond=0); end_m = end.replace(second=0, microsecond=0)
    total_min = int((end_m - start_m).total_seconds() // 60)
    seen = {"NH3": set(), "VOC": set(), "CO": set()}
    rows = _readings_in_range(start, end)
    for r in rows:
        key = r.timestamp.strftime("%Y-%m-%d %H:%M")
        if r.rtype in seen: seen[r.rtype].add(key)
    out = {k: round((len(v)/max(total_min,1))*100.0, 2) for k, v in seen.items()}
    out["minutes_total"] = total_min
    return jsonify(out)

@app.get("/stats/drift")
def stats_drift():
    now = dt.datetime.utcnow(); mid = now - dt.timedelta(days=15); start = now - dt.timedelta(days=30)
    rows_old = _readings_in_range(start, mid); rows_new = _readings_in_range(mid, now)
    def base_med(arr):
        if not arr: return 0.0
        arr = sorted(arr); cut = max(1, int(len(arr)*0.2)); return statistics.median(arr[:cut])
    out = {}
    for k in ("NH3","VOC","CO"):
        oldv = [float(r.value) for r in rows_old if r.rtype==k and r.value is not None]
        newv = [float(r.value) for r in rows_new if r.rtype==k and r.value is not None]
        m1, m2 = base_med(oldv), base_med(newv)
        out[k] = {"baseline1": round(m1,2), "baseline2": round(m2,2), "drift": round(m2-m1,2)}
    return jsonify(out)

@app.get("/metrics/ops")
def metrics_ops():
    start, end, _ = _parse_range(request.args.get("range","30d"))
    evs = (Event.query.filter(Event.created_at >= start, Event.created_at <= end)
           .order_by(Event.created_at.desc()).all())
    tta, ttr = [], []
    for e in evs:
        if e.approved_at: tta.append((e.approved_at - e.created_at).total_seconds()/60.0)
        if e.resolved_at and e.approved_at: ttr.append((e.resolved_at - e.approved_at).total_seconds()/60.0)
    out = {
        "mtta_min": round(statistics.mean(tta),2) if tta else 0,
        "mttr_min": round(statistics.mean(ttr),2) if ttr else 0,
        "count": len(evs)
    }
    return jsonify(out)

@app.get("/stats/hazard_index")
def stats_hazard_index():
    rk = request.args.get("range","24h")
    start, end, _ = _parse_range(rk)
    rows = _readings_in_range(start, end)
    by = {"NH3": [], "VOC": [], "CO": []}
    for r in rows:
        if r.rtype in by: by[r.rtype].append(r)

    dur, inten = {}, {}
    for k, lst in by.items():
        s = 0.0
        for r, dt_s in zip(lst, _pairwise_dts(lst)):
            if (r.value or 0) >= WARNING_THRESHOLD: s += dt_s
        dur[k] = s/60.0

    for k, lst in by.items():
        s = 0.0
        for r, dt_s in zip(lst, _pairwise_dts(lst)):
            v = float(r.value or 0.0)
            if v > WARNING_THRESHOLD: s += (v - WARNING_THRESHOLD) * (dt_s / 60.0)
        inten[k] = s

    exc = _exceed_counts(rk)
    def norm(x, a): return min(x / a, 1.0) if a > 0 else 0.0
    caps = {"dur": 60.0, "inten": 120.0, "exc": 40.0}

    out = {}
    for k in ("NH3", "VOC", "CO"):
        score = 100.0 * (
            0.4 * norm(dur.get(k, 0), caps["dur"])
            + 0.4 * norm(inten.get(k, 0), caps["inten"])
            + 0.2 * norm(exc.get(k, 0), caps["exc"])
        )
        out[k] = round(score, 1)
    return jsonify(out)

# -------- SSE stream --------
@app.get("/stream")
def stream():
    @stream_with_context
    def event_stream():
        q = hub.register()
        try:
            # 1) 최신 GPS 1건
            gps = (Reading.query
                   .filter(Reading.rtype=="GPS")
                   .order_by(Reading.timestamp.desc())
                   .first())
            if gps:
                yield f"event: gps\ndata: {json.dumps(reading_to_dict(gps), ensure_ascii=False)}\n\n"
            db.session.remove()

            # 2) 물질별 최신 1건(NH3/VOC/CO) → reading으로 즉시 쏘기
            for k in ("NH3","VOC","CO"):
                last = (Reading.query
                        .filter(Reading.rtype==k)
                        .order_by(Reading.timestamp.desc())
                        .first())
                if last:
                    yield f"event: reading\ndata: {json.dumps(reading_to_dict(last), ensure_ascii=False)}\n\n"
            db.session.remove()

            # 3) 진행 중 인시던트 1건(있으면)
            e = (Event.query.filter(Event.approved_at.is_(None))
                 .filter(Event.status.in_(("pending","resolved")))
                 .order_by(Event.created_at.desc())
                 .first())
            if e:
                yield f"event: incident\ndata: {json.dumps(_incident_view(e), ensure_ascii=False)}\n\n"
            db.session.remove()

            # 4) keep-alive / 브로드캐스트 루프
            last_ping = dt.datetime.utcnow()
            while True:
                try:
                    msg = q.get(timeout=5.0)
                    yield msg
                except queue.Empty:
                    if (dt.datetime.utcnow() - last_ping).total_seconds() >= 15:
                        yield "event: ping\ndata: {}\n\n"
                        last_ping = dt.datetime.utcnow()
        finally:
            hub.unregister(q)

    resp = Response(event_stream(), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    return resp

# -------- Admin --------
@app.get("/")
def root(): return jsonify({"ok": True, "version": "incident-api-2"})

@app.post("/admin/clear_recent")
def admin_clear_recent():
    hours = int(request.args.get("hours", "24"))
    cutoff = dt.datetime.utcnow() - dt.timedelta(hours=hours)

    ids = [row[0] for row in db.session.execute(
        text("SELECT id FROM events WHERE created_at >= :cut"), {"cut": cutoff}
    ).all()]

    if ids:
        for tbl, col in [("evidence","event_id"),("action_logs","event_id"),
                         ("sop_logs","event_id"),("cosigns","event_id")]:
            db.session.execute(text(f"DELETE FROM {tbl} WHERE {col} IN ({','.join([':i'+str(i) for i in range(len(ids))])})"),
                               {('i'+str(i)): ids[i] for i in range(len(ids))})
        db.session.execute(text(f"DELETE FROM events WHERE id IN ({','.join([':e'+str(i) for i in range(len(ids))])})"),
                           {('e'+str(i)): ids[i] for i in range(len(ids))})

    db.session.execute(text("DELETE FROM readings WHERE timestamp >= :cut"), {"cut": cutoff})
    db.session.commit()
    return jsonify({"ok": True, "cleared_hours": hours, "event_count": len(ids)})

@app.post("/admin/clear_all")
def admin_clear_all():
    db.session.execute(text("DELETE FROM evidence"))
    db.session.execute(text("DELETE FROM action_logs"))
    db.session.execute(text("DELETE FROM sop_logs"))
    db.session.execute(text("DELETE FROM cosigns"))
    db.session.execute(text("DELETE FROM readings"))
    db.session.execute(text("DELETE FROM events"))
    db.session.commit()
    return jsonify({"ok": True, "cleared": "all"})

# -------- Hotspot detail --------
def _truncate(ts: dt.datetime, bucket: str):
    if bucket == "day":  return ts.replace(hour=0, minute=0, second=0, microsecond=0)
    return ts.replace(minute=0, second=0, microsecond=0)

@app.post("/debug/fcm_test")
def fcm_test():
    ok = fcm_send_topic(
        request.args.get("topic", FCM_DEFAULT_TOPIC),
        request.args.get("title", "테스트"),
        request.args.get("body", "PING"),
        {"event_id": request.args.get("event_id", "0")}
    )
    return jsonify({"ok": ok})

# --- DAY FILTER: 해결 전 로그 날짜별 조회 ---
@app.get("/incidents/active_by_date")
def incidents_active_by_date():
    # ?date=YYYY-MM-DD  또는 ?from=ISO&to=ISO 지원
    date_s = request.args.get("date")
    f = request.args.get("from")
    t = request.args.get("to")

    # 날짜만 온 경우: 그 날 00:00:00Z ~ 23:59:59Z
    if date_s and not (f or t):
        try:
            d = dt.datetime.strptime(date_s, "%Y-%m-%d").date()
            f = f"{d.isoformat()}T00:00:00Z"
            t = f"{d.isoformat()}T23:59:59Z"
        except:
            return jsonify({"error":"bad date format (YYYY-MM-DD)"}), 400

    q = (Event.query
         .filter(Event.approved_at.is_(None))
         .filter(Event.status.in_(("pending", "resolved"))))

    def _parse_iso(s):
        # 매우 단순 ISO 처리 (끝이 Z면 UTC로 간주)
        try:
            return dt.datetime.fromisoformat(s.replace("Z",""))
        except:
            return None

    if f:
        fdt = _parse_iso(f)
        if not fdt: return jsonify({"error":"bad from"}), 400
        q = q.filter(Event.created_at >= fdt)
    if t:
        tdt = _parse_iso(t)
        if not tdt: return jsonify({"error":"bad to"}), 400
        q = q.filter(Event.created_at < tdt)

    rows = q.order_by(Event.created_at.desc()).all()
    return jsonify([_incident_view(e) for e in rows])

@app.get("/debug/fcm_diag")
def fcm_diag():
    info = {
        "firebase_app": bool(firebase_app),
        "cred_path": FIREBASE_CRED,
        "cred_exists": bool(FIREBASE_CRED and os.path.exists(FIREBASE_CRED)),
        "project_expected": FIREBASE_PROJECT,
    }
    try:
        with open(FIREBASE_CRED) as f:
            info["project_in_json"] = json.load(f).get("project_id")
    except Exception as e:
        info["project_in_json"] = None
        info["error_read_json"] = str(e)
    return jsonify(info)

# 디버그: 토픽 말고 “특정 토큰”으로 바로 쏘기(토픽 구독 문제 배제용)
@app.post("/debug/fcm_to_token")
def fcm_to_token():
    token = (request.args.get("token") or (request.get_json(silent=True) or {}).get("token"))
    title = request.args.get("title", "테스트")
    body  = request.args.get("body", "PING")
    if not token: return jsonify({"error":"token required"}), 400
    if not firebase_app: return jsonify({"error":"fcm_not_initialized"}), 500
    try:
        mid = messaging.send(messaging.Message(
            token=token,
            notification=messaging.Notification(title=title, body=body),
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(sound="default"),
            ),
            apns=messaging.APNSConfig(
                headers={"apns-priority":"10"},
                payload=messaging.APNSPayload(aps=messaging.Aps(sound="default")),
            ),
        ))
        return jsonify({"ok": True, "message_id": mid})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.post("/admin/wipe_all")
def admin_wipe_all():
    # 테이블 비우기
    for tbl in ("readings","events","evidence","action_logs","cosigns","sop_logs"):
        db.session.execute(text(f"DELETE FROM {tbl}"))
    db.session.commit()
    # 파일 폴더 비우기
    for d in (UPLOAD_DIR, REPORT_DIR):
        for p in d.glob("*"):
            try: p.unlink()
            except: pass
    return jsonify({"ok": True, "wiped": "all"})

@app.get("/stats/hotspot_detail")
def stats_hotspot_detail():
    try:
        lat = float(request.args["lat"]); lng = float(request.args["lng"])
    except:
        return jsonify({"error":"lat,lng required"}), 400
    rk = request.args.get("range","24h")
    grid_m = float(request.args.get("grid","50"))
    base_lat = float(request.args.get("base_lat","37.45"))

    start, end, bucket = _range_and_bucket(rk)
    labels=[]; cur=_truncate(start,bucket)
    step = dt.timedelta(days=1) if bucket=="day" else dt.timedelta(hours=1)
    while cur <= end:
        labels.append(cur.strftime("%Y-%m-%d %H:00" if bucket=="hour" else "%Y-%m-%d"))
        cur += step
    idx={lab:i for i,lab in enumerate(labels)}

    deg_lat = grid_m/111000.0
    deg_lng = grid_m/(111000.0*max(math.cos(math.radians(base_lat)),1e-3))
    iy=int(math.floor(lat/deg_lat)); ix=int(math.floor(lng/deg_lng))
    lat0, lat1 = iy*deg_lat, (iy+1)*deg_lat
    lng0, lng1 = ix*deg_lng, (ix+1)*deg_lng

    rows = (Reading.query
            .filter(Reading.timestamp>=start, Reading.timestamp<=end)
            .filter(Reading.rtype.in_(("NH3","VOC","CO")))
            .filter(Reading.lat>=lat0, Reading.lat<lat1, Reading.lng>=lng0, Reading.lng<lng1)
            .order_by(Reading.timestamp.asc()).all())

    subs = ["NH3","VOC","CO"]
    sums = {k:[0.0]*len(labels) for k in subs}
    cnts = {k:[0]*len(labels) for k in subs}
    exceed = {k:0 for k in subs}

    for r in rows:
        lab = _truncate(r.timestamp, bucket).strftime("%Y-%m-%d %H:00" if bucket=="hour" else "%Y-%m-%d")
        j = idx.get(lab)
        if j is None: continue
        v = float(r.value or 0.0)
        sums[r.rtype][j] += v
        cnts[r.rtype][j] += 1
        if v >= WARNING_THRESHOLD: exceed[r.rtype] += 1

    avg = {k:[round((s/c if c else 0.0),2) for s,c in zip(sums[k], cnts[k])] for k in subs}

    evs = (Event.query
           .filter(Event.created_at>=start, Event.created_at<=end)
           .filter(Event.lat>=lat0, Event.lat<lat1, Event.lng>=lng0, Event.lng<lng1)
           .filter(Event.approved_at.isnot(None)).all())
    tta = [(e.approved_at - e.created_at).total_seconds()/60.0 for e in evs]
    avg_tta = round(sum(tta)/len(tta), 2) if tta else 0.0

    return jsonify({
        "labels": labels,
        "avg_by_sub": avg,                 # 물질별 평균 농도 시계열
        "exceed_counts": exceed,           # 물질별 임계 초과 횟수
        "avg_tta_min": avg_tta,            # 승인까지 평균 시간(분)
        "tta_samples": len(tta)            # 샘플 수
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
