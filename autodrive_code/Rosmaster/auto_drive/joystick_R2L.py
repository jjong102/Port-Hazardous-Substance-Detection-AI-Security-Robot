#!/usr/bin/env python3
# coding: utf-8
"""
START = 저속(10%) 자율주행 ON/OFF
L2/R2 = 브레이크(정지)
- 모델 출력은 [x, y] in [0,1] (apex 좌표)로 가정하고, 중앙(0.5,0.5) 기준 각도를 계산.
- 속도는 항상 '최대속도의 10%' 고정. 조이스틱은 시작/정지 역할만.
"""

# ===================== 설정 =====================
DEFAULTS = {
    # 경로 / 장치
    "TRT_PATH": "road_following_model_trt.pth",
    "CAM_INDEX": 0,                      # /dev/video0
    "SERIAL_PORT": "/dev/ttyCH341USB0",  # 로스마스터 포트
    "JS_INDEX": 0,                       # /dev/input/js0

    # 런타임
    "FPS": 30,
    "SEND_RATE_HZ": 20.0,
    "DEBUG": True,

    # 조향 제한/필터
    "ANGLE_LIMIT": 44,       # 조향 각도 제한(도)
    "SMOOTH_ALPHA": 0.25,    # 0이면 끔 (0.1~0.3 권장)

    # 전처리/정밀도
    "TRT_FP16": True,        # TRT를 fp16로 변환했다면 True가 일반적임
    "NORM": "none",          # 'none' | 'imagenet'
    "BGR2RGB": True,         # USBCamera는 BGR → RGB 변환

    # 출력 해석 (apex 좌표 해석으로 고정)
    "INTERP_MODE": "vec2_centered",   # [x,y] in [0,1]
    "STEER_SIGN": +1.0,               # 좌우 반전 필요시 -1.0
    "STEER_BIAS_DEG": 0.0,            # 영점 보정(도)

    # 주행 속도: 절대 비율(최대속도의 10%)
    "CRUISE_ABS_FRACTION": 0.10,

    # 조이스틱 코드 (장치 따라 다름 → DEBUG 로그 보고 바꿔줘)
    "JS_CODE_START": 0x010B,        # 네 기존 조이스틱 클래스에서 START=0x010B였음
    "JS_CODE_L2_AXIS": 0x0205,      # L2 (axis)
    "JS_CODE_R2_AXIS": 0x0204,      # R2 (axis)
    "JS_CODE_L2_BTN": None,         # 버튼형이면 0x0105 등
    "JS_CODE_R2_BTN": None,
}
# =================================================

import os, time, math, threading, traceback, errno, fcntl, select, struct
import numpy as np
import torch
from torch2trt import TRTModule
from jetcam.usb_camera import USBCamera
from Rosmaster_Lib import Rosmaster

def clamp(v, lo, hi): return lo if v < lo else hi if v > hi else v

def preprocess_bgr(frame):
    """
    입력: OpenCV BGR uint8 (224x224)
    출력: (1,3,224,224) float Tensor on CUDA, dtype은 fp16/fp32 선택
    """
    # BGR -> RGB
    if DEFAULTS["BGR2RGB"]:
        frame = frame[..., ::-1].copy()
    x = torch.from_numpy(frame).permute(2,0,1).contiguous().float() / 255.0
    if DEFAULTS["NORM"].lower() == "imagenet":
        mean = torch.tensor([0.485, 0.456, 0.406]).view(3,1,1)
        std  = torch.tensor([0.229, 0.224, 0.225]).view(3,1,1)
        x = (x - mean) / std
    x = x.unsqueeze(0).cuda(non_blocking=True)
    return x

