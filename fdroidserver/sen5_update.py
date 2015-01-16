#!/usr/bin/env python2
# -*- coding: utf-8 -*-
#
# update.py - part of the FDroid server tools
# Copyright (C) 2010-2013, Ciaran Gultnieks, ciaran@ciarang.com
# Copyright (C) 2013-2014 Daniel Martí <mvdan@mvdan.cc>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import os
import shutil
import glob
import re
import zipfile
import hashlib
import pickle
from xml.dom.minidom import Document
from optparse import OptionParser
import time
from PIL import Image
import logging

import common
import metadata
from common import FDroidPopen, SilentPopen
from metadata import MetaDataException


def get_densities():
    return ['640', '480', '320', '240', '160', '120']


def dpi_to_px(density):
    return (int(density) * 48) / 160


def px_to_dpi(px):
    return (int(px) * 160) / 48


def get_icon_dir(repodir, density):
    if density is None:
        return os.path.join(repodir, "icons")
    return os.path.join(repodir, "icons-%s" % density)


def get_icon_dirs(repodir):
    for density in get_densities():
        yield get_icon_dir(repodir, density)
    yield os.path.join(repodir, "icons")


def update_wiki(apps, apks):
    """Update the wiki

    :param apps: fully populated list of all applications
    :param apks: all apks, except...
    """
    logging.info("Updating wiki")
    wikicat = 'Apps'
    wikiredircat = 'App Redirects'
    import mwclient

    site = mwclient.Site((config['wiki_protocol'], config['wiki_server']),
                         path=config['wiki_path'])
    site.login(config['wiki_user'], config['wiki_password'])
    generated_pages = {}
    generated_redirects = {}
    for app in apps:
        wikidata = ''
        if app['Disabled']:
            wikidata += '{{Disabled|' + app['Disabled'] + '}}\n'
        if app['AntiFeatures']:
            for af in app['AntiFeatures'].split(','):
                wikidata += '{{AntiFeature|' + af + '}}\n'
        wikidata += '{{App|id=%s|name=%s|added=%s|lastupdated=%s|source=%s|tracker=%s|web=%s|donate=%s|flattr=%s|bitcoin=%s|litecoin=%s|dogecoin=%s|license=%s|root=%s}}\n' % (
            app['id'],
            app['Name'],
            time.strftime('%Y-%m-%d', app['added']) if 'added' in app else '',
            time.strftime('%Y-%m-%d', app['lastupdated']) if 'lastupdated' in app else '',
            app['Source Code'],
            app['Issue Tracker'],
            app['Web Site'],
            app['Donate'],
            app['FlattrID'],
            app['Bitcoin'],
            app['Litecoin'],
            app['Dogecoin'],
            app['License'],
            app.get('Requires Root', 'No'))

        if app['Provides']:
            wikidata += "This app provides: %s" % ', '.join(app['Summary'].split(','))

        wikidata += app['Summary']
        wikidata += " - [https://f-droid.org/repository/browse/?fdid=" + app['id'] + " view in repository]\n\n"

        wikidata += "=Description=\n"
        wikidata += metadata.description_wiki(app['Description']) + "\n"

        wikidata += "=Maintainer Notes=\n"
        if 'Maintainer Notes' in app:
            wikidata += metadata.description_wiki(app['Maintainer Notes']) + "\n"
        wikidata += "\nMetadata: [https://gitlab.com/fdroid/fdroiddata/blob/master/metadata/{0}.txt current] [https://gitlab.com/fdroid/fdroiddata/commits/master/metadata/{0}.txt history]\n".format(
            app['id'])

        # Get a list of all packages for this application...
        apklist = []
        gotcurrentver = False
        cantupdate = False
        buildfails = False
        for apk in apks:
            if apk['id'] == app['id']:
                if str(apk['versioncode']) == app['Current Version Code']:
                    gotcurrentver = True
                apklist.append(apk)
        # Include ones we can't build, as a special case...
        for thisbuild in app['builds']:
            if thisbuild['disable']:
                if thisbuild['vercode'] == app['Current Version Code']:
                    cantupdate = True
                # TODO: Nasty: vercode is a string in the build, and an int elsewhere
                apklist.append({'versioncode': int(thisbuild['vercode']),
                                'version': thisbuild['version'],
                                'buildproblem': thisbuild['disable']
                })
            else:
                builtit = False
                for apk in apklist:
                    if apk['versioncode'] == int(thisbuild['vercode']):
                        builtit = True
                        break
                if not builtit:
                    buildfails = True
                    apklist.append({'versioncode': int(thisbuild['vercode']),
                                    'version': thisbuild['version'],
                                    'buildproblem': "The build for this version appears to have failed. Check the [[{0}/lastbuild|build log]].".format(
                                        app['id'])
                    })
        if app['Current Version Code'] == '0':
            cantupdate = True
        # Sort with most recent first...
        apklist = sorted(apklist, key=lambda apk: apk['versioncode'], reverse=True)

        wikidata += "=Versions=\n"
        if len(apklist) == 0:
            wikidata += "We currently have no versions of this app available."
        elif not gotcurrentver:
            wikidata += "We don't have the current version of this app."
        else:
            wikidata += "We have the current version of this app."
        wikidata += " (Check mode: " + app['Update Check Mode'] + ") "
        wikidata += " (Auto-update mode: " + app['Auto Update Mode'] + ")\n\n"
        if len(app['No Source Since']) > 0:
            wikidata += "This application has partially or entirely been missing source code since version " + app[
                'No Source Since'] + ".\n\n"
        if len(app['Current Version']) > 0:
            wikidata += "The current (recommended) version is " + app['Current Version']
            wikidata += " (version code " + app['Current Version Code'] + ").\n\n"
        validapks = 0
        for apk in apklist:
            wikidata += "==" + apk['version'] + "==\n"

            if 'buildproblem' in apk:
                wikidata += "We can't build this version: " + apk['buildproblem'] + "\n\n"
            else:
                validapks += 1
                wikidata += "This version is built and signed by "
                if 'srcname' in apk:
                    wikidata += "F-Droid, and guaranteed to correspond to the source tarball published with it.\n\n"
                else:
                    wikidata += "the original developer.\n\n"
            wikidata += "Version code: " + str(apk['versioncode']) + '\n'

        wikidata += '\n[[Category:' + wikicat + ']]\n'
        if len(app['No Source Since']) > 0:
            wikidata += '\n[[Category:Apps missing source code]]\n'
        if validapks == 0 and not app['Disabled']:
            wikidata += '\n[[Category:Apps with no packages]]\n'
        if cantupdate and not app['Disabled']:
            wikidata += "\n[[Category:Apps we can't update]]\n"
        if buildfails and not app['Disabled']:
            wikidata += "\n[[Category:Apps with failing builds]]\n"
        elif not gotcurrentver and not cantupdate and not app['Disabled'] and app['Update Check Mode'] != "Static":
            wikidata += '\n[[Category:Apps to Update]]\n'
        if app['Disabled']:
            wikidata += '\n[[Category:Apps that are disabled]]\n'
        if app['Update Check Mode'] == 'None' and not app['Disabled']:
            wikidata += '\n[[Category:Apps with no update check]]\n'
        for appcat in app['Categories']:
            wikidata += '\n[[Category:{0}]]\n'.format(appcat)

        # We can't have underscores in the page name, even if they're in
        # the package ID, because MediaWiki messes with them...
        pagename = app['id'].replace('_', ' ')

        # Drop a trailing newline, because mediawiki is going to drop it anyway
        # and it we don't we'll think the page has changed when it hasn't...
        if wikidata.endswith('\n'):
            wikidata = wikidata[:-1]

        generated_pages[pagename] = wikidata

        # Make a redirect from the name to the ID too, unless there's
        # already an existing page with the name and it isn't a redirect.
        noclobber = False
        apppagename = app['Name'].replace('_', ' ')
        apppagename = apppagename.replace('{', '')
        apppagename = apppagename.replace('}', ' ')
        apppagename = apppagename.replace(':', ' ')
        # Drop double spaces caused mostly by replacing ':' above
        apppagename = apppagename.replace('  ', ' ')
        for expagename in site.allpages(prefix=apppagename,
                                        filterredir='nonredirects',
                                        generator=False):
            if expagename == apppagename:
                noclobber = True
        # Another reason not to make the redirect page is if the app name
        # is the same as it's ID, because that will overwrite the real page
        # with an redirect to itself! (Although it seems like an odd
        # scenario this happens a lot, e.g. where there is metadata but no
        # builds or binaries to extract a name from.
        if apppagename == pagename:
            noclobber = True
        if not noclobber:
            generated_redirects[apppagename] = "#REDIRECT [[" + pagename + "]]\n[[Category:" + wikiredircat + "]]"

    for tcat, genp in [(wikicat, generated_pages),
                       (wikiredircat, generated_redirects)]:
        catpages = site.Pages['Category:' + tcat]
        existingpages = []
        for page in catpages:
            existingpages.append(page.name)
            if page.name in genp:
                pagetxt = page.edit()
                if pagetxt != genp[page.name]:
                    logging.debug("Updating modified page " + page.name)
                    page.save(genp[page.name], summary='Auto-updated')
                else:
                    logging.debug("Page " + page.name + " is unchanged")
            else:
                logging.warn("Deleting page " + page.name)
                page.delete('No longer published')
        for pagename, text in genp.items():
            logging.debug("Checking " + pagename)
            if pagename not in existingpages:
                logging.debug("Creating page " + pagename)
                try:
                    newpage = site.Pages[pagename]
                    newpage.save(text, summary='Auto-created')
                except:
                    logging.error("...FAILED to create page")

    # Purge server cache to ensure counts are up to date
    site.pages['Repository Maintenance'].purge()


