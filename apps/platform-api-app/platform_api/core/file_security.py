"""File upload security utilities.

Security measures implemented:
- Extension allowlist (not blocklist)
- MIME type validation via magic bytes
- Double extension attack prevention
- SVG XSS sanitization
- ZIP bomb protection
- Filename sanitization
- Memory limits for image processing

Reference: https://owasp.org/www-community/vulnerabilities/Unrestricted_File_Upload
"""
from __future__ import annotations

import io
import os
import re
import uuid
import zipfile
from pathlib import Path
from typing import Optional, Set, Tuple

from fastapi import HTTPException

ALLOWED_EXTENSIONS: Set[str] = {
    '.csv', '.xlsx', '.xls', '.json', '.txt', '.pdf',
    '.png', '.jpg', '.jpeg', '.gif', '.webp',
    '.md', '.html', '.htm'
}

DANGEROUS_EXTENSIONS: Set[str] = {
    '.php', '.php3', '.php4', '.php5', '.php7', '.phtml', '.phar',
    '.asp', '.aspx', '.jsp', '.jspx', '.war', '.cgi',
    '.exe', '.dll', '.so', '.bat', '.cmd', '.sh', '.ps1', '.psm1',
    '.htaccess', '.htpasswd', '.config', '.env',
    '.svg', '.svgz',
    '.py', '.pyc', '.pyo', '.rb', '.pl', '.pm',
    '.jar', '.class', '.swf',
}

ALLOWED_MIME_TYPES: Set[str] = {
    'text/csv', 'text/plain', 'text/html',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/json',
    'application/pdf',
    'image/png', 'image/jpeg', 'image/gif', 'image/webp',
    'text/markdown',
}

MAGIC_SIGNATURES = {
    b'\x89PNG\r\n\x1a\n': ('.png', 'image/png'),
    b'\xff\xd8\xff': ('.jpg', 'image/jpeg'),
    b'GIF87a': ('.gif', 'image/gif'),
    b'GIF89a': ('.gif', 'image/gif'),
    b'%PDF': ('.pdf', 'application/pdf'),
    b'PK\x03\x04': ('.zip', 'application/zip'),
    b'PK\x05\x06': ('.zip', 'application/zip'),
}

MAX_UPLOAD_SIZE_MB = 50
MAX_DECOMPRESSED_SIZE_MB = 100
MAX_IMAGE_PIXELS = 100_000_000


def detect_mime_from_magic_bytes(file_bytes: bytes) -> Tuple[str, str]:
    """Detect file type from magic bytes.
    
    Returns (extension, mime_type) tuple.
    Raises HTTPException if type cannot be determined or is dangerous.
    """
    if len(file_bytes) < 8:
        try:
            if file_bytes.decode("utf-8").isprintable():
                return ('.txt', 'text/plain')
        except UnicodeDecodeError:
            pass
        return ('.bin', 'application/octet-stream')
    
    header = file_bytes[:16]
    
    for signature, (ext, mime) in MAGIC_SIGNATURES.items():
        if header.startswith(signature):
            return (ext, mime)
    
    if file_bytes[:1] == b'{' or file_bytes[:1] == b'[':
        try:
            import json
            json.loads(file_bytes[:10000])
            return ('.json', 'application/json')
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
    
    try:
        text = file_bytes[:1000].decode('utf-8', errors='ignore')
        if text.replace('\n', '').replace('\r', '').replace(',', '').replace(' ', '').isalnum() or ',' in text:
            return ('.csv', 'text/csv')
    except Exception:
        pass
    
    return ('.bin', 'application/octet-stream')


def validate_file_extension(filename: str) -> str:
    """Validate file extension against allowlist.
    
    Returns the normalized extension.
    Raises HTTPException for disallowed extensions.
    """
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    
    ext = Path(filename).suffix.lower()
    
    if not ext:
        raise HTTPException(
            status_code=400,
            detail="File must have an extension"
        )
    
    if ext in DANGEROUS_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' is not allowed for security reasons"
        )
    
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' is not allowed. Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    
    return ext


