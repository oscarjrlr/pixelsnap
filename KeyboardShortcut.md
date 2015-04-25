To add a keyboard shortcut, edit the file **~/.config/inkscape/keys/default.xml** or create it if it doesn't exist. The complete file should like something like below (it may contain other keybindings). To bind PixelSnap to the shortcut **Shift-X**, add the 2 lines between the horizontal rules (you can cut-n-paste from here):

```
<?xml version="1.0"?>
<keys name="Inkscape default">
```

---

```
 <bind key="x" modifiers="Shift" action="bryhoyt.pixelsnap" display="true"/>
 <bind key="X" modifiers="Shift" action="bryhoyt.pixelsnap" />
```

---

```
</keys>
```