def delete_disabled_builds(apps, apkcache, repodirs):
    """Delete disabled build outputs.

    :param apps: list of all applications, as per metadata.read_metadata
    :param apkcache: current apk cache information
    :param repodirs: the repo directories to process
    """
    for app in apps:
        for build in app['builds']:
            if build['disable']:
                apkfilename = app['id'] + '_' + str(build['vercode']) + '.apk'
                for repodir in repodirs:
                    apkpath = os.path.join(repodir, apkfilename)
                    srcpath = os.path.join(repodir, apkfilename[:-4] + "_src.tar.gz")
                    for name in [apkpath, srcpath]:
                        if os.path.exists(name):
                            logging.warn("Deleting disabled build output " + apkfilename)
                            os.remove(name)
                if apkfilename in apkcache:
                    del apkcache[apkfilename]


def resize_icon(iconpath, density):
    if not os.path.isfile(iconpath):
        return

    try:
        im = Image.open(iconpath)
        size = dpi_to_px(density)

        if any(length > size for length in im.size):
            oldsize = im.size
            im.thumbnail((size, size), Image.ANTIALIAS)
            logging.debug("%s was too large at %s - new size is %s" % (
                iconpath, oldsize, im.size))
            im.save(iconpath, "PNG")

    except Exception, e:
        logging.error("Failed resizing {0} - {1}".format(iconpath, e))


