import asyncio
from config.config import dp, bot
from commands.commands import start, tasks_command,download_command,download_links
async def main():
    await dp.start_polling(bot)
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
