# Whisper+Hailo-8 Microservice on FastApi 
### Modification of the [Speech Recognition](https://github.com/hailo-ai/Hailo-Application-Code-Examples/tree/main/runtime/hailo-8/python/speech_recognition) from [Hailo Application Code Examples](https://github.com/hailo-ai/Hailo-Application-Code-Examples/tree/main)

It was created and tested on:
- Raspberry Pi 5 8Gb ORM 
- Ubuntu Server 25.04
- HailoRT v4.20
- Hailo8L

### Requirements
- Hailo8 / Hailo8L / VOSK 
- HailoRT 4.20
- HailoRT PCIe driver
- PyHailoRT (.whl file; Can be downloaded https://hailo.ai/developer-zone/software-downloads; You need file HailoRT – Python package (whl) for Python 3.11, aarch64)
- Python 3.11.*
- Poetry 


### INFO
This repository runs a speech pipeline service for local voice interaction.

It supports:
- FastAPI HTTP endpoints (`/transcribe`, `/ask`, `/ask/health`, `/tts`)
- Wyoming TCP protocol (Home Assistant)
- Hailo Whisper acceleration and VOSK mode
- Local TTS playback workflow through the provided client script

### High-level architecture

Mic -> Whisper (Hailo/VOSK) -> [start word detected] -> accumulate speech  
-> [stop word detected] -> finalized_text (the question)  
-> POST /ask -> GeminiService -> Gemini API  
-> answer text -> POST /tts -> TTSService -> WAV bytes  
-> play through speakers

Start words: `start`, `старт`  
Stop words: `end`, `стоп`, `кінець`

Gemini responses are constrained by a system instruction to be concise (2-5 sentences).


### Pre-Installation
IMPORTANT STEP

You need to install all requirements from official documentation.

Some files from the `developer-zone` that need to be installed are located in requirements_files folder

https://hailo.ai/developer-zone/documentation/hailort-v4-20-0/?sp_referrer=install/install.html

### Installation
1. Clone repository
    ```shell
    git clone https://github.com/MafiaCoconut/whisper-hailo-8l-fastapi.git
    cd whisper-hailo-8l-fastapi
    ```

2. Run the setup script
    ```shell
    python3 setup.py
    ```
   
3. Activate environment 
    ```shell
    source .venv/bin/activate
    ```

4. Install .whl in environment
    ```shell
    pip install requirements_files/hailort-4.20.0-cp311-cp311-linux_aarch64.whl
    ```
   
    The PyHailoRT version must match the installed HailoRT version. NOTE: This step is not necessary for Raspberry Pi 5 users who installed the hailo-all package, since the venv will inherit the system package.



### Run
#### Docker-compose
Using docker-compose instead of Docker will make it much easier to launch the service.
1346792
1. Configure environment values in `docker-compose.yaml` for your mode and model paths:
    ```
    IS_HAILO_ON_DEVICE: "FALSE"
    HAILO_VERSION: "VOSK"                     # HAILO8 | HAILO8L | VOSK
    WHISPER_VARIANT: "base"                  # base | tiny
    VOSK_MODEL_PATH: "requirements_files/vosk-model-uk-v3-lgraph"

    TTS_ENGINE_BINARY: "piper"               # espeak-ng | piper
    TTS_DEFAULT_VOICE: "requirements_files/piper_models/uk/uk_UA-ukrainian_tts-medium.onnx"
    TTS_DEFAULT_SPEED: "170"

    GEMINI_API_KEY: "<your_key>"
    GEMINI_MODEL: "gemini-2.5-flash-lite"
    GEMINI_TIMEOUT_SECONDS: "30"
    ```

2. Run service
    ```shell
    docker compose up --build

    #### When you want to guarantee a completely fresh build and then start services separately
    docker compose build --no-cache
    docker compose up
    

    ```

#### Local
1. Change `.env` file
    ```
    IS_HAILO_ON_DEVICE="FALSE"
    HAILO_VERSION="VOSK" # HAILO8, HAILO8L, VOSK
    VOSK_MODEL_PATH="requirements_files/vosk-model-uk-v3-lgraph"

    TTS_ENGINE_BINARY="piper" # espeak-ng | piper
    TTS_DEFAULT_VOICE="requirements_files/piper_models/uk/uk_UA-ukrainian_tts-medium.onnx"
    TTS_DEFAULT_SPEED="100"

    GEMINI_API_KEY=""
    GEMINI_MODEL="gemini-2.5-flash-lite"
    GEMINI_TIMEOUT_SECONDS="30"

    WHISPER_MULTI_PROCESS_SERVICE="FALSE" # optional: shared Hailo service mode
    ```

   Notes:
   - The service uses one shared long-lived Whisper pipeline instance.
   - Access to that pipeline is protected by a lock, so transcription jobs are processed one-by-one to avoid mixed outputs.
   - If multiple clients call `/transcribe` at the same time, requests are queued and may wait for previous jobs to finish.
   - `WHISPER_MULTI_PROCESS_SERVICE` enables Hailo shared service mode in the pipeline configuration, but API-level access remains serialized for correctness.

2. Run service
    ```shell
    make run
    ```

### Requests

#### TCP (Homeassistant)
Wyoming protocol is using TCP connection with port `10300`

#### API
For standard requests of your services you can use port `54322` with route `/transcribe`

For Gemini QA, use route `/ask`.

For Gemini readiness check, use route `/ask/health`.

For text-to-speech, use route `/tts` (returns `audio/wav`).

You can change port by changing it in `docker-compose.yaml` or `Makefile` in local

#### API examples

`/ask`:
```shell
curl -X POST "http://localhost:54322/ask" \
    -H "Content-Type: application/json" \
    -d '{"question":"Яка зараз погода в Києві?"}'
```

`/ask/health`:
```shell
curl "http://localhost:54322/ask/health"
```

### Minimal TTS (Ukrainian)

The service includes a local TTS endpoint with support for multiple engines.

#### Supported TTS Engines

**espeak-ng** (lightweight, default):
- Lightweight, fast
- Lower quality synthesis
- Install: `sudo apt update && sudo apt install -y espeak-ng`

**Piper** (neural, recommended on RP5):
- Fast neural TTS on ARM/aarch64
- Better speech quality with compact models
- Install: `pip install piper-tts`
- Set `TTS_DEFAULT_VOICE` to a Piper `.onnx` voice model path (or pass that path in request `voice`)

#### Environment Variables

```shell
TTS_ENGINE_BINARY="espeak-ng"      # espeak-ng | piper
TTS_DEFAULT_VOICE="uk"             # espeak voice code OR piper model path
TTS_DEFAULT_SPEED="170"            # 0-450
```

Piper example:

```shell
TTS_ENGINE_BINARY="piper"
TTS_DEFAULT_VOICE="/opt/piper/uk_UA-lada-medium.onnx"
TTS_DEFAULT_SPEED="170"
```

#### Request example

```shell
curl -X POST "http://localhost:54322/tts" \
    -H "Content-Type: application/json" \
    -d '{"text":"Привіт! Це тест українського синтезу.","voice":"uk","speed":170}' \
    --output tts.wav
```



### EXTRA

If you need another .deb and .whl files, you can add them in requirements_files folder and change pathes

Here is also a simple example of how to send voice_files to this service
    
```py
import requests

url = "http://<device-host>:54322/transcribe"
files = {'file': open('male.wav', 'rb')}
resp = requests.post(url, files=files)
print(resp.json())
```

If you have this error, you should reinstall your .venv, because something went wrong due to your installation/configuration
```
[] [] [HailoRT] [error] [infer_model.cpp:868] [validate_bindings] CHECK failed - Input buffer size 0 is different than expected 320000 for input 'tiny-whisper-encoder-10s/input_layer1'
[] [] [HailoRT] [error] [infer_model.cpp:932] [run_async] CHECK_SUCCESS failed with status=HAILO_INVALID_OPERATION(6)
[] [] [HailoRT] [info] [async_infer_runner.cpp:86] [shutdown] Pipeline was aborted. Shutting it down
[] [] [HailoRT] [error] [infer_model.cpp:651] [run_async] CHECK_SUCCESS failed with status=HAILO_INVALID_OPERATION(6)
```


## Client script: microphone listener and transcriber

The script `client/talk.transkribe.py` continuously records microphone audio,
sends each chunk to `/transcribe`, and prints the server response.
When a start/stop session is completed, it can call `/ask` and then `/tts`, then play the returned WAV.
If `--save` is provided, it also saves each chunk to a local WAV file.

### Install dependencies
```shell
pip install requests numpy sounddevice
```

### Run
```shell
python ./client/talk.transkribe.py --chunk-seconds 10
```

### What it does
1. Prints all available audio input devices at startup.
2. If `--input-device` is not provided, asks you to select device index or name.
3. Validates input settings (device, channels, sample rate).
4. Records audio in chunks (default: 10 seconds, 16kHz, mono).
5. Prints chunk level diagnostics (`rms` and `peak`) to help detect silent input.
6. If `--save` is set, saves chunks to `recorded_chunks/chunk_000001.wav`, `chunk_000002.wav`, etc.
7. Sends each chunk as multipart form-data (`file`) to the endpoint.
8. Detects start/stop words and aggregates spoken text between them.
9. On stop word: sends aggregated text to `/ask` (unless `--no-gemini`), then sends answer to `/tts`.
10. Plays WAV audio through speakers.
11. Repeats until stopped with `Ctrl+C`.

### Useful options
- `--url`: API endpoint (default: `http://localhost:54322/transcribe`)
- `--chunk-seconds`: chunk size in seconds (default: `10`)
- `--sample-rate`: input sample rate in Hz (default: `16000`)
- `--channels`: number of channels (default: `1`)
- `--timeout`: HTTP timeout in seconds (default: `60`)
- `--save`: save each recorded chunk as `.wav`
- `--output-dir`: folder for saved WAV chunks (default: `recorded_chunks`)
- `--input-device`: input device index or name
- `--list-devices`: list devices and exit
- `--step-ms`: how far the window moves each time in ms. Step 9000 ms means:0-10, 9-19, 18-28, ...
- `--overlap-seconds`: Minimum overlap 
- `--workers`: is how many parallel transcription threads the client uses to send chunks to your API.
- `--tts-url`: custom TTS endpoint (default derived from `--url`)
- `--ask-url`: custom Gemini endpoint (default derived from `--url`)
- `--no-gemini`: skip `/ask` and speak finalized text directly
- `--tts-voice`: voice passed to `/tts` (default: `uk`)
- `--tts-speed`: speed passed to `/tts` (default: `170`)

### Examples

```shell
python ./client/talk.transkribe.py --chunk-seconds 10 --step-ms 9000 --overlap-seconds 1.0 --workers 1 --save

# Full voice Q&A flow (start/старт ... end/стоп)
python ./client/talk.transkribe.py --chunk-seconds 5 --step-ms 9000 --overlap-seconds 1.0 --workers 1

# Use custom /ask and /tts endpoints
python ./client/talk.transkribe.py \
    --ask-url http://localhost:54322/ask \
    --tts-url http://localhost:54322/tts

# Disable Gemini and speak only captured final text
python ./client/talk.transkribe.py --no-gemini

# Interactive device selection
python ./client/talk.transkribe.py --chunk-seconds 10

# Use specific input device index
python ./client/talk.transkribe.py --chunk-seconds 10 --input-device 2

# Save chunks to a custom folder
python ./client/talk.transkribe.py --save --output-dir ./my_chunks
```


## How to download additional models

### Hailo

Described info [here](https://github.com/hailo-ai/Hailo-Application-Code-Examples/blob/main/runtime/python/speech_recognition/app/download_resources.py)


```python
BASE_HEF = "https://hailo-csdata.s3.eu-west-2.amazonaws.com/resources/whisper"
BASE_ASSETS = "https://hailo-csdata.s3.eu-west-2.amazonaws.com/resources/npy%20files/whisper/decoder_assets"

FILES = {
    "hefs": {
        "hailo8": {
            "tiny": [
                f"{BASE_HEF}/h8/tiny-whisper-decoder-fixed-sequence-matmul-split.hef",
                f"{BASE_HEF}/h8/tiny-whisper-encoder-10s_15dB.hef",
            ],
            "base": [
                f"{BASE_HEF}/h8/base-whisper-decoder-fixed-sequence-matmul-split.hef",
                f"{BASE_HEF}/h8/base-whisper-encoder-5s.hef",
            ],
        }
    },
    "assets": {
        "tiny": [
            f"{BASE_ASSETS}/tiny/decoder_tokenization/onnx_add_input_tiny.npy",
            f"{BASE_ASSETS}/tiny/decoder_tokenization/token_embedding_weight_tiny.npy",
        ],
        "base": [
            f"{BASE_ASSETS}/base/decoder_tokenization/onnx_add_input_base.npy",
            f"{BASE_ASSETS}/base/decoder_tokenization/token_embedding_weight_base.npy",
        ],
        "tiny.en": [
            f"{BASE_ASSETS}/tiny.en/decoder_tokenization/onnx_add_input_tiny.en.npy",
            f"{BASE_ASSETS}/tiny.en/decoder_tokenization/token_embedding_weight_tiny.en.npy",
        ]
    },
}

```

### Vosk

[Documentation](https://alphacephei.com/vosk/install)

VOSK model can be found on [official site](https://alphacephei.com/vosk/models)
- on pi5 vosk model perform better (quality and speed) then hailo models. Checke with:
 - vosk-model-uk-v3
 - vosk-model-uk-v3-lgraph
 
## Errors

> pyproject.toml changed significantly since poetry.lock was last generated. Run `poetry lock` to fix the lock file. 
Is fixed by running 

`python3 -m poetry lock`

## Future


Impmenet `ukrainian-tts (robinhad)`
Pure Python, ESPNET-based, MIT license
Multiple voices (Oleksa, Dmytro, etc.) with automatic stress placement
Explicitly supports Linux ARM in README
Install: pip install git+https://github.com/robinhad/ukrainian-tts.git
Heavier than Piper (loads ESPNET models), but higher quality synthesis
237 stars, active Ukrainian community