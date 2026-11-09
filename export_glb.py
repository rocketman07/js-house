#! python3
"""Export the 3D Model and Site Model layers of J+S-House.3dm to a GLB for the web viewer.

One glTF node per Rhino layer (node name = full layer path), one primitive per colour on that layer.
Block instances are expanded. Curves, text and dimensions are skipped. Rhino Z-up feet -> glTF Y-up
(x, z, -y), units stay in feet. Layer visibility in Rhino is stored in node extras.visible.
Set OUT_GLB before exec, or run as-is to write js-house.glb next to this script.
"""
import json, struct, math, System, Rhino
import Rhino.Geometry as G
from collections import OrderedDict, defaultdict

doc = Rhino.RhinoDoc.ActiveDoc
import os
if "OUT_GLB" not in globals():
    OUT_GLB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "js-house.glb")
ROOTS = ("3D Model", "Site Model")
SKIP = ("Contour", "Labels", "Property Line", "Front Yard Line", "Right-of-Way", "North Arrow", "Section Cut")
mp = Rhino.Geometry.MeshingParameters.FastRenderMesh
mp_round = Rhino.Geometry.MeshingParameters()
mp_round.GridMinCount = 8
mp_round.GridMaxCount = 24
mp_round.SimplePlanes = True
mp_round.RefineGrid = False
mp_round.JaggedSeams = False
mp_round.MaximumEdgeLength = 0
mp_round.GridAngle = math.radians(30)


def layer_ok(path):
    return any(path == r or path.startswith(r + "::") for r in ROOTS) and not any(s in path for s in SKIP)


def meshes_of(geo, rough=False):
    out = []
    if isinstance(geo, G.Mesh):
        out.append(geo.DuplicateMesh())
    elif isinstance(geo, G.Extrusion):
        b = geo.ToBrep()
        out += list(G.Mesh.CreateFromBrep(b, mp_round if rough else mp) or [])
    elif isinstance(geo, G.Brep):
        out += list(G.Mesh.CreateFromBrep(geo, mp_round if rough else mp) or [])
    return out


def colour_of(o, L):
    a = o.Attributes
    if a.ColorSource == Rhino.DocObjects.ObjectColorSource.ColorFromObject:
        c = a.ObjectColor
    else:
        c = L.Color
    return (c.R, c.G, c.B)


# layer -> colour -> list of meshes
data = OrderedDict()
vis = {}
for L in doc.Layers:
    if L.IsDeleted or not layer_ok(L.FullPath):
        continue
    objs = list(doc.Objects.FindByLayer(L))
    if not objs:
        continue
    vis[L.FullPath] = bool(L.IsVisible)
    rough = "Trees" in L.FullPath or "Pool" in L.FullPath or "Anchor" in L.FullPath or "Piers" in L.FullPath
    for o in objs:
        col = colour_of(o, L)
        if isinstance(o, Rhino.DocObjects.InstanceObject):
            xf = o.InstanceXform
            for so in o.InstanceDefinition.GetObjects():
                scol = colour_of(so, L) if so.Attributes.ColorSource == Rhino.DocObjects.ObjectColorSource.ColorFromObject else col
                for m in meshes_of(so.Geometry, rough):
                    m.Transform(xf)
                    data.setdefault(L.FullPath, defaultdict(list))[scol].append(m)
        else:
            ms = meshes_of(o.Geometry, rough)
            if ms:
                data.setdefault(L.FullPath, defaultdict(list))[col] += ms

# ---------------------------------------------------------------- build buffers
bin_parts = []
offset = 0
views, accessors, meshes, nodes, materials = [], [], [], [], []
mat_index = {}


def add_view(b, target):
    global offset
    pad = (-offset) % 4
    if pad:
        bin_parts.append(b"\x00" * pad)
        offset += pad
    views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(b), "target": target})
    bin_parts.append(b)
    offset += len(b)
    return len(views) - 1


def material(layer, col):
    glass = "Glass" in layer
    key = (col, glass)
    if key in mat_index:
        return mat_index[key]
    m = {"pbrMetallicRoughness": {"baseColorFactor": [col[0] / 255.0, col[1] / 255.0, col[2] / 255.0, 0.35 if glass else 1.0],
                                  "metallicFactor": 0.3 if ("Metal" in layer or "Siding" in layer) else 0.0,
                                  "roughnessFactor": 0.15 if glass else 0.85},
         "doubleSided": True, "name": "%s_%d_%d_%d" % ("glass" if glass else "mat", col[0], col[1], col[2])}
    if glass:
        m["alphaMode"] = "BLEND"
    materials.append(m)
    mat_index[key] = len(materials) - 1
    return mat_index[key]


tri_total = 0
for path, bycol in data.items():
    prims = []
    for col, ms in bycol.items():
        pos, nor, idx = [], [], []
        base = 0
        for m in ms:
            m.Faces.ConvertQuadsToTriangles()
            m.Normals.ComputeNormals()
            m.Compact()
            vs = m.Vertices
            ns = m.Normals
            for i in range(vs.Count):
                p = vs[i]
                n = ns[i]
                pos += [p.X, p.Z, -p.Y]
                nor += [n.X, n.Z, -n.Y]
            for f in m.Faces:
                idx += [base + f.A, base + f.B, base + f.C]
            base += vs.Count
        if not idx:
            continue
        nv = len(pos) // 3
        tri_total += len(idx) // 3
        xs, ys, zs = pos[0::3], pos[1::3], pos[2::3]
        pv = add_view(struct.pack("<%df" % len(pos), *pos), 34962)
        nvw = add_view(struct.pack("<%df" % len(nor), *nor), 34962)
        iv = add_view(struct.pack("<%dI" % len(idx), *idx), 34963)
        accessors.append({"bufferView": pv, "componentType": 5126, "count": nv, "type": "VEC3",
                          "min": [min(xs), min(ys), min(zs)], "max": [max(xs), max(ys), max(zs)]})
        accessors.append({"bufferView": nvw, "componentType": 5126, "count": nv, "type": "VEC3"})
        accessors.append({"bufferView": iv, "componentType": 5125, "count": len(idx), "type": "SCALAR"})
        a0 = len(accessors) - 3
        prims.append({"attributes": {"POSITION": a0, "NORMAL": a0 + 1}, "indices": a0 + 2, "material": material(path, col)})
    if prims:
        meshes.append({"name": path, "primitives": prims})
        nodes.append({"name": path, "mesh": len(meshes) - 1, "extras": {"layer": path, "visible": vis[path]}})

gltf = {"asset": {"version": "2.0", "generator": "J+S House export_glb.py"},
        "scene": 0, "scenes": [{"nodes": list(range(len(nodes)))}],
        "nodes": nodes, "meshes": meshes, "materials": materials,
        "accessors": accessors, "bufferViews": views, "buffers": [{"byteLength": offset}],
        "extras": {"units": "feet", "upAxis": "Y (Rhino Z)"}}
js = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
js += b" " * ((-len(js)) % 4)
binb = b"".join(bin_parts)
binb += b"\x00" * ((-len(binb)) % 4)
total = 12 + 8 + len(js) + 8 + len(binb)
with open(OUT_GLB, "wb") as f:
    f.write(struct.pack("<III", 0x46546C67, 2, total))
    f.write(struct.pack("<II", len(js), 0x4E4F534A))
    f.write(js)
    f.write(struct.pack("<II", len(binb), 0x004E4942))
    f.write(binb)
print("layers %d, triangles %d, size %.1f MB" % (len(nodes), tri_total, total / 1e6))
