# Deneysel harici EMerge (dalga kılavuzu fikstürü ve Tasarım alt kümesi)

Fairbeam, ayrı ve isteğe bağlı bir `fairbeam-emerge` araştırma komutu içerir. Harici bir EMerge
Python ortamını bulur. EMerge'i yalnızca o ortamda başlatılan bir işçi süreci içe aktarır;
Fairbeam süreci `emerge`, `gmsh` veya `emsutil` içe aktarmaz. Normal Fairbeam projeleri,
çalışma ortamı kurulumu ve varsayılan openEMS simülasyon yolu değişmez. Fairbeam kurucusuna
EMerge tekerlekleri gömülmez ve açık bir kullanıcı eylemi olmadan kurulmaz. Masaüstü paketi yine
de Fairbeam'in bağımsız bağdaştırıcılarını (`fairbeam_emerge.py` ve `fairbeam_emerge_worker.py`)
taşır ve çalışma ortamı kurulum/güncellemesinde bunları yönetilen Python uygulama dizinine
kopyalar (`fairbeam_elmer.py` ile aynı düzen). Kurulu uygulama `No module named fairbeam_emerge`
bildirirse Fairbeam'i güncelleyin veya onarın; yalnızca EMerge ortamını yeniden kurmak eksik
bağdaştırıcıyı onarmaz.

**A düzeyi**, iki dalga kılavuzu portlu sabit, kayıpsız, hava dolu WR-90 dikdörtgen dalga
kılavuzunu çalıştırır (kullanıcı Tasarımı yok). **B3 düzeyi** Tasarım Çalıştır yoludur: tek
seçenek **EMerge FEM · Deneysel** (`analysis: "emerge_nport"`, health `emerge` ≥ 3), bugünkü
sınırlı geometri tarifleri altında tek türden **1…8** portu kabul eder — uyarılmış/toplu
(B düzeyi sınıfı), düzlemsel mikroşerit/Ayrık/klasik CPW (B2 düzeyi sınıfı) veya tümü koaksiyel
TEM (port-map B aşaması, `geometry_kind: "coaxial_tem"`) — ve tam deneysel N×N S matrisini
dışa aktarır (`fairbeam.emerge-result/2`). Geometri sınırlı kalır (çok katman, via, eğri veya
sessiz zorlama yok). `design` ve `planar` CLI alt komutları hâlâ uyarılmış/düzlemsel tarifleri
hedefler. Aşağıdaki tarihsel B / B2 bölümleri önceki tek port / iki port ölçümlerini ve
yeterlilik notlarını tutar. Tüm Tasarım yolları isteğe bağlı deneyseldir; sonuçlar
`results_exported`'tur, asla `results_validated` değildir.

## Port eşlemesi (A aşaması)

Deneysel openEMS biçimli Tasarım portları, `fairbeam.emerge_port_map` (`resolve`) içinde EMerge
sınır koşullarına eşlenir. İlke kaynağı:
[docs/agent/specs/2026-11-05-emerge-openems-port-mapping-design.md](../agent/specs/2026-11-05-emerge-openems-port-mapping-design.md).
A aşaması B düzeyi toplu → `LumpedPort`, B2 düzeyi mikroşerit → toplu şerit-toprak `LumpedPort`
(varsayılan düzlemsel kabul) ve A düzeyi fikstür `RectangularWaveguide` eşlemelerini Tasarım
dalga kılavuzu kabulü olmadan bu matrise birleştirir. Kabul hâlâ desteklenmeyen türleri reddeder;
yaklaşık eşlemeler mevcut `accept_*` kapılarını korur. Köken
(`design_port_type`, `mapped_bc`, `approximations`, `accept_used`) durum ve deneysel sonuçlar /
paketler üzerinde kaydedilir. Düzlemsel yolda homojen Ayrık/`lumped` portlar da
`accept_finite_feed` arkasında `LumpedPort`'a eşlenir (mikroşerit terminalleriyle aynı tahta
kenarı plaka geometrisi; tüm portlar tek tür paylaşmalıdır — karışık Ayrık ve mikroşerit
reddedilir). Birleşik Çalıştır penceresi önizlemesi ve kabul onay kutuları sınıflanan yolu ve
taslak port türlerini izler. B aşaması koaksiyel ve C aşaması isteğe bağlı mikroşerit / klasik
CPW `WavePort` aşağıda belgelenir. Ertelenen izlemeler (Tasarım dalga kılavuzu, topraklı CPW,
daha zengin geometri):
[docs/agent/BACKLOG-emerge-port-map.md](../agent/BACKLOG-emerge-port-map.md).
B3 düzeyi, antene karşı düzlemsel Çalıştır seçeneklerini otomatik öneren backlog maddesinin yerini
almıştır.

## Port eşlemesi (B aşaması — koaksiyel → CoaxPort)

