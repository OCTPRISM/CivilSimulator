#!/usr/bin/env python3
"""
Blender 5.x — 汉代游侠剑客 v0.5 (face + light outfit + 环首刀)

Prompt-aligned: middle-aged swordsman, amber eyes, nose scar, Han dynasty
shenyi (深衣交领), wide sleeves, leather lamellar, bronze belt hook, battle cloak,
jian + scabbard, rain/fireflies, teal-orange cinematic lighting.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
    --python backend/scripts/hero_compiler/blender_ronin_swordsman.py

Outputs:
  frontend/public/models/characters/hero/wuxia_wanderer/ronin_cinematic_v0.5.blend
  frontend/public/models/characters/hero/wuxia_wanderer/ronin_cinematic_v0.5.glb
  frontend/public/models/characters/hero/wuxia_wanderer/preview_ronin_v0.5.png
"""
from __future__ import annotations

import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Euler, Vector

try:
    ROOT = Path(__file__).resolve().parents[3]
except NameError:
    ROOT = Path("/Users/roger/Code/CivilSimulator")
OUT_DIR = ROOT / "frontend/public/models/characters/hero/wuxia_wanderer"
VERSION = "v0.9"
BLEND_OUT = OUT_DIR / f"ronin_cinematic_{VERSION}.blend"
GLB_OUT = OUT_DIR / f"ronin_cinematic_{VERSION}.glb"
PREVIEW_OUT = OUT_DIR / f"preview_ronin_{VERSION}.png"
FACE_PREVIEW_OUT = OUT_DIR / f"preview_face_{VERSION}.png"
CHAR_ONLY_GLB = OUT_DIR / f"ronin_character_{VERSION}.glb"


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in list(bpy.data.meshes):
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for mat in list(bpy.data.materials):
        if mat.users == 0:
            bpy.data.materials.remove(mat)


def mat_principled(name: str, base_color=(0.8, 0.8, 0.8, 1.0), roughness=0.45,
                   metallic=0.0, emissive=(0, 0, 0), emissive_strength=0.0,
                   subsurface=0.0, subsurface_color=(0.8, 0.5, 0.4)):
    m = bpy.data.materials.new(name=name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*base_color[:3], 1)
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (*emissive[:3], 1)
            bsdf.inputs["Emission Strength"].default_value = emissive_strength
        if subsurface > 0:
            if "Subsurface Weight" in bsdf.inputs:
                bsdf.inputs["Subsurface Weight"].default_value = subsurface
                if "Subsurface Color" in bsdf.inputs:
                    bsdf.inputs["Subsurface Color"].default_value = (*subsurface_color[:3], 1)
            elif "Subsurface" in bsdf.inputs:
                bsdf.inputs["Subsurface"].default_value = subsurface
                if "Subsurface Color" in bsdf.inputs:
                    bsdf.inputs["Subsurface Color"].default_value = (*subsurface_color[:3], 1)
    return m


def mat_han_hemp_inner(name: str = "Han_Hemp_Inner"):
    """Inner garment — undyed hemp / plain weave."""
    m = bpy.data.materials.new(name=name)
    m.use_nodes = True
    nt = m.node_tree
    nodes, links = nt.nodes, nt.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 55.0
    noise.inputs["Detail"].default_value = 4.0
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.62, 0.58, 0.5, 1)
    ramp.color_ramp.elements[1].color = (0.72, 0.68, 0.6, 1)
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.82
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


def mat_han_shenyi_outer(name: str = "Han_Shenyi_Outer"):
    """Outer deep robe (玄色深衣) — worn hemp-silk with subtle Han cloud motif."""
    m = bpy.data.materials.new(name=name)
    m.use_nodes = True
    nt = m.node_tree
    nodes, links = nt.nodes, nt.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    wear = nodes.new("ShaderNodeTexNoise")
    wear.inputs["Scale"].default_value = 14.0
    wear.inputs["Detail"].default_value = 5.0
    wear_ramp = nodes.new("ShaderNodeValToRGB")
    wear_ramp.color_ramp.elements[0].color = (0.05, 0.06, 0.1, 1)
    wear_ramp.color_ramp.elements[1].color = (0.11, 0.13, 0.22, 1)
    cloud = nodes.new("ShaderNodeTexWave")
    cloud.wave_type = "BANDS"
    cloud.inputs["Scale"].default_value = 6.5
    cloud.inputs["Distortion"].default_value = 3.2
    trim = nodes.new("ShaderNodeMix")
    trim.data_type = "RGBA"
    trim.inputs["Factor"].default_value = 0.18
    trim.inputs["A"].default_value = (0.08, 0.1, 0.18, 1)
    trim.inputs["B"].default_value = (0.42, 0.12, 0.1, 1)
    links.new(wear.outputs["Fac"], wear_ramp.inputs["Fac"])
    links.new(wear_ramp.outputs["Color"], trim.inputs["A"])
    links.new(cloud.outputs["Color"], trim.inputs["Factor"])
    links.new(trim.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.74
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


def mat_han_leather_lamellar(name: str = "Han_Leather_Armor"):
    """Han leather lamellar (皮札甲 / 两当) — laced brown hide."""
    m = mat_principled(name, (0.18, 0.11, 0.07, 1), roughness=0.62, metallic=0.05)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 28.0
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "RINGS"
    wave.inputs["Scale"].default_value = 22.0
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "FLOAT"
    mix.inputs["Factor"].default_value = 0.45
    mix.inputs["A"].default_value = 0.55
    mix.inputs["B"].default_value = 0.78
    nt.links.new(wave.outputs["Color"], mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], bsdf.inputs["Roughness"])
    nt.links.new(noise.outputs["Fac"], bsdf.inputs["Base Color"])
    return m


def mat_han_bronze(name: str = "Han_Bronze"):
    return mat_principled(name, (0.52, 0.38, 0.18, 1), roughness=0.38, metallic=0.88)


def mat_han_cloak(name: str = "Han_BattleCloak"):
    """Faded wanderer's short cloak (氅) — moss-brown hemp."""
    m = mat_principled(name, (0.12, 0.16, 0.1, 1), roughness=0.9)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 9.0
    nt.links.new(noise.outputs["Fac"], bsdf.inputs["Roughness"])
    return m


