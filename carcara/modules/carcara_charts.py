"""Carcara Charts - Chart Generation Utilities for Grasshopper

Common functions for creating chart components in Grasshopper.
Handles coordinate mapping, axes, labels, grids, and data processing.
Designed to work seamlessly with Rhino geometry and Grasshopper DataTrees.

Module Structure:
    1. Data Processing: Parse inputs, calculate ranges, handle margins
    2. Coordinate Mapping: Transform data to canvas coordinates
    3. Geometry Creation: Axes, grids, labels
    4. Utilities: Formatting, validation, helpers

Typical Usage:
    import carcara_charts as charts
    
    # Process data
    x_series = charts.parse_data_input(x)
    
    # Calculate ranges with margins
    x_min, x_max, x_range = charts.calculate_range_with_margin(x_data, margin=5)
    
    # Create coordinate mapper
    mapper = charts.CoordinateMapper(canvas, x_data, y_data, mx=5, my=5)
    
    # Create chart elements
    axes = charts.create_axes(canvas, extension=10)
    labels = charts.create_labels(x_values, canvas, axis='x', distance=10, decimals=1)

Functions:
    Data Processing:
        parse_data_input(data) -> list[list]
        calculate_range_with_margin(data, margin) -> (min, max, range)
        flatten_data_series(series_list) -> list
    
    Coordinate Mapping:
        CoordinateMapper class
        map_value_to_canvas(value, min_val, range_val, canvas_size) -> float
    
    Geometry Creation:
        create_axes(canvas, extension) -> [Line, Line]
        create_grid_lines(canvas, positions, axis) -> list[Line]
        create_labels(values, canvas, axis, distance, decimals) -> (points, texts)
    
    Utilities:
        format_number(value, decimals) -> str
        get_indexed_value(param_list, index, default) -> value
        validate_equal_lengths(x_data, y_data) -> bool
        generate_label_positions(min_val, max_val, num_labels) -> list

Version: 1.0
Date: 2025/11/14
Author: Carcara Team
"""

import Rhino.Geometry as rg
from Grasshopper import DataTree


###############################################################################
# DATA PROCESSING
###############################################################################

def parse_data_input(data):
    """
    Parse input as either flat list or DataTree.
    
    Handles:
        - DataTree (multiple series)
        - Nested lists [[1,2,3], [4,5,6]]
        - Flat lists [1,2,3,4]
        - None/empty inputs
    
    Args:
        data: Input data (DataTree, list, or nested list)
    
    Returns:
        list[list]: List of data series (each series is a list)
        Returns [[]] for empty/invalid input
    
    Example:
        >>> x_series = parse_data_input(x_input)
        >>> for series in x_series:
        ...     print(len(series))
    """
    if data is None:
        return []
    
    # Try DataTree
    try:
        if hasattr(data, 'BranchCount') and data.BranchCount > 0:
            series = []
            for i in range(data.BranchCount):
                branch = data.Branch(i)
                branch_data = [float(x) for x in branch if x is not None]
                if branch_data:
                    series.append(branch_data)
            return series
    except:
        pass
    
    # Try iterable
    try:
        if hasattr(data, '__iter__'):
            # Check for nested structure
            first_elem = None
            for elem in data:
                if elem is not None:
                    first_elem = elem
                    break
            
            if first_elem is not None and hasattr(first_elem, '__iter__') and not isinstance(first_elem, str):
                # Nested list
                series = []
                for sublist in data:
                    if hasattr(sublist, '__iter__'):
                        branch_data = [float(x) for x in sublist if x is not None]
                        if branch_data:
                            series.append(branch_data)
                return series
            else:
                # Flat list
                flat_data = [float(x) for x in data if x is not None]
                return [flat_data] if flat_data else []
    except:
        pass
    
    return []


def flatten_data_series(series_list):
    """
    Flatten list of data series into single list.
    
    Used for calculating global min/max across all series.
    
    Args:
        series_list (list[list]): List of data series
    
    Returns:
        list: Flattened list of all values
    
    Example:
        >>> series = [[1,2,3], [4,5,6]]
        >>> all_data = flatten_data_series(series)
        >>> print(all_data)  # [1,2,3,4,5,6]
    """
    flattened = []
    for series in series_list:
        flattened.extend(series)
    return flattened


def calculate_range_with_margin(data, margin_percent=0):
    """
    Calculate data range (min, max) with optional margin.
    
    Handles edge case where all values are the same.
    Margin is added to the lower bound only (for chart spacing from axis).
    
    Args:
        data (list): Data values
        margin_percent (float): Margin as percentage of range (default 0)
    
    Returns:
        tuple: (min_display, max_display, range_display)
            min_display: Minimum value for display (with margin)
            max_display: Maximum value for display
            range_display: Total display range
    
    Example:
        >>> data = [10, 20, 30, 40]
        >>> min_val, max_val, range_val = calculate_range_with_margin(data, margin=10)
        >>> print(min_val, max_val, range_val)  # 7.0, 40, 33.0
    """
    if not data:
        return 0, 1, 1
    
    data_min = min(data)
    data_max = max(data)
    
    # Handle case where all values are the same
    if data_min == data_max:
        data_min -= 0.5
        data_max += 0.5
    
    # Calculate range and apply margin
    data_range = data_max - data_min
    margin_value = margin_percent * data_range / 100.0
    
    min_display = data_min - margin_value
    max_display = data_max
    range_display = max_display - min_display
    
    return min_display, max_display, range_display


def generate_label_positions(min_val, max_val, num_labels):
    """
    Generate evenly spaced label positions between min and max.
    
    Args:
        min_val (float): Minimum value
        max_val (float): Maximum value
        num_labels (int): Number of labels TOTAL (including endpoints)
    
    Returns:
        list: List of label values
    
    Example:
        >>> positions = generate_label_positions(0, 100, 5)
        >>> print(positions)  # [0, 25, 50, 75, 100] - exactly 5 labels
    """
    if num_labels <= 0:
        return []
    if num_labels == 1:
        return [(min_val + max_val) / 2.0]
    
    # Divide by (num_labels - 1) to get correct spacing
    step = (max_val - min_val) / float(num_labels - 1)
    return [min_val + i * step for i in range(num_labels)]



