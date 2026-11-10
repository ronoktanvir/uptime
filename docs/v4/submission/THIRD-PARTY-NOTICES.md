# Third-party notices for the interface

## Phosphor Icons

The interface uses 21 icons from the Phosphor icon family, at Ronok's request (November 9, 2026).

- **Source:** [github.com/phosphor-icons/homepage](https://github.com/phosphor-icons/homepage), folder `public/assets/phosphor.iconjar/icons/`, at commit `7a57592e564f9ba7996ebac05be5b0546464fb9c`.
- **Files:** `squares-four`, `tray`, `file-text`, `pulse`, `arrows-clockwise`, `arrows-clockwise-bold`, `arrow-right-bold`, `arrow-left-bold`, `arrow-square-out-bold`, `user-bold`, `lightning-bold`, `tray-arrow-down-bold`, `paperclip-bold`, `clock-bold`, `lock-simple-bold`, `check-bold`, `info-fill`, `warning-fill`, `warning-circle-fill`, `seal-check-fill`, `check-circle-fill` (each with the extension `.svg`).
- **How they are used:** only each file's path outline is kept, unchanged. Four are inline in `web/index.html` (the sidebar) with the refresh icon; the rest are image tokens at the top of `web/style.css`, drawn as masks so each icon takes the colour of the text beside it. No file is loaded from another host and no new file is served.
- **How they were taken in:** each file was read as data and accepted only if it had exactly the one expected shape (a single filled path with path-outline characters); nothing else from a file is copied.
- **Decoration only:** every icon is hidden from assistive technology or is an empty pseudo-element, so no link, tag or heading is named by an icon. No icon states anything the words beside it do not.

### Licence (MIT), as distributed with the icons

```
MIT License

Copyright (c) 2020 Phosphor Icons

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
