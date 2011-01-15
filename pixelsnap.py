#!/usr/bin/env python

"""
--------------------- LICENSE ---------------------
Copyright (c) 2009 Bryan Hoyt

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
---------------------------------------------------


--------------------- HELP ---------------------
1. Assuming the extension is properly installed, use it like this:
  1. Load up Inksape, and start editing some objects
  2. Select the objects you want to be pixel-perfect
  3. Go to the menu Extensions->Modify Path->PixelSnap
  4. Click "Apply"
  5. Rinse & repeat for any other objects you want to snap.

2. To install, simply copy pixelsnap.py (this file) and pixelsnap.inx into
    your inkscape extensions directory. However, if you have Inkscape 0.47
    or more recent, it should already be installed.

    The exact folder may be different on your system, but it's likely to be:
      Linux: ~/.config/inkscape/extensions/
      Windows: C:\Documents and Settings\<UserName>\Application Data\Inkscape\extensions\

3. If you use a Mac/MacPorts, and get an error about lxml, it may be the problem
discussed here on the PixelSnap email discussion group:
http://groups.google.com/group/pixelsnap-users/browse_thread/thread/ef3d642b5b47876

4. To add a keyboard shortcut, edit the keybindings file:
     Linux: ~/.config/inkscape/keys/default.xml
     Windows: C:\Documents and Settings\<UserName>\Application Data\Inkscape\keys\default.xml
   or create it if it doesn't exist. The complete file should like something like
   below (it may contain other keybindings). To bind PixelSnap to the shortcut
   Shift-X, add the 2 lines between the horizontal rules:

   <?xml version="1.0"?>
   <keys name="Inkscape default">
    <!-- --------------------------------- -->
    <bind key="x" modifiers="Shift" action="bryhoyt.pixelsnap" display="true"/>
    <bind key="X" modifiers="Shift" action="bryhoyt.pixelsnap" />
    <!-- --------------------------------- -->
   </keys>

---------------------------------------------------

TODO: mark elements that have previously been snapped, along with the settings
    used, so that the same settings can be used for that element next time when
    it's selected as part of a group (and add an option to the extension dialog
    "Use previous/default settings" which is selected by default)

TODO: make elem_offset return [x_offset, y_offset] so we can handle non-symetric scaling
      => will probably need to take into account non-symetric scaling on stroke-widths,
         too (horizontal vs vertical strokes)

TODO: Transforming points isn't quite perfect, to say the least. In particular,
    when translating a point on a bezier curve, we translate the handles by the same amount.
    BUT, some handles that are attached to a particular point are conceptually
    handles of the prev/next node.
    Best way to fix it would be to keep a list of the fractional_offsets[] of
    each point, without transforming anything. Then go thru each point and
    transform the appropriate handle according to the relevant fraction_offset
    in the list.
    
    i.e. calculate first, then modify.
    
    In fact, that might be a simpler algorithm anyway -- it avoids having
    to keep track of all the first_xy/next_xy guff.

Note: This doesn't work very well on paths which have both straight segments
      and curved segments.
      The biggest three problems are:
        a) we don't take handles into account (segments where the nodes are
           aligned are always treated as straight segments, even where the
           handles make it curve)
        b) when we snap a straight segment right before/after a curve, it
           doesn't make any attempt to keep the transition from the straight
           segment to the curve smooth.
        c) no attempt is made to keep equal widths equal. (or nearly-equal
           widths nearly-equal). For example, font strokes.

Note: Paths that have curves & arcs on some sides of the bounding box won't
    be snapped correctly on that side of the bounding box, and nor will they
    be translated/resized correctly before the path is modified. Doesn't affect
    most applications of this extension, but it highlights the fact that we
    take a geometrically simplistic approach to inspecting & modifying the path.
"""

from __future__ import division

import sys

# *** numpy causes issue #4 on Mac OS 10.6.2. I use it for
# matrix inverse -- my linear algebra's a bit rusty, but I could implement my
# own matrix inverse function if necessary, I guess.
from numpy import matrix
import simplestyle, simpletransform, simplepath

