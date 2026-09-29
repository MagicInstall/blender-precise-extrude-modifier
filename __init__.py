import bpy

# Compatibility wrapper for direct add-on install from the repository root.
# Blender keeps this file as the add-on entry point when the repo root is installed.
try:
    from precise_hard_surface_inflate import *  # noqa: F401,F403
except ImportError:
    pass
