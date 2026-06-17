"""
Julabo HE Series - GUI Controller
"""

import sys, os, subprocess, time, threading, gc, signal, atexit

# Always launch with pythonw.exe (no console window)
_PYW = r"C:\Users\mingx\AppData\Local\Programs\Python\Python312\pythonw.exe"
_PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".julabo_pid")
_this = os.path.abspath(__file__)

if os.path.exists(_PYW) and "pythonw" not in sys.executable.lower():
    subprocess.Popen([_PYW, _this] + sys.argv[1:])
    sys.exit()

# Kill previous instance
if os.path.exists(_PID_FILE):
    try:
        old_pid = int(open(_PID_FILE).read().strip())
        subprocess.call(["taskkill", "/PID", str(old_pid), "/F"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
    except Exception:
        pass
open(_PID_FILE, "w").write(str(os.getpid()))

import tkinter as tk
from tkinter import ttk, messagebox
import serial
from serial.tools import list_ports

BAUD = 4800

# ── Serial driver ─────────────────────────────────────────────────────────────

class JulaboHE:
    def __init__(self):
        port = self._find_port()
        if port is None:
            raise serial.SerialException("Julabo not found — check USB cable")
        self.ser = serial.Serial(
            port=port, baudrate=BAUD,
            bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=2, write_timeout=0,
            rtscts=False, xonxoff=False,
        )
        self.ser.setRTS(True)
        self.ser.setDTR(True)
        time.sleep(0.3)

    def _find_port(self):
        candidates = sorted(list_ports.comports(),
                            key=lambda p: 0 if "PROLIFIC" in (p.description or "").upper() else 1)
        for info in candidates:
            try:
                s = serial.Serial(port=info.device, baudrate=BAUD,
                                  bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
                                  stopbits=serial.STOPBITS_ONE, timeout=1, write_timeout=0)
                s.setRTS(True); s.setDTR(True)
                time.sleep(0.3)
                s.reset_input_buffer()
                s.write(b"version\r")
                time.sleep(0.4)
                raw = s.read_until(b"\r")
                s.close()
                decoded = bytes(b & 0x7F for b in raw).decode("ascii", errors="replace").strip()
                if "JULABO" in decoded.upper():
                    return info.device
            except Exception:
                try: s.close()
                except Exception: pass
        return None

    def close(self):
        try: self.ser.close()
        except Exception: pass

    def _query(self, cmd):
        self.ser.reset_input_buffer()
        self.ser.write((cmd + "\r").encode("ascii"))
        time.sleep(0.1)
        raw = self.ser.read_until(b"\r")
        return bytes(b & 0x7F for b in raw).decode("ascii", errors="replace").strip()

    def _cmd(self, cmd):
        self.ser.reset_input_buffer()
        try:
            self.ser.write((cmd + "\r").encode("ascii"))
        except serial.SerialTimeoutException:
            pass
        time.sleep(0.3)

    # ── reads ──────────────────────────────────────────────────────────────
    def get_version(self):
        return self._query("version")
    def get_temperature(self):
        v = self._query("in_pv_00"); return float(v) if v else None
    def get_setpoint(self):
        v = self._query("in_sp_00"); return float(v) if v else None
    def get_pump_speed(self):
        v = self._query("in_mode_05"); return int(v) if v else 1
    def get_status(self):
        return self._query("status")
    def is_running(self):
        try: return self._query("in_mode_04").strip() == "1"
        except: return False
    def get_sensor_mode(self):
        v = self._query("in_mode_02"); return int(v) if v else 0
    def get_control_mode(self):
        v = self._query("in_mode_01"); return int(v) if v else 0

    # ── writes ─────────────────────────────────────────────────────────────
    def set_setpoint(self, t):      self._cmd(f"out_sp_00 {t:.2f}")
    def set_pump_speed(self, spd):  self._cmd(f"out_mode_05 {spd}")
    def set_sensor_mode(self, m):   self._cmd(f"out_mode_02 {m}")
    def set_control_mode(self, m):  self._cmd(f"out_mode_01 {m}")
    def start(self):
        self._cmd("out_mode_05 1")
        time.sleep(0.3)
        self._cmd("out_mode_04 1")
    def stop(self):
        self._cmd("out_mode_04 0")


# ── GUI ───────────────────────────────────────────────────────────────────────

BG   = "#1e1e2e"
CARD = "#2a2a3e"
ACC  = "#89b4fa"
RED  = "#f38ba8"
GRN  = "#a6e3a1"
FG   = "#cdd6f4"
DIM  = "#6c7086"

class App(tk.Tk):
    POLL_MS = 1500

    def __init__(self):
        super().__init__()
        self.title("Julabo HE Controller")
        self.resizable(False, False)
        self.configure(bg=BG)
        self.julabo = None
        self._lock  = threading.Lock()
        self._poll_job = None
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._connect()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        PAD = dict(padx=12, pady=6)

        # header
        hdr = tk.Frame(self, bg=BG); hdr.pack(fill="x", **PAD)
        tk.Label(hdr, text="JULABO HE", font=("Segoe UI", 18, "bold"),
                 bg=BG, fg=ACC).pack(side="left")
        tk.Button(hdr, text="Reconnect", font=("Segoe UI", 9), bg="#45475a", fg=FG,
                  relief="flat", padx=8, command=self._reconnect
                  ).pack(side="right", pady=6)
        self.lbl_status = tk.Label(hdr, text="● Connecting…",
                                   font=("Segoe UI", 10), bg=BG, fg=DIM)
        self.lbl_status.pack(side="right", padx=8)

        # firmware
        self.lbl_fw = tk.Label(self, text="", font=("Segoe UI", 8), bg=BG, fg=DIM)
        self.lbl_fw.pack()
        ttk.Separator(self).pack(fill="x", padx=12, pady=4)

        # temperature card
        card = tk.Frame(self, bg=CARD); card.pack(fill="x", padx=12, pady=4)
        tk.Label(card, text="ACTUAL TEMPERATURE", font=("Segoe UI", 8),
                 bg=CARD, fg=DIM).pack(pady=(10, 0))
        self.lbl_temp = tk.Label(card, text="--.-  °C",
                                 font=("Segoe UI", 42, "bold"), bg=CARD, fg=FG)
        self.lbl_temp.pack()
        tk.Label(card, text="SETPOINT", font=("Segoe UI", 8), bg=CARD, fg=DIM).pack(pady=(4, 0))
        self.lbl_sp = tk.Label(card, text="--.- °C",
                               font=("Segoe UI", 16), bg=CARD, fg=ACC)
        self.lbl_sp.pack(pady=(0, 10))

        # set temperature
        row = tk.Frame(self, bg=BG); row.pack(fill="x", padx=12, pady=4)
        tk.Label(row, text="Set temp (°C):", font=("Segoe UI", 10),
                 bg=BG, fg=FG).pack(side="left")
        self.entry_sp = tk.Entry(row, width=8, font=("Segoe UI", 10),
                                 bg=CARD, fg=FG, insertbackground=FG,
                                 relief="flat", bd=4)
        self.entry_sp.pack(side="left", padx=6)
        tk.Button(row, text="Apply", font=("Segoe UI", 9, "bold"),
                  bg=ACC, fg="#1e1e2e", relief="flat", padx=10, pady=3,
                  command=self._apply_setpoint).pack(side="left")

        # pump speed
        row2 = tk.Frame(self, bg=BG); row2.pack(fill="x", padx=12, pady=4)
        tk.Label(row2, text="Pump speed:", font=("Segoe UI", 10),
                 bg=BG, fg=FG).pack(side="left")
        self.pump_var = tk.IntVar(value=1)
        for i in range(1, 5):
            tk.Radiobutton(row2, text=str(i), variable=self.pump_var, value=i,
                           font=("Segoe UI", 10), bg=BG, fg=FG,
                           selectcolor=CARD, activebackground=BG,
                           command=self._apply_pump).pack(side="left", padx=4)

        ttk.Separator(self).pack(fill="x", padx=12, pady=6)

        # settings panel
        sf = tk.LabelFrame(self, text=" Settings ", font=("Segoe UI", 9),
                           bg=BG, fg=DIM, bd=1, relief="groove")
        sf.pack(fill="x", padx=12, pady=4)

        tk.Label(sf, text="Sensor:", font=("Segoe UI", 9),
                 bg=BG, fg=FG).grid(row=0, column=0, padx=8, pady=6, sticky="w")
        self.sensor_var = tk.IntVar(value=0)
        for val, lbl in [(0, "Internal"), (1, "Int+Ext"), (2, "External")]:
            tk.Radiobutton(sf, text=lbl, variable=self.sensor_var, value=val,
                           font=("Segoe UI", 9), bg=BG, fg=FG,
                           selectcolor=CARD, activebackground=BG,
                           command=self._apply_sensor
                           ).grid(row=0, column=val+1, padx=6)

        tk.Label(sf, text="Control:", font=("Segoe UI", 9),
                 bg=BG, fg=FG).grid(row=1, column=0, padx=8, pady=6, sticky="w")
        self.control_var = tk.IntVar(value=0)
        for val, lbl in [(0, "Internal"), (1, "External")]:
            tk.Radiobutton(sf, text=lbl, variable=self.control_var, value=val,
                           font=("Segoe UI", 9), bg=BG, fg=FG,
                           selectcolor=CARD, activebackground=BG,
                           command=self._apply_control
                           ).grid(row=1, column=val+1, padx=6)

        ttk.Separator(self).pack(fill="x", padx=12, pady=6)

        # start / stop
        btn_row = tk.Frame(self, bg=BG); btn_row.pack(pady=8)
        tk.Button(btn_row, text="START", font=("Segoe UI", 12, "bold"),
                  bg=GRN, fg="#1e1e2e", relief="flat", padx=20, pady=8,
                  command=self._start).pack(side="left", padx=8)
        tk.Button(btn_row, text="STOP", font=("Segoe UI", 12, "bold"),
                  bg=RED, fg="#1e1e2e", relief="flat", padx=20, pady=8,
                  command=self._stop).pack(side="left", padx=8)

        # status bar + reset usb
        bot = tk.Frame(self, bg=BG); bot.pack(fill="x", padx=12, pady=(0, 8))
        self.lbl_msg = tk.Label(bot, text="", font=("Segoe UI", 9),
                                bg=BG, fg=DIM, anchor="w")
        self.lbl_msg.pack(side="left", fill="x", expand=True)
        tk.Button(bot, text="Reset USB", font=("Segoe UI", 9), bg="#45475a", fg=FG,
                  relief="flat", padx=8, command=self._reset_usb
                  ).pack(side="right")

    # ── connection ────────────────────────────────────────────────────────────

    def _connect(self):
        self._msg("Scanning COM ports…")
        def task():
            try:
                j = JulaboHE()
                fw = j.get_version()
                port = j.ser.port
                with self._lock:
                    self.julabo = j
                self.after(0, lambda: self.lbl_fw.config(text=f"{fw}  [{port}]"))
                self.after(0, lambda: self.lbl_status.config(text="● Connected", fg=GRN))
                self.after(0, self._start_polling)
            except Exception as e:
                msg = str(e)
                if "Access is denied" in msg or "not found" in msg.lower():
                    msg = "Port locked — unplug/replug USB cable then click Reconnect"
                self.after(0, lambda m=msg: (
                    self.lbl_status.config(text="● No Connection", fg=RED),
                    self._msg(m)
                ))
        threading.Thread(target=task, daemon=True).start()

    def _reconnect(self):
        if self._poll_job:
            self.after_cancel(self._poll_job)
            self._poll_job = None
        with self._lock:
            if self.julabo:
                self.julabo.close()
            self.julabo = None
        gc.collect()
        self.lbl_status.config(text="● Connecting…", fg=DIM)
        self.after(500, self._connect)

    def _reset_usb(self):
        if self._poll_job:
            self.after_cancel(self._poll_job)
            self._poll_job = None
        with self._lock:
            if self.julabo:
                self.julabo.close()
            self.julabo = None
        gc.collect()
        self.lbl_status.config(text="● Resetting USB…", fg=DIM)
        self._msg("Resetting Prolific USB driver — approve UAC prompt…")
        ps1 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reset_usb.ps1")
        def task():
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-Command", f'Start-Process powershell -Verb RunAs -Wait -ArgumentList \'-NoProfile -ExecutionPolicy Bypass -File "{ps1}"\''],
                capture_output=True
            )
            self.after(0, lambda: self._msg("USB reset done — reconnecting…"))
            self.after(2000, self._connect)
        threading.Thread(target=task, daemon=True).start()

    # ── polling ───────────────────────────────────────────────────────────────

    def _start_polling(self):
        self._schedule_poll()

    def _schedule_poll(self):
        self._poll_job = self.after(self.POLL_MS, self._poll)

    def _poll(self):
        def task():
            j = self.julabo
            if j is None:
                return
            try:
                with self._lock:
                    temp    = j.get_temperature()
                    sp      = j.get_setpoint()
                    pump    = j.get_pump_speed()
                    running = j.is_running()
                    status  = j.get_status()
                    sensor  = j.get_sensor_mode()
                    control = j.get_control_mode()
                self.after(0, lambda: self._update(temp, sp, pump, running, status, sensor, control))
            except Exception as e:
                msg = str(e)
                self.after(0, lambda m=msg: self._msg(f"Poll: {m}"))
            self.after(0, self._schedule_poll)
        threading.Thread(target=task, daemon=True).start()

    def _update(self, temp, sp, pump, running, status, sensor, control):
        self.lbl_temp.config(text=f"{temp:.2f}  °C" if temp is not None else "--.-  °C")
        self.lbl_sp.config(text=f"{sp:.2f} °C"       if sp   is not None else "--.- °C")
        if pump and pump > 0:
            self.pump_var.set(pump)
        if sensor is not None:
            self.sensor_var.set(sensor)
        if control is not None:
            self.control_var.set(control)
        color = GRN if running else RED
        self.lbl_status.config(text=f"● {'RUNNING' if running else 'STOPPED'}", fg=color)
        if status and "REMOTE" not in status.upper():
            self._msg(f"Device: {status}")

    # ── actions ───────────────────────────────────────────────────────────────

    def _ready(self):
        if self.julabo is None:
            self._msg("Not connected yet.")
            return False
        return True

    def _run(self, fn, msg):
        if not self._ready(): return
        def task():
            try:
                with self._lock: fn()
                self.after(0, lambda: self._msg(msg))
            except Exception as e:
                err = str(e)
                self.after(0, lambda m=err: self._msg(f"Error: {m}"))
        threading.Thread(target=task, daemon=True).start()

    def _apply_setpoint(self):
        if not self._ready(): return
        try:    t = float(self.entry_sp.get().strip())
        except: messagebox.showerror("Invalid", "Enter a number."); return
        self._run(lambda: self.julabo.set_setpoint(t), f"Setpoint → {t:.2f} °C")

    def _apply_pump(self):
        spd = self.pump_var.get()
        self._run(lambda: self.julabo.set_pump_speed(spd), f"Pump speed → {spd}")

    def _apply_sensor(self):
        val = self.sensor_var.get()
        labels = ["Internal", "Int+Ext", "External"]
        self._run(lambda: self.julabo.set_sensor_mode(val), f"Sensor → {labels[val]}")

    def _apply_control(self):
        val = self.control_var.get()
        labels = ["Internal", "External"]
        self._run(lambda: self.julabo.set_control_mode(val), f"Control → {labels[val]}")

    def _start(self):
        self._run(lambda: self.julabo.start(), "Start sent")
'''Function for stopping the Julabo device. It sends a command to the device to stop its operation and updates the message label with a confirmation message.'''
    def _stop(self):
        self._run(lambda: self.julabo.stop(), "Stop sent")

    def _msg(self, text):
        self.lbl_msg.config(text=text)

    # ── close ─────────────────────────────────────────────────────────────────

    def _on_close(self):
        if self._poll_job:
            self.after_cancel(self._poll_job)
        if self.julabo:
            try: self.julabo.close()
            except Exception: pass
        try: os.remove(_PID_FILE)
        except Exception: pass
        self.destroy()
        os._exit(0)


# ── emergency cleanup ─────────────────────────────────────────────────────────

_app = None
def _cleanup():
    if _app and _app.julabo:
        try: _app.julabo.close()
        except Exception: pass
    try: os.remove(_PID_FILE)
    except Exception: pass

if __name__ == "__main__":
    atexit.register(_cleanup)
    signal.signal(signal.SIGINT,  lambda *_: (_cleanup(), os._exit(0)))
    signal.signal(signal.SIGTERM, lambda *_: (_cleanup(), os._exit(0)))
    _app = App()
    _app.mainloop()
