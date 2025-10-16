"""Carcara Geometry - WKT and Grasshopper Geometry Conversion Module

This module provides bidirectional conversion between Well-Known Text (WKT) format
and Grasshopper/Rhino geometry objects. Supports points, lines, polygons, and their
multi-part variants. Also includes polygon analysis utilities like point-in-polygon
testing and pole of inaccessibility calculation.

WKT to Grasshopper:
    - parse_wkt: Parse WKT string to Shapely geometry
    - construct_gh_geom: Convert WKT to Grasshopper geometry
    - create_gh_point, create_gh_linestring, create_gh_polygon: Individual converters

Grasshopper to WKT:
    - construct_wkt: Convert Grasshopper geometry to WKT
    - gh_point_to_wkt, gh_linestring_to_wkt, gh_polygon_to_wkt: Individual converters
    - gh_multipolygon_to_wkt, gh_multilinestring_to_wkt: Multi-part converters

Polygon Analysis:
    - point_in_polygon: Ray casting point-in-polygon test
    - point_to_polygon_distance: Distance from point to polygon boundary
    - polygon_centroid: Calculate geometric centroid
    - polylabel: Find pole of inaccessibility (farthest interior point from edges)
    - find_interior_point: Combined centroid/polylabel strategy

Version: 1.0
Date: 2025/10/16
Requires: rhinoscriptsyntax, Rhino.Geometry, shapely
"""

import re
import math
import rhinoscriptsyntax as rs
import Rhino.Geometry as rg
from shapely.wkt import loads
from shapely.geometry import (
    Point, MultiPoint, 
    LineString, MultiLineString, 
    Polygon, MultiPolygon
)


###############################################################################
# HELPER FUNCTIONS
###############################################################################

def _to_point3d(pt):
    """
    Ensure that pt is a Point3d.
    
    Args:
        pt: Point object (Point3d or object with Location attribute)
    
    Returns:
        Point3d: Converted point
    
    Raises:
        ValueError: If conversion fails
    """
    if isinstance(pt, rg.Point3d):
        return pt
    elif hasattr(pt, "Location"):
        return pt.Location
    else:
        raise ValueError("Cannot convert {} to Point3d.".format(type(pt)))


###############################################################################
# WKT TO GRASSHOPPER CONVERSION
###############################################################################

def parse_wkt(wkt_str):
    """
    Parse WKT string and return Shapely geometry object.
    
    Args:
        wkt_str (str): Well-Known Text string
    
    Returns:
        shapely.geometry: Parsed geometry object
    
    Raises:
        ValueError: If WKT parsing fails
    """
    try:
        geometry = loads(wkt_str)
        return geometry
    except Exception as e:
        raise ValueError("Failed to parse WKT string: {}".format(wkt_str))


def create_gh_point(x, y, z=0.0):
    """
    Create 3D point in Grasshopper.
    
    Args:
        x (float): X coordinate
        y (float): Y coordinate
        z (float, optional): Z coordinate. Defaults to 0.0
    
    Returns:
        Point: Grasshopper point object
    """
    return rs.AddPoint((x, y, z))


def create_gh_multipoint(points):
    """
    Create list of 3D points in Grasshopper.
    
    Args:
        points: List of Shapely Point objects
    
    Returns:
        list: List of Grasshopper point objects
    """
    return [create_gh_point(p.x, p.y, p.z if p.has_z else 0.0) for p in points]


def create_gh_linestring(coords):
    """
    Create polyline in Grasshopper from coordinates.
    
    Args:
        coords: List of coordinate tuples
    
    Returns:
        PolylineCurve: Grasshopper polyline
    """
    return rs.AddPolyline([
        (c[0], c[1], c[2] if len(c) > 2 else 0.0) for c in coords
    ])


def create_gh_multilinestring(lines):
    """
    Create list of polylines in Grasshopper.
    
    Args:
        lines: List of Shapely LineString objects
    
    Returns:
        list: List of Grasshopper polylines
    """
    return [create_gh_linestring(line.coords) for line in lines]


