#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Do the parsing required to get all the vulnerabilities as objects in memory so that we can generate the pages.
from __future__ import absolute_import, division, print_function, unicode_literals
# Evil hack to make UTF-8 default
import sys
reload(sys)
sys.setdefaultencoding("UTF-8")
import json
import os
import dateutil.parser
from collections import defaultdict,OrderedDict

def warning(*objs):
	print(*objs, file=sys.stderr)

class DateRef:
	def __init__(self, field, vuln):
		if None == field:
			raise ValueError("Nothing to extract date from: None")
		if isinstance(field, dict):
			self.datestring = field['date']
			self.ref = field['ref']
		elif isinstance(field, list):
			if len(field) == 0:
				raise ValueError("No field to process: " + unicode(field))
			self.datestring = field[0]
			if len(field) == 2:
				self.ref = field[1]
			else:
				self.ref = None
		else:
			raise ValueError("Unexpected type of field %s" % (field))
		if not isinstance(self.datestring,basestring):
			raise ValueError("Date string not a string: " + unicode(type(self.datestring)) + " - " + unicode(self.datestring))
		self.date = dateutil.parser.parse(self.datestring).date()
		self.vuln = vuln
	def __str__(self):
		string = self.datestring
		if self.ref is not None:
			string += ' ' + self.vuln._str_reference(self.ref)
		else:
			string += ' \\[citation-needed\\]'
		return string

def get_submitters(submission_list):
	submitters = []
	for submission in submission_list:
		submitters.append(submission['by'])
	return submitters

class Submission:
	def __init__(self,jsn):
		self.by = jsn['by']
		self.on = jsn['on']
	def __str__(self):
		return "by: [{name}](submitters/{by}), on: {on}".format(name=submitters[self.by].name,by=self.by,on=self.on)
	def __repr__(self):
		return self.__str__()

class Submitter:
	def __init__(self,jsn):
		self.ID = jsn['id']
		self.name = jsn['name']
		self.email = jsn['email']
		self.url = jsn['url']
		self.fingerprints = jsn['fingerprints']
		self.show_photo = jsn['photo']
	def __str__(self):
		if self.show_photo:
			photostring = "![Photo of {name}](images/people/{ID}.jpg)".format(name=self.name,ID=self.ID)
		else:
			photostring=""
		return """#{name} ({ID})

* Name: {name}
* Email: <{email}>
* Website: <{url}>
* GPG fingerprints: {fingerprints}

{photo}
""".format(name=self.name,ID=self.ID,email=self.email,url=self.url,fingerprints=", ".join(self.fingerprints),photo=photostring)
	def __repr__(self):
		return self.__str__()


