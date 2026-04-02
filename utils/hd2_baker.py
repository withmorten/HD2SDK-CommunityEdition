"""
HD2 Shader Baker Adapter

This module provides baking functionality for HD2 Shader node groups by leveraging
techniques from Principled Baker. It handles baking the Bake_X outputs from HD2
Shader nodes to textures.

The HD2 Shader node groups have specific outputs prefixed with "Bake_" that provide
the raw PBR values for baking:
- Bake_Color: Base color
- Bake_Normal: Normal map
- Bake_Metallic: Metallic value
- Bake_Roughness: Roughness value
- Bake_Ambient Occlusion: AO
- Bake_Alpha: Alpha/transparency

This adapter creates temporary node setups to route these outputs through emission
shaders for Cycles baking, then cleans up afterwards.
"""

import bpy
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


# Tag for identifying temporary nodes created during baking
HD2_BAKER_TAG = 'hd2_baker_temp_node'


@dataclass
class BakeJob:
    """Defines a single bake operation"""
    name: str  # Job name (e.g., "Color", "Normal")
    output_name: str  # HD2 Shader output name (e.g., "Bake_Color")
    is_color_data: bool = True  # True for sRGB, False for Non-Color
    default_color: Tuple[float, float, float, float] = (0.5, 0.5, 0.5, 1.0)
    needs_inverse_gamma: bool = False  # True if baked values need inverse gamma (power 1/2.2)


# Standard HD2 bake jobs
# Note: The HD2 Shader's Bake_Roughness, Bake_Metallic, and Bake_Ambient Occlusion outputs
# have gamma correction (POWER 2.2) applied. We need to apply inverse gamma to get correct
# linear values for use in Principled BSDF.
HD2_BAKE_JOBS = [
    BakeJob("Color", "Bake_Color", is_color_data=True, default_color=(0.5, 0.5, 0.5, 1.0), needs_inverse_gamma=False),
    BakeJob("Normal", "Bake_Normal", is_color_data=False, default_color=(0.5, 0.5, 1.0, 1.0), needs_inverse_gamma=False),
    BakeJob("Metallic", "Bake_Metallic", is_color_data=False, default_color=(0.0, 0.0, 0.0, 1.0), needs_inverse_gamma=True),
    BakeJob("Roughness", "Bake_Roughness", is_color_data=False, default_color=(0.5, 0.5, 0.5, 1.0), needs_inverse_gamma=True),
    BakeJob("Ambient Occlusion", "Bake_Ambient Occlusion", is_color_data=False, default_color=(1.0, 1.0, 1.0, 1.0), needs_inverse_gamma=True),
    BakeJob("Alpha", "Bake_Alpha", is_color_data=False, default_color=(1.0, 1.0, 1.0, 1.0), needs_inverse_gamma=False),
]


def find_hd2_shader_node(material: bpy.types.Material) -> Optional[bpy.types.ShaderNode]:
    """
    Find the HD2 Shader node group in a material.

    HD2 Shader nodes are identified by having outputs that start with "Bake_".

    Args:
        material: The Blender material to search

    Returns:
        The HD2 Shader node group, or None if not found
    """
    if not material or not material.node_tree:
        return None

    for node in material.node_tree.nodes:
        if node.type == 'GROUP' and node.node_tree:
            # Check if this node group has Bake_ outputs
            if any(out.name.startswith("Bake_") for out in node.outputs):
                return node
    return None


def has_hd2_shader(obj: bpy.types.Object) -> bool:
    """
    Check if an object has any materials with HD2 Shader node groups.

    Args:
        obj: The Blender object to check

    Returns:
        True if the object has at least one HD2 Shader material
    """
    if not obj.data.materials:
        return False

    for mat in obj.data.materials:
        if find_hd2_shader_node(mat):
            return True
    return False


def _create_temp_emission_node(material: bpy.types.Material,
                                color: Tuple[float, float, float, float] = (0, 0, 0, 1)) -> bpy.types.ShaderNode:
    """Create a temporary emission node for baking."""
    node = material.node_tree.nodes.new(type='ShaderNodeEmission')
    node.inputs['Color'].default_value = color
    node[HD2_BAKER_TAG] = 1
    node.name = "HD2_Baker_Emission"
    node.label = "HD2 Baker Temp (delete if visible)"
    node.use_custom_color = True
    node.color = (1, 0.3, 0.3)
    return node


def _create_temp_output_node(material: bpy.types.Material) -> bpy.types.ShaderNode:
    """Create a temporary material output node for baking."""
    node = material.node_tree.nodes.new(type='ShaderNodeOutputMaterial')
    node.is_active_output = True
    node[HD2_BAKER_TAG] = 1
    node.name = "HD2_Baker_Output"
    node.label = "HD2 Baker Temp (delete if visible)"
    node.use_custom_color = True
    node.color = (1, 0.3, 0.3)
    return node