def create_gh_polygon(exterior, interiors=None):
    """
    Create closed polyline(s) in Grasshopper for polygon.
    
    Args:
        exterior: Shapely LinearRing (exterior boundary)
        interiors: List of Shapely LinearRing objects (holes), optional
    
    Returns:
        PolylineCurve or list: Closed polyline(s)
    """
    exterior_coords = [
        (c[0], c[1], c[2] if len(c) > 2 else 0.0) for c in exterior.coords
    ]
    exterior_polyline = rs.AddPolyline(exterior_coords + [exterior_coords[0]])
    
    if interiors:
        interior_polylines = []
        for interior in interiors:
            int_coords = [
                (c[0], c[1], c[2] if len(c) > 2 else 0.0) for c in interior.coords
            ]
            int_polyline = rs.AddPolyline(int_coords + [int_coords[0]])
            interior_polylines.append(int_polyline)
        return [exterior_polyline] + interior_polylines
    else:
        return exterior_polyline


def create_gh_multipolygon(polygons):
    """
    Create list of closed polylines in Grasshopper for multipolygon.
    
    Args:
        polygons: List of Shapely Polygon objects
    
    Returns:
        list: List of closed polylines (including holes)
    """
    polylines = []
    for poly in polygons:
        exterior_coords = [
            (c[0], c[1], c[2] if len(c) > 2 else 0.0) 
            for c in poly.exterior.coords
        ]
        exterior_polyline = rs.AddPolyline(exterior_coords + [exterior_coords[0]])
        polylines.append(exterior_polyline)
        
        if poly.interiors:
            for interior in poly.interiors:
                int_coords = [
                    (c[0], c[1], c[2] if len(c) > 2 else 0.0) 
                    for c in interior.coords
                ]
                int_polyline = rs.AddPolyline(int_coords + [int_coords[0]])
                polylines.append(int_polyline)
    
    return polylines


def construct_gh_geom(wkt_str):
    """
    Construct Grasshopper geometry from WKT string.
    
    Args:
        wkt_str (str): Well-Known Text string
    
    Returns:
        Grasshopper geometry object(s)
    
    Raises:
        ValueError: If geometry type is unsupported
    """
    geometry = parse_wkt(wkt_str)
    
    if isinstance(geometry, Point):
        return create_gh_point(
            geometry.x, 
            geometry.y, 
            geometry.z if geometry.has_z else 0.0
        )
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
        raise ValueError("Unsupported geometry type: {}".format(type(geometry)))


###############################################################################
# GRASSHOPPER TO WKT CONVERSION
###############################################################################

def gh_point_to_wkt(point):
    """
    Convert Grasshopper point to WKT POINT string.
    
    Only X and Y coordinates are included.
    
    Args:
        point: Point3d or object with Location attribute
    
    Returns:
        str: WKT POINT representation
    """
    p = _to_point3d(point)
    return "POINT ({:.6f} {:.6f})".format(p.X, p.Y)


def gh_linestring_to_wkt(linestring):
    """
    Convert Grasshopper linestring to WKT LINESTRING string.
    
    Handles LineCurve, NurbsCurve, PolylineCurve, Polyline, and lists.
    
    Args:
        linestring: Curve object or list of points
    
    Returns:
        str: WKT LINESTRING representation
    """
    pts = []
    
    if isinstance(linestring, rg.LineCurve):
        start = linestring.PointAt(linestring.Domain.T0)
        end = linestring.PointAt(linestring.Domain.T1)
        pts = [_to_point3d(start), _to_point3d(end)]
    
    elif isinstance(linestring, rg.NurbsCurve):
        for i in range(linestring.Points.Count):
            cp = linestring.Points[i]
            if hasattr(cp, "Location"):
                pts.append(_to_point3d(cp.Location))
            else:
                pts.append(_to_point3d(cp))
    
    elif hasattr(linestring, "ToPolyline") and isinstance(linestring, (rg.PolylineCurve, rg.Polyline)):
        poly = linestring.ToPolyline()
        pts = [_to_point3d(pt) for pt in poly]
    
    elif isinstance(linestring, list):
        pts = [_to_point3d(pt) for pt in linestring]
    
    else:
        try:
            pts = [_to_point3d(pt) for pt in linestring]
        except:
            pts = [_to_point3d(linestring)]
    
    pts_str = ", ".join("{:.6f} {:.6f}".format(pt.X, pt.Y) for pt in pts)
    return "LINESTRING ({})".format(pts_str)