def resize_all_icons(repodirs):
    """Resize all icons that exceed the max size

    :param repodirs: the repo directories to process
    """
    for repodir in repodirs:
        for density in get_densities():
            icon_dir = get_icon_dir(repodir, density)
            icon_glob = os.path.join(icon_dir, '*.png')
            for iconpath in glob.glob(icon_glob):
                resize_icon(iconpath, density)


def scan_apks(repo_dir, knownapks, apkFile=None):
    icon_dirs = get_icon_dirs(repo_dir)
    for icon_dir in icon_dirs:
        if os.path.exists(icon_dir):
            if options.clean:
                shutil.rmtree(icon_dir)
                os.makedirs(icon_dir)
        else:
            os.makedirs(icon_dir)

    name_pat = re.compile(".*name='([a-zA-Z0-9._]*)'.*")
    vercode_pat = re.compile(".*versionCode='([0-9]*)'.*")
    vername_pat = re.compile(".*versionName='([^']*)'.*")
    label_pat = re.compile(".*label='(.*?)'(\n| [a-z]*?=).*")
    icon_pat = re.compile(".*application-icon-([0-9]+):'([^']+?)'.*")
    icon_pat_nodpi = re.compile(".*icon='([^']+?)'.*")
    sdkversion_pat = re.compile(".*'([0-9]*)'.*")
    string_pat = re.compile(".*'([^']*)'.*")

    apkfile = os.path.join(repo_dir, apkFile + '.apk')

    apkfilename = apkfile[len(repo_dir) + 1:]
    if ' ' in apkfilename:
        logging.critical("Spaces in filenames are not allowed.")
        sys.exit(1)

    logging.debug("Processing " + apkfilename)
    thisinfo = dict()
    thisinfo['apkname'] = apkfilename
    srcfilename = apkfilename[:-4] + "_src.tar.gz"
    if os.path.exists(os.path.join(repo_dir, srcfilename)):
        thisinfo['srcname'] = srcfilename
    thisinfo['size'] = os.path.getsize(apkfile)
    thisinfo['permissions'] = []
    thisinfo['features'] = []
    thisinfo['icons_src'] = {}
    thisinfo['icons'] = {}
    p = SilentPopen([config['aapt'], 'dump', 'badging', apkfile])
    if p.returncode != 0:
        if options.delete_unknown:
            if os.path.exists(apkfile):
                logging.error("Failed to get apk information, deleting " + apkfile)
                os.remove(apkfile)
            else:
                logging.error("Could not find {0} to remove it".format(apkfile))
        else:
            logging.error("Failed to get apk information, skipping " + apkfile)
        sys.exit(0)

    for line in p.output.splitlines():
        if line.startswith("package:"):
            try:
                thisinfo['id'] = re.match(name_pat, line).group(1)
                thisinfo['versioncode'] = int(re.match(vercode_pat, line).group(1))
                thisinfo['version'] = re.match(vername_pat, line).group(1)
            except Exception, e:
                logging.error("Package matching failed: " + str(e))
                logging.info("Line was: " + line)
                sys.exit(1)
        elif line.startswith("application:"):
            thisinfo['name'] = re.match(label_pat, line).group(1)
            # Keep path to non-dpi icon in case we need it
            match = re.match(icon_pat_nodpi, line)
            if match:
                thisinfo['icons_src']['-1'] = match.group(1)
        elif line.startswith("launchable-activity:"):
            # Only use launchable-activity as fallback to application
            if not thisinfo['name']:
                thisinfo['name'] = re.match(label_pat, line).group(1)
            if '-1' not in thisinfo['icons_src']:
                match = re.match(icon_pat_nodpi, line)
                if match:
                    thisinfo['icons_src']['-1'] = match.group(1)
        elif line.startswith("application-icon-"):
            match = re.match(icon_pat, line)
            if match:
                density = match.group(1)
                path = match.group(2)
                thisinfo['icons_src'][density] = path
        elif line.startswith("sdkVersion:"):
            m = re.match(sdkversion_pat, line)
            if m is None:
                logging.error(line.replace('sdkVersion:', '') + ' is not a valid minSdkVersion!')
            else:
                thisinfo['sdkversion'] = m.group(1)
        elif line.startswith("maxSdkVersion:"):
            thisinfo['maxsdkversion'] = re.match(sdkversion_pat, line).group(1)
        elif line.startswith("native-code:"):
            thisinfo['nativecode'] = []
            for arch in line[13:].split(' '):
                thisinfo['nativecode'].append(arch[1:-1])
        elif line.startswith("uses-permission:"):
            perm = re.match(string_pat, line).group(1)
            if perm.startswith("android.permission."):
                perm = perm[19:]
            thisinfo['permissions'].append(perm)
        elif line.startswith("uses-feature:"):
            perm = re.match(string_pat, line).group(1)
            # Filter out this, it's only added with the latest SDK tools and
            # causes problems for lots of apps.
            if perm != "android.hardware.screen.portrait" \
                    and perm != "android.hardware.screen.landscape":
                if perm.startswith("android.feature."):
                    perm = perm[16:]
                thisinfo['features'].append(perm)

    if 'sdkversion' not in thisinfo:
        logging.warn("no SDK version information found")
        thisinfo['sdkversion'] = 0

    # Check for debuggable apks...
    if common.isApkDebuggable(apkfile, config):
        logging.warn('{0} is set to android:debuggable="true"!'.format(apkfile))

    # Calculate the sha256...
    sha = hashlib.sha256()
    with open(apkfile, 'rb') as f:
        while True:
            t = f.read(1024)
            if len(t) == 0:
                break
            sha.update(t)
        thisinfo['sha256'] = sha.hexdigest()

    # Get the signature (or md5 of, to be precise)...
    getsig_dir = os.path.join(os.path.dirname(__file__), 'getsig')
    if not os.path.exists(getsig_dir + "/getsig.class"):
        logging.critical("getsig.class not found. To fix: cd '%s' && ./make.sh" % getsig_dir)
        sys.exit(1)
    p = FDroidPopen(['java', '-cp', os.path.join(os.path.dirname(__file__), 'getsig'),
                        'getsig', os.path.join(os.getcwd(), apkfile)])
    if p.returncode != 0 or not p.output.startswith('Result:'):
        logging.critical("Failed to get apk signature")
        sys.exit(1)
    thisinfo['sig'] = p.output[7:].strip()

    apk = zipfile.ZipFile(apkfile, 'r')

    iconfilename = "%s.%s.png" % (
        thisinfo['id'],
        thisinfo['versioncode'])

    # Extract the icon file...
    densities = get_densities()
    empty_densities = []
    for density in densities:
        if density not in thisinfo['icons_src']:
            empty_densities.append(density)
            continue
        iconsrc = thisinfo['icons_src'][density]
        icon_dir = get_icon_dir(repo_dir, density)
        icondest = os.path.join(icon_dir, iconfilename)

        try:
            iconfile = open(icondest, 'wb')
            iconfile.write(apk.read(iconsrc))
            iconfile.close()
            thisinfo['icons'][density] = iconfilename
        except:
            logging.warn("Error retrieving icon file")
            del thisinfo['icons'][density]
            del thisinfo['icons_src'][density]
            empty_densities.append(density)

    if '-1' in thisinfo['icons_src']:
        iconsrc = thisinfo['icons_src']['-1']
        iconpath = os.path.join(get_icon_dir(repo_dir, None), iconfilename)
        iconfile = open(iconpath, 'wb')
        iconfile.write(apk.read(iconsrc))
        iconfile.close()
        try:
            im = Image.open(iconpath)
            dpi = px_to_dpi(im.size[0])
            for density in densities:
                if density in thisinfo['icons']:
                    break
                if density == densities[-1] or dpi >= int(density):
                    thisinfo['icons'][density] = iconfilename
                    shutil.move(iconpath, os.path.join(get_icon_dir(repo_dir, density), iconfilename))
                    empty_densities.remove(density)
                    break
        except Exception, e:
            logging.warn("Failed reading {0} - {1}".format(iconpath, e))

    if thisinfo['icons']:
        thisinfo['icon'] = iconfilename

    apk.close()

    # First try resizing down to not lose quality
    last_density = None
    for density in densities:
        if density not in empty_densities:
            last_density = density
            continue
        if last_density is None:
            continue
        logging.debug("Density %s not available, resizing down from %s"
                    % (density, last_density))

        last_iconpath = os.path.join(get_icon_dir(repo_dir, last_density), iconfilename)
        iconpath = os.path.join(get_icon_dir(repo_dir, density), iconfilename)
        try:
            im = Image.open(last_iconpath)
        except:
            logging.warn("Invalid image file at %s" % last_iconpath)
            continue

        size = dpi_to_px(density)

        im.thumbnail((size, size), Image.ANTIALIAS)
        im.save(iconpath, "PNG")
        empty_densities.remove(density)

    # Then just copy from the highest resolution available
    last_density = None
    for density in reversed(densities):
        if density not in empty_densities:
            last_density = density
            continue
        if last_density is None:
            continue
        logging.debug("Density %s not available, copying from lower density %s" % (density, last_density))

        shutil.copyfile(
            os.path.join(get_icon_dir(repo_dir, last_density), iconfilename),
            os.path.join(get_icon_dir(repo_dir, density), iconfilename))

        empty_densities.remove(density)

    for density in densities:
        icon_dir = get_icon_dir(repo_dir, density)
        icondest = os.path.join(icon_dir, iconfilename)
        resize_icon(icondest, density)

    # Copy from icons-mdpi to icons since mdpi is the baseline density
    baseline = os.path.join(get_icon_dir(repo_dir, '160'), iconfilename)
    if os.path.isfile(baseline):
        shutil.copyfile(baseline,os.path.join(get_icon_dir(repo_dir, None), iconfilename))

    # Record in known apks, getting the added date at the same time..
    added = knownapks.recordapk(thisinfo['apkname'], thisinfo['id'])
    if added:
        thisinfo['added'] = added

    return thisinfo


