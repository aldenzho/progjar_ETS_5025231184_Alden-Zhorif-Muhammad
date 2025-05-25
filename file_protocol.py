import json
import logging
import shlex

from file_interface import FileInterface

"""
* class FileProtocol bertugas untuk memproses 
data yang masuk, dan menerjemahkannya apakah sesuai dengan
protokol/aturan yang dibuat

* data yang masuk dari client adalah dalam bentuk bytes yang 
pada akhirnya akan diproses dalam bentuk string

* class FileProtocol akan memproses data yang masuk dalam bentuk
string
"""




class FileProtocol:
    def _init_(self):
        self.file = FileInterface()
    def proses_string(self, string_datamasuk=''):
        logging.warning(f"string diproses: {string_datamasuk}")
        try:
            c = shlex.split(string_datamasuk)
            if len(c) == 0:
                return json.dumps(dict(status='ERROR', data='request kosong'))
            c_request = c[0].lower()  
            logging.warning(f"memproses request: {c_request}")
            params = c[1:]
            cl = getattr(self.file, c_request)(params)
            return json.dumps(cl)
        except AttributeError:
            return json.dumps(dict(status='ERROR', data='request tidak dikenali'))
        except Exception as e:
            logging.error(f"error processing request: {str(e)}")
            return json.dumps(dict(status='ERROR', data=str(e)))

if _name=='main_':
    #contoh pemakaian
    fp = FileProtocol()
    print(fp.proses_string("LIST"))
    print(fp.proses_string("GET pokijan.jpg"))
