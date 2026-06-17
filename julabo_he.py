"""
Julabo HE Series Controller
COM4 / Prolific USB-to-Serial adapter
"""

import serial
import time
import sys

# Default serial settings for Julabo HE
BAUD = 4800
TIMEOUT = 3  # seconds


def find_julabo_port():
    """Scan all COM ports and return the one that responds like a Julabo."""
    from serial.tools import list_ports
    for info in list_ports.comports():
        try:
            s = serial.Serial(port=info.device, baudrate=BAUD,
                              bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
                              stopbits=serial.STOPBITS_ONE, timeout=1,
                              write_timeout=0)
            s.setRTS(True); s.setDTR(True)
            time.sleep(0.2)
            s.reset_input_buffer()
            s.write(b"version\r")
            time.sleep(0.3)
            raw = s.read_until(b"\r")
            s.close()
            decoded = bytes(b & 0x7F for b in raw).decode("ascii", errors="replace").strip()
            if "JULABO" in decoded.upper():
                return info.device
        except Exception:
            pass
    return None


def _detect_baud(port):
    """Try 4800 then 9600; return whichever gets a response."""
    for baud in (4800, 9600):
        try:
            s = serial.Serial(port=port, baudrate=baud, bytesize=serial.EIGHTBITS,
                              parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
                              timeout=2)
            time.sleep(0.3)
            s.reset_input_buffer()
            s.write(b"version\r")
            time.sleep(0.1)
            raw = s.read_until(b"\r")
            resp = bytes(b & 0x7F for b in raw).decode("ascii", errors="replace").strip()
            s.close()
            if resp:
                print(f"  Auto-detected baud rate: {baud} (response: {resp!r})")
                return baud
            s.close()
        except Exception:
            pass
    print(f"  WARNING: no response at 4800 or 9600 — defaulting to 4800")
    return 4800


class JulaboHE:
    def __init__(self, port=PORT, baud=None):
        if baud is None:
            baud = _detect_baud(port)
        self.ser = serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=TIMEOUT,
            write_timeout=None,
        )
        time.sleep(0.3)

    def close(self):
        if self.ser.is_open:
            self.ser.close()

    def _send(self, command: str) -> str:
        """Send a query command and return the response."""
        self.ser.reset_input_buffer()
        self.ser.write((command + "\r").encode("ascii"))
        time.sleep(0.1)
        raw = self.ser.read_until(b"\r")
        return bytes(b & 0x7F for b in raw).decode("ascii", errors="replace").strip()

    def _cmd(self, command: str):
        """Send a set command — device returns nothing, don't wait for response."""
        self.ser.reset_input_buffer()
        self.ser.write((command + "\r").encode("ascii"))
        time.sleep(0.3)

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_version(self) -> str:
        return self._send("version")

    def get_status(self) -> str:
        """Returns a status word; bit 1 = running."""
        return self._send("status")

    def get_temperature(self) -> float:
        """Bath actual temperature in °C."""
        return float(self._send("in_pv_00"))

    def get_setpoint(self) -> float:
        """Active temperature setpoint in °C."""
        return float(self._send("in_sp_00"))

    def get_high_limit(self) -> float:
        """Over-temperature protection limit in °C."""
        return float(self._send("in_sp_03"))

    def get_low_limit(self) -> float:
        """Under-temperature protection limit in °C."""
        return float(self._send("in_sp_04"))

    def get_pump_speed(self) -> int:
        """Pump speed stage (1–4)."""
        return int(self._send("in_mode_05"))

    def is_running(self) -> bool:
        """True if the circulator is active."""
        try:
            status = int(self._send("status"))
            return bool(status & 0x01)
        except ValueError:
            return False

    # ── Write ─────────────────────────────────────────────────────────────────

    def set_setpoint(self, temp: float):
        """Set bath temperature setpoint (°C)."""
        self._cmd(f"out_sp_00 {temp:.2f}")

    def set_pump_speed(self, stage: int):
        """Set pump speed stage 1–4."""
        if not 1 <= stage <= 4:
            raise ValueError("Pump speed stage must be 1–4")
        self._cmd(f"out_mode_05 {stage}")

    def start(self):
        """Start the circulator."""
        self._cmd("out_mode_04 1")

    def stop(self):
        """Stop the circulator."""
        self._cmd("out_mode_04 0")

    # ── Convenience ───────────────────────────────────────────────────────────

    def status_report(self):
        """Print a full status summary."""
        def safe(fn):
            try:
                v = fn()
                return f"{v:.2f} °C" if isinstance(v, float) else str(v)
            except Exception as e:
                return f"(error: {e})"

        print("─" * 40)
        print(f"  Firmware  : {safe(self.get_version)}")
        print(f"  Running   : {safe(self.is_running)}")
        print(f"  Temp (act): {safe(self.get_temperature)}")
        print(f"  Setpoint  : {safe(self.get_setpoint)}")
        print(f"  High limit: {safe(self.get_high_limit)}")
        print(f"  Low limit : {safe(self.get_low_limit)}")
        print(f"  Pump speed: {safe(self.get_pump_speed)}")
        print("─" * 40)


# ── Interactive CLI ────────────────────────────────────────────────────────────

HELP = """
Commands:
  status              Print full status
  temp                Read actual temperature
  set <°C>            Set temperature setpoint
  pump <1-4>          Set pump speed stage
  start               Start circulator
  stop                Stop circulator
  version             Firmware version
  quit / exit         Close connection and exit
"""


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else PORT
    print(f"Connecting to Julabo HE on {port} at {BAUD} baud …")
    try:
        julabo = JulaboHE(port=port)
    except serial.SerialException as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print("Connected.\n" + HELP)
    julabo.status_report()

    try:
        while True:
            try:
                line = input("\njulabo> ").strip()
            except EOFError:
                break

            if not line:
                continue
            parts = line.split()
            cmd = parts[0].lower()

            if cmd in ("quit", "exit"):
                break
            elif cmd == "status":
                julabo.status_report()
            elif cmd == "temp":
                print(f"  Temperature: {julabo.get_temperature():.2f} °C")
            elif cmd == "set":
                if len(parts) < 2:
                    print("  Usage: set <°C>")
                else:
                    reply = julabo.set_setpoint(float(parts[1]))
                    print(f"  → {reply or 'OK'}")
            elif cmd == "pump":
                if len(parts) < 2:
                    print("  Usage: pump <1-4>")
                else:
                    reply = julabo.set_pump_speed(int(parts[1]))
                    print(f"  → {reply or 'OK'}")
            elif cmd == "start":
                julabo.start()
                time.sleep(0.5)
                status = julabo._send("status")
                print(f"  → {'Started — ' + status if status else 'Command sent (check status)'}")
            elif cmd == "stop":
                julabo.stop()
                time.sleep(0.5)
                status = julabo._send("status")
                print(f"  → {'Stopped — ' + status if status else 'Command sent (check status)'}")
            elif cmd == "version":
                print(f"  Firmware: {julabo.get_version()}")
            else:
                print(HELP)

    finally:
        julabo.close()
        print("Connection closed.")


if __name__ == "__main__":
    main()