def mat_han_boot(name: str = "Han_Boot"):
    return mat_principled(name, (0.14, 0.1, 0.08, 1), roughness=0.7)


def assign_mat(obj, mat):
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


def add_subdiv(obj, levels=1):
    mod = obj.modifiers.new("Subdiv", "SUBSURF")
    mod.levels = levels
    mod.render_levels = levels


def parent_objects(parent, objs):
    for o in objs:
        if o:
            o.parent = parent


def mat_skin_cinematic(name: str = "Skin_Cinematic"):
    """Middle-aged Asian skin — SSS, pores, stubble mask, temple veins, scar zone."""
    m = bpy.data.materials.new(name=name)
    m.use_nodes = True
    nt = m.node_tree
    nodes, links = nt.nodes, nt.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (680, 0)
    out.location = (920, 0)

    texcoord = nodes.new("ShaderNodeTexCoord")
    texcoord.location = (-820, 0)

    # Micro pores
    pore = nodes.new("ShaderNodeTexNoise")
    pore.inputs["Scale"].default_value = 280.0
    pore.inputs["Detail"].default_value = 12.0
    pore.location = (-560, 220)

    pore_bump = nodes.new("ShaderNodeBump")
    pore_bump.inputs["Strength"].default_value = 0.18
    pore_bump.location = (420, 180)

    # Stubble — lower-face mask + dark speckle
    stubble_noise = nodes.new("ShaderNodeTexNoise")
    stubble_noise.inputs["Scale"].default_value = 95.0
    stubble_noise.inputs["Detail"].default_value = 8.0
    stubble_noise.location = (-560, -60)

    stubble_mask = nodes.new("ShaderNodeMapping")
    stubble_mask.inputs["Location"].default_value = (0, 0, -0.55)
    stubble_mask.location = (-740, -180)

    sep = nodes.new("ShaderNodeSeparateXYZ")
    sep.location = (-560, -220)

    stubble_ramp = nodes.new("ShaderNodeValToRGB")
    stubble_ramp.color_ramp.elements[0].position = 0.42
    stubble_ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
    stubble_ramp.color_ramp.elements[1].position = 0.72
    stubble_ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
    stubble_ramp.location = (-360, -220)

    stubble_mix = nodes.new("ShaderNodeMix")
    stubble_mix.data_type = "RGBA"
    stubble_mix.inputs["Factor"].default_value = 0.55
    stubble_mix.inputs["A"].default_value = (0.68, 0.52, 0.42, 1)
    stubble_mix.inputs["B"].default_value = (0.22, 0.16, 0.13, 1)
    stubble_mix.location = (80, 40)

    # Temple veins — subtle blue-green under SSS
    vein = nodes.new("ShaderNodeTexVoronoi")
    vein.feature = "DISTANCE_TO_EDGE"
    vein.inputs["Scale"].default_value = 18.0
    vein.location = (-560, -420)

    vein_ramp = nodes.new("ShaderNodeValToRGB")
    vein_ramp.color_ramp.elements[0].color = (0.68, 0.52, 0.42, 1)
    vein_ramp.color_ramp.elements[1].color = (0.52, 0.38, 0.36, 1)
    vein_ramp.location = (-360, -420)

    vein_mix = nodes.new("ShaderNodeMix")
    vein_mix.data_type = "RGBA"
    vein_mix.inputs["Factor"].default_value = 0.12
    vein_mix.location = (260, -80)

    # Scar zone — warm keloid tint on nose bridge band
    scar_noise = nodes.new("ShaderNodeTexNoise")
    scar_noise.inputs["Scale"].default_value = 42.0
    scar_noise.location = (-560, 420)

    scar_band = nodes.new("ShaderNodeSeparateXYZ")
    scar_band.location = (-740, 520)

    scar_ramp = nodes.new("ShaderNodeValToRGB")
    scar_ramp.color_ramp.elements[0].position = 0.38
    scar_ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
    scar_ramp.color_ramp.elements[1].position = 0.52
    scar_ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
    scar_ramp.location = (-360, 520)

    stubble_factor = nodes.new("ShaderNodeMath")
    stubble_factor.operation = "MULTIPLY"
    stubble_factor.location = (-180, -120)

    scar_factor = nodes.new("ShaderNodeMath")
    scar_factor.operation = "MULTIPLY"
    scar_factor.location = (-180, 420)

    scar_tint = nodes.new("ShaderNodeMix")
    scar_tint.data_type = "RGBA"
    scar_tint.inputs["B"].default_value = (0.38, 0.14, 0.1, 1)
    scar_tint.location = (260, 120)

    links.new(texcoord.outputs["Object"], stubble_mask.inputs["Vector"])
    links.new(stubble_mask.outputs["Vector"], sep.inputs["Vector"])
    links.new(sep.outputs["Z"], stubble_ramp.inputs["Fac"])
    links.new(stubble_noise.outputs["Fac"], stubble_factor.inputs[0])
    links.new(stubble_ramp.outputs["Color"], stubble_factor.inputs[1])
    links.new(stubble_factor.outputs["Value"], stubble_mix.inputs["Factor"])
    links.new(vein.outputs["Distance"], vein_ramp.inputs["Fac"])
    links.new(stubble_mix.outputs["Result"], vein_mix.inputs["A"])
    links.new(vein_ramp.outputs["Color"], vein_mix.inputs["B"])
    links.new(texcoord.outputs["Object"], scar_band.inputs["Vector"])
    links.new(scar_band.outputs["Y"], scar_ramp.inputs["Fac"])
    links.new(scar_noise.outputs["Fac"], scar_factor.inputs[0])
    links.new(scar_ramp.outputs["Color"], scar_factor.inputs[1])
    links.new(scar_factor.outputs["Value"], scar_tint.inputs["Factor"])
    links.new(vein_mix.outputs["Result"], scar_tint.inputs["A"])
    links.new(pore.outputs["Fac"], pore_bump.inputs["Height"])
    links.new(scar_tint.outputs["Result"], bsdf.inputs["Base Color"])
    links.new(pore_bump.outputs["Normal"], bsdf.inputs["Normal"])

    bsdf.inputs["Roughness"].default_value = 0.48
    if "Subsurface Weight" in bsdf.inputs:
        bsdf.inputs["Subsurface Weight"].default_value = 0.22
        if "Subsurface Color" in bsdf.inputs:
            bsdf.inputs["Subsurface Color"].default_value = (0.82, 0.38, 0.28, 1)
        elif "Subsurface Radius" in bsdf.inputs:
            bsdf.inputs["Subsurface Radius"].default_value = (0.8, 0.35, 0.25)
    elif "Subsurface" in bsdf.inputs:
        bsdf.inputs["Subsurface"].default_value = 0.22
        if "Subsurface Color" in bsdf.inputs:
            bsdf.inputs["Subsurface Color"].default_value = (0.82, 0.38, 0.28, 1)

    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


