"""One-time OAuth setup over a localhost SSH tunnel. Never prints credentials."""
import argparse
import configparser
import io
import json
from pathlib import Path
import re
import select
import socketserver
import threading
import time
import webbrowser

import paramiko


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--host', default='raspberrypi.local')
    parser.add_argument('--port', type=int, default=22)
    parser.add_argument('--user', default='pi')
    parser.add_argument('--ssh-secret-file', type=Path)
    parser.add_argument('--key-file', type=Path)
    parser.add_argument('--remote-config-dir', default=None)
    parser.add_argument('--client-json', type=Path, required=True)
    args=parser.parse_args()
    if not args.ssh_secret_file and not args.key_file:
        parser.error('Provide either --key-file or --ssh-secret-file')
    credentials=json.loads(args.client_json.read_text(encoding='utf-8'))['installed']
    client=paramiko.SSHClient()
    client.load_host_keys(str(Path.home()/'.ssh'/'known_hosts'))
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    connect_kwargs={'port':args.port,'username':args.user,'timeout':15}
    if args.key_file:
        connect_kwargs.update({'key_filename':str(args.key_file),'look_for_keys':False,'allow_agent':False})
    else:
        connect_kwargs.update({'password':args.ssh_secret_file.read_text().strip(),'look_for_keys':False,'allow_agent':False})
    client.connect(args.host,**connect_kwargs)
    transport=client.get_transport()
    transport.set_keepalive(30)

    class Tunnel(socketserver.BaseRequestHandler):
        def handle(self):
            try:
                channel=transport.open_channel('direct-tcpip',('127.0.0.1',53682),self.client_address)
            except paramiko.SSHException:
                return  # Browser may request a favicon after OAuth listener closes.
            try:
                while True:
                    ready,_,_=select.select([self.request,channel],[],[],30)
                    for source in ready:
                        data=source.recv(65536)
                        if not data:return
                        (channel if source is self.request else self.request).sendall(data)
            finally:channel.close()

    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address=True
        daemon_threads=True

    try:
        with Server(('127.0.0.1',53682),Tunnel) as server:
            threading.Thread(target=server.serve_forever,daemon=True).start()
            sftp=client.open_sftp()
            home_dir=f'/home/{args.user}' if args.user != 'root' else '/root'
            folder=args.remote_config_dir or f'{home_dir}/.config/rclone'
            parent=folder.rsplit('/',1)[0]
            for name in [parent,folder]:
                try:sftp.mkdir(name,0o700)
                except IOError:pass
            config=configparser.RawConfigParser()
            path=folder+'/rclone.conf'
            try:
                with sftp.open(path) as stream:config.read_string(stream.read().decode())
            except FileNotFoundError:pass
            if config.has_option('iqairdrive','token'):
                raise RuntimeError('Remote already authorized; refusing to replace credentials')
            config['iqairdrive']={'type':'drive','scope':'drive.file',
                'client_id':credentials['client_id'],'client_secret':credentials['client_secret']}
            output=io.StringIO();config.write(output)
            with sftp.open(path,'w') as stream:
                sftp.chmod(path,0o600)
                stream.write(output.getvalue())
            print('OAuth client configured privately; waiting for browser authorization.',flush=True)
            _,stdout,stderr=client.exec_command('timeout 900 rclone config reconnect iqairdrive: --auto-confirm',timeout=920)
            channel=stdout.channel
            buffer='';opened=False;deadline=time.monotonic()+900
            while time.monotonic()<deadline:
                for ready,read in [(channel.recv_ready,channel.recv),(channel.recv_stderr_ready,channel.recv_stderr)]:
                    if ready():
                        buffer+=read(8192).decode(errors='replace')
                if not opened:
                    match=re.search(r'http://127\.0\.0\.1:53682/auth\?state=[A-Za-z0-9_\-]+',buffer)
                    if match:
                        url=match.group(0)
                        print('GOOGLE_LOGIN_URL='+url,flush=True)
                        webbrowser.open(url)
                        opened=True
                # Output may contain token material; never dump the raw buffer.
                if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                    result=channel.recv_exit_status()
                    print('OAUTH_PROCESS_EXIT='+str(result),flush=True)
                    check=configparser.RawConfigParser()
                    with sftp.open(path) as stream:check.read_string(stream.read().decode())
                    ok=bool(check.get('iqairdrive','token',fallback='')) and result==0
                    print('DRIVE_AUTHORIZED='+str(ok),flush=True)
                    server.shutdown()
                    return 0 if ok else 2
                time.sleep(0.2)
            print('OAuth timeout; no sync activated.',flush=True)
            server.shutdown()
            return 2
    finally:client.close()


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        print('SETUP_ERROR='+type(exc).__name__,flush=True)
        raise SystemExit(2)
