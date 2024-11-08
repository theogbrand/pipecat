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

        try:
            # Create the room with the specified parameters
            room = await rest.create_room(room_params)
            # token = await rest.get_token(room.url, 60 * 60, True)
            # print(f"{id}: Room Token: {token}")
            room_info = await rest.get_room_from_url(room.url)
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            if not room_info.config.enable_dialout:
                csv_writer.writerow([id, room_info.config.enable_dialout, current_time])

        except Exception as e:
            print(f"Error creating room for bot {id}: {e}")
            print("Sleeping for 10 seconds")
            await asyncio.sleep(10)
            csv_writer.writerow(
                [id, "Rate Limit Error", datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]]
            )


async def main():
    # Open the CSV file in append mode
    with open("output.csv", mode="w", newline="") as file:
        csv_writer = csv.writer(file)
        # Write the header row
        csv_writer.writerow(["bot_id", "enable_dialout", "timestamp"])

        bots = [run_bot(i, csv_writer) for i in range(50)]
        await asyncio.gather(*bots)
        bots = [run_bot(i, csv_writer) for i in range(50, 100)]
        await asyncio.gather(*bots)
        bots = [run_bot(i, csv_writer) for i in range(100, 150)]
        await asyncio.gather(*bots)


if __name__ == "__main__":
    asyncio.run(main())
