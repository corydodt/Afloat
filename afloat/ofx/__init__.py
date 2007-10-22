"""
Negotiating the network protocol and file format of OFX
"""


if __name__ == '__main__':
    from afloat.ofx import get, parse
    import tempfile
    import shutil
    tempdir = tempfile.mkdtemp()
    try:
        get.run(['get', '--outdir', tempdir, 'EECU', '11340704', 
            '11340704=8', '1', ])
        parse.run(['parse', tempdir + '/account.ofx'])
        parse.run(['parse', tempdir + '/statement.ofx'])
    finally:
        pass # shutil.rmtree(tempdir)
