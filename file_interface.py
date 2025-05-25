import os
import json
import base64
from glob import glob


class FileInterface:
    def _init_(self):
        os.chdir('files/')

    def list(self,params=[]):
        try:
            filelist = glob('.')
            return dict(status='OK',data=filelist)
        except Exception as e:
            return dict(status='ERROR',data=str(e))

    def get(self,params=[]):
        try:
            filename = params[0]
            if (filename == ''):
                return None
            fp = open(f"{filename}",'rb')
            isifile = base64.b64encode(fp.read()).decode()
            return dict(status='OK',data_namafile=filename,data_file=isifile)
        except Exception as e:
            return dict(status='ERROR',data=str(e))
    def upload(self, params=[]):
        try:
            filename = params[0]
            filedata_base64 = params[1]
            filedata_bytes = base64.b64decode(filedata_base64)
            with open(filename, 'wb') as f:
                f.write(filedata_bytes)
            return dict(status='OK', data=f"File {filename} berhasil diupload")
        except Exception as e:
            return dict(status='ERROR', data=str(e))

    def delete(self, params=[]):
        try:
            filename = params[0]
            if not os.path.exists(filename):
                return dict(status='ERROR', data='File tidak ditemukan')
            os.remove(filename)
            return dict(status='OK', data=f"File {filename} berhasil dihapus")
        except Exception as e:
            return dict(status='ERROR', data=str(e))
