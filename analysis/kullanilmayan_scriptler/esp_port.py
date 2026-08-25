"""Board A'nın (veri toplayan STA kartı) seri portunu otomatik bulur.

NEDEN: macOS port isimlerini takılma sırasına göre veriyor. Board B (AP) laptoptan
çıkarılınca Board A'nın adı /dev/cu.usbserial-3 -> -0001 diye değişti ve tüm
scriptlerdeki sabit port yanlış kaldı. Artık elle güncellemeye gerek yok.
"""
import glob

# Board A - esptool ile silikondan doğrulandı (2026-08-24)
BOARD_A_MAC = "d4:e9:f4:a4:9d:9c"


def detect_port(explicit=None):
    """explicit verilmişse onu döndürür; yoksa tek USB seri portu bulur.

    Birden fazla port varsa hangisinin Board A olduğunu buradan bilemeyiz
    (MAC okumak kartı resetler, bu da kesintisiz oturumu bozar) - o durumda
    kullanıcıdan --port bekliyoruz.
    """
    if explicit:
        return explicit
    ports = sorted(glob.glob("/dev/cu.usbserial*"))
    if not ports:
        raise SystemExit("ESP32 bulunamadı. Kart takılı mı?")
    if len(ports) > 1:
        raise SystemExit(
            f"Birden fazla port var: {ports}\n"
            f"--port ile hangisini kullanacağını belirt "
            f"(Board A'nın MAC'i {BOARD_A_MAC})."
        )
    return ports[0]
