"""Pinned public-experiment transport; no claim of provider or user-scope isolation."""
from hashlib import sha256
import json
import os
from pathlib import Path
import pwd
import selectors
import signal
import subprocess
import tempfile
from time import monotonic


def digest(value):
    return sha256(value).hexdigest()


def public_environment():
    # Preserve the existing authentication location; never copy credentials or
    # redirect HOME. No inherited proxy, NODE, provider, or loader variables.
    account=pwd.getpwuid(os.getuid()).pw_name
    return dict(HOME=str(Path.home()), USER=account, LOGNAME=account, PATH='/usr/bin:/bin:/usr/sbin:/sbin',
                LANG='en_US.UTF-8', LC_ALL='en_US.UTF-8', DISABLE_UPDATES='1',
                DISABLE_AUTOUPDATER='1', CLAUDE_CODE_DISABLE_AUTO_MEMORY='1',
                CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1')


def bounded_run(argv, *, payload=b'', cwd, env, timeout=60, limit=300000):
    """One process group; reject timeout/overflow even after partial output."""
    started = monotonic()
    # A regular input file avoids deadlocking while writing a full schema into
    # stdin before draining a provider's output.
    with tempfile.TemporaryFile() as incoming:
        incoming.write(payload); incoming.seek(0)
        process = subprocess.Popen(argv, stdin=incoming, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, cwd=cwd, env=env, start_new_session=True)
        chunks = {process.stdout:bytearray(), process.stderr:bytearray()}
        try:
            with selectors.DefaultSelector() as poll:
                for pipe in chunks:
                    poll.register(pipe, selectors.EVENT_READ)
                while poll.get_map():
                    remaining = timeout - (monotonic() - started)
                    if remaining <= 0:
                        raise TimeoutError('Public provider timed out; partial output refused; no retry.')
                    for key, _ in poll.select(min(remaining, .1)):
                        piece = os.read(key.fileobj.fileno(), 65536)
                        if not piece:
                            poll.unregister(key.fileobj)
                        else:
                            chunks[key.fileobj].extend(piece)
                            if sum(map(len, chunks.values())) > limit:
                                raise ValueError('Public provider output exceeded its byte limit.')
                process.wait(timeout=max(.001, timeout-(monotonic()-started)))
        finally:
            # Reap children even if the leader has exited and a child holds a
            # pipe open. Helpers may not survive either success or failure.
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            process.wait()
            for pipe in chunks: pipe.close()
        return process.returncode, bytes(chunks[process.stdout]), bytes(chunks[process.stderr])


def metadata_inventory():
    """No config, memory, credential, or transcript content is read."""
    home = Path.home()
    roots = {'user':home/'.claude', 'policy_mac':Path('/Library/Application Support/ClaudeCode'),
             'policy_linux':Path('/etc/claude-code')}
    records = {}
    for label, root in roots.items():
        paths = [root] + list(root.rglob('*')) if root.is_dir() else [root]
        for path in paths:
            try:
                stat = path.lstat()
            except FileNotFoundError:
                continue
            relative = str(path.relative_to(root)) if path != root else '.'
            records[label+'/'+relative] = (stat.st_size, stat.st_mtime_ns, path.is_dir())
    # Receipts expose classes/counts/hashes, not private filenames or contents.
    return records


def inventory_receipt(records):
    encoded = json.dumps(records,sort_keys=True,separators=(',',':')).encode()
    return dict(metadata_sha256=digest(encoded),entry_count=len(records),content_read=False,
                user_claude_md_present='user/CLAUDE.md' in records,
                user_settings_present='user/settings.json' in records,
                policy_present=any(k.startswith('policy_') for k in records),
                user_scope_suppression='NOT_ESTABLISHED')


def persistence_delta(before, after, cwd):
    # Other concurrently running consultations may write their own files. Only
    # attribute files under the uniquely owned cwd's project key to this run.
    project_key = str(Path(cwd).resolve()).replace('/', '-')
    prefix = 'user/projects/'+project_key
    changed = [k for k,v in after.items() if before.get(k)!=v and k.startswith(prefix)]
    return dict(project_entries_changed=len(changed),
                changed_path_hashes=[digest(k.encode()) for k in sorted(changed)],
                all_metadata_changed=sum(before.get(k)!=v for k,v in after.items()),
                scope='owned-cwd project metadata; other sessions not attributed')


class SafePublicClaude:
    """Default-disabled caller must manifest this exact profile before use."""
    def __init__(self, executable, *, model, system):
        self.executable = str(Path(executable).resolve(strict=True))
        self.model, self.system, self.env = model, system, public_environment()
        binary_sha = digest(Path(self.executable).read_bytes())
        with tempfile.TemporaryDirectory(prefix='uptime-public-pin-') as empty:
            code, help_bytes, _ = bounded_run([self.executable,'--help'],cwd=empty,env=self.env,timeout=10)
            version_code, version, _ = bounded_run([self.executable,'--version'],cwd=empty,env=self.env,timeout=10)
        if code or version_code or b'--safe-mode' not in help_bytes or b'--tools' not in help_bytes:
            raise ValueError('Pinned CLI help does not support the public profile.')
        self.argv = [self.executable,'-p','--safe-mode','--model',model,'--tools','',
                     '--strict-mcp-config','--mcp-config','{"mcpServers":{}}',
                     '--disable-slash-commands','--no-chrome','--max-budget-usd','1.00',
                     '--system-prompt-snapshot','off','--setting-sources','','--no-session-persistence',
                     '--system-prompt',system,'--output-format','stream-json','--verbose']
        self.profile = dict(name='safe-public-experimental-v2',binary_sha256=binary_sha,
                            help_sha256=digest(help_bytes),version=version.decode().strip(),
                            argv=['<pinned-executable>']+self.argv[1:],
                            environment_keys=sorted(self.env),environment_sha256=digest(json.dumps(self.env,sort_keys=True).encode()),
                            cwd='fresh-owned-temporary-directory',timeout_seconds=60,output_limit_bytes=300000,
                            retry_count=0,receipt_scope='adapter-supplied content/settings only',
                            user_scope_suppression='NOT_ESTABLISHED',customer_processing=False)
        self.last_receipt = None
        self.blocked = False
        self._verify_binary()

    def _verify_binary(self):
        if digest(Path(self.executable).read_bytes()) != self.profile['binary_sha256']:
            raise ValueError('The CLI binary changed after profile pinning.')

    def __call__(self, request):
        if self.blocked:
            raise PermissionError('This transport was blocked by a prior control failure.')
        self._verify_binary()
        value=json.loads(request)
        if value.get('transport')!=self.profile or value['model']!=self.model or value['system']!=self.system or value['tools']!=[]:
            raise ValueError('Unexpected or unmanifested public invocation settings.')
        with tempfile.TemporaryDirectory(prefix='uptime-public-request-') as empty:
            before=metadata_inventory()
            try:
                code, output, error=bounded_run(self.argv,payload=request,cwd=empty,env=self.env)
            finally:
                after=metadata_inventory()
                delta=persistence_delta(before,after,empty)
                self.last_receipt=dict(profile=self.profile,before=inventory_receipt(before),after=inventory_receipt(after),persistence=delta)
                if delta['project_entries_changed']:
                    self.blocked=True
            if self.blocked:
                raise ValueError('Unexpected owned-project persistence; further calls blocked.')
        self._verify_binary()
        self.last_receipt.update(output_sha256=digest(output),stderr_sha256=digest(error),returncode=code)
        if code:
            raise ValueError('The public proposal provider failed; no retry was attempted.')
        events=[json.loads(line) for line in output.splitlines() if line.strip()]
        init=[e for e in events if e.get('type')=='system' and e.get('subtype')=='init']
        tool_events=[part for e in events for part in e.get('message',{}).get('content',[]) if isinstance(part,dict) and part.get('type')=='tool_use']
        if len(init)!=1 or init[0].get('tools')!=[] or init[0].get('mcp_servers')!=[] or tool_events:
            self.blocked=True
            raise ValueError('Unexpected tool/MCP capability or use; further calls blocked.')
        results=[e for e in events if e.get('type')=='result']
        if len(results)!=1 or results[0].get('is_error') is not False or self.model not in results[0].get('modelUsage',{}):
            raise ValueError('The actual proposal provider identity could not be verified.')
        result=results[0]
        self.last_receipt.update(tool_events=0,tool_inventory=[],mcp_inventory=[],client_reported_cost_usd=result.get('total_cost_usd'),hard_cost_cap=False,
                                 model=self.model,session=result.get('session_id'),usage=result.get('usage'),
                                 result_sha256=digest(result.get('result','').encode()))
        return dict(model=self.model,text=result['result'],usage=result.get('usage'),session=result.get('session_id'),cost_usd=result.get('total_cost_usd'),transport=self.last_receipt)
