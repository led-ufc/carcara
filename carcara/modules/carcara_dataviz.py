"""Carcara DataViz - SVG Generation and Export Module

This module provides utilities for creating and saving SVG (Scalable Vector Graphics)
files from Grasshopper/Rhino geometry. Includes functions for canvas management,
SVG document construction, geometry extraction, and file export.

Core Functions:
    - canvas_origin_info: Extract dimensions from canvas geometry
    - bounding_box_info: Compute bounding box from geometries
    - combine_svg: Build complete SVG document
    - save_svg: Save SVG string to file

Geometry Extraction:
    - extract_circle_parameters: Get circle center and radius
    - extract_polyline_points: Get polyline points as (x,y) tuples
    - extract_nurbs_path_data: Sample NURBS curve for SVG path

SVG Element Generation:
    - svg_circle: Generate circle element
    - svg_polyline: Generate polyline/polygon element
    - svg_polygon: Generate polygon element (always closed)
    - svg_path: Generate path element
    - svg_text: Generate text element with alignment
    - svg_rect: Generate rectangle element

Version: 1.0
Date: 2025/10/16
"""

import os
import Rhino.Geometry as rg


###############################################################################
# CANVAS AND BOUNDING BOX FUNCTIONS
###############################################################################

def canvas_origin_info(canvas):
    """
    Extract origin point and dimensions from canvas rectangle geometry.
    
    Args:
        canvas: Rectangle geometry (Rectangle3d, Curve, or similar)
    
    Returns:
        tuple: (anchor_point, width, height)
    
    Raises:
        ValueError: If canvas is not a valid rectangle
    """
    try:
        if isinstance(canvas, rg.Rectangle3d):
            anchor_point = canvas.Corner(0)
            width = canvas.Width
            height = canvas.Height
            return anchor_point, width, height
        
        elif isinstance(canvas, (rg.Curve, rg.PolylineCurve)):
            bbox = canvas.GetBoundingBox(True)
            width = bbox.Max.X - bbox.Min.X
            height = bbox.Max.Y - bbox.Min.Y
            anchor_point = rg.Point3d(bbox.Min.X, bbox.Min.Y, bbox.Min.Z)
            return anchor_point, width, height
        
        else:
            raise ValueError("Canvas must be Rectangle3d or Curve geometry")
    
    except Exception as e:
        raise ValueError("Error extracting canvas info: {}".format(e))


def bounding_box_info(geometries):
    """
    Compute bounding box anchor point and dimensions from geometries.
    
    Args:
        geometries (list): List of geometry objects
    
    Returns:
        tuple: (anchor_point, width, height)
    """
    if not geometries:
        return rg.Point3d(0, 0, 0), 0, 0
    
    bbox = rg.BoundingBox.Empty
    valid_count = 0
    
    for geom in geometries:
        if geom is None:
            continue
        
        try:
            geom_bbox = None
            
            if isinstance(geom, rg.Point3d):
                geom_bbox = rg.BoundingBox(geom, geom)
            
            elif isinstance(geom, rg.Circle):
                center = geom.Center
                radius = geom.Radius
                geom_bbox = rg.BoundingBox(
                    rg.Point3d(center.X - radius, center.Y - radius, center.Z),
                    rg.Point3d(center.X + radius, center.Y + radius, center.Z)
                )
            
            elif isinstance(geom, rg.Polyline):
                geom_bbox = geom.BoundingBox
            
            elif hasattr(geom, 'GetBoundingBox'):
                geom_bbox = geom.GetBoundingBox(True)
            
            elif hasattr(geom, 'BoundingBox'):
                geom_bbox = geom.BoundingBox
            
            if geom_bbox and geom_bbox.IsValid:
                bbox.Union(geom_bbox)
                valid_count += 1
        
        except Exception:
            continue
    
    if bbox.IsValid and valid_count > 0:
        anchor_point = rg.Point3d(bbox.Min.X, bbox.Min.Y, bbox.Min.Z)
        width = bbox.Max.X - bbox.Min.X
        height = bbox.Max.Y - bbox.Min.Y
        return anchor_point, width, height
    else:
        return rg.Point3d(0, 0, 0), 0, 0


###############################################################################
# GEOMETRY EXTRACTION FUNCTIONS
###############################################################################

