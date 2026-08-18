# WiFi CSI ile Duvar Arkası Vital Bulgu Takibi — Proje Planı

**Tarih:** 2026-08-18 (revize edildi)
**İlham kaynağı:** https://github.com/ruvnet/RuView
**Amaç:** WiFi CSI (Channel State Information) sinyallerini kullanarak duvar arkasından bile nefes alma ve kalp atış hızı gibi vital bulguları tespit eden bir sistem kurmak.

---

## 0. Durum Özeti (bugüne kadar netleşenler)

- Elimizdeki ESP32 kart **fiziksel olarak doğrulandı**: `pio run --target erase` çalıştırıldığında esptool kartı sorguladı ve şu çıktıyı verdi:
  ```
  Chip is ESP32-D0WD-V3 (revision v3.1)
  Features: WiFi, BT, Dual Core, 240MHz, VRef calibration in efuse, Coding Scheme None
  Crystal is 40MHz
  MAC: d4:e9:f4:a4:9d:9c
  ...
  Chip erase completed successfully in 6.2 seconds.
  ```
  **Bu, silikon üzerinden okunan bir kimlik — tahmin değil.** "ESP32-D0WD-V3", klasik/orijinal ESP32'nin (WROOM-32 ailesi) imzasıdır. Eğer kart ESP32-S3 ya da ESP32-C6 olsaydı, esptool doğrudan `Chip is ESP32-S3` / `Chip is ESP32-C6` yazardı. **Sonuç: bu kart kesin olarak S3/C6 değil, klasik ESP32.**
- Flash belleği tamamen silindi (erase başarılı) — kart şu an "temiz sayfa", üzerinde herhangi bir firmware yok.
- Yönetici, "elindeki kartla ben de yaptım, çalışıyor" dedi. Bu iki türlü açıklanabilir:
  1. Yönetici **RuView reposunun kendi derlenmiş firmware/Rust backend'ini değil**, CSI çıkarımı yapan başka/genel bir araç veya örnek kullanmış olabilir (bkz. aşağıda ESP32-CSI-Tool — bu tarz araçlar klasik ESP32'de gerçekten çalışıyor, RuView'den bağımsız).
  2. Yönetici farklı bir kart kullanmış olabilir ve "DevKitV1" ismini genel geçer kullanmış olabilir (bazı S3 geliştirme kartları da popüler dilde "devkit" diye anılıyor, karışıklık olabilir).
- **Yöneticiye sorulacak netleştirici soru:** "RuView reposunun (github.com/ruvnet/RuView) kodunu mu çalıştırdın, yoksa başka bir CSI aracı/örnek mi kullandın? Kullandığın kartta esptool/Arduino IDE 'Chip is ...' ne yazıyordu?"

Bu belirsizlik netleşene kadar **elimizdeki donanımla ilerleyebileceğimiz gerçekçi bir yol** aşağıda tanımlanmıştır — böylece kart tartışması netleşirken zaman kaybetmeyiz.

---

## 1. İki Ayrı Hedef — Karıştırılmamalı

| | **RuView reposunun kendisi** | **CSI tabanlı vital tespit tekniği (genel)** |
|---|---|---|
| Donanım | Sadece ESP32-S3 / ESP32-C6 | Klasik ESP32 (DevKitV1) dahil, CSI destekleyen her ESP32 |
| Yazılım | RuView'in Rust backend'i, pose-estimation, hazır firmware binary | Kendi yazacağımız/derleyeceğimiz basit CSI firmware + Python analiz |
| Neden donanım kısıtı var | Multi-band fusion, 17-keypoint pose gibi ağır işlemler için PSRAM + LX7 çekirdeği gerekiyor | Ham CSI çıkarımı ESP-IDF WiFi sürücüsünde (`esp_wifi_set_csi_config`) klasik ESP32'de de mevcut |
| Bugün elimizdeki kartla mümkün mü | ❌ Hayır | ✅ Evet |

