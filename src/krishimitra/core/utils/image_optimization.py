"""
Image compression and quality optimization utilities.

This module provides automatic image resizing, compression, and format optimization
for diagnostic images in low-bandwidth scenarios.
"""

import io
from typing import Optional, Tuple, Union, Dict, Any, List
from pathlib import Path
from enum import Enum

from PIL import Image
import cv2
import numpy as np

from .bandwidth import BandwidthDetector, BandwidthTier


class ImageFormat(Enum):
    """Supported image formats."""
    JPEG = "JPEG"
    PNG = "PNG"
    WEBP = "WEBP"


class ImageQuality(Enum):
    """Image quality presets."""
    LOW = 40
    MEDIUM = 65
    HIGH = 85
    VERY_HIGH = 95


class ImageOptimizer:
    """
    Image compression and optimization for low-bandwidth scenarios.
    
    Automatically adjusts image quality, size, and format based on
    bandwidth conditions while preserving diagnostic quality.
    """
    
    def __init__(
        self,
        bandwidth_detector: Optional[BandwidthDetector] = None,
        preserve_diagnostic_quality: bool = True
    ):
        """
        Initialize image optimizer.
        
        Args:
            bandwidth_detector: Bandwidth detector for adaptive optimization
            preserve_diagnostic_quality: Ensure diagnostic features are preserved
        """
        self.bandwidth_detector = bandwidth_detector
        self.preserve_diagnostic_quality = preserve_diagnostic_quality
    
    def optimize_image(
        self,
        image_data: Union[bytes, Image.Image, np.ndarray],
        max_size: Optional[Tuple[int, int]] = None,
        quality: Optional[int] = None,
        output_format: Optional[ImageFormat] = None
    ) -> bytes:
        """
        Optimize image for transmission.
        
        Args:
            image_data: Input image (bytes, PIL Image, or numpy array)
            max_size: Maximum dimensions (width, height)
            quality: JPEG/WebP quality (1-100)
            output_format: Output image format
            
        Returns:
            Optimized image bytes
        """
        # Load image
        if isinstance(image_data, bytes):
            image = Image.open(io.BytesIO(image_data))
        elif isinstance(image_data, np.ndarray):
            image = Image.fromarray(cv2.cvtColor(image_data, cv2.COLOR_BGR2RGB))
        else:
            image = image_data
        
        # Determine optimal parameters based on bandwidth
        if max_size is None:
            max_size = self._get_adaptive_max_size()
        
        if quality is None:
            quality = self._get_adaptive_quality()
        
        if output_format is None:
            output_format = self._get_adaptive_format()
        
        # Resize if needed
        if max_size:
            image = self._resize_image(image, max_size)
        
        # Enhance for diagnostic quality if needed
        if self.preserve_diagnostic_quality:
            image = self._enhance_diagnostic_features(image)
        
        # Convert to target format and compress
        output = io.BytesIO()
        
        if output_format == ImageFormat.WEBP:
            image.save(output, format='WEBP', quality=quality, method=6)
        elif output_format == ImageFormat.PNG:
            # PNG uses compression level (0-9), convert quality to compression
            compression = int((100 - quality) / 11)
            image.save(output, format='PNG', compress_level=compression)
        else:  # JPEG
            image.save(output, format='JPEG', quality=quality, optimize=True)
        
        return output.getvalue()
    
    def _resize_image(
        self,
        image: Image.Image,
        max_size: Tuple[int, int]
    ) -> Image.Image:
        """
        Resize image while maintaining aspect ratio.
        
        Args:
            image: Input image
            max_size: Maximum dimensions (width, height)
            
        Returns:
            Resized image
        """
        # Calculate new size maintaining aspect ratio
        width, height = image.size
        max_width, max_height = max_size
        
        if width <= max_width and height <= max_height:
            return image
        
        # Calculate scaling factor
        width_ratio = max_width / width
        height_ratio = max_height / height
        scale_factor = min(width_ratio, height_ratio)
        
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        
        # Use high-quality resampling
        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    def _enhance_diagnostic_features(
        self,
        image: Image.Image
    ) -> Image.Image:
        """
        Enhance diagnostic features in agricultural images.
        
        Args:
            image: Input image
            
        Returns:
            Enhanced image
        """
        # Convert to numpy array for OpenCV processing
        img_array = np.array(image)
        
        # Convert to BGR for OpenCV
        if len(img_array.shape) == 3 and img_array.shape[2] == 3:
            img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        else:
            img_bgr = img_array
        
        # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        # This enhances local contrast which is important for crop disease detection
        if len(img_bgr.shape) == 3:
            # Convert to LAB color space
            lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            
            # Apply CLAHE to L channel
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            
            # Merge channels
            lab = cv2.merge([l, a, b])
            
            # Convert back to BGR
            img_bgr = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        else:
            # Grayscale image
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            img_bgr = clahe.apply(img_bgr)
        
        # Slight sharpening to preserve details
        kernel = np.array([[-1, -1, -1],
                          [-1,  9, -1],
                          [-1, -1, -1]]) / 9
        img_bgr = cv2.filter2D(img_bgr, -1, kernel)
        
        # Convert back to RGB for PIL
        if len(img_bgr.shape) == 3:
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        else:
            img_rgb = img_bgr
        
        return Image.fromarray(img_rgb)
    
    def _get_adaptive_max_size(self) -> Tuple[int, int]:
        """
        Get adaptive maximum image size based on bandwidth.
        
        Returns:
            Maximum dimensions (width, height)
        """
        if not self.bandwidth_detector:
            return (800, 600)
        
        return self.bandwidth_detector.get_recommended_max_image_size()
    
    def _get_adaptive_quality(self) -> int:
        """
        Get adaptive image quality based on bandwidth.
        
        Returns:
            Quality value (1-100)
        """
        if not self.bandwidth_detector:
            return ImageQuality.MEDIUM.value
        
        return self.bandwidth_detector.get_recommended_image_quality()
    
    def _get_adaptive_format(self) -> ImageFormat:
        """
        Get adaptive image format based on bandwidth and device.
        
        Returns:
            Recommended image format
        """
        if not self.bandwidth_detector:
            return ImageFormat.JPEG
        
        tier = self.bandwidth_detector.get_current_tier()
        
        # WebP provides better compression for low bandwidth
        if tier in [BandwidthTier.VERY_LOW, BandwidthTier.LOW]:
            return ImageFormat.WEBP
        
        # JPEG is widely supported and good for photos
        return ImageFormat.JPEG
    
    def get_compression_ratio(
        self,
        original_size: int,
        compressed_size: int
    ) -> float:
        """
        Calculate compression ratio.
        
        Args:
            original_size: Original image size in bytes
            compressed_size: Compressed image size in bytes
            
        Returns:
            Compression ratio
        """
        if compressed_size == 0:
            return 0.0
        return original_size / compressed_size