def mat_eye_amber(name: str = "Eye_Amber"):
    """Layered amber iris with depth."""
    m = bpy.data.materials.new(name=name)
    m.use_nodes = True
    nt = m.node_tree
    nodes, links = nt.nodes, nt.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    wave = nodes.new("ShaderNodeTexWave")
    wave.inputs["Scale"].default_value = 14.0
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.42, 0.18, 0.04, 1)
    ramp.color_ramp.elements[1].color = (0.78, 0.48, 0.12, 1)
    links.new(wave.outputs["Color"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.08
    bsdf.inputs["Metallic"].default_value = 0.02
    if "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = (0.55, 0.28, 0.06, 1)
        bsdf.inputs["Emission Strength"].default_value = 0.06
    if "IOR" in bsdf.inputs:
        bsdf.inputs["IOR"].default_value = 1.38
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


def mat_cornea(name: str = "Eye_Cornea"):
    m = bpy.data.materials.new(name=name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (1, 1, 1, 1)
        bsdf.inputs["Roughness"].default_value = 0.02
        if "Transmission Weight" in bsdf.inputs:
            bsdf.inputs["Transmission Weight"].default_value = 1.0
        elif "Transmission" in bsdf.inputs:
            bsdf.inputs["Transmission"].default_value = 0.95
        if "IOR" in bsdf.inputs:
            bsdf.inputs["IOR"].default_value = 1.376
    m.blend_method = "BLEND"
    return m


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge0 == edge1:
        return 0.0
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def build_sculpted_head_mesh() -> bpy.types.Mesh:
    """Single Asian middle-aged male head — high cheekbones, angular jaw, eye sockets."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=72, radius=1.0)

    for v in bm.verts:
        x, y, z = v.co.x, v.co.y, v.co.z
        ax, az = abs(x), abs(z)

        # Base Asian proportions: slightly wider mid-face, narrower chin
        v.co.x *= 0.86 + 0.06 * _smoothstep(0.05, 0.38, az)
        v.co.z *= 1.07

        # Angular jaw — gonial flare + squared chin
        jaw = _smoothstep(-0.15, -0.72, z)
        if jaw > 0:
            if ax > 0.28:
                v.co.x *= 1.0 + jaw * 0.42 * min(1.0, ax / 0.45)
            if ax < 0.22:
                v.co.y += jaw * 0.05
            v.co.z -= jaw * 0.06

        # High cheekbones (middle-aged, pronounced)
        cheek = _smoothstep(0.08, 0.32, az) * (1.0 - _smoothstep(0.32, 0.52, az))
        if cheek > 0 and ax > 0.32 and y > -0.05:
            v.co.x += (1.0 if x > 0 else -1.0) * cheek * 0.055

        # Zygomatic hollow under cheekbone
        hollow = _smoothstep(0.0, 0.22, az) * (1.0 - _smoothstep(0.22, 0.34, az))
        if hollow > 0 and ax > 0.38 and y > 0.05:
            v.co.y -= hollow * 0.018

        # Brow ridge — weathered ronin
        brow = _smoothstep(0.38, 0.52, z) * (1.0 - _smoothstep(0.52, 0.62, z))
        if brow > 0 and ax < 0.62:
            v.co.y += brow * 0.022

        # Almond eye sockets — recessed with lid ridges (eyes sit inside)
        for ex in (-0.36, 0.36):
            dx, dz = x - ex, z - 0.34
            dist = math.sqrt((dx / 1.18) ** 2 + (dz / 0.82) ** 2)
            if dist < 0.145 and y > 0.37:
                t = 1.0 - dist / 0.145
                v.co.y -= t * 0.048
                if dz > 0.015:
                    v.co.y += t * 0.014 * _smoothstep(0.015, 0.09, dz)
                if dz < -0.01:
                    v.co.y += t * 0.009 * _smoothstep(-0.08, -0.01, dz)

        # Crow's feet
        for ex in (-0.36, 0.36):
            dx, dz = x - ex * 1.06, z - (0.36 if z > 0.3 else 0.28)
            dist = math.sqrt(dx * dx + dz * dz * 1.35)
            if dist < 0.11 and y > 0.36:
                v.co.y -= (1.0 - dist / 0.11) * 0.014

        # Integrated lips — bow + philtrum (no sausage attachments)
        mouth_z = -0.02
        if ax < 0.13 and -0.11 < z < 0.07 and y > 0.11:
            lip_t = 1.0 - min(1.0, abs(z - mouth_z) / 0.09)
            lip_t *= 1.0 - min(1.0, ax / 0.13)
            if z >= mouth_z - 0.015:
                v.co.y += lip_t * 0.036
                if ax < 0.045 and z > mouth_z:
                    v.co.z += lip_t * 0.012
            else:
                v.co.y += lip_t * 0.026
            if abs(z - mouth_z) < 0.028 and ax < 0.075:
                v.co.y -= 0.014

        # Philtrum groove
        if ax < 0.035 and 0.0 < z < 0.12 and y > 0.14:
            v.co.y -= _smoothstep(0.0, 0.12, z) * 0.008

        # Integrated nose — bridge, tip, alae
        if ax < 0.14 and -0.1 < z < 0.17 and y > 0.07:
            t = (z + 0.1) / 0.27
            tip = math.sin(max(0.0, min(1.0, t)) * math.pi) * 0.058
            v.co.y += tip
            if 0.045 < ax < 0.14 and -0.06 < z < 0.04:
                v.co.x += (1.0 if x > 0 else -1.0) * 0.018

        if ax < 0.11 and 0.04 < z < 0.48 and y > 0.05:
            t = (z - 0.04) / 0.44
            bridge = math.sin(t * math.pi) * 0.078
            v.co.y += bridge
            scar_line = abs((x * 2.8 + z * 0.55) - 0.04)
            if scar_line < 0.045 and 0.14 < z < 0.42:
                v.co.y += (1.0 - scar_line / 0.045) * 0.016

        # Nasolabial folds (age)
        for sx in (-1, 1):
            nx = x - sx * 0.14
            if 0.0 < z < 0.18 and nx * sx > 0 and y > 0.18:
                fold = _smoothstep(0.0, 0.14, z) * (1.0 - _smoothstep(0.14, 0.22, z))
                v.co.y -= fold * 0.012

        # Temples — slight gauntness
        if az > 0.42 and ax > 0.55 and y < 0.15:
            v.co.x *= 1.0 - 0.04 * _smoothstep(0.42, 0.65, az)

        # Neck taper — narrow jaw into throat before bottom cut (no chin flat face)
        if z < -0.38:
            t = _smoothstep(-0.84, -0.38, z)
            shrink = 1.0 - t * 0.52
            v.co.x *= shrink
            v.co.y *= 0.94 + t * 0.06
            if y > 0.08:
                v.co.y -= t * 0.015

    # Neck base cut — below jaw (z=-0.62 was slicing through chin)
    bmesh.ops.bisect_plane(
        bm,
        geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
        plane_co=(0, 0, -0.84),
        plane_no=(0, 0, 1),
        clear_inner=True,
    )
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0008)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    mesh = bpy.data.meshes.new("HeadMesh_Sculpted")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return mesh


def validate_character_mesh() -> bool:
    """Ensure export is a clean human figure — no env/fx, no duplicate body slots."""
    allowed_prefixes = ("Skin_", "Eye_", "Hair_", "Cloth_", "Metal_")
    forbidden_prefixes = ("Env_", "FX_", "Light_", "Camera_")
    required = (
        "Skin_Head", "Skin_Neck", "Skin_Torso",
        "Eye_Sclera_L", "Eye_Sclera_R",
        "Cloth_ShortTunic", "Metal_DaoBlade", "Cloth_DaoScabbard",
    )
    slot_checks = {
        "head": ("Skin_Head",),
        "neck": ("Skin_Neck",),
        "torso": ("Skin_Torso",),
        "shoulder_L": ("Skin_Shoulder_L",),
        "shoulder_R": ("Skin_Shoulder_R",),
    }

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    names = {o.name for o in meshes}
    issues: list[str] = []

    for o in meshes:
        if any(o.name.startswith(p) for p in forbidden_prefixes):
            issues.append(f"forbidden object: {o.name}")
        if not any(o.name.startswith(p) for p in allowed_prefixes):
            issues.append(f"unexpected mesh: {o.name}")

    for req in required:
        if req not in names:
            issues.append(f"missing required: {req}")

    for slot, objs in slot_checks.items():
        present = [n for n in objs if n in names]
        if len(present) > 1:
            issues.append(f"duplicate slot {slot}: {present}")
        if len(present) == 0:
            issues.append(f"empty slot {slot}")

    legacy_body = [
        n for n in names
        if n.startswith("Skin_")
        and n not in {
            "Skin_Head", "Skin_Neck", "Skin_Torso",
            "Skin_Shoulder_L", "Skin_Shoulder_R",
            "Skin_Brow_L", "Skin_Brow_R",
            "Skin_Nostril_L", "Skin_Nostril_R",
            "Skin_Scar", "Skin_Ear_L", "Skin_Ear_R",
        }
        and not n.startswith("Skin_Stubble")
        and n.startswith(("Skin_Upper", "Skin_Lower", "Skin_Trap", "Skin_Delt",
                          "Skin_Throat", "Skin_Lip", "Skin_Cheek", "Skin_Nose",
                          "Skin_EyeSocket", "Skin_Eyelid"))
    ]
    for n in legacy_body:
        issues.append(f"legacy/duplicate body part: {n}")

    if any(n.startswith("Skin_Stubble") for n in names):
        issues.append("stubble meshes should be removed")

    print("── character validation ──")
    print(f"  mesh count: {len(meshes)}")
    for cat in ("Skin_", "Eye_", "Hair_", "Cloth_", "Metal_"):
        cnt = sum(1 for n in names if n.startswith(cat))
        if cnt:
            print(f"  {cat}* : {cnt}")
    if issues:
        for msg in issues:
            print(f"  ✗ {msg}")
        print("  RESULT: FAIL")
        return False
    print("  ✓ human figure OK — body / cloth / weapon only, no duplicate slots")
    print("  RESULT: PASS")
    return True


def _parent_to_head(head, obj):
    """Attach feature to head local space — moves with skull, no floating."""
    obj.parent = head


def _add_almond_eye(head, sx, created):
    """Recessed almond eye — flat profile, sits inside sculpted socket."""
    eye_white = mat_principled("EyeWhite", (0.95, 0.93, 0.88, 1), roughness=0.18)
    eye_iris = mat_eye_amber()
    cornea_mat = mat_cornea()

    ex = sx * 0.36
    ey, ez = 0.448, 0.338

    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, radius=0.082)
    sclera = bpy.context.active_object
    sclera.name = f"Eye_Sclera_{'L' if sx < 0 else 'R'}"
    sclera.scale = (1.22, 0.20, 0.62)
    sclera.rotation_euler = Euler((0.04, 0, sx * 0.05), "XYZ")
    assign_mat(sclera, eye_white)
    _parent_to_head(head, sclera)
    sclera.location = (ex, ey, ez)
    created.append(sclera)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, radius=0.048)
    iris = bpy.context.active_object
    iris.name = f"Eye_Iris_{'L' if sx < 0 else 'R'}"
    iris.scale = (1.05, 0.14, 0.92)
    assign_mat(iris, eye_iris)
    _parent_to_head(head, iris)
    iris.location = (ex, ey + 0.011, ez + 0.002)
    created.append(iris)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=0.018)
    pupil = bpy.context.active_object
    pupil.name = f"Eye_Pupil_{'L' if sx < 0 else 'R'}"
    assign_mat(pupil, mat_principled("Pupil", (0.008, 0.004, 0.003, 1), roughness=0.03))
    _parent_to_head(head, pupil)
    pupil.location = (ex, ey + 0.013, ez + 0.002)
    created.append(pupil)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=14, radius=0.084)
    cornea = bpy.context.active_object
    cornea.name = f"Eye_Cornea_{'L' if sx < 0 else 'R'}"
    cornea.scale = (1.18, 0.16, 0.60)
    cornea.rotation_euler = Euler((0.04, 0, sx * 0.05), "XYZ")
    assign_mat(cornea, cornea_mat)
    _parent_to_head(head, cornea)
    cornea.location = (ex, ey + 0.006, ez)
    created.append(cornea)


def create_face(parent, skin_mat, hair_mat):
    """Head + neck + hair — lips/nose in sculpt; no stubble or duplicate lip meshes."""
    created = []
    head_z = 1.68
    head_scale = 0.118

    mesh = build_sculpted_head_mesh()
    head = bpy.data.objects.new("Skin_Head", mesh)
    bpy.context.collection.objects.link(head)
    head.location = (0, -0.010, head_z)
    head.scale = (head_scale, head_scale * 0.92, head_scale * 1.06)
    assign_mat(head, skin_mat)
    add_subdiv(head, 1)
    created.append(head)

    # Upper neck only — lower neck/chest is Skin_Torso (no overlap)
    bpy.ops.mesh.primitive_cylinder_add(vertices=28, radius=0.036, depth=0.14, location=(0, 0, 0))
    neck = bpy.context.active_object
    neck.name = "Skin_Neck"
    neck.scale = (1.0, 0.88, 1.0)
    assign_mat(neck, skin_mat)
    _parent_to_head(head, neck)
    neck.location = (0.0, -0.032, -0.72)
    created.append(neck)

    for sx in (-1, 1):
        _add_almond_eye(head, sx, created)

        bpy.ops.mesh.primitive_cube_add(size=0.004, location=(0, 0, 0))
        brow = bpy.context.active_object
        brow.name = f"Skin_Brow_{'L' if sx < 0 else 'R'}"
        brow.scale = (1.6, 0.35, 0.28)
        brow.rotation_euler = Euler((0.06, 0, sx * 0.07), "XYZ")
        assign_mat(brow, hair_mat)
        _parent_to_head(head, brow)
        brow.location = (sx * 0.36, 0.492, 0.388)
        created.append(brow)

        bpy.ops.mesh.primitive_uv_sphere_add(segments=8, ring_count=6, radius=0.022)
        nostril = bpy.context.active_object
        nostril.name = f"Skin_Nostril_{'L' if sx < 0 else 'R'}"
        nostril.scale = (0.55, 0.35, 0.45)
        assign_mat(nostril, mat_principled("Nostril", (0.14, 0.08, 0.06, 1), roughness=0.9))
        _parent_to_head(head, nostril)
        nostril.location = (sx * 0.055, 0.395, -0.012)
        created.append(nostril)

    bpy.ops.mesh.primitive_cube_add(size=0.002, location=(0, 0, 0))
    scar = bpy.context.active_object
    scar.name = "Skin_Scar"
    scar.scale = (0.22, 0.35, 0.55)
    scar.rotation_euler = Euler((0.15, 0.06, -0.42), "XYZ")
    assign_mat(scar, mat_principled("Scar_Keloid", (0.4, 0.12, 0.09, 1), roughness=0.7, subsurface=0.05))
    _parent_to_head(head, scar)
    scar.location = (0.012, 0.418, 0.22)
    created.append(scar)

    for sx in (-1, 1):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=14, radius=0.032)
        ear = bpy.context.active_object
        ear.name = f"Skin_Ear_{'L' if sx < 0 else 'R'}"
        ear.scale = (0.35, 0.55, 0.75)
        assign_mat(ear, skin_mat)
        _parent_to_head(head, ear)
        ear.location = (sx * 0.93, -0.06, 0.10)
        created.append(ear)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=40, ring_count=32, radius=0.88)
    bun = bpy.context.active_object
    bun.name = "Hair_Bun"
    bun.scale = (0.84, 0.92, 0.72)
    assign_mat(bun, hair_mat)
    add_subdiv(bun, 1)
    _parent_to_head(head, bun)
    bun.location = (0.0, -0.20, 0.64)
    created.append(bun)

    for i, (x, y, z, rot) in enumerate((
        (-0.78, 0.58, 0.02, (1.35, 0.35, 0.28)),
        (0.70, 0.62, -0.04, (1.15, -0.28, -0.18)),
        (0.18, 0.68, -0.18, (1.45, 0.08, 0.12)),
    )):
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.11, depth=0.28, location=(0, 0, 0))
        strand = bpy.context.active_object
        strand.name = f"Hair_Strand_{i}"
        strand.rotation_euler = Euler(rot, "XYZ")
        assign_mat(strand, hair_mat)
        _parent_to_head(head, strand)
        strand.location = (x, y, z)
        created.append(strand)

    parent_objects(parent, created)
    return created


def create_body_torso(parent, skin_mat):
    """Single torso + shoulders — replaces old overlapping chest/neck/throat pieces."""
    created = []

    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=20, radius=0.112,
                                         location=(0.0, 0.014, 1.328))
    torso = bpy.context.active_object
    torso.name = "Skin_Torso"
    torso.scale = (1.46, 0.68, 0.94)
    assign_mat(torso, skin_mat)
    add_subdiv(torso, 1)
    created.append(torso)

    for sx, tag in ((-1, "L"), (1, "R")):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=12, radius=0.066,
                                             location=(sx * 0.214, 0.008, 1.358))
        sh = bpy.context.active_object
        sh.name = f"Skin_Shoulder_{tag}"
        sh.scale = (0.66, 0.56, 0.44)
        sh.rotation_euler = Euler((0.08, 0, sx * 0.10), "XYZ")
        assign_mat(sh, skin_mat)
        created.append(sh)

    parent_objects(parent, created)
    return created


def create_clothing(parent, inner_mat, outer_mat, leather_mat, bronze_mat, cloak_mat):
    """Han wanderer light kit — 短褐交领、窄袖、革带，无重甲."""
    created = []
    trim_mat = mat_principled("Han_CrimsonTrim", (0.42, 0.1, 0.08, 1), roughness=0.68)

    # Cross-lapel (交领右衽) — sits over upper chest / throat
    for sx, tag, rot_z in ((1, "R", -0.38), (-1, "L", 0.34)):
        bpy.ops.mesh.primitive_plane_add(size=0.36, location=(sx * 0.03, 0.058, 1.418))
        lapel = bpy.context.active_object
        lapel.name = f"Cloth_Lapel_{tag}"
        lapel.rotation_euler = Euler((0.18, 0.42 * sx, rot_z), "XYZ")
        lapel.scale = (0.5, 0.75, 1.0)
        assign_mat(lapel, inner_mat)
        created.append(lapel)

    # Short hemp tunic body (短褐) — neckline meets lower chest
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0.018, 1.125))
    tunic = bpy.context.active_object
    tunic.name = "Cloth_ShortTunic"
    tunic.scale = (0.36, 0.2, 0.44)
    assign_mat(tunic, outer_mat)
    add_subdiv(tunic, 1)
    created.append(tunic)

    # Short front/back panels (直裾短摆)
    for i, (x, y, z, sc) in enumerate([
        (0.0, 0.03, 0.86, (0.3, 0.1, 0.42)),
        (-0.1, 0.0, 0.84, (0.16, 0.09, 0.38)),
        (0.1, 0.0, 0.84, (0.16, 0.09, 0.38)),
    ]):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z))
        hem = bpy.context.active_object
        hem.name = f"Cloth_Hem_{i}"
        hem.scale = sc
        assign_mat(hem, outer_mat)
        created.append(hem)

    # Slim leather belt + bronze hook only
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0.055, 1.0))
    belt = bpy.context.active_object
    belt.name = "Cloth_Belt"
    belt.scale = (0.34, 0.045, 0.04)
    assign_mat(belt, leather_mat)
    created.append(belt)

    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.1, 0.085, 1.0))
    hook = bpy.context.active_object
    hook.name = "Metal_BeltHook"
    hook.scale = (0.05, 0.02, 0.028)
    hook.rotation_euler = Euler((0.12, 0.3, 0.0), "XYZ")
    assign_mat(hook, bronze_mat)
    created.append(hook)

    # Right wrist guard only (游侠护腕)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.34, 0.05, 0.72))
    bracer = bpy.context.active_object
    bracer.name = "Cloth_Bracer_R"
    bracer.scale = (0.08, 0.07, 0.12)
    bracer.rotation_euler = Euler((0.35, -0.1, 0.45), "XYZ")
    assign_mat(bracer, leather_mat)
    created.append(bracer)

    # Small wind cloak — single back panel
    bpy.ops.mesh.primitive_plane_add(size=0.75, location=(-0.06, -0.14, 1.08))
    cloak = bpy.context.active_object
    cloak.name = "Cloth_Cloak_0"
    cloak.rotation_euler = Euler((1.32, 0.12, 0.08), "XYZ")
    cloak.scale = (0.38, 0.55, 0.72)
    assign_mat(cloak, cloak_mat)
    created.append(cloak)

    # Collar trim
    bpy.ops.mesh.primitive_torus_add(major_radius=0.16, minor_radius=0.006, location=(0, 0.04, 1.42))
    collar = bpy.context.active_object
    collar.name = "Cloth_TrimCollar"
    collar.rotation_euler = Euler((1.57, 0, 0), "XYZ")
    collar.scale = (1.0, 1.0, 0.5)
    assign_mat(collar, trim_mat)
    created.append(collar)

    parent_objects(parent, created)
    return created


def create_limbs_and_feet(parent, outer_mat, inner_mat, boot_mat):
    """窄袖 + 缚裤 + 轻履."""
    created = []
    leather_mat = mat_han_leather_lamellar()

    for sx, tag in [(-1, "L"), (1, "R")]:
        # Narrow sleeves (窄袖) — tapered, practical for sword hand
        bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.046, depth=0.46,
                                            location=(sx * 0.265, 0.028, 1.075))
        upper = bpy.context.active_object
        upper.name = f"Cloth_SleeveUpper_{tag}"
        upper.rotation_euler = Euler((0.12, 0, sx * 0.26), "XYZ")
        assign_mat(upper, outer_mat)
        created.append(upper)

        bpy.ops.mesh.primitive_cylinder_add(vertices=18, radius=0.042, depth=0.32,
                                            location=(sx * 0.38, 0.04, 0.78))
        fore = bpy.context.active_object
        fore.name = f"Cloth_SleeveFore_{tag}"
        fore.rotation_euler = Euler((0.2, 0.04, sx * 0.32), "XYZ")
        assign_mat(fore, outer_mat)
        created.append(fore)

        if tag == "R":
            upper.rotation_euler = Euler((0.36, -0.1, 0.44), "XYZ")
            fore.rotation_euler = Euler((0.4, -0.06, 0.52), "XYZ")

        # Bound trousers (缚裤)
        bpy.ops.mesh.primitive_cylinder_add(vertices=14, radius=0.058, depth=0.36,
                                            location=(sx * 0.1, 0.02, 0.72))
        thigh = bpy.context.active_object
        thigh.name = f"Cloth_TrouserThigh_{tag}"
        assign_mat(thigh, inner_mat)
        created.append(thigh)

        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.045, depth=0.38,
                                            location=(sx * 0.1, 0.025, 0.34))
        shin = bpy.context.active_object
        shin.name = f"Cloth_TrouserShin_{tag}"
        assign_mat(shin, inner_mat)
        created.append(shin)

        # Leg wrap straps
        for z in (0.52, 0.38):
            bpy.ops.mesh.primitive_torus_add(major_radius=0.05, minor_radius=0.005,
                                             location=(sx * 0.1, 0.05, z))
            wrap = bpy.context.active_object
            wrap.name = f"Cloth_LegWrap_{tag}_{z:.2f}"
            wrap.rotation_euler = Euler((1.45, 0, sx * 0.1), "XYZ")
            assign_mat(wrap, leather_mat)
            created.append(wrap)

        # Cloth shoes (布履)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(sx * 0.1, 0.07, 0.06))
        shoe = bpy.context.active_object
        shoe.name = f"Cloth_Shoe_{tag}"
        shoe.scale = (0.085, 0.17, 0.05)
        assign_mat(shoe, boot_mat)
        created.append(shoe)

    parent_objects(parent, created)
    return created


def create_huan_shou_dao(parent, handle_mat, blade_mat, bronze_mat):
    """汉代环首刀 — held in right hand; ring pommel, straight-ish single-edge blade."""
    root = bpy.data.objects.new("Dao_Root", None)
    bpy.context.collection.objects.link(root)
    root.location = (0.36, 0.2, 0.95)
    root.rotation_euler = Euler((0.2, -0.48, 0.58), "XYZ")
    root.parent = parent

    # Blade — single edge, slight taper (环首刀刃)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.48))
    blade = bpy.context.active_object
    blade.name = "Metal_DaoBlade"
    blade.scale = (0.009, 0.042, 0.62)
    assign_mat(blade, blade_mat)
    blade.parent = root

    # Simple guard plate (刀格)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.1))
    guard = bpy.context.active_object
    guard.name = "Metal_DaoGuard"
    guard.scale = (0.045, 0.008, 0.022)
    assign_mat(guard, bronze_mat)
    guard.parent = root

    # Handle (木柄缠绦)
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.022, depth=0.18, location=(0, 0, -0.02))
    handle = bpy.context.active_object
    handle.name = "Cloth_DaoHandle"
    assign_mat(handle, handle_mat)
    handle.parent = root

    for i in range(6):
        bpy.ops.mesh.primitive_torus_add(major_radius=0.023, minor_radius=0.003,
                                         location=(0, 0, -0.1 + i * 0.028))
        wrap = bpy.context.active_object
        wrap.name = f"Cloth_DaoWrap_{i}"
        wrap.rotation_euler = Euler((1.57, 0, 0), "XYZ")
        assign_mat(wrap, mat_principled("HandleWrap", (0.28, 0.14, 0.08, 1), roughness=0.75))
        wrap.parent = root

    # Ring pommel (环首) — signature Han feature
    bpy.ops.mesh.primitive_torus_add(major_radius=0.038, minor_radius=0.007, location=(0, 0, -0.12))
    ring = bpy.context.active_object
    ring.name = "Metal_DaoRing"
    ring.rotation_euler = Euler((1.57, 0, 0), "XYZ")
    assign_mat(ring, bronze_mat)
    ring.parent = root

    return root


def create_dao_scabbard(parent, scabbard_mat, leather_mat):
    """Left hip scabbard (鞘) — lacquered wood/leather."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=(-0.16, -0.05, 0.82))
    saya = bpy.context.active_object
    saya.name = "Cloth_DaoScabbard"
    saya.scale = (0.022, 0.048, 0.42)
    saya.rotation_euler = Euler((0.08, 0.32, 0.15), "XYZ")
    assign_mat(saya, scabbard_mat)
    saya.parent = parent

    bpy.ops.mesh.primitive_cube_add(size=1, location=(-0.16, -0.02, 1.02))
    mouth = bpy.context.active_object
    mouth.name = "Metal_ScyabbardMouth"
    mouth.scale = (0.028, 0.055, 0.035)
    mouth.rotation_euler = Euler((0.08, 0.32, 0.15), "XYZ")
    assign_mat(mouth, leather_mat)
    mouth.parent = parent

    bpy.ops.mesh.primitive_torus_add(major_radius=0.018, minor_radius=0.004,
                                     location=(-0.16, -0.04, 0.62))
    chape = bpy.context.active_object
    chape.name = "Metal_ScabbardChape"
    chape.rotation_euler = Euler((1.5, 0.32, 0.15), "XYZ")
    assign_mat(chape, mat_han_bronze())
    chape.parent = parent


def setup_studio_world():
    """Neutral backdrop for character preview — no cemetery / particles."""
    scene = bpy.context.scene
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.018, 0.022, 0.03, 1)
        bg.inputs["Strength"].default_value = 0.15


def hide_body_for_portrait():
    """Face pass — hide clothing/weapons/env so portrait frames the head."""
    keep_prefix = ("Skin_", "Eye_", "Hair_", "Camera_", "Light_")
    for obj in bpy.data.objects:
        if obj.name.startswith(keep_prefix):
            obj.hide_render = False
            continue
        if obj.type == "MESH":
            obj.hide_render = True


def render_face_closeup():
    """Face preview — Workbench material pass (no EEVEe blowout)."""
    hide_body_for_portrait()
    scene = bpy.context.scene
    prev_engine = scene.render.engine
    prev_filepath = scene.render.filepath
    prev_exposure = scene.view_settings.exposure

    disabled_lights = []
    for obj in bpy.data.objects:
        if obj.type == "LIGHT":
            obj.hide_render = True
            disabled_lights.append(obj)

    scene.render.engine = "BLENDER_WORKBENCH"
    shading = scene.display.shading
    prev_light = shading.light
    prev_color = shading.color_type
    shading.light = "STUDIO"
    shading.color_type = "MATERIAL"

    setup_camera_face()
    cam = scene.camera
    if cam and cam.data:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = 0.20

    scene.view_settings.exposure = 0.0
    scene.render.filepath = str(FACE_PREVIEW_OUT)
    bpy.ops.render.render(write_still=True)
    print(f"preview face → {FACE_PREVIEW_OUT}")

    scene.render.engine = prev_engine
    scene.render.filepath = prev_filepath
    scene.view_settings.exposure = prev_exposure
    shading.light = prev_light
    shading.color_type = prev_color
    if cam and cam.data:
        cam.data.type = "PERSP"
    for obj in disabled_lights:
        obj.hide_render = False


def setup_cinematic_lighting():
    scene = bpy.context.scene
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.015, 0.03, 0.06, 1)
        bg.inputs["Strength"].default_value = 0.12

    # Teal-orange: warm key, cool fill/rim
    bpy.ops.object.light_add(type="AREA", location=(3.5, -2.5, 2.8))
    key = bpy.context.active_object
    key.name = "Light_Key_Orange"
    key.data.energy = 320
    key.data.color = (1.0, 0.68, 0.38)
    key.data.size = 2.8
    key.rotation_euler = Euler((1.05, 0.15, 0.75), "XYZ")

    bpy.ops.object.light_add(type="SPOT", location=(-3, 2.5, 2.4))
    rim = bpy.context.active_object
    rim.name = "Light_Rim_Teal"
    rim.data.energy = 1400
    rim.data.color = (0.35, 0.82, 0.92)
    rim.data.spot_size = math.radians(32)
    rim.rotation_euler = Euler((1.4, 0, -2.15), "XYZ")

    bpy.ops.object.light_add(type="AREA", location=(-2, -3.5, 1.6))
    fill = bpy.context.active_object
    fill.name = "Light_Fill_Cool"
    fill.data.energy = 65
    fill.data.color = (0.5, 0.62, 0.82)
    fill.data.size = 5

    bpy.ops.object.light_add(type="POINT", location=(2.4, -1.8, 1.15))
    lantern = bpy.context.active_object
    lantern.name = "Light_Lantern_Steam"
    lantern.data.energy = 55
    lantern.data.color = (1.0, 0.82, 0.5)

    # Face key — warm portrait fill on eyes/nose
    bpy.ops.object.light_add(type="AREA", location=(0.35, -0.55, 1.74))
    face_key = bpy.context.active_object
    face_key.name = "Light_FaceKey"
    face_key.data.energy = 180
    face_key.data.color = (1.0, 0.82, 0.62)
    face_key.data.size = 0.35
    face_key.rotation_euler = Euler((1.35, 0.1, 0.45), "XYZ")


def setup_camera_face():
    """Face close-up — camera in front of face (+Y), looking back at features."""
    target = Vector((0.0, 0.16, 1.698))
    cam_loc = Vector((0.0, 0.52, 1.702))

    bpy.ops.object.camera_add(location=cam_loc)
    cam = bpy.context.active_object
    cam.name = "Camera_FaceCloseup"
    cam.rotation_euler = (target - cam_loc).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 110
    cam.data.sensor_width = 36
    cam.data.dof.use_dof = True
    cam.data.dof.focus_distance = (target - cam_loc).length
    cam.data.dof.aperture_fstop = 5.6
    bpy.context.scene.camera = cam
    return cam


def setup_camera_body():
    """3/4 hero shot — show Han clothing + face."""
    target = Vector((0.0, 0.04, 1.18))
    cam_loc = Vector((2.15, -2.55, 1.42))

    bpy.ops.object.camera_add(location=cam_loc)
    cam = bpy.context.active_object
    cam.name = "Camera_HeroBody"
    cam.rotation_euler = (target - cam_loc).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 65
    cam.data.sensor_width = 36
    cam.data.dof.use_dof = True
    cam.data.dof.focus_distance = (target - cam_loc).length
    cam.data.dof.aperture_fstop = 3.2
    bpy.context.scene.camera = cam


def setup_render():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.filepath = str(PREVIEW_OUT)
    scene.frame_set(45)
    eevee = getattr(scene, "eevee", None)
    if eevee:
        for attr, val in (
            ("use_bloom", True), ("bloom_intensity", 0.12),
            ("use_volumetric_lights", True),
        ):
            if hasattr(eevee, attr):
                setattr(eevee, attr, val)


def export_glb(filepath: Path):
    """Export character meshes only — body, clothing, weapon."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    skip_prefix = ("Light_", "Camera_")
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        if any(o.name.startswith(p) for p in skip_prefix):
            continue
        o.select_set(True)
    bpy.ops.export_scene.gltf(
        filepath=str(filepath),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_materials="EXPORT",
        export_yup=True,
    )


def main():
    clear_scene()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    skin_mat = mat_skin_cinematic()
    hair_mat = mat_principled("Hair", (0.03, 0.025, 0.04, 1), roughness=0.62)
    inner_mat = mat_han_hemp_inner()
    outer_mat = mat_han_shenyi_outer()
    handle_mat = mat_principled("Dao_HandleWood", (0.28, 0.16, 0.1, 1), roughness=0.62)
    blade_mat = mat_principled("Dao_BladeSteel", (0.82, 0.85, 0.88, 1), roughness=0.08, metallic=0.96)
    scabbard_mat = mat_principled("Dao_Scabbard", (0.06, 0.08, 0.1, 1), roughness=0.55)
    leather_mat = mat_han_leather_lamellar()
    bronze_mat = mat_han_bronze()
    cloak_mat = mat_han_cloak()
    boot_mat = mat_han_boot()

    root = bpy.data.objects.new("Ronin_Root", None)
    bpy.context.collection.objects.link(root)

    body_root = bpy.data.objects.new("Body_Root", None)
    cloth_root = bpy.data.objects.new("Cloth_Root", None)
    weapon_root = bpy.data.objects.new("Weapon_Root", None)
    for node in (body_root, cloth_root, weapon_root):
        bpy.context.collection.objects.link(node)
        node.parent = root

    create_face(body_root, skin_mat, hair_mat)
    create_body_torso(body_root, skin_mat)
    create_clothing(cloth_root, inner_mat, outer_mat, leather_mat, bronze_mat, cloak_mat)
    create_limbs_and_feet(cloth_root, outer_mat, inner_mat, boot_mat)
    create_huan_shou_dao(weapon_root, handle_mat, blade_mat, bronze_mat)
    create_dao_scabbard(weapon_root, scabbard_mat, leather_mat)

    if not validate_character_mesh():
        print("WARNING: character validation failed — check console")

    setup_studio_world()
    setup_cinematic_lighting()
    setup_camera_body()
    setup_render()

    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUT))

    try:
        bpy.ops.render.render(write_still=True)
        print(f"preview body → {PREVIEW_OUT}")

        render_face_closeup()
        bpy.context.scene.render.filepath = str(PREVIEW_OUT)
    except Exception as exc:
        print(f"preview skipped: {exc}")

    export_glb(CHAR_ONLY_GLB)
    export_glb(GLB_OUT)
    print(f"blend      → {BLEND_OUT}")
    print(f"scene glb  → {GLB_OUT}")
    print(f"char glb   → {CHAR_ONLY_GLB}")


if __name__ == "__main__":
    main()