Her Tasarım portu `coaxial` olduğunda birleşik Çalıştır sınıflayıcısı
`geometry_kind: "coaxial_tem"` kabul eder (işçi `kind: "coax"`). `"coax"` yolunda
`emerge_port_map.resolve`, yalnızca `accept_coaxial_tem: true` iken her portu analitik EMerge
`CoaxPort` TEM'e eşler. Çalıştır penceresi bu kabul onay kutusunu ve bir port-map önizleme
satırını gösterir (`Port N · coaxial → CoaxPort`).

**Sınırlar (dürüst):**
- Eksenlere paralel merkez çizgisi (`direction` x|y|z); openEMS koaksiyel için zaten denetlenen
  Tasarım kalkan dış `r_os` ile `0 < r_i < r_o`.
- Sabit εr dolgu (hava veya dağılımsız dielektrik). Dağılımlı dolgu, geçersiz yarıçaplar, eksik
  kabul, karışık port türleri, Tasarım dalga kılavuzu, TM/TEM dışı koaksiyel modlar ve port
  grupları reddedilir — asla sessizce yeniden eşlenmez.
- Geometri MVP, portlardan iç PEC silindir, dış kalkan boru, dielektrik ve dolgulu bir alan
  sentezler; bu yolda Tasarım `parts` kabul edilmez.
- Homojen **1…8** koaksiyel port; aynı sonuç şeması üzerinden tam deneysel N×N S
  (`fairbeam.emerge-result/2`). Durum yalnızca `results_exported` kalır.
- openEMS S parametresi uyumu iddiası yok; bu bölümde uydurulmuş yerel S sayıları yok.

Koaksiyel mesh kalitesi izlemesi: [docs/agent/BACKLOG-emerge-port-map.md](../agent/BACKLOG-emerge-port-map.md)
(Finer coax mesh & excitation).

## Port eşlemesi (C aşaması — mikroşerit → WavePort)

Her Tasarım portu `microstrip` olduğunda düzlemsel yol, her portu toplu terminaller için
kullanılan aynı tahta kenarı plakasında EMerge `WavePort`'a yalnızca
`accept_modal_ports: true` iken eşleyebilir. Çalıştır penceresi, mevcut toplu terminal kabulünün
yanında ayrı bir modal kabul onay kutusu gösterir. İki kabulden en az biri gerekir. İkisi de
ayarlıysa **modal kazanır** (`mapped_bc: "WavePort"`, `accept_used: ["accept_modal_ports"]`).
Önizleme satırları aynı kuralı izler. WavePort kurulum hatası sert hatadır — `LumpedPort`'a
sessiz geri dönüş yoktur. `WavePort` tercih edin; belgelenmiş deneme ve insan onayı olmadan
`ModalPort` göndermeyin.

**Sınırlar (dürüst):**
- Homojen tümü-`microstrip` portlar. Klasik CPW aynı kabul bayraklarını ayrı bir geometri
  sınıfında kullanır (aşağıda).
- Besleme/ölçüm kaymaları kullanılmaz (toplu eşlemeyle aynı plaka sınıfı).
- Yalnızca toplu işaretliyken varsayılan kabul yolu şerit-toprak `LumpedPort` kalır.
- openEMS S parametresi uyumu iddiası yok; burada uydurulmuş C aşaması S sayıları yok.
- Yönetilen EMerge **3.0.0b12** üzerinde 2026-11-06 ölçümü (Windows EMerge'i kur): hairpin
  fikstürü yalnızca `accept_modal_ports`, `mesh_only`, shielded coarse, `approximate_metals`
  ile kabul edildi — işçi her iki terminal yüzüne `WavePort` bağladı ve
  `fairbeam.emerge-mesh-result/1` dışa aktardı (**19435** düğüm / **111428** tet, mesh duvarı
  **~3,0 s**). Bu çalıştırma S parametrelerini taramadı.

## Port eşlemesi (C aşaması — klasik CPW → WavePort)

Her Tasarım portu `cpw` olduğunda düzlemsel yol yalnızca **klasik CPW** kabul eder: bir
dielektrik alttaş kutusu, alttaş **üstünde** metal levhalar (merkez şerit artı ≥2 eşdüzlemli
toprak levhası) ve alttaş altı toprak / PEC-z− levhası yok. Topraklı CPW (alt toprak varken)
açık bir hatayla **reddedilir**. Portlar `accept_modal_ports: true` iken EMerge `WavePort`'a
veya yalnızca `accept_lumped_terminals: true` iken tahta kenarı boşluk tarzı `LumpedPort`
plakasına (`ground_mode: "coplanar"`) eşlenir. En az bir kabul gerekir; ikisi de ayarlıysa
**modal kazanır**. Terminal yüzü kilitli CPW açıklığıdır: tahta kenarı plakası, enine açıklık =
her yanda `2*gap` ile genişletilmiş merkez şerit genişliği, düşey açıklık = alttaş kalınlığı
artı metal düzleminin üstünde `air_height_mm`'nin `CPW_AIR_APERTURE_FRACTION` kadarı (hava
kutusuna sıkıştırılır; şu an **1,0**). Mikroşerit / Ayrık terminaller alttaş yüksekliğinde
kalır. WavePort kurulum hatası sert hatadır — `LumpedPort`'a sessiz geri dönüş yok. Klasik CPW
WavePort'ları, yüzde ikiden fazla PEC adası varken EMerge'in PV Z0 hesaplayabilmesi için
`set_terminals(strip, ground)` çağırır. Çözücü süreci klasik CPW için alttaş altına PEC
**bağlamaz** (bu, arka toprak uydururdu). `WavePort` tercih edin; belgelenmiş deneme ve insan
onayı olmadan `ModalPort` göndermeyin.

