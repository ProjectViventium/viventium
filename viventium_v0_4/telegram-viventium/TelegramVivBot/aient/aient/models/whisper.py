"""
Whisper API implementation for voice transcription.
Supports both OpenAI-compatible API and local Whisper models.
"""
import os
import requests
import json
import logging
from urllib.parse import urlparse
from ..core.utils import BaseAPI

logger = logging.getLogger(__name__)


def _is_azure_url(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return host.endswith("openai.azure.com") or host.endswith("cognitiveservices.azure.com")


def _append_api_version(url: str) -> str:
    if "api-version=" in url or not _is_azure_url(url):
        return url
    api_version = (
        os.environ.get("WHISPER_AZURE_API_VERSION")
        or os.environ.get("AZURE_OPENAI_API_VERSION")
        or ""
    ).strip()
    if not api_version:
        return url
    joiner = "&" if "?" in url else "?"
    return f"{url}{joiner}api-version={api_version}"

class Whisper:
    """Whisper API client for audio transcription"""
    def __init__(
        self,
        api_key: str = None,
        api_url: str = None,
        timeout: float = None,
        use_environment_url: bool = True,
    ):
        self.api_key = api_key
        configured_timeout = timeout or float(os.environ.get("WHISPER_TIMEOUT", "300"))
        self.timeout = configured_timeout
        self._is_azure = False
        
        # Set up API URL - use BaseAPI to parse it and get audio_transcriptions endpoint (matches standalone)
        # === VIVENTIUM START === Saved provider routing can supply its own exact URL.
        override_url = (os.environ.get("WHISPER_API_URL") or "").strip() if use_environment_url else ""
        # === VIVENTIUM END ===
        if override_url:
            self.api_url_obj = None
            self.api_url = _append_api_version(override_url)
            self._is_azure = _is_azure_url(self.api_url)
            logger.info("Initialized Whisper transcription endpoint")
        elif api_url:
            # Use BaseAPI to parse the URL and get the audio_transcriptions property
            try:
                base_api = BaseAPI(api_url)
                self.api_url_obj = base_api  # Store BaseAPI object
                self.api_url = base_api.audio_transcriptions  # Get the transcriptions endpoint
                self.api_url = _append_api_version(self.api_url)
                self._is_azure = _is_azure_url(self.api_url)
                if self._is_azure:
                    # Preserve query params for Azure (api-version).
                    self.api_url_obj = None
                logger.info("Initialized Whisper transcription endpoint")
            except Exception as e:
                # === VIVENTIUM START === An explicit selected endpoint must not fall back.
                if not use_environment_url:
                    raise
                # === VIVENTIUM END ===
                logger.warning("Whisper endpoint configuration failed; using default error_type=%s", type(e).__name__)
                # Fallback to direct URL
                self.api_url_obj = None
                self.api_url = "https://api.openai.com/v1/audio/transcriptions"
        else:
            # Use BASE_URL from environment, parse with BaseAPI
            base_url = os.environ.get("BASE_URL") or "https://api.openai.com/v1/chat/completions"
            try:
                base_api = BaseAPI(base_url)
                self.api_url_obj = base_api
                self.api_url = base_api.audio_transcriptions
                self.api_url = _append_api_version(self.api_url)
                self._is_azure = _is_azure_url(self.api_url)
                if self._is_azure:
                    self.api_url_obj = None
                logger.info("Initialized Whisper transcription endpoint")
            except Exception as e:
                logger.warning("Whisper endpoint configuration failed; using default error_type=%s", type(e).__name__)
                self.api_url_obj = None
                self.api_url = "https://api.openai.com/v1/audio/transcriptions"
        
        self.engine: str = "whisper-1"
        self.session = requests.Session()

    def generate(
        self,
        audio_file,
        model: str = None,
        **kwargs,
    ):
        """
        Transcribe audio file using Whisper API.
        
        Args:
            audio_file: BytesIO stream or bytes containing audio data
            model: Explicit model; omitted uses AUDIO_MODEL_NAME, then whisper-1.
            **kwargs: Additional parameters
            
        Returns:
            str: Transcribed text
        """
        logger.info("Starting Whisper transcription with model=%s", model)
        
        # Handle BytesIO or bytes
        if hasattr(audio_file, 'read'):
            audio_file.seek(0)
            audio_bytes = audio_file.read()
        else:
            audio_bytes = audio_file
        
        if not audio_bytes:
            logger.error("Empty audio file provided")
            raise ValueError("Audio file is empty")
        
        logger.debug(f"Audio file size: {len(audio_bytes)} bytes")
        
        # Use the stored BaseAPI object if available, otherwise use direct URL string
        if hasattr(self, 'api_url_obj') and self.api_url_obj:
            url = self.api_url_obj.audio_transcriptions
        else:
            url = self.api_url
        api_key = kwargs.get('api_key', self.api_key)
        headers = {}
        
        if not api_key:
            logger.error("API key is missing for Whisper transcription")
            raise ValueError("API key is required for Whisper transcription")
        if self._is_azure:
            headers["api-key"] = api_key
        else:
            headers["Authorization"] = f"Bearer {api_key}"

        files = {
            "file": ("audio.mp3", audio_bytes, "audio/mpeg")
        }

        data = {}
        if not self._is_azure:
            # === VIVENTIUM START === Preserve saved selections and legacy defaults.
            data["model"] = model or os.environ.get("AUDIO_MODEL_NAME") or self.engine
            # === VIVENTIUM END ===
        
        model_name = data.get("model") or "azure-deployment"
        logger.debug("Sending Whisper transcription request with model=%s", model_name)
        
        try:
            response = self.session.post(
                url,
                headers=headers,
                data=data,
                files=files,
                timeout=kwargs.get("timeout", self.timeout),
                stream=True,
            )
            logger.debug(f"Whisper API response status: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.error("Whisper transcription request failed error_type=%s", type(e).__name__)
            raise
        except Exception as e:
            logger.error("Whisper transcription request failed error_type=%s", type(e).__name__)
            raise RuntimeError("Whisper transcription request failed") from e

        if response.status_code != 200:
            logger.error("Whisper transcription HTTP rejection status=%s", response.status_code)
            close = getattr(response, 'close', None)
            if callable(close):
                try:
                    close()
                except Exception as error:
                    logger.warning("Whisper response cleanup failed error_type=%s", type(error).__name__)
            raise requests.HTTPError(f"Whisper transcription HTTP {response.status_code}", response=response)
        
        try:
            json_data = json.loads(response.text)
            text = json_data.get("text", "")
            logger.info(f"Whisper transcription successful, length: {len(text)} characters")
            return text
        except json.JSONDecodeError as e:
            logger.error("Whisper transcription response is invalid JSON error_type=%s", type(e).__name__)
            raise RuntimeError("Whisper transcription response is invalid JSON") from e

# Function alias for backward compatibility
def whisper(api_key=None, api_url=None):
    """Create a Whisper instance"""
    return Whisper(api_key=api_key, api_url=api_url)
