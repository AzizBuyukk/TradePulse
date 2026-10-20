# TradePulse

ICT tarzı işlemler için kişisel trade günlüğü. Windows masaüstü uygulaması; veriler yerel SQL Server'da durur.

## Özellikler

- **İşlem kaydı:** giriş, stop, hedef ve çıkış fiyatları; R ve P&L otomatik hesaplanır.
- **Duygu takibi:** girişte, işlem sırasında ve kapanışta ne hissettiğin, her aşama için not.
- **Grafikler:** HTF ve LTF ekran görüntüleri; dosya seç, sürükle bırak veya Ctrl+V ile yapıştır.
- **Dashboard:** kümülatif P&L, işlem ve gün bazında win rate, profit factor, aylık takvim, defter skoru.
- **Raporlar:** setup, duygu, hata, seans, enstrüman ve güne göre win rate ve P&L.
- Gece ve gündüz modu.

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