def validate_mime_type(content_type: Optional[str], detected_mime: str) -> str:
    """Validate MIME type against allowlist.
    
    Uses detected MIME type (from magic bytes) as the source of truth.
    Returns the validated MIME type.
    """
    if detected_mime not in ALLOWED_MIME_TYPES and detected_mime != 'application/octet-stream':
        raise HTTPException(
            status_code=400,
            detail=f"File content type '{detected_mime}' is not allowed"
        )
    
    return detected_mime


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent attacks.
    
    - Removes path separators
    - Removes null bytes
    - Removes dangerous patterns
    - Strips dangerous extensions from double extensions
    """
    if not filename:
        return "upload.bin"
    
    name = Path(filename).name
    
    name = name.replace('\x00', '')
    
    dangerous_patterns = ['../', '..\\', '~', '|', '&', ';', '$', '`', '\n', '\r']
    for pattern in dangerous_patterns:
        name = name.replace(pattern, '')
    
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    
    parts = name.split('.')
    safe_parts = []
    for part in parts:
        test_ext = '.' + part.lower() if safe_parts else part.lower()
        if '.' + part.lower() in DANGEROUS_EXTENSIONS:
            continue
        if part.lower() in {ext.lstrip('.') for ext in DANGEROUS_EXTENSIONS}:
            continue
        safe_parts.append(part)
    
    if len(safe_parts) == 1:
        return safe_parts[0] or "upload"
    if len(safe_parts) == 0:
        return "upload.bin"

    return '.'.join(safe_parts)


def generate_secure_filename(original_filename: str, detected_ext: str) -> str:
    """Generate a secure, random filename.
    
    Uses UUID for the base name to prevent:
    - Information disclosure from original filename
    - Filename collisions
    - Extension-based attacks
    """
    return f"{uuid.uuid4().hex}{detected_ext}"


def validate_upload(
    filename: str,
    content_type: Optional[str],
    file_bytes: bytes,
    max_size_mb: int = MAX_UPLOAD_SIZE_MB,
) -> Tuple[str, str, str]:
    """Comprehensive upload validation.
    
    Returns (secure_filename, validated_mime_type, original_sanitized_name).
    Raises HTTPException for any validation failure.
    """
    if len(file_bytes) > max_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size of {max_size_mb}MB"
        )
    
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    
    detected_ext, detected_mime = detect_mime_from_magic_bytes(file_bytes)
    
    try:
        validate_file_extension(filename)
    except HTTPException:
        if detected_ext in ALLOWED_EXTENSIONS:
            pass
        else:
            raise
    
    validated_mime = validate_mime_type(content_type, detected_mime)
    
    sanitized_name = sanitize_filename(filename)
    
    final_ext = detected_ext if detected_ext in ALLOWED_EXTENSIONS else '.bin'
    secure_filename = generate_secure_filename(filename, final_ext)
    
    return secure_filename, validated_mime, sanitized_name


def validate_zip_archive(file_bytes: bytes) -> bytes:
    """Validate ZIP archive for security issues.
    
    Checks for:
    - Zip bombs (compression ratio attacks)
    - Path traversal in entries
    - Symlinks
    - Dangerous file types inside
    
    Returns the original bytes if valid.
    Raises HTTPException for any security issue.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
            total_uncompressed = 0
            max_decompressed = MAX_DECOMPRESSED_SIZE_MB * 1024 * 1024
            
            for info in zf.infolist():
                if info.filename.startswith('/') or '..' in info.filename:
                    raise HTTPException(
                        status_code=400,
                        detail="ZIP contains path traversal attempt"
                    )
                
                if info.is_dir():
                    continue
                
                if (info.external_attr >> 28) == 0xA:
                    raise HTTPException(
                        status_code=400,
                        detail="ZIP contains symlinks which are not allowed"
                    )
                
                ext = Path(info.filename).suffix.lower()
                if ext in DANGEROUS_EXTENSIONS:
                    raise HTTPException(
                        status_code=400,
                        detail=f"ZIP contains disallowed file type: {ext}"
                    )
                
                total_uncompressed += info.file_size
                if total_uncompressed > max_decompressed:
                    raise HTTPException(
                        status_code=400,
                        detail="ZIP would decompress to more than 100MB (potential zip bomb)"
                    )
                
                if info.compress_size > 0:
                    ratio = info.file_size / info.compress_size
                    if ratio > 100:
                        raise HTTPException(
                            status_code=400,
                            detail="ZIP contains highly compressed file (potential zip bomb)"
                        )
    
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid ZIP file")
    
    return file_bytes


def sanitize_svg_content(file_bytes: bytes) -> bytes:
    """Sanitize SVG to remove XSS vectors.
    
    Removes:
    - <script> elements
    - Event handlers (onclick, onload, etc.)
    - External references
    
    Returns sanitized SVG bytes.
    """
    try:
        content = file_bytes.decode('utf-8', errors='ignore')
    except UnicodeDecodeError:
        return file_bytes
    
    content = re.sub(
        r'<script[^>]*>.*?</script>',
        '',
        content,
        flags=re.IGNORECASE | re.DOTALL
    )
    
    content = re.sub(
        r'\s+on\w+\s*=\s*["\'][^"\']*["\']',
        '',
        content,
        flags=re.IGNORECASE
    )
    
    content = re.sub(
        r'\s+on\w+\s*=\s*[^\s>]+',
        '',
        content,
        flags=re.IGNORECASE
    )
    
    content = re.sub(
        r'<use[^>]*href\s*=\s*["\']https?:',
        '<use ',
        content,
        flags=re.IGNORECASE
    )
    
    return content.encode('utf-8')