def _create_temp_image_node(material: bpy.types.Material,
                            image: bpy.types.Image) -> bpy.types.ShaderNode:
    """Create a temporary image node to bake to."""
    node = material.node_tree.nodes.new(type='ShaderNodeTexImage')
    node.image = image
    node[HD2_BAKER_TAG] = 1
    node.name = "HD2_Baker_Image"
    node.label = "HD2 Baker Temp (delete if visible)"
    node.use_custom_color = True
    node.color = (1, 0.3, 0.3)
    node.select = True
    material.node_tree.nodes.active = node
    return node


def _create_temp_combine_xyz_node(material: bpy.types.Material) -> bpy.types.ShaderNode:
    """Create a temporary Combine XYZ node for converting float to vector."""
    node = material.node_tree.nodes.new(type='ShaderNodeCombineXYZ')
    node[HD2_BAKER_TAG] = 1
    node.name = "HD2_Baker_CombineXYZ"
    return node


def _get_active_material_output(material: bpy.types.Material) -> Optional[bpy.types.ShaderNode]:
    """Get the active material output node."""
    if not material or not material.node_tree:
        return None

    for node in material.node_tree.nodes:
        if node.type == 'OUTPUT_MATERIAL' and node.is_active_output:
            return node
    return None


def _deactivate_material_outputs(material: bpy.types.Material) -> List[bpy.types.ShaderNode]:
    """Deactivate all material outputs and return the list of previously active ones."""
    active_outputs = []
    if not material or not material.node_tree:
        return active_outputs

    for node in material.node_tree.nodes:
        if node.type == 'OUTPUT_MATERIAL':
            if node.is_active_output:
                active_outputs.append(node)
            node.is_active_output = False
    return active_outputs


def cleanup_temp_nodes(material: bpy.types.Material) -> None:
    """
    Remove all temporary nodes created during baking.

    Args:
        material: The material to clean up
    """
    if not material or not material.node_tree:
        return

    nodes_to_remove = []
    for node in material.node_tree.nodes:
        if HD2_BAKER_TAG in node.keys():
            nodes_to_remove.append(node)

    for node in nodes_to_remove:
        material.node_tree.nodes.remove(node)


def cleanup_temp_nodes_all_materials(obj: bpy.types.Object) -> None:
    """Remove temporary nodes from all materials on an object."""
    if not obj.data.materials:
        return

    for mat in obj.data.materials:
        if mat:
            cleanup_temp_nodes(mat)


def prepare_material_for_bake(material: bpy.types.Material,
                               hd2_shader_node: bpy.types.ShaderNode,
                               output_name: str,
                               image: bpy.types.Image) -> Tuple[bpy.types.ShaderNode, bpy.types.ShaderNode, List[bpy.types.ShaderNode]]:
    """
    Prepare a material for baking a specific HD2 Shader output.

    Creates temporary emission and output nodes, connects the specified
    HD2 Shader output to the emission node for baking.

    Args:
        material: The material to prepare
        hd2_shader_node: The HD2 Shader node group
        output_name: The name of the output to bake (e.g., "Bake_Color")
        image: The image to bake to

    Returns:
        Tuple of (emission_node, output_node, previously_active_outputs)
    """
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    # Store and deactivate current outputs
    prev_active_outputs = _deactivate_material_outputs(material)

    # Create temp nodes
    emission_node = _create_temp_emission_node(material)
    output_node = _create_temp_output_node(material)
    image_node = _create_temp_image_node(material, image)

    # Position temp nodes
    orig_output = prev_active_outputs[0] if prev_active_outputs else None
    if orig_output:
        emission_node.location = (orig_output.location.x + 200, orig_output.location.y + 100)
        output_node.location = (orig_output.location.x + 400, orig_output.location.y + 100)
        image_node.location = (orig_output.location.x, orig_output.location.y + 200)

    # Find the output socket on the HD2 Shader
    output_socket = None
    for output in hd2_shader_node.outputs:
        if output.name == output_name:
            output_socket = output
            break

    if output_socket:
        # Connect based on socket type
        if output_socket.type == 'RGBA' or output_socket.type == 'VECTOR':
            links.new(output_socket, emission_node.inputs['Color'])
        elif output_socket.type == 'VALUE':
            # Float value - convert to RGB using Combine XYZ
            combine = _create_temp_combine_xyz_node(material)
            combine.location = (emission_node.location.x - 150, emission_node.location.y)
            links.new(output_socket, combine.inputs['X'])
            links.new(output_socket, combine.inputs['Y'])
            links.new(output_socket, combine.inputs['Z'])
            links.new(combine.outputs[0], emission_node.inputs['Color'])

    # Connect emission to output
    links.new(emission_node.outputs['Emission'], output_node.inputs['Surface'])

    return emission_node, output_node, prev_active_outputs


