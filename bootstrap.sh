#!/bin/bash
## Bootstrap setup for afloat

cat <<EOF
:: This script will check your environment to make sure Afloat is
:: ready to run, and do any one-time setup steps necessary.
::
:: Please check for any errors below, and fix them.
EOF

export errorStatus=""

function testCommand()
# Use: testPython "Software name" "python code"
#  If "python code" has no output, we pass.
# 
#  If there is any output, the last line is considered an error message, and
#  we print it.  Then we set the global errorStatus.
# 
#  "python code" should not write to stderr if possible, so use 2>&1 to
#  redirect to stdout.
{
    software="$1"
    line=$(which $software)

    if [ ! -x "$line" ]; then
        echo "** Install $software ($line)"
        errorStatus="error"
    else
        echo "OK $software"
    fi
}

function testPython()
# Use: testPython "Software name" "python code"
#  If "python code" has no output, we pass.
# 
#  If there is any output, the last line is considered an error message, and
#  we print it.  Then we set the global errorStatus.
# 
#  "python code" should not write to stderr if possible, so use 2>&1 to
#  redirect to stdout.
{
    software="$1"
    line=$(python -Wignore -c "$2" 2>&1 | tail -1)

    if [ -n "$line" ]; then
        echo "** Install $software ($line)"
        errorStatus="error"
    else
        echo "OK $software"
    fi
}

testPython "zope.interface" 'import zope.interface'
t="from twisted import __version__ as v; assert v>='2.5.0', 'Have %s' % (v,)"
testPython "Twisted 2.5" "$t"
testPython "Divmod Nevow" 'import nevow'
testPython "Python 2.5" 'import xml.etree'
testPython "Storm" 'from storm.locals import *'
testPython "SQLite 3" 'import sqlite3'
testPython "SimpleParse 2.1" 'import simpleparse; import afloat.gvent.parsetxn'
testPython "GData API" 'import atom; import gdata'

if [ "$errorStatus" == "error" ]; then
    echo "** Errors occurred.  Please fix the above errors, then re-run this script."
    exit 1
fi

if [ ! -e "afloat/afloat.db" ]; then
    python afloat/database.py
    echo "Wrote afloat/afloat.db"
fi

echo "Done."

