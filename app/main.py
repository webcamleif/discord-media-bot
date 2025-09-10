import asyncio, logging
import uvicorn
from app.admin import build_app
from app.store import load_config, load_admin
from app.bot import BotManager

logging.basicConfig(level=logging.INFO)

bot = BotManager()
app = build_app(bot)

@app.on_event("startup")
async def startup():
    cfg = load_config()
    # Start bot only if a setup exists or you can still run (it simply won't start without token)
    asyncio.create_task(bot.start(cfg))

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=False)