**Sınırlar (dürüst):**
- Yalnızca homojen tümü-`cpw`; karışık mikroşerit/toplu/koaksiyel reddedilmeye devam eder.
- GCPW / alt topraklı CPW henüz kabul edilmez.
- Toplu CPW, mikroşerit şerit-toprak değil aynı eşdüzlemli açıklık plakasını (boşluk tarzı)
  kullanır; işçi hâlâ `direction=ZAX` ile `LumpedPort` sürer (eşdüzlemde zayıf — ölçülen nota
  bakın).
- Besleme/ölçüm kaymaları kullanılmaz; openEMS S parametresi uyumu iddiası yok.
- **O17 BLOCKED (2026-11-07):** hava açıklığı + açık muhafaza + `set_terminals`,
  `portmap_cpw_line` üzerinde inandırıcı geniş bant geçiş hattı vermez. İnsan WavePort S'ini
  reddetti (bant altı hâlâ yüksek yansıtıcı). ModalPort başlatılmadı. Mikroşerit düzlemsel
  sağduyu (hairpin / portmap hattı) aynı kodda sağlıklı kalır — CPW'ye özgü, genel düzlemsel
  kırılma değil.
- Yönetilen EMerge **3.0.0b12** üzerinde 2026-11-07 ölçümü (Windows EMerge'i kur), yerel
  `portmap_cpw_line`, aksi belirtilmedikçe shielded coarse:
  - Erken kabul (yalnızca alttaş yüzü): `mesh_only` **5453** düğüm / **27377** tet (~1,0 s);
    fizik incelemesinden önce 3 noktalı S dışa aktarıldı (~8,1 s).
  - Hava açıklığından sonra (tam hava sütunu): insan işi `20261107-013032-d9b825` — \|S11\|
    min≈0,17 @~3,09 GHz / max≈0,90; \|S21\| max≈0,93 @~3,09 GHz ama **~0,43 (−7,4 dB) @1,2 GHz**
    (geçiş hattı beklentisine göre FAIL). Open pad-10 çalıştırması benzer şekil, orta bantta
    biraz daha iyi.
  - `set_terminals` ile: PV Z0 ~70–74 Ω günlüğe yazıldı; S, yalnızca açıklığa göre değişmedi.
  - Yalnızca toplu kabul: \|S21\| ≲ 0,003 (~−50…−64 dB) — WavePort'tan daha kötü.
  - openEMS S uyumu iddiası yok.

## Çalıştırma

Depodan Python 3.10+ kullanın veya ayrı `fairbeam-emerge` giriş noktasını elde etmek için Python
paketini kurun. `--root` (veya `FAIRBEAM_EMERGE_PYTHON`) değerini EMerge 3.0.0b12 içeren bir
sanal ortam klasörüne veya o ortamın Python yürütülebilir dosyasına yöneltin. PATH araması
yoktur.

```powershell
python python/fairbeam_emerge.py --root $env:LOCALAPPDATA\org.fairbeam.desktop\emerge\3.0.0b12 capabilities
python python/fairbeam_emerge.py --root $env:LOCALAPPDATA\org.fairbeam.desktop\emerge\3.0.0b12 waveguide --experimental --resolution coarse --out E:/research/wr90-coarse
python python/fairbeam_emerge.py --root $env:LOCALAPPDATA\org.fairbeam.desktop\emerge\3.0.0b12 waveguide --experimental --resolution fine --out E:/research/wr90-fine
```

Windows'ta Simülasyon → Deneysel çözücüler içindeki **EMerge'i kur**, yukarıdaki yönetilen
ortamı oluşturur (PyPI'dan hash kilitli `emerge==3.0.0b12` ve bağımlılıkları). Kurulumdan sonra
o kopyayı kullanmak için yolu boş bırakın. Diğer platformlarda `emerge==3.0.0b12` ile kendi
Python 3.10–3.13 ortamınızı oluşturup klasörünü girin veya `FAIRBEAM_EMERGE_PYTHON` ayarlayın.

`capabilities` çözücüyü başlatmaz: kullanılabilirlik, ortamın ve `emerge` dist-info'nun
bulunduğu anlamına gelir; her yerel bağımlılığın denendiği anlamına gelmez. Yürütme için
`--experimental` gerekir. Çıktı yeni bir dizin olmalıdır; mevcut durumlar asla üzerine yazılmaz.
Yalnızca `coarse` (0,25) ve `fine` (0,125) çözünürlükleri — üst frekansta EMerge dalga boyu
kesirleri — ve sabit WR-90 geometrisi desteklenir. İşçi bir OpenMP/BLAS/Numba iş parçacığı,
600 saniye zaman aşımı ve paralel tarama olmadan çalışır. Başarısız veya kesilen manifesto ve
`worker.log` saklanır; analitik denetimleri başarısız olan başarılı bir çıkış, ham çıktı
korunarak `validation_failed` olarak kaydedilir.

## Fiziksel referans ve gerçek yerel Windows gözlemleri

Fikstür düz WR-90 hava dolu dikdörtgen dalga kılavuzudur: geniş duvar a = 22,86 mm (x), dar
duvar b = 10,16 mm (y), uzunluk L = 50,0 mm (z). Duvarlar PEC; dolgu vakum/hava (εr = 1, μr = 1,
kayıpsız). Portlar z = 0 ve z = L yüzlerinde `RectangularWaveguide` TE10'dur. Frekanslar tam
olarak 8,0, 9,0, 10,0, 11,0 ve 12,0 GHz'tir. TE10 kesimi c0/(2a) = 6,557 GHz; sonraki mod TE20
13,11 GHz'tedir, yani bant tek modludur. c0 = 299792458 m/s.

Analitik referans, Fairbeam'in `exp(+i omega t)` fazör uzlaşımını ve port yüzlerindeki referans
düzlemlerini kullanır: k0 = 2πf/c0, β = sqrt(k0² − (π/a)²), S21 = S12 = exp(−i β L),
S11 = S22 = 0. EMerge 3.0.0b12 (ve önceki 2.8.9 sabiti) bu fikstür için aynı yerel uzlaşımı
kullanır; bağdaştırıcı eşlenik almaz.

Yönetilen yerel Windows EMerge **2.8.9**, 2026-11-04'te kaydedildi (3.0.0b12 sabitinden önce):

| Çözünürlük | Dalga boyu kesri | Düğüm / tetrahedra | Çözücü süresi | max \|S11\| | min \|S21\| | max faz hatası |
|---|---|---|---|---|---|---|
| coarse | 0,25 | 163 / 397 | 160,945 s | 0,005462 | 0,999896 | 0,789° |
| fine | 0,125 | 667 / 2305 | 9,223 s | 0,000119 | 0,999993 | 0,037° |

Her iki çalıştırma da `results_validated` bildirdi. Duvar saati 164,8 s (coarse) ve 11,2 s
(fine) idi; ilk (coarse) çalıştırma soğuk Numba JIT maliyeti ödedi, ikinci (fine) sıcak önbelleği
yeniden kullandı. Coarse `result.json` frekans başına değerler:

| f (GHz) | \|S11\| | \|S21\| | faz hatası (°) |
|---|---|---|---|
| 8 | 0,000151 | 0,999961 | 0,120 |
| 9 | 0,000533 | 0,999956 | 0,188 |
| 10 | 0,000629 | 0,999947 | 0,308 |
| 11 | 0,001578 | 0,999932 | 0,499 |
| 12 | 0,005462 | 0,999896 | 0,789 |

Fine çalıştırma özetleri: max \|S11\| = 0,000119, min \|S21\| = 0,999993, max faz hatası =
0,037°, max pasiflik |S11|²+|S21|² = 0,999992 (coarse pasiflik max = 0,999922).

Kabul (bu çalıştırmalardan dondurulmuş; coarse en kötü durum) şunları gerektirir:

- frekanslar üzerinde max \|S11\| ≤ 0,02
- frekanslar üzerinde min \|S21\| ≥ 0,995
- frekanslar üzerinde sarılmış \|arg(S21) − (−β L)\| ≤ 2 derece
- her frekansta \|S11\|² + \|S21\|² ≤ 1,005
- tüm değerler sonlu; frekanslar sırayla tam fikstür listesi

Geçer → `status: "results_validated"`; kalır → `"validation_failed"` (ham çıktı saklanır).
`precision_converged` her zaman `false`'tur. Bu kaba bir uygulanabilirlik fikstürüdür, mesh
yakınsama belgesi değildir. Fikstür yolu hâlâ rastgele proje geometrisini çevirmez; Tasarım
çevirisi aşağıdaki ayrı B düzeyi yoludur.

Ham işçi girdileri (`case.json`), `raw.json`, `result.json`, `manifest.json` ve `worker.log` her
çalıştırma dizininde kalır. Manifestolar işçi ve Python SHA-256 özetlerini kaydeder. Fikstür
sonuçları ayrı araştırma dosyalarıdır; Tasarım çalıştırmaları ayrıca paylaşılan Sonuçlar
paketi yazar (S11 / Zin, boş uzak alan).

## B3 düzeyi: birleşik N-port Çalıştır (Tasarım yolu)

Uygulamada **Çalıştır**'ı açın, **EMerge FEM · Deneysel**'i seçin (health `emerge` ≥ 3 iken
görünür), bandı ve çözünürlüğü ayarlayın, taslak portların gerektirdiği yaklaşıklıkları kabul
edin ve gönderin. `backend` `"emerge"`, `analysis` `"emerge_nport"`'tur. Sunucu Tasarımı
`geometry_kind` `driven_lumped`, `planar_microstrip` veya `coaxial_tem` olarak sınıflar (veya
başarısız sınıf denetimleriyle reddeder). Port sayısı **1…8** olabilir (`N_MAX`); portlar
bitişik `1…N` olmalı ve o sınıf için izin verilen aynı türde olmalıdır. Tümü koaksiyel
taslaklar ayrıca `accept_coaxial_tem` ister (yukarıda B aşaması). Paylaşılan Sonuçlar eksiksiz
N×N deneysel `sparams` matrisi alır (`fairbeam.emerge-result/2`). openEMS aynı pencerede
kullanılabilir kalır. Aşağıdaki tarihsel B ve B2 alt bölümleri geometri tariflerini ve kaydedilmiş
yerel sayıları belgeler; artık ayrı Çalıştır markaları değildir.

## B düzeyi: sınırlı Tasarım alt kümesi (uyarılmış ayrık port)

Kabul, aynı geometri sınıfı için Elmer'in uyarılmış kurallarını yansıtır: eksenlere paralel
dielektrik kutular ve metal levhalar, bitişik `1…N` numaralı **1…8** toplu (Ayrık) port, direnç /
toplu eleman / dönüşüm / kesi / boşluk yok, örtüşen dielektrik yok. İdeal çizgi besleme yalnızca
açık `accept_finite_feed` ve `feed_width_mm` ile genişletilir. Pozitif `conductivity`'li metal
levhalar EMerge `ThinConductor` kullanır (σ ve levha `thickness`, varsayılan 0,035 mm); boş
iletkenlik PEC kalır. İsteğe bağlı `approximate_metals` yalnızca o çalıştırma için PEC zorlar.
Sıfır olmayan `tan_d`, EMerge'in sabit kayıp tanjantı olarak kabul edilir (sınırlama olarak
kaydedilir). Yüzey pürüzlülüğü modellenmez. Hava kutusu, her yanda `padding_mm` eklenmiş
parça+besleme sınır kutusudur; altı yüzde ikinci dereceden soğurucu sınırlar vardır (PML değil).
Desteklenmeyen geometri `ValueError` yükseltir; hiçbir şey sessizce düşürülmez.

Dondurulmuş ayarlar (Görev 5 / Görev 6; B3 uyarılmış sınıf için hâlâ bunları kullanır):
çözünürlükler `coarse` = 0,25 ve `fine` = 0,15 (`f_max`te dalga boyu kesri); işçi zaman aşımı
1800 s; hava kutusu hacim vekili 200000'i aşınca başlatmadan reddet. Tarama:
`f_min_hz`…`f_max_hz`, birleşik formda 3–41 linspace noktası (uyarılmış sınıf tarihsel olarak
3–21 kullandı). Şema yalnızca `geometry_kind: "driven_lumped"` ile `fairbeam.emerge-result/2`.
Durum `results_exported`, `precision_converged: false`, `gain_qualified: false`, uzak alan yok.

```powershell
# after emerge_design.admit → case.json
python python/fairbeam_emerge.py --root $env:LOCALAPPDATA\org.fairbeam.desktop\emerge\3.0.0b12 design --experimental --case case.json --out E:/research/patch-coarse
```

**EMerge FEM · Deneysel** kullanın (B3/B4 düzeyi). CLI `design` hâlâ uyarılmış sınıf
case.json kabul eder.

### Patch sınıfı — kaydedilmiş yerel gözlemler (2026-11-04)

Yerleşik `blank_design("p", "Patch")`, `feed_width_mm=1`, `padding_mm=40`, 2,0–3,0 GHz × 11
nokta, `approximate_metals` false (şablon metalinde iletkenlik yok). Windows'ta yönetilen
EMerge **2.8.9** (2026-11-04 kaydı, 3.0.0b12 sabitinden önce):

| Çalıştırma | Çözünürlük | Düğüm / tet | Çözücü süresi | S11 min (linspace) | max \|S11\| |
|---|---|---|---|---|---|
| EMerge Tasarım | coarse (0,25) | 474 / 1975 | 11,517 s | 2,30 GHz, −7,427 dB | 0,982634 |
| EMerge Tasarım | fine (0,15) | 1141 / 5245 | 16,469 s | 2,30 GHz, −6,349 dB | 0,984801 |

Aynı şablon Fairbeam'in normal openEMS Çalıştır yolundan (tasarım mesh 20 hücre/dalga boyu,
bant `f0*0.6`–`f0*1.3`, 801 frekans noktası): S11 minimumu **2,453981250 GHz** **−45,574 dB**,
`mesh.total_cells=112320`, çözücü 35,2 s, yakınsadı.

