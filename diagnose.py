"""
Raw serial diagnostic for Julabo HE — run this first to see what the device sends.
"""
import serial
import time

PORT = "COM4"

BAUD_RATES = [4800, 9600]
TEST_COMMANDS = [
    b"status\r",
    b"out_mode_04 0\r",
    b"out_mode_04 00\r",
    b"stop\r",
    b"STOP\r",
    b"in_mode_04\r",
    b"status\r",
]

def probe(port, baud, rtscts=False, dsrdtr=False):
    label = f"{baud} baud  rtscts={rtscts}  dsrdtr={dsrdtr}"
    print(f"\n{'='*55}")
    print(f"  {label}")
    print(f"{'='*55}")
    try:
        s = serial.Serial(
            port=port, baudrate=baud,
            bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE, timeout=2,
            rtscts=rtscts, dsrdtr=dsrdtr, xonxoff=False
        )
        s.setRTS(True)
        s.setDTR(True)
        time.sleep(0.5)
        for cmd in TEST_COMMANDS:
            s.reset_input_buffer()
            s.write(cmd)
            time.sleep(0.5)
            raw = s.read(s.in_waiting or 1)
            decoded = bytes(b & 0x7F for b in raw).decode("ascii", errors="replace").strip()
            print(f"  {cmd!r:30s} → raw={raw!r}  decoded={decoded!r}")
        s.close()
    except Exception as e:
        print(f"  ERROR: {e}")

probe(PORT, 4800, rtscts=False)

print("\nDone. Share the output above to identify the correct baud rate and command format.")
