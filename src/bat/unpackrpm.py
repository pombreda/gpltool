#!/usr/bin/python

## Binary Analysis Tool
## Copyright 2009-2013 Armijn Hemel for Tjaldur Software Governance Solutions
## Licensed under Apache 2.0, see LICENSE file for details

'''
This module contains only code specific to RPM unpacking. This is so we don't get
failures on systems that don't have the Python RPM bindings installed.
'''

import sys, os, subprocess, os.path
import tempfile, magic, rpm
import extractor, fwunpack

def unpackRPM(filename, offset, tempdir=None):
	## Assumes (for now) that rpm2cpio is in the path
	tmpdir = fwunpack.unpacksetup(tempdir)
	tmpfile = tempfile.mkstemp(dir=tmpdir)
	os.fdopen(tmpfile[0]).close()

	fwunpack.unpackFile(filename, offset, tmpfile[1], tempdir)

	## first use rpm2cpio to unpack the rpm data
	p = subprocess.Popen(['rpm2cpio', tmpfile[1]], stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
	(stanout, stanerr) = p.communicate()
	if len(stanout) != 0:
		## cleanup first
                os.unlink(tmpfile[1])
		if tempdir == None:
                	os.rmdir(tmpdir)
		## then use unpackCpio() to unpack the RPM
		return fwunpack.unpackCpio(stanout, 0, tempdir)
	else:
                os.unlink(tmpfile[1])
		if tempdir == None:
                	os.rmdir(tmpdir)
		return None

## RPM is basically a header, plus some compressed files, so we might get
## duplicates at the moment. We can defeat this easily by setting the blacklist
## upperbound to the start of compression + 1. This is ugly and should actually
## be fixed.
def searchUnpackRPM(filename, tempdir=None, blacklist=[], offsets={}, scanenv={}, debug=False):
	hints = []
	if not offsets.has_key('rpm'):
		return ([], blacklist, [], hints)
	if offsets['rpm'] == []:
		return ([], blacklist, [], hints)
	diroffsets = []
	rpmcounter = 1
	for offset in offsets['rpm']:
		blacklistoffset = extractor.inblacklist(offset, blacklist)
		if blacklistoffset != None:
			continue
		tmpdir = fwunpack.dirsetup(tempdir, filename, "rpm", rpmcounter)
		res = unpackRPM(filename, offset, tmpdir)
		if res != None:
			diroffsets.append((res, offset, 0))
			rpmcounter = rpmcounter + 1
			## determine which compression is used, so we can
			## find the right offset for the blacklist. Code from the
			## RPM examples.
			tset = rpm.TransactionSet()
			tset.setVSFlags(rpm._RPMVSF_NOSIGNATURES)
        		fdno = os.open(filename, os.O_RDONLY)
        		header = tset.hdrFromFdno(fdno)
        		os.close(fdno)
			## first some sanity checks. payload format should
			## always be 'cpio' according to LSB 3
			if header[rpm.RPMTAG_PAYLOADFORMAT] == 'cpio':
				## compression should always be 'gzip' according to LSB 3
				## but can also be 'xz' on Fedora 15 and later
				## We actually can get payloadoffset from offsets
				## This will only work if offsets actually contains values
				## for these compressions, so they should be added as 'magic'
				## to the configuration for RPM.
				compressor = header[rpm.RPMTAG_PAYLOADCOMPRESSOR]
				if compressor == 'gzip':
					## this should not happen
					if not offsets.has_key('gzip'):
						pass
					else:
						for o in offsets['gzip']:
							if offset > o:
								continue
							else:
								payloadoffset = o
								break
				elif compressor == 'xz':
					## this should not happen
					if not offsets.has_key('xz') and not offsets.has_key('xztrailer'):
						pass
					else:
						for o in offsets['xz']:
							if offset > o:
								continue
							else:
								payloadoffset = o
								break
				try:
					## this header describes the size of headers +
					## compressed payload size. It might be a few bytes off
					## with the actual size of the file.
					bl = header[rpm.RPMTAG_SIGSIZE]
					filesize = os.stat(filename).st_size
					## sanity check. It should not happen with a properly
					## formatted RPM file, but you never know.
					if bl > filesize:
						bl = payloadoffset + 1
				except:
					bl = payloadoffset + 1
				blacklist.append((offset, bl))
		else:
			## cleanup
			os.rmdir(tmpdir)
	return (diroffsets, blacklist, [], hints)
