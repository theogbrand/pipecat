import asyncio
import csv
import os
import subprocess
import time
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
        exp = time.time() + 120
        room_params = DailyRoomParams(
            properties=DailyRoomProperties(
                exp=exp,
                enable_dialout=True,
                eject_at_room_exp=True,
            )
        )

        try:
            # Create the room with the specified parameters
            room = await rest.create_room(room_params)
            # Create token with owner permissions
            token = await rest.get_token(
                room_url=room.url,
                expiry_time=60 * 60,
                owner=True,  # Ensure the token has owner permissions
            )
            # print(f"{id}: Room Token: {token}")
            room_info = await rest.get_room_from_url(room.url)
            # print(f"{id}: Room Info: {room_info}")
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            # Other party joined or not and start dialout joined
            csv_writer.writerow([id, room_info.config.enable_dialout, current_time])

        except Exception as e:
            print(f"Error creating room for bot {id}: {e}")
            print("Sleeping for 10 seconds")
            await asyncio.sleep(10)
            csv_writer.writerow(
                [id, "Rate Limit Error", datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]]
            )

        bot_proc = f"python3 -m batch_dialout_bot -u {room.url} -t {token} -i {id}"

        try:
            subprocess.Popen(
                [bot_proc], shell=True, bufsize=1, cwd=os.path.dirname(os.path.abspath(__file__))
            )
        except Exception as e:
            print(f"Failed to start subprocess: {e}")


async def main():
    # Open the CSV file in append mode
    with open("output.csv", mode="w", newline="") as file:
        csv_writer = csv.writer(file)
        # Write the header row
        csv_writer.writerow(["bot_id", "enable_dialout", "timestamp"])

        for _ in range(2):
            bots = [run_bot(i, csv_writer) for i in range(12)]
            await asyncio.gather(*bots)
            print("Batch finished waiting 15 seconds...")
            await asyncio.sleep(15)
            print("Finished waiting 15 seconds...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Parent process interrupted")
