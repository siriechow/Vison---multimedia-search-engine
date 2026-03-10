"""
Vison - Feature Extraction Module
Extracts feature vectors from images, audio, and video using TensorFlow/OpenVINO.
"""

import io
import logging
import numpy as np
from pathlib import Path
from PIL import Image

from app.config import settings

logger = logging.getLogger(__name__)

# ─── Lazy-loaded globals ───
_tf_model = None
_ov_model = None
_use_openvino = False


def _load_tensorflow_model():
    """Load MobileNetV2 with TensorFlow (fallback)."""
    global _tf_model
    if _tf_model is not None:
        return _tf_model
    try:
        import tensorflow as tf
        tf.get_logger().setLevel("ERROR")
        base_model = tf.keras.applications.MobileNetV2(
            weights="imagenet",
            include_top=False,
            pooling="avg",
            input_shape=(224, 224, 3),
        )
        base_model.trainable = False
        _tf_model = base_model
        logger.info("✓ TensorFlow MobileNetV2 loaded successfully")
        return _tf_model
    except Exception as e:
        logger.error(f"Failed to load TensorFlow model: {e}")
        return None


def _load_openvino_model():
    """Load MobileNetV2 with Intel OpenVINO for optimized inference."""
    global _ov_model, _use_openvino
    if _ov_model is not None:
        return _ov_model
    try:
        from openvino.runtime import Core
        import tensorflow as tf

        # First ensure TF model exists, then convert
        tf_model = _load_tensorflow_model()
        if tf_model is None:
            return None

        core = Core()
        # Convert TF model to OpenVINO IR
        import openvino as ov
        ov_model = ov.convert_model(tf_model)
        compiled = core.compile_model(ov_model, "CPU")
        _ov_model = compiled
        _use_openvino = True
        logger.info("✓ OpenVINO model compiled successfully (CPU optimized)")
        return _ov_model
    except ImportError:
        logger.warning("OpenVINO not available, using TensorFlow backend")
        return None
    except Exception as e:
        logger.warning(f"OpenVINO conversion failed: {e}. Using TensorFlow backend")
        return None


def initialize_models():
    """Initialize ML models at startup. Tries OpenVINO first, falls back to TensorFlow."""
    global _use_openvino
    if settings.USE_OPENVINO:
        model = _load_openvino_model()
        if model is not None:
            _use_openvino = True
            return
    _load_tensorflow_model()
    _use_openvino = False
    logger.info(f"Feature extraction backend: {'OpenVINO' if _use_openvino else 'TensorFlow'}")


def _preprocess_image(image: Image.Image) -> np.ndarray:
    """Preprocess image for MobileNetV2."""
    image = image.convert("RGB")
    image = image.resize(settings.IMAGE_INPUT_SIZE, Image.LANCZOS)
    arr = np.array(image, dtype=np.float32)
    # MobileNetV2 preprocessing: scale to [-1, 1]
    arr = (arr / 127.5) - 1.0
    return np.expand_dims(arr, axis=0)


