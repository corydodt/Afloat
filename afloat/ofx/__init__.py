"""
Negotiating the network protocol and file format of OFX
"""


if __name__ == '__main__':
    import sys
    from afloat.ofx import get, parse
    import tempfile
    import shutil
    if len(sys.argv) > 1:
        tempdir = sys.argv[1]
        reloading = 1
    else:
        tempdir = tempfile.mkdtemp()
        reloading = 0

    try:
        if not reloading:
            get.run(['get', '--outdir', tempdir, 'EECU', '11340704', 
                '11340704=8', '1', ])
        parse.run(['parse', tempdir])
    finally:
        shutil.rmtree(tempdir)
