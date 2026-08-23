# Proje Durumu, Kararlar ve Denenenler
### Yeni bir sohbet/oturum bu dosyayı okuyarak projeyi devralabilir

**Son güncelleme:** 19 Ağustos 2026
**Depo:** `~/Documents/GitHub/wifi-csi-vital-signs` (GitHub: `Floocksheer/wifi-csi-vital-signs`, private)
**Diğer dokümanlar:** `PROJE_SUNUM.md` (sunum için), `RuView_CSI_Proje_Plani.md` (detaylı faz planı)

---

## 0. HIZLI BAŞLANGIÇ (yeni oturumda ilk okunacak)

### Ortamı açma
```bash
# ESP-IDF (firmware derlemek/yüklemek için) - her yeni terminalde bir kez
source ~/Documents/GitHub/wifi-csi-vital-signs/activate_idf.sh
export CMAKE_POLICY_VERSION_MINIMUM=3.5     # modern CMake + eski ESP-IDF uyumu için ŞART

# Python analiz ortamı
cd ~/Documents/GitHub/wifi-csi-vital-signs/analysis && source venv/bin/activate
```

### Sık kullanılan komutlar
```bash
# Firmware yükleme (WiFi bilgisi değişince gerekir)
cd firmware/ESP32-CSI-Tool/active_sta
rm -f sdkconfig sdkconfig.old && idf.py build
idf.py -p /dev/cu.usbserial-0001 -b 115200 flash      # -b 115200 ŞART, 460800 hata veriyor

# Veri toplama (flood otomatik açık, ~145 Hz)
cd analysis && python3 capture_csi.py --duration 8 --output ../data/xxx.csv

# Canlı gösterge
python3 live_server.py        # http://localhost:5050
```

### Donanım gerçekleri
| | |
|---|---|
| Kart | **ESP32-D0WD-V3** (klasik ESP32, DevKitV1). S3/C6 DEĞİL — esptool ile silikondan doğrulandı |
| Anten | **1 adet** (poz tahmini için 3 gerekiyor → yapılamıyor) |
| Bant | **Sadece 2.4 GHz** (5 GHz ağlara bağlanamaz) |
| Seri port | `/dev/cu.usbserial-0001`, baud **921600** |
| MAC | `d4:e9:f4:a4:9d:9c` |

---

## 1. Proje Amacı ve Kapsam

WiFi CSI (Channel State Information) sinyalleriyle **kamerasız** olarak:
- Nefes hızı
- Kalp atış hızı
- Hareket / aktivite (oturma, ayakta, ani hareket)

