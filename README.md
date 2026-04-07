# Whisper+Hailo-8 Microservice on FastApi 
### Modification of the [Speech Recognition](https://github.com/hailo-ai/Hailo-Application-Code-Examples/tree/main/runtime/hailo-8/python/speech_recognition) from [Hailo Application Code Examples](https://github.com/hailo-ai/Hailo-Application-Code-Examples/tree/main)

It was created and tested on:
- Raspberry Pi 5 8Gb ORM 
- Ubuntu Server 25.04
- HailoRT v4.20
- Hailo8L

### Requirements
- Hailo8 / Hailo8L
- HailoRT 4.20
- HailoRT PCIe driver
- PyHailoRT (.whl file; Can be downloaded https://hailo.ai/developer-zone/software-downloads; You need file HailoRT – Python package (whl) for Python 3.11, aarch64)
- Python 3.11.*
- Poetry 


### INFO
It is a standalone service that uses the Hailo-8(L) chip to speed up voice recognition.

It can accept API and TCP requests.

It works correctly with the wyoming protocol for Homeassistant integration


### Pre-Installation
IMPORTANT STEP

You need to install all requirements from official documentation.

Some files from the `developer-zone` that need to be installed are located in hailort_requirements_files folder

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
    pip install hailort_requirements_files/hailort-4.20.0-cp311-cp311-linux_aarch64.whl
    ```
   
    The PyHailoRT version must match the installed HailoRT version. NOTE: This step is not necessary for Raspberry Pi 5 users who installed the hailo-all package, since the venv will inherit the system package.

### Run
#### Docker-compose
Using docker-compose instead of Docker will make it much easier to launch the service.

1. If you have "Hailo-8" you need to open docker-compose.yaml and change ENV value `HAILO_VERSION`

2. Run service
    ```shell
    docker compose up --build
    ```

#### Local
1. Change .env file
    ```
    IS_HAILO_ON_DEVICE="TRUE" # if you want to run service NOT it RP5, you need to change this value on "FALSE"
    HAILO_VERSION="HAILO8L" # This value can be only "HAILO8L" or "HAILO8"
    WHISPER_MULTI_PROCESS_SERVICE="FALSE" # optional: set TRUE to enable Hailo shared multi-process service mode
    ```

   Notes:
   - The service uses one shared long-lived Whisper pipeline instance.
   - Access to that pipeline is protected by a lock, so transcription jobs are processed one-by-one to avoid mixed outputs.
   - If multiple clients call `/transcribe` at the same time, requests are queued and may wait for previous jobs to finish.
   - `WHISPER_MULTI_PROCESS_SERVICE` enables Hailo shared service mode in the pipeline configuration, but API-level access remains serialized for correctness.

2. In file app/application/pipelines/hailo_whisper_pipeline you need to comment out `line 11`
    ```
    from hailo_platform import (HEF, VDevice, HailoSchedulingAlgorithm, FormatType)
    ```

3. Run service
    ```shell
    make run
    ```

### Requests

#### TCP (Homeassistant)
Wyoming protocol is using TCP connection with port `10300`

#### API
For standard requests of your services you can use port `54322` with route `/transcribe`

You can change port by changing it in `docker-compose.yaml` or `Makefile` in local



### EXTRA

If you need another .deb and .whl files, you can add them in hailort_requirements_files folder and change pathes

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
8. Prints HTTP status and JSON/text response to console.
9. Repeats until stopped with `Ctrl+C`.

### Useful options
- `--url`: API endpoint (default: `http://localhost:54322/transcribe`)
- `--chunk-seconds`: chunk size in seconds (default: `10`)
- `--sample-rate`: input sample rate in Hz (default: `16000`)
- `--channels`: number of channels (default: `0`)
- `--timeout`: HTTP timeout in seconds (default: `60`)
- `--save`: save each recorded chunk as `.wav`
- `--output-dir`: folder for saved WAV chunks (default: `recorded_chunks`)
- `--input-device`: input device index or name
- `--list-devices`: list devices and exit
- `--step-ms`: how far the window moves each time in ms. Step 9000 ms means:0-10, 9-19, 18-28, ...
- `--overlap-seconds`: Minimum overlap 
- `--workers`: is how many parallel transcription threads the client uses to send chunks to your API.

### Examples

```shell
python ./client/talk.transkribe.py --chunk-seconds 10 --step-ms 9000 --overlap-seconds 1.0 --workers 1 --save

# Interactive device selection
python ./client/talk.transkribe.py --chunk-seconds 10

# Use specific input device index
python ./client/talk.transkribe.py --chunk-seconds 10 --input-device 2

# Save chunks to a custom folder
python ./client/talk.transkribe.py --save --output-dir ./my_chunks
```


## How to download additional models

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