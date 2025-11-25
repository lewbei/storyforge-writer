"""
File reading tool for analyzing existing project content.
"""

import os
import time
from typing import List, Dict, Tuple, Optional
from .project import get_active_project_folder, is_valid_project_path


# Context caching for frequently-read files
_file_cache: Dict[str, Tuple[str, float, float]] = {}  # {filepath: (content, mtime, cache_time)}
_cache_stats = {"hits": 0, "misses": 0, "invalidations": 0}
_CACHE_TTL = 300  # 5 minutes TTL for cache entries
_MAX_CACHE_SIZE = 50  # Maximum number of cached files


def _get_cache_stats() -> str:
    """Return cache statistics for debugging."""
    total = _cache_stats["hits"] + _cache_stats["misses"]
    if total == 0:
        return "Cache: No requests yet"
    hit_rate = (_cache_stats["hits"] / total) * 100
    return (f"Cache Stats: {_cache_stats['hits']} hits, {_cache_stats['misses']} misses, "
            f"{_cache_stats['invalidations']} invalidations ({hit_rate:.1f}% hit rate)")


def _should_invalidate_cache(file_path: str, cached_mtime: float, cache_time: float) -> bool:
    """Check if cached file should be invalidated."""
    # Check TTL
    if time.time() - cache_time > _CACHE_TTL:
        return True
    
    # Check file modification time
    try:
        current_mtime = os.path.getmtime(file_path)
        if current_mtime > cached_mtime:
            return True
    except:
        return True  # File doesn't exist anymore
    
    return False


def _read_file_with_cache(file_path: str, filename: str) -> Tuple[str, bool]:
    """
    Read file with caching support.
    
    Returns:
        Tuple of (content, was_cached)
    """
    global _file_cache, _cache_stats
    
    # Check if file is in cache and still valid
    if file_path in _file_cache:
        content, cached_mtime, cache_time = _file_cache[file_path]
        
        if not _should_invalidate_cache(file_path, cached_mtime, cache_time):
            _cache_stats["hits"] += 1
            return (content, True)
        else:
            # Invalidate stale cache entry
            del _file_cache[file_path]
            _cache_stats["invalidations"] += 1
    
    # Cache miss - read from disk
    _cache_stats["misses"] += 1
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Add to cache (with LRU eviction if needed)
        if len(_file_cache) >= _MAX_CACHE_SIZE:
            # Evict oldest cache entry by cache_time
            oldest_key = min(_file_cache.keys(), key=lambda k: _file_cache[k][2])
            del _file_cache[oldest_key]
        
        mtime = os.path.getmtime(file_path)
        _file_cache[file_path] = (content, mtime, time.time())
        
        return (content, False)
    
    except Exception as e:
        raise Exception(f"Error reading {filename}: {str(e)}")


def clear_file_cache() -> str:
    """Clear the file cache. Useful for testing or after bulk file modifications."""
    global _file_cache, _cache_stats
    cache_size = len(_file_cache)
    _file_cache.clear()
    _cache_stats = {"hits": 0, "misses": 0, "invalidations": 0}
    return f"Cache cleared: {cache_size} entries removed"


def read_project_files_impl(filenames: List[str] = None) -> str:
    """
    Reads and returns content from files in the active project folder.
    
    Args:
        filenames: Optional list of specific files to read. If empty/None, reads all .md files.
        
    Returns:
        Combined file content with clear separators, or error message
    """
    # Check if project folder is initialized
    project_folder = get_active_project_folder()
    if not project_folder:
        return "STATUS: ERROR | No active project. Call create_project first to set or create a project folder."
    
    # Validate project folder is safe
    if not is_valid_project_path(project_folder):
        return "STATUS: ERROR | Active project folder is invalid or outside output directory."
    
    # Check project folder exists
    if not os.path.exists(project_folder):
        return "STATUS: ERROR | Active project folder does not exist. Create it first or check the path."
    
    try:
        # Determine which files to read
        if filenames and len(filenames) > 0:
            # Read specific files
            files_to_read = []
            for filename in filenames:
                # Basic validation
                if not filename:
                    continue
                if os.path.isabs(filename):
                    return f"STATUS: ERROR | Absolute paths not allowed: {filename}"
                # Check for path separators (but allow dots in filenames like "Chapter 1..md")
                if "/" in filename or "\\" in filename:
                    return f"STATUS: ERROR | Invalid filename (no path separators allowed): {filename}"
                # Check for path traversal sequences specifically
                if filename.startswith("..") or "/.." in filename or "\\.." in filename:
                    return f"STATUS: ERROR | Invalid filename (path traversal not allowed): {filename}"
                
                # Ensure .md extension
                if not filename.endswith('.md'):
                    filename = filename + '.md'
                
                file_path = os.path.join(project_folder, filename)
                
                # Verify it's under project folder
                if not file_path.startswith(project_folder):
                    return f"STATUS: ERROR | File path escapes project folder: {filename}"
                
                if os.path.exists(file_path) and os.path.isfile(file_path):
                    files_to_read.append((filename, file_path))
                else:
                    return f"STATUS: ERROR | File not found: {filename}"
        else:
            # Read all .md files in project folder
            files_to_read = []
            for item in os.listdir(project_folder):
                if item.endswith('.md') and not item.startswith('.'):
                    file_path = os.path.join(project_folder, item)
                    if os.path.isfile(file_path):
                        files_to_read.append((item, file_path))
            
            # Sort for consistent ordering
            files_to_read.sort(key=lambda x: x[0])
        
        if not files_to_read:
            return "STATUS: OK | No markdown files found in project folder."
        
        # Read and combine content
        combined_parts = []
        combined_parts.append(f"STATUS: OK | Read {len(files_to_read)} file(s) from project")
        combined_parts.append("=" * 60)
        
        total_chars = 0
        cached_count = 0
        for filename, file_path in files_to_read:
            try:
                content, was_cached = _read_file_with_cache(file_path, filename)
                if was_cached:
                    cached_count += 1
                
                total_chars += len(content)
                cache_marker = " [CACHED]" if was_cached else ""
                combined_parts.append(f"\n--- FILE: {filename}{cache_marker} ---")
                combined_parts.append(content)
                combined_parts.append(f"--- END: {filename} ({len(content)} chars) ---\n")
                
            except Exception as e:
                combined_parts.append(f"\n--- ERROR reading {filename}: {str(e)} ---\n")
        
        combined_parts.append("=" * 60)
        combined_parts.append(f"Total characters read: {total_chars:,} ({cached_count}/{len(files_to_read)} cached)")
        combined_parts.append(_get_cache_stats())
        
        return "\n".join(combined_parts)
    
    except Exception as e:
        return f"STATUS: ERROR | Failed to read project files: {str(e)}"
