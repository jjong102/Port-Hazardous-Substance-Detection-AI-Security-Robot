#!/usr/bin/env python3
# coding=utf-8
import os, struct, sys, time, traceback, errno, fcntl, select, threading
from Rosmaster_Lib import Rosmaster

# ===================== BrakeAlerter (부저/LED 박자 패턴) =====================
class BrakeAlerter:
    """
    브레이크 시 사용자 지정 박자 패턴으로 부저/LED 알림.
      - PATTERN_BEATS: (label, beats, color_idx) — color_idx가 None이면 LED OFF(REST)
      - BPM으로 1박 시간 결정, on_ms = beats × (60000/BPM)
      - 이벤트 사이 아주 짧은 간격 INTER_GAP_BEATS × beat_ms
    START나 스로틀 재개, 트리거 해제 등 주행 재개 신호 시 stop()을 호출해 OFF.
    """
    # 색상 순환: 빨, 주, 노  (REST에서는 LED OFF)
    COLORS = [(255, 0, 0), (255, 165, 0), (255, 255, 0)]

    # (label, beats, color_idx) — color_idx는 None이면 LED OFF(REST)
    PATTERN_BEATS = [
        ("대",   1.0,   0),
        ("한",   0.5,   1),
        ("민",   0.7,   2),
        ("국",   0.7,   0),
        ("REST", 0.3,   None),  # 쉬고
        ("짝1",  0.5,   1),
        ("짝2",  0.7,   2),
        ("짝3",  0.3,   0),
        ("찍4",  0.7,   1),
        ("짝5",  0.4,   2),
        ("REST", 2.0,   None),
    ]

    # 템포/간격
    BPM = 120.0            # 1박 = 500ms (원하면 110~140 사이로 조절)
    INTER_GAP_BEATS = 0.05 # 이벤트 간 아주 짧은 쉼 (0.03~0.10 추천)

    def __init__(self, bot: Rosmaster, debug=False):
        self.bot = bot
        self.debug = debug
        self._th = None
        self._stop_evt = threading.Event()
        self._running = False

    def start(self):
        if self._running:
            return
        if self.debug: print("[ALERT] on")
        self._stop_evt.clear()
        self._th = threading.Thread(target=self._loop, daemon=True)
        self._running = True
        self._th.start()

    def stop(self):
        if not self._running:
            self._safe_off()
            return
        self._stop_evt.set()
        try: self._th.join(timeout=0.5)
        except Exception: pass
        self._running = False
        self._safe_off()
        if self.debug: print("[ALERT] off")

    def _safe_off(self):
        # 부저/LED 안전 종료
        try: self.bot.set_beep(0)
        except Exception: pass
        try: self.bot.set_colorful_lamps(0xff, 0, 0, 0)
        except Exception: pass

    def _loop(self):
        beat_ms = 60000.0 / float(self.BPM)
        gap_ms  = self.INTER_GAP_BEATS * beat_ms
        step = 0
        while not self._stop_evt.is_set():
            label, beats, color_idx = self.PATTERN_BEATS[step % len(self.PATTERN_BEATS)]
            on_ms = max(30, int(round(beats * beat_ms)))  # 너무 짧으면 30ms로 클램프

            # LED 설정
            try:
                if color_idx is None:
                    self.bot.set_colorful_lamps(0xff, 0, 0, 0)  # REST: LED OFF
                else:
                    r, g, b = self.COLORS[color_idx % len(self.COLORS)]
                    self.bot.set_colorful_lamps(0xff, r, g, b)
            except Exception as e:
                if self.debug: print("[ALERT] set_color err:", e)

            # 부저
            try:
                if label == "REST":
                    # 완전 무음 쉬기
                    if self._stop_evt.wait(on_ms / 1000.0):
                        break
                else:
                    # 지속음: beats × beat_ms 만큼 울림
                    self.bot.set_beep(on_ms)
                    if self._stop_evt.wait(on_ms / 1000.0):
                        break
            except Exception as e:
                if self.debug: print("[ALERT] beep err:", e)

            # 이벤트 간 아주 짧은 간격
            if gap_ms > 0:
                if self._stop_evt.wait(gap_ms / 1000.0):
                    break

            step += 1

