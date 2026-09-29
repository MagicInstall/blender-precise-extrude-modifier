import bpy
import bmesh
import json
import urllib.request
import urllib.error
import os
import shutil
import zipfile
from mathutils import Vector
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from bpy.types import Operator, Panel, PropertyGroup
import threading
import sys

bl_info = {
    "name": "Precise Hard Surface Inflate",
    "author": "MagicInstall",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Hard Surface",
    "description": "Inflate selected hard-surface mesh regions with precise normal control and border retention.",
    "category": "Mesh",
    "doc_url": "https://github.com/MagicInstall/blender-precise-extrude-modifier",
    "tracker_url": "https://github.com/MagicInstall/blender-precise-extrude-modifier/issues",
    "support": "COMMUNITY",
}

# ============================================================================
# VERSION CHECK AND UPDATE SYSTEM
# ============================================================================

GITHUB_REPO = "MagicInstall/blender-precise-extrude-modifier"
GITHUB_API_RELEASES = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
PLUGIN_NAME = "blender-precise-extrude-modifier"


class UpdateChecker:
    def __init__(self):
        self.latest_version = None
        self.download_url = None
        self.update_available = False
        self.error_message = ""

    @staticmethod
    def parse_version(version_str):
        """Convert version string to tuple for comparison."""
        try:
            parts = version_str.strip('v').split('.')
            return tuple(int(p) for p in parts)
        except:
            return (0, 0, 0)

    def check_for_updates(self):
        """Check GitHub releases for new versions (runs in background thread)."""
        try:
            req = urllib.request.Request(
                GITHUB_API_RELEASES,
                headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "Blender"}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                
                if "tag_name" in data:
                    remote_version = self.parse_version(data["tag_name"])
                    current_version = bl_info["version"]
                    
                    if remote_version > current_version:
                        self.latest_version = data["tag_name"]
                        self.update_available = True
                        
                        # Find the zip asset download URL
                        for asset in data.get("assets", []):
                            if asset["name"].endswith(".zip"):
                                self.download_url = asset["browser_download_url"]
                                break
                        
                        if not self.download_url and "zipball_url" in data:
                            self.download_url = data["zipball_url"]
        except urllib.error.URLError as e:
            self.error_message = f"Network error: {str(e)}"
        except Exception as e:
            self.error_message = f"Check failed: {str(e)}"


update_checker = UpdateChecker()


def check_updates_background():
    """Run update check in background thread to avoid blocking UI."""
    thread = threading.Thread(target=update_checker.check_for_updates, daemon=True)
    thread.start()


class PHSI_OT_check_updates(Operator):
    bl_idname = "mesh.phsi_check_updates"
    bl_label = "Check for Updates"
    bl_description = "Check GitHub for new versions of this add-on"

    def execute(self, context):
        update_checker.check_for_updates()
        if update_checker.update_available:
            self.report({'INFO'}, f"Update available: {update_checker.latest_version}")
        else:
            self.report({'INFO'}, "You are running the latest version.")
        return {'FINISHED'}


