from pkg_resources import (resource_stream, resource_listdir)
from io import StringIO
import argparse
import datetime
import re
import os
import subprocess
import sys
import getpass


LICENSES = []
for file in sorted(resource_listdir(__name__, '.')):
    match = re.match(r'template-([a-z0-9_]+).txt', file)
    if match:
        LICENSES.append(match.groups()[0])

DEFAULT_LICENSE = "bsd3"


# To extend language formatting sopport with a new language, add an item in
# LANGS dict:
# "language_suffix":"comment_name"
# where "language_suffix" is the suffix of your language and "comment_name" is
# one of the comment types supported and listed in LANG_CMT:
# text : no comment
# c    : /* * */
# unix : #
# lua  : --- --

# if you want add a new comment type just add an item to LANG_CMT:
# "comment_name":[u'string', u'string', u'string']
# where the first string open multiline comment, second string comment every
# license's line and the last string close multiline comment,
# associate your language and source file suffix with your new comment type
# how explained above.
# EXAMPLE:
# LANG_CMT = {"c":[u'/*', u'*', u'*/']}
# LANGS = {"cpp":"c"}
# (for more examples see LANG_CMT and langs dicts below)
# NOTE: unicode (u) in comment strings is required.


LANGS = {"txt": "text", "h": "c", "hpp": "c", "c": "c", "cc": "c", "cpp": "c",
        "py": "unix", "pl": "perl", "sh": "unix", "lua": "lua", "rb": "ruby",
        "js": "c", "java": "java", "f": "fortran", "f90": "fortran90",
        "erl": "erlang", "html": "html", "css": "c", "m": "c"}

LANG_CMT = {"text": [u'', u'', u''], "c": [u'/*', u' *', u' */'], "unix": [u'', u'#', u''],
        "lua": [u'--[[', u'', u'--]]'], "java": [u'/**', u' *', u' */'],
        "perl": [u'=item', u'', u'=cut'], "ruby": [u'=begin', u'', u'=end'],
        "fortran": [u'C', u'C', u'C'], "fortran90": [u'!*', u'!*', u'!*'],
        "erlang": [u'%%', u'%', u'%%'], "html": [u'<!--', u'', u'-->']}


def clean_path(p):
    """ Clean a path by expanding user and environment variables and
        ensuring absolute path.
    """
    p = os.path.expanduser(p)
    p = os.path.expandvars(p)
    p = os.path.abspath(p)
    return p


def get_context(args):
    return {
        "year": args.year,
        "organization": args.organization,
        "project": args.project,
    }


def guess_organization():
    """ Guess the organization from `git config`. If that can't be found,
        fall back to $USER environment variable.
    """
    try:
        stdout = subprocess.check_output('git config --get user.name'.split())
        org = stdout.strip()
    except:
        org = getpass.getuser()
    return org.decode("UTF-8")


def load_file_template(path, lang):
    """ Load template from the specified filesystem path.
    """
    template = StringIO()
    if not os.path.exists(path):
        raise ValueError("path does not exist: %s" % path)
    with open(clean_path(path), "rb") as infile: # opened as binary
        template.write(LANG_CMT[LANGS[lang]][0] + u'\n')
        for line in infile:
            template.write(LANG_CMT[LANGS[lang]][1] + u' ')
            template.write(line.decode("utf-8")) # ensure utf-8 encoding
        template.write(LANG_CMT[LANGS[lang]][2] + u'\n')
    return template


def load_package_template(license, lang, header=False):
    """ Load license template distributed with package.
    """
    content = StringIO()
    filename = 'template-%s-header.txt' if header else 'template-%s.txt'
    with resource_stream(__name__, filename % license) as licfile:
        content.write(LANG_CMT[LANGS[lang]][0] + u'\n')
        for line in licfile:
            content.write(LANG_CMT[LANGS[lang]][1] + u' ')
            content.write(line.decode("utf-8"))
        content.write(LANG_CMT[LANGS[lang]][2] + u'\n')
    return content


