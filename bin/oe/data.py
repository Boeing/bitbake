#!/usr/bin/python

# proposed new way of structuring environment data for the
# OpenEmbedded buildsystem

from oe import debug

def init():
	return {}

_data = init()

def initVar(var, d = _data):
	"""Non-destructive var init for data structure"""
	if not d.has_key(var):
		d[var] = {}

	if not d[var].has_key("flags"):
		d[var]["flags"] = {}

def setVar(var, value, d = _data):
	"""Set a variable to a given value"""
	try:
		d[var]["content"] = value 
	except KeyError:
		initVar(var, d)
		d[var]["content"] = value 

def getVar(var, d = _data, exp = 0):
	"""Gets the value of a variable"""
	try:
		if exp:
			return expand(d[var]["content"], d)
		else:
			return d[var]["content"]
	except KeyError:
		return None

def delVar(var, d = _data):
	"""Removes a variable from the data set"""
	del d[var]

def setVarFlag(var, flag, flagvalue, d = _data):
	"""Set a flag for a given variable to a given value"""
#	print "d[%s][\"flags\"][%s] = %s" % (var, flag, flagvalue)
	try:
		d[var]["flags"][flag] = flagvalue
	except KeyError:
		initVar(var, d)
		d[var]["flags"][flag] = flagvalue

def getVarFlag(var, flag, d = _data):
	"""Gets given flag from given var""" 
	try:
		return d[var]["flags"][flag]
	except KeyError:
		return None

def setVarFlags(var, flags, d = _data):
	"""Set the flags for a given variable"""
	try:
		d[var]["flags"] = flags
	except KeyError:
		initVar(var, d)
		d[var]["flags"] = flags

def getVarFlags(var, d = _data):
	"""Gets a variable's flags"""
	try:
		return d[var]["flags"]
	except KeyError:
		return None

def getData(d = _data):
	"""Returns the data object used"""
	return d

def setData(newData, d = _data):
	"""Sets the data object to the supplied value"""
	d = newData

import re

__expand_var_regexp__ = re.compile(r"\${[^{}]+}")
__expand_python_regexp__ = re.compile(r"\${@.+?}")

def expand(s, d = _data):
	"""Can expand variables with their values from env[]

	>>> env['MID'] = 'drin'
	>>> print expand('vorher ${MID} dahinter')
	vorher drin dahinter

	Unset variables are kept as is:

	>>> print expand('vorher ${MID} dahinter ${UNKNOWN}')
	vorher drin dahinter ${UNKNOWN}

	A syntax error just returns the string:

	>>> print expand('${UNKNOWN')
	${UNKNOWN

	We can evaluate python code:

	>>> print expand('${@ "Test"*3}')
	TestTestTest
	>>> env['START'] = '0x4000'
	>>> print expand('${@ hex(0x1000000+${START}) }')
	0x1004000

	We are able to handle recursive definitions:

	>>> env['ARCH'] = 'arm'
	>>> env['OS'] = 'linux'
	>>> env['SYS'] = '${ARCH}-${OS}'
	>>> print expand('${SYS}')
	arm-linux
	"""

	def var_sub(match):
		key = match.group()[2:-1]
		#print "got key:", key
		var = getVar(key, d)
		if var is not None:
			return var
		else:
			return match.group()

	def python_sub(match):
		code = match.group()[3:-1]
		import oe
		locals()['d'] = d
		s = eval(code)
		import types
		if type(s) == types.IntType: s = str(s)
		return s

	if s is None: # sanity check
		return s

	while s.find('$') != -1:
		olds = s
		s = __expand_var_regexp__.sub(var_sub, s)
		s = __expand_python_regexp__.sub(python_sub, s)
		if len(s)>2048:
			debug(1, "expanded string too long")
			return s
		if s == olds: break
	return s

def expandData(alterdata = _data, readdata = None):
	"""For each variable in alterdata, expand it, and update the var contents.
	   Replacements use data from readdata.

	   Example:
	   to = {}
	   from = {}
	   setVar("dlmsg", "dl_dir is ${DL_DIR}", to)
	   setVar("DL_DIR", "/path/to/whatever", from)
	   expandData(to, from)
	   getVar("dlmsg", to) returns "dl_dir is /path/to/whatever"
	   """
	if readdata == None:
		readdata = alterdata

	for key in alterdata.keys():
		val = getVar(key, alterdata)
		if val is None:
			continue
		expanded = expand(val, readdata)
#		print "key is %s, val is %s, expanded is %s" % (key, val, expanded)
		setVar(key, expanded, alterdata)

import os

