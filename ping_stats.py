"""Background ICMP pinger (IcmpSendEcho, no admin needed): latency, jitter and packet loss."""
import collections
import ctypes
import socket
import struct
import threading
import time

ip = ctypes.windll.iphlpapi
ip.IcmpCreateFile.restype = ctypes.c_void_p
ip.IcmpSendEcho.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint16, ctypes.c_void_p,
                            ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32]
ip.IcmpSendEcho.restype = ctypes.c_uint32


class Pinger(threading.Thread):
    def __init__(self, host, interval=1.0, timeout_ms=1000, window=60):
        super().__init__(daemon=True)
        self.addr = struct.unpack("<I", socket.inet_aton(host))[0]
        self.interval, self.timeout = interval, timeout_ms
        self.hist = collections.deque(maxlen=window)          # rtt in ms, or None for a lost packet
        self.lock = threading.Lock()
        self.handle = ip.IcmpCreateFile()

    def ping_once(self):
        data = b"EvilOS" * 4
        reply = ctypes.create_string_buffer(256)
        n = ip.IcmpSendEcho(self.handle, self.addr, data, len(data), None, reply, len(reply), self.timeout)
        if n == 0:
            return None
        _addr, status, rtt = struct.unpack_from("<III", reply.raw)
        return float(rtt) if status == 0 else None

    def run(self):
        while True:
            t0 = time.time()
            try:
                r = self.ping_once()
            except OSError:
                r = None
            with self.lock:
                self.hist.append(r)
            time.sleep(max(0.05, self.interval - (time.time() - t0)))

    def stats(self):
        with self.lock:
            h = list(self.hist)
        if not h:
            return {}
        ok = [v for v in h if v is not None]
        recent = ok[-20:]
        jitter = (sum(abs(a - b) for a, b in zip(recent, recent[1:])) / (len(recent) - 1)) if len(recent) > 1 else 0.0
        return {
            "Ping ms": h[-1] if h[-1] is not None else (ok[-1] if ok else None),
            "Ping jitter": jitter,
            "Ping loss": 100.0 * (len(h) - len(ok)) / len(h),
        }


if __name__ == "__main__":
    p = Pinger("8.8.8.8")
    p.start()
    time.sleep(5.5)
    print(p.stats(), list(p.hist))
