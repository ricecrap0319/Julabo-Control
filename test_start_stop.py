import serial, time

PORT = "COM4"
BAUD = 4800

def query(s, cmd):
    s.reset_input_buffer()
    try: s.write((cmd + "\r").encode("ascii"))
    except serial.SerialTimeoutException: pass
    time.sleep(0.2)
    raw = s.read_until(b"\r")
    return bytes(b & 0x7F for b in raw).decode("ascii", errors="replace").strip()

def send(s, cmd):
    s.reset_input_buffer()
    try: s.write((cmd + "\r").encode("ascii"))
    except serial.SerialTimeoutException: pass
    time.sleep(0.5)

s = serial.Serial(port=PORT, baudrate=BAUD, bytesize=8, parity="N",
                  stopbits=1, timeout=2, write_timeout=2)
s.setRTS(True); s.setDTR(True); time.sleep(0.3)

def state():
    return {
        "status"    : query(s, "status"),
        "in_mode_04": query(s, "in_mode_04"),
        "in_mode_05": query(s, "in_mode_05"),
        "in_mode_01": query(s, "in_mode_01"),
        "in_mode_02": query(s, "in_mode_02"),
        "temp"      : query(s, "in_pv_00"),
        "setpoint"  : query(s, "in_sp_00"),
    }

print("=== INITIAL STATE ===")
for k,v in state().items(): print(f"  {k}: {v}")

# Set pump speed first, then start
print("\n=== SET PUMP SPEED 1 ===")
send(s, "out_mode_05 1")
print("  in_mode_05:", query(s, "in_mode_05"))

print("\n=== START (out_mode_04 1) ===")
send(s, "out_mode_04 1")
time.sleep(1)
for k,v in state().items(): print(f"  {k}: {v}")

print("\n=== STOP (out_mode_04 0) ===")
send(s, "out_mode_04 0")
time.sleep(1)
for k,v in state().items(): print(f"  {k}: {v}")

s.close()
