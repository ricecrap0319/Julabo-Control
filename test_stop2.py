"""
Brute-force stop command finder — run with GUI closed.
Tries every plausible stop command and reports what changes.
"""
import serial, time
from serial.tools import list_ports

BAUD = 4800

def find_port():
    for p in list_ports.comports():
        if "PROLIFIC" in (p.description or "").upper():
            return p.device
    return None

def query(s, cmd):
    s.reset_input_buffer()
    s.write((cmd + "\r").encode("ascii"))
    time.sleep(0.4)
    raw = s.read_until(b"\r")
    return bytes(b & 0x7F for b in raw).decode("ascii", errors="replace").strip()

def send_raw(s, raw_bytes, label):
    s.reset_input_buffer()
    s.write(raw_bytes)
    time.sleep(0.8)
    m04   = query(s, "in_mode_04")
    stat  = query(s, "status")
    changed = m04 != prev_m04 or stat != prev_stat
    marker = "  <<< CHANGED" if changed else ""
    print(f"  [{label}]  in_mode_04={m04}  status={stat}{marker}")
    return m04, stat

port = find_port()
print(f"Port: {port}\n")
s = serial.Serial(port=port, baudrate=BAUD, bytesize=8, parity="N",
                  stopbits=1, timeout=2, write_timeout=2)
s.setRTS(True); s.setDTR(True); time.sleep(0.3)

prev_m04  = query(s, "in_mode_04")
prev_stat = query(s, "status")
print(f"Initial: in_mode_04={prev_m04}  status={prev_stat}\n")

candidates = [
    (b"out_mode_04 0\r",   "out_mode_04 0\\r"),
    (b"out_mode_04 00\r",  "out_mode_04 00\\r"),
    (b"out_mode_04 0 \r",  "out_mode_04 0 \\r (trailing space)"),
    (b"out_mode_04\t0\r",  "out_mode_04 TAB 0\\r"),
    (b"OUT_MODE_04 0\r",   "OUT_MODE_04 0 (uppercase)"),
    (b"stop\r",            "stop\\r"),
    (b"STOP\r",            "STOP\\r"),
    (b"out_mode_04 0\r\n", "out_mode_04 0\\r\\n"),
    (b"out_mode_04 0\n",   "out_mode_04 0\\n only"),
    (b"out_mode_05 0\r",   "out_mode_05 0 (pump off)"),
]

for raw, label in candidates:
    prev_m04, prev_stat = query(s, "in_mode_04"), query(s, "status")
    send_raw(s, raw, label)
    time.sleep(0.3)

s.close()
print("\nDone.")