###############################################################################
# COORDINATE MAPPING
###############################################################################

class CoordinateMapper:
    """
    Maps data coordinates to canvas coordinates with margin support.
    
    Handles both X and Y coordinate transformations.
    Stores canvas properties and data ranges for efficient mapping.
    
    Attributes:
        canvas_origin (Point3d): Canvas lower-left corner
        canvas_width (float): Canvas width
        canvas_height (float): Canvas height
        x_min, x_max, x_range (float): X data range with margins
        y_min, y_max, y_range (float): Y data range with margins
    
    Example:
        >>> mapper = CoordinateMapper(canvas, x_data, y_data, mx=5, my=5)
        >>> canvas_x = mapper.map_x(data_x_value)
        >>> canvas_y = mapper.map_y(data_y_value)
        >>> point = mapper.map_point(data_x, data_y)
    """
    
    def __init__(self, canvas, x_data, y_data, mx=0, my=0):
        """
        Initialize coordinate mapper.
        
        Args:
            canvas (Rectangle3d): Canvas rectangle
            x_data (list): X data values
            y_data (list): Y data values
            mx (float): X margin percentage (default 0)
            my (float): Y margin percentage (default 0)
        """
        self.canvas_origin = canvas.Corner(0)
        self.canvas_width = canvas.Width
        self.canvas_height = canvas.Height
        
        # Calculate ranges with margins
        self.x_min, self.x_max, self.x_range = calculate_range_with_margin(x_data, mx)
        self.y_min, self.y_max, self.y_range = calculate_range_with_margin(y_data, my)
    
    def map_x(self, x_value):
        """
        Map X data value to canvas X coordinate.
        
        Args:
            x_value (float): Data value
        
        Returns:
            float: Canvas X coordinate (relative to origin)
        """
        return ((x_value - self.x_min) / self.x_range) * self.canvas_width
    
    def map_y(self, y_value):
        """
        Map Y data value to canvas Y coordinate.
        
        Args:
            y_value (float): Data value
        
        Returns:
            float: Canvas Y coordinate (relative to origin)
        """
        return ((y_value - self.y_min) / self.y_range) * self.canvas_height
    
    def map_point(self, x_value, y_value):
        """
        Map data point to canvas Point3d.
        
        Args:
            x_value (float): X data value
            y_value (float): Y data value
        
        Returns:
            Point3d: Canvas point
        """
        x_canvas = self.map_x(x_value)
        y_canvas = self.map_y(y_value)
        
        return rg.Point3d(
            self.canvas_origin.X + x_canvas,
            self.canvas_origin.Y + y_canvas,
            self.canvas_origin.Z
        )
    
    def get_x_range_info(self):
        """Get X range information for labels."""
        return self.x_min, self.x_max, self.x_range
    
    def get_y_range_info(self):
        """Get Y range information for labels."""
        return self.y_min, self.y_max, self.y_range


def map_value_to_canvas(value, min_val, range_val, canvas_size):
    """
    Simple function to map single value to canvas coordinate.
    
    Args:
        value (float): Data value
        min_val (float): Minimum data value
        range_val (float): Data range
        canvas_size (float): Canvas dimension (width or height)
    
    Returns:
        float: Canvas coordinate (0 to canvas_size)
    
    Example:
        >>> x_canvas = map_value_to_canvas(50, 0, 100, 200)
        >>> print(x_canvas)  # 100.0
    """
    return ((value - min_val) / range_val) * canvas_size


###############################################################################
# GEOMETRY CREATION
###############################################################################

def create_axes(canvas, extension=0):
    """
    Create X and Y axis lines with optional extension.
    
    Extension is applied only at the end of each axis (right for X, top for Y).
    
    Args:
        canvas (Rectangle3d): Canvas rectangle
        extension (float): Length to extend axes beyond canvas (default 0)
    
    Returns:
        list: [x_axis_line, y_axis_line]
    
    Example:
        >>> axes = create_axes(canvas, extension=10)
        >>> x_axis, y_axis = axes
    """
    origin = canvas.Corner(0)
    width = canvas.Width
    height = canvas.Height
    
    # X-axis (horizontal)
    x_start = rg.Point3d(origin.X, origin.Y, origin.Z)
    x_end = rg.Point3d(origin.X + width + extension, origin.Y, origin.Z)
    x_axis = rg.Line(x_start, x_end)
    
    # Y-axis (vertical)
    y_start = rg.Point3d(origin.X, origin.Y, origin.Z)
    y_end = rg.Point3d(origin.X, origin.Y + height + extension, origin.Z)
    y_axis = rg.Line(y_start, y_end)
    
    return [x_axis, y_axis]


def create_grid_lines(canvas, positions, axis='x'):
    """
    Create grid lines at specified positions.
    
    Args:
        canvas (Rectangle3d): Canvas rectangle
        positions (list): List of positions along axis (0 to 1 normalized)
        axis (str): 'x' for vertical lines, 'y' for horizontal lines
    
    Returns:
        list: List of Line objects
    
    Example:
        >>> x_grid = create_grid_lines(canvas, [0, 0.25, 0.5, 0.75, 1], axis='x')
        >>> y_grid = create_grid_lines(canvas, [0, 0.5, 1], axis='y')
    """
    origin = canvas.Corner(0)
    width = canvas.Width
    height = canvas.Height
    
    lines = []
    
    if axis == 'x':
        # Vertical grid lines
        for pos in positions:
            x = origin.X + pos * width
            start = rg.Point3d(x, origin.Y, origin.Z)
            end = rg.Point3d(x, origin.Y + height, origin.Z)
            lines.append(rg.Line(start, end))
    
    elif axis == 'y':
        # Horizontal grid lines
        for pos in positions:
            y = origin.Y + pos * height
            start = rg.Point3d(origin.X, y, origin.Z)
            end = rg.Point3d(origin.X + width, y, origin.Z)
            lines.append(rg.Line(start, end))
    
    return lines


