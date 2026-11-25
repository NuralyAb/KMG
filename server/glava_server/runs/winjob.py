"""Объект задания Windows: процесс и все его потомки завершаются вместе, даже если сервер упал."""

import ctypes
import threading
from ctypes import wintypes

EXTENDED_LIMIT_INFORMATION = 9
KILL_ON_JOB_CLOSE = 0x2000
PROCESS_TERMINATE = 0x0001
PROCESS_SET_QUOTA = 0x0100
EXIT_CODE = 1


class _BasicLimits(ctypes.Structure):
    _fields_ = (
        ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER), ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER), ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t), ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD),
    )


class _ExtendedLimits(ctypes.Structure):
    _fields_ = (
        ("BasicLimitInformation", _BasicLimits), ("IoInfo", ctypes.c_ulonglong * 6), ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t),
    )


def _library() -> ctypes.WinDLL:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    handle, flag, number = wintypes.HANDLE, wintypes.BOOL, wintypes.DWORD
    signatures = {
        "CreateJobObjectW": (handle, (ctypes.c_void_p, wintypes.LPCWSTR)), "SetInformationJobObject": (flag, (handle, ctypes.c_int, ctypes.c_void_p, number)),
        "OpenProcess": (handle, (number, flag, number)), "AssignProcessToJobObject": (flag, (handle, handle)),
        "TerminateJobObject": (flag, (handle, wintypes.UINT)), "CloseHandle": (flag, (handle,)),
    }
    for name, (result, arguments) in signatures.items():
        function = getattr(kernel, name)
        function.restype, function.argtypes = result, arguments
    return kernel


KERNEL = _library()


def _checked[T](value: T) -> T:
    if not value:
        raise ctypes.WinError(ctypes.get_last_error())
    return value


class Job:
    def __init__(self, handle: int) -> None:
        self._handle: int | None = handle
        self._lock = threading.Lock()

    @classmethod
    def holding(cls, pid: int) -> "Job":
        job = cls(_checked(KERNEL.CreateJobObjectW(None, None)))
        try:
            job._assign(pid)
        except OSError:
            job.close()
            raise
        return job

    def _assign(self, pid: int) -> None:
        limits = _ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = KILL_ON_JOB_CLOSE
        # сначала процесс, потом «убивать при закрытии»: неудачное назначение не тронет чужой процесс
        process = _checked(KERNEL.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, pid))
        try:
            _checked(KERNEL.AssignProcessToJobObject(self._handle, process))
        finally:
            KERNEL.CloseHandle(process)
        _checked(KERNEL.SetInformationJobObject(self._handle, EXTENDED_LIMIT_INFORMATION, ctypes.byref(limits), ctypes.sizeof(limits)))

    def terminate(self) -> None:
        with self._lock:
            if self._handle:
                _checked(KERNEL.TerminateJobObject(self._handle, EXIT_CODE))

    def close(self) -> None:
        with self._lock:
            if self._handle:
                KERNEL.CloseHandle(self._handle)
                self._handle = None