tespit etmek. Yönetici tarafından verilen bir iş; ilham kaynağı [RuView](https://github.com/ruvnet/RuView).

**Kullanıcı ayrıca istedi:** Uzuv/poz takibi + canlı animasyonlu görselleştirme (RuView'deki gibi).

---

## 2. TEMEL KARARLAR ve GEREKÇELERİ

### Karar 1: RuView'in kendi kodu YERİNE ESP32-CSI-Tool
**Neden:** RuView firmware'i sadece ESP32-S3/C6 destekliyor (PSRAM + LX7 çekirdeği gerekiyor). Elimizdeki klasik ESP32'de çalışmaz.
**Ne yapıldı:** [ESP32-CSI-Tool](https://github.com/StevenMHernandez/ESP32-CSI-Tool) (`active_sta` modu) kullanıldı, RuView'in *dokümante ettiği algoritmalar* (frekans bantları) referans alındı.
**Sonuç:** "RuView'i çalıştırdık" DEĞİL, "RuView'den ilham alan kendi implementasyonumuz". Raporda böyle belirtilmeli.

### Karar 2: ESP-IDF v4.3 (v5.x değil)
**Neden:** ESP32-CSI-Tool bu sürümü gerektiriyor. Modern macOS'ta kurulumu 6 ayrı sorun çıkardı (çözümler Bölüm 6'da).

### Karar 3: Duruş sınıflandırma modeli SADECE otur/ayakta ile eğitiliyor
**Neden:** İki aşamalı mimari — "ani hareket" tespiti eşikle (fizik) yapılıyor, modele bırakılmıyor. Model sadece kişi hareketsizken çalıştırılıyor (eğitim verisi de öyleydi).

### Karar 4: Uzuv/poz (iskelet) takibi ERTELENDİ
**Neden:** RuView'in hazır modeli (HuggingFace `ruvnet/wifi-densepose-mmfi-pose`) **3 anten × 114 alt-taşıyıcı × 100 Hz** gerektiriyor. Bizde 1 anten var — yazılımla çözülemez.
**Alternatif:** Kaba aktivite sınıflandırma (oturma/ayakta/hareket) yapılıyor.

### Karar 5: Arayüz "en son" kararından vazgeçildi
**Neden:** Zaman baskısı + gösterilebilir sonuç ihtiyacı. Canlı gösterge erken yapıldı (`live_server.py`), sade tutuldu (3D animasyon yok).

---

## 3. DENENENLER ve SONUÇLARI (başarısızlıklar dahil)

### 3.1 Kalp atışı — sinyal işleme yöntemleri
Sentetik veri seti (`saur3x/wifi-sensing`, gerçek `heart_rate_bpm` etiketli) ile:

| Yöntem | Ortalama hata | Karar |
|---|---|---|
| Genlik + FFT | 12.56 BPM | ❌ |
| Genlik + zero-crossing | 8.62 BPM | — |
| **Faz + zero-crossing** | **7.32 BPM** | ✅ sentetikte en iyi |
| PCA ilk bileşen | 11.52 BPM | ❌ kullanılmadı |

### 3.2 Nefes — kendi gerçek verimizle (3 tempo)

| Test | Gerçek | zero-crossing | FFT |
|---|---|---|---|
| Yavaş/derin | 15 BPM | **15.99 (hata 0.99)** ✅ | 16.75 |
| Normal | 24 BPM | 17.96 (hata 6.04) | 20.95 (hata 3.05) |
| Hızlı/sığ | 43.5 BPM | ❌ bant dışı | ❌ bant dışı |

**Not:** 43.5 BPM = 0.725 Hz, nefes bandımızın (0.1-0.5 Hz) dışında → tasarım sınırı, hata değil.
**Metodolojik zayıflık:** 3 testte hem hız hem derinlik aynı anda değişti (kontrolsüz değişken) → sonuçlar "kesin doğrulama" değil, sanity check.

### 3.3 ❌ Faz yöntemi gerçek veride BAŞARISIZ
Sentetikte en iyi olan faz yöntemi, kendi verimizde en kötülerden çıktı:

| Yöntem | Kendi verimiz |
|---|---|
| **Genlik + zero-crossing** | **11.36 BPM** ✅ en iyi |
| Faz + zero-crossing | 13.60 BPM ❌ |
| Otokorelasyon (genlik/faz) | 19+ BPM ❌ |

**Sebep:** Gerçek donanım fazı, cihaz kaynaklı zamanlama/frekans kaymaları içeriyor (sentetikte yoktu). Literatürde "phase sanitization" ön işlemi gerekiyor — yapılmadı.
**Karar:** Gerçek veride genlik yöntemi kullanılıyor.

### 3.4 Aktivite sınıflandırma — UT-HAR (hazır veri seti)
Yöntem: alt-taşıyıcı başına mean/std/min/max + Random Forest
**Sonuç: VAL %97.8, TEST %95.2** (7 sınıf) ✅
**Ama:** Intel 5300 (3 anten, 90 özellik) ile toplanmış → model bizim donanımımıza aktarılamaz, sadece **yöntem** doğrulandı.

### 3.5 Aktivite — kendi verimiz, protokol iyileştirmesi
| Deneme | Protokol | Doğruluk (LOO) |
|---|---|---|
| 1. | 4 tekrar, "otur" kayıtlarında geçiş hareketi + duruş karışık | %50 |
| 2. | 6 tekrar, **saf statik** (önce pozisyona geç, sonra kaydı başlat) | **%77.8** |

Sınıf bazında (2. deneme): oturma 5/6, ayakta 3/6, **ani hareket 6/6** ✅

### 3.6 Pencere boyutu optimizasyonu
Kayan pencere ile veri artırma (aynı kayıttan gelen pencereler test/eğitimde ayrıldı — `LeaveOneGroupOut`):

| Pencere | Örnek | Doğruluk |
|---|---|---|
| 8 sn | 18 | %77.8 |
| 4 sn | 54 | %75.9 |
| 3 sn | 72 | %77.8 |
| **2 sn** | **126** | **%83.3** ✅ |

→ Canlı sistemde 2 saniyelik pencere kullanılıyor (hem daha doğru hem daha az gecikme).

### 3.7 ❌❌ EN KRİTİK BAŞARISIZLIK: Oturumlar arası genelleme
Canlı testte model sürekli "AYAKTA" dedi (%94 güvenle). Teşhis:

| Ölçüm | Değer |
|---|---|
| Eğitim: oturma genlik seviyesi | 19.14 |
| Eğitim: ayakta genlik seviyesi | 18.84 |
| **Sınıf farkı** | **0.30** |
| 2 saat sonra: oturma | 20.55 |
| 2 saat sonra: ayakta | 21.02 |
| **Ortam kayması** | **~1.70 (5 kat büyük!)** |

İlişki tersine bile dönmüş (eğitimde otur>ayakta, tazede otur<ayakta).

**Denenen çözümler — HEPSİ BAŞARISIZ:**

| Normalizasyon | Oturum-içi | **Taze oturum** |
|---|---|---|
| Ham | %75.0 | **%50 (rastgele)** |
| Ortalamaya bölme | %77.4 | **%50** |
| Z-skor şekil | %66.7 | **%50** |

**Ders:** Aynı oturumdan veriyle yapılan LOO doğrulaması **yanıltıcıydı**. Gerçek koşulu temsil etmiyor.

### 3.8 🚀 EN BÜYÜK KAZANIM: Örnekleme hızı 9.5 → 145 Hz

**Kök neden:** CSI, ESP32'nin **GÖNDERDİĞİ** değil **ALDIĞI** çerçevelerden üretilir. Normal ağda kart sadece AP beacon'larını alır (~100ms = ~10 Hz). `CONFIG_PACKET_RATE=100` ayarı bu yüzden hiçbir işe yaramıyordu.

**Çözüm:** Laptop'tan ESP32'ye sürekli UDP paketi göndermek ("flood", `packet_flooder.py`).

| Kurulum | RSSI | Hz |
|---|---|---|
| Uzak modem, flood yok | −77 dBm | 2.4-3.9 |
| Hotspot, flood yok | −31…−61 dBm | 9.5-10.1 |
| Uzak modem, flood VAR | −77 dBm | 3.9 (paketler ulaşmıyor!) |
| **Hotspot, flood VAR** | **−59 dBm** | **115.6** ✅ |
| **Yakın modem, flood VAR** | **−61 dBm** | **145** ✅ |

**Flood'un çalışması için ÜÇ koşul (hepsi gerekli):**
1. Flood açık olmalı (`packet_flooder.py`)
2. **Laptop ve ESP32 AYNI ağda olmalı** — farklı ağlardaysa paketler ulaşmaz (yaşandı: laptop hotspot'ta, ESP32 ev wifi'sinde → flood etkisiz)
3. Sinyal yeterli olmalı (RSSI > −70 dBm) — −77 dBm'de paketler kayboluyor

**Ağın türü (hotspot / ev wifi) fark etmiyor** — ikisi de flood ile 115-145 Hz veriyor. Yani iş yerinde hotspot'la çalışmak sorun değil.

**Yan etki:** Yüksek hızda CSI formatı değişti — paket başına **256 → 128 değer** (128 → 64 alt-taşıyıcı), çünkü beacon ve veri çerçeveleri farklı WiFi modlarında iletiliyor.
**Sonuç:** Eski verilerle eğitilmiş modeller yeni veriyle **uyumsuz**. Eski veriler `data/archive_lowrate/` klasörüne taşındı.

---

## 4. HANGİ ÖZELLİK ORTAM DEĞİŞİNCE BOZULUR? (kritik tablo)

| Özellik | Yöntem | Ortam değişince | Neden |
|---|---|---|---|
| Nefes | Bandpass filtre (frekans) | ✅ Bozulmaz | Frekans ölçüyor; 0.25 Hz her odada 0.25 Hz |
| Kalp atışı | Bandpass filtre (frekans) | ✅ Bozulmaz | Aynı |
| Hareket var/yok | Enerji (ardışık fark) | ✅ Bozulmaz | Kendi geçmişiyle kıyaslıyor |
| **Oturma/ayakta** | **ML (mutlak desen)** | ❌ **Bozulur** | Donmuş sinyalin şeklini ezberliyor, o şekil odaya özgü |

**Genel kural:** *Değişimi* ölçen yöntemler ortamdan bağımsız, *mutlak deseni* ezberleyen yöntemler ortama bağımlı.

---

## 5. SIRADAKİ PLAN (2026-08-19 itibarıyla)

### Hemen yapılacak: Fizibilite testi
145 Hz'de 2 soru ölçülecek:
1. Yüksek hız, eski (mutlak desen) yöntemin oturum-arası başarısını düzeltiyor mu?
2. **Yeni fikir:** Oturma/ayakta ayrımı **dinamik** özelliklerle yapılabilir mi?

### 💡 Yeni fikir: Postural sway (dinamik ayrım) — TEST EDİLECEK
**Hipotez:** Ayakta duran insan asla tam hareketsiz değildir — dengede kalmak için sürekli minik düzeltmeler yapar (postural sway). Oturan insan çok daha kararlıdır. Ayrıca nefes sırasında göğüs hareketi iki pozisyonda farklı görünür.

**Neden umut verici:** Bu bir *dinamik* fark (zaman içindeki değişim) → Bölüm 4'teki kurala göre **ortamdan bağımsız** olmalı → kalibrasyon derdini ortadan kaldırabilir.

**Neden daha önce denenemedi:** 9.5 Hz'de bu ince salınımları görecek çözünürlük yoktu. 145 Hz'de var.

### Kalibrasyon stratejileri (dinamik yöntem tutmazsa)
- **A) Hızlı kalibrasyon rutini:** 145 Hz'de 20 sn = ~2900 paket = yüzlerce pencere. "20 sn otur → 20 sn ayakta dur → otomatik eğit" = **toplam ~1 dakika**. Kalibrasyonu sinir bozucu olmaktan çıkarır.
- **B) Konum kütüphanesi:** Her ortam için bir kez kalibre et (`model_ofis.joblib`, `model_ev.joblib`), o ortama dönünce yükle.

