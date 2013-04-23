#!/usr/bin/python

'''
Yaffs2 unpacker reimplemention, heavily borrowing from unyaffs created
by Kai Wei

(C) 2013 Armijn Hemel, Tjaldur Software Governance Solutions

 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2 as
 * published by the Free Software Foundation.

'''

import sys, os, os.path, struct
from optparse import OptionParser


## some hardcoded settings copied from unyaffs.c and unyaffs.h
## In other devices these settings are actually different
YAFFS_OBJECTID_ROOT=1
YAFFS_MAX_NAME_LENGTH=255
YAFFS_MAX_ALIAS_LENGTH=159

YAFFS_OBJECT_TYPE_UNKNOWN = 0
YAFFS_OBJECT_TYPE_FILE = 1
YAFFS_OBJECT_TYPE_SYMLINK = 2
YAFFS_OBJECT_TYPE_DIRECTORY = 3
YAFFS_OBJECT_TYPE_HARDLINK = 4
YAFFS_OBJECT_TYPE_SPECIAL = 5

def main(argv):
	parser = OptionParser()
	parser.add_option("-b", "--binary", action="store", dest="yaffs2file", help="path to binary file", metavar="FILE")
	parser.add_option("-d", "--directory", action="store", dest="unpackdir", help="path to unpacking directory", metavar="DIR")
	parser.add_option("-v", "--verbose", action="store_true", dest="verbose", help="verbose output")
	(options, args) = parser.parse_args()

	if options.yaffs2file == None:
		parser.error("Path to yaffs2 file needed")
	elif not os.path.exists(options.yaffs2file):
		parser.error("yaffs2 file does not exist")
	else:
		yaffs2file = options.yaffs2file

	if options.unpackdir == None:
		parser.error("Path to unpack directory needed")
	elif not os.path.exists(options.unpackdir):
		parser.error("unpack directory does not exist")
	if os.listdir(options.unpackdir) != []:
		parser.error("unpack directory %s not empty" % options.unpackdir)
	else:
		unpackdir = options.unpackdir

	yaffs2filesize = os.stat(yaffs2file).st_size

	#chunksandspares = [(2048,64), (1024,64)]
	chunksandspares = [(2048,64)]
	possibleyaffs = False

	for cs in chunksandspares:
		(CHUNK_SIZE, SPARE_SIZE) = cs
		if yaffs2filesize%(CHUNK_SIZE + SPARE_SIZE) == 0:
			possibleyaffs = True
			break

	if not possibleyaffs:
		if options.verbose:
			print >>sys.stderr, "not a valid YAFFS2 image"
		sys.exit(1)

	image_file = open(yaffs2file)

	image_file.seek(0)

	yaffsunpacked = False
	for cs in chunksandspares:
		if yaffsunpacked:
			break
		(CHUNK_SIZE, SPARE_SIZE) = cs
		bytesread = 0
		yaffsunpackfail = False

		objectidtoname = {}
		objectidtofullname = {}
		objectparent = {}
		outfile = None

		## read in the blocks of data
		while not bytesread >= yaffs2filesize and not yaffsunpackfail:
			chunkdata = image_file.read(CHUNK_SIZE)
			sparedata = image_file.read(SPARE_SIZE)

			## read in the spare data first and extract some metadata
			sequenceNumber = struct.unpack('<L', sparedata[0:4])[0]
			objectId = struct.unpack('<L', sparedata[4:8])[0]
			chunkId = struct.unpack('<L', sparedata[8:12])[0]
			byteCount = struct.unpack('<L', sparedata[12:16])[0]

			if byteCount > 0xffff:
				yaffsunpackfail = True
				break

			## check if the file is a new file
			if byteCount == 0xffff:
				if outfile != None:
					outfile.close()
				offset = 0
				oid = objectId
				## new file, so process the chunk data
				## first read in the object header
				chunktype = struct.unpack('<L', chunkdata[offset:offset+4])[0]
				offset = offset + 4

				## unused checksum, can be ignored
				parentObjectId = struct.unpack('<L', chunkdata[offset:offset+4])[0]
				offset = offset + 4

				## store the parent id for this object, so it can be retrieved later
				objectparent[objectId] = parentObjectId

				## unused checksum, can be ignored
				checksum = struct.unpack('<H', chunkdata[offset:offset+2])[0]
				offset = offset + 2

				## extract the name, up to the first '\x00' character
				## and store it
				yaffsname = chunkdata[offset:offset+YAFFS_MAX_NAME_LENGTH+1+2]
				eoname = yaffsname.find('\x00')
				yaffsname=yaffsname[:eoname]
				objectidtoname[objectId] = yaffsname
				offset = offset + YAFFS_MAX_NAME_LENGTH + 1 + 2

				## reconstruct the full path
				if objectId != 1 and objectidtoname.has_key(parentObjectId) and objectId != parentObjectId:
					objectpath = yaffsname
					newparentid = parentObjectId
					while newparentid != 1:
						yaffsname = os.path.join(objectidtoname[newparentid], yaffsname)
						newparentid = objectparent[newparentid]
					objectidtofullname[objectId] = yaffsname
					if options.verbose:
						print "unpacking", yaffsname

				yst_mode = struct.unpack('<L', chunkdata[offset:offset+4])[0]
				offset = offset + 4

				yst_uid = struct.unpack('<L', chunkdata[offset:offset+4])[0]
				offset = offset + 4

				yst_gid = struct.unpack('<L', chunkdata[offset:offset+4])[0]
				offset = offset + 4

				yst_atime = struct.unpack('<L', chunkdata[offset:offset+4])[0]
				offset = offset + 4

				yst_mtime = struct.unpack('<L', chunkdata[offset:offset+4])[0]
				offset = offset + 4

				yst_ctime = struct.unpack('<L', chunkdata[offset:offset+4])[0]
				offset = offset + 4

				fileSize = struct.unpack('<L', chunkdata[offset:offset+4])[0]
				offset = offset + 4

				equivalentObjectId = struct.unpack('<L', chunkdata[offset:offset+4])[0]
				offset = offset + 4

				## extract the alias, up to the first '\x00' character
				## and store it
				aliasname = chunkdata[offset:offset+YAFFS_MAX_ALIAS_LENGTH+1]
				eoname = aliasname.find('\x00')
				if eoname != -1:
					aliasname = aliasname[:eoname]
				else:
					aliasname = None
				offset = offset + YAFFS_MAX_ALIAS_LENGTH + 1

				if chunktype == YAFFS_OBJECT_TYPE_FILE:
					outname = os.path.join(unpackdir, yaffsname)
					outfile = open(outname, 'wb')
				elif chunktype == YAFFS_OBJECT_TYPE_SYMLINK:
					if aliasname != None:
						symlink = os.path.join(unpackdir, yaffsname)
						os.symlink(aliasname, symlink)
				elif chunktype == YAFFS_OBJECT_TYPE_DIRECTORY:
					## create the directory and move on
					createdir = os.path.join(unpackdir, yaffsname)
					try:
						os.makedirs(createdir)
					except:
						pass
					yaffsunpacked = True
				elif chunktype == YAFFS_OBJECT_TYPE_HARDLINK:
					## create a hard link.
					## TODO: more sanity checks
					linkname = os.path.join(unpackdir, yaffsname)
					os.link(os.path.join(unpackdir, objectidtofullname[equivalentObjectId]), linkname)
				elif chunktype == YAFFS_OBJECT_TYPE_SPECIAL:
					print "CHUNK special"
				else:
					print "CHUNK unknown"
					yaffsunpackfail = True
			else:
				## block with data, just write the chunkdata to the output file
				if outfile != None:
					outfile.write(chunkdata[:byteCount])

			## move on to the next chunk
			bytesread = bytesread + len(chunkdata) + len(sparedata)

		if outfile != None:
			outfile.close()
	image_file.close()

	if not yaffsunpacked:
		if options.verbose:
			print >>sys.stderr, "YAFFS2 image could not be unpacked"
		sys.exit(1)

if __name__ == "__main__":
	main(sys.argv)
