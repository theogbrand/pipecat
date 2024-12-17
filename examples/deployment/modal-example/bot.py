import asyncio
import os
import sys

import aiohttp
from dotenv import load_dotenv

from loguru import logger

load_dotenv(override=True)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")


async def main(room_url: str, token: str):
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.frames.frames import EndFrame, LLMMessagesFrame
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.task import PipelineParams, PipelineTask
    from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
    from pipecat.services.cartesia import CartesiaTTSService
    from pipecat.services.xtts import XTTSService
    from pipecat.services.openai import OpenAILLMService
    from pipecat.transports.services.daily import DailyParams, DailyTransport
    from pipecat.transcriptions.language import Language
    from pipecat.services.whisper import WhisperSTTService, Model
    from pipecat.services.deepgram import DeepgramSTTService
    from pipecat.frames.frames import Frame, TranscriptionFrame
    from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

    # from pipecat.frames.frames import (
    #     BotInterruptionFrame,
    #     StopInterruptionFrame,
    #     UserStartedSpeakingFrame,
    #     UserStoppedSpeakingFrame,
    # )
    from loguru import logger
    from deepgram import LiveOptions

    class SealionLLMService(OpenAILLMService):
        """A service for interacting with Groq's API using the OpenAI-compatible interface.

        This service extends OpenAILLMService to connect to Groq's API endpoint while
        maintaining full compatibility with OpenAI's interface and functionality.

        Args:
            api_key (str): The API key for accessing Groq's API
            base_url (str, optional): The base URL for Groq API. Defaults to "https://api.groq.com/openai/v1"
            model (str, optional): The model identifier to use. Defaults to "llama-3.1-70b-versatile"
            **kwargs: Additional keyword arguments passed to OpenAILLMService
        """

        def __init__(
            self,
            *,
            api_key: str,
            base_url: str = "https://api.sea-lion.ai/v1",
            model: str = "aisingapore/llama3-8b-cpt-sea-lionv2.1-instruct",
            **kwargs,
        ):
            super().__init__(api_key=api_key, base_url=base_url, model=model, **kwargs)

        def create_client(self, api_key=None, base_url=None, **kwargs):
            """Create OpenAI-compatible client for SEALION API endpoint."""
            logger.debug(f"Creating SEALION client with api {base_url}")
            return super().create_client(api_key, base_url, **kwargs)

    class TranscriptionLogger(FrameProcessor):
        async def process_frame(self, frame: Frame, direction: FrameDirection):
            await super().process_frame(frame, direction)

            if isinstance(frame, TranscriptionFrame):
                print(f"Transcription: {frame.text}")

    async with aiohttp.ClientSession() as session:
        transport = DailyTransport(
            room_url,
            token,
            "bot",
            DailyParams(
                audio_out_enabled=True,
                vad_enabled=True,
                vad_analyzer=SileroVADAnalyzer(),
                vad_audio_passthrough=True,
            ),
        )

        # Initialize Whisper STT
        # stt = WhisperSTTService(model=Model.DISTIL_MEDIUM_EN, device="cuda", no_speech_prob=0.4)

        stt = DeepgramSTTService(
            api_key=os.getenv("DEEPGRAM_API_KEY"),
            # live_options=LiveOptions(vad_events=True, utterance_end_ms="1000"),
        )

        # tl = TranscriptionLogger()

        # tts = CartesiaTTSService(
        #     api_key=os.getenv("CARTESIA_API_KEY", ""), voice_id="79a125e8-cd45-4c13-8a67-188112f4dd22"
        # )
        tts = XTTSService(
            aiohttp_session=session,
            voice_id="Marcos Rudaski",
            language=Language.EN,
            base_url="http://13.59.71.92:8000", # deploy own server
        )

        # llm = OpenAILLMService(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4o")
        llm = SealionLLMService(
            api_key=os.getenv("AISG_API_KEY"),
        )

        messages = [
            {
                "role": "system",
                "content": "You are a helpful LLM in a WebRTC call. Your goal is to demonstrate your capabilities in a succinct way. Your output will be converted to audio so don't include special characters in your answers. Respond to what the user said in a creative and helpful way.",
            },
        ]

        context = OpenAILLMContext(messages)
        context_aggregator = llm.create_context_aggregator(context)

        pipeline = Pipeline(
            [
                transport.input(),
                stt,
                # tl,
                context_aggregator.user(),
                llm,
                tts,
                transport.output(),
                context_aggregator.assistant(),
            ]
        )

        task = PipelineTask(
            pipeline,
            PipelineParams(
                allow_interruptions=True,
                enable_metrics=True,
                enable_usage_metrics=True,
                report_only_initial_ttfb=True,
            ),
        )

        # @stt.event_handler("on_speech_started")
        # async def on_speech_started(stt, *args, **kwargs):
        #     await task.queue_frames([BotInterruptionFrame(), UserStartedSpeakingFrame()])

        # @stt.event_handler("on_utterance_end")
        # async def on_utterance_end(stt, *args, **kwargs):
        #     await task.queue_frames([StopInterruptionFrame(), UserStoppedSpeakingFrame()])

        @transport.event_handler("on_first_participant_joined")
        async def on_first_participant_joined(transport, participant):
            await transport.capture_participant_transcription(participant["id"])
            messages.append({"role": "system", "content": "Please introduce yourself to the user."})
            await task.queue_frames([LLMMessagesFrame(messages)])

        @transport.event_handler("on_participant_left")
        async def on_participant_left(transport, participant, reason):
            await task.queue_frame(EndFrame())

        runner = PipelineRunner()

        await runner.run(task)


def _voice_bot_process(room_url: str, token: str):
    asyncio.run(main(room_url, token))
