"""Carcara DataViz - SVG Generation and Export Module

This module provides utilities for creating and saving SVG (Scalable Vector Graphics)
files from Grasshopper/Rhino geometry. Includes functions for canvas management,
SVG document construction, geometry extraction, coordinate transformation, color
conversion, and file export.

Core Functions:
    - canvas_origin_info: Extract dimensions from canvas geometry
    - bounding_box_info: Compute bounding box from geometries
    - combine_svg: Build complete SVG document
    - save_svg: Save SVG string to file

Grasshopper Integration Helpers:
    - normalize_input_list: Convert input to list format
    - get_indexed_value: Get value from list with fallback logic
    - convert_color_to_svg: Convert .NET Color to SVG format
    - get_canvas_dimensions: Get canvas info from canvas or geometries
    - transform_point_to_svg: Transform Rhino to SVG coordinates

Geometry Extraction:
    - extract_circle_parameters: Get circle center and radius
    - extract_polyline_points: Get polyline points with transformation
    - extract_nurbs_path_data: Sample NURBS curve for SVG path

SVG Element Generation:
    - svg_circle: Generate circle element
    - svg_polyline: Generate polyline/polygon element
    - svg_polygon: Generate polygon element (always closed)
    - svg_path: Generate path element
    - svg_text: Generate text element with alignment
    - svg_rect: Generate rectangle element

Version: 2.0
Date: 2025/11/14
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
# GRASSHOPPER INTEGRATION HELPERS
###############################################################################

def normalize_input_list(data):
    """
    Normalize input to list format.
    
    Converts single items or iterables to a standard list format.
    Returns empty list if input is None.
    
    Args:
        data: Single item, iterable, or None
    
    Returns:
        list: List of items or empty list if None
    
    Examples:
        >>> normalize_input_list(5)
        [5]
        >>> normalize_input_list([1, 2, 3])
        [1, 2, 3]
        >>> normalize_input_list(None)
        []
    """
    if data is None:
        return []
    if not hasattr(data, '__iter__'):
        return [data]
    return list(data)


def get_indexed_value(value_list, index, default):
    """
    Get value from list by index with intelligent fallback logic.
    
    Fallback rules:
    - Single value: applies to all indices
    - List shorter than index: uses last value
    - None value at index: uses default
    - Empty list: uses default
    
    Args:
        value_list: Single value, list of values, or None
        index (int): Current item index
        default: Default value if value_list is None or empty
    
    Returns:
        Value for this index (any type)
    
    Examples:
        >>> get_indexed_value(5, 0, 0)
        5  # Single value applies to all
        >>> get_indexed_value([10, 20, 30], 1, 0)
        20
        >>> get_indexed_value([10, 20], 5, 0)
        20  # Uses last value for out-of-range index
        >>> get_indexed_value(None, 0, 99)
        99  # Uses default
    """
    if value_list is None:
        return default
    
    if not hasattr(value_list, '__iter__'):
        # Single value - apply to all indices
        return value_list
    elif index < len(value_list):
        # Get value at index
        value = value_list[index]
        return value if value is not None else default
    elif len(value_list) > 0:
        # Use last value for out-of-range indices
        value = value_list[-1]
        return value if value is not None else default
    else:
        # Empty list
        return default


def convert_color_to_svg(color_input):
    """
    Convert Grasshopper/System.Drawing.Color to SVG format.
    
    Args:
        color_input: System.Drawing.Color object or string
    
    Returns:
        tuple: (color_string, opacity)
            color_string: Hex color like "#FF0000"
            opacity: Float 0-1 (default 1.0 if not specified)
    """
    # Handle None
    if color_input is None:
        return "#000000", 1.0  # Black, fully opaque
    
    # Handle string input
    if isinstance(color_input, str):
        return color_input, 1.0
    
    # Handle System.Drawing.Color
    try:
        if hasattr(color_input, 'R') and hasattr(color_input, 'G') and hasattr(color_input, 'B'):
            r = color_input.R
            g = color_input.G
            b = color_input.B
            
            # Get alpha if available
            if hasattr(color_input, 'A'):
                opacity = color_input.A / 255.0
            else:
                opacity = 1.0
            
            # Convert to hex
            hex_color = "#{:02X}{:02X}{:02X}".format(r, g, b)
            return hex_color, opacity
    except:
        pass
    
    # Fallback
    return "#000000", 1.0



def get_canvas_dimensions(canvas, geometries):
    """
    Get canvas anchor point and dimensions.
    
    Uses provided canvas if available, otherwise computes bounding box
    from geometries.
    
    Args:
        canvas: Canvas rectangle geometry or None
        geometries (list): List of geometry objects (used if canvas is None)
    
    Returns:
        tuple: (anchor_point, width, height)
    
    Examples:
        >>> anchor, w, h = get_canvas_dimensions(canvas_rect, None)
        >>> anchor, w, h = get_canvas_dimensions(None, [circle1, circle2])
    """
    if canvas is not None:
        return canvas_origin_info(canvas)
    else:
        return bounding_box_info(geometries)


def transform_point_to_svg(x, y, anchor_point, canvas_height):
    """
    Transform Rhino coordinates to SVG coordinates.
    
    Performs two transformations:
    1. Translation: Makes coordinates relative to canvas anchor point
    2. Y-axis flip: Converts from Rhino Y-up to SVG Y-down coordinate system
    
    Args:
        x (float): Rhino X coordinate
        y (float): Rhino Y coordinate
        anchor_point (Point3d): Canvas anchor point
        canvas_height (float): Canvas height for Y-axis flip
    
    Returns:
        tuple: (svg_x, svg_y) in SVG coordinate system
    
    Examples:
        >>> transform_point_to_svg(5, 10, Point3d(0, 0, 0), 100)
        (5.0, 90.0)  # Y flipped: 100 - 10 = 90
        >>> transform_point_to_svg(15, 5, Point3d(10, 0, 0), 50)
        (5.0, 45.0)  # X translated: 15-10=5, Y flipped: 50-5=45
    """
    svg_x = x - anchor_point.X
    svg_y = y - anchor_point.Y
    svg_y = canvas_height - svg_y  # Flip Y-axis
    return svg_x, svg_y

def extract_plane_transform(plane, anchor_pt=None, canvas_height=0):
    """
    Extract position and rotation from a Rhino Plane for SVG.
    
    Converts Rhino plane to SVG coordinates with rotation.
    Returns position and rotation angle for SVG transform attribute.
    
    Args:
        plane (Plane): Rhino.Geometry.Plane object
        anchor_pt (Point3d): Canvas anchor point for offset (optional)
        canvas_height (float): Canvas height for Y-flip (optional)
    
    Returns:
        tuple: (x, y, rotation_degrees)
            x, y: SVG coordinates
            rotation_degrees: Rotation in degrees (counterclockwise in SVG)
    
    Example:
        >>> x, y, rot = extract_plane_transform(plane, anchor, height)
        >>> transform = "translate({},{}) rotate({})".format(x, y, rot)
    """
    import math
    
    # Get origin point
    origin = plane.Origin
    
    # Transform to SVG coordinates
    if anchor_pt and canvas_height > 0:
        x, y = transform_point_to_svg(origin.X, origin.Y, anchor_pt, canvas_height)
    else:
        x, y = origin.X, origin.Y
    
    # Calculate rotation from plane's X-axis
    # In Rhino: X-axis is the "forward" direction
    x_axis = plane.XAxis
    
    # Calculate angle in radians (atan2 gives angle from positive X-axis)
    angle_radians = math.atan2(x_axis.Y, x_axis.X)
    
    # Convert to degrees
    angle_degrees = math.degrees(angle_radians)
    
    # SVG uses counterclockwise rotation, but we need to flip for Y-down
    # Negate the angle to account for Y-axis flip
    svg_rotation = -angle_degrees
    
    return x, y, svg_rotation


def svg_text_with_transform(x, y, text, rotation=0, font_family="Arial", 
                           font_size=12, fill="black", text_anchor="start",
                           dominant_baseline="auto", fill_opacity=1.0):
    """Generate SVG text element with position and rotation transform."""
    
    # Escape text for XML
    escaped_text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    # Build transform attribute
    if rotation != 0:
        transform = ' transform="translate({},{}) rotate({})"'.format(x, y, rotation)
        x_attr = 0
        y_attr = 0
    else:
        transform = ''
        x_attr = x
        y_attr = y
    
    # Build opacity attribute - FIX HERE
    # Handle None opacity (default to 1.0)
    if fill_opacity is None:
        fill_opacity = 1.0
    
    opacity_attr = '' if fill_opacity >= 1.0 else ' fill-opacity="{}"'.format(fill_opacity)
    
    # Also handle None font_family - FIX HERE
    if font_family is None:
        font_family = "Arial"
    
    return '<text x="{}" y="{}" font-family="{}" font-size="{}" fill="{}" text-anchor="{}" dominant-baseline="{}"{}{}>{}</text>\n'.format(
        x_attr, y_attr, font_family, font_size, fill, text_anchor, dominant_baseline, opacity_attr, transform, escaped_text
    )



###############################################################################
# GEOMETRY EXTRACTION FUNCTIONS
###############################################################################

def extract_circle_parameters(circle):
    """
    Extract center coordinates and radius from circle geometry.
    
    Returns raw Rhino coordinates - transformation should be done separately
    using transform_point_to_svg().
    
    Args:
        circle: Circle geometry object
    
    Returns:
        tuple: (cx, cy, radius) in Rhino coordinates
    
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


