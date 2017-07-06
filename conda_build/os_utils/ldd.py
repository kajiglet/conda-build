from __future__ import absolute_import, division, print_function

import sys
import re
import subprocess
from os.path import join, basename

from conda_build.conda_interface import memoized
from conda_build.conda_interface import untracked
from conda_build.conda_interface import linked_data

from conda_build import post
from conda_build.os_utils.macho import otool
from conda_build.os_utils.pyldd import inspect_linkages

LDD_RE = re.compile(r'\s*(.*?)\s*=>\s*(.*?)\s*\(.*\)')
LDD_NOT_FOUND_RE = re.compile(r'\s*(.*?)\s*=>\s*not found')


def ldd(path):
    "thin wrapper around ldd"
    lines = subprocess.check_output(['ldd', path]).decode('utf-8').splitlines()
    res = []
    for line in lines:
        if '=>' not in line:
            continue

        assert line[0] == '\t', (path, line)
        m = LDD_RE.match(line)
        if m:
            res.append(m.groups())
            continue
        m = LDD_NOT_FOUND_RE.match(line)
        if m:
            res.append((m.group(1), 'not found'))
            continue
        if 'ld-linux' in line:
            continue
        raise RuntimeError("Unexpected output from ldd: %s" % line)

    return res


@memoized
def get_linkages(obj_files, prefix, sysroot):
    res = {}

    for f in obj_files:
        path = join(prefix, f)
        # ldd quite often fails on foreign architectures.
        ldd_failed = False
        try:
            if sys.platform.startswith('linux'):
                res[f] = ldd(path)
            elif sys.platform.startswith('darwin'):
                links = otool(path)
                res[f] = [(basename(l['name']), l['name']) for l in links]
        except:
            ldd_failed = True
        finally:
            res_py = inspect_linkages(path, sysroot=sysroot)
            res_py = [(basename(lp), lp) for lp in res_py]
            print("set(res_py) {}".format(set(res_py)))
            if ldd_failed:
                res[f] = res_py
            else:
                print("set(res[f]) = {}".format(set(res[f])))
                if set(res[f]) != set(res_py):
                    print("WARNING: pyldd disagrees with ldd/otool. This will not cause any")
                    print("WARNING: problems for this build, but please file a bug at:")
                    print("WARNING: https://github.com/conda/conda-build")
                    print("WARNING: and (if possible) attach file {}".format(path))
                    print("WARNING: ldd/tool gives {}, pyldd gives {}"
                              .format(set(res[f]), set(res_py)))

    return res


@memoized
def get_package_obj_files(dist, prefix):
    data = linked_data(prefix).get(dist)

    res = []
    if data:
        for f in data.get('files', []):
            path = join(prefix, f)
            if post.is_obj(path):
                res.append(f)

    return res


@memoized
def get_untracked_obj_files(prefix):
    res = []
    files = untracked(prefix)
    for f in files:
        path = join(prefix, f)
        if post.is_obj(path):
            res.append(f)

    return res
