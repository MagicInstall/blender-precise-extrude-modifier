# Precise Hard Surface Inflate

A Blender add-on for fast, controllable inflation of hard-surface mesh selections, designed for mechanical, product, sci-fi, and industrial modeling workflows.

## Features

- Local or world-space inflation
- Border retention to reduce tearing and artifacts
- Edit Mode and Object Mode support
- Optional smoothing after inflation
- GitHub Releases based update detection and one-click installation
- Clean sidebar panel in 3D View

## Installation

Recommended install method:

1. Download the latest release zip from the GitHub Releases page.
2. In Blender, open Edit > Preferences > Add-ons.
3. Click Install…
4. Select the zip file.
5. Enable "Precise Hard Surface Inflate".

Developer install:

1. Clone or download this repository.
2. Copy the `precise_hard_surface_inflate` directory into Blender's user addons folder.
3. Restart Blender and enable the add-on.

## Usage

1. Select a mesh object.
2. Go to the 3D View sidebar.
3. Open the "Hard Surface" tab.
4. Adjust inflate amount and settings.
5. Click "Apply Inflate".

## Update system

The add-on checks GitHub Releases on load and can show an update button when a newer version is published. This is the most stable way to support auto-updates without depending on Blender's native add-on marketplace integration.

## Release workflow

This repository includes a GitHub Actions release workflow that creates a distributable zip package from the add-on folder and uploads it as a release asset.

## Versioning

Use semantic versioning in Git tags, for example:

- v1.0.0
- v1.1.0
- v1.2.3

## Repository

https://github.com/MagicInstall/blender-precise-extrude-modifier