def extract_polyline_points(polyline, anchor_point, canvas_height):
    """
    Extract point coordinates from polyline geometry with coordinate transformation.
    
    Handles transformation from Rhino (Y-up) to SVG (Y-down) coordinate systems.
    
    Args:
        polyline: Polyline geometry object
        anchor_point (Point3d): Canvas anchor for translation
        canvas_height (float): Canvas height for Y-axis flip
    
    Returns:
        list: List of (x, y) coordinate tuples in SVG coordinates
    
    Raises:
        ValueError: If geometry cannot be converted to polyline
    """
    points = []
    
    try:
        # Extract raw points first
        raw_points = []
        
        if isinstance(polyline, rg.Polyline):
            raw_points = [(pt.X, pt.Y) for pt in polyline]
        
        elif isinstance(polyline, rg.PolylineCurve):
            success, pline = polyline.TryGetPolyline()
            if success:
                raw_points = [(pt.X, pt.Y) for pt in pline]
            else:
                for i in range(polyline.PointCount):
                    pt = polyline.Point(i)
                    raw_points.append((pt.X, pt.Y))
        
        elif isinstance(polyline, rg.Curve):
            success, pline = polyline.TryGetPolyline()
            if success:
                raw_points = [(pt.X, pt.Y) for pt in pline]
            else:
                nurbs = polyline.ToNurbsCurve()
                if nurbs:
                    for i in range(nurbs.Points.Count):
                        pt = nurbs.Points[i].Location
                        raw_points.append((pt.X, pt.Y))
                else:
                    raise ValueError("Curve cannot be converted to polyline points")
        
        elif hasattr(polyline, '__iter__'):
            for pt in polyline:
                if isinstance(pt, rg.Point3d):
                    raw_points.append((pt.X, pt.Y))
                elif hasattr(pt, 'X') and hasattr(pt, 'Y'):
                    raw_points.append((pt.X, pt.Y))
                elif isinstance(pt, (list, tuple)) and len(pt) >= 2:
                    raw_points.append((pt[0], pt[1]))
        
        else:
            raise ValueError("Unsupported polyline type: {}".format(type(polyline)))
        
        if not raw_points or len(raw_points) < 2:
            raise ValueError("Polyline has insufficient points (need at least 2)")
        
        # Transform all points to SVG coordinates
        for x, y in raw_points:
            svg_x, svg_y = transform_point_to_svg(x, y, anchor_point, canvas_height)
            points.append((svg_x, svg_y))
        
        return points
        
    except Exception as e:
        raise ValueError("Error extracting polyline points: {}".format(e))


