"""
Debug script to analyze LOD-related data structures in HD2SDK units.
Run this from Blender's Python console after loading the HD2SDK addon.

Usage:
1. In Blender, load an archive containing the units you want to compare
2. Open Blender's Python console (Scripting workspace)
3. Run: exec(open(r"G:\Modding\_Github\HD2SDK-CommunityEdition\debug_lod_data.py").read())
4. Call: analyze_unit(file_id) to analyze a specific unit
5. Call: compare_units(file_id_1, file_id_2) to compare two units
"""

import struct

def hex_dump(data, bytes_per_line=16):
    """Pretty hex dump with ASCII representation"""
    if not data:
        return "  (empty)"
    lines = []
    for i in range(0, len(data), bytes_per_line):
        chunk = data[i:i+bytes_per_line]
        hex_part = ' '.join(f'{b:02x}' for b in chunk)
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        lines.append(f"  {i:04x}: {hex_part:<{bytes_per_line*3}} {ascii_part}")
    return '\n'.join(lines)

def interpret_as_floats(data):
    """Interpret byte data as float32 values"""
    if not data or len(data) < 4:
        return []
    floats = []
    for i in range(0, len(data) - 3, 4):
        try:
            val = struct.unpack('<f', data[i:i+4])[0]
            floats.append(val)
        except:
            floats.append(None)
    return floats

def find_screen_percentages(floats):
    """Find values that look like screen height percentages (0.0-1.0 or 0-100)"""
    results = []
    for i, f in enumerate(floats):
        if f is None:
            continue
        # Check for 0.0-1.0 range (normalized percentage)
        if 0.0 <= f <= 1.0:
            results.append((i, f, "0-1 range (normalized %)"))
        # Check for 0-100 range
        elif 0.0 <= f <= 100.0:
            results.append((i, f, "0-100 range (percentage)"))
        # Check for very small positive values (could be "always visible" threshold)
        elif 0.0 < f < 0.001:
            results.append((i, f, "very small (always visible?)"))
        # Check for very large values (could be "infinite distance" or "never cull")
        elif f > 10000:
            results.append((i, f, "very large (never cull?)"))
    return results

def interpret_as_uint32(data):
    """Interpret byte data as uint32 values"""
    if not data or len(data) < 4:
        return []
    values = []
    for i in range(0, len(data) - 3, 4):
        try:
            val = struct.unpack('<I', data[i:i+4])[0]
            values.append(val)
        except:
            values.append(None)
    return values