B düzeyi bu sınıf için EMerge Tasarım ile openEMS arasında S11 uyumu **iddia etmez**. EMerge
linspace minimumu her iki meshte 2,30 GHz'te kaldı (openEMS minimum frekansının yaklaşık %6,3
altında); eşleşme derinliği çok daha sığdı. Coarse→fine aynı frekans binini tutarken oradaki
`|S11|` 0,425'ten 0,481'e yükseldi. Port modeli ve soğurucu sınır farkları beklenir; sonuçlar
deneysel dışa aktarım olarak kalır.

## B2 düzeyi: düzlemsel mikroşerit (hairpin sınıfı)

Kabul (`emerge_planar.admit`), bitişik `1…N` numaralı **1…8** portu kabul eder: ya tümü
`microstrip` (`x`/`y` yayılım, `z` uyarım, gerçek pozitif `reference_ohm`), ya tümü klasik
`cpw` (eşdüzlemli üst topraklar; yukarıda C aşaması CPW), ya da tümü Ayrık/`lumped`. Mikroşerit
ve Ayrık bir dielektrik alttaş kutusu, alttaş altında z-düz metal kutu veya alan tabanı PEC
olarak toprak ve alttaş üstünde z-normal `polygon` (veya z-düz kutu) metal izleri ister. Karışık
port türlerini, diğer port türlerini, `N > 8`, dirençleri, toplu elemanları, dönüşümleri,
kesileri, boşlukları, çok katman/via geometrisini, topraklı CPW'yi, başka yüksekliklerde metali
ve bilinmeyen ayarları reddeder. Pozitif `conductivity`'li iz metalleri EMerge `ThinConductor`
kullanır (σ ve levha kalınlığı); boş iletkenlik PEC kalır. İsteğe bağlı `approximate_metals` o
çalıştırma için izleri PEC zorlar. Mikroşerit/Ayrık için alttaş altı toprak PEC kalır; klasik
CPW o taban PEC'ini atlar. Her mikroşerit port, kullanıcı `accept_lumped_terminals: true`
ayarladığında tahta kenarı yüzünde toplu şerit-toprak terminal olur veya
`accept_modal_ports: true` iken aynı yüzde EMerge `WavePort` olur (C aşaması; ikisi de
ayarlıysa modal kazanır). Klasik CPW aynı kabul çiftini eşdüzlemli açıklık plakasıyla kullanır.
Her Ayrık port `accept_finite_feed: true` altında tahta kenarı plakasını kullanır. O
çalıştırma için `feed_shift`, `measurement_shift` ve `termination` kullanılmaz. Kayıtlı Tasarım
ve openEMS malzemeleri değişmez.