def create_labels(values, canvas, axis='x', distance=10, decimals=1):
    """
    Create label anchor points and text strings.
    
    Labels are positioned at specified distance from axes.
    X-axis labels: below axis (top-middle alignment)
    Y-axis labels: left of axis (right-middle alignment)
    
    Args:
        values (list): Data values for labels
        canvas (Rectangle3d): Canvas rectangle
        axis (str): 'x' or 'y' (default 'x')
        distance (float): Distance from axis (default 10)
        decimals (int): Decimal places for formatting (default 1)
    
    Returns:
        tuple: (points, texts)
            points: List of Point3d anchor points
            texts: List of formatted text strings
    
    Example:
        >>> x_pts, x_txt = create_labels([0, 50, 100], canvas, axis='x', distance=10, decimals=0)
        >>> y_pts, y_txt = create_labels([0, 25, 50], canvas, axis='y', distance=15, decimals=1)
    """
    origin = canvas.Corner(0)
    width = canvas.Width
    height = canvas.Height
    
    points = []
    texts = []
    format_str = "{{:.{}f}}".format(decimals)
    
    num_labels = len(values)
    
    if axis == 'x':
        # X-axis labels (below axis, top-middle alignment)
        for i, value in enumerate(values):
            x_pos = (i / float(num_labels - 1)) * width if num_labels > 1 else width / 2.0
            pt = rg.Point3d(origin.X + x_pos, origin.Y - distance, origin.Z)
            points.append(pt)
            texts.append(format_str.format(value))
    
    elif axis == 'y':
        # Y-axis labels (left of axis, right-middle alignment)
        for i, value in enumerate(values):
            y_pos = (i / float(num_labels - 1)) * height if num_labels > 1 else height / 2.0
            pt = rg.Point3d(origin.X - distance, origin.Y + y_pos, origin.Z)
            points.append(pt)
            texts.append(format_str.format(value))
    
    return points, texts


###############################################################################
# UTILITIES
###############################################################################

def format_number(value, decimals=1):
    """
    Format number with specified decimal places.
    
    Args:
        value (float): Number to format
        decimals (int): Number of decimal places (default 1)
    
    Returns:
        str: Formatted string
    
    Example:
        >>> format_number(3.14159, 2)
        '3.14'
    """
    format_str = "{{:.{}f}}".format(decimals)
    return format_str.format(value)


def get_indexed_value(param_list, index, default):
    """
    Get value from list or constant parameter.
    
    Handles:
        - Single constant value (returns same value for all indices)
        - List (returns indexed value with wraparound)
        - None (returns default)
    
    Args:
        param_list: Parameter value(s) - single value, list, or None
        index (int): Current item index
        default: Default value if parameter is None
    
    Returns:
        Value at index or default
    
    Example:
        >>> colors = ['red', 'blue', 'green']
        >>> color = get_indexed_value(colors, 5, 'black')  # Returns 'green' (wraparound)
        >>> size = get_indexed_value(10, 3, 5)  # Returns 10 (constant)
    """
    if param_list is None:
        return default
    
    # Single value
    if not hasattr(param_list, '__iter__') or isinstance(param_list, str):
        return param_list
    
    # List
    if index < len(param_list):
        return param_list[index] if param_list[index] is not None else default
    elif len(param_list) > 0:
        return param_list[-1] if param_list[-1] is not None else default
    else:
        return default


def validate_equal_lengths(*data_lists):
    """
    Validate that all data lists have equal length.
    
    Args:
        *data_lists: Variable number of data lists
    
    Returns:
        bool: True if all have same length, False otherwise
    
    Example:
        >>> x = [1, 2, 3]
        >>> y = [4, 5, 6]
        >>> z = [7, 8]
        >>> validate_equal_lengths(x, y)  # True
        >>> validate_equal_lengths(x, y, z)  # False
    """
    if not data_lists:
        return True
    
    first_len = len(data_lists[0])
    return all(len(data) == first_len for data in data_lists)


def create_default_canvas(width=100, height=100, origin=None):
    """
    Create default canvas rectangle.
    
    Args:
        width (float): Canvas width (default 100)
        height (float): Canvas height (default 100)
        origin (Point3d): Canvas origin (default (0,0,0))
    
    Returns:
        Rectangle3d: Canvas rectangle
    
    Example:
        >>> canvas = create_default_canvas(200, 150)
    """
    if origin is None:
        origin = rg.Point3d(0, 0, 0)
    
    plane = rg.Plane(origin, rg.Vector3d.ZAxis)
    return rg.Rectangle3d(plane, width, height)
    
###############################################################################
# COLOR MAPPING UTILITIES
###############################################################################

def map_value_to_color_gradient(value, min_val, max_val, color_list):
    """
    Map numeric value to color using provided color gradient.
    
    Interpolates between colors in the list based on normalized value.
    Preserves alpha channel from source colors.
    
    Args:
        value (float): Value to map
        min_val (float): Minimum value in dataset
        max_val (float): Maximum value in dataset
        color_list (list): List of System.Drawing.Color objects (min 2)
    
    Returns:
        tuple: (R, G, B, A) values as integers 0-255
    
    Example:
        >>> color = map_value_to_color_gradient(50, 0, 100, [blue, yellow, red])
    """
    if not color_list or len(color_list) < 2:
        return (128, 128, 128, 255)  # Grey with full opacity
    
    # Normalize value to 0-1
    if max_val == min_val:
        t = 0.5
    else:
        t = (value - min_val) / (max_val - min_val)
    
    # Clamp to 0-1
    t = max(0.0, min(1.0, t))
    
    # Find which color segment we're in
    num_segments = len(color_list) - 1
    segment = t * num_segments
    segment_index = int(segment)
    
    # Handle edge case (t = 1.0)
    if segment_index >= num_segments:
        segment_index = num_segments - 1
        local_t = 1.0
    else:
        local_t = segment - segment_index
    
    # Get colors to interpolate between
    color1 = color_list[segment_index]
    color2 = color_list[segment_index + 1]
    
    # Interpolate RGBA (including alpha)
    r = int(color1.R + (color2.R - color1.R) * local_t)
    g = int(color1.G + (color2.G - color1.G) * local_t)
    b = int(color1.B + (color2.B - color1.B) * local_t)
    a = int(color1.A + (color2.A - color1.A) * local_t)  # Interpolate alpha too
    
    return (r, g, b, a)