def restore_material_after_bake(material: bpy.types.Material,
                                 prev_active_outputs: List[bpy.types.ShaderNode]) -> None:
    """
    Restore material state after baking.

    Removes temporary nodes and reactivates original outputs.

    Args:
        material: The material to restore
        prev_active_outputs: List of outputs that were previously active
    """
    # Remove temp nodes
    cleanup_temp_nodes(material)

    # Reactivate original outputs
    for output in prev_active_outputs:
        if output and output.name in material.node_tree.nodes:
            output.is_active_output = True


def apply_inverse_gamma(image: bpy.types.Image, gamma: float = 2.2) -> None:
    """
    Apply inverse gamma correction to an image in-place.

    The HD2 Shader's Bake_Roughness, Bake_Metallic, and Bake_AO outputs have
    gamma correction (POWER 2.2) applied. To get correct linear values for
    use in a Principled BSDF, we need to apply the inverse (POWER 1/2.2).

    Args:
        image: The Blender image to modify
        gamma: The gamma value to invert (default 2.2)
    """
    if not image or image.size[0] == 0:
        return

    inv_gamma = 1.0 / gamma
    pixels = list(image.pixels)

    # Apply inverse gamma to RGB channels only (not alpha)
    for i in range(0, len(pixels), 4):
        # Apply to R, G, B channels
        for c in range(3):
            val = pixels[i + c]
            if val > 0:
                pixels[i + c] = val ** inv_gamma

    image.pixels = pixels
    print(f"HD2Baker: Applied inverse gamma ({inv_gamma:.4f}) to {image.name}")


class HD2Baker:
    """
    Main baker class for HD2 Shader materials.

    This class handles the full baking workflow:
    1. Setup Cycles renderer
    2. Create bake images
    3. For each job, prepare material and bake
    4. Apply inverse gamma correction where needed
    5. Clean up and restore

    Example usage:
        baker = HD2Baker(context)
        baker.resolution = 1024
        baker.samples = 16

        results = baker.bake_object(obj)
        # results is a dict: {"Color": image, "Normal": image, ...}
    """

    def __init__(self, context: bpy.types.Context):
        self.context = context
        self.resolution = 1024
        self.samples = 16
        self.use_gpu = True

        # Store original settings
        self._orig_engine = None
        self._orig_samples = None
        self._orig_device = None

    def _setup_cycles(self) -> None:
        """Configure Cycles for baking."""
        scene = self.context.scene

        # Store originals
        self._orig_engine = scene.render.engine
        self._orig_samples = scene.cycles.samples
        try:
            self._orig_device = scene.cycles.device
        except:
            self._orig_device = 'CPU'

        # Set up Cycles
        scene.render.engine = 'CYCLES'
        scene.cycles.samples = self.samples

        if self.use_gpu:
            try:
                scene.cycles.device = 'GPU'
            except:
                scene.cycles.device = 'CPU'

    def _restore_settings(self) -> None:
        """Restore original render settings."""
        scene = self.context.scene

        if self._orig_engine:
            scene.render.engine = self._orig_engine
        if self._orig_samples:
            scene.cycles.samples = self._orig_samples
        if self._orig_device:
            try:
                scene.cycles.device = self._orig_device
            except:
                pass

    def _ensure_uv_layer(self, obj: bpy.types.Object) -> None:
        """Ensure the object has a UV layer for baking."""
        if "UVMap" not in obj.data.uv_layers:
            if len(obj.data.uv_layers) > 0:
                obj.data.uv_layers[0].name = "UVMap"
            else:
                obj.data.uv_layers.new(name="UVMap")

        obj.data.uv_layers["UVMap"].active = True
        obj.data.uv_layers["UVMap"].active_render = True

    def _create_bake_image(self, name: str, job: BakeJob) -> bpy.types.Image:
        """Create a new image for baking."""
        image = bpy.data.images.new(
            name=name,
            width=self.resolution,
            height=self.resolution,
            alpha=True,
            float_buffer=False
        )

        # Set color space
        if job.is_color_data:
            image.colorspace_settings.name = 'sRGB'
        else:
            image.colorspace_settings.name = 'Non-Color'

        # Fill with default color
        pixels = list(job.default_color) * (self.resolution * self.resolution)
        image.pixels = pixels

        return image

    def bake_object(self, obj: bpy.types.Object,
                    jobs: Optional[List[BakeJob]] = None) -> Dict[str, bpy.types.Image]:
        """
        Bake all specified jobs for an object.

        Args:
            obj: The object to bake
            jobs: List of BakeJob instances, or None to use default HD2_BAKE_JOBS

        Returns:
            Dictionary mapping job names to baked images
        """
        if jobs is None:
            jobs = HD2_BAKE_JOBS

        results = {}

        # Find HD2 Shader in first material with one
        hd2_mat = None
        hd2_shader = None
        for mat in obj.data.materials:
            shader = find_hd2_shader_node(mat)
            if shader:
                hd2_mat = mat
                hd2_shader = shader
                break

        if not hd2_shader:
            raise ValueError(f"No HD2 Shader found in {obj.name}")

        try:
            # Setup
            self._setup_cycles()
            self._ensure_uv_layer(obj)

            # Select only this object
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            self.context.view_layer.objects.active = obj

            # Bake each job
            for job in jobs:
                # Check if this output exists
                has_output = any(out.name == job.output_name for out in hd2_shader.outputs)

                if not has_output:
                    print(f"HD2Baker: Output {job.output_name} not found, using default")
                    # Create default image
                    image = self._create_bake_image(f"bake_{job.name}_{obj.name}", job)
                    results[job.name] = image
                    continue

                # Create image
                image = self._create_bake_image(f"bake_{job.name}_{obj.name}", job)

                # Prepare material
                emission, output, prev_outputs = prepare_material_for_bake(
                    hd2_mat, hd2_shader, job.output_name, image
                )

                try:
                    # Bake
                    bpy.ops.object.bake(type='EMIT', use_clear=True)
                    print(f"HD2Baker: Baked {job.name}")

                    # Apply inverse gamma correction if needed
                    # The HD2 Shader's Bake_ outputs for Metallic, Roughness, and AO
                    # have gamma correction applied, which we need to undo
                    if job.needs_inverse_gamma:
                        apply_inverse_gamma(image)

                    results[job.name] = image
                except Exception as e:
                    print(f"HD2Baker: Bake failed for {job.name}: {e}")
                    # Keep the default-filled image
                    results[job.name] = image
                finally:
                    # Restore material
                    restore_material_after_bake(hd2_mat, prev_outputs)

        finally:
            # Cleanup
            self._restore_settings()
            cleanup_temp_nodes_all_materials(obj)

        return results

    def bake_objects(self, objects: List[bpy.types.Object],
                     jobs: Optional[List[BakeJob]] = None) -> Dict[str, Dict[str, bpy.types.Image]]:
        """
        Bake multiple objects.

        Args:
            objects: List of objects to bake
            jobs: List of BakeJob instances, or None to use default

        Returns:
            Dictionary mapping object names to their bake results
        """
        all_results = {}

        for obj in objects:
            if has_hd2_shader(obj):
                try:
                    results = self.bake_object(obj, jobs)
                    all_results[obj.name] = results
                except Exception as e:
                    print(f"HD2Baker: Failed to bake {obj.name}: {e}")

        return all_results


