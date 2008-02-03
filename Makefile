
afloat-start:
	echo Starting afloat
	twistd --pid afloat.pid afloat --interface 127.0.0.1 --prepath 44cc

afloat-stop:
	echo Stopping afloat
	-kill `cat afloat.pid`

