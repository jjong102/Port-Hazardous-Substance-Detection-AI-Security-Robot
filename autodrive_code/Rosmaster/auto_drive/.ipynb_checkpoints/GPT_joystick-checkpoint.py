#!/usr/bin/env python3
# coding=utf-8
import os, struct, sys, time, traceback, errno, fcntl, select, threading
from Rosmaster_Lib import Rosmaster


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
            self._safe_call(self.__robot.set_beep, value)

        elif name == 'MODE':
            log_throttled(f"{name} : {value}")

        elif name == 'BTN_RK1':
            log_throttled(f"{name} : {value}")

        elif name == 'BTN_RK2':
            log_throttled(f"{name} : {value}")

        elif name == "L2":
            value = ((value / 32767) + 1) / 2
            log_throttled("%s : %.3f" % (name, value))
            if int(value) == 1:
                self._safe_call(self.__robot.set_car_motion, 0, 0, 0)

        elif name == "R2":
            value = ((value / 32767) + 1) / 2
            log_throttled("%s : %.3f" % (name, value))
            if int(value) == 1:
                self._safe_call(self.__robot.set_car_motion, 0, 0, 0)

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
