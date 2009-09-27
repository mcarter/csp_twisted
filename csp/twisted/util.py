import zlib, struct, time

try:
    import json
except ImportError:
    import simplejson as json

# gzip from cherrypy
def _compress(body, compress_level):
    """Compress 'body' at the given compress_level."""
    
    yield '\037\213'      # magic header
    yield '\010'         # compression method
    yield '\0'
    yield struct.pack("<L", long(time.time()))
    yield '\002'
    yield '\377'
    
    crc = zlib.crc32("")
    size = 0
    zobj = zlib.compressobj(compress_level,
                            zlib.DEFLATED, -zlib.MAX_WBITS,
                            zlib.DEF_MEM_LEVEL, 0)
    for line in body:
        size += len(line)
        crc = zlib.crc32(line, crc)
        yield zobj.compress(line)
    yield zobj.flush()
    yield struct.pack("<l", crc)
    yield struct.pack("<L", size & 0xFFFFFFFFL)

def compress(body):
    return "".join([x for x in _compress(body, 6)])
