#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""ApexTX RF Image Extractor.

A small Windows tool, in the same style as the ApexTX Flasher and Theme Editor,
that unpacks the RF-module and receiver firmware images from a FlySky Noble
NB4/NB4+ stock updater and copies them to the radio's USB storage, so ApexTX can
offer an in-radio RF / receiver update.

No FlySky files are redistributed: the user supplies their own updater, and this
tool only unpacks it locally. The images themselves are FlySky's property.

The package layout is parsed dynamically from the package itself (section table
-> the "Firmware" directory), not from fixed addresses, so it does not depend on
one specific firmware version.
"""
import argparse
import base64
import functools
import json
import os
import secrets
import string
import struct
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP_VERSION = '1.0'
# Where the images are written on the destination (what ApexTX will read).
OUT_SUBDIR = 'FIRMWARE'
NOR_BASE = 0xC0280000  # the NOR package's mapping on the radio

# Receiver product number -> FlySky model name (from the ApexTX PN_* table).
RX_NAMES = {
    0x12340002: 'FTr10', 0x12340004: 'FGr4', 0x12340006: 'FTr4',
    0x00010103: 'FTr16S', 0x00010104: 'Mini-Z', 0x00010105: 'FTr8B',
    0x00010106: 'FTr12B', 0x00010107: 'FGr8B', 0x00010108: 'FGr12B',
    0x00010109: 'GMr', 0x0001010A: 'TMr', 0x0001010B: 'INr4-GYB',
    0x0001010C: 'INr6-HS', 0x0001010D: 'FTr4B', 0x0001010E: 'FGr4B',
    0x0001010F: 'FBr12', 0x00010110: 'INr6-FC', 0x00010111: 'Tr8B',
    0x00010112: 'FBr8', 0x00010113: 'FBr4',
}


def _resource(name):
    base = getattr(sys, '_MEIPASS', None)
    return (Path(base) if base else Path(__file__).resolve().parent) / name


@functools.lru_cache(maxsize=1)
def _logo_data_uri():
    try:
        raw = _resource('apextx-updater-logo.png').read_bytes()
        return 'data:image/png;base64,' + base64.b64encode(raw).decode('ascii')
    except Exception:
        return ''


# --- extraction core --------------------------------------------------------

def read_pe_resource(data, want_type, want_name):
    """Return the bytes of resource (want_type/want_name) from PE image bytes."""
    d = data
    pe = struct.unpack_from('<I', d, 0x3C)[0]
    opt = struct.unpack_from('<H', d, pe + 20)[0]
    soff = pe + 24 + opt
    nsec = struct.unpack_from('<H', d, pe + 6)[0]
    secs = []
    base_raw = None
    for i in range(nsec):
        o = soff + i * 40
        va = struct.unpack_from('<I', d, o + 12)[0]
        rsz = struct.unpack_from('<I', d, o + 16)[0]
        rptr = struct.unpack_from('<I', d, o + 20)[0]
        secs.append((va, rsz, rptr))
        if d[o:o + 8].rstrip(b'\0') == b'.rsrc':
            base_raw = rptr
    if base_raw is None:
        raise ValueError('This file is not a FlySky updater (no resources found).')

    def rva2off(r):
        for va, rsz, rptr in secs:
            if va <= r < va + rsz:
                return r - va + rptr
        return None

    found = []

    def walk(off, path):
        nn, ni = struct.unpack_from('<HH', d, base_raw + off + 12)
        for i in range(nn + ni):
            e = base_raw + off + 16 + i * 8
            nid, ptr = struct.unpack_from('<II', d, e)
            key = None if (nid & 0x80000000) else nid
            if ptr & 0x80000000:
                walk(ptr & 0x7FFFFFFF, path + [key])
            else:
                r, sz = struct.unpack_from('<II', d, base_raw + (ptr & 0x7FFFFFFF))
                found.append((path + [key], d[rva2off(r):rva2off(r) + sz]))

    walk(0, [])
    for path, blob in found:
        if len(path) >= 2 and path[0] == want_type and path[1] == want_name:
            return blob
    raise ValueError('This updater does not contain the firmware package.')


def _looks_like_cortex_m(img):
    if len(img) < 8:
        return False
    sp, reset = struct.unpack_from('<II', img, 0)
    return 0x20000000 <= sp < 0x20080000 and 0x08000000 <= reset < 0x08100000


def parse_images(pkg):
    """Return [{kind,name,id,version,size,ok,bytes}] from the NOR package."""
    if pkg[:4] != b'\x5a\x5a\x6c\xe7':
        raise ValueError('Unexpected package format; this is not an NB4 updater.')

    def at(addr):
        return addr - NOR_BASE

    nsec = struct.unpack_from('<H', pkg, 6)[0]
    fw_dir_ptr = None
    for i in range(nsec):
        name_ptr, _count, data_ptr = struct.unpack_from('<III', pkg, 0x14 + i * 12)
        end = pkg.find(b'\0', at(name_ptr))
        if pkg[at(name_ptr):end].decode('ascii', 'replace') == 'Firmware':
            fw_dir_ptr = data_ptr
    if fw_dir_ptr is None:
        raise ValueError('No firmware section in this updater.')

    count = pkg[at(fw_dir_ptr)]
    entries_ptr = struct.unpack_from('<I', pkg, at(fw_dir_ptr) + 4)[0]
    images = []
    for i in range(count):
        e = at(entries_ptr) + i * 20
        typ = pkg[e]
        idv, ver, size, data_ptr = struct.unpack_from('<IIII', pkg, e + 4)
        img = pkg[at(data_ptr):at(data_ptr) + size]
        images.append({
            'kind': 'rf-module' if typ == 0 else 'receiver',
            'name': RX_NAMES.get(idv) if typ == 1 else None,
            'id': f'{idv:08x}', 'version': f'{ver:x}', 'size': size,
            'ok': _looks_like_cortex_m(img), 'bytes': img,
        })
    if not images:
        raise ValueError('No firmware images found in this updater.')
    return images


def image_filename(img):
    tag = (img['name'] + '_') if img['name'] else ''
    return f"{img['kind']}_{tag}{img['id']}_v{img['version']}.bin"


# --- destinations -----------------------------------------------------------

def destinations():
    """Radio USB storage (a drive with THEMES or RADIO/radio.yml) + a folder."""
    out = []
    if os.name == 'nt':
        roots = [Path(f'{c}:/') for c in string.ascii_uppercase]
    else:
        roots = [p for base in ('/Volumes', '/media', f'/media/{os.environ.get("USER", "")}')
                 if Path(base).is_dir() for p in Path(base).iterdir()]
    for root in roots:
        try:
            if (root / 'THEMES').is_dir() or (root / 'RADIO' / 'radio.yml').is_file():
                out.append({'path': str(root), 'radio': True})
        except OSError:
            continue
    out.append({'path': str(Path.home() / 'ApexTX-RF-Images'), 'radio': False})
    return out


def _checked_destination(target):
    if target in {d['path'] for d in destinations()}:
        return Path(target)
    # The local folder is always allowed even if it does not exist yet.
    if target == str(Path.home() / 'ApexTX-RF-Images'):
        return Path(target)
    raise ValueError('Unknown destination. Reconnect the radio and try again.')


def _write_images(updater_bytes, dest):
    """Unpack the updater and write every image into `dest` (exact folder)."""
    dest = Path(dest)
    images = parse_images(read_pe_resource(updater_bytes, 10, 901))
    dest.mkdir(parents=True, exist_ok=True)
    written = []
    for img in images:
        fn = image_filename(img)
        (dest / fn).write_bytes(img['bytes'])
        written.append({k: img[k] for k in ('kind', 'name', 'id', 'version', 'size', 'ok')} | {'file': fn})
    return {'folder': str(dest), 'images': written}


def extract_to(updater_bytes, target):
    """Web entry: validate the destination against the detected list first."""
    return _write_images(updater_bytes, _checked_destination(target) / OUT_SUBDIR)


# --- web app ----------------------------------------------------------------

def serve(port, open_browser):
    token = secrets.token_urlsafe(16)
    html = _resource('apextx-rf-image-extractor.html').read_text(encoding='utf-8')
    html = html.replace('__LOGO_DATA__', _logo_data_uri()).replace('__VERSION__', APP_VERSION)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _auth(self):
            from urllib.parse import urlparse, parse_qs
            return parse_qs(urlparse(self.path).query).get('token', [''])[0] == token

        def reply(self, code, obj):
            body = json.dumps(obj).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            from urllib.parse import urlparse
            path = urlparse(self.path).path
            if path == '/':
                body = html.encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif path == '/api/targets' and self._auth():
                self.reply(200, {'targets': destinations()})
            else:
                self.reply(404, {'error': 'not found'})

        def do_POST(self):
            from urllib.parse import urlparse
            if urlparse(self.path).path != '/api/extract' or not self._auth():
                self.reply(404, {'error': 'not found'})
                return
            length = int(self.headers.get('Content-Length', 0))
            try:
                req = json.loads(self.rfile.read(length) or b'{}')
                updater = base64.b64decode(req.get('updater', ''))
                if not updater:
                    raise ValueError('Choose your FlySky updater first.')
                result = extract_to(updater, req.get('target', ''))
            except (ValueError, OSError, json.JSONDecodeError, struct.error) as error:
                self.reply(400, {'error': str(error)})
                return
            self.reply(200, result)

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    address = f'http://127.0.0.1:{server.server_port}/?token={token}'
    print(f'ApexTX RF Image Extractor: {address}', flush=True)
    if os.environ.get('APEXTX_RF_EXTRACTOR_WINDOW') == '1':
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            import webview
            webview.create_window('ApexTX RF Image Extractor', address,
                                  width=940, height=820, min_size=(640, 620))
            webview.start()
        except Exception:
            webbrowser.open(address)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
        finally:
            server.shutdown()
            server.server_close()
        return
    if open_browser:
        webbrowser.open(address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('updater', nargs='?', help='CLI mode: extract this updater')
    parser.add_argument('out', nargs='?', help='CLI mode: output folder')
    args = parser.parse_args()
    if args.updater and args.out:  # headless CLI mode (local, any folder)
        result = _write_images(Path(args.updater).read_bytes(), args.out)
        for im in result['images']:
            print(f"  {im['file']:40s} {im['size']:8d} B  {'ok' if im['ok'] else '??'}")
        print(f"wrote {len(result['images'])} files to {result['folder']}")
        return
    if getattr(sys, 'frozen', False):
        os.environ.setdefault('APEXTX_RF_EXTRACTOR_WINDOW', '1')
    serve(args.port, not args.no_browser)


if __name__ == '__main__':
    main()
