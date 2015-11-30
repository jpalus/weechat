# -*- coding: utf-8 -*-
#
# Copyright (C) 2008-2015 Sébastien Helleu <flashcode@flashtux.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

"""
Documentation generator for WeeChat: build include files with commands,
options, infos, infolists, hdata and completions for WeeChat core and
plugins.

Instructions to build config files yourself in WeeChat directories (replace
all paths with your path to WeeChat):
    1.  run WeeChat and load this script, with following command:
          /python load ~/src/weechat/doc/docgen.py
    2.  change path to build in your doc/ directory:
          /set plugins.var.python.docgen.path "~/src/weechat/doc"
    3.  run docgen command:
          /docgen
Note: it is recommended to load only this script when building doc.
Files should be in ~/src/weechat/doc/xx/autogen/ (where xx is language).
"""

from __future__ import print_function

SCRIPT_NAME = 'docgen'
SCRIPT_AUTHOR = 'Sébastien Helleu <flashcode@flashtux.org>'
SCRIPT_VERSION = '0.1'
SCRIPT_LICENSE = 'GPL3'
SCRIPT_DESC = 'Documentation generator for WeeChat'

SCRIPT_COMMAND = 'docgen'

IMPORT_OK = True

# pylint: disable=wrong-import-position
try:
    import gettext
    import hashlib
    import os
    import re
    from collections import defaultdict
    from operator import itemgetter
except ImportError as message:
    print('Missing package(s) for {0}: {1}'.format(SCRIPT_NAME, message))
    IMPORT_OK = False

try:
    import weechat  # pylint: disable=import-error
except ImportError:
    print('This script must be run under WeeChat.')
    print('Get WeeChat now at: https://weechat.org/')
    IMPORT_OK = False

# default path where doc files will be written (should be doc/ in sources
# package tree)
# path must have subdirectories with languages and autogen directory:
#      path
#       |-- en
#       |   |-- autogen
#       |-- fr
#       |   |-- autogen
#       ...
DEFAULT_PATH = '~/src/weechat/doc'

# list of locales for which we want to build doc files to include
LOCALE_LIST = ('en_US', 'fr_FR', 'it_IT', 'de_DE', 'ja_JP', 'pl_PL')

# all commands/options/.. of following plugins will produce a file
# non-listed plugins will be ignored
# value: "c" = plugin may have many commands
#        "o" = write config options for plugin
# if plugin is listed without "c", that means plugin has only one command
# /name (where "name" is name of plugin)
# Note: we consider core is a plugin called "weechat"
PLUGIN_LIST = {
    'sec': 'o',
    'weechat': 'co',
    'alias': '',
    'aspell': 'o',
    'charset': 'o',
    'exec': 'o',
    'fifo': 'o',
    'irc': 'co',
    'logger': 'o',
    'relay': 'o',
    'script': 'o',
    'perl': '',
    'python': '',
    'javascript': '',
    'ruby': '',
    'lua': '',
    'tcl': '',
    'guile': '',
    'trigger': 'o',
    'xfer': 'co',
}

# options to ignore
IGNORE_OPTIONS = (
    r'aspell\.dict\..*',
    r'aspell\.option\..*',
    r'charset\.decode\..*',
    r'charset\.encode\..*',
    r'irc\.msgbuffer\..*',
    r'irc\.ctcp\..*',
    r'irc\.ignore\..*',
    r'irc\.server\..*',
    r'jabber\.server\..*',
    r'logger\.level\..*',
    r'logger\.mask\..*',
    r'relay\.port\..*',
    r'trigger\.trigger\..*',
    r'weechat\.palette\..*',
    r'weechat\.proxy\..*',
    r'weechat\.bar\..*',
    r'weechat\.debug\..*',
    r'weechat\.notify\..*',
)

# completions to ignore
IGNORE_COMPLETIONS_ITEMS = (
    'docgen.*',
    'jabber.*',
    'weeget.*',
)


