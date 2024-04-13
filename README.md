# About

Vector racing game: pygame version of the old graph paper and colored pencil game.

# Run

```
$ python ./game.py
```

Or, simply:

```
$ ./game.py
```

Vim shortcut: `;<Space>`

# Develop

```
$ make tags
```

Vim shortcut: `;tg<Space>`

# Pygame Tips

* To render *without* alpha transparency, just draw everything
  (`pygame.draw.line()`, `pygame.draw.circle()`, etc.) on one big surface and
  only blit that surface once per game loop.
* To render *with* alpha transparency, artwork has to be blitted for the alpha
  channel to layer its semi-transparent artwork on top of previously blitted
  artwork.
* Blitting large surfaces is slow.
  * You can blit lots of small areas or you can blit a few large areas. Do not
    blit lots of large areas. Use FPS to gauge when blitting is impacting
    performance.
* Creating large surfaces is slow.
* To render *fast* **with alpha transparency**:
  * make a temporary drawing surface that is the same size as the final game art surface
  * draw to that temporary surface (`pygame.draw.line()`, `pygame.draw.circle()`, etc)
  * every `pygame.draw` call returns a `pygame.Rect` that is the smallest rect
    that encompasses the artwork -- blit *only* that rect to the final game art
    surface -- see `render_rect_area()` in `game.py` for an example
  * finally, clean up the temporary drawing surface (otherwise bits of old art will get re-blitted)
    * erase the old art by filling the temporary drawing surface with Color(0,0,0)
    * but do not erase the *entire* temporary drawing surface -- that is slow
    * again, use that rect returned by the draw call to erase the minimum necessary part of the temporary drawing surface