### Toplanacak veri (yüksek hızda, sıfırdan)
Kullanıcı onayladı: oturma, ayakta, **yürüme**, ayakta→oturma geçişi, oturma→ayakta geçişi — her birinden bolca.

---

## 6. TEKNİK TUZAKLAR (tekrar yaşamamak için)

| Sorun | Sebep | Çözüm |
|---|---|---|
| ESP-IDF kurulumu: `SSL: CERTIFICATE_VERIFY_FAILED` | python.org Python'unda sertifika yok | `/Applications/Python 3.12/Install Certificates.command` |
| `gevent` derlenmiyor | Eski bağımlılıklar Python 3.12 ile uyumsuz | `brew install python@3.10`, PATH'e ekleyip `install.sh` çalıştır |
| `No module named 'pkg_resources'` | setuptools 84 bu modülü kaldırdı | IDF venv'inde `pip install "setuptools<81"` |
| CMake `cmake_minimum_required` hatası | CMake 4.x eski mbedtls'i reddediyor | `export CMAKE_POLICY_VERSION_MINIMUM=3.5` |
| Flash hatası `C100` | 460800 baud kararsız | `idf.py -p ... -b 115200 flash` |
| Seri çıktı bozuk karakter | Baud uyuşmazlığı | Okurken 921600 kullan |
| **Hiç CSI gelmiyor** | Araç sabit `192.168.4.1`'e paket atıyordu (iki-ESP32 senaryosu için) | `main.cc` düzeltildi: bağlandığı ağın **gateway**'ini otomatik kullanıyor |
| ESP32 ağa bağlanamıyor | 5 GHz ağ | Klasik ESP32 sadece 2.4 GHz — 2.4 GHz SSID kullan / iPhone'da "Maksimum Uyumluluk" aç |
| CSV parse edilemiyor | Seri satır sonu kaybı → paketler birleşiyor; boşluk kaybı → `32-12` | `pandas` yerine regex tabanlı ayrıştırıcı (`activity_features.py`) |
| Veri tutarsız | **Vantilatör** açıkken bazı kayıtlar alındı (dönen pervane = hareket kaynağı) | Ortamdaki hareketli her şey tutarlı olmalı; etkilenen kayıtlar silinip yeniden alındı |
| Flood işe yaramıyor | Sinyal zayıf (−77 dBm), paketler ulaşmıyor | RSSI > −70 dBm olmalı; modeme yaklaş |
| Flood işe yaramıyor (2) | **Laptop ve ESP32 farklı ağlarda** | İkisi de aynı ağda olmalı; `Got ip` satırından ESP32'nin IP'sini doğrula |
| Seri port meşgul | `live_server.py` arka planda çalışıyor | `pkill -f "live_server.py"` (dikkat: `python3 live_server.py` kalıbı eşleşmiyor) |

