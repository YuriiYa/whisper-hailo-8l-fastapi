#!/bin/bash

set -e
REQ="requirements_files"

# ---------------------------------------------------------------------------
# HEF files
# ---------------------------------------------------------------------------

mkdir -p "${REQ}/hefs/h8/tiny"

HEF_H8_TINY_DECODER="${REQ}/hefs/h8/tiny/tiny-whisper-decoder-fixed-sequence-matmul-split.hef"
if [ -f "${HEF_H8_TINY_DECODER}" ]; then
  echo "Already exists, skipping: ${HEF_H8_TINY_DECODER}"
else
  echo "Downloading tiny-whisper-decoder for Hailo-8..."
  wget -P "${REQ}/hefs/h8/tiny" "https://hailo-csdata.s3.eu-west-2.amazonaws.com/resources/hefs/h8/tiny-whisper-decoder-fixed-sequence-matmul-split.hef"
fi

HEF_H8_TINY_ENCODER="${REQ}/hefs/h8/tiny/tiny-whisper-encoder-10s_15dB.hef"
if [ -f "${HEF_H8_TINY_ENCODER}" ]; then
  echo "Already exists, skipping: ${HEF_H8_TINY_ENCODER}"
else
  echo "Downloading tiny-whisper-encoder for Hailo-8..."
  wget -P "${REQ}/hefs/h8/tiny" "https://hailo-csdata.s3.eu-west-2.amazonaws.com/resources/hefs/h8/tiny-whisper-encoder-10s_15dB.hef"
fi


mkdir -p "${REQ}/hefs/h8l/tiny"

HEF_H8L_TINY_DECODER="${REQ}/hefs/h8l/tiny/tiny-whisper-decoder-fixed-sequence-matmul-split_h8l.hef"
if [ -f "${HEF_H8L_TINY_DECODER}" ]; then
  echo "Already exists, skipping: ${HEF_H8L_TINY_DECODER}"
else
  echo "Downloading tiny-whisper-decoder for Hailo-8L..."
  wget -P "${REQ}/hefs/h8l/tiny" "https://hailo-csdata.s3.eu-west-2.amazonaws.com/resources/hefs/h8l_rpi/tiny-whisper-decoder-fixed-sequence-matmul-split_h8l.hef"
fi

HEF_H8L_TINY_ENCODER="${REQ}/hefs/h8l/tiny/tiny-whisper-encoder-10s_15dB_h8l.hef"
if [ -f "${HEF_H8L_TINY_ENCODER}" ]; then
  echo "Already exists, skipping: ${HEF_H8L_TINY_ENCODER}"
else
  echo "Downloading tiny-whisper-encoder for Hailo-8L..."
  wget -P "${REQ}/hefs/h8l/tiny" "https://hailo-csdata.s3.eu-west-2.amazonaws.com/resources/hefs/h8l_rpi/tiny-whisper-encoder-10s_15dB_h8l.hef"
fi


mkdir -p "${REQ}/hefs/h8/base"

HEF_H8_BASE_DECODER="${REQ}/hefs/h8/base/base-whisper-decoder-fixed-sequence-matmul-split.hef"
if [ -f "${HEF_H8_BASE_DECODER}" ]; then
  echo "Already exists, skipping: ${HEF_H8_BASE_DECODER}"
else
  echo "Downloading base-whisper-decoder for Hailo-8..."
  wget -P "${REQ}/hefs/h8/base" "https://hailo-csdata.s3.eu-west-2.amazonaws.com/resources/whisper/h8/base-whisper-decoder-fixed-sequence-matmul-split.hef"
fi

HEF_H8_BASE_ENCODER="${REQ}/hefs/h8/base/base-whisper-encoder-5s.hef"
if [ -f "${HEF_H8_BASE_ENCODER}" ]; then
  echo "Already exists, skipping: ${HEF_H8_BASE_ENCODER}"
else
  echo "Downloading base-whisper-encoder for Hailo-8..."
  wget -P "${REQ}/hefs/h8/base" "https://hailo-csdata.s3.eu-west-2.amazonaws.com/resources/whisper/h8/base-whisper-encoder-5s.hef"
fi


# ---------------------------------------------------------------------------
# Decoder tokenization assets
# ---------------------------------------------------------------------------

mkdir -p "${REQ}/decoder_assets/tiny/decoder_tokenization"

