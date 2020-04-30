"""
Utilities for siptools
"""
from __future__ import unicode_literals, print_function

import os
import sys
import json

import six

import mets
import xml_helpers
from siptools.utils import generate_digest, encode_path


def _parse_refs(ref):
    """A helper function to parse the given reference according
    to the type.
    """
    reference = ''
    if isinstance(ref, six.binary_type):
        reference = ref.decode(sys.getfilesystemencoding())
    elif isinstance(ref, six.text_type):
        reference = ref
    elif ref:
        reference = six.text_type(ref)

    return reference


def _uniques_list(reference_list, reference):
    """A helper function to append only unique values to a list."""
    set_list = set(reference_list)
    set_list.add(reference)

    return list(set_list)


class MetsSectionCreator(object):
    """
    Class for generating lxml.etree XML for different METS metadata sections
    and corresponing md-references files efficiently.
    """

    def __init__(self, workspace):
        """
        Initialize metadata creator.

        :workspace: Output path
        """
        self.workspace = workspace
        self.md_elements = []
        self.references = []

    # pylint: disable=too-many-arguments
    def add_reference(self, md_id, filepath, stream=None, directory=None):
        """
        Add metadata reference information to the references list, which is
        written into md-references after self.write() is called. md-references
        is read by the compile-structmap script when fileSec and structMap
        elements are created for lxml.etree XML.

        :md_id: ID of MD element to be referenced
        :filepath: path of the file linking to the MD element
        :stream: id of the stream linking to the MD element
        :directory: path of the directory linking to the MD element
        """
        references = {}
        references['md_id'] = md_id
        references['stream'] = stream

        references['path'] = filepath
        references['path_type'] = 'file'
        if directory:
            references['path'] = directory
            references['path_type'] = 'directory'

        self.references.append(references)

    def add_md(self,
               metadata,
               filename=None,
               stream=None,
               directory=None,
               given_metadata_dict=None):
        """
        Append metadata XML element into self.md_elements list.
        self.md_elements is read by write() function and all the elements
        are written into corresponding lxml.etree XML files.

        When write() is called write_md() automatically writes
        corresponding metadata to the same lxml.etree XML file. However,
        serializing and hashing the XML elements can be rather time consuming.
        If the metadata can be easily separated without serializing and
        hashing, this function should only be called once for each distinct
        metadata. This should be implemented by the subclasses of
        MetsSectionCreator.

        :metadata: Metadata XML element
        :filename: Path of the file linking to the MD element
        :stream: Stream index, or None if not a stream
        :directory: Path of the directory linking to the MD element
        :given_metadata_dict: Dict of file metadata
        """

        md_element = (
            metadata, filename, stream, directory, given_metadata_dict)
        self.md_elements.append(md_element)

    def write_references(self, ref_file):
        """
        Write "md-references.json" file, which is read by the
        compile-structmap script when fileSec and structMap elements are
        created for lxml.etree XML.
        """

        def _get_path_from_reference_file(ref_path):
            """An inner function to help read an existing JSON lines file.

            :param ref_path: The ref_path key to look for.
            :return: Dictionary on finding, None when none is found.
            """
            with open(reference_file, 'r') as out_file:
                for line in out_file:
                    try:
                        return json.loads(line)[ref_path]
                    except KeyError:
                        continue
            return None

        def _setup_new_path(path_type):
            """Sets up a new path dictionary. For cases when no prior path data
            is found among references.

            :param path_type: Path type in question in string.
            :return: Newly constructed dictionary.
            """
            return dict(
                path_type=path_type,
                streams=dict(),
                md_ids=list()
            )

        reference_file = os.path.join(self.workspace, ref_file)

        path_map = {}
        paths = []
        # Whether or not the file initially exists.
        file_exists = os.path.exists(reference_file)
        # Collection of paths that underwent an update.
        paths_updated = set()
        for ref in self.references:
            ref_path = _parse_refs(ref['path'])
            try:
                path = paths[path_map[ref_path]][ref_path]
            except KeyError:
                path = None
                if file_exists:
                    path = _get_path_from_reference_file(ref_path)
                    if path is not None:
                        paths_updated.add(ref_path)
                if path is None:
                    path = _setup_new_path(ref['path_type'])
                paths.append({ref_path: path})
                path_map[ref_path] = len(paths) - 1
            if ref['stream']:
                try:
                    stream_ids = _uniques_list(path['streams'][ref['stream']],
                                               ref['md_id'])
                except KeyError:
                    stream_ids = list()
                    stream_ids.append(ref['md_id'])
                path['streams'][ref['stream']] = stream_ids
            else:
                ids = _uniques_list(path['md_ids'], ref['md_id'])
                paths[path_map[ref_path]][ref_path]['md_ids'] = ids

        # Write reference list JSON line file
        if paths_updated:
            # Existing reference file must be updated.
            with open(reference_file, 'rt') as in_file, open(
                    '%s.tmp' % reference_file, 'at') as out_file:
                for line in in_file:
                    existing_json_data = json.loads(line)
                    for key in existing_json_data:
                        if key not in paths_updated:
                            out_file.write(line)

            for path in paths:
                with open('%s.tmp' % reference_file, 'at') as out_file:
                    json.dump(path, out_file)
                    out_file.write('\n')
        else:
            for path in paths:
                with open(reference_file, 'at') as out_file:
                    json.dump(path, out_file)
                    out_file.write('\n')

        if os.path.exists('%s.tmp' % reference_file):
            os.rename('%s.tmp' % reference_file, reference_file)

    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-locals
    def write_md(self, metadata, mdtype, mdtypeversion, othermdtype=None,
                 section=None, stdout=False):
        """
        Wraps XML metadata into MD element and writes it to a lxml.etree XML
        file in the workspace. The output filename is
            <mdtype>-<hash>-othermd.xml,
        where <mdtype> is the type of metadata given as parameter and <hash>
        is a string generated from the metadata.

        Serializing and hashing the root xml element can be rather time
        consuming and as such this method should not be called for each file
        unless more efficient way of separating files by the metadata can't
        be easily implemented. This implementation should be done by the
        subclasses of metadata_creator.

        :metadata (Element): metadata XML element
        :mdtype (string): Value of mdWrap MDTYPE attribute
        :mdtypeversion (string): Value of mdWrap MDTYPEVERSION attribute
        :othermdtype (string): Value of mdWrap OTHERMDTYPE attribute
        :section (string): Type of mets metadata section
        :stdout (boolean): Print also to stdout
        :returns: md_id, filename - Metadata id and filename
        """
        digest = generate_digest(metadata)
        suffix = othermdtype if othermdtype else mdtype
        filename = encode_path("%s-%s-amd.xml" % (digest, suffix))
        md_id = '_{}'.format(digest)
        filename = os.path.join(self.workspace, filename)

        if not os.path.exists(filename):

            xmldata = mets.xmldata()
            xmldata.append(metadata)
            mdwrap = mets.mdwrap(mdtype, mdtypeversion, othermdtype)
            mdwrap.append(xmldata)
            if section == 'digiprovmd':
                amd = mets.digiprovmd(md_id)
            else:
                amd = mets.techmd(md_id)
            amd.append(mdwrap)
            amdsec = mets.amdsec()
            amdsec.append(amd)
            mets_ = mets.mets()
            mets_.append(amdsec)

            with open(filename, 'wb+') as outfile:
                outfile.write(xml_helpers.utils.serialize(mets_))
                if stdout:
                    print(xml_helpers.utils.serialize(mets_).decode("utf-8"))
                print(
                    "Wrote lxml.etree %s administrative metadata to file "
                    "%s" % (mdtype, outfile.name)
                )

        return md_id, filename

    def write_dict(self, file_metadata_dict, premis_amd_id):
        """
        Write streams to a file for further scripts.

        :file_metadata_dict: File metadata dict
        :premis_amd_id: The AMDID of corresponding premis FILE object
        """
        digest = premis_amd_id[1:]
        filename = encode_path("%s-scraper.json" % digest)
        filename = os.path.join(self.workspace, filename)

        if not os.path.exists(filename):
            with open(filename, 'wt') as outfile:
                json.dump(file_metadata_dict, outfile)
            print("Wrote technical data to: %s" % (outfile.name))

    # pylint: disable=too-many-arguments
    def write(self, mdtype="type", mdtypeversion="version",
              othermdtype=None, section=None, stdout=False,
              file_metadata_dict=None, ref_file=None):
        """
        Write lxml.etree XML and md-reference files. First, METS XML files
        are written and self.references is appended. Second, md-references is
        written.

        If subclasses is optimized to call add_md once for each metadata type,
        self.references needs to be appended by the subclass for the instances
        where add_md was not called or write() function needs to be implemented
        differently.

        :mdtype (string): Value of mdWrap MDTYPE attribute
        :mdtypeversion (string): Value of mdWrap MDTYPEVERSION attribute
        :othermdtype (string): Value of mdWrap OTHERMDTYPE attribute
        :section (string): lxml.etree section type
        :stdout (boolean): Print also to stdout
        :file_metadat_dict (dict): File metadata dict
        :ref_file (string): Reference file name
        """
        # Write lxml.etree XML and append self.references
        for (metadata,
             filename,
             stream,
             directory,
             given_metadata_dict) in self.md_elements:
            md_id, _ = self.write_md(
                metadata, mdtype, mdtypeversion, othermdtype=othermdtype,
                section=section, stdout=stdout
            )
            if given_metadata_dict:
                file_metadata_dict = given_metadata_dict
            if file_metadata_dict and stream is None:
                self.write_dict(file_metadata_dict, md_id)
            self.add_reference(md_id, filename, stream, directory)

        # Write md-references
        self.write_references(ref_file)

        # Clear references and md_elements
        self.__init__(self.workspace)


