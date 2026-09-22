# GLİ Telegram bildirim servisi (TEST MODU)

Bu servis Render üzerinde sürekli çalışır ve bildirimleri yalnız
`TELEGRAM_TEST_CHAT_ID` ile belirtilen hesaba yollar.

## Render kurulumu

1. Bu klasörü GitHub deposuna yükleyin.
2. Render'da **New > Blueprint** ile depoyu seçin.
3. `TELEGRAM_BOT_TOKEN` alanına BotFather'ın verdiği tokenı girin.
4. `TELEGRAM_TEST_CHAT_ID` alanına kendi sayısal Telegram chat kimliğinizi girin.
5. Render'ın oluşturduğu `RELAY_SHARED_SECRET` değerini güvenli bir yere kopyalayın.
6. Servis adresini ve gizli anahtarı kurum bilgisayarında ayarlayın:

```bat
setx GLI_TELEGRAM_RELAY_URL "https://gli-telegram-bildirim.onrender.com"
setx GLI_TELEGRAM_RELAY_SECRET "RENDER_DAKI_GIZLI_ANAHTAR"
setx GLI_TELEGRAM_ENABLED "1"
```

Komutlardan sonra programı kapatıp yeniden açın. Bot tokenını kurum
bilgisayarına yazmayın. TEST MODU servis kodunda zorunludur; alıcı chat kimliği
istemciden kabul edilmez.

## Telegram chat kimliğini bulma

Botunuza Telegram'dan `/start` gönderin. Ardından tarayıcıdan aşağıdaki adresi
açıp yanıttaki `message.chat.id` sayısını kullanın:

`https://api.telegram.org/bot<BOT_TOKEN>/getUpdates`

Tokenı kimseyle paylaşmayın ve ekran görüntüsünde göstermeyin.