def validate_color_list(color_list):
    """
    Validate that color list is suitable for gradient.
    
    Args:
        color_list: List of colors to validate
    
    Returns:
        tuple: (is_valid, error_message)
    
    Example:
        >>> is_valid, msg = validate_color_list(colors)
        >>> if not is_valid:
        ...     print(msg)
    """
    if color_list is None:
        return False, "No colors provided"
    
    if not hasattr(color_list, '__iter__'):
        return False, "Colors must be a list"
    
    if len(color_list) < 2:
        return False, "At least 2 colors required for gradient"
    
    # Check if colors are valid
    for i, color in enumerate(color_list):
        if not hasattr(color, 'R') or not hasattr(color, 'G') or not hasattr(color, 'B'):
            return False, "Item {} is not a valid color object".format(i)
    
    return True, ""
    
def rgb_tuple_to_color(color_tuple):
    """
    Convert RGB or RGBA tuple to System.Drawing.Color.
    
    Args:
        color_tuple: (R, G, B) or (R, G, B, A) tuple with values 0-255
    
    Returns:
        System.Drawing.Color object
    
    Example:
        >>> color = rgb_tuple_to_color((255, 128, 0))
        >>> color_alpha = rgb_tuple_to_color((255, 128, 0, 128))
    """
    import System.Drawing
    
    if isinstance(color_tuple, tuple):
        if len(color_tuple) == 4:
            # RGBA tuple
            r, g, b, a = color_tuple
            return System.Drawing.Color.FromArgb(int(a), int(r), int(g), int(b))
        elif len(color_tuple) == 3:
            # RGB tuple (no alpha)
            r, g, b = color_tuple
            return System.Drawing.Color.FromArgb(int(r), int(g), int(b))
    
    return System.Drawing.Color.Black  # Fallback


###############################################################################
# HIGH-LEVEL CHART CREATION FUNCTIONS
###############################################################################

def create_histogram(canvas, values, bins=10, num_x_labels=None, num_y_labels=5,
                    decimals=1, extension=0, label_distance=10.0, grid_y=False):
    """
    Create complete histogram chart with all components.
    
    Single function that handles all histogram creation logic.
    Returns dictionary with all output geometry and metadata.
    
    Args:
        canvas (Rectangle3d): Canvas boundary
        values (list): Data values to histogram
        bins (int): Number of bins (default 10)
        num_x_labels (int): Number of X labels (default: all bin edges)
        num_y_labels (int): Number of Y labels (default 5)
        decimals (int): Label decimal places (default 1)
        extension (float): Axis extension (default 0)
        label_distance (float): Label distance from axis (default 10)
        grid_y (bool): Show Y grid lines (default False)
    
    Returns:
        dict: {
            'bars': [Rectangle3d],
            'axes': [Line, Line],
            'x_pts': [Point3d],
            'x_txt': [str],
            'y_pts': [Point3d],
            'y_txt': [str],
            'grid': [Line],
            'metadata': {
                'num_values': int,
                'num_bins': int,
                'data_range': (min, max),
                'max_count': int
            }
        }
    
    Example:
        >>> result = charts.create_histogram(canvas, data, bins=20, grid_y=True)
        >>> bars = result['bars']
        >>> axes = result['axes']
    """
    result = {
        'bars': [],
        'axes': [],
        'x_pts': [],
        'x_txt': [],
        'y_pts': [],
        'y_txt': [],
        'grid': [],
        'metadata': {}
    }
    
    # Validate input
    if not values:
        return result
    
    data_list = [float(x) for x in values if x is not None]
    if not data_list:
        return result
    
    # Canvas properties
    canvas_origin = canvas.Corner(0)
    canvas_width = canvas.Width
    canvas_height = canvas.Height
    
    # Calculate histogram
    bin_edges, counts = _calculate_histogram_bins(data_list, bins)
    if not counts:
        return result
    
    max_count = max(counts)
    bar_width = canvas_width / float(bins)
    
    # Create bars
    for i, count in enumerate(counts):
        if max_count > 0:
            bar_height = (count / float(max_count)) * canvas_height
        else:
            bar_height = 0
        
        bar = _create_bar_rectangle(i * bar_width, 0, bar_width, bar_height, canvas_origin)
        result['bars'].append(bar)
    
    # Create axes
    result['axes'] = create_axes(canvas, extension=extension)
    
    # X-axis labels
    if num_x_labels is None or num_x_labels <= 0:
        num_x_labels = len(bin_edges)
    
    if num_x_labels >= len(bin_edges):
        x_label_values = bin_edges
    else:
        step = (len(bin_edges) - 1) / float(num_x_labels - 1)
        indices = [int(round(i * step)) for i in range(num_x_labels)]
        x_label_values = [bin_edges[idx] for idx in indices if idx < len(bin_edges)]
    
    result['x_pts'], result['x_txt'] = create_labels(
        x_label_values, canvas, axis='x', distance=label_distance, decimals=decimals
    )
    
    # Y-axis labels
    if max_count > 0:
        y_label_values = generate_label_positions(0, max_count, num_y_labels)
        result['y_pts'], result['y_txt'] = create_labels(
            y_label_values, canvas, axis='y', distance=label_distance, decimals=decimals
        )
        
        # Grid lines
        if grid_y:
            grid_positions = [val / max_count for val in y_label_values]
            result['grid'] = create_grid_lines(canvas, grid_positions, axis='y')
    
    # Metadata
    result['metadata'] = {
        'num_values': len(data_list),
        'num_bins': bins,
        'data_range': (min(data_list), max(data_list)),
        'max_count': max_count
    }
    
    return result