# INKEX MODULE
# If you get the "No module named inkex" error, uncomment the relevant line
# below by removing the '#' at the start of the line.
#
#sys.path += ['/usr/share/inkscape/extensions']                     # If you're using a standard Linux installation
#sys.path += ['/usr/local/share/inkscape/extensions']               # If you're using a custom Linux installation
#sys.path += ['C:\\Program Files\\Inkscape\\share\\extensions']     # If you're using a standard Windows installation

try:
    import inkex
    from inkex import unittouu
except ImportError:
    raise ImportError("No module named inkex.\nPlease edit the file %s and see the section titled 'INKEX MODULE'" % __file__)

Precision = 5                   # number of digits of precision for comparing float numbers

class TransformError(Exception): pass

def elemtype(elem, matches):
    if not isinstance(matches, (list, tuple)): matches = [matches]
    for m in matches:
        if elem.tag == inkex.addNS(m, 'svg'): return True
    return False

def invert_transform(transform):
    transform = transform[:]    # duplicate list to avoid modifying it
    transform += [[0, 0, 1]]
    inverse = matrix(transform).I.tolist()
    inverse.pop()
    return inverse

def transform_point(transform, pt, inverse=False):
    """ Better than simpletransform.applyTransformToPoint,
        a) it's a simpler name
        b) it returns the new xy, rather than modifying the input
    """
    if inverse:
        transform = invert_transform(transform)
    
    x = transform[0][0]*pt[0] + transform[0][1]*pt[1] + transform[0][2]
    y = transform[1][0]*pt[0] + transform[1][1]*pt[1] + transform[1][2]
    return x,y

def transform_dimensions(transform, width=None, height=None, inverse=False):
    """ Dimensions don't get translated. I'm not sure how much diff rotate/skew
        makes in this context, but we currently ignore anything besides scale.
    """
    if inverse: transform = invert_transform(transform)

    if width is not None: width *= transform[0][0]
    if height is not None: height *= transform[1][1]
    
    if width is not None and height is not None: return width, height
    if width is not None: return width
    if height is not None: return height