def get_objectlist(refs_dict, file_path=None):
    """Get unique and sorted list of files or streams from
    md-references.json

    :refs_dict: Dictionary of objects
    :file_path: If given, finds streams of the given file.
                If None, finds a sorted list all file paths.
    :returns: Sorted list of files, or streams of a given file
    """
    objectset = set()
    if file_path is not None:
        for stream in refs_dict[file_path]['streams']:
            objectset.add(stream)
    elif refs_dict:
        for key, value in six.iteritems(refs_dict):
            if value['path_type'] == 'file':
                objectset.add(key)

    return sorted(objectset)


def remove_dmdsec_references(workspace):
    """
    Removes the reference to the dmdSecs in the md-references.json file.

    :workspace: Workspace path
    """
    refs_file = os.path.join(workspace,
                             'import-description-md-references.json')
    if os.path.exists(refs_file):
        os.remove(refs_file)


def read_all_amd_references(workspace):
    """
    Collect all administrative references.

    :workspace: path to workspace directory
    :returns: a set of administrative MD IDs
    """
    references = {}
    for ref_file in ["import-object-md-references.json",
                     "create-addml-md-references.json",
                     "create-audiomd-md-references.json",
                     "create-mix-md-references.json",
                     "create-videomd-md-references.json",
                     "premis-event-md-references.json"]:
        refs = read_md_references(workspace, ref_file)
        if refs:
            for ref in refs:
                if ref in references:
                    references[ref]['md_ids'].extend(refs[ref]['md_ids'])

                    for stream in refs[ref]['streams']:
                        if stream in references[ref]['streams']:
                            references[ref]['streams'][stream].extend(
                                refs[ref]['streams'][stream])
                        else:
                            references[ref]['streams'][stream] = \
                                refs[ref]['streams'][stream]

                else:
                    references[ref] = refs[ref]

    return references