def pack_channels(images: Dict[str, bpy.types.Image],
                  channel_config: Dict[str, Tuple[str, Optional[str]]],
                  resolution: int,
                  name: str = "packed") -> bpy.types.Image:
    """
    Pack multiple baked images into a single image with specific channel mapping.

    Args:
        images: Dictionary mapping job names to baked images
        channel_config: Dictionary mapping output channel ('R', 'G', 'B', 'A') to
                       (source_job_name, source_channel or None for grayscale)
                       Use ("constant", value) for constant values
        resolution: Output resolution
        name: Name for the packed image

    Returns:
        New packed image

    Example:
        # Pack Metallic->R, Roughness->G, AO->B
        packed = pack_channels(baked_images, {
            'R': ("Metallic", None),  # None = use as grayscale
            'G': ("Roughness", None),
            'B': ("Ambient Occlusion", None),
            'A': ("constant", 1.0),
        }, 1024, "PBR")
    """
    packed = bpy.data.images.new(name, resolution, resolution, alpha=True)
    pixels = [0.0] * (resolution * resolution * 4)

    channel_indices = {'R': 0, 'G': 1, 'B': 2, 'A': 3}

    for channel_name, (source, src_channel) in channel_config.items():
        channel_idx = channel_indices[channel_name]

        if source == "constant":
            # Fill with constant value
            value = src_channel
            for i in range(resolution * resolution):
                pixels[i * 4 + channel_idx] = value

        elif source in images:
            src_img = images[source]
            src_pixels = list(src_img.pixels)

            if src_channel is None:
                # Use R channel (grayscale)
                for i in range(resolution * resolution):
                    pixels[i * 4 + channel_idx] = src_pixels[i * 4]
            else:
                # Use specific channel
                src_idx = channel_indices[src_channel]
                for i in range(resolution * resolution):
                    pixels[i * 4 + channel_idx] = src_pixels[i * 4 + src_idx]
        else:
            # Source not found, use default
            default_val = 0.5 if channel_name != 'A' else 1.0
            for i in range(resolution * resolution):
                pixels[i * 4 + channel_idx] = default_val

    packed.pixels = pixels
    return packed
