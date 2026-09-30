import bpy
import json
import os
import shutil
import threading
import urllib.request
import urllib.error
import zipfile

bl_info = {
    "name": "Precise Hard Surface Inflate",
    "author": "MagicInstall",
    "version": (0, 1, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Hard Surface",
    "description": "Inflate selected hard-surface mesh regions with precise normal control and border retention.",
    "category": "Mesh",
    "doc_url": "https://github.com/MagicInstall/blender-precise-extrude-modifier",
    "tracker_url": "https://github.com/MagicInstall/blender-precise-extrude-modifier/issues",
    "support": "COMMUNITY",
}

GITHUB_REPO = "MagicInstall/blender-precise-extrude-modifier"
GITHUB_API_RELEASES = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
PLUGIN_FOLDER_NAME = "precise_hard_surface_inflate"


class GitHubReleaseUpdater:
    def __init__(self):
        self.latest_version = None
        self.download_url = None
        self.update_available = False
        self.error_message = ""

    @staticmethod
    def parse_version(version_str):
        try:
            value = version_str.strip().lstrip("v")
            parts = value.split(".")
            return tuple(int(p) for p in parts)
        except Exception:
            return (0, 0, 0)

    def check_for_updates(self):
        try:
            request = urllib.request.Request(
                GITHUB_API_RELEASES,
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "Blender-Precise-Hard-Surface-Inflate",
                },
            )
            with urllib.request.urlopen(request, timeout=6) as response:
                payload = json.loads(response.read().decode("utf-8"))
                tag_name = payload.get("tag_name")
                if not tag_name:
                    return

                remote_version = self.parse_version(tag_name)
                current_version = bl_info["version"]
                if remote_version > current_version:
                    self.latest_version = tag_name
                    self.update_available = True

                    for asset in payload.get("assets", []):
                        name = asset.get("name", "")
                        if name.lower().endswith(".zip"):
                            self.download_url = asset.get("browser_download_url")
                            break

                    if not self.download_url:
                        self.download_url = payload.get("zipball_url")
                else:
                    self.latest_version = None
                    self.update_available = False
                    self.download_url = None
        except urllib.error.URLError as exc:
            self.error_message = f"Network error: {exc}"
        except Exception as exc:
            self.error_message = f"Update check failed: {exc}"

    def install_update(self):
        if not self.download_url:
            raise RuntimeError("No release zip is available for this add-on.")

        temp_dir = os.path.join(bpy.utils.user_resource('TEMP'), "phsi_update")
        zip_path = os.path.join(temp_dir, "phsi_release.zip")
        extract_dir = os.path.join(temp_dir, "phsi_extracted")

        os.makedirs(temp_dir, exist_ok=True)
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)

        urllib.request.urlretrieve(self.download_url, zip_path)

        with zipfile.ZipFile(zip_path, "r") as archive:
            archive.extractall(extract_dir)

        extracted_root = os.path.join(extract_dir, os.listdir(extract_dir)[0])
        target_dir = os.path.join(bpy.utils.user_resource('SCRIPTS'), "addons", PLUGIN_FOLDER_NAME)
        backup_dir = target_dir + "_backup"

        if os.path.exists(target_dir):
            if os.path.exists(backup_dir):
                shutil.rmtree(backup_dir)
            shutil.copytree(target_dir, backup_dir)
            shutil.rmtree(target_dir)

        shutil.copytree(extracted_root, target_dir)

        if os.path.exists(zip_path):
            os.remove(zip_path)
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)

        return True


updater = GitHubReleaseUpdater()


def check_updates_async():
    thread = threading.Thread(target=updater.check_for_updates, daemon=True)
    thread.start()