repo_pubkey_fingerprint = None


from sen5 import sen5db
apps_db = sen5db.Sen5AppsDB()


def sen5_make_index(app, app_entry, apk, categories, repo=None):

    if app['Disabled'] is not None:
        return

    # Check for duplicates
    if app_entry:
        for apk_entry in app_entry['apks']:
            if apk_entry['vercode'] == apk['versioncode']:
                logging.critical("duplicate versions: '%s' - '%s'" % (apk_entry['apkname'], apk_entry['apkname']))
                sys.exit(1)

    if app_entry:
        application = app_entry
    else:
        application = dict()
    application['id'] = app['id']
    application['_id'] = app['id']

    if 'added' in app:
        application['added'] = time.strftime('%Y-%m-%d', app['added'])
    if 'lastupdated' in app:
        application['lastupdated'] = time.strftime('%Y-%m-%d', app['lastupdated'])
    application['name'] = app['Name']
    application['latestversion'] = app['latestversion']
    application['summary'] = app['Summary']
    if app['icon']:
        application['icon'] = app['icon']

    def linkres(link):
        if app['id'] == link:
            return ("fdroid.app:" + link, app['Name'])
        raise MetaDataException("Cannot resolve app id " + link)

    application['description'] = metadata.description_html(app['Description'], linkres)
    application['license'] = app['License']
    if 'Categories' in app:
        application['categories'] = ','.join(app["Categories"])
        # We put the first (primary) category in LAST, which will have
        # the desired effect of making clients that only understand one
        # category see that one.
        application['category'] = app["Categories"][0]

    application['webURL'] = app['Web Site']
    application['sourceURL'] = app['Source Code']
    application['trackerURL'] = app['Issue Tracker']

    if app['Donate']:
        application['donateURL'] = app['Donate']
    if app['Bitcoin']:
        application['bitcoinAddr'] = app['Bitcoin']
    if app['Litecoin']:
        application['litecoinAddr'] = app['Litecoin']
    if app['Dogecoin']:
        application['dogecoinAddr'] = app['Dogecoin']
    if app['FlattrID']:
        application['flattrID'] = app['FlattrID']

    # These elements actually refer to the current version (i.e. which
    # one is recommended. They are historically mis-named, and need
    # changing, but stay like this for now to support existing clients.
    application['marketversion'] = app['Current Version']
    application['marketvercode'] = int(app['Current Version Code'])

    if app['AntiFeatures']:
        af = app['AntiFeatures'].split(',')
        # TODO: Temporarily not including UpstreamNonFree in the index,
        # because current F-Droid clients do not understand it, and also
        # look ugly when they encounter an unknown antifeature. This
        # filtering can be removed in time...
        if 'UpstreamNonFree' in af:
            af.remove('UpstreamNonFree')
        if af:
            application['antifeatures'] = ','.join(af)

    if app['Provides']:
        pv = app['Provides'].split(',')
        application['provides'] = ','.join(pv)
    if app['Requires Root']:
        application['requirements'] = 'root'

    # pack apk
    package = dict()
    package['version'] = apk['version']
    package['vercode'] = apk['versioncode']
    package['apkname'] = str(apk['apkname'])

    if 'srcname' in apk:
        package['srcname'] = apk['srcname']
    for hash_type in ['sha256']:
        if hash_type not in apk:
            continue
        package['hashType'] = hash_type
        package['hash'] = apk[hash_type]
    package['sig'] = apk['sig']
    package['size'] = str(apk['size'])
    package['minSdkVersion'] = str(apk['sdkversion'])
    if 'maxsdkversion' in apk:
        package['maxSdkVersion'] = str(apk['maxsdkversion'])
    if 'added' in apk:
        package['added'] = time.strftime('%Y-%m-%d', apk['added'])
    if app['Requires Root']:
        if 'ACCESS_SUPERUSER' not in apk['permissions']:
            apk['permissions'].append('ACCESS_SUPERUSER')
    if len(apk['permissions']) > 0:
        package['permissions'] = ','.join(apk['permissions'])
    if 'nativecode' in apk and len(apk['nativecode']) > 0:
        package['nativecode'] = ','.join(apk['nativecode'])
    if len(apk['features']) > 0:
        package['features'] = ','.join(apk['features'])

    if not repo:
        if not 'repo' in application:
            if not apps_db.check_app_group_exist({'_id': 'common'}):
                apps_db.create_common_repository()
            application['repo'] = 'common'
    else:
        application['repo'] = repo

    if not 'score' in application:
        application['score'] = 0
    if not 'downloads' in application:
        application['downloads'] = 0
    if not 'marking' in application:
        application['marking'] = 0

    if not 'pictures' in application:
        application['pictures'] = []

    if 'apks' in application:
        application['apks'].append(package)
        #apps_db.add_apk(application['_id'], package)
        apps_db.update_app(application)
    else:
        application['apks'] = [package]
        apps_db.insert_app(application)


    # initialize dynamical data for the app
    # apps_db.init_scores(application['id'])