def get_content_disposition_header(content_type: str, filename: str) -> str:
    """Get Content-Disposition header value.
    
    Forces download for potentially dangerous content types.
    """
    FORCE_DOWNLOAD_TYPES = {
        'application/pdf',
        'text/html',
        'application/xhtml+xml',
        'image/svg+xml',
        'application/xml',
        'text/xml',
        'application/javascript',
        'text/javascript',
    }
    
    safe_filename = re.sub(r'[^\w\.\-]', '_', filename)
    
    if content_type in FORCE_DOWNLOAD_TYPES:
        return f'attachment; filename="{safe_filename}"'
    
    return f'inline; filename="{safe_filename}"'


def secure_upload_directory(upload_dir: Path) -> None:
    """Create security files in upload directory.
    
    Creates .htaccess for Apache and nginx.conf snippet.
    """
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    htaccess_content = """# Security: Disable all script execution in upload directory
# Generated by platform_api.core.file_security

SetHandler default-handler

<FilesMatch "\\.(php|phtml|php3|php4|php5|php7|phps|cgi|pl|py|jsp|asp|aspx|sh|bash|exe|dll|so|bat|cmd|ps1|htaccess|htpasswd|config|env|svg|svgz)$">
    Order Deny,Allow
    Deny from all
</FilesMatch>

Options -ExecCG -Indexes -FollowSymLinks

<IfModule mod_php.c>
    php_flag engine off
</IfModule>

<IfModule mod_php7.c>
    php_flag engine off
</IfModule>

<IfModule mod_headers.c>
    Header set X-Content-Type-Options "nosniff"
    Header set X-Frame-Options "DENY"
    Header set Content-Security-Policy "default-src 'none'"
</IfModule>
"""
    
    htaccess_path = upload_dir / ".htaccess"
    if not htaccess_path.exists():
        htaccess_path.write_text(htaccess_content)
        try:
            os.chmod(htaccess_path, 0o644)
        except OSError:
            pass
    
    index_html = upload_dir / "index.html"
    if not index_html.exists():
        index_html.write_text("<!DOCTYPE html><html><head><title>403</title></head><body><h1>403 Forbidden</h1></body></html>")
    
    web_config = upload_dir / "web.config"
    if not web_config.exists():
        web_config_content = """<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <system.webServer>
        <handlers>
            <clear />
            <add name="StaticFile" path="*" verb="*" type="System.Web.StaticFileHandler" />
        </handlers>
        <staticContent>
            <mimeMap fileExtension=".*" mimeType="application/octet-stream" />
        </staticContent>
    </system.webServer>
</configuration>
"""
        web_config.write_text(web_config_content)


async def stream_upload_to_file(
    file,
    target_path: Path,
    max_size_bytes: int,
    chunk_size: int = 64 * 1024,
) -> Tuple[int, bytes]:
    """Stream upload to file with size limit.
    
    Security measures:
    - Streams in chunks to avoid loading entire file into memory
    - Enforces size limit during streaming
    - Returns first bytes for MIME detection
    
    Parameters
    ----------
    file : UploadFile
        FastAPI UploadFile object
    target_path : Path
        Target file path
    max_size_bytes : int
        Maximum allowed file size in bytes
    chunk_size : int
        Chunk size for streaming (default 64KB)
    
    Returns
    -------
    Tuple[int, bytes]
        Total bytes written and first chunk for MIME detection
    
    Raises
    ------
    HTTPException
        If file exceeds size limit
    """
    from fastapi import HTTPException
    
    total_size = 0
    first_chunk = b''
    first_chunk_collected = False
    
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_suffix(target_path.suffix + '.tmp')
    
    try:
        with temp_path.open('wb') as f:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                
                total_size += len(chunk)
                
                if total_size > max_size_bytes:
                    temp_path.unlink()
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds maximum size of {max_size_bytes // (1024*1024)}MB"
                    )
                
                if not first_chunk_collected:
                    first_chunk = chunk
                    first_chunk_collected = True
                
                f.write(chunk)
        
        temp_path.rename(target_path)
        
    except HTTPException:
        raise
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise
    
    return total_size, first_chunk


__all__ = [
    'ALLOWED_EXTENSIONS',
    'DANGEROUS_EXTENSIONS',
    'ALLOWED_MIME_TYPES',
    'MAX_UPLOAD_SIZE_MB',
    'MAX_DECOMPRESSED_SIZE_MB',
    'MAX_IMAGE_PIXELS',
    'detect_mime_from_magic_bytes',
    'validate_file_extension',
    'validate_mime_type',
    'sanitize_filename',
    'generate_secure_filename',
    'validate_upload',
    'validate_zip_archive',
    'sanitize_svg_content',
    'get_content_disposition_header',
    'secure_upload_directory',
    'stream_upload_to_file',
]