def analyze_unit(file_id):
    """
    Analyze a unit's LOD-related data structures.
    file_id: The FileID as integer or hex string (e.g., 0x2d84940ffc725c42)
    """
    try:
        from . import Global_TocManager
        from .utils.constants import UnitID
    except:
        # Running as standalone script in Blender
        import sys
        addon_path = r"G:\Modding\_Github\HD2SDK-CommunityEdition"
        if addon_path not in sys.path:
            sys.path.insert(0, addon_path)

        # Try to get from addon
        import bpy
        addon = bpy.context.preferences.addons.get('HD2SDK-CommunityEdition')
        if addon:
            from HD2SDK_CommunityEdition import Global_TocManager
            from HD2SDK_CommunityEdition.utils.constants import UnitID
        else:
            print("ERROR: HD2SDK addon not found. Load the addon first.")
            return None

    # Convert file_id if it's a string
    if isinstance(file_id, str):
        file_id = int(file_id, 16) if file_id.startswith('0x') else int(file_id)

    # Get the entry
    entry = Global_TocManager.GetEntry(file_id, UnitID)
    if not entry:
        print(f"ERROR: Unit {hex(file_id)} not found in loaded archives")
        return None

    # Load the unit data
    entry.Load(Reload=True, MakeBlendObject=False)
    mesh_file = entry.LoadedData

    print(f"\n{'='*80}")
    print(f"UNIT ANALYSIS: {hex(file_id)}")
    print(f"{'='*80}")

    # Header offsets
    print(f"\n--- HEADER OFFSETS ---")
    print(f"  LightListOffset:              {mesh_file.LightListOffset}")
    print(f"  UnreversedLODGroupListOffset: {mesh_file.UnreversedLODGroupListDataOffset}")
    print(f"  TransformInfoOffset:          {mesh_file.TransformInfoOffset}")
    print(f"  CustomizationInfoOffset:      {mesh_file.CustomizationInfoOffset}")
    print(f"  UnkHeaderOffset1:             {mesh_file.UnkHeaderOffset1}")
    print(f"  ConnectingBoneHashOffset:     {mesh_file.ConnectingBoneHashOffset}")
    print(f"  BoneInfoOffset:               {mesh_file.BoneInfoOffset}")
    print(f"  StreamInfoOffset:             {mesh_file.StreamInfoOffset}")
    print(f"  MeshInfoOffset:               {mesh_file.MeshInfoOffset}")

    # LOD Group List Data (the most likely candidate for render distance)
    print(f"\n--- UNREVERSED LOD GROUP LIST DATA ({len(mesh_file.UnreversedLODGroupListData)} bytes) ---")
    print(hex_dump(mesh_file.UnreversedLODGroupListData))

    # Interpret as floats (potential distance values)
    floats = interpret_as_floats(mesh_file.UnreversedLODGroupListData)
    if floats:
        print(f"\n  As float32 values:")
        for i, f in enumerate(floats):
            if f is not None and -1e10 < f < 1e10:  # Filter out garbage
                print(f"    [{i:2d}] offset {i*4:3d}: {f:12.4f}")

        # Look for potential screen percentages
        percentages = find_screen_percentages(floats)
        if percentages:
            print(f"\n  POTENTIAL SCREEN PERCENTAGE VALUES (Stingray uses screen % for LOD):")
            for idx, val, desc in percentages:
                print(f"    [{idx:2d}] offset {idx*4:3d}: {val:12.6f}  -- {desc}")

    # MeshInfo unknown fields
    print(f"\n--- MESH INFO ARRAY ({len(mesh_file.MeshInfoArray)} meshes) ---")
    for i, mesh_info in enumerate(mesh_file.MeshInfoArray):
        print(f"\n  Mesh {i}: LodIndex={mesh_info.LodIndex}, TransformIndex={mesh_info.TransformIndex}, MeshID={mesh_info.MeshID}")

        print(f"    unk1 (8 bytes, uint64): {mesh_info.unk1} ({hex(mesh_info.unk1)})")

        print(f"    unk2 (32 bytes):")
        print(hex_dump(mesh_info.unk2))
        unk2_floats = interpret_as_floats(mesh_info.unk2)
        if unk2_floats:
            print(f"      As floats: {[f'{f:.4f}' if -1e10 < f < 1e10 else 'inf' for f in unk2_floats]}")

        print(f"    unk3: {mesh_info.unk3}")
        print(f"    unk4: {mesh_info.unk4}")

        print(f"    unk6 (40 bytes):")
        print(hex_dump(mesh_info.unk6))
        unk6_floats = interpret_as_floats(mesh_info.unk6)
        if unk6_floats:
            print(f"      As floats: {[f'{f:.4f}' if -1e10 < f < 1e10 else 'inf' for f in unk6_floats]}")

        print(f"    unk8: {mesh_info.unk8}")

    # Other unknown data
    if mesh_file.UnkHeaderData1:
        print(f"\n--- UNK HEADER DATA 1 ({len(mesh_file.UnkHeaderData1)} bytes) ---")
        print(hex_dump(mesh_file.UnkHeaderData1))

    return mesh_file


