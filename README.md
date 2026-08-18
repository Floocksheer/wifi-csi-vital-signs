# WiFi CSI ile Vital Bulgu Takibi

RuView'den (https://github.com/ruvnet/RuView) ilham alan, elimizdeki klasik ESP32 (chip: `ESP32-D0WD-V3`, DevKitV1 kartı) ile CSI tabanlı nefes/kalp atışı tespiti projesi. Detaylı plan: [`docs/RuView_CSI_Proje_Plani.md`](docs/RuView_CSI_Proje_Plani.md).

## Klasör Yapısı

```
firmware/ESP32-CSI-Tool/   # StevenMHernandez'in CSI firmware'i (active_sta kullanacağız)
analysis/                  # Python analiz ortamı (venv/) + ileride yazılacak scriptler
data/                      # Toplanan CSI verisi + Kaggle datasetleri (git'e girmez)
docs/                      # Proje planı ve notlar
```

## Ortam Kurulumu (yeni bir terminalde devam etmek için)

**ESP-IDF v4.3 + doğru Python (tek komut):**
```bash
source activate_idf.sh
export CMAKE_POLICY_VERSION_MINIMUM=3.5   # her idf.py komutundan önce (modern CMake ile eski ESP-IDF uyumu için)
```

**Python analiz ortamı:**
```bash
cd analysis && source venv/bin/activate
```
(venv bu makineye özel, git'e girmez — yeni bir makinede `python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt` ile yeniden kurulur.)

## WiFi Kurulumu (iş yeri + ev, iki ağ arası otomatik geçiş)

Gerçek WiFi bilgileri **asla** git'e giren dosyalara yazılmaz. Her makinede bir kere:
```bash
cd firmware/ESP32-CSI-Tool/active_sta
cp sdkconfig.defaults.local.example sdkconfig.defaults.local
# sdkconfig.defaults.local dosyasını gerçek SSID/şifrelerle doldur (bu dosya .gitignore'da)
rm -f sdkconfig sdkconfig.old
idf.py set-target esp32
idf.py -p /dev/cu.usbserial-0001 -b 115200 flash
```
Kart önce birinci ağı dener, 5 başarısız denemeden sonra otomatik ikinci ağa geçer (`main/main.cc`).

## Neden active_sta?

Tek ESP32'miz var. `active_sta`, WiFi router'ına normal istemci gibi bağlanıp düzenli aralıklarla paket gönderir, gelen cevaplardan CSI okur — ikinci bir ESP32 (AP olarak) gerektirmez. Nefes/kalp atışı analizi için düzenli örnekleme hızı şart, bu yüzden `passive` modu yerine bunu seçtik.

## Kart Bilgisi

- Chip: `ESP32-D0WD-V3` (rev v3.1) — klasik ESP32, S3/C6 değil
- Seri port: `/dev/cu.usbserial-0001`
- MAC: `d4:e9:f4:a4:9d:9c`

## Kurulum Sorun Giderme

ESP-IDF v4.3'ü modern macOS'ta kurarken çıkan sorunlar ve çözümleri için: [`docs/RuView_CSI_Proje_Plani.md`](docs/RuView_CSI_Proje_Plani.md) → Faz 1 bölümü.
