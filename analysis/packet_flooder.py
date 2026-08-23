"""ESP32'ye sürekli UDP paketi gönderip CSI üretim hızını yükselten yardımcı.

NEDEN GEREKLİ: CSI, ESP32'nin GÖNDERDİĞİ değil, ALDIĞI çerçevelerden üretilir.
Normal bir ağda kart sadece AP beacon'larını alır (~100ms aralık = ~10 Hz).
Laptop'tan sürekli paket gönderince kart her pakette CSI üretir.

ÖLÇÜM (2026-08-19): sadece beacon 2.7 Hz -> flood ile 144.9 Hz (RSSI -61 dBm).
Sinyal gücü kritik: RSSI -77 dBm'de flood işe yaramıyor (paketler ulaşmıyor).
"""
import socket
import threading
import time

# DİKKAT: ESP32 hangi ağa bağlandıysa onun IP'si yazılmalı ve laptop da AYNI ağda
# olmalı. Farklı ağlardaysa flood paketleri karta hiç ulaşmaz (sessizce başarısız
# olur, sadece hız düşük kalır). Kart bağlanınca seri porta "Got ip:X.X.X.X" yazar
# - detect_esp_ip() bunu okuyabilir.
DEFAULT_ESP_IP = "172.20.10.12"  # hotspot; ev wifi'sinde 192.168.1.7 idi
DEFAULT_PORT = 2223
DEFAULT_INTERVAL = 0.004  # ~250 paket/sn hedef


class PacketFlooder:
    def __init__(self, esp_ip=DEFAULT_ESP_IP, port=DEFAULT_PORT, interval=DEFAULT_INTERVAL):
        self.esp_ip = esp_ip
        self.port = port
        self.interval = interval
        self._stop = threading.Event()
        self._thread = None

    def _run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        payload = b"x" * 64
        while not self._stop.is_set():
            try:
                sock.sendto(payload, (self.esp_ip, self.port))
            except Exception:
                pass
            time.sleep(self.interval)
        sock.close()

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()


def detect_esp_ip(serial_conn, timeout=3):
    """Firmware bağlanınca 'Got ip:X.X.X.X' yazıyor - varsa oradan öğren.

    Kart zaten bağlıysa bu satır tekrar yazılmaz, o yüzden bulunamayabilir;
    çağıran taraf None dönerse varsayılan IP'ye düşmeli.
    """
    end = time.time() + timeout
    while time.time() < end:
        line = serial_conn.readline()
        if not line:
            continue
        text = line.decode("utf-8", errors="replace")
        if "Got ip:" in text:
            after = text.split("Got ip:")[1]
            ip = after.split()[0].split("(")[0].strip()
            parts = ip.split(".")
            if len(parts) == 4 and all(p.isdigit() for p in parts):
                return ip
    return None
