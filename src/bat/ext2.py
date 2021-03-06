## Binary Analysis Tool
## Copyright 2009-2013 Armijn Hemel for Tjaldur Software Governance Solutions
## Licensed under Apache 2.0, see LICENSE file for details

import sys, os, subprocess, tempfile

'''
Module to 'unpack' an ext2 file system. We are taking a shortcut. We're using
e2cp to copy files, but we're recreating the directories in the file system
ourselves. We can get this information from the output of el2s.

The second column displays the Ext2/linux mode flags which can be found in
<ext2fs/ext2fs.h> from e2fsprogs.

We are mostly interested in regular files and directories:

#define LINUX_S_IFREG  0100000
#define LINUX_S_IFDIR  0040000
'''

def copydir(source, fspath, target):
	(scandirs, scanfiles) = readfiles(source, fspath)
	if scandirs == [] and scanfiles == []:
		return None
	for scandir in scandirs:
		os.mkdir(target + "/" + scandir)
		copydir(source, fspath + "/" + scandir, target + "/" + scandir)
	for scanfile in scanfiles:
		p = subprocess.Popen(['e2cp', source + ":" + fspath + "/" + scanfile, "-d", target], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
        	(stanout, stanerr) = p.communicate()
        	if p.returncode != 0:
			continue
	return target

def copyext2fs(source, target=None):
	if target == None:
		targetdir = tempfile.mkdtemp()
	else:
		targetdir = target
	res = copydir(source, "", targetdir)
	if res != None:
		return targetdir

def readfiles(source, fspath):
	files = []
	dirs = []
	p = subprocess.Popen(['e2ls', '-l', source + ":" + fspath], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
        (stanout, stanerr) = p.communicate()
        if p.returncode != 0:
		return (dirs, files)
	if stanout.strip() == "No files found!":
		return (dirs, files)
	for i in stanout.strip().split("\n"):
		if i.startswith(">"):
			continue
		isplits = i.split()
		if len(isplits[1]) < 5:
			## bogus file system, so continue
			return ([], [])
		modeflag = int(isplits[1][0:-3])
		if len(isplits) < 8:
			continue
		else:
			filename = isplits[7]
		if modeflag == 40:
			dirs.append(filename)
		## also take sticky bit, suid, sgid, etc. into account
		elif modeflag >= 100 and modeflag < 120:
			files.append(filename)
	return (dirs, files)
