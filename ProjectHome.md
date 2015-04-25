## What is it? ##
**PixelSnap** is an extension for [Inkscape](http://inkscape.org/), an incredibly useful vector graphics app. It allows you to align rectangles & paths to pixel boundaries, to create sharp web & digital graphics.

In particular, it solves [the problem described here](http://bearfruit.org/blog/2007/09/14/fuzzy-lines-and-text-in-web-graphics).

![http://pixelsnap.googlecode.com/svn/wiki/demo.png](http://pixelsnap.googlecode.com/svn/wiki/demo.png)

## Download latest release & Installation ##
[PixelSnap-0.2.0](http://pixelsnap.googlecode.com/files/pixelsnap-0.2.0.zip) — just unzip it, and copy the .inx and .py files into your Inkscape extensions folder. **Read the [INSTALL file](http://code.google.com/p/pixelsnap/source/browse/trunk/INSTALL) if you run into trouble,** or ask on the [email discussion group](http://groups.google.com/group/pixelsnap-users)

This release should fix all recent bugs that have been posted, and it also handles complex paths better.

Find out [how to add a keyboard shortcut](KeyboardShortcut.md) for PixelSnap.

## Features ##

  * Snaps rectangles & paths with horizontal or vertical segments
  * Snaps stroke width
  * Takes various offsets into account (document offset, and stroke-width offset)
  * Handles transforms transparently — if an object is scaled or translated, it does the Right Thing (but skews & rotations are ignored)

Just for the record, this doesn't provide pixel-alignment for text. That's what font-hinting is good for, and I'd love to see it in Inkscape someday.

## What's it good for? ##

When you create vector graphics in Inkscape, horizontal & vertical lines and rectangles will usually appear slightly blurry, due to edges not being aligned perfectly with screen pixels.

Particularly if you're creating graphics for the screen & web, this causes an overall unprofessional finish to your graphics. And (for more than a few objects), it requires a lot of tedious work to align every single object. The normal process is something like:

  1. Turn on 1.0-spaced grids
  1. Set snapping to bounding-box
  1. Manually move each & every rectangle to snap to the nearest pixel
  1. Manually resize every rectangle to also snap on the opposite sides
  1. Turn on 0.5-spaced grids & snapping
  1. Manually edit every straight segment of every path so that the nodes are all aligned at the midpoint of the pixel

And of course, if you ever modify any of those objects, particularly when zoomed in, you have to do the whole annoying process again.

With this plugin, the whole thing is a simple case of running Extensions->PixelSnap on the selected objects.

## Isn't this the domain of raster editors? ##
Some people, as [Matt at Bearfruit suggests](http://www.bearfruit.org/blog/2008/08/27/font-hinting-in-inkscape), think that this sort of thing belongs in a raster-editor like the Gimp. But I say:

  * **Convenience:** I don't want to fire up the Gimp every time I need to snap a couple of pixels.
  * **False dichotomy:** If pixels belonged in raster editors, then why should inkscape allow embedding photos, etc? Graphics are graphics, and I don't really care about different conceptual representations.
  * **Impossibility:** To be honest, I can't even see how it would work to align my pixels in a separate app.

If you think I'm destroying the balance of the cosmos, you're welcome to send your thoughtful comments to the [email discussion group](http://groups.google.com/group/pixelsnap-users).

## Whodunnit? ##

PixelSnap is brought to you by **Bryan Hoyt**, one of friendly folks at **[Brush Technology](http://brush.co.nz/)**