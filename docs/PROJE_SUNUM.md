# WiFi Sinyalleriyle Kamerasız İnsan Algılama
### Proje Tanıtımı, Süreç ve Bulgular

**Hazırlayan:** Ahmet Furkan Yorulmaz
**Tarih:** 19 Ağustos 2026
**İlham kaynağı:** [RuView](https://github.com/ruvnet/RuView)
**Depo:** `wifi-csi-vital-signs`

---

## 1. Proje Nedir, Ne İşe Yarar?

Bu proje, **hiçbir kamera veya giyilebilir sensör kullanmadan**, yalnızca ortamdaki WiFi sinyallerini analiz ederek bir insanın:

- **nefes alma hızını**,
- **kalp atış hızını**,
- **hareketlerini** (oturma, ayakta durma, ani hareket)

tespit etmeyi amaçlar.

### Kullanım Alanları

| Alan | Örnek Senaryo |
|---|---|
| Yaşlı bakımı | Evde yalnız yaşayan bireyin düşmesini tespit etme |
| Sağlık takibi | Uyku sırasında solunum izleme (temassız) |
| Güvenlik | Odada kişi var mı tespiti (karanlıkta, duvar arkasında) |
| Mahremiyet | Kamera koyulamayacak alanlarda (banyo, yatak odası) izleme |

**Ana avantajı:** Kamera görüntüsü kaydetmediği için mahremiyeti korur; karanlıkta ve belirli koşullarda duvar arkasında bile çalışabilir.

---

## 2. Temel Çalışma Prensibi

### 2.1 CSI Nedir?

**CSI (Channel State Information — Kanal Durum Bilgisi)**, bir WiFi sinyalinin vericiden alıcıya giderken uğradığı değişimin ayrıntılı ölçümüdür.

WiFi sinyali tek bir frekans değil, **alt-taşıyıcı (subcarrier)** adı verilen onlarca farklı frekans bandından oluşur. CSI, bu alt-taşıyıcıların her biri için ayrı ayrı:

- **Genlik (amplitude):** Sinyal ne kadar zayıfladı?
- **Faz (phase):** Sinyal ne kadar geciktir/kaydı?

bilgisini verir.

### 2.2 İnsan Vücudu Sinyali Nasıl Etkiler?

```
[WiFi Router] ~~~~~~~~~~~~~> [ESP32 Alıcı]
                  ↑
            (İnsan vücudu sinyali
             yansıtır, emer, kırar)
```

- Vücut hareket ettiğinde sinyalin yansıma yolları değişir → CSI değerleri değişir
- **Nefes alırken göğüs kafesi milimetrik hareket eder** → CSI'da çok küçük ama **düzenli/periyodik** bir dalgalanma oluşur
- **Kalp atışı** daha da küçük ama daha hızlı bir periyodik dalgalanma yaratır

### 2.3 Sinyalden Bilgiye: İşlem Hattı (Pipeline)

```
ESP32 → Ham CSI verisi → Ön işleme → Bant filtreleme → Analiz → Sonuç
```

**Vital bulgular için (sinyal işleme yaklaşımı):**

1. Ham CSI genlik değerleri zaman serisine dönüştürülür
2. Paketler düzensiz aralıklarla geldiği için **düzgün zaman ızgarasına yeniden örneklenir** (interpolasyon)
3. **Bant geçiren filtre (bandpass)** ile sadece ilgilenilen frekans aralığı bırakılır:
   - **Nefes:** 0.1–0.5 Hz → dakikada 6–30 nefes
   - **Kalp atışı:** 0.8–2.0 Hz → dakikada 48–120 atış
4. Filtrelenmiş sinyalin periyodu ölçülür:
   - **Sıfır geçiş (zero-crossing) sayımı:** Sinyal kaç kez sıfır çizgisini kesti?
   - **FFT tepe frekansı:** Frekans spektrumunda en güçlü bileşen hangisi?
5. Frekans → dakikadaki atış/nefes sayısına (BPM) çevrilir

**Hareket/aktivite için (makine öğrenmesi yaklaşımı):**

1. Belirli bir zaman penceresindeki (örn. 2 saniye) CSI verisi alınır
2. Her alt-taşıyıcı için **özet istatistikler** çıkarılır: ortalama, standart sapma, minimum, maksimum
3. Bu özellik vektörü, önceden eğitilmiş bir **Random Forest** sınıflandırıcısına verilir
4. Model, "bu örüntü en çok hangi aktiviteye benziyor?" sorusunu cevaplar

---

## 3. Kullanılan Teknolojiler

### Donanım
| Bileşen | Detay |
|---|---|
| **ESP32-D0WD-V3** (DevKitV1 kartı) | Klasik ESP32, çift çekirdek Xtensa LX6, 240 MHz, **tek anten**, sadece 2.4 GHz |
| USB-Seri bağlantı | CP2102/CH340, 921600 baud |
| WiFi Erişim Noktası | Telefon hotspot / ev modemi (2.4 GHz) |

### Firmware (Gömülü Yazılım)
| Teknoloji | Kullanım Amacı |
|---|---|
| **ESP-IDF v4.3** | Espressif'in resmi geliştirme çerçevesi, firmware derleme |
| **[ESP32-CSI-Tool](https://github.com/StevenMHernandez/ESP32-CSI-Tool)** | CSI verisi çıkaran açık kaynak firmware (Steven M. Hernandez) — `active_sta` modu |
| **C / C++** | Firmware özelleştirmeleri (çift ağ desteği, dinamik hedef IP) |
| CMake | Derleme sistemi |

### Analiz ve Yazılım
| Teknoloji | Kullanım Amacı |
|---|---|
| **Python 3.12** | Ana analiz dili |
| **NumPy** | Sayısal işlemler, matris hesaplamaları |
| **SciPy** | Sinyal işleme (Butterworth bandpass filtre, interpolasyon) |
| **scikit-learn** | Makine öğrenmesi (Random Forest, Leave-One-Out doğrulama) |
| **Pandas** | Veri işleme |
| **Matplotlib** | Sinyal görselleştirme, grafik üretimi |
| **PySerial** | ESP32 ile seri port haberleşmesi |
| **PyArrow** | Büyük Parquet dosyalarını bellek dostu okuma |
| **Flask** | Canlı web arayüzü sunucusu |
| **Joblib** | Eğitilmiş modeli diske kaydetme |
| **Git / GitHub** | Sürüm kontrolü |

---

## 4. Kullanılan Veri Setleri

### 4.1 Seçilen ve Kullanılan Veri Setleri

| Veri Seti | Kaynak | İçerik | Kullanım Amacı |
|---|---|---|---|
| **Synthetic WiFi CSI Data for Human Activity & Vital** | Kaggle: `saur3x/wifi-sensing` | 17.28 milyon satır, sentetik, 15 alt-taşıyıcı genlik+faz, **`heart_rate_bpm` etiketli** | Kalp atışı algoritmasının doğrulanması ve yöntem karşılaştırması |
| **UT-HAR** | Kaggle: `hylanj/wifi-csi-dataset-ut-har` (orijinal kaynak: Stanford Ermon Group) | Gerçek veri, Intel 5300 NIC, 90 özellik (30 alt-taşıyıcı × 3 anten), **7 aktivite sınıfı**: yatma, düşme, eşya alma, koşma, oturma, ayağa kalkma, yürüme. 3977 eğitim / 496 doğrulama / 500 test | Aktivite sınıflandırma yönteminin doğrulanması |
| **Kendi topladığımız veri** | ESP32 + ESP32-CSI-Tool | Nefes kayıtları (3 tempo), aktivite kayıtları (oturma/ayakta/ani hareket) | Gerçek donanımda doğrulama |

### 4.2 İncelenen Ama Kullanılmayan Veri Setleri

| Veri Seti | Neden Kullanılmadı |
|---|---|
| **CSI-Bench** (`guozhenjennzhu/csi-bench`) | 81 GB — indirilemeyecek kadar büyük. Ayrıca nefes etiketi sadece ikili (var/yok), sayısal BPM değil; kalp atışı hiç yok |
| **WiFi CSI HAR** (`alanwake12/...`) | İndirildi ancak içinde **hiç etiket bulunmadığı** tespit edildi (sadece ham sinyal dizileri) |
| **IEEE DataPort Multi-Human HAR** | ESP32-Nodemcu + ESP32-CSI-Toolkit ile toplanmış (tam bizim donanımımız) ancak **abonelik gerektiriyor** |
| **Wi-ESP** | Veri seti henüz yayınlanmamış ("Coming Soon") |
| **MM-Fi / Wi-Pose** (poz tahmini) | RuView'in hazır modeli 3 anten × 114 alt-taşıyıcı × 100 Hz gerektiriyor; donanımımızla uyumsuz |

---

## 5. Yapılan Çalışmalar (Kronolojik)

### Aşama 1 — Donanım Tespiti ve Ortam Kurulumu
- ESP32 kartın gerçek modeli `esptool` ile silikon üzerinden doğrulandı: **ESP32-D0WD-V3**
- Flash belleği tamamen silindi (temiz başlangıç)
- ESP-IDF v4.3 kuruldu, ESP32-CSI-Tool derlenip karta yüklendi
- Proje GitHub deposuna taşındı, sürüm kontrolü kuruldu

### Aşama 2 — Firmware Özelleştirmeleri
- **Çift ağ desteği eklendi:** İş yeri ve ev ağı arasında otomatik geçiş (5 başarısız denemeden sonra diğerine geçer)
- **Güvenlik:** Gerçek WiFi şifreleri `.gitignore`'daki ayrı bir dosyada tutuluyor, depoya asla girmiyor
- **Kritik hata düzeltmesi:** Hedef IP dinamik hale getirildi (detay: Bölüm 6.3)

### Aşama 3 — Veri Toplama Altyapısı
- `capture_csi.py`: CSI verisini CSV'ye kaydeden araç geliştirildi
- Gerçek CSI verisi akışı doğrulandı

### Aşama 4 — Vital Bulgu Analizi
- `bpm_pipeline.py`: Bandpass filtre + zero-crossing/FFT tabanlı BPM tahmin modülü
- Sentetik veri setiyle üç yöntem karşılaştırıldı (genlik / faz / PCA)
- Kendi nefes verimiz 3 farklı tempoda toplanıp test edildi
- `plot_breathing_signals.py`: Sinyal görselleştirme

### Aşama 5 — Aktivite Sınıflandırma
- UT-HAR veri setiyle Random Forest sınıflandırıcı eğitildi ve doğrulandı
- Kendi aktivite verimiz toplandı (oturma / ayakta / ani hareket)
- Kendi verimizle model eğitildi

### Aşama 6 — Canlı Sistem
- `live_server.py`: ESP32'den sürekli okuyup gerçek zamanlı tahmin üreten Flask sunucusu
- Web arayüzü: Anlık aktivite + kalp atışı göstergesi
- İki aşamalı mimari: hareket kapısı → duruş modeli → güven eşiği

---

## 6. Karşılaşılan Zorluklar, Sebepleri ve Çözümleri

### 6.1 Donanım Uyumsuzluğu: RuView Çalışmıyor

**Sorun:** Projenin ilham kaynağı olan RuView'in kendi firmware'i elimizdeki kartta çalışmıyor.

**Sebep:** RuView yalnızca **ESP32-S3 / ESP32-C6** modellerini destekliyor. Bu modeller PSRAM ve daha güçlü LX7 çekirdeğine sahip; RuView'in çoklu-bant birleştirme ve poz tahmini algoritmaları bunları gerektiriyor. Elimizdeki kart klasik ESP32 (LX6, PSRAM yok).

**Çözüm:** RuView'in kendi kodu yerine, klasik ESP32'de kanıtlanmış şekilde çalışan **ESP32-CSI-Tool** kullanıldı. RuView'in **dokümante ettiği algoritmalar** (frekans bantları, filtreleme yaklaşımı) referans alınarak kendi işlem hattımız yazıldı.

> **Not:** Bu, "RuView'i çalıştırdık" değil, "RuView'den ilham alan kendi implementasyonumuzu yaptık" demektir. Akademik dürüstlük açısından bu ayrım önemlidir.

---

### 6.2 ESP-IDF Kurulum Sorunları (6 Ayrı Sorun)

**Sorun:** ESP-IDF v4.3 (2021 tarihli) modern bir macOS sisteminde kurulmuyor.

| # | Hata | Sebep | Çözüm |
|---|---|---|---|
| 1 | `SSL: CERTIFICATE_VERIFY_FAILED` | python.org Python'unda sertifika paketi kurulu değil | `Install Certificates.command` çalıştırıldı |
| 2 | `gevent` derleme hatası | ESP-IDF'in eski Python bağımlılıkları Python 3.12 ile derlenemiyor | `brew install python@3.10` ile ayrı sürüm kuruldu |
| 3 | `No module named 'pkg_resources'` | Yeni `setuptools` (84.0) bu modülü kaldırdı | `setuptools<81` sürümüne sabitlendi |
| 4 | CMake `cmake_minimum_required` hatası | Modern CMake 4.x, eski mbedtls'in istediği düşük sürümü desteklemiyor | `CMAKE_POLICY_VERSION_MINIMUM=3.5` |
| 5 | Flash yazma hatası (`C100`) | 460800 baud'da USB-seri kararsızlığı | `-b 115200` ile düşük hızda yazma |
| 6 | Seri çıktıda anlamsız karakterler | Firmware (921600) ile okuyucu baud hızı uyuşmazlığı | Doğru baud hızı kullanıldı |

**Genel ders:** Eski sürüm bir çerçeveyi güncel bir işletim sisteminde kurmak, bağımlılık zincirindeki her katmanda uyumsuzluk riski taşır.

---

### 6.3 Hiç CSI Verisi Gelmemesi

**Sorun:** Firmware çalışıyor, WiFi'ye bağlanıyor, ama hiç CSI verisi üretilmiyordu.

**Sebep:** ESP32-CSI-Tool, CSI üretmek için sabit `192.168.4.1` adresine paket gönderiyordu. Bu adres, aracın tasarlandığı **iki-ESP32 senaryosuna** aitti (biri erişim noktası, biri istemci). Bizim tek kartlı + normal router senaryomuzda böyle bir adres hiç yoktu; paketler boşluğa gidiyordu.

**Çözüm:** Firmware kodu değiştirildi. Kart artık bağlandığı ağın **gateway adresini otomatik olarak** öğrenip (`IP_EVENT_STA_GOT_IP` olayından) oraya paket gönderiyor. Bu sayede hangi ağa bağlanırsa bağlansın (ev, iş, hotspot) otomatik çalışıyor.

---

### 6.4 5 GHz WiFi Uyumsuzluğu

**Sorun:** Ev ağına bağlanamama.

**Sebep:** Klasik ESP32 **sadece 2.4 GHz** destekler, 5 GHz ağları göremez bile.

**Çözüm:** Router'ın 2.4 GHz SSID'si kullanıldı. (Telefon hotspot'unda ise iPhone'un "Maksimum Uyumluluk" ayarı açılarak 2.4 GHz'e zorlandı.)

---

### 6.5 Ortam Kirliliği: Vantilatör Etkisi

**Sorun:** Bazı kayıtlar diğerlerinden sistematik olarak farklı çıkıyordu.

**Sebep:** Kayıt sırasında çalışan vantilatörün **dönen pervanesi de bir hareket kaynağıdır** ve CSI sinyalini etkiler. Bu o kadar bilinen bir olgudur ki, akademik CSI-Bench veri setinde "hareket kaynağı tanıma" görevinin sınıflarından biri doğrudan **"fan"**'dır.

**Çözüm:** Etkilenen kayıtlar silinip vantilatör kapalıyken yeniden çekildi. **Ders:** Veri toplarken ortamdaki tüm hareketli nesneler tutarlı halde olmalıdır.

---

### 6.6 Bozuk CSV Ayrıştırma

**Sorun:** Kaydedilen dosyaların bir kısmı okunamıyordu.

**Sebep:** İki farklı bozulma türü tespit edildi:
1. Seri iletişimde satır sonu karakteri kaybolunca **birden fazla paket tek satırda birleşiyor** (bir dosyada 8 paket üst üste yapışmıştı)
2. Sayılar arası boşluk kaybolunca `32-12` gibi **bitişik sayılar** oluşuyor

**Çözüm:** `pandas.read_csv` yerine, satır sınırlarından bağımsız çalışan **düzenli ifade (regex) tabanlı ayrıştırıcı** yazıldı. Bu, hem bozuk hem sağlam satırlarda doğru çalışıyor.

---

### 6.7 Faz Bilgisi: Sentetikte Çalıştı, Gerçekte Çalışmadı

**Sorun:** Sentetik veride kalp atışı doğruluğunu artıran faz yöntemi, kendi gerçek verimizde performansı **düşürdü**.

| Yöntem | Sentetik veri | Kendi verimiz |
|---|---|---|
| Genlik + zero-crossing | 8.62 BPM hata | **11.36 BPM hata (en iyi)** |
| Faz + zero-crossing | **7.32 BPM hata (en iyi)** | 13.60 BPM hata |
| Otokorelasyon | — | 19+ BPM hata |

**Sebep:** Gerçek WiFi donanımından gelen ham faz bilgisi, cihazın kendi kaynaklı **zamanlama ve frekans kaymalarını** içerir. Sentetik veride bu bozulmalar yoktu. Literatürde bu sorun için "faz temizleme (phase sanitization)" adlı ayrı bir ön işleme adımı gerekir.

**Çözüm/Karar:** Gerçek veride genlik tabanlı yöntem korundu. Bu, "denendi, işe yaramadı" şeklinde kayıt altına alınan geçerli bir bilimsel sonuçtur.

---

### 6.8 Sistemin Kapsam Sınırı: Çok Hızlı Nefes

**Sorun:** Hızlı nefes testinde tahmin tamamen şaştı (gerçek 43.5 BPM, tahmin 16.5 BPM).

**Sebep:** 43.5 BPM = 0.725 Hz, bizim nefes bandımızın (**0.1–0.5 Hz = 6–30 BPM**) **dışında** kalıyor. Bandpass filtre bu sinyali tasarımı gereği bastırıyor; geriye kalan gürültü rastgele bir sonuç üretiyor.

**Çözüm/Değerlendirme:** Bu bir hata değil, **belgelenmiş bir tasarım sınırıdır**. Sistem, normal istirahat nefes hızı (12–20 BPM) ve makul varyasyonlar için tasarlanmıştır; hiperventilasyon seviyesindeki nefesi kapsamaz. Bu sınır RuView'in kendi bant tanımıyla da tutarlıdır.

---

### 6.9 ⚠️ En Kritik Bulgu: Oturumlar Arası Genelleme Başarısızlığı

**Sorun:** Aynı oturum içinde %77.8 doğrulukla çalışan oturma/ayakta modeli, 2 saat sonraki canlı testte **sürekli yanlış cevap verdi** (her şeye "ayakta" dedi, üstelik %94 güvenle).

**Teşhis (ölçümle):**

| Ölçüm | Değer |
|---|---|
| Eğitim verisi — "oturma" genlik seviyesi | 19.14 |
| Eğitim verisi — "ayakta" genlik seviyesi | 18.84 |
| **Sınıflar arası fark** | **0.30** |
| 2 saat sonraki taze kayıt — "oturma" | 20.55 |
| 2 saat sonraki taze kayıt — "ayakta" | 21.02 |
| **Ortam kayması** | **~1.70** |

**Sebep:** Ortamın zaman içindeki doğal kayması (WiFi kanal koşulları, cihaz konumları, sıcaklık), modelin öğrenmesi gereken sınıf farkından **5 kat büyük**. Dahası, ilişki tersine dönmüş: eğitimde oturma > ayakta iken, taze veride oturma < ayakta.

**Denenen çözümler:** Üç farklı normalizasyon yöntemi (ham / ortalamaya bölme / z-skor şekil) denendi.

| Yöntem | Oturum-içi doğruluk | **Taze oturum doğruluğu** |
|---|---|---|
| Ham | %75.0 | **%50 (rastgele)** |
| Ortalamaya bölme | %77.4 | **%50 (rastgele)** |
| Z-skor şekil | %66.7 | **%50 (rastgele)** |

**Sonuç:** Hiçbiri işe yaramadı. Aynı oturum içindeki başarı ölçümü (Leave-One-Out) **yanıltıcıydı** — gerçek dünya performansını temsil etmiyordu.

**Önemli ders:** Makine öğrenmesinde, doğrulama yönteminin gerçek kullanım koşullarını yansıtması şarttır. Aynı oturumdan gelen veriyle yapılan doğrulama, iyimser ve gerçek dışı sonuç verir.

---

### 6.10 🚀 En Büyük Kazanım: Örnekleme Hızı Sorunu ve Çözümü

**Sorun:** Firmware `PACKET_RATE=100` (saniyede 100 paket) ayarlı olmasına rağmen, gerçekte sadece **~9.5 Hz** veri alınıyordu — tasarım hızının 10 katı altında.

**Sebep (kök neden analizi):**

> **CSI, ESP32'nin GÖNDERDİĞİ paketlerden değil, ALDIĞI çerçevelerden üretilir.**

Kart paket gönderiyordu ama karşı taraf (router) her pakete cevap vermediği için kart bir şey **almıyordu**. Aldığı tek düzenli şey, router'ın **beacon** yayınlarıydı — bunlar standart olarak 100 ms aralıkla gönderilir, yani **~10 Hz**. Ölçtüğümüz 9.5 Hz ile birebir uyuşuyor.

**Sinyal gücünün kritik rolü:**

| Kurulum | RSSI (sinyal gücü) | Paket hızı |
|---|---|---|
| Uzak ev modemi | **−77 dBm** | 2.4–3.9 Hz |
| Telefon hotspot (yakın) | −31…−61 dBm | 9.5 Hz |
| Yakın modem, paket gönderimi yok | −61 dBm | 2.7 Hz |
| **Yakın modem + laptop'tan paket gönderimi** | **−61 dBm** | **🎯 145 Hz** |

**Çözüm:** Laptop'tan ESP32'ye sürekli UDP paketi gönderildi. Kart artık her gelen pakette CSI üretiyor. Sonuç: **9.5 Hz → 145 Hz, yani 15 kat hızlanma.**

**Kritik detay:** Bu yöntem ilk denendiğinde işe yaramamıştı (2.4 → 3.9 Hz). Sebep, o anda sinyal gücünün −77 dBm olmasıydı — gönderilen paketlerin çoğu karta ulaşmıyordu. Modeme yaklaşıp sinyal −61 dBm'e çıkınca yöntem çalıştı. **Sinyal gücü, bu sistemin gizli ön koşuludur.**

**Ek bulgu:** Yüksek hızda CSI formatı da değişti (paket başına 256 → 128 değer), çünkü beacon çerçeveleri ile veri çerçeveleri farklı WiFi modlarında iletiliyor. Bu, eski verilerle eğitilmiş modellerin yeni veriyle uyumsuz olması demek — veriler yeniden toplanmalı.

---

## 7. Elde Edilen Sonuçlar

### 7.1 Kalp Atışı (Sentetik veri setiyle doğrulandı)

| Yöntem | Ortalama Mutlak Hata |
|---|---|
| Genlik + FFT | 12.56 BPM |
| Genlik + zero-crossing | 8.62 BPM |
| **Faz + zero-crossing** | **7.32 BPM** ✅ |

### 7.2 Nefes (Kendi gerçek verimizle)

| Test | Gerçek (elle sayım) | Tahmin | Hata |
|---|---|---|---|
| Yavaş/derin tempo | 15 BPM | 15.99 BPM | **0.99 BPM** ✅ |
| Normal tempo | 24 BPM | 20.95 BPM | 3.05 BPM |
| Hızlı tempo | 43.5 BPM | — | Bant dışı (bkz. 6.8) |

### 7.3 Aktivite Sınıflandırma

| Veri Seti | Sınıf Sayısı | Doğruluk |
|---|---|---|
| **UT-HAR** (hazır, gerçek) | 7 | **%95.2** (test seti) ✅ |
| Kendi verimiz (aynı oturum) | 3 | %77.8 |
| Kendi verimiz (farklı oturum) | 3 | %50 ❌ (bkz. 6.9) |

**Not:** UT-HAR'daki yüksek başarı, yöntemin doğruluğunu kanıtlar; ancak o model 3 antenli Intel 5300 donanımıyla toplanmış veriyle eğitildiği için doğrudan bizim tek antenli kartımıza aktarılamaz.

### 7.4 Hareket Tespiti (Canlı testte doğrulandı)

| Durum | Ölçülen hareket enerjisi |
|---|---|
| Tamamen hareketsiz | 0.9 – 1.5 |
| Hafif kıpırdanma | 1.8 – 2.5 |
| Ani hareket (oturma/kalkma) | 3.0 – 5.5 |

**Hareket tespiti, sistemin en güvenilir bileşenidir** — fiziğe dayalı (istatistiksel öğrenmeye değil) olduğu için ortam kaymasından etkilenmez.

### 7.5 Canlı Sistem

- Gerçek zamanlı web arayüzü çalışır durumda (Flask, `localhost:5050`)
- Güncelleme gecikmesi: **~1–2 saniye**
- Gösterilen bilgiler: Aktivite durumu, güven yüzdesi, kalp atışı, hareket enerjisi, bağlantı durumu

---

## 8. Öğrenilen Dersler

1. **Donanım sınırları yazılımla aşılamaz.** Tek antenli, düşük örnekleme hızlı bir kartla, çoklu antenli sistemler için tasarlanmış algoritmalar çalışmaz.

2. **Doğrulama yöntemi, sonucun kendisi kadar önemlidir.** Aynı oturumdan veriyle yapılan test %77.8 gösterirken, gerçek koşul %50 çıktı. Yanlış doğrulama, yanlış güven verir.

3. **Kök neden analizi, semptom tedavisinden değerlidir.** "Model yanlış tahmin ediyor" semptomunun ardında iki farklı kök neden vardı: ortam kayması ve yetersiz örnekleme hızı. İkisi de ölçümle bulundu.

4. **Sinyal işleme ve makine öğrenmesi farklı davranır.** Sinyal işleme (bandpass filtre) donanımdan bağımsızdır ve hazır veri setleri doğrudan kullanılabilir. Makine öğrenmesi ise donanımın parmak izini öğrenir, bu yüzden transfer edilemez.

5. **Negatif sonuçlar da sonuçtur.** Faz yönteminin gerçek veride başarısız olması, normalizasyonun genellemeyi kurtaramaması — bunlar sistemin sınırlarını belgeleyen değerli bulgulardır.

---

## 9. Mevcut Durum ve Sonraki Adımlar

### Tamamlananlar ✅
- Donanım tespiti, ortam kurulumu, firmware özelleştirmeleri
- Veri toplama altyapısı
- Kalp atışı ve nefes analiz hattı
- Aktivite sınıflandırma yöntemi (UT-HAR ile doğrulandı)
- Canlı web arayüzü
- **Örnekleme hızı sorununun çözümü (15 kat iyileşme)**

### Devam Edenler 🔄
- Yüksek hızda (145 Hz) veri setinin yeniden toplanması
- Modellerin yeni veriyle yeniden eğitilmesi ve test edilmesi

### Planlananlar 📋
- Oturumlar arası genellemenin yüksek örnekleme hızıyla yeniden değerlendirilmesi
- Yürüme dahil daha çeşitli aktivite sınıflarının eklenmesi
- Sonuçların raporlanması

### Açık Konular ❓
- **Uzuv/iskelet takibi (poz tahmini):** Mevcut donanımla (tek anten) gerçekçi değil. RuView'in hazır modeli 3 anten × 114 alt-taşıyıcı × 100 Hz gerektiriyor. Bu, donanım yükseltmesi gerektiren ayrı bir çalışma konusudur.
- **IEEE DataPort veri seti:** Bizimle aynı donanımla toplanmış, üniversite aboneliğiyle erişilebilir olabilir.

---

*Bu doküman, 18–19 Ağustos 2026 tarihlerinde yürütülen çalışmanın kaydıdır. Tüm sayısal sonuçlar gerçek ölçümlere dayanmaktadır.*