def compare_units(file_id_1, file_id_2, name1="Unit 1", name2="Unit 2"):
    """
    Compare two units' LOD-related data structures side by side.
    """
    print(f"\n{'#'*80}")
    print(f"# COMPARING: {name1} vs {name2}")
    print(f"{'#'*80}")

    mesh1 = analyze_unit(file_id_1)
    mesh2 = analyze_unit(file_id_2)

    if not mesh1 or not mesh2:
        return

    print(f"\n{'='*80}")
    print(f"COMPARISON SUMMARY")
    print(f"{'='*80}")

    # Compare LOD Group List sizes
    size1 = len(mesh1.UnreversedLODGroupListData)
    size2 = len(mesh2.UnreversedLODGroupListData)
    print(f"\nLOD Group List Data size: {name1}={size1} bytes, {name2}={size2} bytes")

    # Compare floats in LOD data
    floats1 = interpret_as_floats(mesh1.UnreversedLODGroupListData)
    floats2 = interpret_as_floats(mesh2.UnreversedLODGroupListData)

    if floats1 and floats2:
        print(f"\nLOD Group floats comparison:")
        max_len = max(len(floats1), len(floats2))
        for i in range(max_len):
            f1 = floats1[i] if i < len(floats1) else None
            f2 = floats2[i] if i < len(floats2) else None
            f1_str = f"{f1:12.4f}" if f1 is not None and -1e10 < f1 < 1e10 else "N/A"
            f2_str = f"{f2:12.4f}" if f2 is not None and -1e10 < f2 < 1e10 else "N/A"
            diff = ""
            if f1 is not None and f2 is not None and f1 != f2:
                diff = " <-- DIFFERENT"
            print(f"  [{i:2d}] {name1}: {f1_str}  {name2}: {f2_str}{diff}")

    # Compare MeshInfo unk2 fields
    if mesh1.MeshInfoArray and mesh2.MeshInfoArray:
        print(f"\nMeshInfo unk2 comparison (first mesh of each):")
        unk2_floats1 = interpret_as_floats(mesh1.MeshInfoArray[0].unk2)
        unk2_floats2 = interpret_as_floats(mesh2.MeshInfoArray[0].unk2)

        for i in range(8):  # 32 bytes = 8 floats
            f1 = unk2_floats1[i] if i < len(unk2_floats1) else None
            f2 = unk2_floats2[i] if i < len(unk2_floats2) else None
            f1_str = f"{f1:12.4f}" if f1 is not None and -1e10 < f1 < 1e10 else "N/A"
            f2_str = f"{f2:12.4f}" if f2 is not None and -1e10 < f2 < 1e10 else "N/A"
            diff = ""
            if f1 is not None and f2 is not None and f1 != f2:
                diff = " <-- DIFFERENT"
            print(f"  [{i:2d}] {name1}: {f1_str}  {name2}: {f2_str}{diff}")


# Quick helper functions
def analyze_beacon():
    """Analyze the landing zone beacon (stratagem beam)"""
    return analyze_unit(12449657272871172571)

def analyze_armor(armor_hex="1d6dc4216e7ce52d"):
    """Analyze an armor (default: A-9 Helljumper)"""
    return analyze_unit(int(armor_hex, 16))

def compare_beacon_vs_armor():
    """Compare the beacon against A-9 Helljumper armor"""
    compare_units(
        12449657272871172571,
        int("1d6dc4216e7ce52d", 16),
        "Beacon",
        "Armor"
    )


def list_loaded_units():
    """List all units currently loaded in TocManager"""
    try:
        import bpy
        from HD2SDK_CommunityEdition import Global_TocManager
        from HD2SDK_CommunityEdition.utils.constants import UnitID
    except:
        print("ERROR: HD2SDK addon not loaded")
        return

    print("\n--- LOADED UNITS ---")
    count = 0
    if UnitID in Global_TocManager.TocDict:
        for file_id, entry in Global_TocManager.TocDict[UnitID].items():
            archive_name = entry.SourceArchive.name if hasattr(entry, 'SourceArchive') and entry.SourceArchive else "Unknown"
            print(f"  {hex(file_id):>20}  Archive: {archive_name}")
            count += 1
    print(f"\nTotal: {count} units loaded")


def search_for_item(search_term):
    """Search archivehashes.json for items matching the search term"""
    import json
    hash_path = r"G:\Modding\_Github\HD2SDK-CommunityEdition\hashlists\archivehashes.json"
    try:
        with open(hash_path, 'r') as f:
            data = json.load(f)

        print(f"\n--- SEARCH RESULTS FOR '{search_term}' ---")
        count = 0
        for category, items in data.items():
            for hex_id, name in items.items():
                if search_term.lower() in name.lower() or search_term.lower() in category.lower():
                    print(f"  {hex_id}  [{category}] {name}")
                    count += 1
        print(f"\nTotal: {count} matches")
    except Exception as e:
        print(f"ERROR: {e}")


if __name__ == "__main__":
    print("\nLOD Data Debug Script loaded!")
    print("Available functions:")
    print("  analyze_unit(file_id)         - Analyze a unit's LOD data")
    print("  analyze_beacon()              - Analyze the stratagem beacon")
    print("  analyze_armor('hex_id')       - Analyze an armor")
    print("  compare_beacon_vs_armor()     - Compare beacon vs armor")
    print("  compare_units(id1, id2)       - Compare any two units")
    print("  list_loaded_units()           - List units in TocManager")
    print("  search_for_item('name')       - Search archivehashes.json")