# ===================== 자율주행(조향) =====================
class TRTAutoPilot:
    """카메라 → TRT 추론 → 각도(deg) 계산"""
    def __init__(self, trt_path, cam_device=0, width=224, height=224, fps=30, angle_deg_limit=44, debug=False):
        self.debug = debug
        self.angle_lim = int(angle_deg_limit)
        self._running = False
        self._angle = 0.0
        self._dt = 1.0 / max(1, fps)
        self._use_fp16 = bool(DEFAULTS["TRT_FP16"])
        self._alpha = float(DEFAULTS["SMOOTH_ALPHA"])
        self._sign = float(DEFAULTS["STEER_SIGN"])
        self._bias = float(DEFAULTS["STEER_BIAS_DEG"])

        if not os.path.exists(trt_path):
            raise FileNotFoundError(f"TRT file not found: {trt_path}")

        # TRT 로드
        self.m = TRTModule()
        self.m.load_state_dict(torch.load(trt_path))
        self.m.eval()
        if self.debug:
            print(f"[AUTO] TRT loaded: {trt_path} | fp16={self._use_fp16} norm={DEFAULTS['NORM']}")

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
    def angle_deg(self): return self._angle

    def start(self):
        self._running = True
        self.th.start()

    def stop(self):
        self._running = False
        try: self.th.join(timeout=0.5)
        except Exception: pass
        try: self.cam.cap.release()
        except Exception: pass

    def _interpret_vec2_centered(self, y_np):
        """
        y_np: [x, y] in [0,1]
        angle = atan2(0.5 - y, x - 0.5) (deg)
        """
        if y_np.size < 2: return None
        x, y = float(y_np[0]), float(y_np[1])
        if not (math.isfinite(x) and math.isfinite(y)): return None
        ang = math.degrees(math.atan2(0.5 - y, x - 0.5))
        return ang

    def _loop(self):
        last_log = 0.0
        while self._running:
            try:
                frame = self.cam.read()
                if frame is None:
                    time.sleep(self._dt); continue

                x = preprocess_bgr(frame)
                x_in = x.half() if self._use_fp16 else x.float()

                try:
                    with torch.no_grad():
                        y = self.m(x_in)
                except Exception as e_dtype:
                    # fp16 문제시 자동 FP32 폴백
                    if self._use_fp16:
                        if self.debug: print("[AUTO] FP16 failed → FP32 once:", repr(e_dtype))
                        self._use_fp16 = False
                        with torch.no_grad():
                            y = self.m(x.float())
                    else:
                        raise

                y_np = y.detach().float().cpu().numpy().reshape(-1)

                # ---- 여기가 핵심: apex [x,y] 해석을 고정 ----
                angle = self._interpret_vec2_centered(y_np)
                if angle is None or not math.isfinite(angle):
                    time.sleep(self._dt); continue

                # 방향/바이어스 보정 + 클램프 + 스무딩
                angle = (self._sign * angle) + self._bias
                angle = clamp(angle, -self.angle_lim, self.angle_lim)
                self._angle = (1.0 - self._alpha)*self._angle + self._alpha*angle if self._alpha>0 else angle

                # 디버그 로그 (원시 출력/최종각)
                now = time.time()
                if self.debug and (now - last_log) > 0.25:
                    raw = ", ".join(f"{v:.3f}" for v in y_np[:4])
                    print(f"[AUTO] raw=[{raw}] -> angle={self._angle:.1f}°")
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
        if not self.is_open: return
        r,_,_ = select.select([self.jsdev], [], [], timeout)
        if not r: return
        try:
            ev = self.jsdev.read(8)
        except OSError as e:
            if e.errno in (errno.EAGAIN, errno.EINTR): return
            print("[JS] read error:", e); self.is_open=False; return
        if not ev or len(ev)<8: return
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
            v = ((value/32767.0)+1.0)/2.0  # 0..1
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
        if not (isinstance(angle_deg,(int,float)) and math.isfinite(angle_deg)): return
        angle = int(clamp(round(angle_deg), -self.angle_limit, self.angle_limit))
        now = time.time()
        if self._last_angle is not None and angle == self._last_angle and (now-self._last_ts) < self._period:
            return
        try: self.bot.set_akm_steering_angle(angle, True)
        except TypeError: self.bot.set_akm_steering_angle(angle)
        self._last_angle = angle; self._last_ts = now
        if self.debug: print(f"[DRV] steer -> {angle}°")

    def set_speed_abs_fraction(self, fraction):
        f = clamp(float(fraction), 0.0, 1.0)
        dir_flag = 1
        spd = int(round(100.0 * f))
        self._apply_speed(dir_flag, spd)

    def stop(self):
        try: self.bot.set_car_motion(0,0,0)
        except Exception: pass
        if self.debug: print("[DRV] STOP")

    def _apply_speed(self, dir_flag, spd):
        spd = int(clamp(spd,0,100))
        key = (dir_flag, spd)
        now = time.time()
        if self._last_speed is not None and key == self._last_speed and (now-self._last_ts) < self._period:
            return
        if spd == 0: self.bot.set_car_motion(0,0,0)
        else:        self.bot.set_car_run(dir_flag, spd)
        self._last_speed = key; self._last_ts = now
        if self.debug: print(f"[DRV] speed -> dir={dir_flag} spd={spd}%")

# ===================== Main =====================
def main():
    print("[CONFIG]")
    for k in ["TRT_PATH","CAM_INDEX","SERIAL_PORT","JS_INDEX","FPS","SEND_RATE_HZ","DEBUG",
              "ANGLE_LIMIT","SMOOTH_ALPHA","NORM","TRT_FP16","INTERP_MODE","STEER_SIGN","STEER_BIAS_DEG",
              "CRUISE_ABS_FRACTION"]:
        print(f"  {k:>18} = {DEFAULTS[k]}")

    pilot = TRTAutoPilot(DEFAULTS["TRT_PATH"], cam_device=DEFAULTS["CAM_INDEX"],
                         fps=DEFAULTS["FPS"], angle_deg_limit=DEFAULTS["ANGLE_LIMIT"],
                         debug=DEFAULTS["DEBUG"])
    js = Joystick(js_id=DEFAULTS["JS_INDEX"], debug=DEFAULTS["DEBUG"])
    drv = Driver(port=DEFAULTS["SERIAL_PORT"], debug=DEFAULTS["DEBUG"],
                 angle_limit=DEFAULTS["ANGLE_LIMIT"], send_rate_hz=DEFAULTS["SEND_RATE_HZ"])

    print("[INFO] START: cruise 10% ON/OFF, L2/R2: BRAKE")

    try:
        pilot.start()
        while True:
            js.read_once()

            if js.brake:
                drv.stop()
                js.brake = False

            if js.cruise_on:
                drv.set_steer(pilot.angle_deg)
                drv.set_speed_abs_fraction(DEFAULTS["CRUISE_ABS_FRACTION"])
            else:
                drv.set_speed_abs_fraction(0.0)

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n[INFO] Ctrl+C — bye")
    except Exception as e:
        print("\n[FATAL] Unhandled exception:", repr(e))
        traceback.print_exc()
    finally:
        try: drv.stop(); pilot.stop()
        except Exception: pass
        time.sleep(0.1)

if __name__ == "__main__":
    main()