def extract_vars(template):
    """ Extract variables from template. Variables are enclosed in
        double curly braces.
    """
    keys = set()
    for match in re.finditer(r"\{\{ (?P<key>\w+) \}\}", template.getvalue()):
        keys.add(match.groups()[0])
    return sorted(list(keys))


def generate_license(template, context):
    """ Generate a license by extracting variables from the template and
        replacing them with the corresponding values in the given context.
    """
    out = StringIO()
    content = template.getvalue()
    for key in extract_vars(template):
        if key not in context:
            raise ValueError("%s is missing from the template context" % key)
        content = content.replace("{{ %s }}" % key, context[key])
    template.close() # free template memory (when is garbage collected?)
    out.write(content)
    return out


def main():

    def valid_year(string):
        if not re.match(r"^\d{4}$", string):
            raise argparse.ArgumentTypeError("Must be a four digit year")
        return string

    parser = argparse.ArgumentParser(description='Generate a license')

    parser.add_argument('license', metavar='license', nargs="?", choices=LICENSES,
                       help='the license to generate, one of: %s' % ", ".join(LICENSES))
    parser.add_argument('--header', dest='header', action="store_true",
                       help='generate source file header for specified license')
    parser.add_argument('-o', '--org', dest='organization', default=guess_organization(),
                       help='organization, defaults to .gitconfig or os.environ["USER"]')
    parser.add_argument('-p', '--proj', dest='project', default=os.getcwd().split(os.sep)[-1],
                       help='name of project, defaults to name of current directory')
    parser.add_argument('-t', '--template', dest='template_path',
                       help='path to license template file')
    parser.add_argument('-y', '--year', dest='year', type=valid_year,
                       default="%i" % datetime.date.today().year,
                       help='copyright year')
    parser.add_argument('-l', '--language', dest='language', default='txt',
                       help='format output for language source file, one of: %s' % ", ".join(LANGS.keys()))
    parser.add_argument('-f', '--file', dest='ofile', default='stdout',
                       help='Name of the output source file (whitout extension, use -l instead)')
    parser.add_argument('--vars', dest='list_vars', action="store_true",
                       help='list template variables for specified license')

    args = parser.parse_args()

    # do license stuff

    license = args.license or DEFAULT_LICENSE

    # language

    lang = args.language

    # generate header if requested

    if args.header:

        if args.template_path:
            template = load_file_template(args.template_path, lang)
        else:
            try:
                template = load_package_template(license, lang, header=True)
            except IOError:
                sys.stderr.write("Sorry, no source headers are available for %s.\n" % args.license)
                sys.exit(1)

        content = generate_license(template, get_context(args))
        content.seek(0)
        sys.stdout.write(content.getvalue())
        content.close() # free content memory (paranoic memory stuff)
        sys.exit(0)

    # list template vars if requested

    if args.list_vars:

        context = get_context(args)

        if args.template_path:
            template = load_file_template(args.template_path, lang)
        else:
            template = load_package_template(license, lang)

        var_list = extract_vars(template)

        if var_list:
            sys.stdout.write("The %s license template contains the following variables and defaults:\n" % (args.template_path or license))
            for v in var_list:
                if v in context:
                    sys.stdout.write("  %s = %s\n" % (v, context[v]))
                else:
                    sys.stdout.write("  %s\n" % v)
        else:
            sys.stdout.write("The %s license template contains no variables.\n" % (args.template_path or license))

        sys.exit(0)

    # create context

    if args.template_path:
        template = load_file_template(args.template_path, lang)
    else:
        template = load_package_template(license, lang)

    content = generate_license(template, get_context(args))

    content.seek(0)
    if args.ofile != "stdout":
        output = "%s.%s" % (args.ofile, lang)
        with open(output, "w") as f:
            f.write(content.getvalue())
        f.close()
    else:
        sys.stdout.write(content.getvalue())
    content.close() # free content memory (paranoic memory stuff)

if __name__ == "__main__":
    main()

# vim: set ts=4 sw=4 tw=79 :