---

## 7. DOSYA HARİTASI

```
analysis/
  activity_features.py           # Ortak: CSV parse (regex), özellik çıkarımı, hareket enerjisi, kayan pencere
  bpm_pipeline.py                # Bandpass + zero-crossing/FFT BPM tahmini, faz birleştirme
  packet_flooder.py              # ⭐ UDP flood (9.5 → 145 Hz), ESP IP tespiti
  capture_csi.py                 # Veri toplama (flood otomatik açık)
  live_server.py                 # ⭐ Canlı web gösterge (Flask, :5050)
  save_activity_model.py         # Duruş modelini eğitip kaydeder
  train_own_activity_classifier.py   # Kendi verimizle LOO değerlendirme
  train_activity_classifier.py   # UT-HAR ile eğitim/değerlendirme
  evaluate_heart_rate_synthetic.py   # Sentetik veriyle kalp atışı değerlendirme
  evaluate_breathing_own_data.py     # Kendi verimizle nefes değerlendirme
  evaluate_breathing_own_data_v2.py  # Faz/otokorelasyon denemesi (başarısız - kayıt amaçlı)
  plot_breathing_signals.py      # Sinyal görselleştirme
  models/activity_classifier.joblib  # Eğitilmiş duruş modeli
  venv/                          # Python ortamı (git'e girmez)

data/                            # ⚠️ TAMAMI .gitignore'da (büyük dosyalar)
  synthetic_vital_signs/         # Kaggle saur3x/wifi-sensing (2.2 GB)
  ut_har_activity/               # Kaggle hylanj/wifi-csi-dataset-ut-har (854 MB)
  own_breathing_*.csv            # Kendi nefes kayıtlarımız (düşük hız, hâlâ geçerli)
  archive_lowrate/               # Eski düşük-hızlı aktivite verisi (format uyumsuz, kullanılmıyor)
  README.md                      # Veri setlerinin kaynağı ve format notları

firmware/ESP32-CSI-Tool/
  active_sta/main/main.cc        # ⭐ ÖZELLEŞTİRİLDİ: çift ağ + dinamik gateway IP
  active_sta/main/Kconfig.projbuild  # ÖZELLEŞTİRİLDİ: ikinci ağ tanımları
  active_sta/sdkconfig.defaults   # Ayarlar (placeholder WiFi - git'e girer)
  active_sta/sdkconfig.defaults.local  # ⚠️ GERÇEK WiFi şifreleri - .gitignore'da
  _components/sockets_component.h # ÖZELLEŞTİRİLDİ: sabit IP yerine target_ip

docs/
  PROJE_SUNUM.md                 # Sunum dokümanı
  PROJE_DURUM_VE_KARARLAR.md     # BU DOSYA
  RuView_CSI_Proje_Plani.md      # Detaylı faz planı ve kronoloji
activate_idf.sh                  # ESP-IDF ortamını tek satırda açar
```

