"""HTTP routes for this API domain."""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

router = APIRouter()
logger = logging.getLogger(__name__)


# ========== UI Visualizer Endpoints ==========

@router.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serve the clean Michele visualizer UI."""
    ui_path = Path(__file__).parent.parent / "ui" / "index-new.html"
    
    if not ui_path.exists():
        raise HTTPException(status_code=404, detail="UI not found")
    
    with open(ui_path, 'r') as f:
        return HTMLResponse(content=f.read())


@router.get("/motion_library.json")
async def serve_motion_library():
    """Serve motion library manifest."""
    manifest_path = Path(__file__).parent.parent / "ui" / "motion_library.json"
    
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Motion library not found")
    
    return FileResponse(manifest_path, media_type="application/json")


@router.get("/styles.css")
async def serve_css():
    """Serve CSS file."""
    css_path = Path(__file__).parent.parent / "ui" / "styles.css"
    
    if not css_path.exists():
        raise HTTPException(status_code=404, detail="CSS not found")
    
    return FileResponse(css_path, media_type="text/css")


# ========== Favicon Routes ==========

@router.get("/favicon.ico")
async def serve_favicon() -> FileResponse:
    """Serve favicon.ico file."""
    logger.debug("[ENTRY] serve_favicon: Serving favicon.ico")
    favicon_path = Path(__file__).parent.parent / "ui" / "favicon_io" / "favicon.ico"
    
    if not favicon_path.exists():
        logger.warning("[EXIT] serve_favicon: Favicon not found")
        raise HTTPException(status_code=404, detail="Favicon not found")
    
    logger.debug("[EXIT] serve_favicon: Favicon served successfully")
    return FileResponse(favicon_path, media_type="image/x-icon")


@router.get("/favicon-16x16.png")
async def serve_favicon_16() -> FileResponse:
    """Serve 16x16 favicon PNG."""
    logger.debug("[ENTRY] serve_favicon_16: Serving favicon-16x16.png")
    favicon_path = Path(__file__).parent.parent / "ui" / "favicon_io" / "favicon-16x16.png"
    
    if not favicon_path.exists():
        logger.warning("[EXIT] serve_favicon_16: Favicon not found")
        raise HTTPException(status_code=404, detail="Favicon 16x16 not found")
    
    logger.debug("[EXIT] serve_favicon_16: Favicon served successfully")
    return FileResponse(favicon_path, media_type="image/png")


@router.get("/favicon-32x32.png")
async def serve_favicon_32() -> FileResponse:
    """Serve 32x32 favicon PNG."""
    logger.debug("[ENTRY] serve_favicon_32: Serving favicon-32x32.png")
    favicon_path = Path(__file__).parent.parent / "ui" / "favicon_io" / "favicon-32x32.png"
    
    if not favicon_path.exists():
        logger.warning("[EXIT] serve_favicon_32: Favicon not found")
        raise HTTPException(status_code=404, detail="Favicon 32x32 not found")
    
    logger.debug("[EXIT] serve_favicon_32: Favicon served successfully")
    return FileResponse(favicon_path, media_type="image/png")


@router.get("/apple-touch-icon.png")
async def serve_apple_touch_icon() -> FileResponse:
    """Serve Apple touch icon for iOS devices."""
    logger.debug("[ENTRY] serve_apple_touch_icon: Serving apple-touch-icon.png")
    icon_path = Path(__file__).parent.parent / "ui" / "favicon_io" / "apple-touch-icon.png"
    
    if not icon_path.exists():
        logger.warning("[EXIT] serve_apple_touch_icon: Icon not found")
        raise HTTPException(status_code=404, detail="Apple touch icon not found")
    
    logger.debug("[EXIT] serve_apple_touch_icon: Icon served successfully")
    return FileResponse(icon_path, media_type="image/png")


@router.get("/android-chrome-192x192.png")
async def serve_android_chrome_192() -> FileResponse:
    """Serve Android Chrome 192x192 icon."""
    logger.debug("[ENTRY] serve_android_chrome_192: Serving android-chrome-192x192.png")
    icon_path = Path(__file__).parent.parent / "ui" / "favicon_io" / "android-chrome-192x192.png"
    
    if not icon_path.exists():
        logger.warning("[EXIT] serve_android_chrome_192: Icon not found")
        raise HTTPException(status_code=404, detail="Android Chrome 192 icon not found")
    
    logger.debug("[EXIT] serve_android_chrome_192: Icon served successfully")
    return FileResponse(icon_path, media_type="image/png")


@router.get("/android-chrome-512x512.png")
async def serve_android_chrome_512() -> FileResponse:
    """Serve Android Chrome 512x512 icon."""
    logger.debug("[ENTRY] serve_android_chrome_512: Serving android-chrome-512x512.png")
    icon_path = Path(__file__).parent.parent / "ui" / "favicon_io" / "android-chrome-512x512.png"
    
    if not icon_path.exists():
        logger.warning("[EXIT] serve_android_chrome_512: Icon not found")
        raise HTTPException(status_code=404, detail="Android Chrome 512 icon not found")
    
    logger.debug("[EXIT] serve_android_chrome_512: Icon served successfully")
    return FileResponse(icon_path, media_type="image/png")


@router.get("/site.webmanifest")
async def serve_webmanifest() -> FileResponse:
    """Serve PWA web manifest."""
    logger.debug("[ENTRY] serve_webmanifest: Serving site.webmanifest")
    manifest_path = Path(__file__).parent.parent / "ui" / "favicon_io" / "site.webmanifest"
    
    if not manifest_path.exists():
        logger.warning("[EXIT] serve_webmanifest: Manifest not found")
        raise HTTPException(status_code=404, detail="Web manifest not found")
    
    logger.debug("[EXIT] serve_webmanifest: Manifest served successfully")
    return FileResponse(manifest_path, media_type="application/manifest+json")


@router.get("/visualizer.js")
async def serve_js():
    """Serve JavaScript file."""
    js_path = Path(__file__).parent.parent / "ui" / "visualizer.js"
    
    if not js_path.exists():
        raise HTTPException(status_code=404, detail="JavaScript not found")
    
    return FileResponse(js_path, media_type="application/javascript")


@router.get("/workflow-visualizer.js")
async def serve_workflow_js():
    """Serve Workflow Visualizer JavaScript file."""
    js_path = Path(__file__).parent.parent / "ui" / "workflow-visualizer.js"
    
    if not js_path.exists():
        raise HTTPException(status_code=404, detail="Workflow visualizer JavaScript not found")
    
    return FileResponse(js_path, media_type="application/javascript")


@router.get("/metrics-dashboard.js")
async def serve_metrics_js():
    """Serve Metrics Dashboard JavaScript file."""
    js_path = Path(__file__).parent.parent / "ui" / "metrics-dashboard.js"
    
    if not js_path.exists():
        raise HTTPException(status_code=404, detail="Metrics dashboard JavaScript not found")
    
    return FileResponse(js_path, media_type="application/javascript")


# ========== Autonomous Commerce UI ==========

@router.get("/commerce", response_class=HTMLResponse)
async def serve_autonomous_commerce():
    """Serve the Autonomous Commerce marketplace UI."""
    ui_path = Path(__file__).parent.parent / "ui" / "autonomous-commerce.html"
    
    if not ui_path.exists():
        raise HTTPException(status_code=404, detail="Autonomous Commerce UI not found")
    
    with open(ui_path, 'r') as f:
        return HTMLResponse(content=f.read())


@router.get("/autonomous-commerce.js")
async def serve_autonomous_commerce_js():
    """Serve Autonomous Commerce JavaScript file."""
    js_path = Path(__file__).parent.parent / "ui" / "autonomous-commerce.js"
    
    if not js_path.exists():
        raise HTTPException(status_code=404, detail="Autonomous Commerce JavaScript not found")
    
    return FileResponse(js_path, media_type="application/javascript")


# Base path for FBX model files (works in both dev and Docker)
FBX_DIR = Path(__file__).parent.parent.parent.parent / "data" / "mixamo_anims" / "fbx"

@router.get("/static/models/Ch03_nonPBR.fbx")
async def serve_character_model():
    """Serve Michele character FBX model (legacy path, redirects to michelle.fbx)."""
    # Try new name first (michelle.fbx), then fall back to old name
    model_paths = [
        FBX_DIR / "michelle.fbx",
        Path(__file__).parent.parent.parent.parent / "Ch03_nonPBR.fbx",
    ]
    
    for model_path in model_paths:
        if model_path.exists():
            return FileResponse(model_path, media_type="application/octet-stream")
    
    raise HTTPException(status_code=404, detail="Character model not found")


@router.get("/static/models/michelle.fbx")
async def serve_michelle_character():
    """Serve Michelle character FBX model."""
    model_path = FBX_DIR / "michelle.fbx"
    
    if not model_path.exists():
        raise HTTPException(status_code=404, detail="Michelle character model not found")
    
    return FileResponse(model_path, media_type="application/octet-stream")


@router.get("/static/models/remy.fbx")
async def serve_remy_character():
    """Serve Remy character FBX model."""
    # Try both capitalizations
    model_paths = [
        FBX_DIR / "Remy.fbx",
        FBX_DIR / "remy.fbx",
    ]
    
    for model_path in model_paths:
        if model_path.exists():
            return FileResponse(model_path, media_type="application/octet-stream")
    
    raise HTTPException(status_code=404, detail="Remy character model not found")


@router.get("/static/models/X Bot@Capoeira.fbx")
async def serve_xbot_capoeira():
    """Serve X Bot Capoeira animation (temporary placeholder)."""
    model_path = FBX_DIR / "X Bot@Capoeira.fbx"
    
    if not model_path.exists():
        raise HTTPException(status_code=404, detail="X Bot model not found")
    
    return FileResponse(model_path, media_type="application/octet-stream")


@router.get("/static/models/michele/{filename}")
async def serve_michele_animations(filename: str):
    """Serve Michele character animations."""
    # Sanitize filename
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    model_path = FBX_DIR / "michele" / filename
    
    if not model_path.exists():
        raise HTTPException(status_code=404, detail=f"Michele animation not found: {filename}")
    
    return FileResponse(model_path, media_type="application/octet-stream")


@router.get("/static/models/data/mixamo_anims/fbx/{filename:path}")
async def serve_mixamo_fbx(filename: str):
    """Serve FBX files from mixamo_anims directory."""
    # Sanitize filename - allow @ and spaces in filenames
    if ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    model_path = FBX_DIR / filename
    
    if not model_path.exists():
        raise HTTPException(status_code=404, detail=f"FBX file not found: {filename}")
    
    return FileResponse(model_path, media_type="application/octet-stream")


@router.get("/static/animations/{filename:path}")
async def serve_animation_fbx(filename: str):
    """Serve animation FBX files from mixamo_anims directory."""
    # Sanitize filename - allow @ and spaces in filenames
    if ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    # URL decode the filename (spaces may be encoded as %20)
    from urllib.parse import unquote
    decoded_filename = unquote(filename)
    
    model_path = FBX_DIR / decoded_filename
    
    if not model_path.exists():
        raise HTTPException(status_code=404, detail=f"Animation FBX file not found: {decoded_filename}")
    
    return FileResponse(model_path, media_type="application/octet-stream")


@router.get("/api/motions/library")
async def get_motion_library():
    """
    Get motion library catalog.
    
    Returns list of available motions with metadata from Mixamo FBX files.
    Filters out character files (michelle.fbx, Remy.fbx) - only returns animations.
    """
    logger.info("Fetching motion library")
    
    # Path to FBX files
    fbx_dir = Path(__file__).parent.parent.parent.parent / "data" / "mixamo_anims" / "fbx"
    
    # Character files to exclude from animation list
    character_files = {'michelle.fbx', 'remy.fbx', 'ch03_nonpbr.fbx'}
    
    # Animations optimized for specific characters
    # Swing Dancing and Salsa Dancing are optimized for Remy
    # All others are mapped for Michelle
    remy_animations = {'swing dancing.fbx', 'salsa dancing.fbx'}
    
    motions = []
    
    if fbx_dir.exists():
        for fbx_file in fbx_dir.glob("*.fbx"):
            # Skip character files - they are not animations
            if fbx_file.name.lower() in character_files:
                continue
                
            # Extract motion name from filename
            # Example: "X Bot@Capoeira.fbx" -> "Capoeira"
            filename = fbx_file.stem
            motion_name = filename.split('@')[-1] if '@' in filename else filename
            
            # Determine character compatibility
            compatible_character = 'remy' if fbx_file.name.lower() in remy_animations else 'michelle'
            
            # Determine tags and icon based on motion name keywords
            tags = []
            icon = '🎭'  # Default icon
            name_lower = motion_name.lower()
            
            if any(word in name_lower for word in ['walk', 'run', 'jump', 'crouch']):
                tags.append('locomotion')
                icon = '🚶'
            if any(word in name_lower for word in ['salsa']):
                tags.append('dance')
                icon = '💃'
            elif any(word in name_lower for word in ['swing', 'charleston']):
                tags.append('dance')
                icon = '🕺'
            elif any(word in name_lower for word in ['hip hop', 'wave']):
                tags.append('dance')
                icon = '🎤'
            elif any(word in name_lower for word in ['breakdance']):
                tags.append('dance')
                icon = '🤸'
            elif any(word in name_lower for word in ['capoeira']):
                tags.append('dance')
                tags.append('combat')
                icon = '🥋'
            elif any(word in name_lower for word in ['dance']):
                tags.append('dance')
                icon = '💃'
            if any(word in name_lower for word in ['punch', 'kick', 'fight', 'combat']):
                tags.append('combat')
                icon = '👊'
            if any(word in name_lower for word in ['idle', 'stand', 'wait']):
                tags.append('idle')
                icon = '🧍'
            if 'freeze' in name_lower:
                tags.append('freeze')
            if any(word in name_lower for word in ['acrobat', 'flip', 'spin']):
                tags.append('acrobatic')
                icon = '🤸'
            if 'urban' in name_lower or 'street' in name_lower:
                tags.append('urban')
            
            # Generate motion metadata
            motion_id = motion_name.lower().replace(' ', '_').replace('-', '_')
            
            # URL path to serve this animation
            url_path = f"/static/animations/{fbx_file.name}"
            
            motions.append({
                "id": motion_id,
                "name": motion_name,
                "tags": tags if tags else ['other'],
                "icon": icon,
                "character": compatible_character,  # Character this animation is optimized for
                "duration": 3.5 + (hash(motion_name) % 50) / 10,  # Pseudo-random 3.5-8.5s
                "novelty": 0.5 + (hash(motion_name) % 40) / 100,  # Pseudo-random 0.5-0.9
                "filepath": str(fbx_file),
                "path": url_path,
                "frames": 100,  # Will be updated when loaded
                "fps": 30
            })
    
    # Fallback to sample data if no FBX files found
    if not motions:
        logger.warning("No FBX files found, using sample data")
        motions = [
            {
                "id": "capoeira",
                "name": "Capoeira",
                "tags": ["dance", "combat", "acrobatic"],
                "duration": 4.5,
                "novelty": 0.75,
                "filepath": "data/mixamo_anims/fbx/X Bot@Capoeira.fbx"
            },
            {
                "id": "breakdance_freeze",
                "name": "Breakdance Freeze",
                "tags": ["dance", "urban", "freeze"],
                "duration": 3.8,
                "novelty": 0.82,
                "filepath": "data/mixamo_anims/fbx/X Bot@Breakdance Freeze Var 2.fbx"
            }
        ]
    
    logger.info(f"Returning {len(motions)} motions")
    
    return {
        "motions": motions,
        "total": len(motions)
    }
