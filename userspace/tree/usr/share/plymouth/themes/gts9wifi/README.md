# GTS9 Plymouth theme

Black boot splash with the Samsung wordmark, a rotating spinner and the
Fedora logo.  Driven by Plymouth's `script` plugin.

- `samsung.png` is the white Samsung wordmark (Simple Icons path).
- `fedora-icon.png` and `fedora-wordmark.png` come from Fedora's
  `fedora-logos` package.
- `spinner-0001.png` … `spinner-0084.png` are anti-aliased frames (a faint
  full ring plus a bright rotating round-capped arc), originally rendered
  at 256×256 from 8× supersampling; they are raster PNGs, not vector art.
- Every image is pre-rendered at its on-screen size for the 2560×1600
  panel (Samsung 746×114, Fedora icon 122×122, wordmark 306×85, spinner
  112×112).  Plymouth's `Image.Scale` uses a fixed 2×2 interpolation that
  aliases badly at these downscale ratios, so the script loads the assets
  1:1 and never scales them at boot.

Samsung and Fedora marks are trademarks of their owners; this is a
device-local boot splash, not a redistributed branding package.