def gh_polygon_to_wkt(polygon):
    """
    Convert Grasshopper polygon to WKT POLYGON string.
    
    Only X and Y coordinates are included.
    
    Args:
        polygon: Closed PolylineCurve or Polyline
    
    Returns:
        str: WKT POLYGON representation
    
    Raises:
        ValueError: If no points found
    """
    pts = []
    if hasattr(polygon, "ToPolyline"):
        poly = polygon.ToPolyline()
        pts = [_to_point3d(pt) for pt in poly]
    else:
        pts = [_to_point3d(pt) for pt in polygon]
    
    if not pts:
        raise ValueError("No points found in the polygon geometry.")
    
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    
    pts_str = ", ".join("{:.6f} {:.6f}".format(pt.X, pt.Y) for pt in pts)
    return "POLYGON (({}))".format(pts_str)


def gh_multipolygon_to_wkt(gh_geom_list):
    """
    Convert list of Grasshopper polygons to WKT MULTIPOLYGON string.
    
    Args:
        gh_geom_list (list): List of polygon geometries
    
    Returns:
        str: WKT MULTIPOLYGON representation
    
    Raises:
        ValueError: If geometry list is empty
    """
    if not gh_geom_list:
        raise ValueError("The geometry list is empty.")
    
    polygon_wkts = []
    for poly in gh_geom_list:
        poly_wkt = gh_polygon_to_wkt(poly)
        inner = poly_wkt.replace("POLYGON", "").strip()
        if inner.startswith("(") and inner.endswith(")"):
            inner = inner[1:-1].strip()
        polygon_wkts.append("({})".format(inner))
    
    return "MULTIPOLYGON ({})".format(", ".join(polygon_wkts))


def gh_multilinestring_to_wkt(gh_geom_list):
    """
    Convert list of curves to WKT MULTILINESTRING string.
    
    Only X and Y coordinates are included.
    
    Args:
        gh_geom_list (list): List of open curve geometries
    
    Returns:
        str: WKT MULTILINESTRING representation
    """
    ls_parts = []
    for crv in gh_geom_list:
        wkt = gh_linestring_to_wkt(crv)
        inner = wkt.replace("LINESTRING", "").strip()
        if inner.startswith("(") and inner.endswith(")"):
            inner = inner[1:-1].strip()
        ls_parts.append("({})".format(inner))
    
    return "MULTILINESTRING ({})".format(", ".join(ls_parts))


def construct_wkt(gh_geom):
    """
    Convert Grasshopper geometry to WKT string.
    
    Args:
        gh_geom: Single geometry or list of geometries
    
    Returns:
        str: WKT representation
    
    Raises:
        ValueError: If geometry type is unsupported or list is empty
    """
    if isinstance(gh_geom, list):
        if len(gh_geom) == 0:
            raise ValueError("Empty geometry list provided.")
        elif len(gh_geom) == 1:
            return construct_wkt(gh_geom[0])
        else:
            # All points -> MULTIPOINT
            if all(hasattr(g, "X") or hasattr(g, "Location") for g in gh_geom):
                pts = [_to_point3d(g) for g in gh_geom]
                pts_str = ", ".join("{:.6f} {:.6f}".format(pt.X, pt.Y) for pt in pts)
                return "MULTIPOINT ({})".format(pts_str)
            
            # All curves -> check if closed
            elif all(isinstance(g, (rg.PolylineCurve, rg.Polyline, rg.LineCurve, rg.NurbsCurve)) for g in gh_geom):
                if hasattr(gh_geom[0], "IsClosed") and gh_geom[0].IsClosed:
                    return gh_multipolygon_to_wkt(gh_geom)
                else:
                    return gh_multilinestring_to_wkt(gh_geom)
            else:
                converted = [construct_wkt(g) for g in gh_geom]
                return ", ".join(converted)
    else:
        if isinstance(gh_geom, rg.Point3d) or hasattr(gh_geom, "Location"):
            return gh_point_to_wkt(gh_geom)
        elif isinstance(gh_geom, (rg.PolylineCurve, rg.Polyline)):
            if hasattr(gh_geom, "IsClosed") and gh_geom.IsClosed:
                return gh_polygon_to_wkt(gh_geom)
            else:
                return gh_linestring_to_wkt(gh_geom)
        elif isinstance(gh_geom, (rg.LineCurve, rg.NurbsCurve)):
            return gh_linestring_to_wkt(gh_geom)
        else:
            raise ValueError("Unsupported geometry type: {}".format(type(gh_geom)))


