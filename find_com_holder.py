"""Find which process is holding COM3 open using Windows API."""
import ctypes, ctypes.wintypes, sys, os

ntdll    = ctypes.windll.ntdll
kernel32 = ctypes.windll.kernel32

SystemHandleInformation = 16

class SYSTEM_HANDLE(ctypes.Structure):
    _fields_ = [
        ("ProcessId",       ctypes.c_ulong),
        ("ObjectTypeNumber",ctypes.c_byte),
        ("Flags",           ctypes.c_byte),
        ("Handle",          ctypes.c_ushort),
        ("Object",          ctypes.c_void_p),
        ("GrantedAccess",   ctypes.c_ulong),
    ]

class SYSTEM_HANDLE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("HandleCount", ctypes.c_ulong),
        ("Handles",     SYSTEM_HANDLE * 1),
    ]

# Get all handles
size = ctypes.c_ulong(0x10000)
while True:
    buf = ctypes.create_string_buffer(size.value)
    status = ntdll.NtQuerySystemInformation(SystemHandleInformation, buf, size, ctypes.byref(size))
    if status == 0: break
    if status == 0xC0000004:  # STATUS_INFO_LENGTH_MISMATCH
        size.value *= 2
        continue
    print(f"NtQuerySystemInformation failed: {status:#x}")
    sys.exit(1)

count = ctypes.c_ulong.from_buffer(buf).value
print(f"Total handles: {count}")

# Get current process handle value for COM3 by opening it normally... can't.
# Instead look for handles whose object name contains "Serial" or "COM"
PROCESS_DUP_HANDLE = 0x40
DUPLICATE_SAME_ACCESS = 0x2

ObjectNameInformation = 1

class UNICODE_STRING(ctypes.Structure):
    _fields_ = [("Length", ctypes.c_ushort),
                ("MaximumLength", ctypes.c_ushort),
                ("Buffer", ctypes.c_wchar_p)]

found = {}
handles_array = (SYSTEM_HANDLE * count).from_buffer(buf, ctypes.sizeof(ctypes.c_ulong))

for h in handles_array:
    try:
        hProcess = kernel32.OpenProcess(PROCESS_DUP_HANDLE, False, h.ProcessId)
        if not hProcess:
            continue
        hDup = ctypes.wintypes.HANDLE()
        if not kernel32.DuplicateHandle(hProcess, h.Handle, kernel32.GetCurrentProcess(),
                                        ctypes.byref(hDup), 0, False, DUPLICATE_SAME_ACCESS):
            kernel32.CloseHandle(hProcess)
            continue

        buf2 = ctypes.create_string_buffer(1024)
        ret_len = ctypes.c_ulong()
        status2 = ntdll.NtQueryObject(hDup, ObjectNameInformation, buf2, 1024, ctypes.byref(ret_len))
        kernel32.CloseHandle(hDup)
        kernel32.CloseHandle(hProcess)

        if status2 == 0 and ret_len.value > 4:
            name = ctypes.wstring_at(ctypes.addressof(buf2) + 4)
            if name and ("Serial" in name or "\\Device\\CP" in name or "\\Device\\COM" in name.upper()):
                pid = h.ProcessId
                if pid not in found:
                    found[pid] = []
                found[pid].append(name)
    except Exception:
        pass

if found:
    print("\nProcesses holding serial devices:")
    import subprocess
    for pid, names in found.items():
        try:
            out = subprocess.check_output(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                                          text=True).strip().strip('"').split('","')
            pname = out[0] if out else "unknown"
        except Exception:
            pname = "unknown"
        print(f"  PID {pid} ({pname}): {names}")
else:
    print("No process found holding a serial device.")
