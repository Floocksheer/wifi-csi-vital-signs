#!/usr/bin/env python3
"""ESP32'den gelen CSI verisini seri porttan okuyup data/ altına CSV olarak kaydeder.

Kullanım:
    python capture_csi.py --duration 60
    python capture_csi.py --duration 60 --output ../data/nefes_test_01.csv
"""
import argparse
import datetime
import pathlib
import time

import serial

from esp_port import detect_port
from packet_flooder import PacketFlooder, DEFAULT_ESP_IP

HEADER = (
    "type,role,mac,rssi,rate,sig_mode,mcs,bandwidth,smoothing,not_sounding,"
    "aggregation,stbc,fec_coding,sgi,noise_floor,ampdu_cnt,channel,"
    "secondary_channel,local_timestamp,ant,sig_len,rx_state,real_time_set,"
    "real_timestamp,len,CSI_DATA\n"
)


def main():
    parser = argparse.ArgumentParser(description="ESP32 CSI verisini kaydet")
    parser.add_argument("--port", default=None,
                        help="Veri toplayan kartın portu (verilmezse otomatik bulunur)")
    parser.add_argument("--baud", type=int, default=921600)
    parser.add_argument("--duration", type=float, default=30, help="Kaç saniye kaydedilecek")
    parser.add_argument("--output", default=None, help="Çıktı CSV yolu (verilmezse otomatik isimlendirilir)")
    parser.add_argument("--reset", action="store_true", help="Başlamadan önce kartı resetle (RTS/DTR ile)")
    parser.add_argument("--esp-ip", default=DEFAULT_ESP_IP,
                        help="Sadece --flood ile birlikte kullanılır: ESP32'nin IP'si")
    parser.add_argument("--flood", action="store_true",
                        help="Laptop'tan ek UDP paketi gönder. 2. ESP32 (özel AP) mimarisinde "
                             "GEREKMİYOR ve hızı düşürüyor (ölçüldü: 82-101 Hz -> 67 Hz) - firmware'in "
                             "kendi STA->AP trafiği zaten yeterli. Sadece tek kartla ev wifi'si/hotspot'a "
                             "bağlıyken (~3-10 Hz beacon-only) hızı artırmak için kullan.")
    args = parser.parse_args()
    args.port = detect_port(args.port)

    if args.output is None:
        data_dir = pathlib.Path(__file__).resolve().parent.parent / "data"
        data_dir.mkdir(exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = data_dir / f"csi_{ts}.csv"
    else:
        output_path = pathlib.Path(args.output)

    ser = serial.Serial(args.port, args.baud, timeout=1)

    if args.reset:
        ser.setDTR(False)
        ser.setRTS(True)
        time.sleep(0.1)
        ser.setRTS(False)
        time.sleep(0.1)

    csi_count = 0
    flooder = None
    if args.flood:
        flooder = PacketFlooder(esp_ip=args.esp_ip).start()
        time.sleep(0.5)  # akışın oturması için

    try:
        end_time = time.time() + args.duration
        with open(output_path, "w") as f:
            f.write(HEADER)
            mode = f"flood -> {args.esp_ip}" if args.flood else "normal (flood yok)"
            print(f"Kayıt başladı -> {output_path} ({args.duration:.0f} saniye, {mode})")
            while time.time() < end_time:
                line = ser.readline()
                if not line:
                    continue
                text = line.decode("utf-8", errors="replace").rstrip()
                if text.startswith("CSI_DATA"):
                    f.write(text + "\n")
                    csi_count += 1
                    if csi_count % 200 == 0:
                        print(f"  {csi_count} paket kaydedildi...")
    finally:
        if flooder:
            flooder.stop()
        ser.close()

    rate = csi_count / args.duration
    print(f"Bitti. Toplam {csi_count} CSI paketi ({rate:.1f} Hz) -> {output_path}")
    if rate < 30:
        print("  UYARI: Hız düşük (2. ESP32 AP mimarisinde 80-100+ Hz beklenir).")
        print("  Kontrol et: ESP32_CSI_AP'ye bağlı mı, RSSI yeterli mi, --flood deneyip fark var mı?")


if __name__ == "__main__":
    main()
