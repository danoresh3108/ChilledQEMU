"""Private local QMP/GDB connections for guest physical-memory tools."""
import json
import socket
from contextlib import contextmanager


class MemoryAccess:
    def __init__(self, directory):
        self.qmp_path = str(directory / 'qmp')
        self.gdb_path = str(directory / 'gdb')

    def arguments(self):
        return ['-qmp', f'unix:{self.qmp_path},server=on,wait=off',
                '-gdb', f'unix:{self.gdb_path},server=on,wait=off']

    @contextmanager
    def paused(self):
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(10)
            connection.connect(self.qmp_path)
            with connection.makefile('rwb') as stream:
                greeting = json.loads(stream.readline())
                if 'QMP' not in greeting:
                    raise RuntimeError('Invalid QMP greeting')

                def command(name, arguments=None):
                    request = {'execute': name}
                    if arguments is not None:
                        request['arguments'] = arguments
                    stream.write(json.dumps(request).encode() + b'\n')
                    stream.flush()
                    while True:
                        line = stream.readline()
                        if not line:
                            raise RuntimeError('QMP disconnected')
                        response = json.loads(line)
                        if 'error' in response:
                            raise RuntimeError(str(response['error']))
                        if 'return' in response:
                            return response['return']

                command('qmp_capabilities')
                running = command('query-status')['running']
                if running:
                    command('stop')
                try:
                    yield command
                finally:
                    if running:
                        command('cont')

    def dump(self, filename, address, size):
        with self.paused() as command:
            command('pmemsave', {'val': address, 'size': size, 'filename': str(filename)})

    def _packet(self, connection, payload):
        raw = payload.encode('ascii')
        connection.sendall(b'$' + raw + b'#' + f'{sum(raw) & 255:02x}'.encode())
        def byte():
            value = connection.recv(1)
            if not value:
                raise RuntimeError('GDB disconnected')
            return value
        while True:
            marker = byte()
            if marker == b'-':
                raise RuntimeError('GDB rejected packet checksum')
            if marker == b'$':
                break
        result = bytearray()
        while True:
            value = byte()
            if value == b'#':
                break
            result.extend(value)
            if len(result) > 65536:
                raise RuntimeError('GDB response is too large')
        checksum = byte() + byte()
        if int(checksum, 16) != sum(result) & 255:
            connection.sendall(b'-')
            raise RuntimeError('Invalid GDB checksum')
        connection.sendall(b'+')
        # RSP run-length encoding (some QEMU builds compress repeated bytes).
        decoded = bytearray()
        index = 0
        while index < len(result):
            value = result[index]
            if value == 42:
                index += 1
                if not decoded or index >= len(result):
                    raise RuntimeError('Invalid GDB run-length encoding')
                decoded.extend([decoded[-1]] * (result[index] - 29))
            else:
                decoded.append(value)
            index += 1
        response = decoded.decode('ascii')
        if not response or response.startswith('E'):
            raise RuntimeError(f'GDB memory operation failed: {response or "unsupported command"}')
        return response

    def access(self, address, size, data=None, expected=None):
        if address < 0 or size < 1 or size > 4096 or address + size > 2**64:
            raise ValueError('Address/size out of range (maximum 4096 bytes)')
        if data is not None and len(data) != size:
            raise ValueError('The replacement must have exactly the selected size')
        with self.paused():
            with socket.socket(socket.AF_UNIX) as connection:
                connection.settimeout(5)
                connection.connect(self.gdb_path)
                if self._packet(connection, 'Qqemu.PhyMemMode:1') != 'OK':
                    raise RuntimeError('Physical memory mode is unavailable')
                def read():
                    value = bytes.fromhex(self._packet(connection, f'm{address:x},{size:x}'))
                    if len(value) != size:
                        raise RuntimeError('Incomplete memory read')
                    return value
                before = read()
                if data is None:
                    return before
                if expected is not None and before != expected:
                    raise RuntimeError('Memory changed since it was opened; read the region again before editing')
                for offset in range(0, size, 256):
                    chunk = data[offset:offset + 256]
                    if self._packet(connection, f'M{address+offset:x},{len(chunk):x}:{chunk.hex()}') != 'OK':
                        raise RuntimeError('Memory write failed; the region may be partially changed')
                if read() != data:
                    raise RuntimeError('Memory verification failed; the region may be partially changed')
                return before