def read_md_references(workspace, ref_file):
    """If MD reference file exists in workspace, read
    all the MD IDs as a dictionary.

    :workspace: path to workspace directory
    :ref_file: Metadata reference file
    :returns: Root of the reference tree
    """
    reference_file = os.path.join(workspace, ref_file)

    if os.path.isfile(reference_file):
        references = {}
        with open(reference_file) as in_file:
            for line in in_file:
                references.update(json.loads(line))
        return references
    return None


def get_md_references(refs_dict, path=None, stream=None, directory=None):
    """
    Return filtered references from a set of given references.
    :refs_dict: Dictionary of references to be filtered
    :path: Filter by given file path
    :stream: Filter by given strean index
    :directory: Filter by given directory path
    """
    if refs_dict is None:
        return None

    md_ids = []
    try:
        if directory is None and path is None and stream is None:
            for ref_path in refs_dict:
                md_ids.extend(refs_dict[ref_path]['md_ids'])
        elif directory:
            directory = os.path.normpath(directory)
            md_ids = refs_dict[directory]['md_ids']

        elif stream is None:
            md_ids = refs_dict[path]['md_ids']
        else:
            md_ref = refs_dict[path]
            for ref_stream in md_ref['streams']:
                if ref_stream == stream:
                    md_ids = md_ref['streams'][ref_stream]
    except KeyError:
        pass

    return set(md_ids)