def create_scatterplot(canvas, x_values, y_values, radii=2.0, num_x_labels=5,
                      num_y_labels=5, decimals=1, extension=0, label_distance=10.0,
                      margin_x=0, margin_y=0, grid_x=False, grid_y=False,
                      show_legend=False, color_values=None, color_gradient=None, 
                      num_legend_steps=5, legend_width=None, legend_label_distance=5.0,
                      legend_orientation='vertical', legend_distance=20.0):
    """
    Create complete scatter plot chart with all components.
    
    If show_legend=True, chart area is reduced to fit legend inside canvas.
    
    Args:
        canvas (Rectangle3d): Canvas boundary
        x_values (list): X coordinates
        y_values (list): Y coordinates
        radii (float or list): Dot radius/radii (default 2.0)
        num_x_labels (int): Number of X labels (default 5)
        num_y_labels (int): Number of Y labels (default 5)
        decimals (int): Label decimal places (default 1)
        extension (float): Axis extension (default 0)
        label_distance (float): Label distance from axis (default 10)
        margin_x (float): Left margin percentage (default 0)
        margin_y (float): Bottom margin percentage (default 0)
        grid_x (bool): Show X grid lines (default False)
        grid_y (bool): Show Y grid lines (default False)
        show_legend (bool): Generate color legend (default False)
        color_values (list): Values to map to colors (if None, uses y_values)
        color_gradient (list): Color gradient for legend (required if show_legend=True)
        num_legend_steps (int): Number of legend steps (default 5)
        legend_width (float): Legend bar width (default 5% of available space)
        legend_label_distance (float): Distance from legend to labels (default 5)
        legend_orientation (str): 'vertical' or 'horizontal' (default 'vertical')
        legend_distance (float): Distance from chart to legend (default 20)
    
    Returns:
        dict: {
            'dots': [Circle],
            'colors': [Color],
            'axes': [Line, Line],
            'x_pts': [Point3d],
            'x_txt': [str],
            'y_pts': [Point3d],
            'y_txt': [str],
            'grid_x': [Line],
            'grid_y': [Line],
            'legend_cells': [Rectangle3d],
            'legend_colors': [Color],
            'legend_pts': [Point3d],
            'legend_txt': [str],
            'metadata': {...}
        }
    """
    
    result = {
        'dots': [],
        'colors': [],
        'axes': [],
        'x_pts': [],
        'x_txt': [],
        'y_pts': [],
        'y_txt': [],
        'grid_x': [],
        'grid_y': [],
        'legend_cells': [],
        'legend_colors': [],
        'legend_pts': [],
        'legend_txt': [],
        'metadata': {}
    }
    
    # Validate input
    if not x_values or not y_values:
        return result
    
    x_data = [float(x) for x in x_values if x is not None]
    y_data = [float(y) for y in y_values if y is not None]
    
    if not x_data or not y_data or len(x_data) != len(y_data):
        return result
    
    # Check if colors should be generated (independent of legend display)
    generate_colors = color_gradient is not None
    if generate_colors:
        is_valid, error_msg = validate_color_list(color_gradient)
        if not is_valid:
            generate_colors = False
    
    # If legend requested, validate it separately
    show_legend_validated = show_legend and generate_colors
    
    # Determine which values to use for coloring
    if generate_colors:
        if color_values is not None:
            # Use provided color values
            color_data = [float(v) for v in color_values if v is not None]
            if len(color_data) != len(x_data):
                # Mismatch - disable coloring
                generate_colors = False
                show_legend_validated = False
                color_min, color_max = 0, 1
            else:
                color_min = min(color_data)
                color_max = max(color_data)
                if color_min == color_max:
                    color_min -= 0.5
                    color_max += 0.5
        else:
            # Use Y values for coloring (default behavior)
            color_data = y_data
            color_min = min(y_data)
            color_max = max(y_data)
            if color_min == color_max:
                color_min -= 0.5
                color_max += 0.5
    else:
        color_data = y_data
        color_min = min(y_data)
        color_max = max(y_data)
    
    # Canvas properties
    canvas_origin_point = canvas.Corner(0)
    canvas_full_width = canvas.Width
    canvas_full_height = canvas.Height
    
    # Calculate available space for chart (reserve space for legend if needed)
    if show_legend_validated:
        # Set default legend width
        if legend_width is None:
            legend_width = canvas_full_width * 0.05 if legend_orientation == 'vertical' else canvas_full_height * 0.05
        
        if legend_orientation == 'vertical':
            # Reserve space on RIGHT
            legend_space = legend_distance + legend_width + legend_label_distance + 50  # +50 for text
            chart_canvas_width = canvas_full_width - legend_space
            chart_canvas_height = canvas_full_height
        else:
            # Reserve space on BOTTOM
            legend_space = legend_distance + legend_width + legend_label_distance + 20  # +20 for text
            chart_canvas_width = canvas_full_width
            chart_canvas_height = canvas_full_height - legend_space
    else:
        # No legend - use full canvas
        chart_canvas_width = canvas_full_width
        chart_canvas_height = canvas_full_height
    
    # Create a "virtual" canvas for the chart area
    chart_canvas = rg.Rectangle3d(
        rg.Plane(canvas_origin_point, rg.Vector3d.ZAxis),
        chart_canvas_width,
        chart_canvas_height
    )
    
    # Create coordinate mapper using chart canvas
    mapper = CoordinateMapper(chart_canvas, x_data, y_data, mx=margin_x, my=margin_y)
    
    # Create dots (and optionally assign colors)
    for i, (x_val, y_val) in enumerate(zip(x_data, y_data)):
        pt = mapper.map_point(x_val, y_val)
        radius = get_indexed_value(radii, i, 2.0)
        
        plane = rg.Plane(pt, rg.Vector3d.ZAxis)
        circle = rg.Circle(plane, radius)
        result['dots'].append(circle)
        
        # Generate colors if gradient provided (regardless of legend display)
        if generate_colors:
            color_val = color_data[i]
            color_tuple = map_value_to_color_gradient(color_val, color_min, color_max, color_gradient)
            color = rgb_tuple_to_color(color_tuple)
            result['colors'].append(color)
    
    # Create axes (using chart canvas)
    result['axes'] = create_axes(chart_canvas, extension=extension)
    
    # Get range info from mapper
    x_min, x_max, x_range = mapper.get_x_range_info()
    y_min, y_max, y_range = mapper.get_y_range_info()
    
    # X-axis labels (using chart canvas)
    x_label_values = generate_label_positions(x_min, x_max, num_x_labels)
    result['x_pts'], result['x_txt'] = create_labels(
        x_label_values, chart_canvas, axis='x', distance=label_distance, decimals=decimals
    )
    
    if grid_x:
        x_positions = [(val - x_min) / x_range for val in x_label_values]
        result['grid_x'] = create_grid_lines(chart_canvas, x_positions, axis='x')
    
    # Y-axis labels (using chart canvas)
    y_label_values = generate_label_positions(y_min, y_max, num_y_labels)
    result['y_pts'], result['y_txt'] = create_labels(
        y_label_values, chart_canvas, axis='y', distance=label_distance, decimals=decimals
    )
    
    if grid_y:
        y_positions = [(val - y_min) / y_range for val in y_label_values]
        result['grid_y'] = create_grid_lines(chart_canvas, y_positions, axis='y')
    
    # Generate legend in reserved space (only if show_legend is True)
    if show_legend_validated:
        # Generate legend values based on color data range
        legend_values = generate_label_positions(color_min, color_max, num_legend_steps)
        
        if legend_orientation == 'vertical':
            # Vertical legend (to the RIGHT of chart area, within canvas)
            legend_x = canvas_origin_point.X + chart_canvas_width + legend_distance
            legend_height_per_step = chart_canvas_height / float(num_legend_steps)
            
            for i in range(num_legend_steps):
                y = canvas_origin_point.Y + i * legend_height_per_step
                
                # Create legend cell
                corner = rg.Point3d(legend_x, y, canvas_origin_point.Z)
                plane = rg.Plane(corner, rg.Vector3d.ZAxis)
                legend_cell = rg.Rectangle3d(plane, legend_width, legend_height_per_step)
                result['legend_cells'].append(legend_cell)
                
                # Get value, color, and create label
                value = legend_values[i]
                color_tuple = map_value_to_color_gradient(value, color_min, color_max, color_gradient)
                color = rgb_tuple_to_color(color_tuple)
                result['legend_colors'].append(color)
                
                # Label position
                label_x = legend_x + legend_width + legend_label_distance
                label_y = y + legend_height_per_step / 2.0
                label_pt = rg.Point3d(label_x, label_y, canvas_origin_point.Z)
                result['legend_pts'].append(label_pt)
                result['legend_txt'].append(format_number(value, decimals))
        
        else:
            # Horizontal legend (BELOW chart area, within canvas)
            legend_y = canvas_origin_point.Y + chart_canvas_height + legend_distance
            legend_width_per_step = chart_canvas_width / float(num_legend_steps)
            
            for i in range(num_legend_steps):
                x = canvas_origin_point.X + i * legend_width_per_step
                
                # Create legend cell
                corner = rg.Point3d(x, legend_y, canvas_origin_point.Z)
                plane = rg.Plane(corner, rg.Vector3d.ZAxis)
                legend_cell = rg.Rectangle3d(plane, legend_width_per_step, legend_width)
                result['legend_cells'].append(legend_cell)
                
                # Get value, color, and create label
                value = legend_values[i]
                color_tuple = map_value_to_color_gradient(value, color_min, color_max, color_gradient)
                color = rgb_tuple_to_color(color_tuple)
                result['legend_colors'].append(color)
                
                # Label position
                label_x = x + legend_width_per_step / 2.0
                label_y = legend_y + legend_width + legend_label_distance
                label_pt = rg.Point3d(label_x, label_y, canvas_origin_point.Z)
                result['legend_pts'].append(label_pt)
                result['legend_txt'].append(format_number(value, decimals))
    
    # Metadata
    result['metadata'] = {
        'num_points': len(x_data),
        'x_range': (x_min, x_max),
        'y_range': (y_min, y_max),
        'has_legend': show_legend_validated,
        'has_colors': generate_colors,
        'color_range': (color_min, color_max) if generate_colors else None,
        'chart_area': (chart_canvas_width, chart_canvas_height),
        'canvas_area': (canvas_full_width, canvas_full_height)
    }
    
    return result






