"""
Negotiating the network protocol and file format of OFX
"""


if __name__ == '__main__':
    from afloat.ofx import get, parse

    getter = get.Options()
    getter.parseOptions([])
    out = getter['out']
    parser = parse.Options()
    parser['stream'] = out
    parser.parseOptions([])
