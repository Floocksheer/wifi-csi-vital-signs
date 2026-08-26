# Proje Durumu, Kararlar ve Denenenler
### Yeni bir sohbet/oturum bu dosyayı okuyarak projeyi devralabilir

**Son güncelleme:** 25 Ağustos 2026 (akşam - yürüme modeli + otur/ayakta kapanışı + yeniden düzenleme)
**Depo:** `~/Documents/GitHub/wifi-csi-vital-signs` (GitHub: `Floocksheer/wifi-csi-vital-signs`, private)
**Diğer dokümanlar:** `PROJE_SUNUM.md` (sunum için), `OTUR_AYAKTA_VERI_TOPLAMA_PLANI.md` (yükseklik hipotezi + protokol), `RuView_CSI_Proje_Plani.md` (detaylı faz planı)

---

## 0. HIZLI BAŞLANGIÇ (yeni oturumda ilk okunacak)

### 🏁🏁🏁 2026-08-25 (AKŞAM): Yürüme MODELİ çalışıyor, OTUR/AYAKTA KAPANDI — EN GÜNCEL

**Özet (30 saniyede):** Kartlar 5V adaptöre alınıp odanın uçlarına, ofis
sandalyelerinin kafalıklarına (~1 m) yerleştirildi. Gün boyu otur/ayakta
ayrımı için **altı ayrı yöntem** denendi; **altısı da tekrarda çöktü** — bu
ayrım bu donanımda **kapandı** (sayılarla detay: Bölüm 3.9). Buna karşılık
elle eşik yerine **eğitilmiş bir yürüme modeli** yazıldı ve canlı arayüz
tamamen ona geçirildi: Leave-One-**Session**-Out ile **%92.9 faz doğruluğu**,
**kalibrasyon adımı YOK**. Ayrıca kullanılmayan 16 script + 2 ölü model ve
~3.1 GB veri ayrı klasörlere **taşındı (silinmedi)**.

#### Canlı arayüzün şu anki hali (`analysis/live_server_udp.py`)

| Gösterge | Nasıl üretiliyor | Güvenilirlik |
|---|---|---|
| **YÜRÜYOR / DURUYOR** | Eğitilmiş model (`models/walking_model.joblib`) | ✅ %92.9 faz bazında |
| oturuyor / ayakta | **Ölçülmüyor** — geçişlerden TAKİP ediliyor (durum makinesi) | ⚠️ kayabilir, arayüzden elle düzeltilir |
| nefes / nabız | `bpm_pipeline.py`, bantgeçiren + FFT | nefes ✅ (Bölüm 3.2), nabız ⚠️ (Bölüm 3.3) |

Çalıştırma:
```bash
cd analysis && source venv/bin/activate && python3 live_server_udp.py --start ayakta
# http://localhost:5050  |  durdurmak icin: pkill -f "live_server_udp.py"
```

**Soğuk başlatma doğrulandı (2026-08-25):** taşımalardan ve `__pycache__`
temizliğinden sonra sıfırdan başlatıldı, iki karttan da veri geldi
(507 / 529 paket), kalibrasyon istemedi, doğru tahmin üretti.

#### A-2) 🎬 İKİ ARAYÜZ VAR (2026-08-26)

| Dosya | Port | Ne için |
|---|---|---|
| `live_server_udp.py` | 5050 | **B planı.** Sade, yazı tabanlı. Sunum çökerse buna dön. |
| `live_view_udp.py` | **5051** | **Gösterim arayüzü.** RuView tarzı sahne: insan figürü, kart noktaları, canlı sinyal hattı. |

**`live_view_udp.py`, `live_server_udp.py`'yi import eder ve onun
`processing_loop`'unu çalıştırır** — yani ikisi AYNI beyni kullanıyor, asla
farklı tahmin gösteremezler. Sade arayüzün kodu hiç değiştirilmedi.

⚠️ **İKİSİ AYNI ANDA ÇALIŞAMAZ** — ikisi de UDP 2223'e bağlanıp kartlara
talip olur. `live_view_udp.py` bunu önden kontrol edip anlaşılır bir hata
verir; `live_server_udp.py` ise çıplak `OSError: Address already in use`
fırlatır. Önce çalışanı durdur:
```bash
pkill -f live_server_udp.py    # veya live_view_udp.py
```

**Sahnede figürün YATAY yeri KONUM DEĞİLDİR.** Bu donanım konum ölçemez
(kart başına 1 anten, faz bozuk, Bölüm 3.9). Figürün yeri her kartın kendi
hareket enerjisinin kendi sakin tabanına oranından türetilen "bozulma
dengesi"dir; ekranda da böyle yazıyor. Uydurma koordinat üretmemek için
bilerek böyle etiketlendi.

#### A) ✅ Yürüme modeli — projenin teslim edilebilir çıktısı

`analysis/train_walking_model.py` → `analysis/models/walking_model.joblib`

| | Değer |
|---|---|
| Eğitim verisi | 8 etiketli oturum, **2288 pencere** (509 yürüyor / 1779 yürümüyor) |
| Pencere / adım | 3.0 sn / 0.5 sn (canlı sistemle **aynı**) |
| Model | RandomForest, `class_weight="balanced"` |
| Doğrulama | **Leave-One-Session-Out** (model o oturumu hiç görmedi) |
| **Faz bazında doğruluk** | **%92.9** |
| Yumuşatılmış pencere / tek pencere | %86.9 / %85.1 |
| Şans seviyesi (çoğunluk sınıfı) | %77.8 |

Oturum bazında (tek pencere / yumuşatılmış / faz):
```
20260824_hareket_teshis         70.0%  69.4%   8/12 faz
20260824_hareket_turu           80.3%  79.7%  15/18 faz
20260824_hareket_turu_02        83.7%  85.3%  15/18 faz
20260824_durus_konum_degisken   85.2%  82.0%  17/17 faz
posture_v2/coupling_test        85.2%  83.6%  14/16 faz
posture_v2/s1_P1 / slow1 / slow2   (tek sinif)  100% / 97.1% / 96.8%
```

**Neden bu model eski yaklaşımların düştüğü tuzağa düşmüyor — 11 özelliğin
tamamı ÖLÇEKTEN BAĞIMSIZ:** bant enerji *oranları* (6 bant), log
sinyal/gürültü oranı, spektral merkez, değişim katsayısı, lag-1
otokorelasyon, aktif alt-taşıyıcı oranı. Mutlak genlik **hiç
kullanılmıyor** — çünkü mutlak genlik oturumdan oturuma kayıyor ve bu
projedeki bütün büyük başarısızlıkların kaynağı tam olarak oydu
(Bölüm 3.7: sınıf farkı 0.30, 2 saatlik ortam kayması 1.70).

En önemli özellikler: `spektral_merkez` 0.224, `bant_3.0_6.0` 0.131,
`bant_12.0_25.0` 0.126, `log_sinyal_gurultu` 0.120.

**Yan kazanım:** Model kol sallamayı (olasılık 0.08-0.14) yürümeden
(0.86-0.90) ayırıyor. Eski enerji eşiği bunu yapamıyordu — ikisi de
"hareket" görünüyordu.

**Özellik kodu `analysis/activity_features.py` içinde
(`walking_features()`), eğitim ve canlı sunucu AYNI fonksiyonu çağırıyor.**
Bilerek böyle: iki yerde ayrı yazılırsa eğitimle canlı davranış sessizce
ayrışır.

#### B) ❌ Otur/ayakta — altı yöntemin hepsi çöktü, KAPANDI

Detaylı sayılar ve neden'i **Bölüm 3.9**'da. Özet: duruş farkı SABİT bir
seviye farkı; sabit farklar donanım sürüklenmesiyle (AGC, sıcaklık, TX güç
uyarlaması) tam olarak aynı yerde yaşıyor, ayrıştırılamıyor.

**Canlı arayüzde ne yapıldı:** duruş ölçülmüyor, **takip ediliyor**. Kısa
hareket patlaması (0.5-4 sn) + seviye adımı = geçiş → durumu çevir.
**Yürüyüş bitince durum zorla AYAKTA'ya çekiliyor** — bu kesin bilgi, çünkü
her yürüyüş ayakta biter; yani her yürüyüş durum makinesini sıfırlıyor ve
hata birikmesini engelliyor. Kayarsa arayüzdeki düğmeyle elle düzeltilir
(`POST /posture/<oturuyor|ayakta>`).

#### C) 🗂️ Veri ve script yeniden düzenlemesi (hiçbir şey SİLİNMEDİ)

| Klasör | İçerik |
|---|---|
| `analysis/` | **9 aktif script** + `models/walking_model.joblib` |
| `analysis/kullanilmayan_scriptler/` | 16 script + 2 ölü model + `README.md` |
| `data/udp_session/`, `data/posture_v2/` | **Aktif eğitim seti** (75 M + 107 M) |
| `data/kullanilmayan_veriler/` | ~3.1 G (Kaggle setleri, seri port dönemi verisi) + `README.md` |

