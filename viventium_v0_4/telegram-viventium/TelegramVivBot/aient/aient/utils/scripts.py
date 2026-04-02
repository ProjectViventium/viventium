import os
import requests
import urllib.parse
import subprocess
import shutil
import tempfile
from io import BytesIO

from ..core.utils import get_image_message

def get_doc_from_url(url):
    filename = urllib.parse.unquote(url.split("/")[-1])
    response = requests.get(url, stream=True)
    with open(filename, 'wb') as f:
        for chunk in response.iter_content(chunk_size=1024):
            f.write(chunk)
    return filename

VIDEO_EXTENSIONS = (
    ".mp4",
    ".m4v",
    ".mov",
    ".mkv",
    ".webm",
    ".avi",
    ".mpg",
    ".mpeg",
)

def extract_audio_from_video(video_path):
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required to process video files")
    temp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    temp_file.close()
    command = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-vn",
        "-acodec",
        "libmp3lame",
        "-ar",
        "44100",
        "-ac",
        "2",
        temp_file.name,
    ]
    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode != 0:
        if os.path.exists(temp_file.name):
            os.remove(temp_file.name)
        error_output = process.stderr.decode("utf-8", errors="ignore").strip()
        raise RuntimeError(f"ffmpeg failed: {error_output}")
    return temp_file.name

def transcribe_audio_file(file_path):
    with open(file_path, "rb") as file:
        file_bytes = file.read()
    return get_audio_message(file_bytes)

def get_audio_message(file_bytes):
    """Transcribe audio bytes using local Whisper or API"""
    import logging
    import tempfile
    import os
    logger = logging.getLogger(__name__)
    
    try:
        # Create a byte stream object
        audio_stream = BytesIO(file_bytes)
        logger.debug(f"Created audio stream from {len(file_bytes)} bytes")

        # Directly use the byte stream object for transcription
        import config
        logger.info(f"Whisper mode: {config.WHISPER_MODE}")
        
        # Accept both "local" and "pywhispercpp" for local mode
        if config.WHISPER_MODE in ("local", "pywhispercpp"):
            logger.info("Using local Whisper model")
            ensure_stt_engine = getattr(config, "ensure_stt_engine", None)
            if not config.local_whisper and callable(ensure_stt_engine):
                ensure_stt_engine()
            if not config.local_whisper:
                error_msg = "Local whisper model not initialized"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            # pywhispercpp.transcribe() requires a file path, not BytesIO
            # Write BytesIO to temporary file (matches viventium_v1 pattern)
            audio_stream.seek(0)
            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as tmp_file:
                tmp_path = tmp_file.name
                tmp_file.write(file_bytes)
            
            try:
                logger.debug(f"Transcribing with local model, language={config.LOCAL_WHISPER_LANG}, temp_file={tmp_path}")
                
                transcript_segments = config.local_whisper.transcribe(
                    tmp_path,  # Pass file path, not BytesIO
                    language=config.LOCAL_WHISPER_LANG,
                    translate=False,
                    print_realtime=config.LOCAL_WHISPER_VERBOSE,
                )
                transcript = " ".join(segment.text for segment in transcript_segments)
                logger.info(f"Local transcription successful, {len(transcript_segments)} segments")
            finally:
                # Clean up temp file
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        # === VIVENTIUM START ===
        # Feature: AssemblyAI STT option for Telegram voice transcription.
        elif config.WHISPER_MODE == "assemblyai":
            logger.info("Using AssemblyAI transcription")
            ensure_stt_engine = getattr(config, "ensure_stt_engine", None)
            if not getattr(config, "assemblyai_client", None) and callable(ensure_stt_engine):
                ensure_stt_engine()
            if not getattr(config, "assemblyai_client", None):
                error_msg = "AssemblyAI client not initialized (check ASSEMBLYAI_API_KEY)"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            transcript = config.assemblyai_client.transcribe_bytes(file_bytes)
            logger.info("AssemblyAI transcription successful")
        # === VIVENTIUM END ===
        else:
            logger.info("Using API Whisper model")
            ensure_stt_engine = getattr(config, "ensure_stt_engine", None)
            if not config.whisperBot and callable(ensure_stt_engine):
                ensure_stt_engine()
            if not config.whisperBot:
                error_msg = "Whisper API client not initialized (check API_KEY)"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            logger.debug(f"Calling whisperBot.generate() with audio stream")
            transcript = config.whisperBot.generate(audio_stream)
            logger.info(f"API transcription successful")

        if not transcript:
            logger.warning("Transcription returned empty result")
            return "error: Transcription returned empty result"

        logger.debug(f"Final transcript length: {len(transcript)} characters")
        return transcript

    except RuntimeError as e:
        logger.exception(f"Runtime error during transcription: {e}")
        return f"error: {str(e)}"
    except Exception as e:
        logger.exception(f"Unexpected error processing audio file: {e}")
        return f"error: Error processing audio file: {str(e)}"

async def Document_extract(docurl, docpath=None, engine_type = None):
    cleanup_paths = []
    local_path = docpath
    prompt = None
    if docurl:
        needs_download = not local_path or not os.path.exists(local_path)
        if needs_download:
            filename = get_doc_from_url(docurl)
            local_path = os.path.join(os.getcwd(), filename)
            cleanup_paths.append(local_path)
    if not local_path:
        return None
    extension = os.path.splitext(local_path)[1].lower()
    text = None
    if extension == ".pdf":
        from pdfminer.high_level import extract_text
        text = extract_text(local_path)
    if extension in {".txt", ".md", ".py", ".yml"}:
        with open(local_path, 'r') as file:
            text = file.read()
    if text:
        prompt = (
            "Here is the document, inside <document></document> XML tags:"
            "<document>"
            "{}"
            "</document>"
        ).format(text)
    elif extension in {".jpg", ".png", ".jpeg"}:
        prompt = await get_image_message(docurl or local_path, engine_type)
    elif extension in {".wav", ".mp3"}:
        transcript = transcribe_audio_file(local_path)
        prompt = (
            "Here is the text content after voice-to-text conversion, inside <voice-to-text></voice-to-text> XML tags:"
            "<voice-to-text>"
            "{}"
            "</voice-to-text>"
        ).format(transcript)
    elif extension in VIDEO_EXTENSIONS:
        audio_path = extract_audio_from_video(local_path)
        cleanup_paths.append(audio_path)
        transcript = transcribe_audio_file(audio_path)
        prompt = (
            "Here is the text content after voice-to-text conversion, inside <voice-to-text></voice-to-text> XML tags:"
            "<voice-to-text>"
            "{}"
            "</voice-to-text>"
        ).format(transcript)
    for path in cleanup_paths:
        if path and os.path.exists(path):
            os.remove(path)
    return prompt