def create_lineplot(canvas, x_series, y_series, num_x_labels=5, num_y_labels=5,
                   decimals=1, extension=0, label_distance=10.0, margin_x=0,
                   margin_y=0, grid_x=False, grid_y=False):
    """
    Create complete line plot chart with all components.
    
    Supports multiple series via lists of lists or DataTree.
    
    Args:
        canvas (Rectangle3d): Canvas boundary
        x_series (list or DataTree): X coordinates (one series per branch)
        y_series (list or DataTree): Y coordinates (one series per branch)
        num_x_labels (int): Number of X labels (default 5)
        num_y_labels (int): Number of Y labels (default 5)
        decimals (int): Label decimal places (default 1)
        extension (float): Axis extension (default 0)
        label_distance (float): Label distance from axis (default 10)
        margin_x (float): Left margin percentage (default 0)
        margin_y (float): Bottom margin percentage (default 0)
        grid_x (bool): Show X grid lines (default False)
        grid_y (bool): Show Y grid lines (default False)
    
    Returns:
        dict: {
            'lines': [Polyline],
            'axes': [Line, Line],
            'x_pts': [Point3d],
            'x_txt': [str],
            'y_pts': [Point3d],
            'y_txt': [str],
            'grid_x': [Line],
            'grid_y': [Line],
            'metadata': {...}
        }
    """
    result = {
        'lines': [],
        'axes': [],
        'x_pts': [],
        'x_txt': [],
        'y_pts': [],
        'y_txt': [],
        'grid_x': [],
        'grid_y': [],
        'metadata': {}
    }
    
    # Parse inputs
    x_data_series = parse_data_input(x_series)
    y_data_series = parse_data_input(y_series)
    
    if not x_data_series or not y_data_series or len(x_data_series) != len(y_data_series):
        return result
    
    # Validate series
    valid_series = []
    for x_data, y_data in zip(x_data_series, y_data_series):
        if len(x_data) == len(y_data) and len(x_data) >= 2:
            valid_series.append((x_data, y_data))
    
    if not valid_series:
        return result
    
    # Flatten all data for global range
    all_x = flatten_data_series([x for x, y in valid_series])
    all_y = flatten_data_series([y for x, y in valid_series])
    
    # Create coordinate mapper with margins
    mapper = CoordinateMapper(canvas, all_x, all_y, mx=margin_x, my=margin_y)
    
    # Create lines
    for x_data, y_data in valid_series:
        points = [mapper.map_point(x_val, y_val) for x_val, y_val in zip(x_data, y_data)]
        if len(points) >= 2:
            polyline = rg.Polyline(points)
            result['lines'].append(polyline)
    
    # Create axes
    result['axes'] = create_axes(canvas, extension=extension)
    
    # Get range info
    x_min, x_max, x_range = mapper.get_x_range_info()
    y_min, y_max, y_range = mapper.get_y_range_info()
    
    # X-axis labels
    x_label_values = generate_label_positions(x_min, x_max, num_x_labels)
    result['x_pts'], result['x_txt'] = create_labels(
        x_label_values, canvas, axis='x', distance=label_distance, decimals=decimals
    )
    
    if grid_x:
        x_positions = [(val - x_min) / x_range for val in x_label_values]
        result['grid_x'] = create_grid_lines(canvas, x_positions, axis='x')
    
    # Y-axis labels
    y_label_values = generate_label_positions(y_min, y_max, num_y_labels)
    result['y_pts'], result['y_txt'] = create_labels(
        y_label_values, canvas, axis='y', distance=label_distance, decimals=decimals
    )
    
    if grid_y:
        y_positions = [(val - y_min) / y_range for val in y_label_values]
        result['grid_y'] = create_grid_lines(canvas, y_positions, axis='y')
    
    # Metadata
    result['metadata'] = {
        'num_series': len(valid_series),
        'x_range': (x_min, x_max),
        'y_range': (y_min, y_max)
    }
    
    return result