Birleşik yoldaki dondurulmuş ayarlar: `geometry_kind: "planar_microstrip"` ile
`analysis: "emerge_nport"`,
`enclosure: "shielded" | "open"`, `air_height_mm` (alttaş üstünün üstünde > 0), `padding_mm`
(> 0, yalnızca `open` ile), çözünürlükler `coarse` = 0,25 ve `fine` = 0,15, bant 1 MHz–100 GHz
ile 3–41 linspace noktası, isteğe bağlı `approximate_metals`. İz modeli: sıfır kalınlıklı
`XYPolygon` levhalar (`ThinConductor` veya PEC); metal kenar mesh boyutu 0,4 mm; her terminal
yüzünün ötesinde `PORT_PAD_MM` = 1,0. İşçi zaman aşımı 3600 s; kaynak vekili 400000 tetrahedra
aşınca reddet. Şema yalnızca `fairbeam.emerge-result/2`. Durum `results_exported`,
`precision_converged: false`, `gain_qualified: false`, boş uzak alan. Paylaşılan Sonuçlar
eksiksiz N×N `sparams` matrisi alır.

`shielded`, dış yüzleri EMerge'in varsayılan PEC kutusuna bırakır (tahta üstünde kapalı boşluk).
`open`, dört yan ve üstte ikinci dereceden soğurucu sınırlar koyar; bu yüzlerde `padding_mm`
vardır. Alttaş altı her zaman PEC'tir.

