#!/usr/bin/env python3
# coding: utf-8
"""
START = 저속(최대속도 10%) 자율주행 ON/OFF
L2/R2 = 브레이크(정지)

- TRT 모델 출력: 스칼라 x ∈ [-1, 1] 로 가정 (tanh형)
  각도(deg) = x * ANGLE_LIMIT
- utils.preprocess가 있으면 그대로 사용하여 학습 파이프라인과 동기화
- '확확' 방지: 각도 EMA + 슬루(rate) 제한
- START로 켤 때 0°에서 잠깐 유지 후 부드럽게 램프업
"""

# ===================== 설정 =====================
DEFAULTS = {
    # 경로/장치
    "TRT_PATH": "road_following_model_trt.pth",
    "ALT_TRT_PATH": "/mnt/data/road_following_model_trt.pth",  # 업로드 경로 대안
    "CAM_INDEX": 0,                      # /dev/video0
    "SERIAL_PORT": "/dev/ttyCH341USB0",  # 포트를 명시하면 더 안정적
    "JS_INDEX": 0,                       # /dev/input/js0

    # 런타임
    "FPS": 30,
    "SEND_RATE_HZ": 20.0,
    "DEBUG": True,

    # 조향 제한/필터
    "ANGLE_LIMIT": 44,         # ±44°
    "ANGLE_LPF_ALPHA": 0.10,   # 각도 EMA(0이면 끔; 0.08~0.15 권장)
    "ANGLE_SLEW_DEG_PER_S": 120.0,  # 각도 최대 변화속도(°/s)
    "START_NEUTRAL_SEC": 0.6,  # 켠 직후 0° 유지 시간

    # 전처리/정밀도
    "TRT_FP16": True,
    "USE_UTILS_PREPROCESS": True,  # utils.preprocess 있으면 최우선 사용
    "FALLBACK_BGR2RGB": True,      # fallback 전처리에서만 적용
    "FALLBACK_NORM": "none",       # 'none' | 'imagenet'

    # 방향 보정
    "STEER_SIGN": +1.0,       # 좌우 반전 필요시 -1.0
    "STEER_BIAS_DEG": 0.0,    # 영점 보정(도)

    # 속도: 절대 비율(최대속도의 20%)
    "CRUISE_ABS_FRACTION": 0.20,

    # 조이스틱 코드 (장치에 맞춰 조정)
    "JS_CODE_START": 0x010B,  # START/OPTIONS (안 되면 0x0107로 바꿔봐)
    "JS_CODE_L2_AXIS": 0x0205,
    "JS_CODE_R2_AXIS": 0x0204,
    "JS_CODE_L2_BTN":  None,  # 버튼형이면 코드 넣기(예: 0x0105)
    "JS_CODE_R2_BTN":  None,
}
# =================================================

import os, time, math, threading, traceback, errno, fcntl, select, struct
import numpy as np
import torch
from torch2trt import TRTModule
from jetcam.usb_camera import USBCamera
from Rosmaster_Lib import Rosmaster

def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v

# -------- utils.preprocess 사용 시도 --------
_UTILS_PREPROCESS = None
if DEFAULTS["USE_UTILS_PREPROCESS"]:
    try:
        from utils import preprocess as _UTILS_PREPROCESS
    except Exception:
        _UTILS_PREPROCESS = None

def _preprocess_with_utils(frame):
    x = _UTILS_PREPROCESS(frame)  # (1,3,224,224) CUDA 텐서 기대
    return x.half() if DEFAULTS["TRT_FP16"] else x.float()

def _preprocess_fallback(frame):
    # BGR → RGB (USBCamera는 BGR)
    if DEFAULTS["FALLBACK_BGR2RGB"]:
        frame = frame[..., ::-1].copy()
    x = torch.from_numpy(frame).permute(2,0,1).contiguous().float() / 255.0
    if DEFAULTS["FALLBACK_NORM"].lower() == "imagenet":
        mean = torch.tensor([0.485,0.456,0.406]).view(3,1,1)
        std  = torch.tensor([0.229,0.224,0.225]).view(3,1,1)
        x = (x - mean) / std
    x = x.unsqueeze(0).cuda(non_blocking=True)
    return x.half() if DEFAULTS["TRT_FP16"] else x.float()

def preprocess_frame(frame):
    if _UTILS_PREPROCESS is not None:
        return _preprocess_with_utils(frame)
    return _preprocess_fallback(frame)