**Karar:** Elimizde DevKitV1 olduğu ve yönetici de bu tip kartla sonuç aldığını iddia ettiği için, **sağ sütundaki yolu** (genel CSI tekniği, RuView'in dokümante ettiği algoritmayı referans alarak) izleyeceğiz. S3/C6 kartı temin edilirse, aynı bilgi birikimiyle RuView'in kendi reposuna geçiş kolay olur (Faz 5'te ele alınıyor).

---

## 2. Kullanılacak Araç: ESP32-CSI-Tool

RuView yerine, klasik ESP32'de kanıtlanmış şekilde çalışan **[ESP32-CSI-Tool](https://github.com/StevenMHernandez/ESP32-CSI-Tool)** (Steven M. Hernandez) kullanılacak. Bu araç akademik CSI/WiFi-sensing araştırmalarında yaygın referans, aktif/pasif CSI toplama modları var, seri port + SD karta veri yazabiliyor.

- **Gereksinim:** ESP-IDF v4.3 (RuView'in istediği v5.4'ten farklı — dikkat, aynı makinede iki IDF versiyonu yönetmek gerekebilir, `idf.py` sürüm çakışmasına dikkat).
- **PlatformIO desteği yok**, ESP-IDF ile deriliyor (RuView ile aynı durum).
- Aktif mod: ESP32 bir Access Point'e bağlanıp paket gönderir, cevap paketlerinden CSI çıkarır.
- Pasif mod: ESP32 belirli bir WiFi kanalını dinleyip geçen paketlerden CSI çıkarır (mesafeye ve ortama göre daha esnek).

---

## 3. Sinyal İşleme Yaklaşımı (RuView'in dokümante ettiği yöntemi referans alarak)

RuView'in yayımladığı bantlar ve yöntem, kendi Python pipeline'ımızda da uygulanabilir:

- **Nefes:** 0.1–0.5 Hz bandpass filtre → 6–30 BPM aralığı
- **Kalp atışı:** 0.8–2.0 Hz bandpass filtre → 40–120 BPM aralığı
- **Yöntem:** Ham CSI fazını "unwrap" et → ilgili banda bandpass filtre uygula → faz varyansı / zero-crossing sayımı ile BPM tahmini çıkar
- Bu, RuView'in kullandığı yaklaşımın basitleştirilmiş, tek-kartlı (multi-band fusion olmadan) bir versiyonu olacak — daha düşük doğruluk beklenir ama kavram kanıtı (proof of concept) için yeterli.

---

## 4. Adım Adım Yol Haritası

### Faz 0 — Netleştirme (bu hafta, paralel yürüsün)
- [ ] Yöneticiye yukarıdaki netleştirici soruyu sor (RuView'in kendisi mi, başka araç mı; hangi kart).
- [x] Elimizdeki DevKitV1'i sıfırla — **tamamlandı**, chip `ESP32-D0WD-V3` olarak doğrulandı, flash temiz.
- [ ] Cevaba göre bu planı güncelle (S3 siparişi gerekiyorsa Faz 5'i öne çek).

### Faz 1 — Ortam Kurulumu ✅ TAMAMLANDI (2026-08-18)
- [x] ESP-IDF v4.3 kuruldu (`~/esp-idf-v4.3/esp-idf`)
- [x] `firmware/ESP32-CSI-Tool` klonlandı, `active_sta` alt-projesi seçildi
- [x] `active_sta` başarıyla derlendi ve karta flash edildi
- [x] Seri porttan boot çıktısı doğrulandı — kart doğru firmware ile çalışıyor
- [ ] Gerçek WiFi SSID/şifre gelince `sdkconfig.defaults` güncellenip yeniden flash edilecek, CSI verisi akışı doğrulanacak

**Ortamı yeniden açmak için (yeni terminal):**
```bash
source ~/Documents/GitHub/wifi-csi-vital-signs/activate_idf.sh
export CMAKE_POLICY_VERSION_MINIMUM=3.5
cd ~/Documents/GitHub/wifi-csi-vital-signs/firmware/ESP32-CSI-Tool/active_sta
idf.py -p /dev/cu.usbserial-0001 -b 115200 flash monitor
```

**Kurulumda çıkan sorunlar ve çözümleri (ileride aynı ortamı kurarsan tekrar uğraşmamak için):**

1. **`SSL: CERTIFICATE_VERIFY_FAILED`** — python.org Python'unda sertifika paketi eksikti. Çözüm: `/Applications/Python 3.12/Install Certificates.command` çalıştırıldı.
2. **`gevent` derleme hatası (Cython)** — ESP-IDF v4.3'ün eski Python paketleri (`gevent` dahil) sistem Python 3.12 ile derlenemiyor. Çözüm: `brew install python@3.10` ile ayrı bir Python 3.10 kuruldu, `install.sh` bu sürümle çalıştırıldı (`PATH="/opt/homebrew/opt/python@3.10/libexec/bin:$PATH"`).
3. **`ModuleNotFoundError: No module named 'pkg_resources'`** — ESP-IDF'nin kendi sanal ortamına kurulan en yeni `setuptools` (84.0.0) artık `pkg_resources`'ı içermiyor. Çözüm: o venv içinde `pip install "setuptools<81"`.
4. **CMake `cmake_minimum_required` hatası (mbedtls)** — sistemdeki güncel CMake (4.2.1), ESP-IDF v4.3'ün paketlediği eski `mbedtls`'in istediği çok düşük minimum sürümü artık desteklemiyor. Çözüm: `export CMAKE_POLICY_VERSION_MINIMUM=3.5` (her `idf.py` komutundan önce).
5. **Flash sırasında `Failed to write compressed data... (result was C100)`** — USB-seri çipin varsayılan 460800 baud'da bağlantı stabilite sorunu. Çözüm: `idf.py -p <port> -b 115200 flash`.
6. **Seri monitor çıktısı "çöp karakter"** — firmware'in konsol baud rate'i (`921600`, sdkconfig'de ayarladık) ile okuyucunun baud rate'i uyuşmadığında oluyor. Doğru baud'da (921600) okununca normal, renkli log çıktısı görünüyor.

`activate_idf.sh` scripti bu ortamı (doğru PATH + export.sh) tek satırda kurmak için proje kökünde duruyor.

### Faz 1.5 — GitHub'a Taşıma + İki Ağ (İş/Ev) Desteği ✅ TAMAMLANDI (2026-08-18)

- [x] `active_sta/main/main.cc` ve `Kconfig.projbuild` güncellendi: artık **iki WiFi ağı** tanımlanabiliyor (`ESP_WIFI_SSID`/`_2`). Kart önce birinci ağı dener, `WIFI_FAILS_BEFORE_SWITCH` (5) başarısız denemeden sonra otomatik ikinci ağa geçer — iş yeri/ev arasında reflash gerekmeden çalışır.
- [x] Güvenlik: gerçek SSID/şifreler **`sdkconfig.defaults.local`** dosyasında tutulacak (git'e girmez, `.gitignore`'da). Committed `sdkconfig.defaults` sadece placeholder içerir. Şablon: `sdkconfig.defaults.local.example` (bunu kopyalayıp doldurmak yeterli, her makinede ayrı doldurulur).
- [x] `CMakeLists.txt`, `sdkconfig.defaults.local` varsa otomatik olarak `sdkconfig.defaults`'un üzerine ek olarak okuyacak şekilde güncellendi.
- [x] Değişikliklerle yeniden derleme test edildi, başarılı.
- [ ] Proje GitHub'a taşınıyor: kullanıcı github.com'da boş bir repo açtı/açacak, GitHub Desktop ile clone'layacak, sonrasında mevcut yerel dosyalar oraya taşınacak.

**Yeni WiFi kurulumu (ilk bilgiler geldiğinde her makinede yapılacak):**
```bash
cd firmware/ESP32-CSI-Tool/active_sta
cp sdkconfig.defaults.local.example sdkconfig.defaults.local
# sdkconfig.defaults.local dosyasını gerçek SSID/şifrelerle doldur
rm -f sdkconfig sdkconfig.old
idf.py set-target esp32 && idf.py -p /dev/cu.usbserial-0001 -b 115200 flash
```

### Faz 2 — Veri Toplama (Kaggle + kendi verimiz) — BAŞLADI (2026-08-18)

- [x] Gerçek WiFi bağlantısı kuruldu (telefon hotspot, yönetici onayıyla geçici çözüm — iş yeri ağı gelince `sdkconfig.defaults.local`'a ikinci ağ olarak eklenecek)
- [x] **Önemli bugfix:** `_components/sockets_component.h` CSI tetiklemek için sabit `192.168.4.1` adresine paket gönderiyordu (orijinal araç iki-ESP32 senaryosu için tasarlanmış — biri AP, biri istemci). Bizim tek-kart + normal router/hotspot senaryomuzda bu IP hiç var olmuyordu, paketler kayboluyor, CSI hiç tetiklenmiyordu. Çözüm: `main.cc`, IP alındığında bağlı olduğu ağın **gateway IP'sini** (`event->ip_info.gw`) `target_ip` global değişkenine yazıyor, `sockets_component.h` artık sabit IP yerine bunu kullanıyor. Bu sayede hangi ağa bağlanırsak bağlanalım (ev/iş/hotspot fark etmez) otomatik doğru hedefe paket gidiyor.
- [x] Doğrulandı: 15 saniyede 121 adet gerçek `CSI_DATA` satırı (subcarrier genlik/faz dizisi) seri porttan okundu.
- [ ] **Bu değişiklikler (main.cc, sockets_component.h) GitHub Desktop'tan commit + push edilmeli** — kod değişikliği, `sdkconfig.defaults.local` gibi gitignore'da değil.
- [ ] CSI verisini bir CSV dosyasına kaydetme (`idf.py monitor | grep CSI_DATA > data/...csv`)
- [ ] Kaggle datasetleriyle Python analiz pipeline'ını test et
- [ ] Kendi CSI verimizi topla (gönüllü onamı + referans nabız ölçer ile)
- [ ] Aşağıdaki Kaggle datasetleriyle Python analiz pipeline'ını (bandpass + faz analizi) önceden test et, format/ölçek alışkanlığı kazan.
- [ ] Kendi CSI verimizi ESP32-CSI-Tool ile topla: sabit mesafe, oda içi, gönüllü bir kişiden (kendi nefes/kalp atışını) — **gönüllü onamı önemli**, ölçüm sırasında referans olarak akıllı saat/nabız ölçer kullan.

### Faz 3 — Analiz / Model
- [ ] Bandpass filtre + faz varyansı + zero-crossing BPM tahmini pipeline'ını kur (Python: `numpy`, `scipy.signal`).
- [ ] Referans ölçümle (akıllı saat/pulse oksimetre) doğruluğu karşılaştır.
- [ ] "Öğretmen" (teacher model) konusu netleşirse — eğer bilgi damıtma (knowledge distillation) kastediliyorsa, büyük bir modelden ESP32 üzerinde çalışabilecek küçük modele aktarım değerlendirilebilir.

### Faz 4 — Rapor / Sunum
- [ ] Sonuçları [[project_bitirme_tezi]] belgesindeki mevcut tez yapısına nasıl entegre edileceğini planla (eğer bu iş tez kapsamındaysa).
- [ ] Yöntem farkını (RuView'in kendisi değil, RuView'den ilham alan kendi implementasyonumuz olduğunu) rapor/sunumda açıkça belirt — akademik dürüstlük açısından önemli.

### Faz 5 — (Opsiyonel/Gelecek) RuView'e Geçiş
- [ ] S3/C6 kartı temin edilirse: `firmware/esp32-csi-node/` içindeki gerçek RuView firmware'ini ESP-IDF v5.4 ile derle, `esptool` ile yükle, `provision.py` ile WiFi'a bağla.
- [ ] Faz 1-3'te öğrenilen sinyal işleme bilgisiyle RuView'in sunduğu Rust backend ve pose-estimation katmanını karşılaştır.

---

## 5. Kaggle CSI Dataset Adayları

- [WIFI CSI dataset - UT_HAR](https://www.kaggle.com/datasets/hylanj/wifi-csi-dataset-ut-har) — insan aktivite tanıma
- [WIFI CSI dataset - ARIL](https://www.kaggle.com/datasets/hylanj/wifi-csi-dataset-aril) — aktivite + konum tanıma
- [WIFI CSI dataset - NTU_Fi_HumanID](https://www.kaggle.com/datasets/hylanj/wifi-csi-dataset-ntu-fi-humanid) — kişi tanıma (yürüyüş)
- [CSI-Bench](https://www.kaggle.com/datasets/guozhenjennzhu/csi-bench) — büyük ölçekli, çoklu görev
- [CSI dataset (geninhu)](https://www.kaggle.com/datasets/geninhu/csi-dataset)
- [WiFi CSI Human Activity Recognition](https://www.kaggle.com/datasets/alanwake12/wifi-csi-human-activity-recognition)

Akademik (Kaggle dışı) vital-bulgu odaklı kaynaklar (talep üzerine erişim gerekebilir):
- **eHealth CSI** — Wi-Fi CSI insan aktivitesi + sağlık verisi
- **VitalCSI** — solunum hızı (RR) odaklı, Raspberry Pi + ticari AP, 15 katılımcı

---

## 6. Açık Sorular / Yöneticiye Sorulacaklar

1. **[Öncelikli]** RuView reposunun (github.com/ruvnet/RuView) kodunu mu çalıştırdın, yoksa başka bir CSI aracı mı kullandın? Kullandığın kartta chip kimliği ne yazıyordu (esptool/Arduino IDE çıktısı)?
2. "Öğretmen" derken akademik danışman mı, yoksa ML'de "teacher model" (bilgi damıtma) mı kastedildi?
3. Proje bir bitirme tezi kapsamında mı, yoksa şirket içi bağımsız Ar-Ge mi? (İnsan vital verisi toplamak için etik/onam süreci gerekebilir.)
4. Hedef ortam ne — tek oda içi demo mu, gerçek duvar-arkası senaryo mu?
5. S3/C6 kartı temin edilecek mi, yoksa proje tamamen elimizdeki DevKitV1 ile mi sürdürülecek?

---

## Ekler: PlatformIO/esptool Hatırlatmalar

- `pio` komutu terminalde bulunamıyorsa: `echo 'export PATH="$PATH:$HOME/.platformio/penv/bin"' >> ~/.zshrc && source ~/.zshrc`
- Flash sıfırlama (tekrar gerekirse): `pio run --target erase` (proje varsa) veya `python -m esptool --chip esp32 --port /dev/cu.usbserial-0001 erase_flash`
- Kartın seri portu doğrulandı: `/dev/cu.usbserial-0001`, MAC: `d4:e9:f4:a4:9d:9c`, chip: `ESP32-D0WD-V3 rev v3.1`

---

*Bu belge, kullanıcıyla yapılan konuşmaya ve https://github.com/ruvnet/RuView ile https://github.com/StevenMHernandez/ESP32-CSI-Tool projelerinin (2026-08-18 itibarıyla) genel dokümantasyonuna dayanarak hazırlanmıştır.*
