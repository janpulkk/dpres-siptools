"""Command line tool for creating mets"""

import os
import sys
import argparse
import datetime
import uuid
from shutil import copyfile
from scandir import scandir
import lxml.etree
import siptools.xml.mets as m
from siptools.xml.namespaces import NAMESPACES, METS_PROFILE, METS_CATALOG, \
    METS_SPECIFICATION
from siptools.xml.mets_record_status_types import RECORD_STATUS_TYPES
from siptools.utils import decode_path

def parse_arguments(arguments):
    """Parse arguments
    """
    parser = argparse.ArgumentParser(description="Tool for creating mets")
    parser.add_argument(
        'mets_profile', type=str, choices=METS_PROFILE,
        help='list of METS-profiles:%s' % METS_PROFILE)
    parser.add_argument(
        'organization_name', type=str, help='Creator name (organization)')
    parser.add_argument(
        '--objid', dest='objid', type=str, default=str(uuid.uuid4()),
        help='Organizations unique identifier for the package')
    parser.add_argument(
        '--label', dest='label', type=str,
        help='Short description of the information package')
    parser.add_argument(
        '--catalog', dest='catalog', default=METS_CATALOG, type=str,
        help='Version number of the NDL schema catalog used')
    parser.add_argument(
        '--specification', dest='specification', default=METS_SPECIFICATION,
        type=str, help='Version number of packaging specification used in '
                       'creation of data package')
    parser.add_argument(
        '--contentid', dest='contentid', type=str,
        help='Identifier for SIP Content')
    parser.add_argument(
        '--create_date', dest='create_date', type=str,
        default=datetime.datetime.utcnow().isoformat(),
        help='SIP create datetime yyyy-mm-ddThh:mm:ss')
    parser.add_argument(
        '--last_moddate', dest='last_moddate', type=str,
        help='Last modification datetime yyyy-mm-ddThh:mm:ss')
    parser.add_argument(
        '--record_status', dest='record_status', choices=RECORD_STATUS_TYPES,
        type=str, default='submission',
        help='list of record status types:%s' % RECORD_STATUS_TYPES)
    parser.add_argument(
        '--workspace', dest='workspace', type=str, default='./workspace',
        help="Workspace directory")
    parser.add_argument(
        '--clean', dest='clean', action='store_true', help='Workspace cleanup')
    parser.add_argument(
        '--copy_files', dest='copy_files', action='store_true', 
        help='Copy digital objects from base path to workspace')
    parser.add_argument(
        '--base_path', dest='base_path', type=str, default='./',
        help='Base path of the digital objects')    
    parser.add_argument('--stdout', help='Print output to stdout')

    return parser.parse_args(arguments)


def main(arguments=None):
    """The main method
    """
    args = parse_arguments(arguments)

    # Create mets header
    mets = m.mets_mets(METS_PROFILE[args.mets_profile], args.objid, args.label,
                       args.catalog, args.specification, args.contentid)
    metshdr = m.metshdr(args.organization_name, args.create_date,
                        args.last_moddate, args.record_status)
    mets.append(metshdr)

    # Collect elements from workspace XML files
    elements = []
    for entry in scandir(args.workspace):
        if not entry.name.startswith('mets.xml') and entry.is_file():
            element = lxml.etree.parse(entry.path).getroot()[0]
            elements.append(element)

    elements = m.merge_elements('{%s}amdSec' % NAMESPACES['mets'], elements)
    elements.sort(key=m.order)

    for element in elements:
        mets.append(element)

    if args.stdout:
        print m.serialize(mets)

    output_file = os.path.join(args.workspace, 'mets.xml')

    if not os.path.exists(os.path.dirname(output_file)):
        os.makedirs(os.path.dirname(output_file))

    with open(output_file, 'w+') as outfile:
        outfile.write(m.serialize(mets))

    print "compile_mets created file: %s" % output_file

    if args.copy_files != DEFAULT:
        copy_files(args.workspace, args.base_path)
        print "compile_mets copied objects from %s to workspace" % \
            args.base_path

    if args.clean:
        clean_metsparts(args.workspace)
        print "compile_mets cleaned work files from workspace"


    return 0


def clean_metsparts(path):
    """Clean mets parts from workspace
    """
    for root, _, files in os.walk(path, topdown=False):
        for name in files:
            if (name.endswith(('-techmd.xml', '-agent.xml', '-event.xml',
                               'dmdsec.xml', 'structmap.xml', 'filesec.xml'))):
                os.remove(os.path.join(root, name))


def copy_files(workspace, data_dir):
    """Copy digital objects to workspace
    """
    for entry in scandir(workspace):
        if entry.name.endswith('-techmd.xml') and entry.is_file():
            source = decode_path(entry.name, '-techmd.xml')
            target = os.path.join(workspace, source)
            if not os.path.exists(os.path.dirname(target)):
                os.makedirs(os.path.dirname(target))
            copyfile(os.path.join(data_dir, source), target)


if __name__ == '__main__':
    RETVAL = main()
    sys.exit(RETVAL)
