# Third-party notices for the interface

## Phosphor Icons

The interface uses 40 icons from the Phosphor icon family, at Ronok's request (November 9, 2026). The second pass that evening added the sidebar's tool icons, the page tiles and the card title icons.

- **Source:** [github.com/phosphor-icons/homepage](https://github.com/phosphor-icons/homepage), folder `public/assets/phosphor.iconjar/icons/`, at commit `7a57592e564f9ba7996ebac05be5b0546464fb9c`.
- **Files:** `squares-four`, `tray`, `file-text`, `pulse`, `arrows-clockwise`, `arrows-clockwise-bold`, `arrow-right-bold`, `arrow-left-bold`, `arrow-square-out-bold`, `user-bold`, `lightning-bold`, `tray-arrow-down-bold`, `paperclip-bold`, `clock-bold`, `lock-simple-bold`, `check-bold`, `info-fill`, `warning-fill`, `warning-circle-fill`, `seal-check-fill`, `check-circle-fill`, `bank`, `list-magnifying-glass`, `flask`, `shield-check`, `plugs-connected`, `flow-arrow`, `chart-bar`, `file-text-bold`, `tray-bold`, `path-bold`, `hand-coins-bold`, `list-checks-bold`, `chat-circle-text-bold`, `scales-bold`, `tag-bold`, `receipt-bold`, `pulse-bold`, `check-circle-bold`, `key-bold` (each with the extension `.svg`).
- **How they are used:** only each file's path outline is kept, unchanged. The sidebar's eleven destinations and the refresh icon are inline in `web/index.html`; the rest are image tokens at the top of `web/style.css`, drawn as masks so each icon takes the colour of the text beside it. No file is loaded from another host and no new file is served.
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

## Inter

The interface is set in Inter, at Ronok's request (November 9, 2026: "use a cleaner font", then "Yes, use Inter").

- **Source:** [github.com/rsms/inter](https://github.com/rsms/inter), version 4.1 (tag `v4.1`), file `docs/font-files/InterVariable.woff2`.
- **File in this repository:** `web/InterVariable.woff2`, 352,240 bytes, unmodified. SHA-256 `693b77d4f32ee9b8bfc995589b5fad5e99adf2832738661f5402f9978429a8e3`.
- **How it is used:** the app serves the file itself at `/static/InterVariable.woff2`; `web/style.css` declares it and both pages preload it. Nothing is loaded from another host, and the content security policy is unchanged (a font from the app's own origin is allowed by `default-src 'self'`). The system font stack remains as the fallback.

### Licence (SIL Open Font License 1.1), as distributed with the font

```
Copyright (c) 2016 The Inter Project Authors (https://github.com/rsms/inter)

This Font Software is licensed under the SIL Open Font License, Version 1.1.
This license is copied below, and is also available with a FAQ at:
http://scripts.sil.org/OFL

-----------------------------------------------------------
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide
development of collaborative font projects, to support the font creation
efforts of academic and linguistic communities, and to provide a free and
open framework in which fonts may be shared and improved in partnership
with others.

The OFL allows the licensed fonts to be used, studied, modified and
redistributed freely as long as they are not sold by themselves. The
fonts, including any derivative works, can be bundled, embedded,
redistributed and/or sold with any software provided that any reserved
names are not used by derivative works. The fonts and derivatives,
however, cannot be released under any other type of license. The
requirement for fonts to remain under this license does not apply
to any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright
Holder(s) under this license and clearly marked as such. This may
include source files, build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the
copyright statement(s).

"Original Version" refers to the collection of Font Software components as
distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to, deleting,
or substituting -- in part or in whole -- any of the components of the
Original Version, by changing formats or by porting the Font Software to a
new environment.

"Author" refers to any designer, engineer, programmer, technical
writer or other person who contributed to the Font Software.

PERMISSION AND CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining
a copy of the Font Software, to use, study, copy, merge, embed, modify,
redistribute, and sell modified and unmodified copies of the Font
Software, subject to the following conditions:

1) Neither the Font Software nor any of its individual components,
in Original or Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy
contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or
in the appropriate machine-readable metadata fields within text or
binary files as long as those fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font
Name(s) unless explicit written permission is granted by the corresponding
Copyright Holder. This restriction only applies to the primary font name as
presented to the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font
Software shall not be used to promote, endorse or advertise any
Modified Version, except to acknowledge the contribution(s) of the
Copyright Holder(s) and the Author(s) or with their explicit written
permission.

5) The Font Software, modified or unmodified, in part or in whole,
must be distributed entirely under this license, and must not be
distributed under any other license. The requirement for fonts to
remain under this license does not apply to any document created
using the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are
not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM
OTHER DEALINGS IN THE FONT SOFTWARE.
```