class AutogenDoc(object):
    """A class to write auto-generated doc files."""

    def __init__(self, directory, doc, name):
        """Initialize auto-generated doc file."""
        self.filename = os.path.join(directory, doc, name + '.asciidoc')
        self.filename_tmp = self.filename + '.tmp'
        self._file = open(self.filename_tmp, 'w')
        self.write('//\n')
        self.write('// This file is auto-generated by script docgen.py.\n')
        self.write('// DO NOT EDIT BY HAND!\n')
        self.write('//\n')

    def write(self, string):
        """Write a line in auto-generated doc file."""
        self._file.write(string)

    def update(self, obj_name, num_files, num_files_updated):
        """Update doc file if needed (if content has changed)."""
        # close temp file
        self._file.close()
        # compute checksum on old file
        try:
            with open(self.filename, 'r') as _file:
                shaold = hashlib.sha256(_file.read()).hexdigest()
        except IOError:
            shaold = ''
        # compute checksum on new (temp) file
        try:
            with open(self.filename_tmp, 'r') as _file:
                shanew = hashlib.sha256(_file.read()).hexdigest()
        except IOError:
            shanew = ''
        # compare checksums
        if shaold != shanew:
            # update doc file
            if os.path.exists(self.filename):
                os.unlink(self.filename)
            os.rename(self.filename_tmp, self.filename)
            num_files_updated['total1'] += 1
            num_files_updated['total2'] += 1
            num_files_updated[obj_name] += 1
        else:
            os.unlink(self.filename_tmp)
        # update counters
        num_files['total1'] += 1
        num_files['total2'] += 1
        num_files[obj_name] += 1


def get_commands():
    """
    Get list of WeeChat/plugins commands as dictionary with 3 indexes: plugin,
    command, xxx.
    """
    commands = defaultdict(lambda: defaultdict(defaultdict))
    infolist = weechat.infolist_get('hook', '', 'command')
    while weechat.infolist_next(infolist):
        plugin = weechat.infolist_string(infolist, 'plugin_name') or 'weechat'
        if plugin in PLUGIN_LIST:
            command = weechat.infolist_string(infolist, 'command')
            if command == plugin or 'c' in PLUGIN_LIST[plugin]:
                for key in ('description', 'args', 'args_description',
                            'completion'):
                    commands[plugin][command][key] = \
                        weechat.infolist_string(infolist, key)
    weechat.infolist_free(infolist)
    return commands


def get_options():
    """
    Get list of WeeChat/plugins config options as dictionary with 4 indexes:
    config, section, option, xxx.
    """
    options = \
        defaultdict(lambda: defaultdict(lambda: defaultdict(defaultdict)))
    infolist = weechat.infolist_get('option', '', '')
    while weechat.infolist_next(infolist):
        full_name = weechat.infolist_string(infolist, 'full_name')
        if not re.search('|'.join(IGNORE_OPTIONS), full_name):
            config = weechat.infolist_string(infolist, 'config_name')
            if config in PLUGIN_LIST and 'o' in PLUGIN_LIST[config]:
                section = weechat.infolist_string(infolist, 'section_name')
                option = weechat.infolist_string(infolist, 'option_name')
                for key in ('type', 'string_values', 'default_value',
                            'description'):
                    options[config][section][option][key] = \
                        weechat.infolist_string(infolist, key)
                for key in ('min', 'max', 'null_value_allowed'):
                    options[config][section][option][key] = \
                        weechat.infolist_integer(infolist, key)
    weechat.infolist_free(infolist)
    return options


def get_infos():
    """
    Get list of WeeChat/plugins infos as dictionary with 3 indexes: plugin,
    name, xxx.
    """
    infos = defaultdict(lambda: defaultdict(defaultdict))
    infolist = weechat.infolist_get('hook', '', 'info')
    while weechat.infolist_next(infolist):
        info_name = weechat.infolist_string(infolist, 'info_name')
        plugin = weechat.infolist_string(infolist, 'plugin_name') or 'weechat'
        for key in ('description', 'args_description'):
            infos[plugin][info_name][key] = \
                weechat.infolist_string(infolist, key)
    weechat.infolist_free(infolist)
    return infos