class CropImageAnalyzer:
    """
    Analyze crop images for diagnostic purposes.
    
    Provides image quality assessment and feature extraction for
    agricultural diagnostics.
    """
    
    def __init__(self):
        """Initialize crop image analyzer."""
        pass
    
    def assess_image_quality(
        self,
        image: Union[bytes, Image.Image, np.ndarray]
    ) -> Dict[str, Any]:
        """
        Assess image quality for diagnostic purposes.
        
        Args:
            image: Input image
            
        Returns:
            Quality assessment metrics
        """
        # Load image
        if isinstance(image, bytes):
            img = Image.open(io.BytesIO(image))
            img_array = np.array(img)
        elif isinstance(image, Image.Image):
            img_array = np.array(image)
        else:
            img_array = image
        
        # Convert to grayscale for analysis
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        
        # Calculate sharpness (Laplacian variance)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        sharpness = laplacian.var()
        
        # Calculate brightness
        brightness = np.mean(gray)
        
        # Calculate contrast
        contrast = gray.std()
        
        # Assess if image is suitable for diagnosis
        is_suitable = (
            sharpness > 100 and  # Sufficient sharpness
            brightness > 30 and brightness < 225 and  # Not too dark or bright
            contrast > 20  # Sufficient contrast
        )
        
        return {
            'sharpness': float(sharpness),
            'brightness': float(brightness),
            'contrast': float(contrast),
            'is_suitable_for_diagnosis': is_suitable,
            'recommendations': self._get_quality_recommendations(
                sharpness, brightness, contrast
            )
        }
    
    def _get_quality_recommendations(
        self,
        sharpness: float,
        brightness: float,
        contrast: float
    ) -> List[str]:
        """
        Get recommendations for improving image quality.
        
        Args:
            sharpness: Sharpness metric
            brightness: Brightness metric
            contrast: Contrast metric
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        if sharpness < 100:
            recommendations.append("Image is blurry. Hold camera steady and focus properly.")
        
        if brightness < 30:
            recommendations.append("Image is too dark. Take photo in better lighting.")
        elif brightness > 225:
            recommendations.append("Image is too bright. Avoid direct sunlight.")
        
        if contrast < 20:
            recommendations.append("Image has low contrast. Ensure good lighting conditions.")
        
        if not recommendations:
            recommendations.append("Image quality is good for diagnosis.")
        
        return recommendations
    
    def extract_crop_features(
        self,
        image: Union[bytes, Image.Image, np.ndarray]
    ) -> Dict[str, Any]:
        """
        Extract features from crop image for analysis.
        
        Args:
            image: Input image
            
        Returns:
            Extracted features
        """
        # Load image
        if isinstance(image, bytes):
            img = Image.open(io.BytesIO(image))
            img_array = np.array(img)
        elif isinstance(image, Image.Image):
            img_array = np.array(image)
        else:
            img_array = image
        
        # Convert to different color spaces for analysis
        if len(img_array.shape) == 3:
            # RGB to HSV for color analysis
            hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)
            
            # Calculate color statistics
            h_mean = np.mean(hsv[:, :, 0])
            s_mean = np.mean(hsv[:, :, 1])
            v_mean = np.mean(hsv[:, :, 2])
            
            # Detect green vegetation (hue around 60-120 degrees)
            green_mask = cv2.inRange(hsv, (30, 40, 40), (90, 255, 255))
            green_percentage = (np.sum(green_mask > 0) / green_mask.size) * 100
            
            # Detect brown/yellow (potential disease indicators)
            brown_mask = cv2.inRange(hsv, (10, 40, 40), (30, 255, 255))
            brown_percentage = (np.sum(brown_mask > 0) / brown_mask.size) * 100
            
            return {
                'hue_mean': float(h_mean),
                'saturation_mean': float(s_mean),
                'value_mean': float(v_mean),
                'green_vegetation_percentage': float(green_percentage),
                'brown_area_percentage': float(brown_percentage),
                'health_indicator': 'healthy' if green_percentage > 50 else 'needs_attention'
            }
        else:
            # Grayscale image
            return {
                'mean_intensity': float(np.mean(img_array)),
                'std_intensity': float(np.std(img_array)),
                'health_indicator': 'unknown'
            }


def optimize_crop_image(
    image_data: bytes,
    bandwidth_kbps: Optional[float] = None
) -> bytes:
    """
    Optimize crop image for transmission with diagnostic quality preservation.
    
    Args:
        image_data: Original image bytes
        bandwidth_kbps: Available bandwidth in kbps
        
    Returns:
        Optimized image bytes
    """
    bandwidth_detector = None
    if bandwidth_kbps is not None:
        bandwidth_detector = BandwidthDetector()
        bandwidth_detector.add_measurement(bandwidth_kbps)
    
    optimizer = ImageOptimizer(
        bandwidth_detector=bandwidth_detector,
        preserve_diagnostic_quality=True
    )
    
    return optimizer.optimize_image(image_data)


def analyze_crop_image_quality(image_data: bytes) -> Dict[str, Any]:
    """
    Analyze crop image quality for diagnostic suitability.
    
    Args:
        image_data: Image bytes
        
    Returns:
        Quality assessment and recommendations
    """
    analyzer = CropImageAnalyzer()
    return analyzer.assess_image_quality(image_data)