# Class definition for a vulnerability
class Vulnerability:
	year_fields = ['Discovered_on','Reported_on','Fixed_on','Fix_released_on']
	def __init__(self,jsn):
		self.jsn = jsn
		self.name = jsn['name']
		self.urlname = self.name.replace(' ','_')
	def _years_append(self,yrs,field):
		try:
			daterefs = self._rawdateref(field)
		except ValueError as e:
			warning(e)
			return
		for dateref in daterefs:
			yrs.append(unicode(dateref.date.year))
	def years(self):
		yrs = []
		for year_field in self.year_fields:
			field = self.jsn[year_field]
			if len(field) > 0:
				if isinstance(field,list) and isinstance(field[0],list):
					for entry in field:
						self._years_append(yrs,entry)
				else:
					self._years_append(yrs,field)
		return set(yrs)
	def _dates_append(self,dates,field):
		try:
			daterefs = self._rawdateref(field)
		except ValueError as e:
			warning(e)
			return
		for dateref in daterefs:
			dates.append(dateref.date)
	def _dates(self):
		dates = []
		for year_field in self.year_fields:
			field = self.jsn[year_field]
                        if len(field) > 0:
				if isinstance(field,list) and isinstance(field[0],list):
					for entry in field:
						self._dates_append(dates,entry)
				else:
					self._dates_append(dates,field)
		return sorted(dates)
	def raw_vulnerability(self):
		dates = self._dates()
		regex = self.jsn['Affected_versions_regexp']
		if len(regex) > 0:#TODO regex is a list but we are not treating it as one.
			return (regex[0],unicode(dates[0].isoformat()),self.name)
	def versions(self):
		return []#TODO
	def manufacturers(self):
		return self.jsn['Affected_manufacturers']
	def submitters(self):
		submitterslist = get_submitters(self.jsn['Submission'])
		return submitterslist
	def _get_reference_url(self,reference):
		return self.jsn['references'][reference]['url']
	def _str_reference(self,reference):
		return "\\[[{reference}]({url})\\]".format(reference=reference,url=self._get_reference_url(reference))
	def _print_ref_list(self,reflist,separator=", "):
		answer = []
		for itemref in reflist:
			if isinstance(itemref, list):
				itemstr = itemref[0]
				if isinstance(itemstr, list):
					itemstr = '(' + ', '.join(itemstr) + ')'
				if len(itemref) == 2:
					itemstr += " " + self._str_reference(itemref[1])
				else:
					itemstr += ' \\[citation-needed\\]'
			else:
				raise ValueError("Unknown type of itemref:" + unicode(type(itemref)) + " - "+ unicode(itemref))
			#if isinstance(itemref, dict):
				#TODO we don't use this yet
			answer.append(itemstr)
		return separator.join(answer)
	def _print_manufacturer_list(self,reflist,separator=", "):
		answer = []
                for itemref in reflist:
                        if isinstance(itemref, list):
                                itemstr = "[{manufacturer}](by/manufacturer/{manufacturer})".format(manufacturer=itemref[0])
                                if len(itemref) == 2:
                                        itemstr += " " + self._str_reference(itemref[1])
                                else:
                                        itemstr += ' \\[citation-needed\\]'
                        else:
                                raise ValueError("Unknown type of itemref:" + unicode(type(itemref)) + " - "+ unicode(itemref))
                        answer.append(itemstr)
                return separator.join(answer)
	def _rawdateref(self,jsn):
		if isinstance(jsn,list):
			if isinstance(jsn[0],list) or isinstance(jsn[0],dict):
				return map(lambda x : DateRef(x[0],x[1]),zip(jsn,[self]*len(jsn)))
		return [DateRef(jsn,self)]
	def _dateref(self,jsn):
		"""Try and turn json into a DateRef or a string representing a list of DateRefs but if that fails Return 'Unknown'"""
		if len(jsn) == 0:
			return "Unknown"
		try:
			return ", ".join(map(str,self._rawdateref(jsn)))
		except ValueError as e:
			warning("Error in _dateref: " + unicode(e))
			return "Unknown"
	def __str__(self):
		return """### [{name}](/vulnerabilities/{urlname})
([json](vulnerabilities/{urlname}.json))

* CVE numbers: {cve}
* Responsibly disclosed?: {responsibly}
* Details: {details}
* Discovered by: {discovered_by} on: {discovered_on}
* Reported on: {reported_on}
* Fixed on: {fixed_on}
* Fix released on: {fix_released_on}
* Affected versions: {affected_versions} regex: {affected_versions_regexp}
* Affected devices: {affected_devices}
* Affected manufacturers: {affected_manufacturers}
* Fixed versions: {fixed_versions}
* Submission: {submission_list}
""".format(name=self.name, urlname=self.urlname,
		cve=self._print_ref_list(self.jsn['CVE']),
		responsibly=self.jsn['Responsibly_disclosed'],
		details=self._print_ref_list(self.jsn['Details'], separator="\n"),
		discovered_by=self._print_ref_list(self.jsn['Discovered_by']),
		discovered_on=self._dateref(self.jsn['Discovered_on']),
		reported_on=self._dateref(self.jsn['Reported_on']),
		fixed_on=self._dateref(self.jsn['Fixed_on']),
		fix_released_on=self._dateref(self.jsn['Fix_released_on']),
		affected_versions=self._print_ref_list(self.jsn['Affected_versions']),
		affected_versions_regexp=", ".join(self.jsn['Affected_versions_regexp']),
		affected_devices=self._print_ref_list(self.jsn['Affected_devices']),
		affected_manufacturers=self._print_manufacturer_list(self.jsn['Affected_manufacturers']),
		fixed_versions=self._print_ref_list(self.jsn['Fixed_versions']),
		submission_list="; ".join(map(str,map(Submission,self.jsn['Submission']))),
		)
	def __repr__(self):
		return self.__str__()