def extract_circle_parameters(circle):
    """
    Extract center coordinates and radius from circle geometry.
    
    Args:
        circle: Circle geometry object
    
    Returns:
        tuple: (cx, cy, radius)
    
    Raises:
        ValueError: If geometry is not a valid circle
    """
    try:
        if isinstance(circle, rg.Circle):
            return circle.Center.X, circle.Center.Y, circle.Radius
        
        elif isinstance(circle, rg.ArcCurve):
            if circle.IsCircle():
                arc_circle = circle.Arc
                if abs(arc_circle.AngleDegrees - 360.0) < 0.01:
                    return arc_circle.Center.X, arc_circle.Center.Y, arc_circle.Radius
                else:
                    raise ValueError("ArcCurve is not a complete circle (angle: {:.2f}°)".format(
                        arc_circle.AngleDegrees))
            else:
                raise ValueError("ArcCurve is not circular")
        
        elif isinstance(circle, rg.NurbsCurve):
            success, circle_geom = circle.TryGetCircle()
            if success:
                return circle_geom.Center.X, circle_geom.Center.Y, circle_geom.Radius
            else:
                raise ValueError("NurbsCurve cannot be converted to circle")
        
        elif isinstance(circle, rg.Curve):
            nurbs = circle.ToNurbsCurve()
            if nurbs:
                success, circle_geom = nurbs.TryGetCircle()
                if success:
                    return circle_geom.Center.X, circle_geom.Center.Y, circle_geom.Radius
            raise ValueError("Curve cannot be converted to circle")
        
        else:
            raise TypeError("Unsupported circle type: {}".format(type(circle).__name__))
    
    except (ValueError, TypeError) as e:
        raise e
    except Exception as e:
        raise ValueError("Error extracting circle parameters: {}".format(e))


def extract_polyline_points(polyline):
    """
    Extract point coordinates from polyline geometry.
    
    Args:
        polyline: Polyline geometry object
    
    Returns:
        list: List of (x, y) coordinate tuples
    
    Raises:
        ValueError: If geometry cannot be converted to polyline
    """
    points = []
    
    try:
        if isinstance(polyline, rg.Polyline):
            points = [(pt.X, pt.Y) for pt in polyline]
        
        elif isinstance(polyline, rg.PolylineCurve):
            success, pline = polyline.TryGetPolyline()
            if success:
                points = [(pt.X, pt.Y) for pt in pline]
            else:
                for i in range(polyline.PointCount):
                    pt = polyline.Point(i)
                    points.append((pt.X, pt.Y))
        
        elif isinstance(polyline, rg.Curve):
            success, pline = polyline.TryGetPolyline()
            if success:
                points = [(pt.X, pt.Y) for pt in pline]
            else:
                nurbs = polyline.ToNurbsCurve()
                if nurbs:
                    for i in range(nurbs.Points.Count):
                        pt = nurbs.Points[i].Location
                        points.append((pt.X, pt.Y))
                else:
                    raise ValueError("Curve cannot be converted to polyline points")
        
        elif hasattr(polyline, '__iter__'):
            for pt in polyline:
                if isinstance(pt, rg.Point3d):
                    points.append((pt.X, pt.Y))
                elif hasattr(pt, 'X') and hasattr(pt, 'Y'):
                    points.append((pt.X, pt.Y))
                elif isinstance(pt, (list, tuple)) and len(pt) >= 2:
                    points.append((pt[0], pt[1]))
        
        else:
            raise ValueError("Unsupported polyline type: {}".format(type(polyline)))
        
        if not points or len(points) < 2:
            raise ValueError("Polyline has insufficient points (need at least 2)")
        
        return points
        
    except Exception as e:
        raise ValueError("Error extracting polyline points: {}".format(e))


def extract_nurbs_path_data(curve, sample_count, anchor_point):
    """
    Extract SVG path data from NURBS curve using linear approximation.
    
    Args:
        curve: NURBS curve geometry
        sample_count (int): Number of sample points
        anchor_point (Point3d): Canvas anchor for coordinate transformation
    
    Returns:
        str: SVG path data string
    
    Raises:
        ValueError: If curve or sample_count is invalid
    """
    if curve is None or sample_count < 2:
        return ""
    
    try:
        domain = curve.Domain
        t_values = [domain.T0 + (domain.T1 - domain.T0) * i / (sample_count - 1) 
                   for i in range(sample_count)]
        
        path_commands = []
        
        for i, t in enumerate(t_values):
            pt = curve.PointAt(t)
            x = pt.X - anchor_point.X
            y = anchor_point.Y - pt.Y
            command = "M" if i == 0 else "L"
            path_commands.append("{}{},{}".format(command, x, y))
        
        return " ".join(path_commands)
    
    except Exception as e:
        raise ValueError("Error extracting path data: {}".format(e))


###############################################################################
# SVG DOCUMENT FUNCTIONS
###############################################################################

