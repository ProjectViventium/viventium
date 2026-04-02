import io
import httpx
import base64
from PIL import Image
from fastapi import HTTPException
from urllib.parse import urlparse

from .log_config import logger

# REMOVED: get_model_dict function - Not imported anywhere, was for model selection UI

class BaseAPI:
    def __init__(
        self,
        api_url: str = "https://api.openai.com/v1/chat/completions",
    ):
        if api_url == "":
            api_url = "https://api.openai.com/v1/chat/completions"
        self.source_api_url: str = api_url
        from urllib.parse import urlparse, urlunparse
        parsed_url = urlparse(self.source_api_url)
        # print("parsed_url", parsed_url)
        if parsed_url.scheme == "":
            raise Exception("Error: API_URL is not set")
        if parsed_url.path != '/':
            before_v1 = parsed_url.path.split("chat/completions")[0]
            if not before_v1.endswith("/"):
                before_v1 = before_v1 + "/"
        else:
            before_v1 = ""
        self.base_url: str = urlunparse(parsed_url[:2] + ("",) + ("",) * 3)
        self.v1_url: str = urlunparse(parsed_url[:2]+ (before_v1,) + ("",) * 3)
        if "v1/messages" in parsed_url.path:
            self.v1_models: str = urlunparse(parsed_url[:2] + ("v1/models",) + ("",) * 3)
        else:
            self.v1_models: str = urlunparse(parsed_url[:2] + (before_v1 + "models",) + ("",) * 3)

        if "v1/responses" in parsed_url.path:
            self.chat_url: str = api_url
        elif "v1/messages" in parsed_url.path or parsed_url.netloc.endswith("anthropic.com"):
            # Anthropic's Messages API already points at the correct endpoint
            self.chat_url: str = api_url
        else:
            self.chat_url: str = urlunparse(parsed_url[:2] + (before_v1 + "chat/completions",) + ("",) * 3)
        self.image_url: str = urlunparse(parsed_url[:2] + (before_v1 + "images/generations",) + ("",) * 3)
        if parsed_url.hostname == "dashscope.aliyuncs.com":
            self.audio_transcriptions: str = urlunparse(parsed_url[:2] + ("/api/v1/services/aigc/multimodal-generation/generation",) + ("",) * 3)
        else:
            self.audio_transcriptions: str = urlunparse(parsed_url[:2] + (before_v1 + "audio/transcriptions",) + ("",) * 3)
        self.moderations: str = urlunparse(parsed_url[:2] + (before_v1 + "moderations",) + ("",) * 3)
        self.embeddings: str = urlunparse(parsed_url[:2] + (before_v1 + "embeddings",) + ("",) * 3)
        if parsed_url.hostname == "api.minimaxi.com":
            self.audio_speech: str = urlunparse(parsed_url[:2] + ("v1/t2a_v2",) + ("",) * 3)
        else:
            self.audio_speech: str = urlunparse(parsed_url[:2] + (before_v1 + "audio/speech",) + ("",) * 3)
        # Audio transcriptions endpoint (for Whisper)
        self.audio_transcriptions: str = urlunparse(parsed_url[:2] + (before_v1 + "audio/transcriptions",) + ("",) * 3)

        if parsed_url.path.endswith("/v1beta") or \
        (parsed_url.netloc == 'generativelanguage.googleapis.com' and "openai/chat/completions" not in parsed_url.path):
            before_v1 = parsed_url.path.split("/v1")[0]
            self.base_url = api_url
            self.v1_url = api_url
            self.chat_url = api_url
            self.embeddings = urlunparse(parsed_url[:2] + (before_v1 + "/v1beta/embeddings",) + ("",) * 3)

def get_engine(provider, endpoint=None, original_model=""):
    parsed_url = urlparse(provider['base_url'])
    # print("parsed_url", parsed_url)
    engine = None
    stream = None
    if parsed_url.path.endswith("/v1beta") or \
    (parsed_url.netloc == 'generativelanguage.googleapis.com' and "openai/chat/completions" not in parsed_url.path):
        engine = "gemini"
    elif parsed_url.netloc.rstrip('/').endswith('aiplatform.googleapis.com') or \
        (parsed_url.netloc.rstrip('/').endswith('gateway.ai.cloudflare.com') and "google-vertex-ai" in parsed_url.path) or \
        "aiplatform.googleapis.com" in parsed_url.path:
        engine = "vertex"
    elif parsed_url.netloc.rstrip('/').endswith('azure.com'):
        engine = "azure"
    elif parsed_url.netloc.rstrip('/').endswith('azuredatabricks.net'):
        engine = "azure-databricks"
    elif parsed_url.netloc == 'api.cloudflare.com':
        engine = "cloudflare"
    elif parsed_url.netloc == 'api.anthropic.com' or parsed_url.path.endswith("v1/messages"):
        engine = "claude"
    elif 'amazonaws.com' in parsed_url.netloc:
        engine = "aws"
    elif parsed_url.netloc == 'api.cohere.com':
        engine = "cohere"
        stream = True
    else:
        engine = "gpt"

    original_model = original_model.lower()
    if original_model \
    and "claude" not in original_model \
    and "gpt" not in original_model \
    and "deepseek" not in original_model \
    and "o1" not in original_model \
    and "o3" not in original_model \
    and "o4" not in original_model \
    and "gemini" not in original_model \
    and "gemma" not in original_model \
    and "learnlm" not in original_model \
    and "grok" not in original_model \
    and parsed_url.netloc != 'api.cloudflare.com' \
    and parsed_url.netloc != 'api.cohere.com':
        engine = "openrouter"

    if "claude" in original_model and engine == "vertex":
        engine = "vertex-claude"

    if "gemini" in original_model and engine == "vertex":
        engine = "vertex-gemini"

    if provider.get("engine"):
        engine = provider["engine"]

    if engine != "gemini" and (endpoint == "/v1/images/generations" or "stable-diffusion" in original_model):
        engine = "dalle"
        stream = False

    if endpoint == "/v1/audio/transcriptions":
        engine = "whisper"
        stream = False

    if endpoint == "/v1/moderations":
        engine = "moderation"
        stream = False

    if endpoint == "/v1/embeddings":
        engine = "embedding"

    if endpoint == "/v1/audio/speech":
        engine = "tts"
        stream = False

    if "stream" in safe_get(provider, "preferences", "post_body_parameter_overrides", default={}):
        stream = safe_get(provider, "preferences", "post_body_parameter_overrides", "stream")

    return engine, stream

