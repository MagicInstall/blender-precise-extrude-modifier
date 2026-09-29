import bpy
import bmesh
import sys
import importlib
from mathutils import Vector
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from bpy.types import Operator, Panel, PropertyGroup

from .updater import bl_info, updater, check_updates_async


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
        description="Do not move vertices on mesh boundaries",
        default=True,
    )

    use_smooth: BoolProperty(
        name="Smooth Result",
        description="Apply a smoothing pass after inflation",
        default=False,
    )

    smooth_passes: IntProperty(
        name="Smooth Passes",
        description="Number of smoothing iterations",
        default=1,
        min=1,
        max=10,
    )


class PHSI_OT_check_updates(Operator):
    bl_idname = "mesh.phsi_check_updates"
    bl_label = "Check for Updates"
    bl_description = "Check GitHub releases for a newer version of this add-on"

    def execute(self, context):
        updater.check_for_updates()
        if updater.update_available:
            self.report({'INFO'}, f"Update available: {updater.latest_version}")
        else:
            self.report({'INFO'}, "You are running the latest version.")
        return {'FINISHED'}


class PHSI_OT_download_update(Operator):
    bl_idname = "mesh.phsi_download_update"
    bl_label = "Download and Install Update"
    bl_description = "Download and install the latest released version of this add-on"

    def execute(self, context):
        if not updater.download_url:
            self.report({'ERROR'}, "No update package is available.")
            return {'CANCELLED'}

        try:
            updater.install_update()
            self.report({'INFO'}, f"Updated to {updater.latest_version}. Please restart Blender.")
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, f"Update failed: {exc}")
            return {'CANCELLED'}


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

        box = layout.box()
        box.label(text="Inflate Settings", icon='OBJECT_DATA')
        box.prop(props, "inflate_amount")
        box.prop(props, "offset_mode")
        box.prop(props, "keep_border")
        box.prop(props, "use_smooth")
        if props.use_smooth:
            box.prop(props, "smooth_passes")
        box.operator("mesh.phsi_inflate", text="Apply Inflate")

        update_box = layout.box()
        update_box.label(text="Updates", icon='PREFERENCES')
        if updater.update_available:
            update_box.alert = True
            update_box.label(text=f"Update available: {updater.latest_version}", icon='INFO')
            update_box.operator("mesh.phsi_download_update", text="Download & Install Update")
        else:
            update_box.label(text="You are running the latest version", icon='CHECKMARK')
        update_box.operator("mesh.phsi_check_updates", text="Check for Updates")


def _is_boundary_vertex(v):
    for edge in v.link_edges:
        if len(edge.link_faces) <= 1:
            return True
    return False


def _is_boundary_vertex_in_object(mesh, index):
    for edge in mesh.edges:
        if index in edge.vertices:
            if sum(1 for poly in mesh.polygons if edge.vertices[0] in poly.vertices and edge.vertices[1] in poly.vertices) <= 1:
                return True
    return False


def _get_vertex_normal_local(mesh, v_index):
    normal = Vector((0.0, 0.0, 0.0))
    for poly in mesh.polygons:
        if v_index in poly.vertices:
            normal += poly.normal
    if normal.length_squared > 0.0:
        normal.normalize()
    return normal


def _smooth_selected_vertices(bm_verts, passes):
    if passes <= 0:
        return
    for _ in range(passes):
        for v in bm_verts:
            neighbors = []
            for edge in v.link_edges:
                for other in edge.verts:
                    if other.index != v.index and other in bm_verts:
                        neighbors.append(other)
            if not neighbors:
                continue
            avg_delta = Vector((0.0, 0.0, 0.0))
            for other in neighbors:
                avg_delta += other.co - v.co
            avg_delta /= len(neighbors)
            v.co += avg_delta * 0.25


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

        direction = (obj.matrix_world.to_3x3() @ normal).normalized() if props.offset_mode == "WORLD" else normal.normalized()
        v.co += direction * props.inflate_amount

    if props.use_smooth:
        _smooth_selected_vertices(selected_verts, props.smooth_passes)

    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    return {'FINISHED'}


def _inflate_object_mode(obj, props):
    mesh = obj.data
    selected_verts = [v for v in mesh.vertices if v.select]
    if not selected_verts:
        return {'CANCELLED'}

    for v in selected_verts:
        if props.keep_border and _is_boundary_vertex_in_object(mesh, v.index):
            continue
        normal = _get_vertex_normal_local(mesh, v.index)
        direction = (obj.matrix_world.to_3x3() @ normal).normalized() if props.offset_mode == "WORLD" else normal.normalized()
        v.co += direction * props.inflate_amount

    if props.use_smooth:
        for _ in range(props.smooth_passes):
            for v in selected_verts:
                neighbors = []
                for edge in mesh.edges:
                    if v.index in edge.vertices:
                        other_index = edge.vertices[1] if edge.vertices[0] == v.index else edge.vertices[0]
                        if other_index in {vv.index for vv in selected_verts}:
                            neighbors.append(mesh.vertices[other_index])
                if not neighbors:
                    continue
                avg = sum((n.co - v.co) for n in neighbors) / len(neighbors)
                v.co += avg * 0.25

    mesh.update()
    return {'FINISHED'}


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
    check_updates_async()


def unregister():
    del bpy.types.Scene.phsi_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
