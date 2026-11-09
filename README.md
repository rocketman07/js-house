# J+S House web viewer

Two files make the whole viewer:

- `index.html` - the viewer page (three.js, loaded from the jsDelivr CDN)
- `js-house.glb` - the model, exported from J+S-House.3dm (about 7.6 MB)

## Putting it on your website

Upload both files into one folder on your web host, for example `yoursite.com/js-house/`, and send the client
`https://yoursite.com/js-house/`. Any host that serves plain files works: WordPress (upload with a file
manager or FTP), Netlify (drag the folder onto app.netlify.com/drop), GitHub Pages, or your own server.

Squarespace and Wix can't host the .glb file directly. Host the folder on Netlify (free) and embed it on a page:

```html
<iframe src="https://YOUR-SITE.netlify.app/" style="width:100%;height:80vh;border:0" allowfullscreen></iframe>
```

Opening `index.html` straight from your computer (double-click) won't load the model; browsers block that.
It has to be served from a web address.

## Controls

- Orbit: drag to rotate, right-drag to pan, scroll to zoom, double-click a surface to centre on it.
- Walk: click Walk, then click the view. W A S D to move, mouse to look, Shift to run, Esc to stop.
  Walls and floors are solid; door slabs and glass are not, so you can walk through doorways.
- Layers panel: every Rhino layer under 3D Model and Site Model, with checkboxes. Presets: Everything,
  Framing, Interior (no roof), House only.
- Phones and tablets get orbit and layers; walk mode needs a keyboard and mouse.

## Updating after design changes

Re-run `export_glb.py` in Rhino (ScriptEditor) with `OUT_GLB` set to this folder's `js-house.glb`,
then re-upload `js-house.glb`. The page doesn't change.
