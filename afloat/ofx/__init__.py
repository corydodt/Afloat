"""
Negotiating the network protocol and file format of OFX
"""

if __name__ == '__main__':
    from afloat.ofx import get, parse
    # o = get.optionsRun(['get', 'eecu', '11340704', '11340704', 'CHECKING'])
    o = {'outFilename': 'eecu20071020.ofx'}
    parse.run(['parse', o['outFilename']])
