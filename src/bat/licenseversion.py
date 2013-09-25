#!/usr/bin/python

## Binary Analysis Tool
## Copyright 2013 Armijn Hemel for Tjaldur Software Governance Solutions
## Licensed under Apache 2.0, see LICENSE file for details

import os, os.path, sys, subprocess, copy, cPickle, multiprocessing, sqlite3

'''
This program can be used to optionally prune results of a scan. Sometimes
results of scans can get very large, for example a scan of a Linux kernel image
could have thousands of string matches, which can each be found in a few
hundred kernel source code archives.

By pruning results the amount of noise can be much reduce, reports can be made
smaller and source code checks using the results of BAT can be made more
efficient.

To remove a version A from the set of versions the following conditions have
to hold:

* there is a minimum amount of results available (20 or 30 seems a good cut off value)

* all strings/variables/function names found in A are found in the most promising
version

* the amount of strings/variables/function names found in A are significantly
smaller than the amount in the most promising version (expressed as a maximum
percentage)
'''

fossology_to_ninka = { 'No_license_found': 'NONE'
                     , 'GPL_v1': 'GPLv1'
                     , 'GPL_v1+': 'GPLv1+'
                     , 'GPL_v2': 'GPLv2'
                     , 'GPL_v2+': 'GPLv2+'
                     , 'GPL_v3': 'GPLv3'
                     , 'GPL_v3+': 'GPLv3+'
                     , 'LGPL_v2': 'LibraryGPLv2'
                     , 'LGPL_v2+': 'LibraryGPLv2+'
                     , 'LGPL_v2.1': 'LesserGPLv2.1'
                     , 'LGPL_v2.1+': 'LesserGPLv2.1+'
                     , 'LGPL_v3': 'LesserGPLv3'
                     , 'LGPL_v3+': 'LesserGPLv3+'
                     , 'GPLv2+KDEupgradeClause': 'GPLVer2or3KDE+'
                     , 'Apache_v1.1': 'Apachev1.1'
                     , 'Apache_v2.0': 'Apachev2'
                     , 'MPL_v1.0': 'MPLv1_0'
                     , 'MPL_v1.1': 'MPLv1_1'
                     , 'QPL_v1.0': 'QTv1'
                     , 'Eclipse_v1.0': 'EPLv1'
                     , 'Boost_v1.0': 'boostV1'
                     , 'See-file(LICENSE)': 'SeeFile'
                     , 'See-doc(OTHER)': 'SeeFile'
                     , 'See-file(README)': 'SeeFile'
                     , 'See-file(COPYING)': 'SeeFile'
                     , 'Freetype': 'FreeType'
                     , 'Zend_v2.0': 'zendv2'
                     , 'PHP_v3.01': 'phpLicV3.01'
                     , 'CDDL': 'CDDLic'
                     , 'CDDL_v1.0': 'CDDL_v1.0'
                     , 'W3C-IP': 'W3CLic'
                     , 'Public-domain': 'publicDomain'
                     , 'IBM-PL': 'IBMv1'
                     , 'Sun': 'sunRPC'
                     , 'NPL_v1.0': 'NPLv1_0'
                     , 'NPL_v1.1': 'NPLv1_1'
                     , 'Artifex': 'artifex'
                     , 'CPL_v1.0': 'CPLv1'
                     , 'Beerware': 'BeerWareVer42'
                     , 'Public-domain-ref': 'publicDomain'
                     , 'Intel': 'InterACPILic'
                     , 'Artistic': 'ArtisticLicensev1'
                     }

## The scanners that are used in BAT are Ninka and FOSSology. These scanners
## don't always agree on results, but when they do, it is very reliable.
def squashlicenses(licenses):
	## licenses: [(license, scanner)]
	if len(licenses) != 2:
		return licenses
	if licenses[0][1] == 'ninka':
		if fossology_to_ninka.has_key(licenses[1][0]):
			if fossology_to_ninka[licenses[1][0]] == licenses[0][0]:
				if licenses[0][0] == 'InterACPILic':
					licenses = [('IntelACPILic', 'squashed')]
				else:   
					licenses = [(licenses[0][0], 'squashed')]
		else:   
			status = "difference"
	elif licenses[1][1] == 'ninka':
		if fossology_to_ninka.has_key(licenses[0][0]):
			if fossology_to_ninka[licenses[0][0]] == licenses[1][0]:
				if licenses[0][0] == 'InterACPILic':
					licenses = [('IntelACPILic', 'squashed')]
				else:
					licenses = [(licenses[0][0], 'squashed')]
	return licenses

