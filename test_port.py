import serial, time
from serial.tools import list_ports

for info in list_ports.comports():
    print("Port:", info.device, "|", info.description)
    try:
        s = serial.Serial(port=info.device, baudrate=4800, bytesize=8,
                          parity="N", stopbits=1, timeout=2, write_timeout=0)
        s.setRTS(True); s.setDTR(True); time.sleep(0.3)
        s.reset_input_buffer(); s.write(b"version\r"); time.sleep(0.5)
        raw = s.read_until(b"\r"); s.close()
        decoded = bytes(b & 0x7F for b in raw).decode("ascii", errors="replace").strip()
        print("Response:", repr(decoded))
    except Exception as e:
        print("Error:", e)