def create_heatmap(canvas, data_matrix, color_gradient, row_labels=None, 
                  col_labels=None, show_values=False, decimals=1,
                  num_legend_steps=5, label_distance=10.0, 
                  legend_width=None, legend_label_distance=5.0,
                  legend_orientation='vertical', legend_distance=20.0,
                  show_legend=True):
    """
    Create complete heatmap chart with all components.
    
    Visualizes 2D matrix data as colored grid using custom color gradient.
    If show_legend=True, chart area is reduced to fit legend inside canvas.
    
    Args:
        canvas (Rectangle3d): Canvas boundary
        data_matrix (list[list]): 2D matrix of values (rows × columns)
        color_gradient (list): List of System.Drawing.Color objects (min 2)
        row_labels (list[str]): Labels for rows/Y-axis (optional)
        col_labels (list[str]): Labels for columns/X-axis (optional)
        show_values (bool): Show numeric values in cells (default False)
        decimals (int): Decimal places for values (default 1)
        num_legend_steps (int): Number of color legend steps (default 5)
        label_distance (float): Distance from canvas for row/col labels (default 10)
        legend_width (float): Width of legend bar (default 5% of available space)
        legend_label_distance (float): Distance from legend to labels (default 5)
        legend_orientation (str): 'vertical' or 'horizontal' (default 'vertical')
        legend_distance (float): Distance from chart to legend (default 20)
        show_legend (bool): Include legend in canvas (default True)
    
    Returns:
        dict: {
            'cells': [Rectangle3d],
            'colors': [Color],
            'row_pts': [Point3d],
            'row_txt': [str],
            'col_pts': [Point3d],
            'col_txt': [str],
            'value_pts': [Point3d],
            'value_txt': [str],
            'legend_cells': [Rectangle3d],
            'legend_colors': [Color],
            'legend_pts': [Point3d],
            'legend_txt': [str],
            'metadata': {...}
        }
    """
    result = {
        'cells': [],
        'colors': [],
        'row_pts': [],
        'row_txt': [],
        'col_pts': [],
        'col_txt': [],
        'value_pts': [],
        'value_txt': [],
        'legend_cells': [],
        'legend_colors': [],
        'legend_pts': [],
        'legend_txt': [],
        'metadata': {}
    }
    
    # Validate color gradient
    is_valid, error_msg = validate_color_list(color_gradient)
    if not is_valid:
        return result
    
    # Validate data matrix
    if not data_matrix or not data_matrix[0]:
        return result
    
    # Convert to numeric matrix
    try:
        numeric_matrix = []
        for row in data_matrix:
            numeric_row = [float(val) if val is not None else 0.0 for val in row]
            numeric_matrix.append(numeric_row)
    except:
        return result
    
    num_rows = len(numeric_matrix)
    num_cols = len(numeric_matrix[0])
    
    # Validate all rows have same length
    if not all(len(row) == num_cols for row in numeric_matrix):
        return result
    
    # Canvas properties
    canvas_origin = canvas.Corner(0)
    canvas_full_width = canvas.Width
    canvas_full_height = canvas.Height
    
    # Calculate available space for heatmap chart (reserve space for legend if needed)
    if show_legend:
        # Set default legend width based on orientation
        if legend_width is None:
            legend_width = canvas_full_width * 0.05 if legend_orientation == 'vertical' else canvas_full_height * 0.05
        
        if legend_orientation == 'vertical':
            # Reserve space on RIGHT side for legend
            legend_space = legend_distance + legend_width + legend_label_distance + 50  # +50 for text width
            chart_width = canvas_full_width - legend_space
            chart_height = canvas_full_height
        else:
            # Reserve space on BOTTOM for legend
            legend_space = legend_distance + legend_width + legend_label_distance + 20  # +20 for text height
            chart_width = canvas_full_width
            chart_height = canvas_full_height - legend_space
    else:
        # No legend - use full canvas
        chart_width = canvas_full_width
        chart_height = canvas_full_height
    
    # Calculate cell dimensions based on available chart area
    cell_width = chart_width / float(num_cols)
    cell_height = chart_height / float(num_rows)
    
    # Find min/max values for color mapping
    all_values = [val for row in numeric_matrix for val in row]
    min_val = min(all_values)
    max_val = max(all_values)
    
    # Create cells and colors
    for i, row in enumerate(numeric_matrix):
        # Row index from top (reversed for proper display)
        row_idx = num_rows - 1 - i
        
        for j, value in enumerate(row):
            # Calculate cell position
            x = canvas_origin.X + j * cell_width
            y = canvas_origin.Y + row_idx * cell_height
            
            # Create rectangle
            corner = rg.Point3d(x, y, canvas_origin.Z)
            plane = rg.Plane(corner, rg.Vector3d.ZAxis)
            cell = rg.Rectangle3d(plane, cell_width, cell_height)
            result['cells'].append(cell)
            
            # Map value to color using gradient
            color = map_value_to_color_gradient(value, min_val, max_val, color_gradient)
            result['colors'].append(color)
            
            # Optional: show values in cells
            if show_values:
                center_x = x + cell_width / 2.0
                center_y = y + cell_height / 2.0
                center_pt = rg.Point3d(center_x, center_y, canvas_origin.Z)
                result['value_pts'].append(center_pt)
                result['value_txt'].append(format_number(value, decimals))
    
    # Row labels (Y-axis) - positioned relative to chart area
    if row_labels and len(row_labels) == num_rows:
        for i, label in enumerate(row_labels):
            row_idx = num_rows - 1 - i  # Reversed
            y_center = canvas_origin.Y + (row_idx + 0.5) * cell_height
            pt = rg.Point3d(canvas_origin.X - label_distance, y_center, canvas_origin.Z)
            result['row_pts'].append(pt)
            result['row_txt'].append(str(label))
    
    # Column labels (X-axis) - positioned relative to chart area
    if col_labels and len(col_labels) == num_cols:
        for j, label in enumerate(col_labels):
            x_center = canvas_origin.X + (j + 0.5) * cell_width
            pt = rg.Point3d(x_center, canvas_origin.Y - label_distance, canvas_origin.Z)
            result['col_pts'].append(pt)
            result['col_txt'].append(str(label))
    
    # Generate legend if requested (positioned in reserved space within canvas)
    if show_legend:
        # Generate legend values
        legend_values = generate_label_positions(min_val, max_val, num_legend_steps)
        
        if legend_orientation == 'vertical':
            # Vertical legend (to the right of chart area, within canvas)
            legend_x = canvas_origin.X + chart_width + legend_distance
            legend_height_per_step = chart_height / float(num_legend_steps)
            
            for i in range(num_legend_steps):
                y = canvas_origin.Y + i * legend_height_per_step
                
                # Create legend cell
                corner = rg.Point3d(legend_x, y, canvas_origin.Z)
                plane = rg.Plane(corner, rg.Vector3d.ZAxis)
                legend_cell = rg.Rectangle3d(plane, legend_width, legend_height_per_step)
                result['legend_cells'].append(legend_cell)
                
                # Get value, color, and create label
                value = legend_values[i]
                color = map_value_to_color_gradient(value, min_val, max_val, color_gradient)
                result['legend_colors'].append(color)
                
                # Label position
                label_x = legend_x + legend_width + legend_label_distance
                label_y = y + legend_height_per_step / 2.0
                label_pt = rg.Point3d(label_x, label_y, canvas_origin.Z)
                result['legend_pts'].append(label_pt)
                result['legend_txt'].append(format_number(value, decimals))
        
        else:
            # Horizontal legend (below chart area, within canvas)
            legend_y = canvas_origin.Y + chart_height + legend_distance
            legend_width_per_step = chart_width / float(num_legend_steps)
            
            for i in range(num_legend_steps):
                x = canvas_origin.X + i * legend_width_per_step
                
                # Create legend cell
                corner = rg.Point3d(x, legend_y, canvas_origin.Z)
                plane = rg.Plane(corner, rg.Vector3d.ZAxis)
                legend_cell = rg.Rectangle3d(plane, legend_width_per_step, legend_width)
                result['legend_cells'].append(legend_cell)
                
                # Get value, color, and create label
                value = legend_values[i]
                color = map_value_to_color_gradient(value, min_val, max_val, color_gradient)
                result['legend_colors'].append(color)
                
                # Label position
                label_x = x + legend_width_per_step / 2.0
                label_y = legend_y + legend_width + legend_label_distance
                label_pt = rg.Point3d(label_x, label_y, canvas_origin.Z)
                result['legend_pts'].append(label_pt)
                result['legend_txt'].append(format_number(value, decimals))
    
    # Metadata
    result['metadata'] = {
        'num_rows': num_rows,
        'num_cols': num_cols,
        'value_range': (min_val, max_val),
        'num_colors': len(color_gradient),
        'legend_orientation': legend_orientation,
        'chart_area': (chart_width, chart_height),
        'canvas_area': (canvas_full_width, canvas_full_height),
        'has_legend': show_legend
    }
    
    # Convert RGB tuples to Color objects before returning
    result['colors'] = [rgb_tuple_to_color(c) for c in result['colors']]
    result['legend_colors'] = [rgb_tuple_to_color(c) for c in result['legend_colors']]
    
    return result