def _normalize_vector(vec: np.ndarray) -> np.ndarray:
    """L2-normalize a feature vector for cosine similarity."""
    norm = np.linalg.norm(vec)
    if norm == 0:
        return vec
    return vec / norm


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  IMAGE FEATURE EXTRACTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def extract_image_features(image_input) -> np.ndarray | None:
    """
    Extract feature vector from an image.

    Args:
        image_input: PIL Image, file path (str/Path), or bytes

    Returns:
        Normalized 1280-dim feature vector, or None on failure
    """
    try:
        # Handle different input types
        if isinstance(image_input, (str, Path)):
            image = Image.open(image_input)
        elif isinstance(image_input, bytes):
            image = Image.open(io.BytesIO(image_input))
        elif isinstance(image_input, Image.Image):
            image = image_input
        else:
            logger.error(f"Unsupported image input type: {type(image_input)}")
            return None

        preprocessed = _preprocess_image(image)

        if _use_openvino and _ov_model is not None:
            # OpenVINO inference
            result = _ov_model([preprocessed])
            features = result[_ov_model.output(0)]
            features = np.squeeze(features)
        else:
            # TensorFlow inference
            model = _load_tensorflow_model()
            if model is None:
                # Fallback: generate random features for development
                logger.warning("No ML model available. Generating placeholder features.")
                features = np.random.randn(settings.IMAGE_FEATURE_DIM).astype(np.float32)
            else:
                features = model.predict(preprocessed, verbose=0)
                features = np.squeeze(features)

        return _normalize_vector(features.astype(np.float32))

    except Exception as e:
        logger.error(f"Image feature extraction failed: {e}")
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AUDIO FEATURE EXTRACTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def extract_audio_features(audio_input) -> np.ndarray | None:
    """
    Extract feature vector from an audio file using MFCCs.

    Args:
        audio_input: File path (str/Path) or bytes

    Returns:
        Normalized 512-dim feature vector, or None on failure
    """
    try:
        import librosa

        # Load audio
        if isinstance(audio_input, (str, Path)):
            y, sr = librosa.load(str(audio_input), sr=22050, duration=30)
        elif isinstance(audio_input, bytes):
            import soundfile as sf
            y, sr = sf.read(io.BytesIO(audio_input))
            if sr != 22050:
                y = librosa.resample(y, orig_sr=sr, target_sr=22050)
                sr = 22050
        else:
            logger.error(f"Unsupported audio input type: {type(audio_input)}")
            return None

        if len(y) == 0:
            logger.warning("Empty audio file")
            return None

        # Extract MFCCs (40 coefficients)
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=40)
        # Extract spectral features
        spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
        chroma = librosa.feature.chroma_stft(y=y, sr=sr, n_chroma=12)
        zero_crossing = librosa.feature.zero_crossing_rate(y)

        # Aggregate statistics: mean + std for each feature
        feature_parts = []
        for feat in [mfccs, spectral_centroid, spectral_rolloff, chroma, zero_crossing]:
            feature_parts.extend([
                np.mean(feat, axis=1),
                np.std(feat, axis=1),
                np.max(feat, axis=1),
                np.min(feat, axis=1),
            ])

        combined = np.concatenate(feature_parts)

        # Pad or truncate to target dimension
        target_dim = settings.AUDIO_FEATURE_DIM
        if len(combined) < target_dim:
            combined = np.pad(combined, (0, target_dim - len(combined)))
        else:
            combined = combined[:target_dim]

        return _normalize_vector(combined.astype(np.float32))

    except ImportError:
        logger.warning("librosa not available. Generating placeholder audio features.")
        return _normalize_vector(np.random.randn(settings.AUDIO_FEATURE_DIM).astype(np.float32))
    except Exception as e:
        logger.error(f"Audio feature extraction failed: {e}")
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  VIDEO FEATURE EXTRACTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def extract_video_features(video_input, max_frames: int = 10) -> np.ndarray | None:
    """
    Extract feature vector from video by sampling keyframes.

    Args:
        video_input: File path (str/Path)
        max_frames:  Maximum number of frames to sample

    Returns:
        Normalized 1280-dim feature vector (averaged frame features), or None
    """
    try:
        import cv2

        if isinstance(video_input, (str, Path)):
            cap = cv2.VideoCapture(str(video_input))
        else:
            logger.error("Video extraction requires a file path")
            return None

        if not cap.isOpened():
            logger.error(f"Cannot open video: {video_input}")
            return None

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            cap.release()
            return None

        # Sample frames evenly across the video
        frame_indices = np.linspace(0, total_frames - 1, min(max_frames, total_frames), dtype=int)
        frame_features = []

        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret:
                continue

            # Convert BGR (OpenCV) to RGB (PIL)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(frame_rgb)

            features = extract_image_features(pil_image)
            if features is not None:
                frame_features.append(features)

        cap.release()

        if not frame_features:
            return None

        # Average all frame features
        avg_features = np.mean(frame_features, axis=0)
        return _normalize_vector(avg_features.astype(np.float32))

    except ImportError:
        logger.warning("OpenCV not available. Generating placeholder video features.")
        return _normalize_vector(np.random.randn(settings.VIDEO_FEATURE_DIM).astype(np.float32))
    except Exception as e:
        logger.error(f"Video feature extraction failed: {e}")
        return None


def generate_thumbnail(input_path: str | Path, output_path: str | Path, media_type: str) -> bool:
    """Generate a thumbnail for a media file."""
    try:
        input_path = Path(input_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if media_type == "image":
            img = Image.open(input_path)
            img.thumbnail(settings.THUMBNAIL_SIZE, Image.LANCZOS)
            img.save(output_path, "JPEG", quality=85)
            return True

        elif media_type == "video":
            import cv2
            cap = cv2.VideoCapture(str(input_path))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            # Grab a frame from the middle
            cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 2)
            ret, frame = cap.read()
            cap.release()
            if ret:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame_rgb)
                img.thumbnail(settings.THUMBNAIL_SIZE, Image.LANCZOS)
                img.save(output_path, "JPEG", quality=85)
                return True

        elif media_type == "audio":
            # Generate a waveform thumbnail for audio
            try:
                import librosa
                import librosa.display
                import matplotlib
                matplotlib.use("Agg")
                import matplotlib.pyplot as plt

                y, sr = librosa.load(str(input_path), sr=22050, duration=30)
                fig, ax = plt.subplots(1, 1, figsize=(4, 2), dpi=75)
                ax.plot(y, color="#7c3aed", linewidth=0.5)
                ax.axis("off")
                fig.tight_layout(pad=0)
                fig.savefig(output_path, bbox_inches="tight", pad_inches=0)
                plt.close(fig)
                return True
            except ImportError:
                pass

        return False
    except Exception as e:
        logger.error(f"Thumbnail generation failed: {e}")
        return False
