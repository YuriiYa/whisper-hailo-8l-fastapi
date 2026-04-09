import os

class HefUtils:
    @staticmethod
    def get_encoder_hef_path(hw_arch, variant="base"):
        """
        Get the HEF path for the encoder based on the selected Whisper variant.

        Args:
            hw_arch (str): Hardware architecture ("hailo8" or "hailo8l").
            variant (str): Whisper variant ("tiny", "base").

        Returns:
            str: Path to the encoder HEF file.
        """
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, os.pardir))
        hw_arch = (hw_arch or "").upper()
        variant = (variant or "base").lower()

        if variant == "base":
            hef_path = os.path.join(
                base_path,
                "requirements_files",
                "hefs",
                "h8",
                "base",
                "base-whisper-encoder-5s.hef",
            )
        elif variant == "tiny":
            if hw_arch == "HAILO8L":
                hef_path = os.path.join(base_path, 'requirements_files', 'hefs', 'h8l', 'tiny', 'tiny-whisper-encoder-10s_15dB_h8l.hef')
            else:
                hef_path = os.path.join(base_path, 'requirements_files', 'hefs', 'h8', 'tiny', 'tiny-whisper-encoder-10s_15dB.hef')
        else:
            raise ValueError(f"Unsupported WHISPER_VARIANT: {variant}. Supported variants: tiny/base")

        if not os.path.exists(hef_path):
            raise FileNotFoundError(f"Encoder HEF file not found: {hef_path}. Please check the path.")
        return hef_path

    @staticmethod
    def get_decoder_hef_path(hw_arch, variant="base"):
        """
        Get the HEF path for the decoder based on the selected Whisper variant.

        Args:
            hw_arch (str): Hardware architecture ("hailo8" or "hailo8l").
            variant (str): Whisper variant ("tiny", "base").

        Returns:
            str: Path to the decoder HEF file.
        """
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, os.pardir))
        hw_arch = (hw_arch or "").upper()
        variant = (variant or "base").lower()

        if variant == "base":
            hef_path = os.path.join(
                base_path,
                "requirements_files",
                "hefs",
                "h8",
                "base",
                "base-whisper-decoder-fixed-sequence-matmul-split.hef",
            )
        elif variant == "tiny":
            if hw_arch == "HAILO8L":
                hef_path = os.path.join(base_path, 'requirements_files', 'hefs', "h8l", "tiny",
                                        "tiny-whisper-decoder-fixed-sequence-matmul-split_h8l.hef")
            else:
                hef_path = os.path.join(base_path, "requirements_files", "hefs", "h8", "tiny",
                                        "tiny-whisper-decoder-fixed-sequence-matmul-split.hef")
        else:
            raise ValueError(f"Unsupported WHISPER_VARIANT: {variant}. Supported variants: tiny/base")

        if not os.path.exists(hef_path):
            raise FileNotFoundError(f"Decoder HEF file not found: {hef_path}. Please check the path.")
        return hef_path