# ===================== Joystick =====================
# V1.2.1 (robust joystick + decoupled TX + Rosmaster API signature fallback)
class Rosmaster_Joystick(object):
    def __init__(self, robot: Rosmaster, js_id=0, debug=False):
        self.__debug = debug
        self.__js_id = int(js_id)
        self.__js_isOpen = False
        self.__robot = robot
        self.__ignore_count = 24

        # speed / scale
        self.__WIDTH_SCALE_X = 30
        self.__WIDTH_SCALE_Y = 0.2
        self.__WIDTH_SCALE_Z = 45.0

        self.__akm_angle = 0
        self.__car_back = False

        # states
        self.STATE_OK = 0
        self.STATE_NO_OPEN = 1
        self.STATE_DISCONNECT = 2
        self.STATE_KEY_BREAK = 3

        # debug throttling
        self.__raw_debug = debug
        self._last_log_ts = 0.0
        self._log_interval = 0.15  # seconds

        # steering TX control
        self._angle_min = -44
        self._angle_max = 44
        self._angle_delta_min = 2        # deg: min change to send
        self._send_rate_hz = 20.0        # max TX rate
        self._last_angle_sent = None
        self._last_send_ts = 0.0

        # run flag
        self._running = True

        # ---- NEW: 브레이크 알림 컨트롤러 ----
        self._alerter = BrakeAlerter(self.__robot, debug=self.__debug)

        # list devices
        print('Joystick Available devices:')
        for fn in os.listdir('/dev/input'):
            if fn.startswith('js'):
                print('    /dev/input/%s' % (fn))

        # open js
        self._open_js()

        # function map (adjust per your gamepad if needed)
        self.__function_names = {
            # BUTTON FUNCTION
            0x0100: 'A',
            0x0101: 'B',
            0x0103: 'X',
            0x0104: 'Y',
            0x0106: 'L1',
            0x0107: 'R1',
            0x0108: 'L2_1',
            0x0109: 'R2_1',
            0x010A: 'SELECT',
            0x010B: 'START',
            0x010D: 'BTN_RK1',
            0x010E: 'BTN_RK2',

            # AXIS FUNCTION
            0x0200: 'RK1_LEFT_RIGHT',
            0x0201: 'RK1_UP_DOWN',
            0x0202: 'RK2_LEFT_RIGHT',   # (장치에 따라 0x0203과 교체 필요할 수 있음)
            0x0203: 'RK2_UP_DOWN',
            0x0204: 'R2',
            0x0205: 'L2',
            0x0206: 'WSAD_LEFT_RIGHT',
            0x0207: 'WSAD_UP_DOWN',
        }

        # start TX thread (decoupled from input)
        self._tx_thread = threading.Thread(target=self._tx_loop, daemon=True)
        self._tx_thread.start()

    # ---------- low-level device ----------
    def _open_js(self):
        try:
            js = '/dev/input/js' + str(self.__js_id)
            self.__jsdev = open(js, 'rb', buffering=0)
            # non-blocking
            flags = fcntl.fcntl(self.__jsdev.fileno(), fcntl.F_GETFL)
            fcntl.fcntl(self.__jsdev.fileno(), fcntl.F_SETFL, flags | os.O_NONBLOCK)
            self.__js_isOpen = True
            print('---Opening %s Succeeded---' % js)
        except Exception as e:
            self.__js_isOpen = False
            print('---Failed To Open /dev/input/js%s--- (%r)' % (self.__js_id, e))

    def __del__(self):
        try:
            self._running = False
        except Exception:
            pass
        try:
            if getattr(self, "_tx_thread", None):
                self._tx_thread.join(timeout=0.2)
        except Exception:
            pass
        # ---- NEW: alerter 안전 종료 ----
        try:
            self._alerter.stop()
        except Exception:
            pass
        try:
            if self.__js_isOpen:
                self.__jsdev.close()
        except Exception:
            pass
        if self.__debug:
            print("\n---Joystick DEL---\n")

    def is_Opened(self):
        return self.__js_isOpen

    # ---------- robot helpers ----------
    def _safe_call(self, fn, *args, **kwargs):
        try:
            fn(*args, **kwargs)
            return True
        except Exception as e:
            if self.__debug:
                print("Robot call error:", repr(e))
                traceback.print_exc()
            return False

    def _clamp_angle(self, angle):
        return int(max(self._angle_min, min(self._angle_max, round(angle))))

    def _call_set_angle(self, angle, blocking_hint=True):
        """Support both Rosmaster.set_akm_steering_angle(angle[, blocking]) signatures."""
        angle = self._clamp_angle(angle)
        try:
            # try (angle, blocking)
            self.__robot.set_akm_steering_angle(angle, blocking_hint)
            return True
        except TypeError:
            # fallback: (angle) only
            try:
                self.__robot.set_akm_steering_angle(angle)
                return True
            except Exception as e:
                if self.__debug:
                    print("set_akm_steering_angle(angle) error:", repr(e))
                    traceback.print_exc()
                return False
        except Exception as e:
            if self.__debug:
                print("set_akm_steering_angle(angle, blocking) error:", repr(e))
                traceback.print_exc()
            return False

    def _send_steer_angle_once(self, angle, blocking=True):
        angle = self._clamp_angle(angle)
        now = time.time()
        should_send = (
            self._last_angle_sent is None
            or abs(angle - self._last_angle_sent) >= self._angle_delta_min
            or (now - self._last_send_ts) >= (1.0 / self._send_rate_hz)
        )
        if not should_send:
            return False
        ok = self._call_set_angle(angle, blocking_hint=blocking)
        if ok:
            self._last_angle_sent = angle
            self._last_send_ts = now
        return ok

    def _tx_loop(self):
        """Dedicated TX loop: run at fixed cadence, send latest steering angle safely."""
        interval = 1.0 / self._send_rate_hz
        while self._running:
            try:
                self._send_steer_angle_once(self.__akm_angle, True)
            except Exception as e:
                if self.__debug:
                    print("TX loop error:", repr(e))
                    traceback.print_exc()
            time.sleep(interval)

    # ---------- helpers ----------
    def _stop_alert_on_drive(self):
        """스로틀/주행 재개 시 알림 종료."""
        try:
            self._alerter.stop()
        except Exception:
            pass

    # ---------- event processing ----------
    def __data_processing(self, name, value):
        now = time.time()
        def log_throttled(msg):
            if not self.__debug:
                return
            if (now - self._last_log_ts) >= self._log_interval:
                print(msg)
                self._last_log_ts = now

        if name == "RK1_LEFT_RIGHT":
            value = -value / 32767
            log_throttled("%s : %.3f" % (name, value))

        elif name == 'RK1_UP_DOWN':
            value = -value / 32767
            log_throttled("%s : %.3f" % (name, value))
            fvalue = self.__WIDTH_SCALE_X * value / 100.0
            if value >= 0:
                self._safe_call(self.__robot.set_car_run, 1, fvalue * 100)
            else:
                self._safe_call(self.__robot.set_car_run, 2, -fvalue * 100)
            # 주행 재개 시 알림 종료
            if abs(value) > 1e-3:
                self._stop_alert_on_drive()

        elif name == 'RK2_LEFT_RIGHT':
            value = -value / 32767
            log_throttled("%s : %.3f" % (name, value))
            fvalue = int(self.__WIDTH_SCALE_Z * -value)
            self.__akm_angle = fvalue  # TX thread picks this up

        elif name == 'RK2_UP_DOWN':
            value = value / 32767
            log_throttled("%s : %.3f" % (name, value))

        elif name == 'A':
            log_throttled(f"{name} : {value}")

        elif name == 'B':
            log_throttled(f"{name} : {value}")
            self.__akm_angle = self._clamp_angle(self.__akm_angle + 2)

        elif name == 'X':
            log_throttled(f"{name} : {value}")
            self.__akm_angle = self._clamp_angle(self.__akm_angle - 2)

        elif name == 'Y':
            log_throttled(f"{name} : {value}")

        elif name == 'L1':
            log_throttled(f"{name} : {value}")
            self.__WIDTH_SCALE_X = 50

        elif name == 'R1':
            log_throttled(f"{name} : {value}")
            self.__WIDTH_SCALE_X = 30

        elif name == 'SELECT':
            log_throttled(f"{name} : {value}")

        elif name == 'START':
            log_throttled(f"{name} : {value}")
            # 기존 동작 유지 + 알림 종료 (주행 재개 의도)
            self._safe_call(self.__robot.set_beep, value)
            self._stop_alert_on_drive()

        elif name == 'MODE':
            log_throttled(f"{name} : {value}")

        elif name == 'BTN_RK1':
            log_throttled(f"{name} : {value}")

        elif name == 'BTN_RK2':
            log_throttled(f"{name} : {value}")

        elif name == "L2":
            # 0..1로 정규화
            value = ((value / 32767) + 1) / 2
            log_throttled("%s : %.3f" % (name, value))
            if value >= 0.98:
                # 브레이크: 정지 + 알림 시작
                self._safe_call(self.__robot.set_car_motion, 0, 0, 0)
                self._alerter.start()
            elif value <= 0.10:
                # 트리거 해제 시 알림 종료
                self._stop_alert_on_drive()

        elif name == "R2":
            value = ((value / 32767) + 1) / 2
            log_throttled("%s : %.3f" % (name, value))
            if value >= 0.98:
                self._safe_call(self.__robot.set_car_motion, 0, 0, 0)
                self._alerter.start()
            elif value <= 0.10:
                self._stop_alert_on_drive()

        elif name == 'WSAD_LEFT_RIGHT':
            value = -value / 32767
            log_throttled("%s : %.3f" % (name, value))
            # fvalue = (value * self.__WIDTH_SCALE_Y)

        elif name == 'WSAD_UP_DOWN':
            value = -value / 32767
            log_throttled("%s : %.3f" % (name, value))
            fvalue = int(value * self.__WIDTH_SCALE_X)
            if value == 0:
                if self.__car_back:
                    self.__car_back = False
                    self._safe_call(self.__robot.set_car_motion, 0, 0, 0)
            elif value > 0:
                self._safe_call(self.__robot.set_car_run, 1, fvalue)
            else:
                self.__car_back = True
                self._safe_call(self.__robot.set_car_run, 2, -fvalue)
            # 주행 재개 시 알림 종료
            if abs(value) > 1e-3:
                self._stop_alert_on_drive()

    # ---------- polling ----------
    def joystick_handle(self):
        """Non-blocking read with select(); only real I/O errors mark disconnect."""
        if not self.__js_isOpen:
            return self.STATE_NO_OPEN
        try:
            # wait up to 20ms
            r, _, _ = select.select([self.__jsdev], [], [], 0.02)
            if not r:
                return self.STATE_OK

            try:
                evbuf = self.__jsdev.read(8)
            except OSError as e:
                # transient
                if e.errno in (errno.EAGAIN, errno.EINTR):
                    return self.STATE_OK
                # hard I/O error => disconnect
                if self.__debug:
                    print("Joystick read OSError:", e, "errno=", getattr(e, "errno", None))
                self.__js_isOpen = False
                print('---Joystick Disconnected---')
                return self.STATE_DISCONNECT

            if not evbuf or len(evbuf) < 8:
                return self.STATE_OK

            timestamp, value, typ, number = struct.unpack('IhBB', evbuf)
            # strip init flag(0x80)
            etyp = typ & ~0x80
            func = (etyp << 8) | number
            name = self.__function_names.get(func)

            if name is not None:
                self.__data_processing(name, value)
            else:
                if self.__ignore_count > 0:
                    self.__ignore_count -= 1
                elif self.__debug or self.__raw_debug:
                    print(f"UNMAPPED type=0x{typ:02X} etype=0x{etyp:02X} number={number} func=0x{func:04X} value={value}")

            return self.STATE_OK

        except KeyboardInterrupt:
            if self.__debug:
                print('Key Break Joystick')
            return self.STATE_KEY_BREAK

        except Exception as e:
            # non-I/O errors shouldn't mark disconnect
            if self.__debug:
                print("Joystick non-fatal error:", repr(e))
                traceback.print_exc()
            return self.STATE_OK

    def reconnect(self):
        try:
            self._open_js()
            self.__ignore_count = 24
            return self.__js_isOpen
        except Exception:
            self.__js_isOpen = False
            return False


if __name__ == '__main__':
    g_debug = True
    if len(sys.argv) > 1:
        if str(sys.argv[1]) == "debug":
            g_debug = True
    print("debug=", g_debug)

    # 권장: 포트 명시해서 자동탐지 불안정 제거
    # g_bot = Rosmaster(com='/dev/ttyUSB0', debug=g_debug)
    g_bot = Rosmaster(debug=g_debug)

    js = Rosmaster_Joystick(g_bot, debug=g_debug)
    try:
        while True:
            state = js.joystick_handle()
            if state != js.STATE_OK:
                if state == js.STATE_KEY_BREAK:
                    break
                time.sleep(0.2)
                js.reconnect()
    except KeyboardInterrupt:
        pass
    del js