def repo_init(repo_dir):
    repo = dict()

    repo['_id'] = config['repo_name']
    repo['@name'] = config['repo_name']
    if config['repo_maxage'] != 0:
        repo['@maxage'] = str(config['repo_maxage'])
    repo['@icon'] = os.path.basename(config['repo_icon'])
    repo['@url'] = config['repo_url']
    repo['description'] = config['repo_description']

    repo['@version'] = 12
    repo['@timestamp'] = str(int(time.time()))

    apps_db.main_repo.insert(repo)

    # Copy the repo icon into the repo directory...
    icon_dir = os.path.join(repo_dir, 'icons')
    icon_file_name = os.path.join(icon_dir, os.path.basename(config['repo_icon']))
    shutil.copyfile(config['repo_icon'], icon_file_name)

    logging.info("The repository has been initialized.")


def archive_old_apks(apps, apks, archapks, repodir, archivedir, defaultkeepversions):
    for app in apps:

        # Get a list of the apks for this app...
        apklist = []
        for apk in apks:
            if apk['id'] == app['id']:
                apklist.append(apk)

        # Sort the apk list into version order...
        apklist = sorted(apklist, key=lambda apk: apk['versioncode'], reverse=True)

        if app['Archive Policy']:
            keepversions = int(app['Archive Policy'][:-9])
        else:
            keepversions = defaultkeepversions

        if len(apklist) > keepversions:
            for apk in apklist[keepversions:]:
                logging.info("Moving " + apk['apkname'] + " to archive")
                shutil.move(os.path.join(repodir, apk['apkname']),
                            os.path.join(archivedir, apk['apkname']))
                if 'srcname' in apk:
                    shutil.move(os.path.join(repodir, apk['srcname']),
                                os.path.join(archivedir, apk['srcname']))
                    # Move GPG signature too...
                    sigfile = apk['srcname'] + '.asc'
                    sigsrc = os.path.join(repodir, sigfile)
                    if os.path.exists(sigsrc):
                        shutil.move(sigsrc, os.path.join(archivedir, sigfile))

                archapks.append(apk)
                apks.remove(apk)


