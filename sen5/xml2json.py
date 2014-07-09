#!/usr/bin/env python2
# -*- coding: utf-8 -*-
__author__ = 'lijiyang'

import json
import sys
import xml.etree.cElementTree as ET

import config


def xml2json(xmlstring, starwith, strip_ns=1, strip=1):
    """Convert an XML string into a JSON string."""

    elem = ET.fromstring(xmlstring)
    apps = elem.findall(starwith)
    jsons = []
    for app in apps:
        jsonstring = elem2json(app, strip_ns=strip_ns, strip=strip)
        jsons.append(json.loads(jsonstring))
    return jsons


def elem2json(elem, strip_ns=1, strip=1):
    """Convert an ElementTree or Element into a JSON string."""

    if hasattr(elem, 'getroot'):
        elem = elem.getroot()
    return json.dumps(elem_to_internal(elem, strip_ns=strip_ns, strip=strip), sort_keys=True, indent=4,
                      separators=(',', ': '))


def elem_to_internal(elem, strip_ns=1, strip=1):
    """Convert an Element into an internal dictionary (not JSON!)."""

    d = {}
    elem_tag = elem.tag
    if strip_ns:
        elem_tag = strip_tag(elem.tag)
    else:
        for key, value in list(elem.attrib.items()):
            d['@' + key] = value

    # loop over subelements to merge them
    for subelem in elem:
        v = elem_to_internal(subelem, strip_ns=strip_ns, strip=strip)

        tag = subelem.tag
        if strip_ns:
            tag = strip_tag(subelem.tag)

        value = v[tag]

        try:
            # add to existing list for this tag
            d[tag].append(value)
        except AttributeError:
            # turn existing entry into a list
            d[tag] = [d[tag], value]
        except KeyError:
            # add a new non-list entry
            d[tag] = value
    text = elem.text
    tail = elem.tail
    if strip:
        # ignore leading and trailing whitespace
        if text:
            text = text.strip()
        if tail:
            tail = tail.strip()

    if tail:
        d['#tail'] = tail

    if d:
        # use #text element if other attributes exist
        if text:
            d["#text"] = text
    else:
        # text is the value if no attributes
        d = text or None
    return {elem_tag: d}


def strip_tag(tag):
    strip_ns_tag = tag
    split_array = tag.split('}')
    if len(split_array) > 1:
        strip_ns_tag = split_array[1]
        tag = strip_ns_tag
    return tag


def getJson(starwith):
    """ starwith: the element in xml to start with when parsing """
    strip = 1
    strip_ns = 0
    inputfile = readfile()
    return xml2json(inputfile, starwith, strip_ns, strip)


def readfile():
    try:
        inputstream = open(config.repo_path + config.indexfile)
    except:
        sys.stderr.write("Problem reading '{0}'\n", config.indexfile)
        sys.exit(-1)
    return inputstream.read()

import pydevd
def main():
#    pydevd.settrace('192.168.56.1', port=51234, stdoutToServer=True, stderrToServer=True)
    js = getJson('application')
    print js


if __name__ == "__main__":
    main()