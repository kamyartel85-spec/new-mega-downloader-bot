import re
import io
import json
import base64
import struct
import queue
import aiohttp
from Crypto.Cipher import AES
from Crypto.Util import Counter

def makebyte(x): return x.encode('latin-1') if isinstance(x, str) else x
def makestring(x): return x.decode('latin-1') if isinstance(x, bytes) else x
def str_to_a32(b):
    b = makebyte(b)
    if len(b) % 4: b += b'\0' * (4 - len(b) % 4)
    return struct.unpack(">%dI" % (len(b) / 4), b)
def base64_url_decode(data):
    data += "=="[(2 - len(data) * 3) % 4:]
    data = re.sub(r"[-_,]", lambda x: {"-": "+", "_": "/", ",": ""}[x.group()], data)
    return base64.b64decode(data)
def base64_to_a32(s): return str_to_a32(base64_url_decode(s))
def aes_cbc_decrypt(data, key):
    aes_cipher = AES.new(key, AES.MODE_CBC, makebyte("\0" * 16))
    return aes_cipher.decrypt(data)
def a32_to_str(a): return struct.pack(">%dI" % len(a), *a)
def decrypt_attr(attr, key):
    attr = aes_cbc_decrypt(attr, a32_to_str(key))
    attr = makestring(attr)
    attr = attr.rstrip("\0")
    return json.loads(attr[4:]) if attr[:6] == 'MEGA{"' else False

def human_bytes(size: int) -> str:
    if not size: return "0 B"
    power = 1024
    n = 0
    dic_powerN = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB'}
    while size > power and n < 3:
        size /= power
        n += 1
    return f"{round(size, 2)} {dic_powerN[n]}"

class StreamQueueFile(io.RawIOBase):
    def __init__(self, size, name):
        self.size = size
        self.name = name
        self.q = queue.Queue(maxsize=15)
        self.pos = 0
        self.buffer = b""
        self._tell = 0
        self.closed = False

    def read(self, n=-1):
        if self.closed:
            return b""
        if n == -1:
            n = self.size - self.pos
        
        while len(self.buffer) < n and self.pos < self.size:
            try:
                chunk = self.q.get(timeout=60)
                if chunk is None:
                    break
                self.buffer += chunk
            except queue.Empty:
                break
        
        res = self.buffer[:n]
        self.buffer = self.buffer[n:]
        self.pos += len(res)
        return res

    def seek(self, offset, whence=0):
        if whence == 2:
            self._tell = self.size
        elif whence == 0:
            self._tell = 0
        return self._tell

    def tell(self):
        return self._tell

    def close(self):
        self.closed = True

    def fileno(self):
        raise OSError("Not a real file")

class MegaTools:
    @staticmethod
    async def get_download_info(url: str):
        regex = re.search(r"https://mega\.nz/(?:file/([0-z-_]+)#|#!([0-z-_]+)!)([0-z-_]+)", url)
        if not regex:
            raise Exception("فقط لینک‌های پابلیک فایل تکی (بدون پوشه) پشتیبانی می‌شود.")
            
        file_id = regex.group(1) or regex.group(2)
        file_key = regex.group(3)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://g.api.mega.co.nz/cs",
                json=[{"a": "g", "g": 1, "p": file_id}],
            ) as resp:
                data = (await resp.json())[0]

        if "e" in data:
            raise Exception(f"خطای MEGA API: {data['e']}")

        key = base64_to_a32(file_key)
        tk = (key[0] ^ key[4], key[1] ^ key[5], key[2] ^ key[6], key[3] ^ key[7])
        fsize = data["s"]
        fname = decrypt_attr(base64_url_decode(data["at"]), tk)["n"]
        dl_url = data["g"]

        return fsize, fname, dl_url, tk, key

    @staticmethod
    async def stream_download(dl_url, fsize, tk, key, stream: StreamQueueFile):
        key_bytes = struct.pack(">IIII", *tk)
        iv_bytes = struct.pack(">II", key[4], key[5])
        
        initial_value = int.from_bytes(iv_bytes + b"\0\0\0\0\0\0\0\0", byteorder='big')
        ctr = Counter.new(128, initial_value=initial_value)
        cipher = AES.new(key_bytes, AES.MODE_CTR, counter=ctr)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(dl_url) as resp:
                    async for chunk in resp.content.iter_chunked(1024 * 1024):
                        if stream.closed:
                            break
                        stream.q.put(cipher.decrypt(chunk))
        except Exception as e:
            print(f"Download stream error: {e}")
        finally:
            stream.q.put(None)
