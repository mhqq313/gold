import logging
import re
from datetime import datetime
from typing import Dict, Optional

import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = "7803211933:AAExloLFtFXg0eInbFwECSADBe9XK4SmBu0"

class GoldPriceService:
    SOURCES = [
        {
            'name': 'Jijinhao',
            'url': 'https://api.jijinhao.com/sQuoteCenter/realTime.htm?code=JO_92233',
            'parser': lambda text: GoldPriceService.parse_jijinhao(text)
        }
    ]

    @staticmethod
    def parse_jijinhao(text):
        try:
            import re
            raw_data = re.findall(r'"(.*),"', text)[0].split(',')
            return {
                'price': float(raw_data[3]),
                'high': float(raw_data[4]),
                'low': float(raw_data[5]),
                'open': float(raw_data[38]),
                'close': float(raw_data[2]),
                'timestamp': datetime.now()
            }
        except Exception as e:
            logger.warning(f"فشل في تحليل بيانات jijinhao: {e}")
            return None

    async def get_price(self) -> Optional[Dict]:
        for source in self.SOURCES:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        source['url'],
                        timeout=10
                    )
                if response.status_code == 200:
                    # jijinhao يرجع نص وليس JSON
                    data = source['parser'](response.text)
                    if data:
                        return data
            except Exception as e:
                logger.warning(f"فشل مصدر {source['name']}: {str(e)}")
                continue
        logger.error("فشل جميع مصادر البيانات")
        return None

class GoldPriceBot:
    def __init__(self):
        self.application = Application.builder().token(TOKEN).build()
        self.price_service = GoldPriceService()
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("price", self.get_price))
        self.application.job_queue.run_repeating(
            self.update_price,
            interval=60.0,
            first=5.0
        )

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🟡 مرحباً بك في بوت تتبع أسعار الذهب!\n"
            "استخدم /price لعرض السعر الحالي."
        )

    async def get_price(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        price_data = await self.price_service.get_price()
        if price_data:
            change = price_data['price'] - price_data['close']
            change_pct = (change / price_data['close']) * 100
            change_emoji = "📈" if change >= 0 else "📉"
            message = (
                f"💰 <b>سعر الذهب الحالي:</b>\n"
                f"• السعر: {price_data['price']:.2f} دولار\n"
                f"• التغيير: {change_emoji} {change:+.2f} ({change_pct:+.2f}%)\n"
                f"• الأعلى اليومي: {price_data['high']:.2f}\n"
                f"• الأدنى اليومي: {price_data['low']:.2f}\n"
                f"⏱ آخر تحديث: {price_data['timestamp'].strftime('%H:%M:%S')}"
            )
        else:
            message = "⚠️ تعذر جلب سعر الذهب حالياً. يرجى المحاولة لاحقاً"
        await update.message.reply_text(message, parse_mode='HTML')

    async def update_price(self, context: ContextTypes.DEFAULT_TYPE):
        price_data = await self.price_service.get_price()
        if price_data:
            logger.info(f"تحديث السعر: {price_data['price']:.2f}")

    def run(self):
        logger.info("Starting Gold Price Bot...")
        self.application.run_polling()

if __name__ == "__main__":
    try:
        bot = GoldPriceBot()
        bot.run()
    except Exception as e:
        logger.error(f"خطأ في تشغيل البوت: {e}")