def prune(scanenv, uniques, package):
	uniqueversions = {}

	linesperversion = {}

	for u in uniques:
		(line, res) = u
		versions = set([])
		map(lambda x: versions.add(x[1]), res)
		for version in versions:
			if linesperversion.has_key(version):
				linesperversion[version].append(line)
			else:
				linesperversion[version] = [line]
			if uniqueversions.has_key(version):
				uniqueversions[version] += 1
			else:
				uniqueversions[version] = 1

	## there is only one version, so no need to continue
	if len(uniqueversions.keys()) == 1:
		return uniques

	pruneme = set([])

	unique_sorted_rev = sorted(uniqueversions, key = lambda x: uniqueversions.__getitem__(x), reverse=True)
	unique_sorted = sorted(uniqueversions, key = lambda x: uniqueversions.__getitem__(x))

	equivalents = set([])
	for l in unique_sorted_rev:
		if l in pruneme:
			continue
		if l in equivalents:
			continue
		linesperversion_l = set(linesperversion[l])
		pruneremove = []
		for k in unique_sorted:
			if uniqueversions[k] == uniqueversions[l]:
				## Both versions have the same amount of identifiers, so
				## could be the same. If so, add to 'equivalents'
				## and skip all equivalents since the results would be the
				## same as with the current 'l' and no versions would be
				## pruned that weren't already pruned.
				if set(linesperversion[k]) == linesperversion_l:
					equivalents.add(k)
				continue
			if uniqueversions[k] > uniqueversions[l]:
				break
			if set(linesperversion[k]).issubset(linesperversion_l):
				pruneme.add(k)
				pruneremove.append(k)
		## make the inner loop a bit shorter
		for k in pruneremove:
			unique_sorted.remove(k)

	notpruned = set(uniqueversions.keys()).difference(pruneme)
	newuniques = []
	for u in uniques:
		(line, res) = u
		newres = filter(lambda x: x[1] in notpruned, res)
		newuniques.append((line, newres))
	return newuniques

def determinelicense_version_copyright(unpackreports, scantempdir, topleveldir, processors, debug=False, envvars=None, unpacktempdir=None):
	scanenv = os.environ.copy()
	envvars = licensesetup(envvars, debug)
	if envvars[0]:
		for en in envvars[1].items():
			try:
				(envname, envvalue) = en
				scanenv[envname] = envvalue
			except Exception, e:
				pass

	determineversion = False
	if scanenv.get('BAT_RANKING_VERSION', 0) == '1':
		determineversion = True

	determinelicense = False
	if scanenv.get('BAT_RANKING_LICENSE', 0) == '1':
		determinelicense = True

	determinecopyright = False
	if scanenv.get('BAT_RANKING_COPYRIGHT', 0) == '1':
		determinecopyright = True

	## only continue if there actually is a need
	if not determinelicense and not determineversion and not determinecopyright:
		return None

	## Some methods use a database to lookup renamed packages.
	clonedb = scanenv.get('BAT_CLONE_DB')
	clones = {}
	if clonedb != None:
		conn = sqlite3.connect(clonedb)
		c = conn.cursor()
		clonestmp = c.execute("SELECT originalname,newname from renames").fetchall()
		for cl in clonestmp:
			(originalname,newname) = cl
			if not clones.has_key(originalname):
				clones[originalname] = newname
		c.close() 
		conn.close()

	pool = multiprocessing.Pool(processes=processors)
	## ignore files which don't have ranking results
	rankingfiles = []
	filehashseen = []
	for i in unpackreports:
		if not unpackreports[i].has_key('sha256'):
			continue
		if not unpackreports[i].has_key('tags'):
			continue
		if not 'ranking' in unpackreports[i]['tags']:
			continue
		filehash = unpackreports[i]['sha256']
		if filehash in filehashseen:
			continue
		filehashseen.append(filehash)
		if not os.path.exists(os.path.join(topleveldir, "filereports", "%s-filereport.pickle" % filehash)):
			continue
		compute_version(pool, processors, scanenv, unpackreports[i], topleveldir, determinelicense, determinecopyright)
	pool.terminate()