def get_infos_hashtable():
    """
    Get list of WeeChat/plugins infos (hashtable) as dictionary with 3 indexes:
    plugin, name, xxx.
    """
    infos_hashtable = defaultdict(lambda: defaultdict(defaultdict))
    infolist = weechat.infolist_get('hook', '', 'info_hashtable')
    while weechat.infolist_next(infolist):
        info_name = weechat.infolist_string(infolist, 'info_name')
        plugin = weechat.infolist_string(infolist, 'plugin_name') or 'weechat'
        for key in ('description', 'args_description', 'output_description'):
            infos_hashtable[plugin][info_name][key] = \
                weechat.infolist_string(infolist, key)
    weechat.infolist_free(infolist)
    return infos_hashtable


def get_infolists():
    """
    Get list of WeeChat/plugins infolists as dictionary with 3 indexes: plugin,
    name, xxx.
    """
    infolists = defaultdict(lambda: defaultdict(defaultdict))
    infolist = weechat.infolist_get('hook', '', 'infolist')
    while weechat.infolist_next(infolist):
        infolist_name = weechat.infolist_string(infolist, 'infolist_name')
        plugin = weechat.infolist_string(infolist, 'plugin_name') or 'weechat'
        for key in ('description', 'pointer_description', 'args_description'):
            infolists[plugin][infolist_name][key] = \
                weechat.infolist_string(infolist, key)
    weechat.infolist_free(infolist)
    return infolists


# pylint: disable=too-many-locals
def get_hdata():
    """
    Get list of WeeChat/plugins hdata as dictionary with 3 indexes: plugin,
    name, xxx.
    """
    hdata = defaultdict(lambda: defaultdict(defaultdict))
    infolist = weechat.infolist_get('hook', '', 'hdata')
    while weechat.infolist_next(infolist):
        hdata_name = weechat.infolist_string(infolist, 'hdata_name')
        plugin = weechat.infolist_string(infolist, 'plugin_name') or 'weechat'
        hdata[plugin][hdata_name]['description'] = \
            weechat.infolist_string(infolist, 'description')
        variables = ''
        variables_update = ''
        lists = ''
        ptr_hdata = weechat.hdata_get(hdata_name)
        if ptr_hdata:
            hdata2 = []
            string = weechat.hdata_get_string(ptr_hdata, 'var_keys_values')
            if string:
                for item in string.split(','):
                    key = item.split(':')[0]
                    var_offset = weechat.hdata_get_var_offset(ptr_hdata, key)
                    var_array_size = \
                        weechat.hdata_get_var_array_size_string(ptr_hdata, '',
                                                                key)
                    if var_array_size:
                        var_array_size = \
                            ', array_size: "{0}"'.format(var_array_size)
                    var_hdata = weechat.hdata_get_var_hdata(ptr_hdata, key)
                    if var_hdata:
                        var_hdata = ', hdata: "{0}"'.format(var_hdata)
                    type_string = weechat.hdata_get_var_type_string(ptr_hdata,
                                                                    key)
                    hdata2.append({
                        'offset': var_offset,
                        'text': '\'{0}\' ({1})'.format(key, type_string),
                        'textlong': '\'{0}\' ({1}{2}{3})'.format(
                            key, type_string, var_array_size, var_hdata),
                        'update': weechat.hdata_update(
                            ptr_hdata, '', {'__update_allowed': key}),
                    })
                hdata2 = sorted(hdata2, key=itemgetter('offset'))
                for item in hdata2:
                    variables += '*** {0}\n'.format(item['textlong'])
                    if item['update']:
                        variables_update += '*** {0}\n'.format(item['text'])
                if weechat.hdata_update(ptr_hdata, '',
                                        {'__create_allowed': ''}):
                    variables_update += '*** \'__create\'\n'
                if weechat.hdata_update(ptr_hdata, '',
                                        {'__delete_allowed': ''}):
                    variables_update += '*** \'__delete\'\n'
            hdata[plugin][hdata_name]['vars'] = variables
            hdata[plugin][hdata_name]['vars_update'] = variables_update

            string = weechat.hdata_get_string(ptr_hdata, 'list_keys')
            if string:
                for item in sorted(string.split(',')):
                    lists += '*** \'{0}\'\n'.format(item)
            hdata[plugin][hdata_name]['lists'] = lists
    weechat.infolist_free(infolist)
    return hdata