def combine_svg(elements, width="800px", height="600px", viewBox="0 0 800 600", 
                xmlns="http://www.w3.org/2000/svg", version="1.1"):
    """
    Combine SVG elements into complete SVG document with proper headers.
    
    Args:
        elements (list[str]): List of SVG element strings
        width (str, optional): SVG width attribute
        height (str, optional): SVG height attribute
        viewBox (str, optional): SVG viewBox attribute
        xmlns (str, optional): XML namespace
        version (str, optional): SVG version
    
    Returns:
        str: Complete SVG document as string
    """
    svg_body = "\n".join(elements)
    
    svg_document = '''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="{xmlns}" version="{version}" width="{width}" height="{height}" viewBox="{viewBox}">
{body}
</svg>'''.format(
        xmlns=xmlns,
        version=version,
        width=width,
        height=height,
        viewBox=viewBox,
        body=svg_body
    )
    
    return svg_document


def save_svg(svg_content, file_path):
    """
    Save SVG content to file.
    
    Args:
        svg_content (str): Complete SVG document as string
        file_path (str): Absolute or relative file path for output
    
    Raises:
        IOError: If file cannot be written
        OSError: If directory cannot be created
    """
    try:
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(svg_content)
    
    except IOError as e:
        raise IOError("Error writing SVG file to {}: {}".format(file_path, e))
    except OSError as e:
        raise OSError("Error creating directory for {}: {}".format(file_path, e))


###############################################################################
# SVG ELEMENT GENERATION FUNCTIONS
###############################################################################

def svg_circle(cx, cy, r, stroke="none", fill="none", stroke_width=0):
    """Generate SVG circle element string."""
    if r <= 0:
        return ""
    
    return '<circle cx="{}" cy="{}" r="{}" fill="{}" stroke="{}" stroke-width="{}"/>'.format(
        cx, cy, r, fill, stroke, stroke_width
    )


def svg_polyline(points, stroke="none", fill="none", stroke_width=0, dash=""):
    """Generate SVG polyline or polygon element string."""
    if not points or len(points) < 2:
        return ""
    
    is_closed = False
    if len(points) >= 3:
        tolerance = 0.001
        first = points[0]
        last = points[-1]
        if abs(first[0] - last[0]) < tolerance and abs(first[1] - last[1]) < tolerance:
            is_closed = True
    
    points_str = " ".join(["{},{}".format(x, y) for x, y in points])
    element_type = "polygon" if is_closed else "polyline"
    
    style_parts = []
    style_parts.append('fill="{}"'.format(fill))
    style_parts.append('stroke="{}"'.format(stroke))
    style_parts.append('stroke-width="{}"'.format(stroke_width))
    
    if dash and dash.strip():
        style_parts.append('stroke-dasharray="{}"'.format(dash))
    
    return '<{} points="{}" {}/>'.format(
        element_type,
        points_str,
        " ".join(style_parts)
    )


def svg_polygon(points, stroke="none", fill="none", stroke_width=0, dash=""):
    """Generate SVG polygon element (always closed)."""
    if not points or len(points) < 3:
        return ""
    
    points_str = " ".join(["{},{}".format(x, y) for x, y in points])
    
    style_parts = []
    style_parts.append('fill="{}"'.format(fill))
    style_parts.append('stroke="{}"'.format(stroke))
    style_parts.append('stroke-width="{}"'.format(stroke_width))
    
    if dash and dash.strip():
        style_parts.append('stroke-dasharray="{}"'.format(dash))
    
    return '<polygon points="{}" {}/>'.format(
        points_str,
        " ".join(style_parts)
    )


def svg_path(path_data, stroke="none", fill="none", stroke_width=0, dash=""):
    """Generate SVG path element string."""
    if not path_data or not path_data.strip():
        return ""
    
    style_parts = []
    style_parts.append('fill="{}"'.format(fill))
    style_parts.append('stroke="{}"'.format(stroke))
    style_parts.append('stroke-width="{}"'.format(stroke_width))
    
    if dash and dash.strip():
        style_parts.append('stroke-dasharray="{}"'.format(dash))
    
    return '<path d="{}" {}/>'.format(
        path_data,
        " ".join(style_parts)
    )


def svg_text(x, y, text, font_family="Arial", font_size=12, fill="black",
            text_anchor="start", dominant_baseline="auto"):
    """Generate SVG text element with alignment."""
    return '<text x="{}" y="{}" font-family="{}" font-size="{}px" fill="{}" text-anchor="{}" dominant-baseline="{}">{}</text>'.format(
        x, y, font_family, font_size, fill, text_anchor, dominant_baseline, text
    )


def svg_rect(x, y, width, height, fill="black", stroke="none", stroke_width=1):
    """Generate SVG rectangle element."""
    return '<rect x="{}" y="{}" width="{}" height="{}" fill="{}" stroke="{}" stroke-width="{}"/>'.format(
        x, y, width, height, fill, stroke, stroke_width
    )
