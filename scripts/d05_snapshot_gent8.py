#!/usr/bin/env python3
"""Pre-registered snapshot of one public vendor SLA page for the D05 unseen-vendor proof.

Fixed before selection (docs/v4/evaluation-gent8/D05-SELECTION-PREREGISTRATION.md). Stdlib only, no model,
no credential. Fetches one public HTTPS page, keeps the raw bytes, and extracts visible text mechanically:
script/style/noscript/svg/template/nav/header/footer/form/button are dropped; <main> is used when present,
otherwise <body>; block tags break lines; whitespace inside a line collapses; empty lines are dropped. No
text is edited, summarized or truncated. Output files are create-only and owner-only.
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

DROP = {'script', 'style', 'noscript', 'svg', 'template', 'nav', 'header', 'footer', 'form', 'button'}
BLOCK = {'p', 'div', 'section', 'article', 'li', 'ul', 'ol', 'table', 'tr', 'td', 'th', 'h1', 'h2', 'h3', 'h4',
         'h5', 'h6', 'br', 'dt', 'dd', 'blockquote', 'pre', 'main', 'body', 'thead', 'tbody'}
VOID = {'br', 'img', 'hr', 'meta', 'link', 'input', 'source', 'wbr', 'area', 'col', 'embed', 'param', 'track'}
MAX_TEXT = 50000  # uptime.vendor_terms.Document.text max_length
USER_AGENT = 'uptime-evaluation-snapshot/1 (+public SLA text capture)'


class _Visible(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.parts, self.main_parts, self.in_main = [], [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            if tag == 'br':
                self._emit('\n')
            return
        self.stack.append(tag)
        if tag == 'main':
            self.in_main += 1
        if tag in BLOCK:
            self._emit('\n')

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        while self.stack:
            popped = self.stack.pop()
            if popped == 'main':
                self.in_main -= 1
            if popped == tag:
                break
        if tag in BLOCK:
            self._emit('\n')

    def handle_data(self, data):
        if any(tag in DROP for tag in self.stack):
            return
        self._emit(data)

    def _emit(self, text):
        self.parts.append(text)
        if self.in_main:
            self.main_parts.append(text)


def extract(html):
    parser = _Visible()
    parser.feed(html)
    parser.close()
    chosen = parser.main_parts if ''.join(parser.main_parts).strip() else parser.parts
    lines = (re.sub(r'[ \t\f\v ]+', ' ', line).strip() for line in ''.join(chosen).splitlines())
    text = '\n'.join(line for line in lines if line)
    return ''.join(ch for ch in text if ord(ch) >= 32 or ch in '\n\t')


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
    text = extract(html)
    document = {'name': f'{vendor} Service Level Agreement', 'uri': final_url, 'classification': 'public', 'text': text}
    encoded = (json.dumps(document, ensure_ascii=False, indent=2) + '\n').encode()
    out = Path(out_dir)
    _create(out / 'page.html', raw)
    _create(out / 'document.json', encoded)
    record = {'url': url, 'final_url': final_url, 'http_status': status, 'content_type': content_type,
              'raw_sha256': sha256(raw).hexdigest(), 'raw_bytes': len(raw), 'text_sha256': sha256(text.encode()).hexdigest(),
              'text_characters': len(text), 'document_sha256': sha256(encoded).hexdigest(), 'document_bytes': len(encoded),
              'within_text_limit': len(text) <= MAX_TEXT, 'within_document_bytes_limit': len(encoded) <= 80000,
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