NPY_TINY_ADD="${REQ}/decoder_assets/tiny/decoder_tokenization/onnx_add_input_tiny.npy"
if [ -f "${NPY_TINY_ADD}" ]; then
  echo "Already exists, skipping: ${NPY_TINY_ADD}"
else
  echo "Downloading decoder assets (tiny)..."
  wget -P "${REQ}/decoder_assets/tiny/decoder_tokenization" "https://hailo-csdata.s3.eu-west-2.amazonaws.com/resources/npy%20files/whisper/decoder_assets/tiny/decoder_tokenization/onnx_add_input_tiny.npy"
fi

NPY_TINY_EMB="${REQ}/decoder_assets/tiny/decoder_tokenization/token_embedding_weight_tiny.npy"
if [ -f "${NPY_TINY_EMB}" ]; then
  echo "Already exists, skipping: ${NPY_TINY_EMB}"
else
  wget -P "${REQ}/decoder_assets/tiny/decoder_tokenization" "https://hailo-csdata.s3.eu-west-2.amazonaws.com/resources/npy%20files/whisper/decoder_assets/tiny/decoder_tokenization/token_embedding_weight_tiny.npy"
fi


mkdir -p "${REQ}/decoder_assets/base/decoder_tokenization"

NPY_BASE_ADD="${REQ}/decoder_assets/base/decoder_tokenization/onnx_add_input_base.npy"
if [ -f "${NPY_BASE_ADD}" ]; then
  echo "Already exists, skipping: ${NPY_BASE_ADD}"
else
  echo "Downloading decoder assets (base)..."
  wget -P "${REQ}/decoder_assets/base/decoder_tokenization" "https://hailo-csdata.s3.eu-west-2.amazonaws.com/resources/npy%20files/whisper/decoder_assets/base/decoder_tokenization/onnx_add_input_base.npy"
fi

NPY_BASE_EMB="${REQ}/decoder_assets/base/decoder_tokenization/token_embedding_weight_base.npy"
if [ -f "${NPY_BASE_EMB}" ]; then
  echo "Already exists, skipping: ${NPY_BASE_EMB}"
else
  wget -P "${REQ}/decoder_assets/base/decoder_tokenization" "https://hailo-csdata.s3.eu-west-2.amazonaws.com/resources/npy%20files/whisper/decoder_assets/base/decoder_tokenization/token_embedding_weight_base.npy"
fi


echo "Download complete."


# ---------------------------------------------------------------------------
# VOSK model (used when HAILO_VERSION=VOSK)
# ---------------------------------------------------------------------------
VOSK_MODEL_NAME="vosk-model-uk-v3-lgraph"
VOSK_MODEL_ZIP="${VOSK_MODEL_NAME}.zip"
VOSK_MODEL_URL="https://alphacephei.com/vosk/models/${VOSK_MODEL_ZIP}"
VOSK_MODEL_DEST="${REQ}/${VOSK_MODEL_NAME}"

if [ -d "${VOSK_MODEL_DEST}" ]; then
  echo "VOSK model '${VOSK_MODEL_NAME}' already exists, skipping download."
else
  echo "=========================================="
  echo "Downloading VOSK model ${VOSK_MODEL_NAME}..."
  echo "URL: ${VOSK_MODEL_URL}"
  echo "=========================================="
  if ! wget --show-progress -O "${REQ}/${VOSK_MODEL_ZIP}" "${VOSK_MODEL_URL}"; then
    echo "ERROR: Failed to download ${VOSK_MODEL_ZIP}. Check network connectivity and URL."
    exit 1
  fi
  
  echo "Extracting ${VOSK_MODEL_ZIP} to ${REQ}..."
  if ! unzip -q "${REQ}/${VOSK_MODEL_ZIP}" -d "${REQ}"; then
    echo "ERROR: Failed to extract ${VOSK_MODEL_ZIP}. unzip may not be installed."
    exit 1
  fi
  
  if [ ! -d "${VOSK_MODEL_DEST}" ]; then
    echo "ERROR: Extraction succeeded but directory not found at ${VOSK_MODEL_DEST}"
    exit 1
  fi
  
  rm "${REQ}/${VOSK_MODEL_ZIP}"
  echo "=========================================="
  echo "✓ VOSK model ready at: ${VOSK_MODEL_DEST}"
  echo "=========================================="
fi


