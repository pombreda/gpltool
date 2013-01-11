#!/usr/bin/python

## Binary Analysis Tool
## Copyright 2013 Armijn Hemel for Tjaldur Software Governance Solutions
## Licensed under Apache 2.0, see LICENSE file for details

import os, os.path, sys, subprocess, copy

'''
This plugin is used to aggregate ranking results for Java JAR files.
The ranking scan only ranks individual class files, which often do not
contain enough information. By aggregating the results of these classes
it is possible to get a better view of what is inside a JAR.
'''

def aggregatejars(unpackreports, leafreports, scantempdir, envvars=None):
	## find all JAR files. Do this by:
	## 1. checking the tags for 'zip'
	## 2. verifying for unpacked files that there are .class files
	## 3. possibly verifying there is a META-INF directory with a manifest
	for i in unpackreports:
		classfiles = []
		if leafreports.has_key(i):
			## add a name check. TODO: make case insensitive
			if i.endswith('.jar'):
				if leafreports[i].has_key('tags'):
					## check if it was tagged as a ZIP file
					if 'zip' in leafreports[i]['tags']:
						## sanity checks
						if unpackreports[i]['scans'] != []:
							## since it was a single ZIP file there should be only
							## one item in unpackreports[i]['scan']
							if len(unpackreports[i]['scans']) != 1:
								continue
							## more sanity checks
							if unpackreports[i]['scans'][0]['offset'] != 0:
								continue
							if unpackreports[i]['scans'][0]['scanname'] != 'zip':
								continue
							classfiles = filter(lambda x: x.endswith('.class'), unpackreports[i]['scans'][0]['scanreports'])
		for c in classfiles:
			if not leafreports.has_key(c):
				continue
			## sanity checks
			if not leafreports[c].has_key('tags'):
				continue
			if not 'binary' in leafreports[c]['tags']:
				continue
			print >>sys.stderr, c, leafreports[c]