###############################################################################
# PRIVATE HELPER FUNCTIONS (for high-level functions)
###############################################################################

def _calculate_histogram_bins(data, num_bins):
    """Calculate histogram bins and counts (internal)."""
    if not data or num_bins <= 0:
        return [], []
    
    data_min = min(data)
    data_max = max(data)
    
    if data_min == data_max:
        return [data_min, data_max], [len(data)]
    
    bin_width = (data_max - data_min) / float(num_bins)
    bin_edges = [data_min + i * bin_width for i in range(num_bins + 1)]
    
    counts = [0] * num_bins
    for value in data:
        bin_index = int((value - data_min) / bin_width)
        if bin_index >= num_bins:
            bin_index = num_bins - 1
        counts[bin_index] += 1
    
    return bin_edges, counts


def _create_bar_rectangle(x, y, width, height, origin):
    """Create histogram bar rectangle (internal)."""
    corner = rg.Point3d(origin.X + x, origin.Y + y, origin.Z)
    plane = rg.Plane(corner, rg.Vector3d.ZAxis)
    return rg.Rectangle3d(plane, width, height)



###############################################################################
# MODULE INFO
###############################################################################

__version__ = "1.0"
__date__ = "2025/11/14"
__author__ = "Eugenio Moreira"

# Export main classes and functions
__all__ = [
    # Data Processing
    'parse_data_input',
    'flatten_data_series',
    'calculate_range_with_margin',
    'generate_label_positions',
    
    # Coordinate Mapping
    'CoordinateMapper',
    'map_value_to_canvas',
    
    # Geometry Creation
    'create_axes',
    'create_grid_lines',
    'create_labels',
    
    # Utilities
    'format_number',
    'get_indexed_value',
    'validate_equal_lengths',
    'create_default_canvas',
]
