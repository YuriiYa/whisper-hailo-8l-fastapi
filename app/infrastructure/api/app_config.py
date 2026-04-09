from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging
import asyncio
from infrastructure.api import api_config, cors
from infrastructure.config import whisper_hailo
from infrastructure.config.runtime_env import RuntimeEnvConfig
from infrastructure.tcp_server.wyoming_tsp_server_config import start_tcp_server
from dotenv import load_dotenv



load_dotenv()

app = FastAPI()

cors.config(app=app)
system_logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    system_logger.info("Program is starting")

    system_logger.info("API configuration is started")
    api_config.config(app=app)
    runtime_env = RuntimeEnvConfig.from_env()

    if runtime_env.can_transcribe:
        system_logger.info(
            "Initializing transcription pipeline. IS_HAILO_ON_DEVICE=%s, HAILO_VERSION=%s",
            runtime_env.is_hailo_on_device,
            runtime_env.hailo_version,
        )
        whisper_hailo.config(app=app, _model=runtime_env.hailo_version)

    system_logger.info("Starting Wyoming TCP server")
    asyncio.create_task(start_tcp_server())

    system_logger.info("Program is started")
    yield
    system_logger.info("Program is stopping")
    if runtime_env.can_transcribe:
        whisper_hailo.whisper_hailo_stop()
    system_logger.info("Program is stopped")


app.router.lifespan_context = lifespan
