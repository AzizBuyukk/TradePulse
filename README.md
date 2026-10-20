# TradePulse

TradePulse, işlemlerini kaydedip analiz etmen için geliştirilmiş kişisel bir trade günlüğü. Sadece "kazandım mı, kaybettim mi" sorusuna değil, **neden** kazandığına ya da kaybettiğine de odaklanır: her işlemde setup'ını, hatalarını ve işlemin üç aşamasında ne hissettiğini kaydedersin, uygulama da hangi durumda daha iyi işlem yaptığını sayılarla gösterir.

Windows masaüstü uygulaması olarak çalışır. Tüm veriler senin bilgisayarındaki SQL Server'da durur; internete hiçbir şey gönderilmez.

## Neler sunuyor?

### İşlem kaydı
- Tarih, saat, seans (New York, London, Asya), enstrüman, yön (Long/Short) ve işlem türü (Demo/Gerçek)
- Giriş, stop, hedef ve çıkış fiyatları; **planlanan RR, R sonucu ve P&L otomatik hesaplanır**
- Risk tutarı ($) ve risk yüzdesi; P&L elle de girilebilir
- Setup etiketleri (FVG, Order Block, Liquidity Sweep, MSS/CHoCH vb.) ve kendi setup'larını ekleme
- Hata etiketleri (erken giriş, stopu oynatma, FOMO, intikam işlemi vb.)
- 1–5 arası "kurallara uyum" puanı, analiz notu ve işlemden çıkarılan ders

### Duygu takibi
- **Girerken, işlemdeyken ve kapanınca** ne hissettiğini ayrı ayrı seçme
- Her aşama için serbest not
- Raporlarda "hangi duyguyla girdiğimde kazanıyorum?" sorusunun cevabı

### Grafik ekran görüntüleri
- Her işleme ayrı **HTF** (4H/Günlük) ve **LTF** (15m/5m/1m) görselleri
- Dosya seçerek, sürükleyip bırakarak veya **Ctrl+V** ile yapıştırarak ekleme
- İşlem detayında büyük görüntüleme

### Dashboard
- Net P&L, profit factor, ortalama kazanç/kayıp oranı
- İşlem bazında ve gün bazında **win rate** halka grafikleri
- **Günlük kümülatif P&L** ve günlük net P&L grafikleri
- Aylık takvim: her günün P&L'i, işlem sayısı, win rate ve haftalık toplamlar
- **Defter skoru:** win rate, profit factor, kazanç/kayıp oranı, gün win rate ve kurala uyumdan hesaplanan 0–100 puan ve radar grafiği
- Otomatik çıkarımlar: en iyi ve en kötü giriş duygusu, en çok kaybettiren hata, en kârlı setup

### İşlem günlüğü ve raporlar
- Tüm işlemleri arama ve filtreleme (sonuç, setup, Demo/Gerçek, ay)
- Setup, giriş/işlem sırası/sonuç duygusu, hata, seans, enstrüman, haftanın günü ve kurala uyuma göre **win rate, net P&L ve R** raporları

### Diğer
- Gece ve gündüz modu
- Veriler SQL Server'da: SSMS'ten kendi sorgularını yazabilirsin (`dbo.vTradeSummary` görünümü hazır)
- Tek tıkla açılan `.exe` olarak paketlenebilir


## Gereksinimler

- Windows 10 veya 11
- SQL Server (Express, Developer veya LocalDB) ve Windows Authentication ile bağlanabilen bir hesap
- Python 3.12 veya 3.13
- ODBC Driver 17 veya 18 for SQL Server (genelde SQL Server ile birlikte gelir)

## Kurulum

```bat
git clone https://github.com/<kullanici-adin>/TradePulse.git
cd TradePulse
kurulum.bat
```

Sonra `TradePulse.bat` ile aç. İlk açılışta `TradePulse` veritabanı ve tablolar kendiliğinden oluşur.

Sunucuya bağlanamazsa uygulama sunucu adını sorar. SSMS'te "Server name" alanına ne yazıyorsan onu yaz, örneğin `localhost\SQLEXPRESS`. Ayarlar `config.ini` dosyasına kaydedilir. Örnek ayar dosyası `config.example.ini`.

Tek tıkla açılan bir `.exe` için `exe_yap.bat` çalıştır.

## Proje yapısı

| Dosya | Görevi |
| --- | --- |
| `app.py` | Yerel web sunucusu, API ve uygulama penceresi (pywebview, yoksa Edge uygulama modu) |
| `db.py` | SQL Server bağlantısı, tablo oluşturma, işlem okuma ve yazma |
| `web/index.html` | Arayüz (HTML, CSS, JavaScript) |
| `_python.bat` | Bilgisayardaki Python'u bulur; diğer .bat dosyaları kullanır |
| `kurulum.bat`, `TradePulse.bat`, `hata_ayikla.bat`, `exe_yap.bat` | Kurulum, çalıştırma, hata ayıklama, exe derleme |

## Veritabanı

| Tablo | İçerik |
| --- | --- |
| `dbo.Trades` | Her işlem: tarih, fiyatlar, risk, P&L, R, sonuç, 3 aşamalı duygu ve notlar |
| `dbo.TradeTags` | Setup'lar (`TagType = 'setup'`) ve hatalar (`TagType = 'mistake'`) |
| `dbo.TradeImages` | HTF/LTF ekran görüntüsü dosya adları (dosyalar `data/images` klasöründe) |
| `dbo.vTradeSummary` | Hesaplanmış R, P&L ve sonuçla hazır görünüm |

Örnek sorgu:

```sql
-- Giriş duygusuna göre win rate ve toplam P&L
SELECT EmoIn,
       COUNT(*) AS Islem,
       AVG(CASE WHEN Result = 'Win' THEN 1.0 WHEN Result = 'Loss' THEN 0.0 END) AS WinRate,
       SUM(PnlUsd) AS ToplamPnl
FROM dbo.vTradeSummary
GROUP BY EmoIn
ORDER BY ToplamPnl DESC;
```

## Yedekleme

- SSMS'te `TradePulse` veritabanına sağ tıkla, sonra **Tasks > Back Up**.
- `data/images` klasörünü kopyala.

## Sorun giderme

- Uygulama açılmıyorsa `hata_ayikla.bat` ile aç; hata pencerede görünür ve `data/hata.log` dosyasına yazılır.
- "ODBC Driver" hatasında Microsoft'un "ODBC Driver 18 for SQL Server" sürücüsünü kur.
