# Precise Hard Surface Inflate

A Blender add-on for fast, controllable inflation of hard-surface mesh selections. It is designed for mechanical, sci-fi, industrial, and product-style forms that need clean outward expansion while keeping borders and hard edges stable.

## Features

- Inflates selected mesh geometry along local or world normals
- Retains border vertices to reduce unwanted tearing
- Optional smoothing passes for cleaner transitions
- Supports both Object Mode and Edit Mode
- Clean panel under 3D View > Sidebar > Hard Surface

## Installation

1. Open Blender.
2. Go to Edit > Preferences > Add-ons.
3. Click Install…
4. Select this repository's `__init__.py` file.
5. Enable the add-on named "Precise Hard Surface Inflate".

## Usage

1. Select one or more mesh objects.
2. Open the sidebar in the 3D View (`N` key).
3. Go to the "Hard Surface" tab.
4. Adjust the inflate amount and mode.
5. Click "Apply Inflate".

## Recommended workflow

- Use a small inflate amount for precision shelling.
- Enable "Keep Border" for mechanical parts with sharp boundaries.
- Use world-space normal mode for large-scale object offsets.
- Use smoothing only after the main inflate pass.

## Notes

This add-on is intentionally lightweight and optimized for practical hard-surface modeling tasks. It does not attempt to mimic a full Blender modifier stack, but it behaves like a fast sculpt-style inflation utility for complex, precisely controlled mesh expansion.