def grab_sha256_filename((masterdb, tasks)):
	results = {}
	## open the database containing all the strings that were extracted
	## from source code.
	conn = sqlite3.connect(masterdb)
	## we have byte strings in our database, not utf-8 characters...I hope
	conn.text_factory = str
	c = conn.cursor()
	for sha256sum in tasks:
		c.execute("select version, filename from processed_file where sha256=?", (sha256sum,))
		res = c.fetchall()
		results[sha256sum] = res
	c.close()
	conn.close()
	return results

def grab_sha256_license((licensedb, tasks)):
	results = {}
	## open the database containing all the strings that were extracted
	## from source code.
	conn = sqlite3.connect(licensedb)
	## we have byte strings in our database, not utf-8 characters...I hope
	conn.text_factory = str
	c = conn.cursor()
	for sha256sum in tasks:
		c.execute("select distinct license, scanner from licenses where sha256=?", (sha256sum,))
		licenses = c.fetchall()

		results[sha256sum] = licenses
	c.close()
	conn.close()
	return results

def grab_sha256_parallel((masterdb, tasks, language, querytype)):
	results = []
	## open the database containing all the strings that were extracted
	## from source code.
	conn = sqlite3.connect(masterdb)
	## we have byte strings in our database, not utf-8 characters...I hope
	conn.text_factory = str
	c = conn.cursor()
	for line in tasks:
		if querytype == "string":
			c.execute("select distinct sha256, linenumber, language from extracted_file where programstring=?", (line,))
		elif querytype == 'function':
			c.execute("select distinct sha256, linenumber, language from extracted_function where functionname=?", (line,))
		res = c.fetchall()
		if res != None:
			res = filter(lambda x: x[2] == language, res)
			## TODO: make a list of line numbers
			res = map(lambda x: (x[0], x[1]), res)
		results.append((line, res))
	c.close()
	conn.close()
	return results


