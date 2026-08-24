"""İki ESP32'den UDP ile gelen CSI verisini toplayan sunucu (2026-08-24).

MİMARİ (yönetici önerisi):
    telefon hotspot'u = odanın ortasında verici
    ESP32 x2         = odanın uçlarında alıcı, adaptörle beslenir (USB yok)
    laptop (bu kod)  = aynı hotspot'ta, CSI'yi UDP ile toplar

İKİ İŞİ BİRDEN YAPIYOR:
  1. TOPLAMA  - kartlardan gelen CSI satırlarını alır, karta göre ayırır.
     Ayırma "role" sütunundan yapılıyor ("STA-9d9c" / "STA-85b0"); firmware
     bunu kendi MAC'inden üretiyor, CSV formatı değişmiyor.
  2. BESLEME  - kartlara sürekli paket gönderir. CSI, kartın ALDIĞI
     çerçevelerden üretilir; kimse paket göndermezse hız ~10 Hz'e düşer
     (2026-08-24 ölçümü: hotspot'ta flood'suz 10 Hz, flood'la 115 Hz).
       - keşif: saniyede 2 kez YAYIN (broadcast) - kartlar sunucunun adresini
         bu paketlerden öğreniyor, elle IP ayarı gerekmiyor
       - besleme: kart bulununca ona DOĞRUDAN yüksek hızda paket

Kullanım:
    python csi_udp_server.py --duration 20 --output ../data/udp_test
    (veya başka scriptlerden CsiUdpServer sınıfı olarak)
"""
import argparse
import pathlib
import socket
import threading
import time
from collections import defaultdict, deque

PORT = 2223
DISCOVERY_ADDR = "255.255.255.255"
DISCOVERY_INTERVAL = 0.5      # saniyede 2 kez - sadece keşif için, düşük hız
FLOOD_INTERVAL = 0.004        # kart başına ~250 paket/sn
FLOOD_PAYLOAD = b"x" * 64

# recv_time SONA eklendi: iki kartın kendi saatleri bağımsız (her biri kendi
# açılışından beri sayıyor), bu yüzden ortak zaman ekseni laptobun saati olmak
# zorunda. Sona eklendiği için mevcut ayrıştırıcılar bozulmuyor - onlar
# fields[23]'ü ve [..] bloğunu kullanıyor, ikisi de yerinde kalıyor.
HEADER = (
    "type,role,mac,rssi,rate,sig_mode,mcs,bandwidth,smoothing,not_sounding,"
    "aggregation,stbc,fec_coding,sgi,noise_floor,ampdu_cnt,channel,"
    "secondary_channel,local_timestamp,ant,sig_len,rx_state,real_time_set,"
    "real_timestamp,len,CSI_DATA,recv_time\n"
)


class CsiUdpServer:
    def __init__(self, port=PORT, flood=True, keep_sec=30):
        self.port = port
        self.flood = flood
        self.keep_sec = keep_sec
        # kart_kimligi -> deque[(alinma_zamani, satir)]
        self.buffers = defaultdict(deque)
        self.lock = threading.Lock()
        self.boards = {}          # kimlik -> ip
        self.counts = defaultdict(int)
        self.bad_lines = 0
        self._stop = threading.Event()
        self.sock = None
        self._threads = []

    # --- iç işler ---
    def _recv_loop(self):
        while not self._stop.is_set():
            try:
                data, addr = self.sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            text = data.decode("utf-8", errors="replace").strip()
            if not text.startswith("CSI_DATA"):
                continue
            parts = text.split(",", 2)
            if len(parts) < 3:
                self.bad_lines += 1
                continue
            role = parts[1] or "bilinmeyen"
            now = time.time()
            with self.lock:
                self.boards[role] = addr[0]
                self.counts[role] += 1
                buf = self.buffers[role]
                buf.append((now, text))
                cutoff = now - self.keep_sec
                while buf and buf[0][0] < cutoff:
                    buf.popleft()

    def _discovery_loop(self):
        """Yayın paketi: kartlar sunucunun adresini buradan öğreniyor."""
        while not self._stop.is_set():
            try:
                self.sock.sendto(FLOOD_PAYLOAD, (DISCOVERY_ADDR, self.port))
            except OSError:
                pass
            self._stop.wait(DISCOVERY_INTERVAL)

    def _flood_loop(self):
        """Bulunan her karta doğrudan paket - CSI üretim hızını yükseltir."""
        while not self._stop.is_set():
            with self.lock:
                ips = list(set(self.boards.values()))
            if not ips:
                self._stop.wait(0.2)
                continue
            for ip in ips:
                try:
                    self.sock.sendto(FLOOD_PAYLOAD, (ip, self.port))
                except OSError:
                    pass
            time.sleep(FLOOD_INTERVAL)

    # --- dış arayüz ---
    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.settimeout(0.5)
        self.sock.bind(("", self.port))

        targets = [self._recv_loop, self._discovery_loop]
        if self.flood:
            targets.append(self._flood_loop)
        for fn in targets:
            t = threading.Thread(target=fn, daemon=True)
            t.start()
            self._threads.append(t)
        return self

    def stop(self):
        self._stop.set()
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass

    def recent(self, board, seconds):
        """Son N saniyenin satırları (canlı sunucu için)."""
        cutoff = time.time() - seconds
        with self.lock:
            return [t for ts, t in self.buffers[board] if ts >= cutoff]

    def save(self, out_base):
        """Her kart için ayrı CSV yazar; her satırın sonunda geliş zamanı olur."""
        base = pathlib.Path(out_base)
        base.parent.mkdir(parents=True, exist_ok=True)
        written = {}
        with self.lock:
            for role, buf in self.buffers.items():
                path = base.parent / f"{base.name}_{role}.csv"
                with open(path, "w") as f:
                    f.write(HEADER)
                    for ts, line in buf:
                        f.write(f"{line},{ts:.6f}\n")
                written[role] = str(path)
        return written

    def status(self):
        with self.lock:
            return {r: {"ip": self.boards[r], "paket": self.counts[r]}
                    for r in sorted(self.boards)}

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()


def main():
    ap = argparse.ArgumentParser(description="UDP CSI sunucusu")
    ap.add_argument("--duration", type=float, default=20)
    ap.add_argument("--output", default=None,
                    help="Uzantısız yol; her kart için <yol>_<kimlik>.csv yazılır")
    ap.add_argument("--no-flood", action="store_true")
    args = ap.parse_args()

    srv = CsiUdpServer(flood=not args.no_flood, keep_sec=args.duration + 5).start()
    print(f"Dinleniyor: UDP {PORT}. Kartlar aranıyor...")

    t_end = time.time() + args.duration
    last = {}
    while time.time() < t_end:
        time.sleep(2)
        st = srv.status()
        if not st:
            print("  ... henüz kart yok (kartlar hotspot'a bağlandı mı?)")
            continue
        line = []
        for role, info in st.items():
            d = info["paket"] - last.get(role, 0)
            last[role] = info["paket"]
            line.append(f"{role}@{info['ip']}: {d / 2:.0f} Hz")
        print("  " + " | ".join(line))

    srv.stop()
    st = srv.status()
    print(f"\nBitti. {len(st)} kart:")
    for role, info in st.items():
        rate = info["paket"] / args.duration
        print(f"  {role} ({info['ip']}): {info['paket']} paket, {rate:.1f} Hz")

    if args.output and st:
        for role, path in srv.save(args.output).items():
            print(f"  -> {path}")


if __name__ == "__main__":
    main()
