""" Test"""
from __future__ import unicode_literals

import os
import io

import pytest

import lxml.etree as ET
from siptools.scripts import import_description
from siptools.scripts.import_description import main
from siptools.utils import fsdecode_path


def get_md_file(path, input_target):
    """Get id"""
    ref = os.path.join(path, 'md-references.xml')

    root = ET.parse(ref).getroot()
    amdref = root.xpath("/mdReferences/mdReference"
                        "[@directory='%s']" % fsdecode_path(input_target))[0]
    output = os.path.join(path, amdref.text[1:] +
                          "-dmdsec.xml")
    return output


def test_import_description_valid_file(testpath, run_cli):
    """ Test case for single valid xml-file"""
    dmdsec_location = 'tests/data/import_description/metadata/' \
        'dc_description.xml'
    dmdsec_target = 'tests/data/structured'

    run_cli(main, [
        dmdsec_location, '--dmdsec_target', dmdsec_target,
        '--workspace', testpath, '--remove_root'])
    output = get_md_file(testpath, dmdsec_target)

    output_path = os.path.join(testpath, output)
    tree = ET.parse(output_path)
    root = tree.getroot()
    assert len(root.xpath('./*/*/*/*')) == 4
    assert root.xpath('./*/*/*/*')[0].tag == \
        '{http://purl.org/dc/elements/1.1/}title'


@pytest.mark.parametrize((
    'base_path', 'dmdsec_target', 'dmd_target'), [
        # No base_path
        ('.', 'tests/data/structured', 'tests/data/structured'),
        # No base_path or dmdsec_target, target is package root
        ('.', None, '.'),
        # No dmdsec_target, target is still package root
        ('tests/data', None, '.'),
        # Target is a directory
        ('tests/data/', 'structured', 'structured'),
        ])
def test_dmd_target_path(base_path, dmdsec_target, dmd_target):
    """Tests the dmd_target_path function."""
    out_target = import_description.dmd_target_path(
        base_path, dmdsec_target)

    assert out_target == dmd_target


def test_invalid_dmd_target_path():
    """Tests that event_target_path raises IOError if given
    event_target path doesn't exist.
    """
    with pytest.raises(IOError):
        import_description.dmd_target_path('.', 'foo/bar')


def test_import_description_file_not_found(testpath, run_cli):
    """ Test case for not existing xml-file."""
    dmdsec_location = 'tests/data/import_description/metadata/' \
        'dc_description_not_found.xml'
    dmdsec_target = 'tests/data/structured/'

    result = run_cli(main, [
        dmdsec_location, '--dmdsec_target', dmdsec_target,
        '--workspace', testpath],
        success=False)
    assert isinstance(result.exception, SystemExit)


def test_import_description_no_xml(testpath, run_cli):
    """ test case for invalid XML file """
    dmdsec_location = 'tests/data/import_description/plain_text.xml'
    dmdsec_target = 'tests/data/structured/'

    result = run_cli(main, [
        dmdsec_location, '--workspace', dmdsec_target,
        '--workspace', testpath],
        success=False)
    assert isinstance(result.exception, ET.XMLSyntaxError)


def test_import_description_invalid_namespace(testpath, run_cli):
    """ test case for invalid namespace in XML file """
    dmdsec_location = 'tests/data/import_description/dc_invalid_ns.xml'
    dmdsec_target = 'tests/data/structured/'

    result = run_cli(main, [
        dmdsec_location, '--workspace', dmdsec_target,
        '--workspace', testpath],
        success=False)
    assert isinstance(result.exception, TypeError)


@pytest.mark.parametrize("directory, base_path", [
    ("tests/data/audio", ""),
    ("./tests/data/audio", ""),
    ("audio", "tests/data"),
    ("./audio", "./tests/data"),
    ("data/audio", "absolute"),
    ("tests/data/audio/", ""),
    ("./tests/data/audio/", ""),
    ("audio/", "tests/data"),
    ("./audio/", "./tests/data"),
    ("data/audio/", "absolute")
])
def test_paths(testpath, directory, base_path, run_cli):
    """ Test the following path arguments:
    (1) Path without base_path
    (2) Path without base bath, but with "./"
    (3) Path with base path
    (4) Path with base path and with "./"
    (5) Absolute base path
    (6) Cases (1)-(5) with and without ending "/"
    """
    if "absolute" in base_path:
        base_path = os.path.join(os.getcwd(), "tests")
    if base_path != "":
        run_cli(import_description.main, [
            "--workspace", testpath, "--base_path", base_path,
            "--dmdsec_target", directory, "--remove_root",
            "tests/data/import_description/metadata/dc_description.xml"
        ])
    else:
        run_cli(import_description.main, [
            "--workspace", testpath, "--dmdsec_target", directory,
            "--remove_root",
            "tests/data/import_description/metadata/dc_description.xml"
        ])

    with io.open(os.path.join(testpath, "md-references.xml"), "rt") as md_ref:
        md_references = md_ref.read()

    assert 'directory=\"%s\"' % os.path.normpath(directory) in md_references
    assert os.path.isdir(os.path.normpath(os.path.join(base_path, directory)))