```powershell
# after emerge_planar.admit → case.json
python python/fairbeam_emerge.py --root $env:LOCALAPPDATA\org.fairbeam.desktop\emerge\3.0.0b12 planar --experimental --case case.json --out E:/research/hairpin-coarse
```

Birleşik **EMerge FEM · Deneysel** Çalıştır girişini tercih edin (B3 düzeyi); muhafaza, hava
yüksekliği ve pay, Tasarım düzlemsel sınıflanınca görünür. Eski **EMerge FEM · Deneysel
düzlemsel iki port** etiketi seçiciden kaldırılmıştır; CLI `planar` hâlâ düzlemsel case.json
kabul eder. Aşağıdaki kaydedilmiş hairpin sayıları tarihsel iki port çalıştırmalarındandır.

### Hairpin sınıfı — kaydedilmiş yerel gözlemler (2026-11-04)

Test fikstürü `python/tests/fixtures/emerge_hairpin.design.json` (50,828 × 58 mm FR4 benzeri
alttaş 1,6 mm, εr 4,34, 0,95 GHz'te tanδ 0,0026, beş bakır çokgen, iki mikroşerit port).
Windows'ta yönetilen EMerge **2.8.9** (2026-11-04 kaydı, 3.0.0b12 sabitinden önce), levha bakır
`approximate_metals` ile PEC'e zorlandı (ThinConductor öncesi yol), `air_height_mm=6,4`, bant
0,75–1,25 GHz × 15 nokta (aksi belirtilmedikçe):

| Çalıştırma | Muhafaza / çözünürlük | Düğüm / tet | Çözücü süresi | En iyi \|S21\| | Orada S21 / S11 |
|---|---|---|---|---|---|
| CLI planar | shielded coarse | 19147 / 109584 | 971,7 s | 1,071429 GHz | −0,63 dB / −30,45 dB |
| CLI planar | shielded fine | 19164 / 109714 | 1054 s | 1,071429 GHz | −0,63 dB / −31,27 dB |
| CLI planar | open coarse (`padding_mm=10`) | 19441 / 111586 | 1055 s | 1,071429 GHz | −0,51 dB / −34,20 dB |
| CLI / Çalıştır | shielded coarse, kısa 5 nokta 0,95–1,15 GHz | 19194 / 109920 | 320–338 s | 1,050 GHz | −0,82 dB / −19,55 dB |

Dört EMerge çalıştırması da `results_exported` bildirdi. Tam bant coarse→fine aynı en iyi-|S21|
frekans binini (1,071429 GHz) ve aynı −0,63 dB tepeyi tuttu; mesh boyutu metal kenar ayarına
hâkimdi (~110k tet). Açık muhafaza o tepe frekansını korudu ve ekleme kaybını biraz düşürdü
(−0,51 dB). Karşılıklılık max |S21 − S12| ≤ 4,2e−5 kaldı; sütun gücü ≤ 0,999 kaldı.

Aynı fikstür Fairbeam'in normal openEMS Çalıştır yolundan (`fairbeam run --engine gpu --threads
auto`, tasarım varsayılan mesh/bant): `sparams.complete=false` (yalnızca port 1 uyarıldı; Tasarım
port 2 `excite: false`), en iyi |S21| **1,025625 GHz** **+5,07 dB** (fiziksel değil; bildirilen
sütun gücü max 3,40), orada S11 **−7,27 dB**; Fairbeam bant notu min S11 **−13,4 dB** **1,024 GHz**;
`mesh.total_cells=145152`, çözücü 107,4 s, yakınsadı.

### Hairpin yeterlilik ifadesi

B2 düzeyi bu fikstür için EMerge düzlemsel ile Fairbeam openEMS arasında S parametresi uyumu
**iddia etmez**. Yukarıdaki openEMS varsayılan yolu nitelikli iki port denetimi değildir
(|S21| > 1, eksik matris). Yalnızca EMerge düzlemsel çalıştırmalar arasında: 15 noktalı
shielded linspace üzerinde geçirme bandı merkezi **1,071429 GHz**; o ızgarada coarse→fine tepe
kayması **0**; open ile shielded tepe frekansı kayması da **0**, open tepede ~0,12 dB daha düşük
ekleme kaybı. Sonuçlar deneysel dışa aktarım olarak kalır (yalnızca `results_exported`). Port
modeli (tahta kenarında toplu şerit-toprak) ve muhafaza seçiminin, besleme/ölçüm düzlemli bir
mikroşerit modal porta göre büyüklükleri kaydırması beklenir.

## Alan düzlemleri (çok frekanslı son örnekleme)

Başarılı bir EMerge Tasarım çözümünden sonra işçi, ikinci bir FEM olmadan `MWField.cutplane` ile
E-alanı kesitlerini örnekler. Varsayılan: bir otomatik frekans (`max_abs_s21`, yoksa
`min_abs_s11`, yoksa bant merkezi). İsteğe bağlı Çalıştır ayarı `field_cut_frequencies_hz`
(≤ **4** pozitif Hz) her isteği en yakın çözülmüş tarama frekansına oturtur, tekilleştirir ve
artan haritaları `field_cuts` / paylaşılan Sonuçlar `field_planes` içine dışa aktarır. Boş liste
= otomatik bir. Oynatma, seçilen harmonik haritada faz animasyonudur; FDTD zaman filmi değildir.

Yönetilen EMerge **3.0.0b12** üzerinde 2026-11-07 ölçümü (Windows), klasik CPW port-map hat
durumu (shielded coarse, 1,2–3,6 GHz × 15 nokta, `accept_lumped_terminals`), `fairbeam serve`
yeniden başlatıldıktan sonra CLI `planar --experimental`:

| Çalıştırma | İstenen Hz | `field_planes` | İşçi duvarı |
| --- | --- | --- | --- |
| Otomatik (liste yok) | — | 1 @ 3,6 GHz (`max_abs_s21`) | **27,4 s** |
| Kullanıcı listesi | 2,4 / 3,5 / 3,0 GHz | 3 @ 2,4 / ≈2,914 / ≈3,429 GHz (`user`) | **27,2 s** |

Ek haritalar çözüm süresini çarpmadı (aynı mesh+tarama sınıfı); maliyet son örnekleme + daha
büyük JSON. Kanıt dizinleri: `.sim/o4-smoke/auto/run`, `.sim/o4-smoke/multi/run`.

## Sonuçlar UI dürüstlüğü (yakınsama)

EMerge dışa aktarımları her zaman `precision_converged: false` tutar (mesh yakınsama belgesi
yok). Paylaşılan Sonuçlar başlığı openEMS FDTD “Yakınsamadı” ifadesini (zaman adımı / alan
enerjisi duruşu) **yeniden kullanmaz**: bitmiş deneysel dışa aktarım bunun yerine **Mesh
sertifikasız** gösterir. Çalıştırma kalitesi zaman adımı sınırı rozetleri EMerge paketleri için
atlanır. Araştırma hâlâ `emergeExp.qa` kullanır (“Bu çalıştırma için mesh, besleme ve sınır
yakınsaması kurulmamıştır.”).

## Lisans ve dağıtım

EMerge yalnızca istek üzerine kurulur. Yönetilen Windows yolu,
`python/fairbeam/emerge_lock/win_amd64-cp313.txt` içindeki hash kilitli bağımlılık kümesini
(`3.0.0b12` sabiti için 50 tekerlek, tahmini indirme 418619020 bayt / yaklaşık 399 MiB, PyPI
tekerlek boyutları 2026-11-04) uygulama veri klasörüne indirir. `3.0.0b12` sabiti için
2026-11-04'te ölçülen yönetilen kurulum **80,9 s** sonra **1421133962 bayt (1355,3 MiB)** idi.
Daha önceki bir `2.8.9` klasörü 74,7 s sonra 1567317171 bayt (1494,7 MiB) ölçüldü. Bu kümeden
hiçbir şey Fairbeam kurucusunun içinde gönderilmez.

Kurulu paketlerden ve üst akış bildirimlerinden kaydedilen bileşen lisans alanları:

- EMerge 3.0.0b12: GPL-2.0-or-later (paket başlıkları; tekerlek LICENSE GPL-2 metni)
- gmsh: GPLv2+ (tekerlek METADATA)
- emsutil 0.8.3: tekerlekte lisans alanı yok; üst akış deposu LICENSE MIT iken tekerlekteki
  `material.py` ve `pyvista/display.py` GPL-2.0-or-later başlıkları taşır
- Intel MKL ve eşlik eden çalışma zamanı paketleri (`mkl`, `intel-openmp`, `onemkl-license` ve
  kilitteki ilgili tekerlekler): Intel Simplified Software License (özel; Intel koşulları altında
  yeniden dağıtılabilir, yalnızca kullanıcı EMerge'i kur istediğinde PyPI'dan kurulur)

Fairbeam GPL-3.0-or-later kalır. Bu özellik yalnızca harici isteğe bağlı bir Python ortamı
kullanır ve üçüncü taraf çözücü ikilileri göndermez. Araştırma paneli, Kur düğmesinden önce
EMerge ve Intel MKL lisans notlarını gösterir.

## Testler

```powershell
$env:PYTHONPATH = "python"
$env:OPENEMS_INSTALL_PATH = "$env:LOCALAPPDATA\org.fairbeam.desktop\runtime\openEMS"
.\.venv\Scripts\python.exe -m unittest discover -s python/tests -p "test_emerge_*.py" -q
```

Bu çözücüsüz testler keşif, yetenekler, analitik değerlendirme, araştırma kuyruğu kabulü, içe
aktarma yalıtımı ve yönetilen venv kurucusunu ağ olmadan çalıştırır. Gerçek yerel çalıştırmalar
ayrıdır ve `--experimental` veya Araştırma paneli Kur / Çalıştır akışıyla açıkça yetkilendirilir.