###############################################################################
# POLYGON ANALYSIS FUNCTIONS
###############################################################################

def point_in_polygon(x, y, vertices):
    """
    Ray casting algorithm to test if point is inside polygon.
    
    Args:
        x (float): Point X coordinate
        y (float): Point Y coordinate
        vertices (list): List of (x, y) tuples defining polygon
    
    Returns:
        bool: True if point is inside polygon
    """
    n = len(vertices)
    inside = False
    
    p1x, p1y = vertices[0]
    for i in range(1, n + 1):
        p2x, p2y = vertices[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    
    return inside


def point_to_polygon_distance(x, y, vertices):
    """
    Calculate minimum distance from point to polygon boundary.
    
    Args:
        x (float): Point X coordinate
        y (float): Point Y coordinate
        vertices (list): List of (x, y) tuples defining polygon
    
    Returns:
        float: Minimum distance to polygon boundary
    """
    min_dist = float('inf')
    
    for i in range(len(vertices) - 1):
        x1, y1 = vertices[i]
        x2, y2 = vertices[i + 1]
        
        dx = x2 - x1
        dy = y2 - y1
        
        if dx == 0 and dy == 0:
            dist = math.sqrt((x - x1)**2 + (y - y1)**2)
        else:
            t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
            proj_x = x1 + t * dx
            proj_y = y1 + t * dy
            dist = math.sqrt((x - proj_x)**2 + (y - proj_y)**2)
        
        min_dist = min(min_dist, dist)
    
    return min_dist


def polygon_centroid(vertices):
    """
    Calculate geometric centroid of polygon.
    
    Args:
        vertices (list): List of (x, y) tuples defining polygon
    
    Returns:
        tuple: (x, y) coordinates of centroid
    """
    unique_vertices = vertices[:-1] if vertices[0] == vertices[-1] else vertices
    
    if not unique_vertices:
        return (0, 0)
    
    sum_x = sum(v[0] for v in unique_vertices)
    sum_y = sum(v[1] for v in unique_vertices)
    
    return (sum_x / len(unique_vertices), sum_y / len(unique_vertices))


def polylabel(vertices, precision=0.01):
    """
    Find pole of inaccessibility using grid search.
    
    Returns the point inside polygon that is farthest from all edges.
    
    Args:
        vertices (list): List of (x, y) tuples defining polygon
        precision (float, optional): Grid cell size precision. Defaults to 0.01
    
    Returns:
        tuple: ((x, y), distance) where (x, y) is the pole and distance is the distance to nearest edge
    """
    xs = [v[0] for v in vertices[:-1]]
    ys = [v[1] for v in vertices[:-1]]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    
    width = max_x - min_x
    height = max_y - min_y
    cell_size = max(min(width, height) / 20, precision)
    
    best_point = None
    best_distance = -1
    
    y = min_y
    while y <= max_y:
        x = min_x
        while x <= max_x:
            if point_in_polygon(x, y, vertices):
                distance = point_to_polygon_distance(x, y, vertices)
                if distance > best_distance:
                    best_distance = distance
                    best_point = (x, y)
            x += cell_size
        y += cell_size
    
    if best_point is None:
        best_point = ((min_x + max_x) / 2, (min_y + max_y) / 2)
        best_distance = 0
    
    return best_point, best_distance


def find_interior_point(vertices, precision=0.01):
    """
    Find point inside polygon using centroid-first strategy.
    
    Tries centroid first (fastest), falls back to polylabel if outside.
    
    Args:
        vertices (list): List of (x, y) tuples defining polygon
        precision (float, optional): Precision for polylabel. Defaults to 0.01
    
    Returns:
        tuple: ((x, y), method) where method is "centroid" or "polylabel"
    """
    centroid = polygon_centroid(vertices)
    
    if point_in_polygon(centroid[0], centroid[1], vertices):
        return centroid, "centroid"
    
    point, distance = polylabel(vertices, precision)
    return point, "polylabel"