def safe_get(data, *keys, default=None):
    for key in keys:
        try:
            if isinstance(data, (dict, list)):
                data = data[key]
            elif isinstance(key, str) and hasattr(data, key):
                data = getattr(data, key)
            else:
                data = data.get(key)
        except (KeyError, IndexError, AttributeError, TypeError):
            return default
    if not data:
        return default
    return data

def get_image_format(file_content: bytes):
    try:
        img = Image.open(io.BytesIO(file_content))
        return img.format.lower()
    except:
        return None

def encode_image(file_content: bytes):
    img_format = get_image_format(file_content)
    if not img_format:
        raise ValueError("Unrecognized image format")
    base64_encoded = base64.b64encode(file_content).decode('utf-8')

    if img_format == 'png':
        return f"data:image/png;base64,{base64_encoded}"
    elif img_format in ['jpg', 'jpeg']:
        return f"data:image/jpeg;base64,{base64_encoded}"
    else:
        raise ValueError(f"Unsupported image format: {img_format}")

async def get_image_from_url(url):
    transport = httpx.AsyncHTTPTransport(
        http2=True,
        verify=False,
        retries=1
    )
    async with httpx.AsyncClient(transport=transport) as client:
        try:
            response = await client.get(
                url,
                timeout=30.0
            )
            response.raise_for_status()
            return response.content

        except httpx.RequestError as e:
            logger.error(f"Error requesting URL {e.request.url!r}: {e}")
            raise HTTPException(status_code=400, detail=f"Unable to get content from URL: {url}")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred when getting URL {e.request.url!r}: {e.response.status_code}")
            raise HTTPException(status_code=e.response.status_code, detail=f"Error getting URL: {url}")

async def get_encode_image(image_url):
    file_content = await get_image_from_url(image_url)
    base64_image = encode_image(file_content)
    return base64_image

# from PIL import Image
# import io
# def validate_image(image_data, image_type):
#     try:
#         decoded_image = base64.b64decode(image_data)
#         image = Image.open(io.BytesIO(decoded_image))

#         # Check if image format matches declared type
#         # print("image.format", image.format)
#         if image_type == "image/png" and image.format != "PNG":
#             raise ValueError("Image is not a valid PNG")
#         elif image_type == "image/jpeg" and image.format not in ["JPEG", "JPG"]:
#             raise ValueError("Image is not a valid JPEG")

#         # If no exception, image is valid
#         return True
#     except Exception as e:
#         print(f"Image validation failed: {str(e)}")
#         return False

async def get_image_message(base64_image, engine = None):
    if base64_image.startswith("http"):
        base64_image = await get_encode_image(base64_image)
    colon_index = base64_image.index(":")
    semicolon_index = base64_image.index(";")
    image_type = base64_image[colon_index + 1:semicolon_index]

    if image_type == "image/webp":
        # Convert webp to png

        # Decode base64 to get image data
        image_data = base64.b64decode(base64_image.split(",")[1])

        # Open webp image using PIL
        image = Image.open(io.BytesIO(image_data))

        # Convert to PNG format
        png_buffer = io.BytesIO()
        image.save(png_buffer, format="PNG")
        png_base64 = base64.b64encode(png_buffer.getvalue()).decode('utf-8')

        # Return PNG format base64
        base64_image = f"data:image/png;base64,{png_base64}"
        image_type = "image/png"

    if "gpt" == engine or "openrouter" == engine or "azure" == engine or "azure-databricks" == engine:
        return {
            "type": "image_url",
            "image_url": {
                "url": base64_image,
            }
        }
    if "claude" == engine or "vertex-claude" == engine or "aws" == engine:
        # if not validate_image(base64_image.split(",")[1], image_type):
        #     raise ValueError(f"Invalid image format. Expected {image_type}")
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": image_type,
                "data": base64_image.split(",")[1],
            }
        }
    if "gemini" == engine or "vertex-gemini" == engine:
        return {
            "inlineData": {
                "mimeType": image_type,
                "data": base64_image.split(",")[1],
            }
        }
    raise ValueError("Unknown engine")