config = None
options = None


def update(apkfile):
    global config, options
    repodirs = 'repo'

    # Read known apks data (will be updated and written back when we've finished)
    knownapks = common.KnownApks()

    # Scan all apks in the main repo
    apk = scan_apks(repodirs, knownapks, apkfile)
    app = metadata.sen5_read_metadata(apk['id'])

    # Generate a list of categories...
    categories = set()
    categories.update(app['Categories'])

    app_entry = apps_db.find_app({'_id': app['id']})

    # query current latest version
    if not app_entry:
        app['added'] = apk['added']
        app['lastupdated'] = apk['added']
        if app['Name'] is None:
            app['Name'] = app['id']
        app['icon'] = apk['icon']
        app['latestversion'] = apk['versioncode']
    else:
        app['added'] = time.strptime(str(app_entry['added']), '%Y-%m-%d')
        last_updated = time.strptime(str(app_entry['lastupdated']), '%Y-%m-%d')
        if apk['added'] > last_updated:
            app['lastupdated'] = apk['added']
        else:
            app['lastupdated'] = last_updated
        if app_entry['latestversion'] > apk['versioncode']:
            app['Name'] = str(app_entry['name'])
            app['icon'] = str(app_entry['icon'])
            app['latestversion'] = app_entry['latestversion']
        else:
            if app['Name'] is None:
                app['Name'] = app['id']
            app['icon'] = apk['icon'] if 'icon' in apk else None
            app['latestversion'] = apk['versioncode']

    # Make the index for the main repo...
    sen5_make_index(app, app_entry, apk, categories, options.repo)

    if config['update_stats']:
        # Update known apks info...
        knownapks.writeifchanged()

        # Generate latest apps data for widget
        if os.path.exists(os.path.join('stats', 'latestapps.txt')):
            data = ''
            for line in file(os.path.join('stats', 'latestapps.txt')):
                appid = line.rstrip()
                data += appid + "\t"
                if app['id'] == appid:
                    data += app['Name'] + "\t"
                    if app['icon'] is not None:
                        data += app['icon'] + "\t"
                    data += app['License'] + "\n"
                    break
            f = open(os.path.join(repodirs, 'latestapps.dat'), 'w')
            f.write(data)
            f.close()

    # Update the wiki...
    #   if options.wiki:
    #       update_wiki(app, apk)

    logging.info("Finished.")


