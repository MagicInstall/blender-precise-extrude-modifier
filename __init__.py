import bpy
import bmesh
from mathutils import Vector
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty
from bpy.types import Operator, Panel, PropertyGroup


bl_info = {
    "name": "Precise Hard Surface Inflate",
    "author": "MagicInstall",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Hard Surface",
    "description": "Inflate selected hard-surface mesh regions with precise normal control and border retention.",
    "category": "Mesh",
}


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

        layout.prop(props, "inflate_amount")
        layout.prop(props, "offset_mode")
        layout.prop(props, "keep_border")
        layout.prop(props, "use_smooth")
        if props.use_smooth:
            layout.prop(props, "smooth_passes")
        layout.operator("mesh.phsi_inflate", text="Apply Inflate")


classes = (
    PHSIProperties,
    PHSI_OT_inflate,
    PHSI_PT_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.phsi_props = bpy.props.PointerProperty(type=PHSIProperties)


def unregister():
    del bpy.types.Scene.phsi_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
    bpy.ops.object.select_all(action='DESELECT')
    print("Precise Hard Surface Inflate add-on loaded.")