def extract_nurbs_path_data(curve, sample_count, anchor_point, canvas_height):
    """
    Extract SVG path data from NURBS curve using linear approximation.
    
    Handles coordinate transformation from Rhino (Y-up) to SVG (Y-down).
    
    Args:
        curve: NURBS curve geometry
        sample_count (int): Number of sample points
        anchor_point (Point3d): Canvas anchor for coordinate transformation
        canvas_height (float): Canvas height for Y-axis flip
    
    Returns:
        str: SVG path data string (e.g., "M 10 20 L 30 40 L 50 60")
    
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
            
            # Transform to SVG coordinates
            svg_x, svg_y = transform_point_to_svg(pt.X, pt.Y, anchor_point, canvas_height)
            
            command = "M" if i == 0 else "L"
            path_commands.append("{} {:.2f} {:.2f}".format(command, svg_x, svg_y))
        
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

def svg_circle(cx, cy, r, stroke="none", fill="none", stroke_width=0, 
               fill_opacity=None, stroke_opacity=None):
    """
    Generate SVG circle element string with Illustrator-compatible opacity.
    
    Args:
        cx (float): Center X coordinate (in SVG coordinates)
        cy (float): Center Y coordinate (in SVG coordinates)
        r (float): Radius
        stroke (str): Stroke color (RGB hex or color name)
        fill (str): Fill color (RGB hex or color name)
        stroke_width (float): Stroke width
        fill_opacity (float, optional): Fill opacity (0.0-1.0)
        stroke_opacity (float, optional): Stroke opacity (0.0-1.0)
    
    Returns:
        str: SVG circle element
    """
    if r <= 0:
        return ""
    
    attrs = [
        'cx="{}"'.format(cx),
        'cy="{}"'.format(cy),
        'r="{}"'.format(r),
        'fill="{}"'.format(fill),
        'stroke="{}"'.format(stroke),
        'stroke-width="{}"'.format(stroke_width)
    ]
    
    if fill_opacity is not None and fill_opacity < 1.0:
        attrs.append('fill-opacity="{:.2f}"'.format(fill_opacity))
    
    if stroke_opacity is not None and stroke_opacity < 1.0:
        attrs.append('stroke-opacity="{:.2f}"'.format(stroke_opacity))
    
    return '<circle {}/>'.format(" ".join(attrs))


def svg_polyline(points, stroke="none", fill="none", stroke_width=0, dash="",
                 fill_opacity=None, stroke_opacity=None):
    """
    Generate SVG polyline or polygon element string.
    
    Automatically detects if polyline is closed (first and last points match)
    and generates polygon element accordingly.
    
    Args:
        points (list): List of (x, y) coordinate tuples (in SVG coordinates)
        stroke (str): Stroke color (RGB hex or color name)
        fill (str): Fill color (RGB hex or color name)
        stroke_width (float): Stroke width
        dash (str): Stroke dash pattern
        fill_opacity (float, optional): Fill opacity (0.0-1.0)
        stroke_opacity (float, optional): Stroke opacity (0.0-1.0)
    
    Returns:
        str: SVG polyline or polygon element
    """
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
    
    attrs = [
        'points="{}"'.format(points_str),
        'fill="{}"'.format(fill),
        'stroke="{}"'.format(stroke),
        'stroke-width="{}"'.format(stroke_width)
    ]
    
    if dash and dash.strip():
        attrs.append('stroke-dasharray="{}"'.format(dash))
    
    if fill_opacity is not None and fill_opacity < 1.0:
        attrs.append('fill-opacity="{:.2f}"'.format(fill_opacity))
    
    if stroke_opacity is not None and stroke_opacity < 1.0:
        attrs.append('stroke-opacity="{:.2f}"'.format(stroke_opacity))
    
    return '<{} {}/>'.format(element_type, " ".join(attrs))


def svg_polygon(points, stroke="none", fill="none", stroke_width=0, dash="",
                fill_opacity=None, stroke_opacity=None):
    """
    Generate SVG polygon element (always closed).
    
    Args:
        points (list): List of (x, y) coordinate tuples (in SVG coordinates)
        stroke (str): Stroke color (RGB hex or color name)
        fill (str): Fill color (RGB hex or color name)
        stroke_width (float): Stroke width
        dash (str): Stroke dash pattern
        fill_opacity (float, optional): Fill opacity (0.0-1.0)
        stroke_opacity (float, optional): Stroke opacity (0.0-1.0)
    
    Returns:
        str: SVG polygon element
    """
    if not points or len(points) < 3:
        return ""
    
    points_str = " ".join(["{},{}".format(x, y) for x, y in points])
    
    attrs = [
        'points="{}"'.format(points_str),
        'fill="{}"'.format(fill),
        'stroke="{}"'.format(stroke),
        'stroke-width="{}"'.format(stroke_width)
    ]
    
    if dash and dash.strip():
        attrs.append('stroke-dasharray="{}"'.format(dash))
    
    if fill_opacity is not None and fill_opacity < 1.0:
        attrs.append('fill-opacity="{:.2f}"'.format(fill_opacity))
    
    if stroke_opacity is not None and stroke_opacity < 1.0:
        attrs.append('stroke-opacity="{:.2f}"'.format(stroke_opacity))
    
    return '<polygon {}/>'.format(" ".join(attrs))


def svg_path(path_data, stroke="none", fill="none", stroke_width=0, dash="",
             fill_opacity=None, stroke_opacity=None):
    """
    Generate SVG path element string with Illustrator-compatible opacity.
    
    Args:
        path_data (str): SVG path data (already transformed to SVG coordinates)
        stroke (str): Stroke color (RGB hex or color name)
        fill (str): Fill color (RGB hex or color name)
        stroke_width (float): Stroke width
        dash (str): Stroke dash pattern
        fill_opacity (float, optional): Fill opacity (0.0-1.0)
        stroke_opacity (float, optional): Stroke opacity (0.0-1.0)
    
    Returns:
        str: SVG path element
    """
    if not path_data or not path_data.strip():
        return ""
    
    attrs = [
        'd="{}"'.format(path_data),
        'fill="{}"'.format(fill),
        'stroke="{}"'.format(stroke),
        'stroke-width="{}"'.format(stroke_width)
    ]
    
    if dash and dash.strip():
        attrs.append('stroke-dasharray="{}"'.format(dash))
    
    if fill_opacity is not None and fill_opacity < 1.0:
        attrs.append('fill-opacity="{:.2f}"'.format(fill_opacity))
    
    if stroke_opacity is not None and stroke_opacity < 1.0:
        attrs.append('stroke-opacity="{:.2f}"'.format(stroke_opacity))
    
    return '<path {}/>'.format(" ".join(attrs))


def svg_text(x, y, text, font_family="Arial", font_size=12, fill="black",
            text_anchor="start", dominant_baseline="auto", fill_opacity=None):
    """
    Generate SVG text element with alignment and optional opacity.
    
    Args:
        x (float): X coordinate (in SVG coordinates)
        y (float): Y coordinate (in SVG coordinates)
        text (str): Text content
        font_family (str): Font family name
        font_size (int): Font size in pixels
        fill (str): Text color (RGB hex or color name)
        text_anchor (str): Horizontal alignment ("start", "middle", "end")
        dominant_baseline (str): Vertical alignment ("auto", "middle", "hanging")
        fill_opacity (float, optional): Text opacity (0.0-1.0)
    
    Returns:
        str: SVG text element
    """
    attrs = [
        'x="{}"'.format(x),
        'y="{}"'.format(y),
        'font-family="{}"'.format(font_family),
        'font-size="{}px"'.format(font_size),
        'fill="{}"'.format(fill),
        'text-anchor="{}"'.format(text_anchor),
        'dominant-baseline="{}"'.format(dominant_baseline)
    ]
    
    if fill_opacity is not None and fill_opacity < 1.0:
        attrs.append('fill-opacity="{:.2f}"'.format(fill_opacity))
    
    return '<text {}>{}</text>'.format(" ".join(attrs), text)


def svg_rect(x, y, width, height, fill="black", stroke="none", stroke_width=1,
             fill_opacity=None, stroke_opacity=None):
    """
    Generate SVG rectangle element with optional opacity.
    
    Args:
        x (float): Top-left X coordinate (in SVG coordinates)
        y (float): Top-left Y coordinate (in SVG coordinates)
        width (float): Rectangle width
        height (float): Rectangle height
        fill (str): Fill color (RGB hex or color name)
        stroke (str): Stroke color (RGB hex or color name)
        stroke_width (float): Stroke width
        fill_opacity (float, optional): Fill opacity (0.0-1.0)
        stroke_opacity (float, optional): Stroke opacity (0.0-1.0)
    
    Returns:
        str: SVG rectangle element
    """
    attrs = [
        'x="{}"'.format(x),
        'y="{}"'.format(y),
        'width="{}"'.format(width),
        'height="{}"'.format(height),
        'fill="{}"'.format(fill),
        'stroke="{}"'.format(stroke),
        'stroke-width="{}"'.format(stroke_width)
    ]
    
    if fill_opacity is not None and fill_opacity < 1.0:
        attrs.append('fill-opacity="{:.2f}"'.format(fill_opacity))
    
    if stroke_opacity is not None and stroke_opacity < 1.0:
        attrs.append('stroke-opacity="{:.2f}"'.format(stroke_opacity))
    
    return '<rect {}/>'.format(" ".join(attrs))