def compute_version(pool, processors, scanenv, unpackreport, topleveldir, determinelicense, determinecopyright):
	## read the pickle
	filehash = unpackreport['sha256']
	leaf_file = open(os.path.join(topleveldir, "filereports", "%s-filereport.pickle" % filehash), 'rb')
	leafreports = cPickle.load(leaf_file)
	leaf_file.close()
	if not leafreports.has_key('ranking'):
		return

	(res, dynamicRes, variablepvs) = leafreports['ranking']

	if res == None and dynamicRes == {}:
		return

	masterdb = scanenv.get('BAT_DB')
	if determinelicense:
		licensedb = scanenv.get('BAT_LICENSE_DB')

	if processors == None:
		processors = multiprocessing.cpu_count()
	## keep a list of versions per sha256, since source files often are in more than one version
	sha256_versions = {}
	## indicate whether or not the pickle should be written back to disk.
	## If uniquematches is empty and if dynamicRes is also empty, then nothing needs to be written back.
	changed = False
	
	if res != None:
		newreports = []

		for r in res['reports']:
			(rank, package, unique, percentage, packageversions, packagelicenses, language) = r
			if unique == []:
				newreports.append(r)
				continue
			changed = True
			newuniques = []
			newpackageversions = {}
			packagecopyrights = []
			uniques = list(set(map(lambda x: x[0], unique)))

			## first grab all possible checksums, plus associated line numbers for this string. Since
			## these are unique strings they will only be present in the package (or clones of the package).
			vtasks_tmp = []
			if len(uniques) < processors:
				step = 1
			else:
				step = len(uniques)/processors
			for v in xrange(0, len(uniques), step):
				vtasks_tmp.append(uniques[v:v+step])
			vtasks = map(lambda x: (masterdb, x, language, 'string'), filter(lambda x: x!= [], vtasks_tmp))
			vsha256s = pool.map(grab_sha256_parallel, vtasks)
			vsha256s = reduce(lambda x, y: x + y, filter(lambda x: x != [], vsha256s))

			## for each combination (line,sha256,linenumber) store per checksum
			## the line and linenumber(s). The checksums are used to look up version
			## and filename information.
			sha256_scan_versions = {}

			for l in vsha256s:
				line_sha256_version = []
				(line, versionsha256s) = l
				for s in versionsha256s:
					(checksum, linenumber) = s
					if not sha256_versions.has_key(checksum):
						if sha256_scan_versions.has_key(checksum):
							sha256_scan_versions[checksum].append((line, linenumber))
						else:
							sha256_scan_versions[checksum] = [(line, linenumber)]

			vtasks_tmp = []
			if len(sha256_scan_versions) < processors:
				step = 1
			else:
				step = len(sha256_scan_versions)/processors
			for v in xrange(0, len(sha256_scan_versions), step):
				vtasks_tmp.append(sha256_scan_versions.keys()[v:v+step])
			vtasks = map(lambda x: (masterdb, x), filter(lambda x: x!= [], vtasks_tmp))

			## grab version and file information
			fileres = pool.map(grab_sha256_filename, vtasks)
			resdict = {}
			map(lambda x: resdict.update(x), fileres)

			tmplines = {}
			## construct the full information needed by other scans
			for checksum in resdict:
				versres = resdict[checksum]
				for l in sha256_scan_versions[checksum]:
					(line, linenumber) = l
					if not tmplines.has_key(line):
						tmplines[line] = []
					## TODO: store (checksum, linenumber(s), versres)
					for v in versres:
						tmplines[line].append((checksum, v[0], linenumber, v[1]))
				for v in versres:
					if sha256_versions.has_key(checksum):
						sha256_versions[checksum].append((v[0], v[1]))
					else:
						sha256_versions[checksum] = [(v[0], v[1])]
			for l in tmplines.keys():
				newuniques.append((l, tmplines[l]))

			## optionally prune version information
			if scanenv.has_key('BAT_KEEP_VERSIONS'):
				keepversions = int(scanenv.get('BAT_KEEP_VERSIONS', 0))
				if keepversions > 0:
					## there need to be a minimum of unique hits (like strings), otherwise
					## it's silly
					if scanenv.has_key('BAT_MINIMUM_UNIQUE'):
						minimumunique = int(scanenv.get('BAT_MINIMUM_UNIQUE', 0))
						if minimumunique > 0:
							if len(newuniques) > minimumunique:
								newuniques = prune(scanenv, newuniques, package)

			licensesha256s = []
			for u in newuniques:
				versionsha256s = u[1]
				if determinelicense:
					licensesha256s += map(lambda x: x[0], versionsha256s)
				for s in versionsha256s:
					v = s[1]
					if newpackageversions.has_key(v):
						newpackageversions[v] = newpackageversions[v] + 1
					else:   
						newpackageversions[v] = 1

			## Ideally the version number should be stored with the license.
			## There are good reasons for this: files are sometimes collectively
			## relicensed when there is a new release (example: Samba 3.2 relicensed
			## to GPLv3+) so the version number can be very significant for licensing.
			## determinelicense and determinecopyright *always* imply determineversion
			## TODO: store license with version number.
			if determinelicense:
				vtasks_tmp = []
				licensesha256s = list(set(licensesha256s))
				if len(licensesha256s) < processors:
					step = 1
				else:
					step = len(licensesha256s)/processors
				for v in xrange(0, len(licensesha256s), step):
					vtasks_tmp.append(licensesha256s[v:v+step])
				vtasks = map(lambda x: (licensedb, x), filter(lambda x: x!= [], vtasks_tmp))

				packagelicenses = pool.map(grab_sha256_license, vtasks)
				## result is a list of {sha256sum: list of licenses}
				packagelicenses_tmp = []
				for p in packagelicenses:
					packagelicenses_tmp += reduce(lambda x,y: x + y, p.values())
				packagelicenses = list(set(packagelicenses_tmp))
			else:
				packagelicenses = []

			'''
			## extract copyrights. 'statements' are not very accurate so ignore those for now in favour of URL
			## and e-mail
			if determinecopyright:
				copyrightpv = []
				copyrightcursor.execute("select distinct * from extracted_copyright where sha256=?", (s[0],))
				copyrights = copyrightcursor.fetchall()
				copyrights = filter(lambda x: x[2] != 'statement', copyrights)
				if copyrights != []:
					copyrights = list(set(map(lambda x: (x[1], x[2]), copyrights)))
					copyrightpv = copyrightpv + copyrights
					packagecopyrights = list(set(packagecopyrights + copyrightpv))

			'''
			newreports.append((rank, package, newuniques, percentage, newpackageversions, packagelicenses, language))
		res['reports'] = newreports

	## TODO: determine versions of functions and variables here as well

	if dynamicRes.has_key('versionresults'):

		for package in dynamicRes['versionresults'].keys():
			if not dynamicRes.has_key('uniquepackages'):
				continue
			if not dynamicRes['uniquepackages'].has_key(package):
				continue
			changed = True
			versions = []
			functionnames = dynamicRes['uniquepackages'][package]
			## right now only C is supported. TODO: fix this for other languages such as Java.
			vtasks_tmp = []
			if len(functionnames) < processors:
				step = 1
			else:
				step = len(functionnames)/processors
			for v in xrange(0, len(functionnames), step):
				vtasks_tmp.append(functionnames[v:v+step])
			vtasks = map(lambda x: (masterdb, x, 'C', 'function'), vtasks_tmp)

			vsha256s = pool.map(grab_sha256_parallel, vtasks)
			vsha256s = reduce(lambda x, y: x + y, filter(lambda x: x != [], vsha256s))

			sha256_scan_versions = {}
			tmplines = {}

			for p in vsha256s:
				line_sha256_version = []
				(functionname, res) = p
				for s in res:
					(checksum, linenumber) = s
					if not sha256_versions.has_key(checksum):
						if sha256_scan_versions.has_key(checksum):
							sha256_scan_versions[checksum].append((functionname, linenumber))
						else:
							sha256_scan_versions[checksum] = [(functionname, linenumber)]
					else:
						for v in sha256_versions[checksum]:
							(version, filename) = v
							if not tmplines.has_key(functionname):
								tmplines[functionname] = []
							tmplines[functionname].append((checksum, version, linenumber, filename))

			vtasks_tmp = []
			if len(sha256_scan_versions.keys()) < processors:
				step = 1
			else:
				step = len(sha256_scan_versions.keys())/processors
			for v in xrange(0, len(sha256_scan_versions.keys()), step):
				vtasks_tmp.append(sha256_scan_versions.keys()[v:v+step])
			vtasks = map(lambda x: (masterdb, x), vtasks_tmp)

			## grab version and file information
			fileres = pool.map(grab_sha256_filename, vtasks)
			resdict = {}
			map(lambda x: resdict.update(x), fileres)

			## construct the full information needed by other scans
			for checksum in resdict:
				versres = resdict[checksum]
				for l in sha256_scan_versions[checksum]:
					(functionname, linenumber) = l
					if not tmplines.has_key(functionname):
						tmplines[functionname] = []
					## TODO: store (checksum, linenumber(s), versres)
					for v in versres:
						(version, filename) = v
						tmplines[functionname].append((checksum, version, linenumber, filename))
				for v in versres:
					if sha256_versions.has_key(checksum):
						sha256_versions[checksum].append((v[0], v[1]))
					else:
						sha256_versions[checksum] = [(v[0], v[1])]
			for l in tmplines.keys():
				dynamicRes['versionresults'][package].append((l, tmplines[l]))

		newresults = {}
		for package in dynamicRes['versionresults'].keys():
			newuniques = dynamicRes['versionresults'][package]
			## optionally prune version information
			if scanenv.has_key('BAT_KEEP_VERSIONS'):
				keepversions = int(scanenv.get('BAT_KEEP_VERSIONS', 0))
				if keepversions > 0:
					## there need to be a minimum of unique hits (like strings), otherwise
					## it's silly
					if scanenv.has_key('BAT_MINIMUM_UNIQUE'):
						minimumunique = int(scanenv.get('BAT_MINIMUM_UNIQUE', 0))
						if minimumunique > 0:
							if len(newuniques) > minimumunique:
								newuniques = prune(scanenv, newuniques, package)
			newresults[package] = newuniques
			uniqueversions = {}
			dynamicRes['packages'][package] = []
			vs = []
			for r in newuniques:
				vs = vs + list(set(map(lambda x: x[1], r[1])))
			for v in list(set(vs)):
				dynamicRes['packages'][package].append((v, vs.count(v)))
		dynamicRes['versionresults'] = newresults

	if changed:
		leaf_file = open(os.path.join(topleveldir, "filereports", "%s-filereport.pickle" % filehash), 'wb')
		leafreports = cPickle.dump(leafreports, leaf_file)
		leaf_file.close()