class PixelSnapEffect(inkex.Effect):
    def __init__(self):
        inkex.Effect.__init__(self)
        opts = [('-a', 'inkbool', 'snap_ancestors', True,
                 "Snap unselected ancestors' translations (groups, layers, document height) first"),
                ('-t', 'inkbool', 'ancestor_offset', True,
                 "Calculate offset relative to unselected ancestors' transforms (includes document height offset)"),
                ('-s', 'string', 'modify_shapes', 'size_only',
                 "Modify shapes, size, and positions (valid options: size_only, shape_and_size, position_only)"),
                ('-g', 'float', 'max_gradient', 0.5,
                 "Maximum slope to consider straight (%)"),
                ]
        for o in opts:
            self.OptionParser.add_option(o[0], '--'+o[2], action="store", type=o[1],
                                         dest=o[2], default=o[3], help=o[4])

    def vertical(self, pt1, pt2):
        hlen = abs(pt1[0] - pt2[0])
        vlen = abs(pt1[1] - pt2[1])
        if vlen==0 and hlen==0:
            return True
        elif vlen==0:
            return False
        return (hlen / vlen) < self.options.max_gradient/100

    def horizontal(self, pt1, pt2):
        hlen = round(abs(pt1[0] - pt2[0]), Precision)
        vlen = round(abs(pt1[1] - pt2[1]), Precision)
        if hlen==0 and vlen==0:
            return True
        elif hlen==0:
            return False
        return (vlen / hlen) < self.options.max_gradient/100


    def stroke_width_offset(self, elem, parent_transform=None):
        """ Returns the amount the bounding-box is offset due to the stroke-width.
            Transform is taken into account.
        """
        stroke_width = self.stroke_width(elem)
        if stroke_width == 0: return 0                                          # if there's no stroke, no need to worry about the transform

        transform = self.get_transform(elem, parent_transform=parent_transform)
        if abs(abs(transform[0][0]) - abs(transform[1][1])) > (10**-Precision):
            raise TransformError("Selection contains non-symetric scaling")     # *** wouldn't be hard to get around this by calculating vertical_offset & horizontal_offset separately, maybe 2 functions, or maybe returning a tuple

        stroke_width = transform_dimensions(transform, width=stroke_width)

        return (stroke_width/2)

    def stroke_width(self, elem, setval=None):
        """ Get/set stroke-width in pixels, untransformed
        """
        style = simplestyle.parseStyle(elem.attrib.get('style', ''))
        stroke = style.get('stroke', None)
        if stroke == 'none': stroke = None
            
        stroke_width = 0
        if stroke and setval is None:
            stroke_width = unittouu(style.get('stroke-width', '').strip())
            
        if setval:
            style['stroke-width'] = str(setval)
            elem.attrib['style'] = simplestyle.formatStyle(style)
        else:
            return stroke_width

    def set_transform(self, elem, matrix):
        """ Sets this element's transform value to the given matrix """
        elem.attrib['transform'] = simpletransform.formatTransform(matrix)

    def get_transform(self, elem, parent_transform=None):
        """ Get this element's transform as a matrix. If parent_transform is
            specified, return the cumulative transform.
        """
        transform = elem.attrib.get('transform', '').strip()
        
        if transform:
            transform = simpletransform.parseTransform(transform)
        else:
            transform = [[1,0,0], [0,1,0], [0,0,1]]
        if parent_transform:
            transform = simpletransform.composeTransform(parent_transform, transform)
            
        return transform

    def get_ancestor_transform(self, elem):
        """ Returns the cumulative transform of all this element's ancestors
            (excluding this element's own transform)
        """
        transform = [[1,0,0], [0,1,0], [0,0,1]]
        for a in self.ancestors(elem):
            transform = simpletransform.composeTransform(transform, self.get_transform(a))
        return transform

    def transform_path_node(self, transform, path, i):
        """ Modifies a node so that every point is transformed, including handles
        """
        segtype = path[i][0].lower()
        
        if segtype == 'z': return
        elif segtype == 'h':
            path[i][1][0] = transform_point(transform, [path[i][1][0], 0])[0]
        elif segtype == 'v':
            path[i][1][0] = transform_point(transform, [0, path[i][1][0]])[1]
        else:
            first_coordinate = 0
            if (segtype == 'a'): first_coordinate = 5           # for elliptical arcs, skip the radius x/y, rotation, large-arc, and sweep
            for j in range(first_coordinate, len(path[i][1]), 2):
                x, y = path[i][1][j], path[i][1][j+1]
                x, y = transform_point(transform, (x, y))
                path[i][1][j] = x
                path[i][1][j+1] = y
        
    
    def pathxy(self, path, i, setval=None):
        """ Get/set the endpoint of the given path segment.
            Inspects the segment type to know which elements are the endpoints.

            *** we don't treat 'z' segments correctly, meaning that this doesn't work
            right for paths with multiple subpaths.
        """
        segtype = path[i][0].lower()
        x = y = 0

        if segtype == 'z':                          # Return to start of current subpath -- final point == first point
            while path[i][0].lower() != 'm' and i != 0:
                i -= 1

        if segtype == 'h':                          # Horizontal segment
            if setval: path[i][1][0] = setval[0]
            else: x = path[i][1][0]
            
        elif segtype == 'v':                        # Vertical segment 
            if setval: path[i][1][0] = setval[1]
            else: y = path[i][1][0]
        else:
            if setval:                              # We still modify "return to origin" points (segtype=='z'), even though they're equal to the first point
                path[i][1][-2] = setval[0]
                path[i][1][-1] = setval[1]
            else:
                x = path[i][1][-2]                  # Ordinary point
                y = path[i][1][-1]

        if setval is None: return [x, y]
    
    def path_bounding_box(self, elem, parent_transform=None, stroke_width=True):
        """ Returns [min_x, min_y], [max_x, max_y] of the transformed
            element. (It doesn't make any sense to return the untransformed
            bounding box, with the intent of transforming it later, because
            the min/max points will be completely different points)
            
            If stroke_width=True (default), the returned bounding box includes
            stroke-width offset.
            
            This function uses a simplistic algorithm & doesn't take curves
            or arcs into account, just node positions.
        """
        # If we have a Live Path Effect, modify original-d. If anyone clamours
        # for it, we could make an option to ignore paths with Live Path Effects
        original_d = '{%s}original-d' % inkex.NSS['inkscape']
        path = simplepath.parsePath(elem.attrib.get(original_d, elem.attrib['d']))

        transform = self.get_transform(elem, parent_transform)
        if stroke_width: offset = self.stroke_width_offset(elem, parent_transform)
        else: offset = 0
        
        min_x = min_y = max_x = max_y = 0
        for i in range(len(path)):
            x, y = self.pathxy(path, i)
            x, y = transform_point(transform, (x, y))
            
            if i == 0:
                min_x = max_x = x
                min_y = max_y = y
            else:
                min_x = min(x, min_x)
                min_y = min(y, min_y)
                max_x = max(x, max_x)
                max_y = max(y, max_y)
        
        return (min_x-offset, min_y-offset), (max_x+offset, max_y+offset)
    
    def snap_translation(self, elem):
        # Only snaps the x/y translation of the transform, nothing else.
        # Doesn't take any parent_transform into account -- assumes
        # that the parent's transform has already been snapped.
        transform = self.get_transform(elem)
        if transform[0][1] or transform[1][0]:             # if we've got any skew/rotation, get outta here
            raise TransformError("Selection contains transformations with skew/rotation")
 
        transform[0][2] = round(transform[0][2])
        transform[1][2] = round(transform[1][2])
        
        self.set_transform(elem, transform)
    
    def snap_stroke(self, elem, parent_transform=None):
        transform = self.get_transform(elem, parent_transform)

        stroke_width = self.stroke_width(elem)
        if (stroke_width == 0): return                                          # no point raising a TransformError if there's no stroke to snap

        if abs(abs(transform[0][0]) - abs(transform[1][1])) > (10**-Precision):
            raise TransformError("Selection contains non-symetric scaling, can't snap stroke width")
        
        if stroke_width:
            stroke_width = transform_dimensions(transform, width=stroke_width)
            stroke_width = round(stroke_width)
            stroke_width = transform_dimensions(transform, width=stroke_width, inverse=True)
            self.stroke_width(elem, stroke_width)

    def snap_path_scale(self, elem, parent_transform=None):
        """ Goes through each node in the given path and modifies it as
            necessary in order to scale the entire path by the required
            (calculated) factor.
        """
    
        # If we have a Live Path Effect, modify original-d. If anyone clamours
        # for it, we could make an option to ignore paths with Live Path Effects
        original_d = '{%s}original-d' % inkex.NSS['inkscape']
        path = simplepath.parsePath(elem.attrib.get(original_d, elem.attrib['d']))
        transform = self.get_transform(elem, parent_transform)
        min_xy, max_xy = self.path_bounding_box(elem, parent_transform)
        
        width = max_xy[0] - min_xy[0]
        height = max_xy[1] - min_xy[1]

        # In case somebody tries to snap a 0-high element,
        # or a curve/arc with all nodes in a line, and of course
        # because we should always check for divide-by-zero!
        if (width==0 or height==0): return

        rescale = round(width)/width, round(height)/height                                  # Calculate scaling factor

        min_xy = transform_point(transform, min_xy, inverse=True)
        max_xy = transform_point(transform, max_xy, inverse=True)

        for i in range(len(path)):
            self.transform_path_node([[1, 0, -min_xy[0]], [0, 1, -min_xy[1]]], path, i)     # Center transform
            self.transform_path_node([[rescale[0], 0, 0],                                   # Perform scaling
                                       [0, rescale[1], 0]],
                                       path, i)
            self.transform_path_node([[1, 0, +min_xy[0]], [0, 1, +min_xy[1]]], path, i)     # Uncenter transform
        
        path = simplepath.formatPath(path)
        if original_d in elem.attrib: elem.attrib[original_d] = path
        else: elem.attrib['d'] = path

    def snap_path_pos(self, elem, parent_transform=None):
        """ Goes through each node in the given path and modifies it as
            necessary in order to shift the entire path by the required
            (calculated) distance.
        """

        # If we have a Live Path Effect, modify original-d. If anyone clamours
        # for it, we could make an option to ignore paths with Live Path Effects
        original_d = '{%s}original-d' % inkex.NSS['inkscape']
        path = simplepath.parsePath(elem.attrib.get(original_d, elem.attrib['d']))
        transform = self.get_transform(elem, parent_transform)
        min_xy, max_xy = self.path_bounding_box(elem, parent_transform)

        fractional_offset = min_xy[0]-round(min_xy[0]), min_xy[1]-round(min_xy[1])-self.document_offset
        fractional_offset = transform_dimensions(transform, fractional_offset[0], fractional_offset[1], inverse=True)

        for i in range(len(path)):
            self.transform_path_node([[1, 0, -fractional_offset[0]],
                                       [0, 1, -fractional_offset[1]]],
                                       path, i)

        path = simplepath.formatPath(path)
        if original_d in elem.attrib: elem.attrib[original_d] = path
        else: elem.attrib['d'] = path

    def snap_path_intent(self, elem, parent_transform=None):
        """ Like snap_path_shape, but preserves widths, making it much better
            for delicate shapes like fonts (ideally this could act like an auto
            hinting algorithm). The idea is to obselete the original snap_path_shape
            altogether.
            
            We assume the position of the path has already been snapped to
            a pixel boundary (i.e. we calculate all widths relative to the edge
            of the path).
            
            Note: to preserve shape in some special cases (eg very thin font
            strokes) any widths that snap to 0 we should snap to 0.5, but calculate
            the subsequent width relative to the previous segment.
        """
        class Node(object):
            def __init__(self, **kwargs):
                for k,v in kwargs.iteritems(): setattr(self, k, v)
        
        # If we have a Live Path Effect, modify original-d. If anyone clamours
        # for it, we could make an option to ignore paths with Live Path Effects
        original_d = '{%s}original-d' % inkex.NSS['inkscape']
        path = simplepath.parsePath(elem.attrib.get(original_d, elem.attrib['d']))

        transform = self.get_transform(elem, parent_transform)

        if transform[0][1] or transform[1][0]:          # if we've got any skew/rotation, get outta here
            raise TransformError("Selection contains transformations with skew/rotation")
        
        offset = self.stroke_width_offset(elem, parent_transform) % 1

        # First, create our own list of the path's nodes, to keep track of various useful info for each node.
        # This list will include the endpoint node (which equals the first node) for a closed path
        nodes = [ Node(untransformed=self.pathxy(path, i), index=i) for i in range(len(path)) ]

        # Then calculate the transformed location for each node
        for node in nodes:
            node.transformed = tuple(transform_point(transform, node.untransformed))
        
        # Now mark whether it's a vertical or horizontal segment, find the
        # next node in the segment, and set some other useful properties
        for node in nodes:
            node.next = nodes[(node.index+1) % len(nodes)]
            node.vertical = node.next.on_vertical = self.vertical(node.transformed, node.next.transformed)
            node.horizontal = node.next.on_horizontal= self.horizontal(node.transformed, node.next.transformed)
            node.vertical_direction = node.transformed[1] - node.next.transformed[1]
            node.horizontal_direction = node.transformed[0] - node.next.transformed[0]
            node.snapped = list(node.transformed)
        
        # Create an ordered list of all segments, ordered by horizontal position,
        # and another ordered by vertical position.
        horizontals = sorted(nodes, key=lambda node: node.transformed[1])
        verticals = sorted(nodes, key=lambda node: node.transformed[0])

        # Calculate the distance of each segment relative to the previous.
        # If segments are the same direction, allow snapping to zero width,
        # otherwise don't snap when < 0.5. If we didn't snap, calculate distance
        # of the next segment relative to the previous segment
        prev_segment = None
        for node in verticals:
            if not node.vertical: continue
            if prev_segment:
                node.distance = node.transformed[0] - prev_segment.transformed[0]
                if node.vertical_direction != prev_segment.vertical_direction and abs(node.distance) < 0.5:
                    node.vertical = False       # Pretend it's not straight after this
                    node.next.on_vertical = False
                    continue
                prev_segment.next_vertical = node
                node.snapped_distance = round(node.distance)
                node.snapped[0] = prev_segment.snapped[0] + node.snapped_distance

            # Set them equal so that almost-vertical lines (slope < max_gradient)
            # are certain to be made straight. Also, do it in every case, whether
            # or not this is the first segment (no prev_segment), because sometimes
            # first segments could be almost-vertical
            node.next.snapped[0] = node.snapped[0]
            prev_segment = node

        prev_segment = None
        for node in horizontals:
            if not node.horizontal: continue
            if prev_segment:
                node.distance = node.transformed[1] - prev_segment.transformed[1]
                if node.horizontal_direction != prev_segment.horizontal_direction and abs(node.distance) < 0.5:
                    node.horizontal = False     # Pretend it's not straight after this
                    node.next.on_horizontal = False
                    continue
                prev_segment.next_horizontal = node
                node.snapped_distance = round(node.distance)
                node.snapped[1] = prev_segment.snapped[1] + node.snapped_distance
            
            # See comment above re almost-vertical
            node.next.snapped[1] = node.snapped[1]
            prev_segment = node

        # Go through the in-between nodes and distribute each one between the
        # segments, according to the amount we've shifted the segments
        current_offset = {'origin': 0, 'shift': 0, 'scale': 1}
        for node in verticals:
            if node.on_vertical: continue
            if node.vertical:
                current_offset['origin'] = node.transformed[0]
                current_offset['shift'] = node.snapped[0] - node.transformed[0]
                if hasattr(node, 'next_vertical') and node.next_vertical.distance:
                    current_offset['scale'] = node.next_vertical.snapped_distance / node.next_vertical.distance
                else:
                    current_offset['scale'] = 1
                continue
            node.snapped[0] = (node.snapped[0] - current_offset['origin']) * current_offset['scale'] + current_offset['origin'] + current_offset['shift']

        current_offset = {'origin': 0, 'shift': 0, 'scale': 1}
        for node in horizontals:
            if node.on_horizontal: continue
            if node.horizontal:
                current_offset['origin'] = node.transformed[1]
                current_offset['shift'] = node.snapped[1] - node.transformed[1]
                if hasattr(node, 'next_horizontal') and node.next_horizontal.distance:
                    current_offset['scale'] = node.next_horizontal.snapped_distance / node.next_horizontal.distance
                else:
                    current_offset['scale'] = 1
                continue
            node.snapped[1] = (node.snapped[1] - current_offset['origin']) * current_offset['scale'] + current_offset['origin'] + current_offset['shift']

        # Calculate the distance required to snap the first horizontal & vertical
        # segments to a pixel, and shift the whole path accordingly.
        # (Like snap_path_pos, but relative to the first straight segment, not
        # the bounding box)
        # Incidentally, the .snapped and .transformed attributes of the first
        # straight segment are identical at this point.
        
        stroke_offset = self.stroke_width_offset(elem, parent_transform)
        x_offset = 0
        y_offset = 0
        for node in horizontals:
            if node.horizontal:
                y_offset = round(node.snapped[1]) - node.snapped[1] + self.document_offset
                break
        for node in verticals:
            if node.vertical:
                x_offset = round(node.snapped[0]) - node.snapped[0]
                break
        
        for node in nodes:
            node.snapped[0] += x_offset + stroke_offset
            node.snapped[1] += y_offset + stroke_offset

        # Finally go through each altered node and modify the actual path
        for node in nodes:
            fractional_offset = node.snapped[0]-node.transformed[0], node.snapped[1]-node.transformed[1]
            fractional_offset = transform_dimensions(transform, fractional_offset[0], fractional_offset[1], inverse=True)
            self.transform_path_node([[1, 0, fractional_offset[0]],
                           [0, 1, fractional_offset[1]]],
                           path, node.index)

        path = simplepath.formatPath(path)
        if original_d in elem.attrib: elem.attrib[original_d] = path
        else: elem.attrib['d'] = path

    def snap_path_shape(self, elem, parent_transform=None):
        """ Goes through each node in the given path and shifts it to the
            nearest pixel boundary. This would normally be done after
            the path is shifted & scaled into position, to make sure the
            least intrusive modifications are done first -- often the shape
            won't need to be snapped at all, if a shift/scale was successful.
        """

        # If we have a Live Path Effect, modify original-d. If anyone clamours
        # for it, we could make an option to ignore paths with Live Path Effects
        original_d = '{%s}original-d' % inkex.NSS['inkscape']
        path = simplepath.parsePath(elem.attrib.get(original_d, elem.attrib['d']))

        transform = self.get_transform(elem, parent_transform)

        if transform[0][1] or transform[1][0]:          # if we've got any skew/rotation, get outta here
            raise TransformError("Selection contains transformations with skew/rotation")
        
        offset = self.stroke_width_offset(elem, parent_transform) % 1
        
        prev_xy = self.pathxy(path, -1)
        first_xy = self.pathxy(path, 0)
        for i in range(len(path)):
            xy = self.pathxy(path, i)
            if (i == len(path)-1) or \
               ((i == len(path)-2) and path[-1][0].lower() == 'z'):
                next_xy = first_xy
            else:
                next_xy = self.pathxy(path, i+1)
            
            if not (xy and prev_xy and next_xy):
                print >>sys.stderr, "xy=%s, prev_xy=%s, next_xy=%" % (xy, prev_xy, next_xy)
                prev_xy = xy
                continue
            
            xy_untransformed = tuple(xy)
            xy = list(transform_point(transform, xy))
            prev_xy = transform_point(transform, prev_xy)
            next_xy = transform_point(transform, next_xy)
            
            on_vertical = on_horizontal = False
            
            if self.horizontal(xy, prev_xy):
                if len(path) > 2 or i==0:                   # on 2-point paths, first.next==first.prev==last and last.next==last.prev==first
                    xy[1] = prev_xy[1]                      # make the almost-equal values equal, so they round in the same direction
                on_horizontal = True
            if self.horizontal(xy, next_xy):
                on_horizontal = True
            
            if self.vertical(xy, prev_xy):                       # as above
                if len(path) > 2 or i==0:
                    xy[0] = prev_xy[0]
                on_vertical = True
            if self.vertical(xy, next_xy):
                on_vertical = True

            prev_xy = tuple(xy_untransformed)
            
            fractional_offset = [0,0]
            if on_vertical:
                fractional_offset[0] = xy[0] - (round(xy[0]-offset) + offset)
            if on_horizontal:
                fractional_offset[1] = xy[1] - (round(xy[1]-offset) + offset) - self.document_offset
            
            fractional_offset = transform_dimensions(transform, fractional_offset[0], fractional_offset[1], inverse=True)
            self.transform_path_node([[1, 0, -fractional_offset[0]],
                                       [0, 1, -fractional_offset[1]]],
                                       path, i)


        path = simplepath.formatPath(path)
        if original_d in elem.attrib: elem.attrib[original_d] = path
        else: elem.attrib['d'] = path

    def snap_path(self, elem, parent_transform=None):
        # we always modify at least the position, no matter what option they choose
        if self.options.modify_shapes == 'size_and_position':
            self.snap_path_pos(elem, parent_transform)
            self.snap_path_scale(elem, parent_transform)

        if self.options.modify_shapes == 'shape':
            #self.snap_path_shape(elem, parent_transform)
            self.snap_path_intent(elem, parent_transform)

    def snap_rect(self, elem, parent_transform=None):
        transform = self.get_transform(elem, parent_transform)
        
        if transform[0][1] or transform[1][0]:          # if we've got any skew/rotation, get outta here
            raise TransformError("Selection contains transformations with skew/rotation")
        
        offset = self.stroke_width_offset(elem, parent_transform) % 1

        width = unittouu(elem.attrib['width'])
        height = unittouu(elem.attrib['height'])
        x = unittouu(elem.attrib['x'])
        y = unittouu(elem.attrib['y'])

        width, height = transform_dimensions(transform, width, height)
        x, y = transform_point(transform, [x, y])

        # Snap to the nearest pixel
        height = round(height)
        width = round(width)
        x = round(x - offset) + offset                  # If there's a stroke of non-even width, it's shifted by half a pixel
        y = round(y - offset) + offset
        
        width, height = transform_dimensions(transform, width, height, inverse=True)
        x, y = transform_point(transform, [x, y], inverse=True)
        
        y += self.document_offset/transform[1][1]
        
        # Position the elem at the newly calculate values
        elem.attrib['width'] = str(width)
        elem.attrib['height'] = str(height)
        elem.attrib['x'] = str(x)
        elem.attrib['y'] = str(y)
    
    def snap_image(self, elem, parent_transform=None):
        self.snap_rect(elem, parent_transform)

    def snap_group(self, elem, parent_transform=None):
        group_transform = self.get_transform(elem, parent_transform)
        for e in elem:
            try:
                self.snap_object(e, parent_transform=group_transform)
            except TransformError, e:
                print >>sys.stderr, e
    
    def ancestors(self, elem):
        """ Returns all ancestors of the given element, in a list ordered from
            outermost to innermost. Does not include the element itself
            (it's not its own ancestor!)
        """
        ancestors = [ e for e in elem.iterancestors() ]
        ancestors.reverse()
        return ancestors
        
    def snap_object(self, elem, parent_transform=None):
        if not elemtype(elem, ('path', 'rect', 'image', 'g', 'use')):
            return
        
        if self.options.snap_ancestors and parent_transform==None:      # If we've been given a parent_transform, we can assume that the parents have already been snapped, or don't need to be
            for a in self.ancestors(elem):                              # Loop through ancestors from outermost to innermost, excluding this element.
                self.snap_translation(a)

        if self.options.ancestor_offset and parent_transform==None:     # If we haven't been given a parent_transform, then we need to calculate it
            parent_transform = self.get_ancestor_transform(elem)

        self.snap_translation(elem)

        if not elemtype(elem, 'g'):
            try:
                self.snap_stroke(elem, parent_transform)
            except TransformError, e:
                print >>sys.stderr, e

        if elemtype(elem, 'use'):       return                                  # We only snap the position of clones, nothing else to snap.
        elif elemtype(elem, 'g'):       self.snap_group(elem, parent_transform)
        elif elemtype(elem, 'path'):    self.snap_path(elem, parent_transform)
        elif elemtype(elem, 'rect'):    self.snap_rect(elem, parent_transform)
        elif elemtype(elem, 'image'):   self.snap_image(elem, parent_transform)

    def effect(self):
        svg = self.document.getroot()

        # Note: when you change the document height, Inkscape adds a vertical translation
        # to each layer so that relative positions of the objects don't change. This
        # causes problems when this translation is fractional, because pixel-aligned
        # sub-elements will be shifted off-pixel by the layer's translation.

        self.document_offset = 0
        if self.options.ancestor_offset:
            # although SVG units are absolute, the elements are positioned relative to the top of the page, rather than zero
            self.document_offset = unittouu(svg.attrib['height']) % 1

        for id, elem in self.selected.iteritems():
            try:
                self.snap_object(elem)
            except TransformError, e:
                print >>sys.stderr, e


if __name__ == '__main__':
    effect = PixelSnapEffect()
    effect.affect()

