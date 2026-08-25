# Kullanılmayan scriptler (2026-08-25'te buraya taşındı)

**Hiçbiri silinmedi.** Projenin şu anki halinde çalıştırılmıyorlar ve aktif
hiçbir script bunları import etmiyor (doğrulandı).

İki sebepten kullanım dışılar:

1. **Mimari değişti** — 2026-08-24 akşamı tek kart + USB seri porttan,
   iki kart + telefon hotspot + UDP mimarisine geçildi. Seri porttan okuyan
   her şey karşılıksız kaldı.
2. **Otur/ayakta sınıflandırması kapandı** — bu donanımda altı ayrı yöntem
   denendi, hepsi tekrarda çöktü (bkz. `docs/PROJE_DURUM_VE_KARARLAR.md`).
   O sınıflandırmayı eğiten/kullanan scriptler de kapandı.

---

## Aktif kalan (kıyas için)

| Script | Ne yapıyor |
|---|---|
| `live_server_udp.py` | Canlı arayüz — eğitilmiş modelle yürüme tespiti + nefes/nabız |
| `train_walking_model.py` | Yürüme modelini eğitir, Leave-One-Session-Out doğrular |
| `activity_features.py` | Ortak: CSV ayrıştırma, hareket enerjisi, `walking_features()` |
| `bpm_pipeline.py` | Nefes/nabız frekans kestirimi |
| `csi_udp_server.py` | İki karttan UDP ile CSI toplar + besleme paketleri gönderir |
| `guided_capture_udp.py` | Sesli yönlendirmeli etiketli veri toplama |
| `evaluate_udp_session.py` | Toplanan oturumu değerlendirir |
| `probe_geometry.py` | Kart yüksekliği tarama aracı |
| `voice.py` | `speak()` — sesli komut (eskiden `guided_capture.py` içindeydi) |

---

## Taşınanlar

### Seri port / tek kart dönemi (mimari değişti)

| Script | Neydi | Yerini alan |
|---|---|---|
| `esp_port.py` | Hangi `/dev/cu.usbserial-X` hangi kart, MAC'ten bulurdu | — (USB yok artık) |
| `capture_csi.py` | Seri porttan veri toplama | `csi_udp_server.py` |
| `guided_capture.py` | Sesli yönlendirmeli kayıt, seri port + ESP saati | `guided_capture_udp.py` |
| `live_server.py` | Canlı gösterge, tek kart, seri port | `live_server_udp.py` |
| `evaluate_guided_session.py` | Eski guided kayıtları (ESP saatiyle) değerlendirirdi | `evaluate_udp_session.py` |
| `evaluate_continuous_session.py` | `continuous_session/` kayıtlarını değerlendirirdi | — |
| `evaluate_ap_feasibility.py` | 2. ESP'nin AP olduğu mimarinin fizibilitesi | — (o mimari terk edildi) |

⚠️ `packet_flooder.py` — Bağımsız UDP flood aracı. Örnekleme hızını 9.5 ->
145 Hz'e çıkaran şeydi (projenin en büyük tek kazanımı). Artık işlevi
`csi_udp_server.py`'nin içinde. **Tek kart senaryosuna dönülürse yine işe
yarar** - o yüzden silinmedi.

### Otur/ayakta sınıflandırması (yöntem kapandı)

| Script | Neydi |
|---|---|
| `save_activity_model.py` | Duruş modelini eğitip kaydederdi |
| `train_own_activity_classifier.py` | Kendi verimizle LOO değerlendirme (Bölüm 3.5, %77.8) |
| `calibrate_live.py` | Canlı sistemde duruş modelini kalibre ederdi |
| `models/activity_classifier.joblib` | Eğitilmiş duruş modeli |
| `models/live_calibration.joblib` | Canlı kalibrasyon modeli |

İki modelin de **iki ayrı sebepten** kullanılamaz olduğuna dikkat: (a) duruş
sınıflandırması bu donanımda çalışmıyor, (b) `VALID_SUBCARRIERS` maskesi
eklendiğinde özellik vektörünün boyutu değişti, yani o modeller yeni veriyle
boyut uyumsuzluğu verir.

### Dış veri setiyle çalışanlar

| Script | Neydi |
|---|---|
| `train_activity_classifier.py` | UT-HAR ile eğitim (VAL %97.8, TEST %95.2). Intel 5300 donanımı, 3 anten - model bize aktarılamıyordu, sadece YÖNTEM doğrulamasıydı. |
| `evaluate_heart_rate_synthetic.py` | Sentetik veriyle kalp atışı yöntem karşılaştırması (Bölüm 3.1) |

### Nefes değerlendirmesi

| Script | Neydi |
|---|---|
| `evaluate_breathing_own_data.py` | Kendi 3 kaydımızla nefes doğrulama (yavaş 15 BPM -> 15.99) |
| `evaluate_breathing_own_data_v2.py` | Faz/otokorelasyon denemesi (başarısız, kayıt amaçlı) |
| `plot_breathing_signals.py` | Nefes sinyali görselleştirme |

Not: canlı arayüz nefes göstermeye **devam ediyor** (`bpm_pipeline.py` aktif).
Taşınanlar sadece o yöntemi *değerlendiren* araçlar.

---

## Bunları tekrar çalıştırmak gerekirse

İki şeyi birden düzeltmek gerekiyor - hem scriptler hem verileri taşındı:

1. **Script yolu:** bu klasörden çalıştırılırsa `analysis/`'teki ortak
   modülleri (`activity_features`, `bpm_pipeline`) bulamaz.
   `PYTHONPATH=../ python3 <script>.py` ile çalıştır.
2. **Veri yolu:** içlerindeki `../data/<x>` yolları artık
   `../../data/kullanilmayan_veriler/<x>` olmalı.
   Detay: `data/kullanilmayan_veriler/README.md`