# -------- 간단한 슬루 제한기 --------
class SlewLimiter:
    def __init__(self, rate_deg_per_s, initial=0.0):
        self.rate = float(max(0.0, rate_deg_per_s))
        self.last = float(initial)
        self.t_last = time.time()

    def reset(self, value=0.0):
        self.last = float(value)
        self.t_last = time.time()

    def apply(self, target):
        now = time.time()
        dt = max(1e-3, now - self.t_last)
        max_step = self.rate * dt if self.rate > 0 else float('inf')
        delta = float(target) - self.last
        if abs(delta) > max_step:
            delta = math.copysign(max_step, delta)
        self.last += delta
        self.t_last = now
        return self.last

# ===================== 자율주행(조향) =====================
class TRTAutoPilot:
    """카메라 → TRT 추론 → 각도(deg) 계산 (x-only tanh: x∈[-1,1])"""
    def __init__(self, trt_path, cam_device=0, width=224, height=224, fps=30, angle_deg_limit=44, debug=False):
        self.debug = debug
        self.angle_lim = int(angle_deg_limit)
        self._running = False
        self._dt = 1.0 / max(1, fps)
        self._use_fp16 = bool(DEFAULTS["TRT_FP16"])
        self._alpha_ang = float(DEFAULTS["ANGLE_LPF_ALPHA"])
        self._sign = float(DEFAULTS["STEER_SIGN"])
        self._bias = float(DEFAULTS["STEER_BIAS_DEG"])
        self._angle = 0.0  # 필터 후 각도

        # TRT 경로
        load_path = trt_path if os.path.exists(trt_path) else DEFAULTS["ALT_TRT_PATH"]
        if not os.path.exists(load_path):
            raise FileNotFoundError(f"TRT not found: {trt_path} or {DEFAULTS['ALT_TRT_PATH']}")

        # TRT 로드
        self.m = TRTModule()
        self.m.load_state_dict(torch.load(load_path))
        self.m.eval()
        if self.debug:
            print(f"[AUTO] TRT loaded: {load_path} | fp16={self._use_fp16} utils_preprocess={_UTILS_PREPROCESS is not None}")

        # 카메라
        self.cam = USBCamera(
            capture_device=int(cam_device),
            capture_width=640, capture_height=480, capture_fps=fps,
            width=width, height=height
        )
        time.sleep(0.3)
        try:
            f0 = self.cam.read()
            if self.debug:
                print(f"[AUTO] frame0 mean={float(f0.mean()):.1f}, shape={tuple(f0.shape)}")
        except Exception as e:
            if self.debug: print("[AUTO] WARN frame0:", repr(e))

        self.th = threading.Thread(target=self._loop, daemon=True)

    @property
    def angle_deg(self):
        return self._angle

    def start(self):
        self._running = True
        self.th.start()

    def stop(self):
        self._running = False
        try: self.th.join(timeout=0.5)
        except Exception: pass
        try: self.cam.cap.release()
        except Exception: pass

    def _loop(self):
        last_log = 0.0
        while self._running:
            try:
                frame = self.cam.read()
                if frame is None:
                    time.sleep(self._dt)
                    continue

                x = preprocess_frame(frame)

                try:
                    with torch.no_grad():
                        y = self.m(x)
                except Exception as e_dtype:
                    if self._use_fp16:
                        if self.debug:
                            print("[AUTO] FP16 failed → FP32 once:", repr(e_dtype))
                        self._use_fp16 = False
                        with torch.no_grad():
                            y = self.m(x.float())
                    else:
                        raise

                y_np = y.detach().float().cpu().numpy().reshape(-1)
                if y_np.size < 1 or not math.isfinite(y_np[0]):
                    time.sleep(self._dt)
                    continue

                # ---- x-only tanh decoder ----
                x_hat = float(y_np[0])
                x_hat = clamp(x_hat, -1.0, 1.0)
                ang_raw = x_hat * self.angle_lim

                # 보정 + 클램프
                ang = (self._sign * ang_raw) + self._bias
                ang = clamp(ang, -self.angle_lim, self.angle_lim)

                # 각도 EMA
                if self._alpha_ang > 0.0:
                    self._angle = (1.0 - self._alpha_ang) * self._angle + self._alpha_ang * ang
                else:
                    self._angle = ang

                # 로그
                now = time.time()
                if self.debug and (now - last_log) > 0.25:
                    print(f"[AUTO] x={x_hat:+.3f} -> ang_raw={ang_raw:+.1f}°, out={self._angle:+.1f}°")
                    last_log = now

            except Exception as e:
                if self.debug:
                    print("[AUTO] inference error:", repr(e))
                    traceback.print_exc()
            time.sleep(self._dt)

