from __future__ import unicode_literals
# Splits the file and pull out attributes and sections

import os
import re
import six

import yaml

from . import utils
from . import mdsplit

ATTR_IDENTIFIER_RE = re.compile(r"^yaml .*@$")
ATTR_INLINE_RE = re.compile(r"`@{(.*?)}`")


class Section(object):
    TYPE = 'SECTION'

    def __init__(self, parent, header, attributes, sections, contents):
        self._parent = parent
        self.header = header
        self.attributes = attributes
        self.sections = sections
        self.contents = contents

    @classmethod
    def new(cls, parent, header):
        return cls(
            parent=parent,
            header=header,
            attributes={},
            sections=[],
            contents=[])

    def is_root(self):
        return self.header is None

    @classmethod
    def from_md(cls, filename, md_text):
        components = mdsplit.split(md_text)
        root = cls.new(None, None)
        current_section = root

        # Loop through the components, adding them to the correct section
        # and storing attributes.
        for cmt in components:
            if isinstance(cmt, mdsplit.Header):
                if current_section.is_root() or cmt.level < current_section.header.level:
                    parent = current_section
                else:
                    parent = current_section._parent

                new_section = Section.new(parent=parent, header=cmt)
                _append_section(current_section, new_section)
                current_section = new_section
            elif isinstance(cmt, mdsplit.Code):
                if cmt.is_attributes:
                    code_txt = '\n'.join(cmt.text)
                    current_section.update_attributes(yaml.safe_load(code_txt))
                current_section.contents.append(cmt)
            else:
                assert isinstance(cmt, mdsplit.Text)
                for line in cmt.raw:
                    for match in ATTR_INLINE_RE.finditer(line):
                        value = utils.to_unicode(yaml.safe_load(match.group(1)))
                        if isinstance(value, six.text_type):
                            value = {value: None}
                        current_section.update_attributes(value)

                current_section.contents.append(cmt)

        return root

    @classmethod
    def from_md_path(cls, path):
        filename = os.path.basename(path)
        with open(path) as f:
            return cls.from_md(filename, f.read())

    def to_dict(self):
        return {
            "type": self.TYPE,
            "header": self.header.to_dict() if self.header else None,
            "attributes": self.attributes,
            "sections": [s.to_dict() for s in self.sections],
            "contents": [c.to_dict() for c in self.contents],
        }

    @classmethod
    def from_dict(cls, dct):
        assert dct['type'] == cls.TYPE
        parent = dct.get('parent')
        section = cls(
            parent=None,
            header=dct['header'],
            attributes=dct['attributes'],
            sections=[Section.from_dict(s) for s in dct['sections']],
            contents=[mdsplit.from_dict(o) for o in dct['contents']])

        for child in section.sections:
            child._parent = section

        return section

    def update_attributes(self, attributes):
        utils.update_dict(self.attributes, attributes)

    def __eq__(self, other):
        return isinstance(other, self.__class__) and other._tuple() == self._tuple()

    def __repr__(self):
        return "Section(header={}, sections={})".format(self.header, self.sections)

    def _tuple(self):
        return (self.header, self.attributes, self.sections, self.contents)


def _append_section(last_section, section):
    """ Appends the section to the correct parent, based on the level.

    Called when digesting a list of sections.
    """

    assert section.header.level > 0
    if last_section.is_root() or section.header.level > last_section.header.level:
        last_section.sections.append(section)
    else:
        _append_section(last_section._parent, section)

