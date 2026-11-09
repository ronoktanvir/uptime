#!/usr/bin/env python3
"""Pre-registered snapshot v2 for the second D05 unseen-vendor attempt (boilerplate-aware, still mechanical).

Fixed before selection (docs/v4/evaluation-gent8/D05-SECOND-PREREGISTRATION.md). Stdlib only, no model, no
credential. Differences from v1, decided in advance after run 1 captured site navigation text:
- content container priority: first <main>, else first <article>, else first element with role="main", else <body>;
- dropped subtrees: script/style/noscript/svg/template/nav/header/footer/aside/form/button/dialog/iframe, and any
  element whose id or class tokens include nav, navbar, navigation, menu, header, footer, cookie, banner,
  breadcrumb, sidebar, announcement, promo or skip;
- invisible zero-width characters (U+200B-U+200D, U+2060, U+FEFF) are removed.
Text is otherwise not edited, summarized or truncated. A page whose result still starts or ends with page chrome
fails eligibility check E6; it is never trimmed by hand.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

DROP_TAGS = {'script', 'style', 'noscript', 'svg', 'template', 'nav', 'header', 'footer', 'aside', 'form', 'button',
             'dialog', 'iframe'}
DROP_TOKENS = {'nav', 'navbar', 'navigation', 'menu', 'header', 'footer', 'cookie', 'banner', 'breadcrumb',
               'breadcrumbs', 'sidebar', 'announcement', 'promo', 'skip'}
BLOCK = {'p', 'div', 'section', 'article', 'li', 'ul', 'ol', 'table', 'tr', 'td', 'th', 'h1', 'h2', 'h3', 'h4',
         'h5', 'h6', 'br', 'dt', 'dd', 'blockquote', 'pre', 'main', 'body', 'thead', 'tbody'}
VOID = {'br', 'img', 'hr', 'meta', 'link', 'input', 'source', 'wbr', 'area', 'col', 'embed', 'param', 'track'}
ZERO_WIDTH = dict.fromkeys(map(ord, '​‌‍⁠﻿'))
MAX_TEXT = 50000
USER_AGENT = 'uptime-evaluation-snapshot/2 (+public SLA text capture)'
CONTAINERS = ('main', 'article', 'role_main', 'body')


def _dropped(tag, attrs):
    if tag in DROP_TAGS:
        return True
    values = ' '.join(v for k, v in attrs if k in ('id', 'class') and v).lower()
    return bool(DROP_TOKENS & set(re.split(r'[\s_\-]+', values)))


class _Visible(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []  # (tag, dropped, containers opened by this element)
        self.parts = {name: [] for name in CONTAINERS}
        self.open = {name: 0 for name in CONTAINERS}
        self.seen = {name: False for name in CONTAINERS}

    def _dropping(self):
        return any(dropped for _, dropped, _ in self.stack)

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            if tag == 'br':
                self._emit('\n')
            return
        opened = []
        role_main = any(k == 'role' and v == 'main' for k, v in attrs)
        for name, hit in (('main', tag == 'main'), ('article', tag == 'article'),
                          ('role_main', role_main and tag != 'main'), ('body', tag == 'body')):
            if hit and not self.seen[name]:
                self.seen[name] = True
                self.open[name] += 1
                opened.append(name)
        self.stack.append((tag, _dropped(tag, attrs), opened))
        if tag in BLOCK:
            self._emit('\n')

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        while self.stack:
            popped, _, opened = self.stack.pop()
            for name in opened:
                self.open[name] -= 1
            if popped == tag:
                break
        if tag in BLOCK:
            self._emit('\n')

    def handle_data(self, data):
        if not self._dropping():
            self._emit(data)

    def _emit(self, text):
        if self._dropping():
            return
        for name in CONTAINERS:
            if self.open[name]:
                self.parts[name].append(text)


def extract(html):
    parser = _Visible()
    parser.feed(html)
    parser.close()
    container = next((name for name in CONTAINERS if ''.join(parser.parts[name]).strip()), 'body')
    raw = ''.join(parser.parts[container]).translate(ZERO_WIDTH)
    lines = (re.sub(r'[ \t\f\v ]+', ' ', line).strip() for line in raw.splitlines())
    text = '\n'.join(line for line in lines if line)
    return ''.join(ch for ch in text if ord(ch) >= 32 or ch in '\n\t'), container


def chrome_check(text, vendor):
    """E6: the first line must name the SLA or vendor; the last line must not be footer chrome."""
    lines = text.splitlines() or ['']
    first, last = lines[0].lower(), lines[-1].lower()
    starts_ok = any(token in first for token in ('service level', 'sla', vendor.lower()))
    ends_ok = not any(token in last for token in ('©', 'copyright', 'all rights reserved', 'privacy', 'cookie'))
    return {'first_line_names_sla_or_vendor': starts_ok, 'last_line_not_footer_chrome': ends_ok, 'pass': starts_ok and ends_ok}


def _create(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'wb') as out:
        out.write(data)


def snapshot(url, vendor, out_dir):
    if urlsplit(url).scheme != 'https':
        raise ValueError('HTTPS provenance is required.')
    with urlopen(Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'text/html'}), timeout=30) as response:
        status, final_url = response.status, response.geturl()
        content_type = response.headers.get('Content-Type', '')
        raw = response.read(5_000_000)
    charset = re.search(r'charset=([\w-]+)', content_type)
    html = raw.decode(charset[1] if charset else 'utf-8', errors='replace')
    text, container = extract(html)
    document = {'name': f'{vendor} Service Level Agreement', 'uri': final_url, 'classification': 'public', 'text': text}
    encoded = (json.dumps(document, ensure_ascii=False, indent=2) + '\n').encode()
    out = Path(out_dir)
    _create(out / 'page.html', raw)
    _create(out / 'document.json', encoded)
    record = {'url': url, 'final_url': final_url, 'http_status': status, 'content_type': content_type,
              'container': container, 'raw_sha256': sha256(raw).hexdigest(), 'raw_bytes': len(raw),
              'text_sha256': sha256(text.encode()).hexdigest(), 'text_characters': len(text),
              'document_sha256': sha256(encoded).hexdigest(), 'document_bytes': len(encoded),
              'within_text_limit': len(text) <= MAX_TEXT, 'within_document_bytes_limit': len(encoded) <= 80000,
              'chrome_check': chrome_check(text, vendor),
              'extractor_sha256': sha256(Path(__file__).read_bytes()).hexdigest()}
    _create(out / 'snapshot.json', (json.dumps(record, indent=2) + '\n').encode())
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--vendor', required=True)
    parser.add_argument('--out-dir', required=True, type=Path)
    args = parser.parse_args(argv)
    json.dump(snapshot(args.url, args.vendor, args.out_dir), sys.stdout, indent=2)
    print()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