def inheritFromOS(pos, d = _data):
	pos = str(pos)
	for s in os.environ.keys():
		try:
			inherit = getVarFlag(s, "inherit", d)
			if inherit is not None and inherit == pos:
				setVar(s, os.environ[s], d)
		except KeyError:
			pass

import sys, string

def emit_var(var, o=sys.__stdout__, d = _data):
	if getVarFlag(var, "python", d):
		return 0

	val = getVar(var, d, 1)
	if val is None:
		debug(2, "Warning, %s variable is None, not emitting" % var)
		return 0

	if getVarFlag(var, "func", d):
		# NOTE: should probably check for unbalanced {} within the var
		o.write("%s() {\n%s\n}\n" % (var, val))
		return 1
	else:	
		if getVarFlag(var, "export", d):
			o.write('export ')
		# if we're going to output this within doublequotes,
		# to a shell, we need to escape the quotes in the var
		alter = re.sub('"', '\\"', val.strip())
		o.write('%s="%s"\n' % (var, alter))
		return 1


def emit_env(o=sys.__stdout__, d = _data):
	"""This prints the data so that it can later be sourced by a shell
	Normally, it prints to stdout, but this it can be redirectory to some open file handle

	It is used by exec_shell_func().
	"""

	oedir = getVar('OEDIR', d)
	if oedir is None:
		oedir = "." 

	oepath = string.split(getVar('OEPATH', d, 1) or oedir, ":")
	path = getVar('PATH', d)
	if path:
		path = path.split(":")
		for p in oepath:
			path[0:0] = [ os.path.join("%s" % p, "bin/build") ]
		path[0:0] = [ "${STAGING_BINDIR}" ]
		setVar('PATH', expand(string.join(path, ":"), d), d)

	expandData(d)
	env = d.keys()

	for e in env:
		if getVarFlag(e, "func", d):
			continue
		emit_var(e, o, d) and o.write('\n')

	for e in env:
		if not getVarFlag(e, "func", d):
			continue
		emit_var(e, o, d) and o.write('\n')

def update_data(d = _data):
	"""Modifies the environment vars according to local overrides

	For the example we do some preparations:

	>>> setenv('TEST_arm', 'target')
	>>> setenv('TEST_ramses', 'machine')
	>>> setenv('TEST_local', 'local')
        >>> setenv('OVERRIDES', 'arm')

	and then we set some TEST environment variable and let it update:

	>>> setenv('TEST', 'original')
	>>> update_env()
	>>> print env['TEST']
	target

	You can set OVERRIDES to another value, yielding another result:

        >>> setenv('OVERRIDES', 'arm:ramses:local')
	>>> setenv('TEST', 'original')
	>>> update_env()
	>>> print env['TEST']
	local

	Besides normal updates, we are able to append text:

	>>> setenv('TEST_append', ' foo')
	>>> update_env()
	>>> print env['TEST']
	local foo

	And we can prepend text:

	>>> setenv('TEST_prepend', 'more ')
	>>> update_env()
	>>> print env['TEST']
	more local foo

	Deleting stuff is more fun with multiline environment variables, but
	it works with normal ones, too. The TEST_delete='foo' construct
	deletes any line in TEST that matches 'foo':

	>>> setenv('TEST_delete', 'foo ')
	>>> update_env()
	>>> print "'%s'" % env['TEST']
	''
	"""

	debug(2, "update_env()")

	# can't do delete env[...] while iterating over the dictionary, so remember them
	dodel = []
	# preprocess overrides
	overrides = expand(getVar('OVERRIDES', d), d)
	if not overrides:
		debug(1, "OVERRIDES not defined, nothing to do")
		return
	overrides = overrides.split(':')

	for s in d.keys():
		for o in overrides:
			name = "%s_%s" % (s, o)
			nameval = getVar(name, d)
			if nameval:
				setVar(s, nameval, d)
				dodel.append(name)

		# Handle line appends:
		name = "%s_append" % s
		nameval = getVar(name, d)
		if nameval:
			sval = getVar(s, d) or ""
			setVar(s, sval+nameval, d)
			dodel.append(name)

		# Handle line prepends
		name = "%s_prepend" % s
		nameval = getVar(name, d)
		if nameval:
			sval = getVar(s, d) or ""
			setVar(s, nameval+sval, d)
			dodel.append(name)

		# Handle line deletions
		name = "%s_delete" % s
		nameval = getVar(name, d)
		if nameval:
			sval = getVar(s, d)
			if sval:
				new = ''
				pattern = string.replace(nameval,"\n","").strip()
				for line in string.split(sval,"\n"):
					if line.find(pattern) == -1:
						new = new + '\n' + line
				setVar(s, new, d)
				dodel.append(name)

	# delete all environment vars no longer needed
	for s in dodel:
		delVar(s, d)

	inheritFromOS(5)