class PHSI_OT_download_update(Operator):
    bl_idname = "mesh.phsi_download_update"
    bl_label = "Download and Install Update"
    bl_description = "Download the latest version and install it"

    def execute(self, context):
        if not update_checker.download_url:
            self.report({'ERROR'}, "No download URL available.")
            return {'CANCELLED'}
        
        try:
            # Download the zip file
            temp_path = os.path.join(bpy.utils.user_resource('TEMP'), f"{PLUGIN_NAME}_update.zip")
            urllib.request.urlretrieve(update_checker.download_url, temp_path)
            
            # Get the add-on path
            addon_dir = os.path.join(bpy.utils.user_resource('SCRIPTS'), "addons", PLUGIN_NAME)
            
            # Backup current version
            backup_dir = addon_dir + "_backup"
            if os.path.exists(addon_dir):
                if os.path.exists(backup_dir):
                    shutil.rmtree(backup_dir)
                shutil.copytree(addon_dir, backup_dir)
            
            # Extract and install
            extract_dir = os.path.join(bpy.utils.user_resource('TEMP'), f"{PLUGIN_NAME}_extract")
            if os.path.exists(extract_dir):
                shutil.rmtree(extract_dir)
            os.makedirs(extract_dir, exist_ok=True)
            
            with zipfile.ZipFile(temp_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            # Find the actual add-on directory in extracted files
            extracted_items = os.listdir(extract_dir)
            if extracted_items:
                source_dir = os.path.join(extract_dir, extracted_items[0])
                if os.path.isdir(source_dir):
                    if os.path.exists(addon_dir):
                        shutil.rmtree(addon_dir)
                    shutil.copytree(source_dir, addon_dir)
            
            # Cleanup
            os.remove(temp_path)
            shutil.rmtree(extract_dir, ignore_errors=True)
            
            # Reload the add-on
            import importlib
            if PLUGIN_NAME in sys.modules:
                importlib.reload(sys.modules[PLUGIN_NAME])
            
            self.report({'INFO'}, f"Updated to {update_checker.latest_version}. Please restart Blender.")
            return {'FINISHED'}
        
        except Exception as e:
            self.report({'ERROR'}, f"Update failed: {str(e)}")
            return {'CANCELLED'}


# ============================================================================
# MAIN PLUGIN CODE
# ============================================================================

class PHSIProperties(PropertyGroup):
    inflate_amount: FloatProperty(
        name="Inflate Amount",
        description="How far to push selected vertices along their normals",
        default=0.02,
        min=-2.0,
        max=10.0,
        precision=4,
        step=0.1,
    )

    offset_mode: EnumProperty(
        name="Offset Mode",
        description="Use local or world-space normals for the inflation direction",
        items=(
            ("LOCAL", "Local Normal", "Inflate along the object's local normals"),
            ("WORLD", "World Normal", "Inflate along world-space normals"),
        ),
        default="LOCAL",
    )

    keep_border: BoolProperty(
        name="Keep Border",
        description="Do not move vertices that lie on a mesh boundary",
        default=True,
    )

    use_smooth: BoolProperty(
        name="Smooth Result",
        description="Apply a small smoothing pass after inflation",
        default=False,
    )

    smooth_passes: IntProperty(
        name="Smooth Passes",
        description="How many smoothing iterations to apply",
        default=1,
        min=1,
        max=10,
    )

    update_status: StringProperty(
        name="Update Status",
        description="Current update status",
        default="Checking..."
    )


def _is_boundary_vertex(v):
    for edge in v.link_edges:
        if len(edge.link_faces) <= 1:
            return True
    return False


def _get_vertex_normal_local(obj, mesh, v_index):
    normal = Vector((0.0, 0.0, 0.0))
    for poly in mesh.polygons:
        if v_index in poly.vertices:
            normal += poly.normal
    if normal.length_squared > 0.0:
        normal.normalize()
    return normal


def _smooth_selected_vertices(obj, selected_vertices, passes):
    if passes <= 0:
        return

    for _ in range(passes):
        for v in selected_vertices:
            neighbors = []
            for edge in v.link_edges:
                for other in edge.verts:
                    if other.index != v.index and other in selected_vertices:
                        neighbors.append(other)
            if not neighbors:
                continue

            avg_delta = Vector((0.0, 0.0, 0.0))
            for other in neighbors:
                avg_delta += other.co - v.co
            avg_delta /= len(neighbors)
            v.co += avg_delta * 0.25


def _inflate_object_mode(obj, props):
    mesh = obj.data
    selected_verts = [v for v in mesh.vertices if v.select]
    if not selected_verts:
        return {'CANCELLED'}

    for v in selected_verts:
        if props.keep_border and _is_boundary_vertex_in_object(mesh, v.index):
            continue

        normal = _get_vertex_normal_local(obj, mesh, v.index)
        if props.offset_mode == "WORLD":
            direction = (obj.matrix_world.to_3x3() @ normal).normalized()
        else:
            direction = normal.normalized()

        v.co += direction * props.inflate_amount

    if props.use_smooth:
        _smooth_selected_vertices_for_object(obj, selected_verts, props.smooth_passes)

    mesh.update()
    return {'FINISHED'}


def _is_boundary_vertex_in_object(mesh, vertex_index):
    vertex = mesh.vertices[vertex_index]
    for edge in mesh.edges:
        if vertex_index in edge.vertices:
            if sum(1 for poly in mesh.polygons if edge.vertices[0] in poly.vertices and edge.vertices[1] in poly.vertices) <= 1:
                return True
    return False


def _smooth_selected_vertices_for_object(obj, selected_verts, passes):
    if passes <= 0 or not selected_verts:
        return

    for _ in range(passes):
        original = {v.index: v.co.copy() for v in selected_verts}
        for v in selected_verts:
            neighbors = []
            for edge in obj.data.edges:
                if v.index in edge.vertices:
                    other_index = edge.vertices[1] if edge.vertices[0] == v.index else edge.vertices[0]
                    if other_index in original and other_index != v.index:
                        neighbors.append(obj.data.vertices[other_index])
            if not neighbors:
                continue
            avg = sum((n.co - original[v.index]) for n in neighbors) / len(neighbors)
            v.co = original[v.index] + avg * 0.25

    obj.data.update()


def _inflate_edit_mode(obj, props):
    bm = bmesh.from_edit_mesh(obj.data)
    selected_verts = [v for v in bm.verts if v.select]
    if not selected_verts:
        return {'CANCELLED'}

    for v in selected_verts:
        if props.keep_border and _is_boundary_vertex(v):
            continue

        normal = Vector((0.0, 0.0, 0.0))
        for face in v.link_faces:
            normal += face.normal
        if normal.length_squared > 0.0:
            normal.normalize()

        if props.offset_mode == "WORLD":
            direction = (obj.matrix_world.to_3x3() @ normal).normalized()
        else:
            direction = normal.normalized()

        v.co += direction * props.inflate_amount

    if props.use_smooth:
        _smooth_selected_vertices(obj, selected_verts, props.smooth_passes)

    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    return {'FINISHED'}


class PHSI_OT_inflate(Operator):
    bl_idname = "mesh.phsi_inflate"
    bl_label = "Apply Inflate"
    bl_description = "Inflate the selected mesh region with precise normal control"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, "Select a mesh object first.")
            return {'CANCELLED'}

        props = context.scene.phsi_props

        if obj.mode == 'EDIT':
            return _inflate_edit_mode(obj, props)

        return _inflate_object_mode(obj, props)