## method that makes sure that everything is set up properly and modifies
## the environment, as well as determines whether the scan should be run at
## all.
## Returns tuple (run, envvars)
## * run: boolean indicating whether or not the scan should run
## * envvars: (possibly) modified
## This is the minimum that is needed for determining the licenses
def licensesetup(envvars, debug=False):
	scanenv = os.environ.copy()
	newenv = {}
	if envvars != None:
		for en in envvars.split(':'):
			try:
				(envname, envvalue) = en.split('=')
				scanenv[envname] = envvalue
				newenv[envname] = envvalue
			except Exception, e:
				pass

	## Is the master database defined?
	if not scanenv.has_key('BAT_DB'):
		return (False, None)

	masterdb = scanenv.get('BAT_DB')

	## Does the master database exist?
	if not os.path.exists(masterdb):
		return (False, None)

	## Does the master database have the right tables?
	## processed_file is always needed
	conn = sqlite3.connect(masterdb)
	c = conn.cursor()
	res = c.execute("select * from sqlite_master where type='table' and name='processed_file'").fetchall()
	if res == []:
		c.close()
		conn.close()
		return (False, None)

	## extracted_file is needed for string matches
	res = c.execute("select * from sqlite_master where type='table' and name='extracted_file'").fetchall()
	if res == []:
		stringmatches = False
	else:
		stringmatches = True

	## TODO: copy checks for functions as well

	## check the license database. If it does not exist, or does not have
	## the right schema remove it from the configuration
	if scanenv.get('BAT_RANKING_LICENSE', 0) == '1' or scanenv.get('BAT_RANKING_COPYRIGHT', 0) == 1:
		if scanenv.get('BAT_LICENSE_DB') != None:
			try:
				licenseconn = sqlite3.connect(scanenv.get('BAT_LICENSE_DB'))
				licensecursor = licenseconn.cursor()
				licensecursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='licenses';")
				if licensecursor.fetchall() == []:
					if newenv.has_key('BAT_LICENSE_DB'):
						del newenv['BAT_LICENSE_DB']
					if newenv.has_key('BAT_RANKING_LICENSE'):
						del newenv['BAT_RANKING_LICENSE']
				## also check if copyright information exists
				licensecursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='extracted_copyright';")
				if licensecursor.fetchall() == []:
					if newenv.has_key('BAT_RANKING_COPYRIGHT'):
						del newenv['BAT_RANKING_COPYRIGHT']
				licensecursor.close()
				licenseconn.close()
			except:
				if newenv.has_key('BAT_LICENSE_DB'):
					del newenv['BAT_LICENSE_DB']
				if newenv.has_key('BAT_RANKING_LICENSE'):
					del newenv['BAT_RANKING_LICENSE']
				if newenv.has_key('BAT_RANKING_COPYRIGHT'):
					del newenv['BAT_RANKING_COPYRIGHT']
	## cleanup
	c.close()
	conn.close()

	## check the cloning database. If it does not exist, or does not have
	## the right schema remove it from the configuration
	if scanenv.has_key('BAT_CLONE_DB'):
		clonedb = scanenv.get('BAT_CLONE_DB')
		if os.path.exists(clonedb):
			conn = sqlite3.connect(clonedb)
			c = conn.cursor()
			c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='renames';")
			if c.fetchall() == []:
				if newenv.has_key('BAT_CLONE_DB'):
					del newenv['BAT_CLONE_DB']
			c.close()
			conn.close()
		else:   
			if newenv.has_key('BAT_CLONE_DB'):
				del newenv['BAT_CLONE_DB']
	return (True, newenv)