# ===================== 조이스틱: START & 브레이크 =====================
class Joystick:
    def __init__(self, js_id=0, debug=False):
        self.debug = debug
        self.js_id = int(js_id)
        self.cruise_on = False
        self.brake = False
        self.is_open = False
        self.codes = { DEFAULTS["JS_CODE_START"]: 'BTN_START' }
        if DEFAULTS["JS_CODE_L2_AXIS"] is not None: self.codes[DEFAULTS["JS_CODE_L2_AXIS"]] = 'L2_AXIS'
        if DEFAULTS["JS_CODE_R2_AXIS"] is not None: self.codes[DEFAULTS["JS_CODE_R2_AXIS"]] = 'R2_AXIS'
        if DEFAULTS["JS_CODE_L2_BTN"]  is not None: self.codes[DEFAULTS["JS_CODE_L2_BTN"]]  = 'L2_BTN'
        if DEFAULTS["JS_CODE_R2_BTN"]  is not None: self.codes[DEFAULTS["JS_CODE_R2_BTN"]]  = 'R2_BTN'
        self._open()

    def _open(self):
        path = f"/dev/input/js{self.js_id}"
        try:
            self.jsdev = open(path, "rb", buffering=0)
            fl = fcntl.fcntl(self.jsdev.fileno(), fcntl.F_GETFL)
            fcntl.fcntl(self.jsdev.fileno(), fcntl.F_SETFL, fl | os.O_NONBLOCK)
            self.is_open = True
            print(f"[JS] open {path} ok")
        except Exception as e:
            self.is_open = False
            print(f"[JS] open {path} failed:", e)

    def read_once(self, timeout=0.02):
        if not self.is_open:
            return
        r,_,_ = select.select([self.jsdev], [], [], timeout)
        if not r:
            return
        try:
            ev = self.jsdev.read(8)
        except OSError as e:
            if e.errno in (errno.EAGAIN, errno.EINTR):
                return
            print("[JS] read error:", e)
            self.is_open = False
            return
        if not ev or len(ev) < 8:
            return

        ts, value, typ, number = struct.unpack('IhBB', ev)
        etyp = typ & ~0x80
        code = (etyp << 8) | number
        name = self.codes.get(code)

        if name is None:
            if self.debug and etyp in (1,2) and value != 0:
                print(f"[JS] unknown code 0x{code:04x} (etyp={etyp}, num={number}, val={value})")
            return

        if name == 'BTN_START' and value == 1:
            self.cruise_on = not self.cruise_on
            print(f"[JS] CRUISE 10% = {self.cruise_on}")

        elif name in ('L2_AXIS','R2_AXIS'):
            v = ((value/32767.0)+1.0)/2.0
            if v > 0.98:
                self.brake = True
                self.cruise_on = False
                if self.debug: print("[JS] BRAKE by", name)

        elif name in ('L2_BTN','R2_BTN'):
            if value == 1:
                self.brake = True
                self.cruise_on = False
                if self.debug: print("[JS] BRAKE by", name)

