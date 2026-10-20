"""Small raw-RFB viewer for a private QEMU Unix VNC socket."""
import struct
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtNetwork import QLocalSocket
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QWidget


class GuestScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setMinimumSize(320, 240)
        self.socket = QLocalSocket(self)
        self.socket.readyRead.connect(self.receive)
        self.socket.errorOccurred.connect(lambda *_: self.update())
        self.timer = QTimer(self); self.timer.setInterval(100)
        self.timer.timeout.connect(self.request)
        self.buffer = bytearray(); self.state = 'version'
        self.image = QImage(); self.rectangles = 0; self.pending = False
        self.message = 'VM display'; self.keys = set()

    def connect_display(self, path):
        self.disconnect_display()
        self.buffer.clear(); self.state = 'version'; self.image = QImage()
        self.pending = False; self.rectangles = 0; self.message = 'Connecting…'
        self.connection_path = str(path)
        self._connect_when_ready(str(path), 50)
        self.update()

    def _connect_when_ready(self, path, attempts):
        if getattr(self, 'connection_path', None) != path: return
        if Path(path).exists(): self.socket.connectToServer(path)
        elif attempts:
            QTimer.singleShot(100, lambda: self._connect_when_ready(path, attempts-1))
        else:
            self.message = 'QEMU display socket not available'; self.update()

    def disconnect_display(self):
        self.connection_path = None
        self.timer.stop(); self.keys.clear(); self.socket.abort()
        self.message = 'VM display disconnected'; self.update()

    def take(self, count):
        data = bytes(self.buffer[:count]); del self.buffer[:count]; return data

    def receive(self):
        self.buffer.extend(bytes(self.socket.readAll()))
        try:
            while self.parse(): pass
        except (ValueError, struct.error) as exc:
            self.disconnect_display(); self.message = str(exc); self.update()

    def parse(self):
        b = self.buffer
        if self.state == 'version':
            if len(b) < 12: return False
            if self.take(12) != b'RFB 003.008\n': raise ValueError('Unsupported RFB version')
            self.socket.write(b'RFB 003.008\n'); self.state = 'security'
        elif self.state == 'security':
            if not b or len(b) < 1 + b[0]: return False
            count = self.take(1)[0]
            if not count or 1 not in self.take(count): raise ValueError('Private VNC requires no-auth security')
            self.socket.write(b'\x01'); self.state = 'auth'
        elif self.state == 'auth':
            if len(b) < 4: return False
            if self.take(4) != b'\0'*4: raise ValueError('VNC authentication failed')
            self.socket.write(b'\x01'); self.state = 'init'
        elif self.state == 'init':
            if len(b) < 24: return False
            length = struct.unpack('>I', b[20:24])[0]
            if length > 1024*1024: raise ValueError('VNC name too large')
            if len(b) < 24 + length: return False
            width, height = struct.unpack('>HH', self.take(4))
            self.take(20 + length); self.resize_image(width, height)
            # 32-bit little-endian RGB, compatible with QImage RGB32 on macOS/Linux.
            pixel = struct.pack('>BBBBHHHBBBxxx', 32, 24, 0, 1, 255, 255, 255, 16, 8, 0)
            self.socket.write(b'\0\0\0\0' + pixel)
            self.socket.write(struct.pack('>BBHii', 2, 0, 2, 0, -223))
            self.state = 'messages'; self.timer.start(); self.request(False)
        elif self.state == 'messages':
            if self.rectangles:
                if len(b) < 12: return False
                x,y,w,h,encoding = struct.unpack('>HHHHi', b[:12])
                if encoding == -223:
                    self.take(12); self.resize_image(w,h)
                elif encoding == 0:
                    if x+w > self.image.width() or y+h > self.image.height(): raise ValueError('Invalid VNC rectangle')
                    length = w*h*4
                    if len(b) < 12+length: return False
                    self.take(12); raw = self.take(length)
                    if w and h:
                        tile = QImage(raw,w,h,w*4,QImage.Format_RGB32)
                        painter = QPainter(self.image); painter.drawImage(x,y,tile); painter.end()
                else: raise ValueError('Unsupported VNC encoding')
                self.rectangles -= 1
                if not self.rectangles: self.pending = False; self.update()
            else:
                if not b: return False
                if b[0] == 0:
                    if len(b) < 4: return False
                    self.rectangles = struct.unpack('>H', b[2:4])[0]; self.take(4)
                    if not self.rectangles: self.pending = False
                elif b[0] == 2: self.take(1)
                elif b[0] == 3:
                    if len(b) < 8: return False
                    length = struct.unpack('>I', b[4:8])[0]
                    if length > 1024*1024: raise ValueError('VNC clipboard too large')
                    if len(b) < 8+length: return False
                    self.take(8+length)
                else: raise ValueError('Unsupported VNC message')
        return True

    def resize_image(self, width, height):
        if width < 1 or height < 1 or width*height > 16777216:
            raise ValueError('Invalid display size')
        self.image = QImage(width,height,QImage.Format_RGB32); self.image.fill(Qt.black)

    def request(self, incremental=True):
        if self.state != 'messages' or self.pending or self.image.isNull(): return
        self.socket.write(struct.pack('>BBHHHH',3,int(incremental),0,0,self.image.width(),self.image.height()))
        self.pending = True

    def paintEvent(self, event):
        painter = QPainter(self); painter.fillRect(self.rect(),Qt.black)
        if self.image.isNull():
            painter.setPen(Qt.white); painter.drawText(self.rect(),Qt.AlignCenter,self.message)
        else:
            size = self.image.size().scaled(self.size(),Qt.KeepAspectRatio)
            painter.drawImage((self.width()-size.width())//2,(self.height()-size.height())//2,
                self.image.scaled(size,Qt.KeepAspectRatio))

    def pointer(self, event):
        if self.state != 'messages' or self.image.isNull(): return
        size = self.image.size().scaled(self.size(),Qt.KeepAspectRatio)
        x = int((event.position().x()-(self.width()-size.width())/2)*self.image.width()/size.width())
        y = int((event.position().y()-(self.height()-size.height())/2)*self.image.height()/size.height())
        buttons = event.buttons()
        mask = (1 if buttons & Qt.LeftButton else 0) | (2 if buttons & Qt.MiddleButton else 0) | (4 if buttons & Qt.RightButton else 0)
        self.socket.write(struct.pack('>BBHH',5,mask,max(0,min(x,self.image.width()-1)),max(0,min(y,self.image.height()-1))))

    def mousePressEvent(self, event): self.setFocus(); self.pointer(event)
    def mouseReleaseEvent(self, event): self.pointer(event)
    def mouseMoveEvent(self, event): self.pointer(event)

    def key(self, event, pressed):
        mapping = {Qt.Key_Return:0xff0d, Qt.Key_Enter:0xff0d, Qt.Key_Escape:0xff1b,
            Qt.Key_Backspace:0xff08, Qt.Key_Tab:0xff09, Qt.Key_Delete:0xffff,
            Qt.Key_Left:0xff51, Qt.Key_Up:0xff52, Qt.Key_Right:0xff53, Qt.Key_Down:0xff54,
            Qt.Key_Shift:0xffe1, Qt.Key_Control:0xffe3, Qt.Key_Alt:0xffe9,
            Qt.Key_Home:0xff50, Qt.Key_End:0xff57, Qt.Key_PageUp:0xff55, Qt.Key_PageDown:0xff56}
        symbol = mapping.get(event.key())
        if Qt.Key_F1 <= event.key() <= Qt.Key_F12: symbol = 0xffbe+event.key()-Qt.Key_F1
        if symbol is None:
            symbol = event.key()
            if event.text() and event.text().isprintable():
                point = ord(event.text()[0]); symbol = point if point < 256 else 0x01000000|point
            elif 65 <= event.key() <= 90: symbol = ord(chr(event.key()).lower())
            else: return
        if not pressed: symbol = next((value for key,value in self.keys if key == event.key()),symbol)
        self.socket.write(struct.pack('>BBHI',4,int(pressed),0,symbol))
        if pressed: self.keys.add((event.key(),symbol))
        else: self.keys.discard((event.key(),symbol))

    def keyPressEvent(self, event): self.key(event,True)
    def keyReleaseEvent(self, event):
        if not event.isAutoRepeat(): self.key(event,False)

    def focusOutEvent(self, event):
        for _,symbol in self.keys: self.socket.write(struct.pack('>BBHI',4,0,0,symbol))
        self.keys.clear(); super().focusOutEvent(event)