def get_completions():
    """
    Get list of WeeChat/plugins completions as dictionary with 3 indexes:
    plugin, item, xxx.
    """
    completions = defaultdict(lambda: defaultdict(defaultdict))
    infolist = weechat.infolist_get('hook', '', 'completion')
    while weechat.infolist_next(infolist):
        completion_item = weechat.infolist_string(infolist, 'completion_item')
        if not re.search('|'.join(IGNORE_COMPLETIONS_ITEMS), completion_item):
            plugin = weechat.infolist_string(infolist, 'plugin_name') or \
                'weechat'
            completions[plugin][completion_item]['description'] = \
                weechat.infolist_string(infolist, 'description')
    weechat.infolist_free(infolist)
    return completions


def get_url_options():
    """
    Get list of URL options as list of dictionaries.
    """
    url_options = []
    infolist = weechat.infolist_get('url_options', '', '')
    while weechat.infolist_next(infolist):
        url_options.append({
            'name': weechat.infolist_string(infolist, 'name').lower(),
            'option': weechat.infolist_integer(infolist, 'option'),
            'type': weechat.infolist_string(infolist, 'type'),
            'constants': weechat.infolist_string(
                infolist, 'constants').lower().replace(',', ', ')
        })
    weechat.infolist_free(infolist)
    return url_options


def get_irc_colors():
    """
    Get list of IRC colors as list of dictionaries.
    """
    irc_colors = []
    infolist = weechat.infolist_get('irc_color_weechat', '', '')
    while weechat.infolist_next(infolist):
        irc_colors.append({
            'color_irc': weechat.infolist_string(infolist, 'color_irc'),
            'color_weechat': weechat.infolist_string(infolist,
                                                     'color_weechat'),
        })
    weechat.infolist_free(infolist)
    return irc_colors


def get_plugins_priority():
    """
    Get priority of default WeeChat plugins as a dictionary.
    """
    plugins_priority = {}
    infolist = weechat.infolist_get('plugin', '', '')
    while weechat.infolist_next(infolist):
        name = weechat.infolist_string(infolist, 'name')
        priority = weechat.infolist_integer(infolist, 'priority')
        if priority in plugins_priority:
            plugins_priority[priority].append(name)
        else:
            plugins_priority[priority] = [name]
    weechat.infolist_free(infolist)
    return plugins_priority


