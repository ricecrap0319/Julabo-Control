"""
Diagnose STOP command — run while GUI is CLOSED.
Sends out_mode_04 0 in several formats and checks if machine stops.
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
    time.sleep(0.3)
    raw = s.read_until(b"\r")
    return bytes(b & 0x7F for b in raw).decode("ascii", errors="replace").strip()

def send(s, raw_bytes):
    s.reset_input_buffer()
    s.write(raw_bytes)
    time.sleep(0.5)

def state(s):
    return {
        "in_mode_04": query(s, "in_mode_04"),
        "status":     query(s, "status"),
    }

port = find_port()
print(f"Port: {port}")
s = serial.Serial(port=port, baudrate=BAUD, bytesize=8, parity="N",
                  stopbits=1, timeout=2, write_timeout=2)
s.setRTS(True); s.setDTR(True); time.sleep(0.3)

print("\n--- INITIAL STATE ---")
for k, v in state(s).items(): print(f"  {k}: {v}")

# Make sure machine is running first
print("\n--- STARTING MACHINE ---")
send(s, b"out_mode_05 1\r"); time.sleep(0.3)
send(s, b"out_mode_04 1\r"); time.sleep(1)
for k, v in state(s).items(): print(f"  {k}: {v}")

print("\n--- ATTEMPT 1: out_mode_04 0\\r (standard) ---")
send(s, b"out_mode_04 0\r")
time.sleep(1)
for k, v in state(s).items(): print(f"  {k}: {v}")

if query(s, "in_mode_04") == "1":
    print("\n--- ATTEMPT 2: out_mode_04 0\\r\\n ---")
    send(s, b"out_mode_04 0\r\n")
    time.sleep(1)
    for k, v in state(s).items(): print(f"  {k}: {v}")

if query(s, "in_mode_04") == "1":
    print("\n--- ATTEMPT 3: out_mode_04  0\\r (extra space) ---")
    send(s, b"out_mode_04  0\r")
    time.sleep(1)
    for k, v in state(s).items(): print(f"  {k}: {v}")

if query(s, "in_mode_04") == "1":
    print("\n--- ATTEMPT 4: OUT_MODE_04 0\\r (uppercase) ---")
    send(s, b"OUT_MODE_04 0\r")
    time.sleep(1)
    for k, v in state(s).items(): print(f"  {k}: {v}")

s.close()
print("\nDone.")
