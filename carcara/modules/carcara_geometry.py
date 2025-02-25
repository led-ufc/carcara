#! python3

import re
import rhinoscriptsyntax as rs
from shapely.wkt import loads
from shapely.geometry import Point, MultiPoint, LineString, MultiLineString, Polygon, MultiPolygon

def parse_wkt(wkt_str):
    """Parse the WKT string and return the Shapely geometry object."""
    try:
        geometry = loads(wkt_str)
        return geometry
    except Exception as e:
        raise ValueError(f"Failed to parse WKT string: {wkt_str}") from e

def create_gh_point(x, y, z=0.0):
    """Create a 3D point in Grasshopper with a default z-coordinate of 0.0 if not provided."""
    return rs.AddPoint((x, y, z))

def create_gh_multipoint(points):
    """Create a list of 3D points in Grasshopper."""
    return [create_gh_point(p.x, p.y, p.z if p.has_z else 0.0) for p in points]

def create_gh_linestring(coords):
    """Create a line in Grasshopper."""
    return rs.AddPolyline([(c[0], c[1], c[2] if len(c) > 2 else 0.0) for c in coords])

def create_gh_multilinestring(lines):
    """Create a list of lines in Grasshopper."""
    return [create_gh_linestring(line.coords) for line in lines]

def create_gh_polygon(exterior, interiors=None):
    """Create a closed polyline in Grasshopper for a polygon."""
    exterior_coords = [(c[0], c[1], c[2] if len(c) > 2 else 0.0) for c in exterior.coords]
    exterior_polyline = rs.AddPolyline(exterior_coords + [exterior_coords[0]])  # Close the polyline
    
    if interiors:
        interior_polylines = [rs.AddPolyline([(c[0], c[1], c[2] if len(c) > 2 else 0.0) for c in interior.coords] + [(c[0], c[1], c[2] if len(c) > 2 else 0.0) for c in interior.coords][0]) for interior in interiors]
        return [exterior_polyline] + interior_polylines
    else:
        return exterior_polyline

def create_gh_multipolygon(polygons):
    """Create a list of closed polylines in Grasshopper for a multipolygon."""
    polylines = []
    for poly in polygons:
        exterior_coords = [(c[0], c[1], c[2] if len(c) > 2 else 0.0) for c in poly.exterior.coords]
        exterior_polyline = rs.AddPolyline(exterior_coords + [exterior_coords[0]])  # Close the polyline
        polylines.append(exterior_polyline)
        
        if poly.interiors:
            interior_polylines = [rs.AddPolyline([(c[0], c[1], c[2] if len(c) > 2 else 0.0) for c in interior.coords] + [(c[0], c[1], c[2] if len(c) > 2 else 0.0) for c in interior.coords][0]) for interior in poly.interiors]
            polylines.extend(interior_polylines)
    
    return polylines

def construct_gh_geom(wkt_str):
    """Construct Grasshopper geometry from WKT string and return a tree structure."""
    geometry = parse_wkt(wkt_str)
    
    if isinstance(geometry, Point):
        return create_gh_point(geometry.x, geometry.y, geometry.z if geometry.has_z else 0.0)
    elif isinstance(geometry, MultiPoint):
        return create_gh_multipoint(geometry.geoms)
    elif isinstance(geometry, LineString):
        return create_gh_linestring(geometry.coords)
    elif isinstance(geometry, MultiLineString):
        return create_gh_multilinestring(geometry.geoms)
    elif isinstance(geometry, Polygon):
        return create_gh_polygon(geometry.exterior, geometry.interiors)
    elif isinstance(geometry, MultiPolygon):
        return create_gh_multipolygon(geometry.geoms)
    else:
        raise ValueError(f"Unsupported geometry type: {type(geometry)}")