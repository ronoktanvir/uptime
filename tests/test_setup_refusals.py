"""Common setup mistakes end in one plain line and exit 1, with nothing written or changed.

Before this change each of these ended in a Python traceback (or, for a busy port, created the
workspace and then failed to serve it).
"""
from hashlib import sha256
import json
import socket
import subprocess
import sys

import pytest

from scripts import setup_northwind as setup

SCRIPT = setup.ROOT / 'scripts' / 'setup_northwind.py'


def cli(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True,
                          timeout=300, cwd=setup.ROOT)


def snapshot(folder):
    if not folder.exists():
        return None
    return {str(p.relative_to(folder)): sha256(p.read_bytes()).hexdigest() for p in sorted(folder.rglob('*')) if p.is_file()}


def refused_with(result, line):
    assert result.returncode == 1, result.stderr[-2000:]
    assert 'Traceback' not in result.stderr
    assert result.stderr.strip().splitlines() == ['setup_northwind: ' + line]
    assert result.stdout == ''


@pytest.fixture(scope='module')
def workspace(tmp_path_factory):
    folder = tmp_path_factory.mktemp('refusals') / 'northwind-01'
    created = cli('--directory', folder, '--origin', 'http://127.0.0.1:8822')
    assert created.returncode == 0, created.stderr[-2000:]
    return folder


def hold(port):
    holder = socket.socket()
    holder.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        holder.bind(('127.0.0.1', port))
    except OSError:
        holder.close()
        return None
    holder.listen()
    return holder


def occupied_port():
    for port in range(8821, 8830):  # the throwaway range assigned for this push
        holder = hold(port)
        if holder is not None:
            return holder, port
    pytest.skip('No free throwaway port in 8821-8829.')


def test_rerunning_create_in_the_same_folder_is_a_plain_refusal(workspace):
    before = snapshot(workspace)
    refused_with(cli('--directory', workspace, '--serve'), setup.FOLDER_HOLDS_WORKSPACE)
    assert snapshot(workspace) == before


def test_creating_in_an_existing_folder_without_a_workspace_is_refused(tmp_path):
    folder = tmp_path / 'occupied'
    folder.mkdir()
    (folder / 'notes.txt').write_text('mine\n')
    before = snapshot(folder)
    refused_with(cli('--directory', folder), setup.FOLDER_EXISTS)
    assert snapshot(folder) == before


def test_resuming_a_missing_folder_is_refused(tmp_path):
    folder = tmp_path / 'never-created'
    refused_with(cli('--directory', folder, '--resume', '--serve'), setup.FOLDER_MISSING)
    assert not folder.exists()


def test_resuming_a_folder_without_a_workspace_is_refused(tmp_path):
    folder = tmp_path / 'empty'
    folder.mkdir()
    refused_with(cli('--directory', folder, '--resume'), setup.FOLDER_EMPTY)
    assert snapshot(folder) == {}


def test_serving_on_a_busy_port_is_refused_before_a_workspace_is_created(tmp_path):
    holder, port = occupied_port()
    folder = tmp_path / 'northwind-02'
    try:
        origin = 'http://127.0.0.1:' + str(port)
        refused_with(cli('--directory', folder, '--origin', origin, '--serve'),
                     'Port ' + str(port) + ' is already in use, so ' + origin + ' cannot be served. '
                     'Stop whatever is using it, or choose another port with --origin.')
        assert not folder.exists()
    finally:
        holder.close()


def test_resuming_on_a_busy_port_is_refused_and_leaves_the_workspace_unchanged(tmp_path):
    holder, port = occupied_port()
    folder = tmp_path / 'northwind-03'
    origin = 'http://127.0.0.1:' + str(port)
    try:
        holder.close()  # free it to create the workspace on this port, then take it again
        created = cli('--directory', folder, '--origin', origin)
        assert created.returncode == 0, created.stderr[-2000:]
        holder = hold(port)
        assert holder is not None, 'The port was taken by another process during the test.'
        before = snapshot(folder)
        refused_with(cli('--directory', folder, '--resume', '--serve'),
                     'Port ' + str(port) + ' is already in use, so ' + origin + ' cannot be served. '
                     'Stop whatever is using it; a resumed workspace keeps the port it was created with.')
        assert snapshot(folder) == before
    finally:
        holder.close()


def test_a_workspace_from_a_different_package_is_refused_plainly(workspace, tmp_path):
    import shutil
    copy = tmp_path / 'copy'
    shutil.copytree(workspace, copy)
    private = json.loads((copy / 'workspace.json').read_text())
    (copy / 'workspace.json').write_text(json.dumps(dict(private, package_sha256='0' * 64)))
    before = snapshot(copy)
    refused_with(cli('--directory', copy, '--resume'),
                 'The verified package differs from this workspace; preserve it and create a new directory.')
    assert snapshot(copy) == before


def test_a_correct_resume_still_works(workspace):
    resumed = cli('--directory', workspace, '--resume')
    assert resumed.returncode == 0 and 'Traceback' not in resumed.stderr
    assert resumed.stderr.strip().splitlines()[-1] == 'http://127.0.0.1:8822'
