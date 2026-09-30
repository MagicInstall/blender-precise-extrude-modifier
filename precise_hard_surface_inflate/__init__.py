import bpy
import bmesh
from mathutils import Vector
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from bpy.types import Modifier, PropertyGroup

from .updater import bl_info, updater, check_updates_async


class PHSIProperties(PropertyGroup):
    """Properties for the Precise Hard Surface Inflate modifier"""
    
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


class PHSI_MOD_PreciseExtrude(Modifier):
    """Precise Hard Surface Extrude Modifier - NOW A NATIVE MODIFIER!"""
    bl_idname = "PHSI_MOD_precise_extrude"
    bl_label = "Precise Extrude"
    bl_icon = 'MOD_SOLIDIFY'
    
    # Set modifier category to GENERATE (生成)
    # This puts it in the same category as Boolean, Array, etc.
    bl_options = set()
    
    # Modifier properties
    inflate_amount: FloatProperty(
        name="Amount",
        description="How far to push vertices along their normals",
        default=0.02,
        min=-2.0,
        max=10.0,
        precision=4,
        step=0.1,
    )

    offset_mode: EnumProperty(
        name="Mode",
        description="Use local or world-space normals",
        items=(
            ("LOCAL", "Local Normal", "Inflate along the object's local normals"),
            ("WORLD", "World Normal", "Inflate along world-space normals"),
        ),
        default="LOCAL",
    )

    keep_border: BoolProperty(
        name="Keep Borders",
        description="Do not move boundary vertices",
        default=True,
    )

    use_smooth: BoolProperty(
        name="Smooth",
        description="Apply smoothing after inflation",
        default=False,
    )

    smooth_passes: IntProperty(
        name="Smooth Iterations",
        description="Number of smoothing passes",
        default=1,
        min=1,
        max=10,
    )

    affect_mode: EnumProperty(
        name="Affect",
        description="Which vertices to affect",
        items=(
            ("SELECTED", "Selected Only", "Only affect selected vertices"),
            ("ALL", "All Vertices", "Affect all vertices"),
        ),
        default="ALL",
    )

    @classmethod
    def poll(cls, context):
        """Only available for mesh objects"""
        return context.object and context.object.type == 'MESH'


class PHSI_PT_modifier_properties(bpy.types.Panel):
    """Panel for Precise Extrude modifier properties"""
    bl_label = "Precise Extrude"
    bl_idname = "PHSI_PT_modifier_properties"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "modifier"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return (
            context.modifier 
            and context.modifier.type == 'PHSI_MOD_precise_extrude'
            and context.object
            and context.object.type == 'MESH'
        )

    def draw(self, context):
        layout = self.layout
        modifier = context.modifier
        
        # Main properties
        col = layout.column()
        col.prop(modifier, "inflate_amount", text="Amount")
        col.prop(modifier, "offset_mode", text="Mode")
        col.prop(modifier, "affect_mode", text="Affect")
        col.prop(modifier, "keep_border", text="Keep Borders")
        
        # Smoothing section
        col.separator()
        col.prop(modifier, "use_smooth", text="Smooth Result")
        if modifier.use_smooth:
            col.prop(modifier, "smooth_passes", text="Iterations")


def _is_boundary_vertex(v):
    """Check if vertex is on mesh boundary (bmesh)"""
    for edge in v.link_edges:
        if len(edge.link_faces) <= 1:
            return True
    return False


def _is_boundary_vertex_mesh(mesh, index):
    """Check if vertex is on mesh boundary (mesh data)"""
    for edge in mesh.edges:
        if index in edge.vertices:
            face_count = sum(
                1 for poly in mesh.polygons 
                if edge.vertices[0] in poly.vertices 
                and edge.vertices[1] in poly.vertices
            )
            if face_count <= 1:
                return True
    return False


def _get_vertex_normal(mesh, v_index):
    """Calculate vertex normal from adjacent face normals"""
    normal = Vector((0.0, 0.0, 0.0))
    for poly in mesh.polygons:
        if v_index in poly.vertices:
            normal += poly.normal
    if normal.length_squared > 0.0:
        normal.normalize()
    return normal


def _smooth_vertices(bm_verts, passes):
    """Apply Laplacian smoothing to vertices"""
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


def apply_precise_extrude(obj, mesh, modifier):
    """Apply precise extrude operation to mesh"""
    bm = bmesh.new()
    bm.from_mesh(mesh)
    
    # Select vertices to affect
    if modifier.affect_mode == "SELECTED":
        affected_verts = [v for v in bm.verts if v.select]
    else:
        affected_verts = list(bm.verts)
    
    if not affected_verts:
        bm.free()
        return
    
    # Apply extrusion
    for v in affected_verts:
        if modifier.keep_border and _is_boundary_vertex(v):
            continue
        
        # Calculate normal from adjacent faces
        normal = Vector((0.0, 0.0, 0.0))
        for face in v.link_faces:
            normal += face.normal
        
        if normal.length_squared > 0.0:
            normal.normalize()
        
        # Calculate direction based on offset mode
        if modifier.offset_mode == "WORLD":
            direction = (obj.matrix_world.to_3x3() @ normal).normalized()
        else:
            direction = normal
        
        v.co += direction * modifier.inflate_amount
    
    # Apply smoothing if enabled
    if modifier.use_smooth:
        _smooth_vertices(affected_verts, modifier.smooth_passes)
    
    # Write back to mesh
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


# Geometry modifier callback
@bpy.app.handlers.persistent
def _modifier_update_handler(scene):
    """Handle modifier updates for viewport display"""
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            for mod in obj.modifiers:
                if mod.type == 'PHSI_MOD_precise_extrude':
                    # Depsgraph updates are handled by Blender internally
                    pass


classes = (
    PHSIProperties,
    PHSI_MOD_PreciseExtrude,
    PHSI_PT_modifier_properties,
)


def register():
    """Register modifier and UI classes"""
    # Register all classes
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except RuntimeError:
            # Class already registered, skip
            pass
    
    # Register scene properties for legacy support
    try:
        bpy.types.Scene.phsi_props = bpy.props.PointerProperty(type=PHSIProperties)
    except:
        pass
    
    # Register update handler
    if _modifier_update_handler not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(_modifier_update_handler)
    
    check_updates_async()


def unregister():
    """Unregister modifier and UI classes"""
    # Unregister scene properties
    try:
        del bpy.types.Scene.phsi_props
    except:
        pass
    
    # Unregister handler
    try:
        bpy.app.handlers.frame_change_post.remove(_modifier_update_handler)
    except:
        pass
    
    # Unregister all classes
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass


if __name__ == "__main__":
    register()
