#!/bin/bash

# Check if the HEFs directory exists and delete it if it does
if [ -d "app/infrastructure/hefs" ]; then
  echo "Deleting existing 'app/infrastructure/hefs' directory..."
  rm -rf app/infrastructure/hefs
fi

# Create tiny HEF directories
mkdir -p app/infrastructure/hefs/h8/tiny

echo "Downloading tiny-whisper-decoder for Hailo-8..."
wget -P app/infrastructure/hefs/h8/tiny "https://hailo-csdata.s3.eu-west-2.amazonaws.com/resources/hefs/h8/tiny-whisper-decoder-fixed-sequence-matmul-split.hef"

echo "Downloading tiny-whisper-encoder for Hailo-8..."
wget -P app/infrastructure/hefs/h8/tiny "https://hailo-csdata.s3.eu-west-2.amazonaws.com/resources/hefs/h8/tiny-whisper-encoder-10s_15dB.hef"


# Create tiny HEF directories for Hailo-8L
mkdir -p app/infrastructure/hefs/h8l/tiny

echo "Downloading tiny-whisper-decoder for Hailo-8L..."
wget -P app/infrastructure/hefs/h8l/tiny "https://hailo-csdata.s3.eu-west-2.amazonaws.com/resources/hefs/h8l_rpi/tiny-whisper-decoder-fixed-sequence-matmul-split_h8l.hef"

echo "Downloading tiny-whisper-encoder for Hailo-8L..."
wget -P app/infrastructure/hefs/h8l/tiny "https://hailo-csdata.s3.eu-west-2.amazonaws.com/resources/hefs/h8l_rpi/tiny-whisper-encoder-10s_15dB_h8l.hef"


# Create base HEF directory for Hailo-8
mkdir -p app/infrastructure/hefs/h8/base

echo "Downloading base-whisper-decoder for Hailo-8..."
wget -P app/infrastructure/hefs/h8/base "https://hailo-csdata.s3.eu-west-2.amazonaws.com/resources/whisper/h8/base-whisper-decoder-fixed-sequence-matmul-split.hef"

echo "Downloading base-whisper-encoder for Hailo-8..."
wget -P app/infrastructure/hefs/h8/base "https://hailo-csdata.s3.eu-west-2.amazonaws.com/resources/whisper/h8/base-whisper-encoder-5s.hef"


if [ -d "app/infrastructure/decoder_assets" ]; then
  echo "Deleting existing 'app/infrastructure/decoder_assets' directory..."
  rm -rf app/infrastructure/decoder_assets
fi


echo "Creating new 'decoder_assets/tiny' directory..."
mkdir -p app/infrastructure/decoder_assets/tiny
mkdir -p app/infrastructure/decoder_assets/tiny/decoder_tokenization

echo "Downloading decoder assets..."
wget -P app/infrastructure/decoder_assets/tiny/decoder_tokenization "https://hailo-csdata.s3.eu-west-2.amazonaws.com/resources/npy%20files/whisper/decoder_assets/tiny/decoder_tokenization/onnx_add_input_tiny.npy"
wget -P app/infrastructure/decoder_assets/tiny/decoder_tokenization "https://hailo-csdata.s3.eu-west-2.amazonaws.com/resources/npy%20files/whisper/decoder_assets/tiny/decoder_tokenization/token_embedding_weight_tiny.npy"


echo "Creating new 'decoder_assets/base' directory..."
mkdir -p app/infrastructure/decoder_assets/base
mkdir -p app/infrastructure/decoder_assets/base/decoder_tokenization

echo "Downloading base decoder assets..."
wget -P app/infrastructure/decoder_assets/base/decoder_tokenization "https://hailo-csdata.s3.eu-west-2.amazonaws.com/resources/npy%20files/whisper/decoder_assets/base/decoder_tokenization/onnx_add_input_base.npy"
wget -P app/infrastructure/decoder_assets/base/decoder_tokenization "https://hailo-csdata.s3.eu-west-2.amazonaws.com/resources/npy%20files/whisper/decoder_assets/base/decoder_tokenization/token_embedding_weight_base.npy"


echo "Download complete."


# ---------------------------------------------------------------------------
# VOSK model (used when HAILO_VERSION=VOSK)
# ---------------------------------------------------------------------------
VOSK_MODEL_NAME="vosk-model-uk-v3-lgraph"
VOSK_MODEL_ZIP="${VOSK_MODEL_NAME}.zip"
VOSK_MODEL_URL="https://alphacephei.com/vosk/models/${VOSK_MODEL_ZIP}"

if [ -d "${VOSK_MODEL_NAME}" ]; then
  echo "VOSK model '${VOSK_MODEL_NAME}' already exists, skipping download."
else
  echo "Downloading VOSK model ${VOSK_MODEL_NAME}..."
  wget -q --show-progress "${VOSK_MODEL_URL}"
  echo "Extracting ${VOSK_MODEL_ZIP}..."
  unzip -q "${VOSK_MODEL_ZIP}"
  rm "${VOSK_MODEL_ZIP}"
  echo "VOSK model ready at: ${VOSK_MODEL_NAME}"
fi



