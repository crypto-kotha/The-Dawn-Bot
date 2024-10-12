import asyncio
import random
import sys

from typing import Callable, Coroutine, Any, List
from loguru import logger
from loader import config, semaphore, file_operations
from core.bot import Bot
from models import Account
from utils import setup
from console import Console  # You can remove this if you're not using it anymore
from database import initialize_database


async def run_module_safe(
    account: Account, process_func: Callable[[Bot], Coroutine[Any, Any, Any]]
) -> Any:
    async with semaphore:
        bot = Bot(account)
        try:
            if config.delay_before_start.min > 0:
                random_delay = random.randint(config.delay_before_start.min, config.delay_before_start.max)
                logger.info(f"Account: {account.email} | Sleep for {random_delay} sec")
                await asyncio.sleep(random_delay)

            result = await process_func(bot)
            return result
        finally:
            await bot.close_session()


async def process_registration(bot: Bot) -> None:
    operation_result = await bot.process_registration()
    await file_operations.export_result(operation_result, "register")


async def process_farming(bot: Bot) -> None:
    await bot.process_farming()


async def process_export_stats(bot: Bot) -> None:
    data = await bot.process_get_user_info()
    await file_operations.export_stats(data)


async def process_complete_tasks(bot: Bot) -> None:
    operation_result = await bot.process_complete_tasks()
    await file_operations.export_result(operation_result, "tasks")


async def run_module(
    accounts: List[Account], process_func: Callable[[Bot], Coroutine[Any, Any, Any]]
) -> tuple[Any]:
    tasks = [run_module_safe(account, process_func) for account in accounts]
    return await asyncio.gather(*tasks)


async def farm_continuously(accounts: List[Account]) -> None:
    while True:
        random.shuffle(accounts)
        await run_module(accounts, process_farming)
        await asyncio.sleep(10)


async def run() -> None:
    await initialize_database()
    await file_operations.setup_files()

    module_map = {
        "1": ("register", config.accounts_to_register, process_registration),
        "2": ("farm", config.accounts_to_farm, farm_continuously),
        "3": ("complete_tasks", config.accounts_to_farm, process_complete_tasks),
        "4": ("export_stats", config.accounts_to_farm, process_export_stats),
        "5": ("exit", [], None)
    }

    while True:
        print("\nSelect a module:")
        print("1. Register")
        print("2. Farm")
        print("3. Complete tasks")
        print("4. Export statistics")
        print("5. Exit")
        option = input("Enter the option: ").strip()

        if option not in module_map:
            logger.error(f"Invalid option: {option}")
            continue

        module_name, accounts, process_func = module_map[option]

        if module_name == "exit":
            print("Exiting...")
            break

        if not accounts:
            logger.error(f"No accounts for {module_name}")
            continue

        if module_name == "farm":
            await process_func(accounts)
        else:
            await run_module(accounts, process_func)
            input("\n\nPress Enter to continue...")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    setup()
    asyncio.run(run())