# ===================== 차량 Driver =====================
class Driver:
    def __init__(self, port=None, debug=False, angle_limit=44, send_rate_hz=20.0):
        self.debug = debug
        self.angle_limit = int(angle_limit)
        self._last_angle = None
        self._last_speed = None
        self._last_ts = 0.0
        self._period = 1.0 / send_rate_hz
        self.bot = Rosmaster(com=port, debug=debug) if port else Rosmaster(debug=debug)

    def set_steer(self, angle_deg):
        if not (isinstance(angle_deg,(int,float)) and math.isfinite(angle_deg)):
            return
        angle = int(clamp(round(angle_deg), -self.angle_limit, self.angle_limit))
        now = time.time()
        if self._last_angle is not None and angle == self._last_angle and (now - self._last_ts) < self._period:
            return
        try:
            self.bot.set_akm_steering_angle(angle, True)
        except TypeError:
            self.bot.set_akm_steering_angle(angle)
        self._last_angle = angle
        self._last_ts = now
        if self.debug:
            print(f"[DRV] steer -> {angle}°")

    def set_speed_abs_fraction(self, fraction):
        f = clamp(float(fraction), 0.0, 1.0)
        dir_flag = 1  # forward
        spd = int(round(100.0 * f))
        self._apply_speed(dir_flag, spd)

    def stop(self):
        try:
            self.bot.set_car_motion(0,0,0)
        except Exception:
            pass
        if self.debug:
            print("[DRV] STOP")

    def _apply_speed(self, dir_flag, spd):
        spd = int(clamp(spd, 0, 100))
        key = (dir_flag, spd)
        now = time.time()
        if self._last_speed is not None and key == self._last_speed and (now - self._last_ts) < self._period:
            return
        if spd == 0:
            self.bot.set_car_motion(0,0,0)
        else:
            self.bot.set_car_run(dir_flag, spd)
        self._last_speed = key
        self._last_ts = now
        if self.debug:
            print(f"[DRV] speed -> dir={dir_flag} spd={spd}%")

# ===================== Main =====================
def main():
    print("[CONFIG]")
    for k in ["TRT_PATH","ALT_TRT_PATH","CAM_INDEX","SERIAL_PORT","JS_INDEX","FPS","SEND_RATE_HZ","DEBUG",
              "ANGLE_LIMIT","ANGLE_LPF_ALPHA","ANGLE_SLEW_DEG_PER_S","START_NEUTRAL_SEC",
              "TRT_FP16","USE_UTILS_PREPROCESS","FALLBACK_NORM","FALLBACK_BGR2RGB",
              "STEER_SIGN","STEER_BIAS_DEG","CRUISE_ABS_FRACTION"]:
        print(f"  {k:>22} = {DEFAULTS[k]}")

    pilot = TRTAutoPilot(DEFAULTS["TRT_PATH"], cam_device=DEFAULTS["CAM_INDEX"],
                         fps=DEFAULTS["FPS"], angle_deg_limit=DEFAULTS["ANGLE_LIMIT"],
                         debug=DEFAULTS["DEBUG"])
    js = Joystick(js_id=DEFAULTS["JS_INDEX"], debug=DEFAULTS["DEBUG"])
    drv = Driver(port=DEFAULTS["SERIAL_PORT"], debug=DEFAULTS["DEBUG"],
                 angle_limit=DEFAULTS["ANGLE_LIMIT"], send_rate_hz=DEFAULTS["SEND_RATE_HZ"])

    print("[INFO] START: cruise 10% ON/OFF, L2/R2: BRAKE")

    # 각도 슬루 제한기 (초기 0°)
    slew = SlewLimiter(DEFAULTS["ANGLE_SLEW_DEG_PER_S"], initial=0.0)

    # START 눌러 켤 때 0° 유지 위한 타이머
    cruise_prev = False
    neutral_until_ts = 0.0

    try:
        pilot.start()
        while True:
            js.read_once()

            # 브레이크
            if js.brake:
                drv.stop()
                js.brake = False

            # START 토글 감지 → 0° 유지 타이머 설정 및 슬루 리셋
            if js.cruise_on and not cruise_prev:
                neutral_until_ts = time.time() + float(DEFAULTS["START_NEUTRAL_SEC"])
                slew.reset(0.0)  # 0°에서 부드럽게 올라가게
            cruise_prev = js.cruise_on

            if js.cruise_on:
                # 목표 각도
                target_angle = pilot.angle_deg

                # 켠 직후엔 0° 유지
                if time.time() < neutral_until_ts:
                    target_angle = 0.0

                # 슬루 제한 적용
                smooth_angle = slew.apply(target_angle)

                drv.set_steer(smooth_angle)
                drv.set_speed_abs_fraction(DEFAULTS["CRUISE_ABS_FRACTION"])
            else:
                drv.set_speed_abs_fraction(0.0)
                # 다음 시작 시 0°에서 시작되도록 하고 싶으면 아래 주석 해제:
                # slew.reset(0.0)

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n[INFO] Ctrl+C — bye")
    except Exception as e:
        print("\n[FATAL] Unhandled exception:", repr(e))
        traceback.print_exc()
    finally:
        try:
            drv.stop()
            pilot.stop()
        except Exception:
            pass
        time.sleep(0.1)

if __name__ == "__main__":
    main()