def main():
    global config, options

    # Parse command line...
    parser = OptionParser()
    parser.disable_interspersed_args()
    parser.add_option("-c", "--create-metadata", action="store_true", default=False,
                      help="Create skeleton metadata files that are missing")
    parser.add_option("--delete-unknown", action="store_true", default=False,
                      help="Delete APKs without metadata from the repo")
    parser.add_option("-v", "--verbose", action="store_true", default=False,
                      help="Spew out even more information than normal")
    parser.add_option("-q", "--quiet", action="store_true", default=False,
                      help="Restrict output to warnings and errors")
    parser.add_option("-b", "--buildreport", action="store_true", default=False,
                      help="Report on build data status")
    parser.add_option("-i", "--interactive", default=False, action="store_true",
                      help="Interactively ask about things that need updating.")
    parser.add_option("-I", "--icons", action="store_true", default=False,
                      help="Resize all the icons exceeding the max pixel size and exit")
    parser.add_option("-e", "--editor", default="/etc/alternatives/editor",
                      help="Specify editor to use in interactive mode. Default " +
                           "is /etc/alternatives/editor")
    parser.add_option("-w", "--wiki", default=False, action="store_true",
                      help="Update the wiki")
    parser.add_option("", "--pretty", action="store_true", default=False,
                      help="Produce human-readable index.xml")
    parser.add_option("--clean", action="store_true", default=False,
                      help="Clean update - don't uses caches, reprocess all apks")

    parser.add_option("--all", action="store_true", default=False, help="update all apks")
    parser.add_option("--apkFile", default=None, help="apk file")
    parser.add_option("--repo", default=None, help="repo name")
    parser.add_option("", "--init", default=False, action="store_true", help="repo init")

    (options, args) = parser.parse_args()

    config = common.read_config(options)

    repodirs = 'repo'
    if config['archive_older'] != 0:
        repodirs.append('archive')
        if not os.path.exists('archive'):
            os.mkdir('archive')

    if options.icons:
        resize_all_icons(repodirs)
        sys.exit(0)

    if options.init:
        repo_init(repodirs)
        sys.exit(0)

    # check that icons exist now, rather than fail at the end of `fdroid update`
    for k in ['repo_icon', 'archive_icon']:
        if k in config:
            if not os.path.exists(config[k]):
                logging.critical(k + ' "' + config[k] + '" does not exist! Correct it in config.py.')
                sys.exit(1)

    if options.all:
        apk_regex = re.compile("\.apk$")
        for apkfile in os.listdir(repodirs):
            if os.path.isfile(repodirs + '/' + apkfile) and apkfile[-4:] == '.apk':
                update(apkfile[:-4])
    else:
        if options.apkFile is None:
            logging.error(' apkFile not found')
            return
        else:
            update(options.apkFile)


if __name__ == "__main__":
    main()