# pylint: disable=too-many-locals, too-many-branches, too-many-statements
# pylint: disable=too-many-nested-blocks
def docgen_cmd_cb(data, buf, args):
    """Callback for /docgen command."""
    if args:
        locales = args.split(' ')
    else:
        locales = LOCALE_LIST
    commands = get_commands()
    options = get_options()
    infos = get_infos()
    infos_hashtable = get_infos_hashtable()
    infolists = get_infolists()
    hdata = get_hdata()
    completions = get_completions()
    url_options = get_url_options()
    irc_colors = get_irc_colors()
    plugins_priority = get_plugins_priority()

    # get path and replace ~ by home if needed
    path = weechat.config_get_plugin('path')
    if path.startswith('~'):
        path = os.environ['HOME'] + path[1:]

    # write to doc files, by locale
    num_files = defaultdict(int)
    num_files_updated = defaultdict(int)

    # pylint: disable=undefined-variable
    translate = lambda s: (s and _(s)) or s
    escape = lambda s: s.replace('|', '\\|')

    for locale in locales:
        for key in num_files:
            if key != 'total2':
                num_files[key] = 0
                num_files_updated[key] = 0
        trans = gettext.translation('weechat',
                                    weechat.info_get('weechat_localedir', ''),
                                    languages=[locale + '.UTF-8'],
                                    fallback=True)
        trans.install()
        directory = path + '/' + locale[0:2] + '/autogen'
        if not os.path.isdir(directory):
            weechat.prnt('',
                         '{0}docgen error: directory "{1}" does not exist'
                         ''.format(weechat.prefix('error'), directory))
            continue

        # write commands
        for plugin in commands:
            doc = AutogenDoc(directory, 'user', plugin + '_commands')
            for i, command in enumerate(sorted(commands[plugin])):
                if i > 0:
                    doc.write('\n')
                _cmd = commands[plugin][command]
                args = translate(_cmd['args'])
                args_formats = args.split(' || ')
                desc = translate(_cmd['description'])
                args_desc = translate(_cmd['args_description'])
                doc.write('[[command_{0}_{1}]]\n'.format(plugin, command))
                doc.write('[command]*`{0}`* {1}::\n\n'.format(command, desc))
                doc.write('----\n')
                prefix = '/' + command + '  '
                if args_formats != ['']:
                    for fmt in args_formats:
                        doc.write(prefix + fmt + '\n')
                        prefix = ' ' * len(prefix)
                if args_desc:
                    doc.write('\n')
                    for line in args_desc.split('\n'):
                        doc.write(line + '\n')
                doc.write('----\n')
            doc.update('commands', num_files, num_files_updated)

        # write config options
        for config in options:
            doc = AutogenDoc(directory, 'user', config + '_options')
            i = 0
            for section in sorted(options[config]):
                for option in sorted(options[config][section]):
                    if i > 0:
                        doc.write('\n')
                    i += 1
                    _opt = options[config][section][option]
                    opt_type = _opt['type']
                    string_values = _opt['string_values']
                    default_value = _opt['default_value']
                    opt_min = _opt['min']
                    opt_max = _opt['max']
                    null_value_allowed = _opt['null_value_allowed']
                    desc = translate(_opt['description'])
                    type_nls = translate(opt_type)
                    values = ''
                    if opt_type == 'boolean':
                        values = 'on, off'
                    elif opt_type == 'integer':
                        if string_values:
                            values = string_values.replace('|', ', ')
                        else:
                            values = '{0} .. {1}'.format(opt_min, opt_max)
                    elif opt_type == 'string':
                        if opt_max <= 0:
                            values = _('any string')
                        elif opt_max == 1:
                            values = _('any char')
                        elif opt_max > 1:
                            values = '{0} ({1}: {2})'.format(_('any string'),
                                                             _('max chars'),
                                                             opt_max)
                        else:
                            values = _('any string')
                        default_value = '"{0}"'.format(
                            default_value.replace('"', '\\"'))
                    elif opt_type == 'color':
                        values = _('a WeeChat color name (default, black, '
                                   '(dark)gray, white, (light)red, '
                                   '(light)green, brown, yellow, (light)blue, '
                                   '(light)magenta, (light)cyan), a terminal '
                                   'color number or an alias; attributes are '
                                   'allowed before color (for text color '
                                   'only, not background): \"*\" for bold, '
                                   '\"!\" for reverse, \"/\" for italic, '
                                   '\"_\" for underline')
                    doc.write('* [[option_{0}.{1}.{2}]] *{3}.{4}.{5}*\n'
                              ''.format(config, section, option, config,
                                        section, option))
                    doc.write('** {0}: `{1}`\n'.format(_('description'), desc))
                    doc.write('** {0}: {1}\n'.format(_('type'), type_nls))
                    doc.write('** {0}: {1} ({2}: `{3}`)\n'
                              ''.format(_('values'), values,
                                        _('default value'), default_value))
                    if null_value_allowed:
                        doc.write('** {0}\n'.format(
                            _('undefined value allowed (null)')))
            doc.update('options', num_files, num_files_updated)

        # write IRC colors
        doc = AutogenDoc(directory, 'user', 'irc_colors')
        doc.write('[width="30%",cols="^2m,3",options="header"]\n')
        doc.write('|===\n')
        doc.write('| {0} | {1}\n\n'
                  ''.format(_('IRC color'), _('WeeChat color')))
        for color in irc_colors:
            doc.write('| {0} | {1}\n'
                      ''.format(escape(color['color_irc']),
                                escape(color['color_weechat'])))
        doc.write('|===\n')
        doc.update('irc_colors', num_files, num_files_updated)

        # write infos hooked
        doc = AutogenDoc(directory, 'plugin_api', 'infos')
        doc.write('[width="100%",cols="^1,^2,6,6",options="header"]\n')
        doc.write('|===\n')
        doc.write('| {0} | {1} | {2} | {3}\n\n'
                  ''.format(_('Plugin'), _('Name'), _('Description'),
                            _('Arguments')))
        for plugin in sorted(infos):
            for info in sorted(infos[plugin]):
                _inf = infos[plugin][info]
                desc = translate(_inf['description'])
                args_desc = translate(_inf['args_description'] or '-')
                doc.write('| {0} | {1} | {2} | {3}\n\n'
                          ''.format(escape(plugin), escape(info),
                                    escape(desc), escape(args_desc)))
        doc.write('|===\n')
        doc.update('infos', num_files, num_files_updated)

        # write infos (hashtable) hooked
        doc = AutogenDoc(directory, 'plugin_api', 'infos_hashtable')
        doc.write('[width="100%",cols="^1,^2,6,6,6",options="header"]\n')
        doc.write('|===\n')
        doc.write('| {0} | {1} | {2} | {3} | {4}\n\n'
                  ''.format(_('Plugin'), _('Name'), _('Description'),
                            _('Hashtable (input)'), _('Hashtable (output)')))
        for plugin in sorted(infos_hashtable):
            for info in sorted(infos_hashtable[plugin]):
                _inh = infos_hashtable[plugin][info]
                desc = translate(_inh['description'])
                args_desc = translate(_inh['args_description'])
                output_desc = translate(_inh['output_description']) or '-'
                doc.write('| {0} | {1} | {2} | {3} | {4}\n\n'
                          ''.format(escape(plugin), escape(info),
                                    escape(desc), escape(args_desc),
                                    escape(output_desc)))
        doc.write('|===\n')
        doc.update('infos_hashtable', num_files, num_files_updated)

        # write infolists hooked
        doc = AutogenDoc(directory, 'plugin_api', 'infolists')
        doc.write('[width="100%",cols="^1,^2,5,5,5",options="header"]\n')
        doc.write('|===\n')
        doc.write('| {0} | {1} | {2} | {3} | {4}\n\n'
                  ''.format(_('Plugin'), _('Name'), _('Description'),
                            _('Pointer'), _('Arguments')))
        for plugin in sorted(infolists):
            for infolist in sorted(infolists[plugin]):
                _inl = infolists[plugin][infolist]
                desc = translate(_inl['description'])
                pointer_desc = translate(_inl['pointer_description']) or '-'
                args_desc = translate(_inl['args_description']) or '-'
                doc.write('| {0} | {1} | {2} | {3} | {4}\n\n'
                          ''.format(escape(plugin), escape(infolist),
                                    escape(desc), escape(pointer_desc),
                                    escape(args_desc)))
        doc.write('|===\n')
        doc.update('infolists', num_files, num_files_updated)

        # write hdata hooked
        doc = AutogenDoc(directory, 'plugin_api', 'hdata')
        for plugin in sorted(hdata):
            for hdata_name in sorted(hdata[plugin]):
                anchor = 'hdata_{0}'.format(hdata_name)
                _hda = hdata[plugin][hdata_name]
                desc = translate(_hda['description'])
                variables = _hda['vars']
                variables_update = _hda['vars_update']
                lists = _hda['lists']
                doc.write('* [[{0}]]<<{0},\'{1}\'>>: {2}\n'
                          ''.format(escape(anchor), escape(hdata_name),
                                    escape(desc)))
                doc.write('** {0}: {1}\n'.format(_('plugin'),
                                                 escape(plugin)))
                doc.write('** {0}:\n{1}'.format(_('variables'),
                                                escape(variables)))
                if variables_update:
                    doc.write('** {0}:\n{1}'.format(
                        _('update allowed'),
                        escape(variables_update)))
                if lists:
                    doc.write('** {0}:\n{1}'.format(_('lists'),
                                                    escape(lists)))
        doc.update('hdata', num_files, num_files_updated)

        # write completions hooked
        doc = AutogenDoc(directory, 'plugin_api', 'completions')
        doc.write('[width="65%",cols="^1,^2,8",options="header"]\n')
        doc.write('|===\n')
        doc.write('| {0} | {1} | {2}\n\n'
                  ''.format(_('Plugin'), _('Name'), _('Description')))
        for plugin in sorted(completions):
            for completion_item in sorted(completions[plugin]):
                _cmp = completions[plugin][completion_item]
                desc = translate(_cmp['description'])
                doc.write('| {0} | {1} | {2}\n\n'
                          ''.format(escape(plugin), escape(completion_item),
                                    escape(desc)))
        doc.write('|===\n')
        doc.update('completions', num_files, num_files_updated)

        # write url options
        doc = AutogenDoc(directory, 'plugin_api', 'url_options')
        doc.write('[width="100%",cols="2,^1,7",options="header"]\n')
        doc.write('|===\n')
        doc.write('| {0} | {1} | {2}\n\n'
                  ''.format(_('Option'), _('Type'),
                            _('Constants') + ' ^(1)^'))
        for option in url_options:
            constants = option['constants']
            if constants:
                constants = ' ' + constants
            doc.write('| {0} | {1} |{2}\n\n'
                      ''.format(escape(option['name']),
                                escape(option['type']),
                                escape(constants)))
        doc.write('|===\n')
        doc.update('url_options', num_files, num_files_updated)

        # write plugins priority
        doc = AutogenDoc(directory, 'plugin_api', 'plugins_priority')
        for priority in sorted(plugins_priority, reverse=True):
            plugins = ', '.join(sorted(plugins_priority[priority]))
            doc.write('. {0} ({1})\n'.format(escape(plugins), priority))
        doc.update('plugins_priority', num_files, num_files_updated)

        # write counters
        weechat.prnt('',
                     'docgen: {0}: {1} files, {2} updated'
                     ''.format(locale,
                               num_files['total1'],
                               num_files_updated['total1']))
    weechat.prnt('',
                 'docgen: total: {0} files, {1} updated'
                 ''.format(num_files['total2'], num_files_updated['total2']))
    return weechat.WEECHAT_RC_OK


def docgen_completion_cb(data, completion_item, buf, completion):
    """Callback for completion."""
    for locale in LOCALE_LIST:
        weechat.hook_completion_list_add(completion, locale, 0,
                                         weechat.WEECHAT_LIST_POS_SORT)
    return weechat.WEECHAT_RC_OK


if __name__ == '__main__' and IMPORT_OK:
    if weechat.register(SCRIPT_NAME, SCRIPT_AUTHOR, SCRIPT_VERSION,
                        SCRIPT_LICENSE, SCRIPT_DESC, '', ''):
        weechat.hook_command(SCRIPT_COMMAND,
                             'Documentation generator.',
                             '[locales]',
                             'locales: list of locales to build (by default '
                             'build all locales)',
                             '%(docgen_locales)|%*',
                             'docgen_cmd_cb', '')
        weechat.hook_completion('docgen_locales', 'locales for docgen',
                                'docgen_completion_cb', '')
        if not weechat.config_is_set_plugin('path'):
            weechat.config_set_plugin('path', DEFAULT_PATH)