⚠️ `data/` klasörü `.gitignore`'da — oradaki dosyaların **git'te yedeği YOK**.
Her iki `README.md` de hangi verinin hangi dokümante sonucun kaynağı
olduğunu ve taşınan scriptleri tekrar çalıştırmak için gereken yol
düzeltmelerini yazıyor.

---

### 🚀🚀🚀 2026-08-25: BYOD/MAC-spoof denemesi kapandı, dünkü 2-ESP UDP mimarisine GERİ DÖNÜLDÜ

**Özet (30 saniyede):** Bugün yönetici ofis WiFi'sine (BYOD, MAC filtreli) MAC
taklidiyle bağlanmayı denedik — donanımsal engel yüzünden (BYOD 5GHz, klasik
ESP32 sadece 2.4GHz) imkansız olduğu kanıtlandı, kapandı. Tek-ESP+telefon
hotspot alternatifi de denendi, teknik olarak çalışıyor ama dünkü kanıtlanmış
2-ESP mimarisinin gerisinde kaldığı için **terk edildi**. Şu an sistem
**dünkü haliyle** (Bölüm 0'ın altındaki 2026-08-24 UDP mimarisi) çalışıyor ve
doğrulandı: iki kart da hotspot üzerinden UDP ile veri gönderiyor. **Kartlar
henüz USB'de** — bir sonraki adım onları 5V adaptöre alıp odanın uçlarına
yerleştirmek.

#### A) BYOD / MAC-spoof denemesi (KAPANDI, kod duruyor ama pasif)

**Neden denendik:** BT ekibi ofis WiFi şifresini vermeyeceğini söyledi.
Yönetici "orada erişim MAC adresine göre veriliyor, kendi laptobumun MAC'ini
ESP'ye çak, o da bağlansın" dedi.

**Ne yapıldı:**
- `firmware/ESP32-CSI-Tool/active_sta/main/main.cc` — `parse_mac()` ve
  `apply_spoof_mac()` eklendi. `CONFIG_SPOOF_MAC` (Kconfig, yeni) boş
  değilse `esp_wifi_set_mac()` ile ESP'nin STA MAC'ini değiştiriyor.
  `station_init()` içinde `esp_wifi_set_mode()` sonrası, kimlik bilgilerinden
  ÖNCE çağrılıyor.
- `Kconfig.projbuild` — `SPOOF_MAC` string seçeneği (varsayılan boş = dokunma).
- Bu iki değişiklik **push edilmeye karar verildi** (2026-08-25, kullanıcı
  GitHub Desktop'ta inceledi) — eski/çöp değil, çalışan opsiyonel bir özellik,
  varsayılan davranışı hiç etkilemiyor (boş string = no-op).

**Test sonucu — donanımsal engel:**
1. `sdkconfig.defaults.local`: `SSID="BYOD"`, şifre boş, `SPOOF_MAC="4e:bd:9f:62:b7:fc"`
   (kullanıcının kendi laptop MAC'i) ile derlendi, flashlandı.
2. Seri log: **`reason=201` (NO_AP_FOUND)** sürekli tekrarladı — ESP "BYOD"
   SSID'sini TARAMA aşamasında bile bulamıyordu (MAC taklidi devreye
   girmeden önce tıkanıyordu).
3. Kullanıcı laptobunun BYOD'a bağlıyken hangi bantta olduğunu kontrol etti:
   **5GHz**. Klasik ESP32 (D0WD-V3, DevKitV1) donanımsal olarak SADECE
   2.4GHz destekliyor — hiçbir yazılım/config ayarıyla çözülemez.
4. **Karar: BYOD yolu tamamen kapandı.** Kod (`SPOOF_MAC`) silinmedi çünkü
   ileride 2.4GHz bir MAC-filtreli ağ çıkarsa işe yarayabilir, ama şu an
   `sdkconfig.defaults.local`'de `CONFIG_SPOOF_MAC=""` (pasif).

⚠️ **Çakışma uyarısı (hâlâ geçerli, ileride tekrar denenirse):** MAC spoof
kullanılacaksa, o MAC'in gerçek sahibi (kullanıcının laptobu) AYNI ANDA aynı
ağda OLMAMALI (iki cihaz aynı MAC = çakışma). Laptobu farklı bir ağa (ör.
telefon hotspot) alıp ESP'yi BYOD'a bağlamak gerekir.

#### B) Tek-ESP32 + telefon hotspot denemesi (teknik olarak ÇALIŞIYOR ama TERK EDİLDİ)

BYOD kapanınca ara adım olarak: tek ESP32'yi doğrudan telefon hotspot'una
("Furkan iPhone" / `frk21wrk`) bağlayıp test ettik.

**Bağlantı:** `sdkconfig.defaults.local`'i `SSID="Furkan iPhone"` yapıp
flashladık → bağlandı, RSSI -39 ile -48 arası, IP `172.20.10.12` aldı.

**Hız sorunu ve KÖK NEDEN ANALİZİ (önemli, tekrar düşmemek için):**
- İlk ölçüm: sadece **~8.3-8.9 Hz**. `CONFIG_PACKET_RATE=100` ayarlı, ESP'nin
  kendi üstündeki `socket_transmitter_sta_loop` görevi ("flood", gateway'e
  UDP gönderiyor) da çalışıyordu ("sending frames." logu görüldü) — ama hıza
  hiç yansımadı.
- **Yanlış ipucu (denendi, işe yaramadı):** Serideki `<ba-add> ... winSize:64`
  logundan "AMPDU blok-ACK agregasyonu paketleri topluyor, ACK sayısını
  azaltıyor" diye şüphelenildi. `CONFIG_ESP32_WIFI_AMPDU_TX_ENABLED=n` ile
  kapatılıp yeniden flashlandı → **hiçbir fark yaratmadı** (hâlâ ~8.9 Hz).
  Bu değişiklik geri alındı (config'te kalmadı).
- **Gerçek kök neden (Bölüm 3.8'de zaten belgeliydi, unutulmuştu):**
  **CSI, ESP32'nin GÖNDERDİĞİ değil ALDIĞI çerçevelerden üretilir.** ESP'nin
  kendi flood'u (STA→gateway) bu yüzden anlamsız — CSI'yi artırmıyor, sadece
  gönderdiği paketleri sayıyor. Asıl çözüm **laptop'tan ESP'nin IP'sine**
  paket yağdırmak (`analysis/packet_flooder.py`, ESP'nin RECEIVE ettiği
  paket sayısını artırır).
- **Doğrulama:** `packet_flooder.py`'yi laptoptan ESP'nin IP'sine
  (`172.20.10.12:2223`, 250 paket/sn) çalıştırınca hız **102-127 Hz**'e
  çıktı (RSSI -39 ile -52 arası, iki ayrı ölçümde tutarlı).

**Neden yine de terk edildi:** Bu kurulum teknik olarak çalışsa da:
1. Dünkü 2-ESP mimarisi zaten **kanıtlanmış** (%85-87 yürüme doğruluğu,
   gerçek veriyle), tek-ESP için böyle bir doğrulama yok.
2. Yöneticinin kendi önerdiği mimari zaten 2-ESP (Bölüm 0'ın altı).
3. 2-ESP, odanın iki farklı hattını tarıyor (uzamsal çeşitlilik) — tek ESP
   sadece telefon-ESP arasındaki tek hatta bağımlı.

**Yan tartışma (fizik, ileride tekrar sorulursa diye not):** Kullanıcı flood
paketlerinin insan-vücudu-engelleme etkisini bozup bozmadığını sordu. Cevap:
Hayır — CSI paketin İÇERİĞİNDEN değil, radyo dalgasının fiziksel kanaldan
geçişinden hesaplanıyor; boş/dolu fark etmez, vücut aynı şekilde
engelliyor/yansıtıyor. Flood sadece ölçüm SIKLIĞINI artırıyor, fiziği
değiştirmiyor. Ayrıca "tek kart + telefon dip dibe masada dursa ne kadar
alan ölçülür" sorusuna: bu HİÇ test edilmedi ama fizik olarak beklenti
kötü — Tx/Rx çok yakınken güçlü doğrudan yol, zayıf ortam-yansımalarını
"boğar" (monostatic/backscatter'a döner, bistatic blocking yerine); tahmin
~1-2 metre güvenilir alan, doğrulanmadı.

**"360 derece algılama" netleştirmesi (kullanıcı önceki oturumda farklı bir
cevap almıştı, çelişki giderildi):** Anten yönsüz — sinyal gerçekten her
yöne yayılıyor (bu doğru). Ama tek bir sabit noktadan (ESP) alınan CSI,
sadece O NOKTAYA ulaşan sinyali (doğrudan yol + yansımalar) yansıtıyor.
Yani "odanın her yerini EŞİT hassasiyette görür" YANLIŞ; "telefon-ESP
hattına ve güçlü yansıma yollarına yakın hareketi iyi görür, uzak/gölgede
kalan köşeleri zayıf görür" DOĞRU. Bu yüzden 2-ESP mimarisi (iki ayrı hat)
tek-ESP'den fiziksel olarak daha güvenilir.

#### C) Dünkü 2-ESP UDP mimarisine dönüş ve doğrulama (2026-08-25)

**Kod durumu doğrulandı:** `git log` kontrol edildi — HEAD (`e53d47c`) zaten
`0c5d109` ("hotspot 2 esp ile canlı testler") + üzerine sadece
`live_server_udp.py` eklenmiş halde duruyordu. Yani UDP mimarisinin TÜM
kodu (`csi_udp_server.py`, `csi_udp_component.h`, `guided_capture_udp.py`,
`evaluate_udp_session.py` vb.) bozulmadan, olduğu gibi mevcuttu — hiçbir
şey geri yüklemeye gerek kalmadı, sadece firmware config'i çevirip iki
kartı yeniden flashlamak yeterliydi.

**Yapılanlar:**
1. `sdkconfig.defaults.local` → `SSID="Furkan iPhone"`, `SPOOF_MAC=""`,
   **`SEND_CSI_TO_SERIAL=n`, `SEND_CSI_TO_UDP=y`** olarak ayarlandı.
2. İki kart da (`/dev/cu.usbserial-0001` = STA-9d9c, `/dev/cu.usbserial-3`
   = STA-85b0) bu ayarla flashlandı, ikisinde de "Hash of data verified"
   ile tam tamamlandı (yarım flash riski yok).
3. **İlk doğrulama denemesi BAŞARISIZ oldu: "0 kart" bulundu.** Teşhis:
   laptop, macOS'un otomatik ağ tercihiyle **ofis WiFi'sine** (`172.70.x.x`,
   5GHz, WPA2-Enterprise) geri kaymıştı — ESP'ler telefon hotspot'unda
   (`172.20.10.x`) kalmıştı, iki taraf da farklı ağdaydı, discovery broadcast'i
   hiç ulaşmadı. `ipconfig getifaddr en0` ile yakalandı.
4. Kullanıcı laptobu elle "Furkan iPhone"ya bağladı (`172.20.10.6`).
5. **Doğrulama BAŞARILI:** `csi_udp_server.py --duration 15` çalıştırıldı →
   iki kart da bulundu, veri akıttı:
   - `STA-85b0` (172.20.10.13): başlangıçta 98-100 Hz, ortalama 48.9 Hz
   - `STA-9d9c` (172.20.10.12): başlangıçta 114-125 Hz, ortalama 45.3 Hz
   - (Hız zamanla düşüyor — muhtemelen iki kart aynı hotspot bant
     genişliğini paylaşıyor; dünkü "130-190 Hz" muhtemelen anlık/tek-kart
     zirvesiydi. Bu normal, kanıtlanmış hareket tespiti eşiği zaten bu
     hız aralığında çalışıyordu.)

**⚠️ YENİ TUZAK (bu oturumda ilk kez yaşandı, listeye eklendi — Bölüm 6):**
macOS, tercih sırasına göre bilinen bir ağı (ör. kurumsal WiFi) telefon
hotspot'undan daha yüksek öncelikli görüp **otomatik olarak ona geçebilir**,
laptop hotspot'tan sessizce kopar. `csi_udp_server.py` "0 kart" derse İLK
kontrol edilecek şey: `ipconfig getifaddr en0` ile laptobun GERÇEKTEN hangi
ağda olduğunu doğrulamak (ESP'lerin IP'siyle aynı /28 alt ağda mı?).

**Şu anki fiziksel durum:** İki kart da HÂLÂ USB'ye takılı (laptoptan güç
alıyor, flash için gerekliydi). Bir sonraki adım: USB'den çıkarıp 5V
adaptörlere takmak, odanın iki ucuna yerleştirmek, telefonu ortaya koymak
— firmware ayarları flash'ta kalıcı olduğu için güç kaynağı değişimi
hiçbir ayarı bozmaz.

---

### 🎙️ SESLİ YÖNLENDİRMELİ VERİ TOPLAMA — TAM FORMAT REFERANSI (güncel, UDP mimarisi)

Bu proje boyunca tüm etiketli veri, kronometre yerine **bilgisayar sesli
komutuyla** toplandı (kronometre senkron hatası ilk denemede veriyi
kullanılamaz hale getirmişti — bkz. Bölüm 5.1). Güncel (2-ESP UDP) mimaride
kullanılacak script: **`analysis/guided_capture_udp.py`**.

**Mekanizma:**
1. `CsiUdpServer` başlatılır (discovery broadcast + flood otomatik döner,
   arka planda thread).
2. `--settle-sec` (varsayılan 6 sn) kadar beklenir, kartların bulunması
   için. Bulunamazsa `SystemExit` ile hata verir ("kartlar açık mı, hotspot'a
   bağlı mı, laptop aynı ağda mı" kontrol ettirir).
3. Geri sayım: `say -v Yelda` ile "Hazır ol" → 2 sn → "3" → "2" → "1"
   (her sayı arası 1 sn), bloklamadan (`subprocess.Popen`, konuşma süresi
   zamanlamayı kaydırmaz).
4. Her faz başında (`t0 + i*phase_sec` anında) o fazın komutu SESLİ
   SÖYLENİR (`speak(cue)`) ve **o anki laptop saati** (`time.time()`)
   `recv_ts_start` olarak kaydedilir.
5. Bitişte "Bitti" söylenir, 0.5 sn beklenir (son paketler gelsin diye),
   `srv.save()` ile CSV'ler yazılır.

**Neden ESP saati DEĞİL laptop saati kullanılıyor (kritik fark, eski
`guided_capture.py`'den ayrılan nokta):** İki kartın saatleri BAĞIMSIZ
(her biri kendi açılışından beri sayıyor, ortak referans yok). UDP
sunucusu her satırın laptoba ULAŞTIĞI anı zaten `recv_time` sütununa
yazıyor — bu ortak eksen olarak kullanılıyor. Ağ gecikmesi (birkaç ms)
3 saniyelik geçiş paylarının yanında ihmal edilebilir.

**Çıktı formatı:**
- `<output>_STA-9d9c.csv`, `<output>_STA-85b0.csv` — her kart için ayrı CSV,
  başlık: `type,role,mac,rssi,rate,sig_mode,mcs,bandwidth,smoothing,
  not_sounding,aggregation,stbc,fec_coding,sgi,noise_floor,ampdu_cnt,
  channel,secondary_channel,local_timestamp,ant,sig_len,rx_state,
  real_time_set,real_timestamp,len,CSI_DATA,recv_time` (son sütun YENİ,
  eski ayrıştırıcılarla uyumluluk için SONA eklendi).
- `<output>.json` — faz meta verisi:
  ```json
  {
    "phase_sec": 12,
    "cues": ["otur", "ayakta", "otur", ...],
    "postures": ["otur", "ayakta"],
    "phases": [
      {"phase": 0, "posture": "otur", "label": 0,
       "recv_ts_start": 1755999999.123, "recv_ts_end": 1756000011.456},
      ...
    ],
    "files": {"STA-9d9c": "...", "STA-85b0": "..."},
    "note": "recv_ts_* laptop saati; CSV'nin son sutunu recv_time ayni saat"
  }
  ```

**2026-08-25'te eklenen bayraklar (ikisi de acı deneyimden doğdu):**

| Bayrak | Ne işe yarıyor | Neden eklendi |
|---|---|---|
| `--jitter N --seed K` | Faz süresine ±N sn rastgelelik katar | **Sabit süre = sahte başarı.** Kişi komut zamanını öğrenip hazırlanıyor; zirve gecikmesi farkı FİZİK sanılıyor. Jitter eklenince o "ayrım" buharlaştı. Bkz. Bölüm 3.9 |
| `--position P1` | Kişinin durduğu noktayı JSON'a yazar | Konum etiketi olmadan doğru doğrulama **yapılamıyor**: gruplar faza göre ayrılırsa aynı konumun başka fazı eğitimde kalır, model duruş yerine konumu ezberler. Leave-One-**Position**-Out buna muhtaç |
| `--height CM` | Kartların yerden yüksekliği | Geometri değişince veriler BİRLİKTE eğitilemez |
| `--session tur1` | Oturum kimliği | Oturumlar arası kaymayı ayırmak için (Bölüm 3.7) |

**Kullanım örnekleri:**
```bash
# Varsayılan: otur/ayakta dönüşümlü, 12 faz x 12 sn
python guided_capture_udp.py --output ../data/udp_session/test

# Özel komut listesi (virgülle ayrılmış, sırayla söylenir)
python guided_capture_udp.py --cues "kıpırdama,yürü,kıpırdama,yürü" \
    --phase-sec 10 --output ../data/udp_session/hareket_teshis

# ⭐ ÖNERİLEN: koşullar etiketli + jitter'lı (geçiş verisi için ZORUNLU)
python guided_capture_udp.py --cues "otur,ayakta,otur,ayakta" \
    --phase-sec 12 --jitter 3 --seed 1 \
    --position P1 --height 150 --session tur1 \
    --output ../data/posture_v2/tur1_P1
```

⚠️ `speak()` artık `voice.py`'de (eskiden `guided_capture.py`'nin içindeydi;
modern UDP araçları sırf 4 satır için tüm seri-port mimarisini import ediyordu).

**Değerlendirme:** `analysis/evaluate_udp_session.py` — `parse_udp_csv()`,
`phase_windows()`, `logo_accuracy()` fonksiyonlarıyla kaydedilen JSON+CSV'yi
okuyup LeaveOneGroupOut doğruluğu hesaplıyor, tek kart vs iki kart
birleşimini karşılaştırıyor.

**Bu formatla toplanan AKTİF veriler — yürüme modelinin eğitim seti**

`data/posture_v2/` (2026-08-25, kartlar ~1 m, sandalye kafalıklarında):

- `s1_P1` — otur/ayakta, tek konum (P1)
- `coupling_test` — kişinin hatta ne kadar bağlı olduğu ölçüldü: yürüme
  enerji oranı **1.78x / 3.35x** → kişi hatta NET görünüyor ("bağlı değil"
  hipotezi bu kayıtla çürütüldü)
- `slow1` / `slow2` — YAVAŞ otur/kalk, jitter'lı. Yöntem 6'nın hem %100'ü
  hem %56'sı buradan çıktı (Bölüm 3.9)

`data/udp_session/` (2026-08-24):
- `20260824_hareket_teshis` — yürüme %85-87 ile ayrışıyor (KANITLANMIŞ, ✅)
- `20260824_durus_konum_degisken` — otur/ayakta %40-46 (şans altı, KRİTİK
  NEGATİF bulgu — Bölüm 0'ın altındaki "EN KRİTİK BULGU"na bak)
- `20260824_hareket_turu` + `_02` — hareketin TÜRÜNÜ (yerinde mi, yer
  değiştirerek mi) ayırt etme denendi, İKİ TEKRARDA DA başarısız (enerji
  oranı ~1.0x, "kayma" ölçüsü iki testte ters yön verdi: 1.22x vs 0.66x)
  — **bu ayrım şu an mümkün değil, tekrar denenmeden önce yeni bir yöntem
  fikri gerekiyor.**

---

### 🚀🚀 2026-08-24 (AKŞAM): UDP mimarisine geçildi

**Yönetici önerisi üzerine mimari değişti.** Artık kartlar USB kablosuna bağlı değil.

```
   [ESP32 #1]  ......  [TELEFON hotspot]  ......  [ESP32 #2]
   odanın ucu           odanın ORTASI              odanın ucu
   5V adaptör           (asıl VERİCİ)              5V adaptör
        \                     |                      /
         \_____ CSI verisi (UDP) ____________________/
                          |
                    [LAPTOP] aynı hotspot'ta, csi_udp_server.py
```

**Neden değişti:** Kartlar USB'ye bağlı olduğu için odanın uçlarına
konamıyordu; algılama hacmi bir masa üstü kadar kalıyor ve yürüme/duruş
ayrımı fiziksel olarak mümkün olmuyordu (bkz. Bölüm 5.1, Sonuç 3-4).

**ÖLÇÜLEN SONUÇ (ilk test): 130-190 Hz, İKİ karttan aynı anda.**
Önceki en iyi: tek kart, 100 Hz. Yani hem hız arttı hem de iki bağımsız
ölçüm akışı (uzamsal çeşitlilik) kazanıldı.

| | Eski (AP+STA, USB) | Yeni (UDP, kablosuz) |
|---|---|---|
| Kart sayısı (veri veren) | 1 | **2** |
| Hız | 70-100 Hz | **130-190 Hz** |
| Kartların yeri | USB kablosu kadar | **odanın herhangi bir yeri** |
| Laptop bağlantısı | USB seri | WiFi (aynı hotspot) |

**Firmware değişiklikleri (hepsi commit edilmeli):**
- `_components/csi_udp_component.h` — YENİ. CSI'yi UDP ile gönderir.
  Kuyruk + ayrı görev (CSI geri çağırımı WiFi görevinde çalışıyor, orada
  ağ işlemi yapmak sistemi bloklar). Kuyruk dolarsa satır düşürülür, sayılır.
- `_components/csi_component.h` — UDP kuyruğuna yazar; seri çıkış artık
  `CONFIG_SEND_CSI_TO_SERIAL` ile opsiyonel. Ayrıca her kart kendi MAC'inden
  kimlik üretiyor: `role` sütunu "STA-9d9c" / "STA-85b0" oluyor.
  **CSV formatı değişmedi** - eski analiz kodları çalışmaya devam ediyor.
- `active_sta/main/main.cc` — **PMF ayarı eklendi** (`pmf_cfg.capable = true`).
  ⚠️ BU OLMADAN iPhone hotspot'una BAĞLANILAMIYOR: şifre doğru olsa bile
  `reason=204` (HANDSHAKE_TIMEOUT) ile düşüyor. iOS hotspot'u WPA2/WPA3
  karışık modda yayın yapıp korumalı yönetim çerçevesi bekliyor.
- `active_sta/main/Kconfig.projbuild` — `SEND_CSI_TO_UDP` seçeneği.
- `CONFIG_WIFI_CHANNEL=0` (tüm kanalları tara) - hotspot kanalı sabit değil.

**Sunucu tarafı:** `analysis/csi_udp_server.py` — iki iş birden yapıyor:
1. Kartlardan gelen CSI'yi toplar, `role` sütununa göre karta ayırır
2. Kartlara paket gönderir (CSI ALINAN çerçevelerden üretilir; kimse
   göndermezse hız ~10 Hz'e düşer). Saniyede 2 kez YAYIN paketi (kartlar
   sunucunun adresini böyle öğreniyor - elle IP ayarı YOK), kart bulununca
   ona doğrudan ~250 paket/sn.

**Kurulum sırası (önemli):** Sunucu çalışmıyorsa kartlar veri göndermez
(sunucuyu keşfedememiş olurlar). Önce `csi_udp_server.py`, sonra ölçüm.

**Tuzak:** Flash yarıda kalırsa kart açılış döngüsüne girer
("No bootable app partitions"). Yükleme çıktısında **3 adet "Hash of data
verified" + "Leaving..."** görülmeli; görülmüyorsa tekrar yükle.

---

### ❌❌ EN KRİTİK BULGU (2026-08-24 akşam): OTUR/AYAKTA ÇALIŞMIYOR — kapandı

**Kontrollü test yapıldı ve önceki tüm olumlu sonuçları çürüttü.**

Bugün gün boyunca otur/ayakta için %70-74 doğruluk aldık ve bir noktada
"24 faz, 17 doğru, binom p=0.032, istatistiksel olarak anlamlı" dedik.
**Bu sonuç GEÇERSİZ.** Sebebi: o testlerin hepsinde kişi HEP AYNI NOKTADA
oturup kalkıyordu. Model duruşu değil, o noktanın/zamanın imzasını
ezberliyordu.

**Çürüten test (calib_01, UDP mimarisi, 9 faz):** Kişi her turda FARKLI bir
noktada oturup kalktı (tur içinde aynı nokta, turlar arası farklı). Modelin
konuma tutunma imkanı kapatıldı:

| | Doğruluk |
|---|---|
| STA-85b0 tek başına | %45.6 |
| STA-9d9c tek başına | %43.3 |
| İkisi birlikte (416 özellik) | %40.0 |
| *şans seviyesi* | *%50* |

Üçü de şans seviyesinin ALTINDA. Konum serbest bırakılınca sinyal tamamen
kayboluyor.

**SONUÇ: Bu donanımla (1 anten, 2.4 GHz, klasik ESP32) statik duruş
sınıflandırması yapılamıyor.** Denenen ve başarısız olan her şey:
mutlak desen, postural sway (dinamik), yüksek örnekleme hızı (9.5 -> 190 Hz),
kesintisiz oturum, 4 farklı geometri, iki kartın birleşimi. **Tekrar
denemeye değmez** - yeni bir fikir varsa önce konum-değişken protokolle
test edilmeli, sabit konumda alınan hiçbir sonuca güvenilmemeli.

**METODOLOJİK DERS (bu projenin en pahalı dersi):** Sabit konumda ölçüm,
duruş sınıflandırmasında yanıltıcı yüksek doğruluk üretir. Doğrulama
protokolü, modelin tutunabileceği her yardımcı değişkeni (konum, zaman,
oturum) bilerek değiştirmeli. Yoksa "istatistiksel olarak anlamlı" bir
sonuç bile tamamen yanlış olabilir.

### ✅ ÇALIŞAN: hareket/yürüme tespiti (UDP mimarisi, 2026-08-24 akşam)

⚠️ **GÜNCEL DEĞİL — bu bölüm tarihseldir.** Aşağıdaki eşik yöntemi
2026-08-25'te **eğitilmiş modelle değiştirildi** (%92.9 faz doğruluğu,
kalibrasyon yok). Eşik yönteminin iki kusuru vardı: (a) kalibrasyona
bağımlıydı ve kalibrasyon anı sakin değilse sistem tamamen ölüyordu,
(b) kol sallamayı yürümeden ayıramıyordu. Güncel yöntem: Bölüm 0 / A.

| Ölçüm | Değer |
|---|---|
| Yürüme / hareketsiz enerji oranı | **1.72x** |
| Eşikle ayırma doğruluğu | **%85** |
| Yöntem | bantgeçiren 0.3-3 Hz, 4 sn pencere, İKİ KARTIN MİNİMUMU |

**"İki kartın minimumu" neden en iyisi:** gürültü sıçramaları iki kartta
bağımsız; minimum alınca birinde çıkan sahte yükselme eleniyor, gerçek
hareket ikisini birden yükselttiği için hayatta kalıyor. Ölçüm: tek kart
%76 ve %83, minimum %87 (motion_check); calib_01'de %85.

Bu yöntem üç ayrı geometride tutarlı çalıştı - konumdan bağımsız,
güvenilir. **Projenin sağlam teslim edilebilir çıktısı budur.**

---

### 2026-08-24 (öğlen): 2. ESP32 AP olarak kuruldu — ARTIK KULLANILMIYOR
(Yukarıdaki UDP mimarisi bunun yerini aldı. Yedek yapılandırma:
`active_sta/sdkconfig.defaults.local.apbak`. Aşağıdaki bilgiler tarihsel.)

### 🚀 2026-08-24: 2. ESP32 kuruldu — mimari değişti (TARİHSEL, UDP mimarisi bunun yerini aldı)
Artık **iki kart** var, laptop bağlantısı olmadan çalışan bir AP+STA çifti:
- **Board A** (orijinal kart, MAC `d4:e9:f4:a4:9d:9c`) — `active_sta` firmware'i,
  laptopa USB ile bağlı, **CSI toplayan ve seri porttan veri gönderen kart**.
  Port: `/dev/cu.usbserial-3` (port ismi değişebilir, aşağıya bak).
- **Board B** (2. kart, MAC `d4:e9:f4:a4:85:b0`) — `active_ap` firmware'i,
  kendi WiFi ağını yayınlıyor (SSID `ESP32_CSI_AP`, şifre `csitool123`, kanal 6).
  CSI TOPLAMIYOR (`SHOULD_COLLECT_CSI=n` — Board A'nın hızını maksimize etmek için).
  Sadece güç istiyor, laptopa veri bağlantısı GEREKMİYOR (şu an ikisi de aynı
  laptopta çünkü kullanıcının başka güç kaynağı yok — bu sorun değil, iki port
  yeter).
- **Ölçülen sonuç: flood'suz, sadece firmware'in kendi dahili STA→AP
  trafiğiyle 82-101 Hz.** Laptop flood'u bu mimaride YARDIMCI DEĞİL, ZARARLI
  (82-101 Hz → flood ile 67 Hz'e düşüyor — seri port + radyo zamanı için
  firmware'in kendi trafiğiyle yarışıyor). `capture_csi.py` artık varsayılan
  olarak flood YAPMIYOR (`--flood` ile açılabilir, sadece tek kart + ev
  wifi/hotspot senaryosu için hâlâ işe yarar).
- **Port isimleri karışabilir:** iki CP2102 kartın ikisi de fabrika seri
  numarası "0001" paylaşıyor, macOS `/dev/cu.usbserial-0001` ve
  `/dev/cu.usbserial-3` gibi farklı isimler veriyor ama SIRA GARANTİLİ DEĞİL.
  Emin olmak için: `esptool.py --port /dev/cu.usbserial-X chip_id` çalıştır,
  MAC `...9d:9c` ise Board A (STA/veri), `...85:b0` ise Board B (AP).
- Sıradaki adım: bu yeni hızla otur/ayakta + yürüme verisi baştan toplamak
  (bkz. Bölüm 5).

### Ortamı açma
```bash
# ESP-IDF (firmware derlemek/yüklemek için) - her yeni terminalde bir kez
source ~/Documents/GitHub/wifi-csi-vital-signs/activate_idf.sh
export CMAKE_POLICY_VERSION_MINIMUM=3.5     # modern CMake + eski ESP-IDF uyumu için ŞART

# Python analiz ortamı
cd ~/Documents/GitHub/wifi-csi-vital-signs/analysis && source venv/bin/activate
```

### Sık kullanılan komutlar (2026-08-25 itibarıyla GÜNCEL)
```bash
cd analysis && source venv/bin/activate

# 1) GÖSTERİM ARAYÜZÜ (asıl gösterilecek şey) - kalibrasyon adımı YOK
python3 live_view_udp.py --start ayakta         # http://localhost:5051
pkill -f "live_view_udp.py"                     # durdurmak için

# 1b) B PLANI: sade arayüz (AYNI ANDA DEĞİL - ikisi de UDP 2223'e bağlanır)
python3 live_server_udp.py --start ayakta       # http://localhost:5050

# 2) Kartların bağlı olduğunu ve hızı doğrula (kartlar adaptörde, USB gerekmez)
python3 csi_udp_server.py --duration 15
#    Beklenen: iki kart da görünmeli, ~45-190 Hz (paylaşımlı bant, dalgalanır)

# 3) Yürüme modelini yeniden eğit (özellik/veri değişirse ŞART)
python3 train_walking_model.py                  # -> models/walking_model.joblib

# 4) Etiketli veri topla (geçiş verisinde --jitter ZORUNLU, bkz. Bölüm 3.9)
python3 guided_capture_udp.py --cues "kıpırdama,yürü,kıpırdama,yürü" \
    --phase-sec 12 --jitter 3 --seed 1 --position P1 --height 150 \
    --session tur1 --output ../data/posture_v2/tur1_P1

# 5) Firmware yükleme (SADECE ayar değişince - kartı USB'ye takman gerekir)
cd ../firmware/ESP32-CSI-Tool/active_sta
rm -f sdkconfig sdkconfig.old && idf.py build
idf.py -p /dev/cu.usbserial-X -b 115200 flash    # -b 115200 ŞART
#    Çıktıda 3x "Hash of data verified" + "Leaving..." GÖRÜLMELİ
```
⚠️ Kartlar hotspot'a bağlanmıyorsa: telefonda *Kişisel Erişim Noktası →
Maksimum Uyumluluk* açık mı? Laptop da AYNI hotspot'ta mı?
(`ipconfig getifaddr en0` ile doğrula.)

**ESKİ (seri port) komutları** — `capture_csi.py`, `guided_capture.py`,
`calibrate_live.py`, `live_server.py` artık
`analysis/kullanilmayan_scriptler/` içinde ve hâlâ seri porttan okuyorlar.
Sadece USB mimarisine dönülürse geçerli; o klasördeki `README.md`
çalıştırma yollarını anlatıyor.

### Donanım gerçekleri
| | Board A (STA, veri) | Board B (AP, sadece yayın) |
|---|---|---|
| Rol | CSI toplar, laptopa USB ile bağlı | Kendi ağını yayınlar, CSI toplamaz |
| Kart | ESP32-D0WD-V3 (klasik ESP32, DevKitV1) | ESP32-D0WD-V3 (aynı model) |
| MAC | `d4:e9:f4:a4:9d:9c` | `d4:e9:f4:a4:85:b0` (AP arayüzü: `...85:b1`) |
| Seri port | `/dev/cu.usbserial-3` (değişebilir) | `/dev/cu.usbserial-0001` (değişebilir) |
| Ağ | `ESP32_CSI_AP` şifre `csitool123` kanal 6'ya bağlanır, IP `192.168.4.2` | AP olarak `192.168.4.1`'i yayınlar |

Ortak: **1 anten** (poz tahmini için 3 gerekiyor → yapılamıyor), **sadece 2.4 GHz**, baud **921600**.

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

### Karar 3: ~~Duruş sınıflandırma modeli SADECE otur/ayakta ile eğitiliyor~~ → İPTAL
**Eski karar (2026-08-19):** İki aşamalı mimari — "ani hareket" tespiti eşikle (fizik), duruş ayrımı modele.
**İPTAL EDİLDİ (2026-08-25):** Tam tersi oldu. Duruş ayrımı bu donanımda yapılamıyor (Bölüm 3.9), buna karşılık HAREKET tespiti eşikten alınıp **modele** verildi. Yani roller yer değiştirdi: model yürümeyi öğreniyor, duruş ise ölçülmüyor (geçişlerden takip ediliyor).

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

### 3.9 ⛔ OTUR/AYAKTA: ALTI YÖNTEM, ALTISI DA ÇÖKTÜ (2026-08-25) — DOSYA KAPANDI

**Bu bölümün amacı:** Yeni bir oturum "acaba şunu denesek mi" diye aynı
fikirlere geri dönmesin. Her satır GERÇEKTEN denendi ve GERÇEKTEN çöktü.
Çökme biçimi hep aynı: **bir ölçümde umut verdi, tekrarında ya kayboldu ya
işaret değiştirdi.**

| # | Yöntem | İlk ölçüm | Tekrarda ne oldu |
|---|---|---|---|
| 1 | Postural sway (dinamik salınım) | — | %39.6, binom **p=0.92** (tamamen rastgele) |
| 2 | Mutlak desen (ML, tüm alt-taşıyıcılar) | sabit konumda %70-74 | konum serbestken **%40-46** (şans %50'nin ALTI) |
| 3 | "Kayma" ölçüsü (yer değiştirme enerjisi) | 1.22x | tekrarda **0.66x** — iki kart birbirini yalanladı |
| 4 | Faz-arası seviye adımı (Δseviye işareti) | işaretler `- - +` | tekrarda `+ + +` — işaret oturuma göre değişiyor |
| 5 | Geçiş dalga şekli asimetrisi | **+1.25** | veri artınca **−0.70** — yön tamamen döndü |
| 6 | Dar pencere önce/sonra farkı | slow1: **%100**, Cohen d=**3.50** | slow2 (aynı nokta, dakikalar sonra): **%56**, d=**0.32**, STA-85b0'da işaret TERS |

**Yöntem 6 en çok umut vereni ve en öğreticisiydi:** geçiş anının hemen
öncesi (−3.5…−0.5 sn) ile hemen sonrası (+1.0…+4.0 sn) medyanlarının farkı.
İlk kayıtta kusursuz ayırdı. **Aynı kişi, aynı nokta, aynı kartlar, birkaç
dakika sonra** tekrarlanınca çöktü. Yani sorun yöntemde değil, ölçülen
büyüklüğün kendisinde.

#### Neden — ölçülen sayılarla

| Ölçüm | Değer |
|---|---|
| İki duruş **arasındaki** seviye farkı (85b0 / 9d9c) | **0.30 / 0.40** |
| Aynı duruşun **kendi içindeki** yayılımı (85b0 / 9d9c) | **2.68 / 0.88** |

Aranan sinyal, gürültünün **içinde kalıyor**. Yürüme neden çalışıyor da bu
çalışmıyor sorusunun cevabı burada: yürümede fark zamanla değişen (0.3-3 Hz)
bir salınım, filtreyle ayrılabiliyor. Duruş farkı ise **sabit bir seviye
kayması** — ve sabit kaymalar donanım sürüklenmesiyle (AGC, sıcaklık, TX güç
uyarlaması, hız uyarlaması) tam olarak aynı yerde yaşıyor. Onları
birbirinden ayıracak hiçbir filtre yok.

**Geçiş YÖNÜNÜ (oturdu mu kalktı mı) bulmanın tek temiz yolu Doppler
işareti** — o da temiz FAZ istiyor. ESP32'nin fazı CFO/zamanlama
kaymalarıyla bozuk (Bölüm 3.3'te ölçüldü). Ayrıca tek anten var, uzamsal
çözünürlük yok; 2.4 GHz'de yarım dalga boyu 6 cm, yani **"aynı nokta" radyo
için aynı nokta değil.**

#### Elenen yan hipotezler (bunlar da kapandı)

- **"Kişi hatta yeterince bağlı değil" (benim hipotezim) — YANLIŞ.** Bağlanma
  testi (`data/posture_v2/coupling_test`) çürüttü: yürüme enerji oranı
  **1.78x / 3.35x**, yani kişi hatta gayet net görünüyor. Doğru teşhis:
  yürüme >> kol sallama >> otur/kalk geçişi. Sorun bağlantı değil, otur/kalk
  hareketinin kendisinin küçüklüğü.
- **"Kullanıcı komutları zamanında yapmıyor" — YANLIŞ.** Zamanlama denetimi
  yapıldı: iki kartta da **0/20** statik pencerede kirlilik. Protokol
  uygulaması temizdi, kabahat kullanıcıda değildi.
- **"Yavaş hareket edersek bozulma görünür hale gelir" — kısmen doğru ama
  yetmedi.** Yavaş kalkma/oturma zirveyi büyüttü (yöntem 6'nın ilk %100'ü
  buradan geldi) ama tekrarlanabilirlik gelmedi.
- **Kart yüksekliği 115 cm — işe yaramadı.** `probe_geometry.py` ile ölçüldü:
  ayrım gücü Cohen **d = 0.45 / 0.88** (karar eşiği d ≥ 1.5 idi). Ama dikkat:
  **bu yükseklik hipotezi ÇÜRÜTMEZ** — 115 cm oturan kişinin baş
  hizasının ALTINDA ve kişi masa yüzünden hattan sapmıştı. Gerçek test
  (~145-155 cm, sandalyenin iki yanında ~1.5 m) **hâlâ yapılmadı.**

#### ⚠️ ÇOK ÖNEMLİ METODOLOJİK BULGU: sabit faz süresi = sahte başarı

`h115` kaydında geçiş zirvesinin gecikmesi ölçüldü: **"otur" komutunda
0.15-0.25 sn sonra, "ayakta" komutunda 2.5-3.75 sn sonra.** Muhteşem bir
ayrım gibi görünüyordu. Gerçekte bu **fizik değil TEPKİ SÜRESİ** farkıydı —
faz süreleri sabit olduğu için kişi bir sonraki komutun ne zaman geleceğini
öğrenip hazırlanıyordu.

Faz sürelerine rastgelelik (`--jitter`) eklenince **bu ayrım tamamen
buharlaştı.** Yani jitter eklenmeseydi eğitim verisinde mükemmel çalışan,
gerçek hayatta çöken bir "çözüm" bulmuş olacaktık.

➡️ **Kural: geçiş verisi toplanırken `--jitter` ZORUNLU.**

#### Bu dosya nasıl yeniden açılır

Şu an denenmemiş **tek** kaldıraç: kartları **~145-155 cm**'e (oturan kişinin
baş hizasının ÜSTÜ, ayaktaki gövdenin İÇİ) ve sandalyenin iki yanına ~1.5 m
mesafeye almak. O geometride ilk Fresnel bölgesi ~±22 cm'e daralıyor ve
engelleme neredeyse ikili (var/yok) hale geliyor.
**Karar kapısı:** `probe_geometry.py` ile ölçülen Cohen d **≥ 1.5** çıkmazsa
bu dosya bir daha açılmasın. Detaylı protokol:
`docs/OTUR_AYAKTA_VERI_TOPLAMA_PLANI.md`.

---

## 4. HANGİ ÖZELLİK ORTAM DEĞİŞİNCE BOZULUR? (kritik tablo)

| Özellik | Yöntem | Ortam değişince | Neden |
|---|---|---|---|
| Nefes | Bandpass filtre (frekans) | ✅ Bozulmaz | Frekans ölçüyor; 0.25 Hz her odada 0.25 Hz |
| Kalp atışı | Bandpass filtre (frekans) | ✅ Bozulmaz | Aynı |
| Hareket var/yok | Enerji (ardışık fark) | ✅ Bozulmaz | Kendi geçmişiyle kıyaslıyor |
| **Oturma/ayakta** | **ML (mutlak desen)** | ❌ **Bozulur** | Donmuş sinyalin şeklini ezberliyor, o şekil odaya özgü |
| ~~Oturma/ayakta~~ | ~~ML (dinamik/postural sway)~~ | — | ❌ 2026-08-24: hiç çalışmıyor (%39.6, p=0.92). Bkz. Bölüm 5.1 |
| ~~Oturma/ayakta~~ | ~~diğer 4 yöntem~~ | — | ⛔ 2026-08-25: **DOSYA KAPANDI**, altı yöntem de tekrarda çöktü. Bkz. Bölüm 3.9 |
| **Yürüme var/yok** | **ML — ölçekten bağımsız spektral özellikler** | ✅ Bozulmaz | Mutlak genlik değil spektrumun ŞEKLİ; Leave-One-Session-Out %92.9 |

**Genel kural:** *Değişimi* ölçen yöntemler ortamdan bağımsız, *mutlak deseni* ezberleyen yöntemler ortama bağımlı.

⚠️ **2026-08-24 istisnası:** Bu kural "dinamik olan her şey çalışır" anlamına GELMİYOR.
Dinamik özellikler ancak ölçtükleri fark gerçekten varsa işe yarar. Hareket enerjisi
çalışıyor çünkü hareket gerçek ve büyük; postural sway çalışmadı çünkü bu donanımda
(1 anten, 2.4 GHz) o kadar ince bir salınım ölçülemiyor.

---

## 5. SIRADAKİ PLAN — ⚠️ TARİHSEL (2026-08-19/24)

> **Bu bölüm artık yol göstermiyor, kayıt amaçlı duruyor.** Aşağıdaki
> "kalibrasyon stratejileri" otur/ayakta ayrımını kurtarmak içindi; o dosya
> 2026-08-25'te kapandı (Bölüm 3.9) ve canlı sistemde kalibrasyon tamamen
> kaldırıldı. **Güncel durum ve sıradaki adım için Bölüm 0'ın en üstüne
> ve Bölüm 8'e bak.**

**Güncelleme (2026-08-24):** 2. ESP32 AP mimarisi kuruldu ve doğrulandı (Bölüm 0),
82-101 Hz native hız alınıyor. Aşağıdaki "145 Hz" referansları hotspot-flood
döneminden kalma ama sonuç aynı ölçekte (80-150 Hz bandı). **Fizibilite testi
YAPILDI — sonuçlar Bölüm 5.1'de.** Özet: postural sway çürüdü, mutlak desen sadece
kesintisiz oturum içinde çalışıyor (%70.5, p=0.032), hareket tespiti sağlam (2.44x).

### ✅ Fizibilite testi YAPILDI (2026-08-24) — sonuçlar aşağıda (Bölüm 5.1)

### ❌ Postural sway (dinamik ayrım) — TEST EDİLDİ, ÇÜRÜDÜ
**Hipotez neydi:** Ayakta duran insan dengede kalmak için sürekli minik düzeltmeler
yapar (postural sway); oturan insan daha kararlıdır. Bu *dinamik* bir fark olduğu
için Bölüm 4'teki kurala göre ortamdan bağımsız olmalıydı.

**Sonuç: hipotez YANLIŞ.** Dinamik özellikler (ardışık paket farklarının
mean/std/abs-mean'i) her testte şans seviyesinin ALTINDA kaldı:
| Test | Postural sway | Mutlak desen |
|---|---|---|
| Ayrı kayıtlar (resetli), 10 grup | %45.9 | %52.9 |
| guided_01 (kesintisiz), 12 faz | %64.6 | %66.7 |
| guided_02 (kesintisiz), 12 faz | %44.4 | %80.6 |
| **guided_01+02 birleşik, 24 faz** | **%39.6** (9/24, p=0.92) | **%70.5** (17/24, p=0.032) |

Bu fikri tekrar denemeye gerek yok - 24 bağımsız faz grubuyla test edildi,
binom testi p=0.92 (yani tamamen rastgele). **Kapandı.**

### Kalibrasyon stratejileri (dinamik yöntem tutmadı → bunlar tek yol)
- **A) Hızlı kalibrasyon rutini:** ~90 Hz'de 20 sn = ~1800 paket = yüzlerce pencere.
  "20 sn otur → 20 sn ayakta dur → otomatik eğit" = **toplam ~1 dakika**.
  ⚠️ 2026-08-24 bulgusuna göre kalibrasyon ile kullanım **aynı kesintisiz bağlantıda**
  olmalı (arada reset/yeniden bağlanma olmamalı) - bkz. Bölüm 5.1.
- **B) Konum kütüphanesi:** Her ortam için bir kez kalibre et (`model_ofis.joblib`,
  `model_ev.joblib`), o ortama dönünce yükle. ⚠️ Aynı reset kısıtı burada da geçerli,
  bu yüzden B seçeneği pratikte çalışmayabilir.

---

## 5.1 FİZİBİLİTE TESTİ SONUÇLARI (2026-08-24, 2 ESP32 AP mimarisi)

### Ne yapıldı
1. Ayrı ayrı 19 kayıt (5 otur, 5 ayakta, 3 ani-otur, 3 ani-kalk, 3 yürüme), her biri
   `--reset` ile → `data/own_activity_*.csv`
2. Tek kesintisiz 90 sn kayıt, kullanıcının kendi kronometresiyle → **başarısız**,
   etiketler veriyle hizalanmadı (hareket zirveleri faz sınırlarına düşmedi)
3. `guided_capture.py` yazıldı: macOS `say` ile sesli komut + komut anındaki ESP zaman
   damgası kaydediliyor → senkron hatası fiziksel olarak imkansız
4. guided_01 (12 faz × 12 sn), motion_check_01 (hareket duyarlılığı), guided_02
   (12 faz × 10 sn, belirgin geçişlerle) → `data/continuous_session/`

### Sonuç 1: Hareket tespiti ÇALIŞIYOR (sağlam)
`motion_check_01` (kıpırdama vs kollarını salla, 6 faz):
```
KIPIRDAMA      : 1.36        KOLLARINI SALLA: 3.32        ORAN: 2.44x
faz faz: 1.26 / 1.98 / 1.24 / 3.80 / 1.58 / 4.19  (temiz ayrışıyor)
```
Zirveler tam komut anında başlıyor → hem hareket tespiti hem de sesli yönlendirme
mekanizması doğrulandı.

### Sonuç 2: Otur/ayakta — zayıf ama GERÇEK sinyal, sadece kesintisiz oturumda
| Koşul | Doğruluk | Anlamlılık |
|---|---|---|
| Ayrı kayıtlar (her biri resetli), 10 grup | %52.9 | şans seviyesi |
| Kesintisiz oturum, 24 faz grubu | **%70.5** | 17/24, **binom p=0.032** |

**Yorum:** Reset/yeniden bağlanma, kayıtlar arası karşılaştırmayı yok ediyor. Aynı
kesintisiz bağlantı içinde ise gerçek (ama mütevazı) bir sinyal var. Fold başına
sapma hâlâ yüksek (±%32.5), yani tek bir 2 sn'lik pencereye güvenilmez - çoklu
pencere oylaması gerekir.

### Sonuç 3: Geometri sorunu (açık konu)
Kartlar masa seviyesinde ve kişi tam aralarında dururken, **gövde her iki duruşta da
doğrudan hattı aynı şekilde kesiyor** → otur/ayakta farkı fizik olarak zayıf kalıyor.
Kanıt: kol sallamak net görünüyor (2.44x) ama otur/ayakta geçişlerinin çoğu hiç
görünmüyor (guided_02'de 12 fazın sadece 2'sinde geçiş zirvesi var; buna karşılık
bazı geçişler 8.05 gibi devasa değerler üretiyor - yani tutarsız).

**Önerilen çözüm — 2026-08-25 durumu:** ~1 m'e (sandalye kafalığı) ve 115 cm'e
(`probe_geometry.py`) kaldırıldı, **ikisi de yetmedi** (d=0.45/0.88). Asıl hipotez
olan ~145-155 cm hâlâ TEST EDİLMEDİ — bkz. Bölüm 3.9. Fikir şuydu: kartları ayaktayken
göğüs hizasına (~140-150 cm) kaldırmak. O yükseklikte ayaktayken hat kesilir,
otururken baş o seviyenin altında kalır → fizik olarak zorunlu büyük fark.

### Sonuç 4: Kişinin konumu — ölçüldü (2026-08-24 akşam)
İki pozisyon aynı protokolle (otur/ayakta/yürü, sesli kalibrasyon) karşılaştırıldı:

| Kişinin yeri | hareketsiz enerji | yürüme enerjisi | otur/ayakta |
|---|---|---|---|
| Kartların **tam arasında** (sağ/sol) | 2.83 | 2.43 ⟵ **TERS** | %70.0 |
| Kartların **ön çaprazında**, geride | 1.80 | 1.86 ⟵ doğru yön | **%73.8** |

**Bulgu:** Tam arada dururken vücut doğrudan hattı derinden kesiyor; kişi uzaklaşınca
yol temizlenip sinyal SAKİNLEŞİYOR → "hareket = daha çok dalgalanma" varsayımı
tersine dönüyor ve hareket kapısı çalışmıyor. Ön çaprazda durunca kişi hattı kesmek
yerine bozuyor (saçıcı gibi davranıyor) → yön düzeliyor. **Ön çapraz pozisyon tercih
edilmeli.** Ama fark hâlâ çok küçük (%3), yürüme tespiti için yetersiz.

**Asıl darboğaz: algılama hacmi.** İki kart masada ~1 m arayla duruyor, kişi yürürken
zamanının çoğunu bu küçük bölgenin dışında geçiriyor. Board B (AP) sadece GÜCE
ihtiyaç duyuyor (veri bağlantısı gerekmiyor) - herhangi bir USB telefon şarj
adaptörü/powerbank ile odanın öbür ucuna konabilir. **Bu, denenmemiş en yüksek
getirili değişiklik.**

### Alt-taşıyıcı maskeleme (2026-08-24, kod düzeltmesi)
64 alt-taşıyıcının 12'si bilgi taşımıyor: index 0 sabit 146 (başlık değeri),
1-5 ve 59-63 kenar guard bandı, 32 DC. Bunlar hareket enerjisi ortalamasını
sulandırıyordu (aynı veri: tümü=1.46, sadece geçerliler=1.76). `activity_features.py`
içinde `VALID_SUBCARRIERS` ile maskelendi. ⚠️ Bu, özellik vektörünün boyutunu
değiştirir - bu değişiklikten ÖNCE eğitilmiş modeller uyumsuzdur, yeniden
kalibre edilmeli.

### Veri kalitesi notu (kontrol edildi, sorun yok)
guided_02'de paket aralığı medyan 10.0 ms (~100 Hz), 0.2 sn üstü tek bir boşluk
(220 ms), saniye başına 55-118 paket. Seri hat ~%72 doluluk. **Veri kaybı yok** -
yukarıdaki başarısızlıklar ölçüm kaynaklı değil, fiziksel.

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
| ESP32 5GHz ağa bağlanamıyor (`reason=201`, NO_AP_FOUND) | Klasik ESP32 (D0WD-V3) donanımsal olarak SADECE 2.4GHz destekliyor | Çözümü yok — ağın 2.4GHz SSID'sini kullan (ofis ağı 5GHz-only ise o ağ tamamen kapalı, MAC spoof bile kurtarmaz) |
| ESP'nin kendi flood'u (`socket_transmitter_sta_loop`, STA→gateway) CSI hızını artırmıyor | CSI ALINAN çerçevelerden üretilir, GÖNDERİLENDEN değil — ESP kendi gönderdiği paketten CSI çıkaramaz | Laptoptan ESP'nin IP'sine paket gönder (`packet_flooder.py` veya `csi_udp_server.py`'nin dahili flood'u) |
| **`csi_udp_server.py` "0 kart" buluyor ama kartlar hotspot'a bağlı** | macOS, bilinen bir ağı (ör. kurumsal WiFi) telefon hotspot'undan önceliklendirip laptobu SESSİZCE ona geçiriyor — laptop ve kartlar farklı ağda kalıyor | `ipconfig getifaddr en0` ile laptobun GERÇEK IP'sini kontrol et; ESP'lerin aldığı IP ile aynı /28 alt ağda değilse laptobu elle hotspot'a geri bağla |
| **Canlı sistem hiçbir şey algılamıyor, ibre hiç kıpırdamıyor** | Tek seferlik kalibrasyon, kalibrasyon anı sakin değilse tabanı şişiriyor (ölçüldü: taban **1.49**, gerçek değerler 0.56-0.98 → geçiş eşiği 1.31, gerçek geçişler 0.29-0.77 → HEPSİ reddedildi) | Tek seferlik kalibrasyona GÜVENME. Eşikler sürekli güncellenen yüzdeliklerden gelmeli (`ADAPT_WINDOW`), karar eğitilmiş modelden. `live_server_udp.py`'de artık kalibrasyon YOK |
| **Sabit faz süresiyle toplanan geçiş verisi sahte "çözüm" üretiyor** | Kişi bir sonraki komutun ne zaman geleceğini öğrenip hazırlanıyor; zirve gecikmesi FİZİK değil TEPKİ SÜRESİ farkı oluyor (ölçüldü: "otur" 0.15-0.25 sn, "ayakta" 2.5-3.75 sn — jitter eklenince ayrım BUHARLAŞTI) | `guided_capture_udp.py --jitter 3 --seed N` kullan. Geçiş verisinde zorunlu |
| **`mv own_activity_*.csv ...` hiçbir şey taşımadı, hata da vermedi** | zsh, tırnaksız değişkeni kelimelere BÖLMEZ (bash'ten farklı): `pat="*.csv"; mv $pat hedef/` glob'u genişletmez | Glob'u komutta DOĞRUDAN yaz (`mv own_activity_*.csv hedef/`), değişkene koyma. Taşımadan sonra `ls` ile SAY, çıktıya güvenme |
| **`python3 -c "..."` içinde Türkçe metin: "character not in range" / JSON decode hatası** | zsh tırnak içi Unicode + kabuk kaçışları çakışıyor | `<<'PY' ... PY` heredoc kullan ve çıktıyı ASCII tut |
| **STA-85b0 aniden 2-70 Hz'e düşüp sonra kendiliğinden düzeliyor** | Hotspot bant paylaşımı + RSSI eşiğe dayanıyor (düşüş anında **−69.1/−63.2 dBm**, sağlıklıyken −57.9/−57.5; belgeli arıza eşiği −70 dBm) | Kayıt öncesi `csi_udp_server.py --duration 15` ile hızı DOĞRULA. Düşükse kartı hotspot'a yaklaştır. Düşük hızlı kayıtla eğitme |

---

## 7. DOSYA HARİTASI

⚠️ **2026-08-25'te yeniden düzenlendi.** Kullanılmayan scriptler ve veriler
ayrı klasörlere TAŞINDI (silinmedi). Aşağıdaki harita taşımadan SONRAKİ
gerçek durumdur.

```
analysis/                          # ── AKTİF: 9 script ─────────────────
  live_view_udp.py               # ⭐ GÖSTERİM arayüzü (Flask :5051) - insan figürlü sahne
  live_server_udp.py             # ⭐ B PLANI: sade canlı gösterge (Flask :5050)
  train_walking_model.py         # ⭐ Yürüme modelini eğitir + Leave-One-Session-Out doğrular
  activity_features.py           # Ortak: CSV parse (regex), hareket enerjisi, walking_features()
  bpm_pipeline.py                # Bandpass + zero-crossing/FFT BPM tahmini
  csi_udp_server.py              # İki karttan UDP ile CSI toplar + besleme (flood) paketi gönderir
  guided_capture_udp.py          # Sesli yönlendirmeli etiketli veri toplama
  evaluate_udp_session.py        # Kaydedilen oturumu değerlendirir
  probe_geometry.py              # Kart yüksekliği tarama aracı (Cohen d ölçer)
  voice.py                       # speak() - sesli komut (eski guided_capture.py'den ayrıldı)
  models/walking_model.joblib    # ⭐ Canlı arayüzün kullandığı TEK model
  requirements.txt  venv/  plots/

  kullanilmayan_scriptler/       # ── PASİF (16 script + 2 ölü model) ──
    README.md                    # Her birinin ne olduğu + tekrar çalıştırma yolu
    esp_port.py  capture_csi.py  guided_capture.py  live_server.py
    evaluate_guided_session.py  evaluate_continuous_session.py
    evaluate_ap_feasibility.py  packet_flooder.py
    save_activity_model.py  train_own_activity_classifier.py  calibrate_live.py
    train_activity_classifier.py  evaluate_heart_rate_synthetic.py
    evaluate_breathing_own_data.py  evaluate_breathing_own_data_v2.py
    plot_breathing_signals.py
    models/activity_classifier.joblib  models/live_calibration.joblib

data/                            # ⚠️ TAMAMI .gitignore'da - GİT'TE YEDEĞİ YOK
  udp_session/                   # ⭐ AKTİF eğitim seti (75 M) - 4 oturum + README
  posture_v2/                    # ⭐ AKTİF eğitim seti (107 M) - 4 oturum
  kullanilmayan_veriler/         # PASİF ~3.1 G + README.md (neyin kaynağı olduğu yazılı)
    synthetic_vital_signs/  ut_har_activity/     # Kaggle setleri (yeniden indirmek mobil veri yakar)
    continuous_session/  own_activity_*.csv  own_breathing_*.csv
    archive_lowrate/  geometry_probe/  udp_verify_test3_*.csv
  README.md

firmware/ESP32-CSI-Tool/
  active_sta/main/main.cc        # ⭐ ÖZELLEŞTİRİLDİ: dinamik gateway IP + PMF + SPOOF_MAC
  active_sta/main/Kconfig.projbuild  # ÖZELLEŞTİRİLDİ: ikinci ağ, SEND_CSI_TO_UDP, SPOOF_MAC
  active_sta/sdkconfig.defaults        # Ayarlar (placeholder WiFi - git'e girer)
  active_sta/sdkconfig.defaults.local  # ⚠️ GERÇEK WiFi şifreleri - .gitignore'da
  active_sta/sdkconfig.defaults.local.apbak  # Eski AP mimarisi yedeği
  _components/csi_udp_component.h  # ⭐ CSI'yi UDP ile gönderir (kuyruk + ayrı görev)
  _components/csi_component.h      # UDP kuyruğuna yazar, role sütununu MAC'ten üretir
  _components/sockets_component.h  # ÖZELLEŞTİRİLDİ: sabit IP yerine target_ip

docs/
  PROJE_DURUM_VE_KARARLAR.md     # BU DOSYA
  PROJE_SUNUM.md                 # Sunum dokümanı
  OTUR_AYAKTA_VERI_TOPLAMA_PLANI.md  # ⭐ YENİ: yükseklik hipotezi + karar kapısı + protokol
  RuView_CSI_Proje_Plani.md      # Detaylı faz planı ve kronoloji
activate_idf.sh                  # ESP-IDF ortamını tek satırda açar
```

---

## 8. AÇIK KONULAR

### 🎯 Sıradaki adım (2026-08-25 itibarıyla)

**Sistem şu an gösterilebilir durumda:** canlı arayüz açılıyor, yürümeyi
%92.9 doğrulukla tanıyor, nefes gösteriyor, kalibrasyon istemiyor. Final
demo bu haliyle yapılabilir — tek uyarı, oturuyor/ayakta göstergesinin
ÖLÇÜLMEDİĞİ, takip edildiği ve kayabileceği.

Seçenekler (kullanıcı/yönetici kararı):

| Seçenek | İş | Getiri |
|---|---|---|
| **A) Olduğu gibi teslim** | yok | Yürüme + nefes sağlam ve dürüstçe doğrulanmış |
| **B) Yükseklik denemesi** | kartları ~145-155 cm'e, sandalyenin iki yanına ~1.5 m; `probe_geometry.py` ile Cohen d ölç | Otur/ayakta açılabilir. **Karar kapısı: d < 1.5 ise vazgeç** (Bölüm 3.9) |
| **C) Yürüme modelini güçlendir** | daha çok oturum/konumla yeniden eğit | %92.9 → daha kararlı; en düşük oturum %70 (hareket_teshis) |

⚠️ **Hangisi seçilirse seçilsin geçerli kural:** duruş sınıflandırmasıyla
ilgili HİÇBİR sonuca, konum-değişken protokolle ve Leave-One-Session/Position-Out
ile doğrulanmadan güvenilmeyecek. Bu projenin en pahalı dersi buydu.

### Eski açık konular

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
