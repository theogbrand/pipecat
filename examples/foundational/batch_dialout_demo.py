import asyncio
import csv
import os
from datetime import datetime

import aiohttp

from pipecat.transports.services.helpers.daily_rest import (
    DailyRESTHelper,
    DailyRoomParams,
    DailyRoomProperties,
)


async def run_bot(id: int, csv_writer):
    async with aiohttp.ClientSession() as aiohttp_session:
        print(f"Starting bot number: {id}")
        rest = DailyRESTHelper(
            daily_api_key=os.getenv("DAILY_API_KEY", ""),
            daily_api_url=os.getenv("DAILY_API_URL", "https://api.daily.co/v1"),
            aiohttp_session=aiohttp_session,
        )
        # Create daily.co room with dialin and dialout enabled
        room_params = DailyRoomParams(properties=DailyRoomProperties(enable_dialout=True))

        # Create the room with the specified parameters
        room = await rest.create_room(room_params)
        # token = await rest.get_token(room.url, 60 * 60, True)
        # print(f"{id}: Room Token: {token}")

        # Check the room properties three times waiting 1 second between each check
        for i in range(3):
            room_info = await rest.get_room_from_url(room.url)
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            if not room_info.config.enable_dialout:
                csv_writer.writerow([id, room_info.config.enable_dialout, current_time])
            await asyncio.sleep(1 * i)


async def main():
    # Open the CSV file in append mode
    with open("output.csv", mode="w", newline="") as file:
        csv_writer = csv.writer(file)
        # Write the header row
        csv_writer.writerow(["bot_id", "enable_dialout", "timestamp"])

        bots = [run_bot(i, csv_writer) for i in range(10)]
        await asyncio.gather(*bots)
        # bots = [run_bot(i, csv_writer) for i in range(10, 20)]
        # await asyncio.gather(*bots)
        # bots = [run_bot(i, csv_writer) for i in range(20, 30)]
        # await asyncio.gather(*bots)
        # bots = [run_bot(i, csv_writer) for i in range(30, 40)]
        # await asyncio.gather(*bots)

        # Read the CSV file into memory
        with open("output.csv", mode="r", newline="") as file:
            csv_reader = csv.reader(file)
            header = next(csv_reader, None)  # Read the header row
            rows = list(csv_reader)  # Read the remaining rows

        if header:
            # Sort the rows by the bot_id column (index 0)
            rows.sort(key=lambda row: int(row[0]))

            # Write the sorted rows to the final CSV file
            with open("output_sorted.csv", mode="w", newline="") as file:
                csv_writer = csv.writer(file)
                csv_writer.writerow(["bot_id", "enable_dialout", "timestamp"])
                csv_writer.writerows(rows)  # Write the sorted rows

        # Write the sorted rows to the final CSV file
        with open("output_sorted.csv", mode="w", newline="") as file:
            csv_writer = csv.writer(file)
            csv_writer.writerow(["bot_id", "enable_dialout", "timestamp"])
            csv_writer.writerows(rows)  # Write the sorted rows

        # Remove the temporary output.csv file
        os.remove("output.csv")


if __name__ == "__main__":
    asyncio.run(main())