def print_by_page(vulndict):
	for key, vulns in vulndict.items():
		print("##{key}\n\n".format(key=key))
		for vuln in vulns:
			print(vuln)


vulnerabilities = []
# Key to list of vulnerability dicts
by_year = defaultdict(list)
by_version = defaultdict(list)
by_manufacturer = defaultdict(list)
by_submitter = defaultdict(list)
raw_vulnerabilities = []

for filename in os.listdir('input/vulnerabilities'):
	if filename == 'template.json':# skip over template
		continue
	if not filename.endswith('.json'):
		continue
	with open('input/vulnerabilities/' + filename,'r') as f:
		print("processing: " + filename)
		vulnerability = Vulnerability(json.load(f))
		vulnerabilities.append(vulnerability)
		for year in vulnerability.years():
			by_year[year].append(vulnerability)
		for version in vulnerability.versions():
			by_version[version].append(vulnerability)
		manufacturers = vulnerability.manufacturers()
		for manufacturer in vulnerability.manufacturers():
			by_manufacturer[manufacturer[0]].append(vulnerability)
		if len(manufacturers) == 0:
			by_manufacturer['none'].append(vulnerability)
		for submitter in vulnerability.submitters():
			by_submitter[submitter].append(vulnerability)
		raw_vulnerability = vulnerability.raw_vulnerability()
		if raw_vulnerability != None:
			raw_vulnerabilities.append(raw_vulnerability)
print(raw_vulnerabilities)

submitters = dict()
for filename in os.listdir('input/submitters'):
	if not filename.endswith('.json'):
		continue
	with open('input/submitters/' + filename,'r') as f:
		print("processing: " + filename)
		submitter = Submitter(json.load(f))
		submitters[submitter.ID] = submitter

by_year = OrderedDict(sorted(by_year.items()))
by_version = OrderedDict(sorted(by_version.items()))
by_manufacturer = OrderedDict(sorted(by_manufacturer.items()))
by_submitter = OrderedDict(sorted(by_submitter.items()))

# Create a page for each vulnerability
def hook_preconvert_vulnpages():
	for vulnerability in vulnerabilities:
		p = Page("vulnerabilities/{name}.md".format(name=vulnerability.urlname),virtual=unicode(vulnerability),title=vulnerability.name)
		pages.append(p)

def hook_preconvert_submitterpages():
	for ID, submitter in submitters.items():
		p = Page("submitters/{ID}.md".format(ID=ID),virtual=unicode(submitter),title="{name} ({ID})".format(name=submitter.name,ID=ID))
		pages.append(p)

def hook_preconvert_bypages():
	by_pages(by_year,'year')
	by_pages(by_version,'version')
	by_pages(by_manufacturer,'manufacturer')
	by_pages(by_submitter,'submitter')

def by_pages(vulndict,by):
	bypagestring = '\n'#Can't be the empty string or empty pages will cause errors
	for key, vulns in vulndict.items():
		bypagestring += "##[{key}](by/{by}/{key})\n\n".format(key=key,by=by)
		vstring = "#{key}\n\n".format(key=key)
		for vuln in vulns:
			vulnstring = unicode(vuln) + '\n'
			vstring += vulnstring
			bypagestring += vulnstring
		p = Page("by/{by}/{key}.md".format(key=key,by=by),virtual=vstring,title=key)
		pages.append(p)
	p = Page("by/{by}/index.md".format(by=by),virtual=bypagestring,title="By {by}".format(by=by))
	pages.append(p)

