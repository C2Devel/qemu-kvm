#!/usr/bin/python
#
# Compares RHEL6 vmstate information for various machine types and
# src/dest qemu combinations.
#
# Assumes json files are in the format
#   rhelNN,rhelX.Y.0.json
# where NN is the RHEL release on which the json output was taken,
# and rhelX.Y.0 is the machine type for which the output was taken.
#
# Copyright 2014 Amit Shah <amit.shah@redhat.com>
# Copyright 2014 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <http://www.gnu.org/licenses/>.

from subprocess import call
import argparse
import os.path

count = 0

def bump_count():
    global count

    count = count + 1

def check_jsons(src, dest, machine):
    src_str = "rhel6" + str(src)
    dst_str = "rhel6" + str(dest)
    machine_str = "rhel6." + str(machine) + ".0"

    srcname = args.path + "/" + src_str + "," + machine_str + ".json"
    dstname = args.path + "/" + dst_str + "," + machine_str + ".json"

    if not os.path.isfile(dstname):
        return -1

    if not os.path.isfile(srcname):
        return -2

    print "Comparing", srcname, "with", dstname
    ret = call([args.cmd, "-s", srcname, "-d", dstname])
    if ret > 0:
        print "-->", ret, "errors comparing -M", machine_str,
        print "from", src_str, "to", dst_str
        print "--------------------------------------------------------"

    bump_count()
    return 0

def go_to_machines(src, dest):
    if args.machine is not "":
        if int(args.machine) > src:
            return 0
        return check_jsons(src, dest, int(args.machine))

    machine = -1
    ret = 0
    while machine < src and machine < dest and ret == 0:
        machine = machine + 1
        ret = check_jsons(src, dest, machine)

    return ret

def go_to_src(dest):
    if args.src is not "":
        src = int(args.src)
        if src == dest:
            return 0
        if src > dest and not args.backward:
            return 0
        return go_to_machines(src, dest)

    ret = 0
    src = -1
    while ret == 0:
        src = src + 1
        if src == dest:
            continue
        if src > dest and not args.backward:
            return 0
        ret = go_to_machines(src, dest)
        if ret == -2:
            return 0

    return ret

def check_all():
    if args.dest is not "":
        go_to_src(int(args.dest))
        return

    ret = 0
    dest = 0
    while ret == 0:
        ret = go_to_src(dest)
        dest = dest + 1


help_text="compare machine types"
parser = argparse.ArgumentParser(description=help_text)
parser.add_argument('-p', '--path', type=str, required=False,
                    default="tests/vmstate-static-checker-data",
                    help='directory that holds RHEL6 json files')
parser.add_argument('-c', '--cmd', type=str, required=False,
                    default="scripts/vmstate-static-checker.py",
                    help='path to vmstate-static-checker.py script')
parser.add_argument('-m', '--machine', type=str, required=False,
                    default="", help='machine type to compare; only provide the Y in RHELX.Y release, e.g. 3 for rhel-6.3.0')
parser.add_argument('-s', '--src', type=str, required=False,
                    default="", help='src qemu version to compare; only provide the Y in RHELX.Y release, e.g. 0 for rhel-6.0')
parser.add_argument('-d', '--dest', type=str, required=False,
                    default="", help='dest qemu version to compare; only provide the Y in RHELX.Y release, e.g. 5 for rhel-6.5')
parser.add_argument('-b', '--backward', required=False, default=False,
                    action='store_true',help="test backward migration as well")
args = parser.parse_args()

check_all()

print "Compared", count, "jsons",
if args.machine != "":
    print "for machine type rhel6." + str(args.machine) + ".0",
if args.src != "":
    print "for source rhel6." + str(args.src),
if args.dest != "":
    print "to dest rhel6." + str(args.dest),
if args.backward:
    print "with backward migration checking enabled",