class PHSI_PT_panel(Panel):
    bl_label = "Hard Surface"
    bl_idname = "PHSI_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Hard Surface'

    def draw(self, context):
        layout = self.layout
        props = context.scene.phsi_props

        # Main inflate controls
        box = layout.box()
        box.label(text="Inflate Settings", icon='OBJECT_DATA')
        box.prop(props, "inflate_amount")
        box.prop(props, "offset_mode")
        box.prop(props, "keep_border")
        box.prop(props, "use_smooth")
        if props.use_smooth:
            box.prop(props, "smooth_passes")
        box.operator("mesh.phsi_inflate", text="Apply Inflate")

        # Update check section
        box = layout.box()
        box.label(text="Updates", icon='PREFERENCES')
        
        if update_checker.update_available:
            box.alert = True
            box.label(text=f"Update available: {update_checker.latest_version}", icon='INFO')
            box.operator("mesh.phsi_download_update", text="Download & Install Update")
        else:
            box.label(text="You have the latest version", icon='CHECKMARK')
        
        box.operator("mesh.phsi_check_updates", text="Check for Updates")


classes = (
    PHSIProperties,
    PHSI_OT_inflate,
    PHSI_OT_check_updates,
    PHSI_OT_download_update,
    PHSI_PT_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.phsi_props = bpy.props.PointerProperty(type=PHSIProperties)
    
    # Check for updates when add-on is loaded
    check_updates_background()


def unregister():
    del bpy.types.Scene.phsi_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
    bpy.ops.object.select_all(action='DESELECT')
    print("Precise Hard Surface Inflate add-on loaded.")
