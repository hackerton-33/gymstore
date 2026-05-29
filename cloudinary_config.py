"""
Cloudinary Configuration and Helper Functions
Upload and manage images on Cloudinary
"""
import cloudinary
import cloudinary.uploader
import cloudinary.api

# ============================================
# Cloudinary credentials
# Dashboard: https://console.cloudinary.com/console
# ============================================
CLOUDINARY_CLOUD_NAME = "dr4pwx7kk"
CLOUDINARY_API_KEY = "459353212878213"
CLOUDINARY_API_SECRET = "nNgcsBFGJwWGIbwUkI5pfkkmA0E"

# Configure Cloudinary
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True
)

def upload_image(file, folder="products"):
    """
    Upload image to Cloudinary
    
    Args:
        file: File object or file path
        folder: Cloudinary folder name (default: "products")
    
    Returns:
        str: Secure URL of uploaded image, or None if failed
    """
    try:
        result = cloudinary.uploader.upload(
            file,
            folder=folder,
            resource_type="image",
            transformation=[
                {'width': 800, 'height': 800, 'crop': 'limit'},  # Max 800x800
                {'quality': 'auto'},                              # Auto quality
                {'fetch_format': 'auto'}                          # Auto format (WebP, etc.)
            ]
        )
        print(f"✅ Image uploaded to Cloudinary: {result['secure_url']}")
        return result['secure_url']
    except Exception as e:
        print(f"❌ Cloudinary upload error: {e}")
        return None

def upload_multiple_images(files, folder="products"):
    """
    Upload multiple images to Cloudinary
    
    Args:
        files: List of file objects
        folder: Cloudinary folder name
    
    Returns:
        list: List of secure URLs
    """
    urls = []
    for file in files:
        url = upload_image(file, folder)
        if url:
            urls.append(url)
    return urls

def delete_image(public_id):
    """
    Delete image from Cloudinary
    
    Args:
        public_id: Cloudinary public ID (e.g., "products/image123")
    
    Returns:
        bool: True if deleted successfully, False otherwise
    """
    try:
        result = cloudinary.uploader.destroy(public_id)
        success = result['result'] == 'ok'
        if success:
            print(f"✅ Image deleted from Cloudinary: {public_id}")
        else:
            print(f"⚠️ Image not found or already deleted: {public_id}")
        return success
    except Exception as e:
        print(f"❌ Cloudinary delete error: {e}")
        return False

def get_public_id_from_url(url):
    """
    Extract public_id from Cloudinary URL
    
    Args:
        url: Cloudinary URL (e.g., "https://res.cloudinary.com/.../products/image.jpg")
    
    Returns:
        str: Public ID (e.g., "products/image")
    """
    try:
        # URL format: https://res.cloudinary.com/{cloud_name}/image/upload/v{version}/{public_id}.{format}
        parts = url.split('/upload/')
        if len(parts) == 2:
            # Remove version number and get public_id with folder
            path = parts[1].split('/')
            if len(path) > 1:
                # Remove version (v1234567890)
                if path[0].startswith('v'):
                    path = path[1:]
                # Join folder and filename, remove extension
                public_id = '/'.join(path).rsplit('.', 1)[0]
                return public_id
    except Exception as e:
        print(f"Error extracting public_id: {e}")
    return None

def is_cloudinary_configured():
    """
    Check if Cloudinary is properly configured
    
    Returns:
        bool: True if configured, False otherwise
    """
    if (CLOUDINARY_CLOUD_NAME == "YOUR_CLOUD_NAME" or 
        CLOUDINARY_API_KEY == "YOUR_API_KEY" or 
        CLOUDINARY_API_SECRET == "YOUR_API_SECRET"):
        print("⚠️ Cloudinary not configured! Please update credentials in cloudinary_config.py")
        return False
    return True

# Test configuration on import
if __name__ == "__main__":
    if is_cloudinary_configured():
        print("✅ Cloudinary is configured!")
        print(f"Cloud Name: {CLOUDINARY_CLOUD_NAME}")
    else:
        print("❌ Cloudinary is NOT configured!")
        print("Please update credentials in cloudinary_config.py")