---

## 8. AÇIK KONULAR

1. **Yöneticiye sorulacak:** "Öğretmen" derken ML'deki *teacher model* (bilgi damıtma) mı kastedildi? RuView'in kendi GitHub tartışmasında (issue #45) "kamera tabanlı öğretmen modeli" ifadesi geçiyor — bu ihtimali güçlendiriyor.
2. **IEEE DataPort veri seti:** [Multi-Human HAR](https://ieee-dataport.org/documents/channel-state-information-dataset-multi-human-activity-recognition-indoor-environments) — ESP32-Nodemcu + ESP32-CSI-Toolkit ile toplanmış (tam bizim donanımımız), 80+ katılımcı. **Abonelik gerekiyor** — üniversite hesabıyla denenebilir.
3. **Nefes için etiketli veri seti bulunamadı.** Ücretsiz erişilebilir tek aday [WiFi-CSI-MiningTool](https://github.com/AlbanyArmenta0711/WiFi-CSI-MiningTool) (GitHub, Intel 5300) — indirilmedi.
4. **Uzuv/poz takibi:** Donanım yetersiz (1 anten). Yöneticiyle konuşulması gerekiyor.

---

## 9. KULLANICI TERCİHLERİ / ÇALIŞMA ŞEKLİ

- Kullanıcı Türkçe konuşuyor, teknik terimleri açıklamak gerekiyor
- **İndirme yapmadan önce sormak gerekiyor** — mobil veri paketi sınırlı, şirket internetine geçmesi gerekebilir
- Veri toplarken kullanıcıyı yönlendirmek gerekiyor: "ŞİMDİ OTUR" / "BAŞLA" / "DUR" gibi net komutlar
- GitHub'a push işlemini kullanıcı kendi yapıyor (GitHub Desktop ile)
- Zaman baskısı var — gösterilebilir somut sonuç önemli
